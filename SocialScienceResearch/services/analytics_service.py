"""Research analytics over collected YouTube data.

Analytics read from the *latest* observation of each entity (never fabricate
history) and surface ``DataAvailability`` whenever a value is absent or the
collection method cannot provide it. No metric is estimated or inferred.

Available analytics:
* ``channel_overview`` - latest channel statistics with availability flags.
* ``top_videos`` - top/bottom videos of a channel by a public metric.
* ``video_engagement`` - engagement/like/comment rates for one video.
* ``comment_like_percentiles`` - like-count percentile bands for comments.
* ``comment_velocity`` - comment publication timeline (per day/hour).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from SocialScienceResearch.domain.enums import DataAvailability, PercentileBand
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.statistics_service import StatisticsService
from SocialScienceResearch.utils.idgen import utcnow

METRICS = frozenset({"views", "likes", "comments"})


@dataclass(frozen=True)
class ValueWithAvailability:
    """A metric value plus its explicit availability."""

    value: float | int | None = None
    availability: DataAvailability = DataAvailability.AVAILABLE


@dataclass
class ChannelOverview:
    channel_id: str
    subscriber_count: ValueWithAvailability
    video_count: ValueWithAvailability
    view_count: ValueWithAvailability
    observed_at: datetime | None = None


@dataclass
class TopVideoEntry:
    video_id: str
    title: str | None = None
    metric: str | None = None
    value: float | int | None = None
    availability: DataAvailability = DataAvailability.AVAILABLE


@dataclass
class VideoEngagement:
    video_id: str
    views: ValueWithAvailability
    likes: ValueWithAvailability
    comments: ValueWithAvailability
    engagement_rate: ValueWithAvailability
    like_rate: ValueWithAvailability
    comment_rate: ValueWithAvailability
    observed_at: datetime | None = None


@dataclass
class CommentPercentiles:
    video_id: str
    like_counts: list[int] = field(default_factory=list)
    bands: dict[str, float | None] = field(default_factory=dict)
    availability: DataAvailability = DataAvailability.AVAILABLE


class AnalyticsService:
    """Read-only analytics over the repository data."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    # ------------------------------------------------------------------
    def channel_overview(self, channel_id: str) -> ChannelOverview:
        """Latest observed statistics of a channel, with availability flags."""
        obs = self._repos.channels.get_latest_channel_observation(channel_id)
        if obs is None:
            return ChannelOverview(
                channel_id=channel_id,
                subscriber_count=ValueWithAvailability(None, DataAvailability.MISSING),
                video_count=ValueWithAvailability(None, DataAvailability.MISSING),
                view_count=ValueWithAvailability(None, DataAvailability.MISSING),
            )
        return ChannelOverview(
            channel_id=channel_id,
            subscriber_count=self._avail(obs.subscriber_count),
            video_count=self._avail(obs.video_count),
            view_count=self._avail(obs.view_count),
            observed_at=obs.observed_at,
        )

    # ------------------------------------------------------------------
    def top_videos(
        self, channel_id: str, metric: str = "views", n: int = 10, reverse: bool = True
    ) -> list[TopVideoEntry]:
        """Top/bottom videos of a channel by a public metric.

        Videos without an observation for ``metric`` are ranked last; their
        availability is ``MISSING`` and they are never assigned a value.
        """
        if metric not in METRICS:
            raise ValueError(f"Unknown metric {metric!r}; expected one of {sorted(METRICS)}")

        videos = self._repos.videos.list_videos(channel_id=channel_id)
        latest_obs = self._repos.videos.get_latest_video_observations(
            [video.video_id for video in videos]
        )

        def metric_value(video):
            obs = latest_obs.get(video.video_id)
            if obs is None:
                return None
            if metric == "views":
                return obs.view_count
            if metric == "likes":
                return obs.like_count
            return obs.comment_count

        scored = [(v, metric_value(v)) for v in videos]
        with_value = [(v, val) for v, val in scored if val is not None]
        without_value = [(v, val) for v, val in scored if val is None]
        with_value.sort(key=lambda pair: pair[1], reverse=reverse)

        entries: list[TopVideoEntry] = []
        for video, value in with_value[:n]:
            entries.append(
                TopVideoEntry(
                    video_id=video.video_id,
                    title=video.title,
                    metric=metric,
                    value=value,
                    availability=DataAvailability.AVAILABLE,
                )
            )
        for video, _ in without_value[: max(0, n - len(entries))]:
            entries.append(
                TopVideoEntry(
                    video_id=video.video_id,
                    title=video.title,
                    metric=metric,
                    availability=DataAvailability.MISSING,
                )
            )
        return entries

    # ------------------------------------------------------------------
    def video_engagement(self, video_id: str) -> VideoEngagement:
        """Engagement metrics for one video from its latest observation."""
        obs = self._repos.videos.get_latest_video_observation(video_id)
        if obs is None:
            return VideoEngagement(
                video_id=video_id,
                views=ValueWithAvailability(None, DataAvailability.MISSING),
                likes=ValueWithAvailability(None, DataAvailability.MISSING),
                comments=ValueWithAvailability(None, DataAvailability.MISSING),
                engagement_rate=ValueWithAvailability(None, DataAvailability.MISSING),
                like_rate=ValueWithAvailability(None, DataAvailability.MISSING),
                comment_rate=ValueWithAvailability(None, DataAvailability.MISSING),
            )

        views = self._avail(obs.view_count)
        likes = self._avail(obs.like_count)
        comments = self._avail(obs.comment_count)
        numerator = self._sum_available(obs.like_count, obs.comment_count)
        engagement_rate = self._rate(numerator, obs.view_count)
        like_rate = self._rate(obs.like_count, obs.view_count)
        comment_rate = self._rate(obs.comment_count, obs.view_count)

        return VideoEngagement(
            video_id=video_id,
            views=views,
            likes=likes,
            comments=comments,
            engagement_rate=engagement_rate,
            like_rate=like_rate,
            comment_rate=comment_rate,
            observed_at=obs.observed_at,
        )

    # ------------------------------------------------------------------
    def comment_like_percentiles(
        self,
        video_id: str,
        bands: tuple[PercentileBand, ...] = (
            PercentileBand.P75,
            PercentileBand.P90,
            PercentileBand.P95,
            PercentileBand.P99,
        ),
    ) -> CommentPercentiles:
        """Like-count percentile bands over the video's comments.

        Uses the *latest* observation of each comment's like count. When a
        comment has no observation its likes are treated as missing - no value
        is imputed. With zero observed comments, availability is ``MISSING``.
        """
        comments = self._repos.comments.list_comments(video_id)
        latest_obs = self._repos.comments.get_latest_comment_observations(
            [comment.comment_id for comment in comments]
        )
        likes: list[int] = []
        for comment in comments:
            obs = latest_obs.get(comment.comment_id)
            if obs is not None and obs.like_count is not None:
                likes.append(obs.like_count)
        likes.sort()

        if not likes:
            return CommentPercentiles(
                video_id=video_id,
                availability=DataAvailability.MISSING,
            )

        thresholds = {
            int(band.value): self._percentile(likes, int(band.value)) for band in bands
        }
        return CommentPercentiles(
            video_id=video_id,
            like_counts=likes,
            bands={band.value: thresholds[int(band.value)] for band in bands},
            availability=DataAvailability.AVAILABLE,
        )

    # ------------------------------------------------------------------
    def comment_velocity(
        self, video_id: str, bucket: str = "day"
    ) -> list[dict[str, object]]:
        """Number of collected comments published per time bucket.

        ``bucket`` is ``'hour'`` or ``'day'``. Only comments with a known
        ``published_at`` contribute; others are counted separately as
        ``missing`` and never assigned a fabricated time.
        """
        if bucket not in ("hour", "day"):
            raise ValueError("bucket must be 'hour' or 'day'")
        comments = self._repos.comments.list_comments(video_id)
        counter: Counter = Counter()
        missing = 0
        for comment in comments:
            if comment.published_at is None:
                missing += 1
                continue
            if bucket == "hour":
                key = comment.published_at.strftime("%Y-%m-%dT%H:00")
            else:
                key = comment.published_at.date().isoformat()
            counter[key] += 1

        timeline = [{"bucket": k, "count": v} for k, v in sorted(counter.items())]
        if missing:
            timeline.append({"bucket": "missing_published_at", "count": missing})
        return timeline

    # ------------------------------------------------------------------
    @staticmethod
    def _avail(value) -> ValueWithAvailability:
        if value is None:
            return ValueWithAvailability(None, DataAvailability.MISSING)
        return ValueWithAvailability(value, DataAvailability.AVAILABLE)

    @staticmethod
    def _rate(numerator, denominator) -> ValueWithAvailability:
        if numerator is None or denominator in (None, 0):
            availability = (
                DataAvailability.MISSING
                if numerator is None or denominator is None
                else DataAvailability.UNSUPPORTED
            )
            return ValueWithAvailability(None, availability)
        # Delegate the None/zero-safe math to StatisticsService; keep the
        # value as a plain ratio so external behaviour is unchanged (tests
        # assert like_rate == 0.10, i.e. a fraction, not a per-1000 rate).
        return ValueWithAvailability(
            StatisticsService.ratio(numerator, denominator), DataAvailability.AVAILABLE
        )

    @staticmethod
    def _sum_available(*values) -> int | None:
        if any(v is None for v in values):
            return None
        return sum(values)  # type: ignore[arg-type]

    @staticmethod
    def _percentile(sorted_values: list[int], percentile: int) -> float | None:
        """Linear-interpolated percentile (P75/P90/P95/P99).

        Delegates to ``StatisticsService.percentile`` (identical semantics:
        rank ``(len-1) * p / 100`` with linear interpolation).
        """
        return StatisticsService.percentile(list(sorted_values), percentile)
