"""Reproducible research sampling of videos and comments.

Sampling is transparent: every call records the exact criteria used
(strategy, size, seed, strata) in ``criteria_json`` so samples can be audited
and reproduced. Videos whose ranking metric is unavailable (no observation,
no duration, ...) are ranked last and reported in ``missing_metric_count`` -
never fabricated or silently dropped.

Strategies implemented follow :class:`SamplingStrategy`. Comment sampling
supports only the strategies that are meaningful for comments
(``TOP_LIKES``, ``RANDOM``, ``STRATIFIED``, ``LATEST``, ``EARLIEST``,
``DATE_RANGE``); requesting a video-only strategy for comments raises
:class:`UnsupportedSamplingError` instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from random import Random
from typing import Callable, Iterable

from SocialScienceResearch.domain.enums import SamplingStrategy
from SocialScienceResearch.domain.models import Comment, Video
from SocialScienceResearch.domain.query import SamplingSpec, AdvancedSamplingSpec
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.statistics_service import StatisticsService
from SocialScienceResearch.utils.idgen import utcnow


class SamplingError(Exception):
    """Base error for sampling problems."""


class UnsupportedSamplingError(SamplingError):
    """A strategy was requested for an entity type it does not apply to."""


@dataclass
class SamplingResult:
    """Outcome of a reproducible sampling operation."""

    strategy: SamplingStrategy
    entity_type: str  # 'video' | 'comment'
    population_size: int
    sample_size: int
    entity_ids: list[str] = field(default_factory=list)
    criteria_json: dict = field(default_factory=dict)
    seed: int | None = None
    missing_metric_count: int = 0


class SamplingService:
    """Applies explicit, reproducible sampling strategies to the corpus."""

    def __init__(self, repos: Repositories, default_seed: int = 42) -> None:
        self._repos = repos
        self._default_seed = default_seed

    # ------------------------------------------------------------------
    # Videos
    # ------------------------------------------------------------------
    def sample_videos(
        self,
        channel_id: str,
        spec: SamplingSpec,
    ) -> SamplingResult:
        """Sample videos of a channel using ``spec.strategy``."""
        videos = self._repos.videos.list_videos(channel_id=channel_id)
        latest_obs = self._repos.videos.get_latest_video_observations(
            [video.video_id for video in videos]
        )
        metric_cache = {
            video.video_id: latest_obs.get(video.video_id) for video in videos
        }

        def metric(key: str) -> Callable[[Video], float | int | None]:
            def _get(video: Video):
                obs = metric_cache[video.video_id]
                if key == "views":
                    return obs.view_count if obs else None
                if key == "likes":
                    return obs.like_count if obs else None
                if key == "comments":
                    return obs.comment_count if obs else None
                if key == "engagement":
                    return self._ratio(
                        self._sum(obs, "like_count", "comment_count"),
                        obs.view_count if obs else None,
                    )
                if key == "comment_rate":
                    return self._ratio(
                        obs.comment_count if obs else None,
                        obs.view_count if obs else None,
                    )
                if key == "like_rate":
                    return self._ratio(
                        obs.like_count if obs else None,
                        obs.view_count if obs else None,
                    )
                return None

            return _get

        ranked: list[Video] | None = None
        missing = 0
        strategy = spec.strategy

        if strategy == SamplingStrategy.TOP_VIEWS:
            ranked, missing = self._rank(videos, metric("views"), reverse=True)
        elif strategy == SamplingStrategy.BOTTOM_VIEWS:
            ranked, missing = self._rank(videos, metric("views"), reverse=False)
        elif strategy == SamplingStrategy.TOP_LIKES:
            ranked, missing = self._rank(videos, metric("likes"), reverse=True)
        elif strategy == SamplingStrategy.BOTTOM_LIKES:
            ranked, missing = self._rank(videos, metric("likes"), reverse=False)
        elif strategy == SamplingStrategy.TOP_ENGAGEMENT:
            ranked, missing = self._rank(videos, metric("engagement"), reverse=True)
        elif strategy == SamplingStrategy.BOTTOM_ENGAGEMENT:
            ranked, missing = self._rank(videos, metric("engagement"), reverse=False)
        elif strategy == SamplingStrategy.TOP_COMMENTS:
            ranked, missing = self._rank(videos, metric("comments"), reverse=True)
        elif strategy == SamplingStrategy.TOP_COMMENT_RATE:
            ranked, missing = self._rank(videos, metric("comment_rate"), reverse=True)
        elif strategy == SamplingStrategy.TOP_LIKE_RATE:
            ranked, missing = self._rank(videos, metric("like_rate"), reverse=True)
        elif strategy == SamplingStrategy.LONGEST:
            ranked, missing = self._rank(
                videos, lambda v: v.duration, reverse=True
            )
        elif strategy == SamplingStrategy.SHORTEST:
            ranked, missing = self._rank(
                videos, lambda v: v.duration, reverse=False
            )
        elif strategy == SamplingStrategy.LATEST:
            ranked, missing = self._rank(
                videos, lambda v: v.upload_date, reverse=True
            )
        elif strategy == SamplingStrategy.EARLIEST:
            ranked, missing = self._rank(
                videos, lambda v: v.upload_date, reverse=False
            )
        elif strategy == SamplingStrategy.DATE_RANGE:
            ranked, missing = self._date_range(videos, spec)
        elif strategy == SamplingStrategy.RANDOM:
            ranked, missing = self._random(videos, spec)
        elif strategy == SamplingStrategy.STRATIFIED:
            ranked, missing = self._stratified(videos, spec)
        else:  # pragma: no cover - enum is closed
            raise UnsupportedSamplingError(f"Unknown strategy {strategy}")

        ids = [v.video_id for v in ranked]
        sample = self._cut(ids, spec)
        return SamplingResult(
            strategy=strategy,
            entity_type="video",
            population_size=len(videos),
            sample_size=len(sample),
            entity_ids=sample,
            criteria_json=self._criteria(spec, len(videos), missing),
            seed=spec.seed if spec.seed is not None else self._default_seed,
            missing_metric_count=missing,
        )

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------
    def sample_comments(
        self,
        video_id: str,
        spec: SamplingSpec,
    ) -> SamplingResult:
        """Sample comments of a video using a comment-applicable strategy."""
        comments = self._repos.comments.list_comments(video_id)
        strategy = spec.strategy
        if strategy not in self._COMMENT_STRATEGIES:
            raise UnsupportedSamplingError(
                f"Strategy '{strategy.value}' is not applicable to comments"
            )

        ranked: list[Comment] | None = None
        if strategy == SamplingStrategy.TOP_LIKES:
            latest_obs = self._repos.comments.get_latest_comment_observations(
                [c.comment_id for c in comments]
            )
            likes = {
                c.comment_id: (
                    latest_obs[c.comment_id].like_count
                    if latest_obs.get(c.comment_id) is not None
                    else None
                )
                for c in comments
            }
            ranked, _ = self._rank(
                comments, lambda c: likes[c.comment_id], reverse=True
            )
        elif strategy == SamplingStrategy.LATEST:
            ranked, _ = self._rank(comments, lambda c: c.published_at, reverse=True)
        elif strategy == SamplingStrategy.EARLIEST:
            ranked, _ = self._rank(comments, lambda c: c.published_at, reverse=False)
        elif strategy == SamplingStrategy.DATE_RANGE:
            ranked, _ = self._comment_date_range(comments, spec)
        elif strategy == SamplingStrategy.RANDOM:
            ranked, _ = self._random(comments, spec)
        elif strategy == SamplingStrategy.STRATIFIED:
            ranked, _ = self._stratified(comments, spec)

        ids = [c.comment_id for c in ranked or []]
        sample = self._cut(ids, spec)
        return SamplingResult(
            strategy=strategy,
            entity_type="comment",
            population_size=len(comments),
            sample_size=len(sample),
            entity_ids=sample,
            criteria_json=self._criteria(spec, len(comments), 0),
            seed=spec.seed if spec.seed is not None else self._default_seed,
        )

    # ------------------------------------------------------------------
    # Strategy internals
    # ------------------------------------------------------------------
    @staticmethod
    def _ratio(numerator: float | int | None, denominator: float | int | None):
        """None/zero-safe ratio; delegates to StatisticsService."""
        return StatisticsService.ratio(numerator, denominator)

    @staticmethod
    def _sum(obs, *fields: str) -> float | int | None:
        if obs is None:
            return None
        return StatisticsService.sum_values(*(getattr(obs, field_name) for field_name in fields))

    def _latest_obs(self, video_id: str):
        return self._repos.videos.get_latest_video_observation(video_id)

    def _latest_comment_likes(self, comment_id: str):
        obs = self._repos.comments.get_latest_comment_observation(comment_id)
        return obs.like_count if obs else None

    @staticmethod
    def _rank(
        items: list, key: Callable, *, reverse: bool
    ) -> tuple[list, int]:
        """Sort items by ``key`` with missing values ranked last.

        Returns ``(ranked_items, missing_count)``.
        """
        with_value = [it for it in items if key(it) is not None]
        without_value = [it for it in items if key(it) is None]
        with_value.sort(key=lambda it: (key(it) is None, key(it)), reverse=reverse)
        return with_value + without_value, len(without_value)

    def _cut(self, ids: list[str], spec: SamplingSpec) -> list[str]:
        """Apply ``size`` or ``percent`` to an already-ordered id list."""
        population = len(ids)
        if spec.size is not None:
            return ids[: max(0, min(spec.size, population))]
        if spec.percent is not None:
            count = round(population * spec.percent / 100.0)
            return ids[: max(0, min(count, population))]
        if spec.top_n is not None:
            return ids[: max(0, min(spec.top_n, population))]
        return ids

    def _random(self, items: list, spec: SamplingSpec) -> tuple[list, int]:
        rng = Random(spec.seed if spec.seed is not None else self._default_seed)
        return rng.sample(items, len(items)), 0

    def _date_range(self, videos: list[Video], spec: SamplingSpec) -> tuple[list, int]:
        if not spec.date_from and not spec.date_to:
            return videos, 0
        start, end = spec.date_from or date.min, spec.date_to or date.max
        kept = [
            v for v in videos if v.upload_date is not None and start <= v.upload_date <= end
        ]
        return kept, 0

    def _comment_date_range(
        self, comments: list[Comment], spec: SamplingSpec
    ) -> tuple[list, int]:
        if not spec.date_from and not spec.date_to:
            return comments, 0
        start = (
            spec.date_from
            if spec.date_from
            else date(1970, 1, 1)
        )
        end = spec.date_to or date.max
        kept = [
            c
            for c in comments
            if c.published_at is not None
            and start <= c.published_at.date() <= end
        ]
        return kept, 0

    def _stratified(self, items: list, spec: SamplingSpec) -> tuple[list, int]:
        """Balanced sampling per stratum (year/month/weekday of publication).

        Draws ``sample_per_stratum`` items *randomly within each stratum* using
        a seed-derived RNG (same seed -> same sample, different seed -> a
        different representative), mirroring :meth:`_random`.
        """
        per = spec.sample_per_stratum or 1
        rng = Random(spec.seed if spec.seed is not None else self._default_seed)
        strata: dict[str, list] = {}
        for item in items:
            key = self._stratum_key(item, spec.strata)
            if key is not None:
                strata.setdefault(key, []).append(item)
        selected: list = []
        for key in sorted(strata):
            bucket = strata[key]
            if len(bucket) <= per:
                selected.extend(bucket)
            else:
                selected.extend(rng.sample(bucket, per))
        return selected, 0

    @staticmethod
    def _stratum_key(item, strata: str | None) -> str | None:
        published = item.published_at if isinstance(item, Comment) else item.upload_date
        if published is None:
            return None
        if strata == "year":
            return str(published.year)
        if strata == "month":
            return f"{published.year}-{published.month:02d}"
        if strata == "weekday":
            return str(published.weekday())
        return str(published.year)

    @staticmethod
    def _criteria(spec: SamplingSpec, population: int, missing: int) -> dict:
        return {
            "strategy": spec.strategy.value,
            "size": spec.size,
            "percent": spec.percent,
            "top_n": spec.top_n,
            "seed": spec.seed,
            "strata": spec.strata,
            "sample_per_stratum": spec.sample_per_stratum,
            "date_from": spec.date_from.isoformat() if spec.date_from else None,
            "date_to": spec.date_to.isoformat() if spec.date_to else None,
            "population_size": population,
            "missing_metric_count": missing,
            "generated_at": utcnow().isoformat(),
        }

    _COMMENT_STRATEGIES = frozenset(
        {
            SamplingStrategy.TOP_LIKES,
            SamplingStrategy.TOP_REPLIES,
            SamplingStrategy.RANDOM,
            SamplingStrategy.STRATIFIED,
            SamplingStrategy.LATEST,
            SamplingStrategy.EARLIEST,
            SamplingStrategy.DATE_RANGE,
        }
    )

    # ------------------------------------------------------------------
    # Advanced Sampling (cross-channel, multi-video, user-based)
    # ------------------------------------------------------------------
    def sample_advanced(
        self,
        spec: AdvancedSamplingSpec,
    ) -> SamplingResult:
        """Advanced sampling with complex filter combinations.

        Supports researcher scenarios:
        - Sample specific user comments across all videos/channels
        - Sample within specific channel(s) with video filters
        - Sample specific users with their IDs
        - Sample non-specified users across channel among specified videos
        - Multiple channels with date range filters
        """
        if spec.entity_type == "video":
            return self._sample_videos_advanced(spec)
        elif spec.entity_type == "comment":
            return self._sample_comments_advanced(spec)
        else:
            raise UnsupportedSamplingError(f"Unknown entity_type: {spec.entity_type}")

    def _sample_videos_advanced(self, spec: AdvancedSamplingSpec) -> SamplingResult:
        """Sample videos with advanced cross-channel/video filters."""
        # Collect candidate videos
        if spec.include_all_channels:
            # Sample across all channels
            all_channels = self._repos.channels.list_channels()
            channel_ids = [c.channel_id for c in all_channels]
        elif spec.channel_ids:
            channel_ids = spec.channel_ids
        else:
            raise ValueError("Either channel_ids or include_all_channels must be specified for video sampling")

        # Gather all videos from specified channels
        all_videos = []
        for channel_id in channel_ids:
            videos = self._repos.videos.list_videos(channel_id=channel_id)
            all_videos.extend(videos)

        # Restrict to videos first discovered in the given collection runs
        if spec.run_ids:
            run_set = set(spec.run_ids)
            all_videos = [
                v for v in all_videos if v.first_observed_run_id in run_set
            ]

        # Filter by specific video_ids if provided
        if spec.video_ids:
            video_id_set = set(spec.video_ids)
            all_videos = [v for v in all_videos if v.video_id in video_id_set]

        # Apply video-level filters
        filtered_videos = self._apply_video_filters(all_videos, spec)

        # Get latest observations for ranking
        latest_obs = self._repos.videos.get_latest_video_observations(
            [v.video_id for v in filtered_videos]
        )
        metric_cache = {v.video_id: latest_obs.get(v.video_id) for v in filtered_videos}

        def metric(key: str):
            def _get(video: Video):
                obs = metric_cache[video.video_id]
                if key == "views":
                    return obs.view_count if obs else None
                if key == "likes":
                    return obs.like_count if obs else None
                if key == "comments":
                    return obs.comment_count if obs else None
                if key == "engagement":
                    return self._ratio(
                        self._sum(obs, "like_count", "comment_count"),
                        obs.view_count if obs else None,
                    )
                if key == "comment_rate":
                    return self._ratio(
                        obs.comment_count if obs else None,
                        obs.view_count if obs else None,
                    )
                if key == "like_rate":
                    return self._ratio(
                        obs.like_count if obs else None,
                        obs.view_count if obs else None,
                    )
                return None
            return _get

        ranked: list[Video] | None = None
        missing = 0
        strategy = spec.strategy

        if strategy == SamplingStrategy.TOP_VIEWS:
            ranked, missing = self._rank(filtered_videos, metric("views"), reverse=True)
        elif strategy == SamplingStrategy.BOTTOM_VIEWS:
            ranked, missing = self._rank(filtered_videos, metric("views"), reverse=False)
        elif strategy == SamplingStrategy.TOP_LIKES:
            ranked, missing = self._rank(filtered_videos, metric("likes"), reverse=True)
        elif strategy == SamplingStrategy.BOTTOM_LIKES:
            ranked, missing = self._rank(filtered_videos, metric("likes"), reverse=False)
        elif strategy == SamplingStrategy.TOP_ENGAGEMENT:
            ranked, missing = self._rank(filtered_videos, metric("engagement"), reverse=True)
        elif strategy == SamplingStrategy.BOTTOM_ENGAGEMENT:
            ranked, missing = self._rank(filtered_videos, metric("engagement"), reverse=False)
        elif strategy == SamplingStrategy.TOP_COMMENTS:
            ranked, missing = self._rank(filtered_videos, metric("comments"), reverse=True)
        elif strategy == SamplingStrategy.TOP_COMMENT_RATE:
            ranked, missing = self._rank(filtered_videos, metric("comment_rate"), reverse=True)
        elif strategy == SamplingStrategy.TOP_LIKE_RATE:
            ranked, missing = self._rank(filtered_videos, metric("like_rate"), reverse=True)
        elif strategy == SamplingStrategy.LONGEST:
            ranked, missing = self._rank(filtered_videos, lambda v: v.duration, reverse=True)
        elif strategy == SamplingStrategy.SHORTEST:
            ranked, missing = self._rank(filtered_videos, lambda v: v.duration, reverse=False)
        elif strategy == SamplingStrategy.LATEST:
            ranked, missing = self._rank(filtered_videos, lambda v: v.upload_date, reverse=True)
        elif strategy == SamplingStrategy.EARLIEST:
            ranked, missing = self._rank(filtered_videos, lambda v: v.upload_date, reverse=False)
        elif strategy == SamplingStrategy.DATE_RANGE:
            ranked, missing = self._date_range(filtered_videos, spec)
        elif strategy == SamplingStrategy.RANDOM:
            ranked, missing = self._random(filtered_videos, spec)
        elif strategy == SamplingStrategy.STRATIFIED:
            ranked, missing = self._stratified(filtered_videos, spec)
        else:
            raise UnsupportedSamplingError(f"Unknown strategy {strategy}")

        ids = [v.video_id for v in ranked]
        sample = self._cut(ids, spec)

        # Build criteria JSON with all filters
        criteria = self._criteria(spec, len(filtered_videos), missing)
        criteria.update({
            "channel_ids": spec.channel_ids,
            "run_ids": spec.run_ids,
            "video_ids": spec.video_ids,
            "include_all_channels": spec.include_all_channels,
            "author_names": spec.author_names,
            "exclude_author_names": spec.exclude_author_names,
            "video_type": spec.video_type,
            "duration_min": spec.duration_min,
            "duration_max": spec.duration_max,
            "views_min": spec.views_min,
            "views_max": spec.views_max,
            "upload_hour": spec.upload_hour,
            "upload_weekday": spec.upload_weekday,
            "keywords": spec.keywords,
            "tags": spec.tags,
            "category": spec.category,
            "categories": spec.categories,
        })

        return SamplingResult(
            strategy=strategy,
            entity_type="video",
            population_size=len(filtered_videos),
            sample_size=len(sample),
            entity_ids=sample,
            criteria_json=criteria,
            seed=spec.seed if spec.seed is not None else self._default_seed,
            missing_metric_count=missing,
        )

    def _sample_comments_advanced(self, spec: AdvancedSamplingSpec) -> SamplingResult:
        """Sample comments with advanced cross-channel/user/video filters."""
        # Collect candidate comments
        all_comments = []

        if spec.include_all_channels:
            # Get all videos from all channels, then their comments
            all_channels = self._repos.channels.list_channels()
            channel_ids = [c.channel_id for c in all_channels]
        elif spec.channel_ids:
            channel_ids = spec.channel_ids
        else:
            channel_ids = []

        # Build the candidate video population. Specific video_ids take priority;
        # otherwise every video in the selected channels is considered.
        all_videos: list[Video] = []
        if spec.video_ids:
            for video_id in spec.video_ids:
                video = self._repos.videos.get_video(video_id)
                if video is not None:
                    all_videos.append(video)
        else:
            for channel_id in channel_ids:
                all_videos.extend(self._repos.videos.list_videos(channel_id=channel_id))

        # Restrict to videos first discovered in the given collection runs
        if spec.run_ids:
            run_set = set(spec.run_ids)
            all_videos = [
                v for v in all_videos if v.first_observed_run_id in run_set
            ]

        # Apply video-level filters (type/duration/views/categories/date...) to
        # the whole population so every comment's video must satisfy them.
        filtered_videos = self._apply_video_filters(all_videos, spec)
        video_ids = [v.video_id for v in filtered_videos]

        # Collect comments from all relevant videos
        for video_id in video_ids:
            comments = self._repos.comments.list_comments(video_id)
            all_comments.extend(comments)

        # Apply comment-level filters
        filtered_comments = self._apply_comment_filters(all_comments, spec)

        # Filter by author_ids if specified
        if spec.author_ids:
            author_id_set = set(spec.author_ids)
            filtered_comments = [c for c in filtered_comments if c.author_id in author_id_set]

        # Exclude author_ids if specified
        if spec.exclude_author_ids:
            exclude_set = set(spec.exclude_author_ids)
            filtered_comments = [c for c in filtered_comments if c.author_id not in exclude_set]

        # Include comments whose author name contains any given name (case-insensitive)
        if spec.author_names:
            names_lower = [n.lower() for n in spec.author_names]
            filtered_comments = [
                c
                for c in filtered_comments
                if c.author_name
                and any(n in c.author_name.lower() for n in names_lower)
            ]

        # Exclude comments whose author name contains any given name (case-insensitive)
        if spec.exclude_author_names:
            excluded_lower = [n.lower() for n in spec.exclude_author_names]
            filtered_comments = [
                c
                for c in filtered_comments
                if not (
                    c.author_name
                    and any(n in c.author_name.lower() for n in excluded_lower)
                )
            ]

        # Author-overlap filter, computed on the already-filtered population
        if spec.overlap and spec.overlap != "off":
            video_channel = {
                v.video_id: v.channel_id for v in filtered_videos if v.channel_id
            }
            filtered_comments = self._apply_overlap(
                filtered_comments, spec, video_channel
            )

        strategy = spec.strategy
        if strategy not in self._COMMENT_STRATEGIES:
            raise UnsupportedSamplingError(
                f"Strategy '{strategy.value}' is not applicable to comments"
            )

        ranked: list[Comment] | None = None
        if strategy == SamplingStrategy.TOP_LIKES:
            latest_obs = self._repos.comments.get_latest_comment_observations(
                [c.comment_id for c in filtered_comments]
            )
            likes = {
                c.comment_id: (
                    latest_obs[c.comment_id].like_count
                    if latest_obs.get(c.comment_id) is not None
                    else None
                )
                for c in filtered_comments
            }
            ranked, _ = self._rank(filtered_comments, lambda c: likes[c.comment_id], reverse=True)
        elif strategy == SamplingStrategy.TOP_REPLIES:
            latest_obs = self._repos.comments.get_latest_comment_observations(
                [c.comment_id for c in filtered_comments]
            )
            replies = {
                c.comment_id: (
                    latest_obs[c.comment_id].reply_count
                    if latest_obs.get(c.comment_id) is not None
                    else None
                )
                for c in filtered_comments
            }
            ranked, _ = self._rank(
                filtered_comments, lambda c: replies[c.comment_id], reverse=True
            )
        elif strategy == SamplingStrategy.LATEST:
            ranked, _ = self._rank(filtered_comments, lambda c: c.published_at, reverse=True)
        elif strategy == SamplingStrategy.EARLIEST:
            ranked, _ = self._rank(filtered_comments, lambda c: c.published_at, reverse=False)
        elif strategy == SamplingStrategy.DATE_RANGE:
            ranked, _ = self._comment_date_range(filtered_comments, spec)
        elif strategy == SamplingStrategy.RANDOM:
            ranked, _ = self._random(filtered_comments, spec)
        elif strategy == SamplingStrategy.STRATIFIED:
            ranked, _ = self._stratified(filtered_comments, spec)

        ids = [c.comment_id for c in ranked or []]
        sample = self._cut(ids, spec)

        # Build criteria JSON with all filters
        criteria = self._criteria(spec, len(filtered_comments), 0)
        criteria.update({
            "channel_ids": spec.channel_ids,
            "run_ids": spec.run_ids,
            "video_ids": spec.video_ids,
            "author_ids": spec.author_ids,
            "exclude_author_ids": spec.exclude_author_ids,
            "author_names": spec.author_names,
            "exclude_author_names": spec.exclude_author_names,
            "include_all_channels": spec.include_all_channels,
            "min_likes": spec.min_likes,
            "max_likes": spec.max_likes,
            "min_replies": spec.min_replies,
            "max_replies": spec.max_replies,
            "only_roots": spec.only_roots,
            "only_replies": spec.only_replies,
            "is_author": spec.is_author,
            "comment_keywords": spec.comment_keywords,
            "video_type": spec.video_type,
            "duration_min": spec.duration_min,
            "duration_max": spec.duration_max,
            "views_min": spec.views_min,
            "views_max": spec.views_max,
            "upload_hour": spec.upload_hour,
            "upload_weekday": spec.upload_weekday,
            "keywords": spec.keywords,
            "tags": spec.tags,
            "category": spec.category,
            "categories": spec.categories,
            "overlap": spec.overlap,
            "overlap_min": spec.overlap_min,
            "overlap_video_ids": spec.overlap_video_ids,
            "overlap_channel_ids": spec.overlap_channel_ids,
        })

        return SamplingResult(
            strategy=strategy,
            entity_type="comment",
            population_size=len(filtered_comments),
            sample_size=len(sample),
            entity_ids=sample,
            criteria_json=criteria,
            seed=spec.seed if spec.seed is not None else self._default_seed,
            missing_metric_count=0,
        )

    def _apply_video_filters(self, videos: list[Video], spec: AdvancedSamplingSpec) -> list[Video]:
        """Apply video-level filters from AdvancedSamplingSpec."""
        filtered = videos

        if spec.video_type:
            filtered = [v for v in filtered if v.live_status == spec.video_type or v.is_short == (spec.video_type == "short")]

        if spec.duration_min is not None:
            filtered = [v for v in filtered if v.duration is not None and v.duration >= spec.duration_min]
        if spec.duration_max is not None:
            filtered = [v for v in filtered if v.duration is not None and v.duration <= spec.duration_max]

        if spec.views_min is not None or spec.views_max is not None:
            latest_obs = self._repos.videos.get_latest_video_observations([v.video_id for v in filtered])
            if spec.views_min is not None:
                filtered = [v for v in filtered if latest_obs.get(v.video_id) and latest_obs[v.video_id].view_count is not None and latest_obs[v.video_id].view_count >= spec.views_min]
            if spec.views_max is not None:
                filtered = [v for v in filtered if latest_obs.get(v.video_id) and latest_obs[v.video_id].view_count is not None and latest_obs[v.video_id].view_count <= spec.views_max]

        if spec.upload_hour is not None:
            filtered = [v for v in filtered if v.upload_timestamp is not None and v.upload_timestamp.hour == spec.upload_hour]
        if spec.upload_weekday is not None:
            filtered = [v for v in filtered if v.upload_date is not None and v.upload_date.weekday() == spec.upload_weekday]

        if spec.keywords:
            kw_lower = [k.lower() for k in spec.keywords]
            filtered = [v for v in filtered if any(k in (v.title or "").lower() or k in (v.description or "").lower() for k in kw_lower)]

        if spec.tags:
            tag_set = set(spec.tags)
            filtered = [v for v in filtered if tag_set.intersection(set(v.tags))]

        if spec.category:
            filtered = [v for v in filtered if v.categories and spec.category in v.categories]

        if spec.categories:
            categories = set(spec.categories)
            filtered = [
                v for v in filtered if v.categories and categories.intersection(v.categories)
            ]

        # Date range filter
        if spec.date_from or spec.date_to:
            start = spec.date_from or date.min
            end = spec.date_to or date.max
            filtered = [v for v in filtered if v.upload_date is not None and start <= v.upload_date <= end]

        return filtered

    def _apply_comment_filters(self, comments: list[Comment], spec: AdvancedSamplingSpec) -> list[Comment]:
        """Apply comment-level filters from AdvancedSamplingSpec."""
        filtered = comments

        if spec.min_likes is not None or spec.max_likes is not None:
            latest_obs = self._repos.comments.get_latest_comment_observations([c.comment_id for c in filtered])
            if spec.min_likes is not None:
                filtered = [c for c in filtered if latest_obs.get(c.comment_id) and latest_obs[c.comment_id].like_count is not None and latest_obs[c.comment_id].like_count >= spec.min_likes]
            if spec.max_likes is not None:
                filtered = [c for c in filtered if latest_obs.get(c.comment_id) and latest_obs[c.comment_id].like_count is not None and latest_obs[c.comment_id].like_count <= spec.max_likes]

        if spec.min_replies is not None or spec.max_replies is not None:
            latest_obs = self._repos.comments.get_latest_comment_observations([c.comment_id for c in filtered])
            if spec.min_replies is not None:
                filtered = [c for c in filtered if latest_obs.get(c.comment_id) and latest_obs[c.comment_id].reply_count is not None and latest_obs[c.comment_id].reply_count >= spec.min_replies]
            if spec.max_replies is not None:
                filtered = [c for c in filtered if latest_obs.get(c.comment_id) and latest_obs[c.comment_id].reply_count is not None and latest_obs[c.comment_id].reply_count <= spec.max_replies]

        if spec.only_roots:
            filtered = [c for c in filtered if not c.is_reply]
        if spec.only_replies:
            filtered = [c for c in filtered if c.is_reply]

        if spec.is_author is not None:
            filtered = [c for c in filtered if c.is_author == spec.is_author]

        if spec.comment_keywords:
            kw_lower = [k.lower() for k in spec.comment_keywords]
            filtered = [c for c in filtered if c.comment_text and any(k in c.comment_text.lower() for k in kw_lower)]

        # Date range filter
        if spec.date_from or spec.date_to:
            start = spec.date_from if spec.date_from else date(1970, 1, 1)
            end = spec.date_to or date.max
            filtered = [c for c in filtered if c.published_at is not None and start <= c.published_at.date() <= end]

        return filtered

    @staticmethod
    def _author_key(comment: Comment) -> str | None:
        """Best-effort author identity: author_id, falling back to author_name."""
        return comment.author_id or comment.author_name

    def _apply_overlap(
        self,
        comments: list[Comment],
        spec: AdvancedSamplingSpec,
        video_channel: dict[str, str | None],
    ) -> list[Comment]:
        """Keep comments whose author is active across enough distinct units.

        With ``overlap == "video"`` the unit is the comment's video; with
        ``overlap == "channel"`` it is the video's channel (``video_channel``
        maps video_id -> channel_id for the filtered population). A comment is
        kept only when its author appears in at least ``overlap_min`` distinct
        units. When ``overlap_video_ids`` (video mode) or ``overlap_channel_ids``
        (channel mode) are provided, only those specific units are counted, so
        the researcher can measure overlap across the entities they care about.
        Authors without a stable identity (no author_id or author_name) cannot
        be judged and are dropped, matching the membership check below.
        """
        minimum = max(1, spec.overlap_min)
        allowed_units: set[str] | None = None
        if spec.overlap == "video" and spec.overlap_video_ids:
            allowed_units = set(spec.overlap_video_ids)
        elif spec.overlap == "channel" and spec.overlap_channel_ids:
            allowed_units = set(spec.overlap_channel_ids)

        by_author: dict[str, set[str]] = {}
        for comment in comments:
            key = self._author_key(comment)
            if key is None:
                continue
            unit = (
                comment.video_id
                if spec.overlap == "video"
                else video_channel.get(comment.video_id)
            )
            if unit is None:
                continue
            if allowed_units is not None and unit not in allowed_units:
                continue
            by_author.setdefault(key, set()).add(unit)

        qualified = {
            key for key, units in by_author.items() if len(units) >= minimum
        }
        return [
            comment for comment in comments if self._author_key(comment) in qualified
        ]
