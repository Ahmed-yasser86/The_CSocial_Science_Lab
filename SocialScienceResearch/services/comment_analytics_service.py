"""B3: Comment analytics (participation, replies, age at posting, velocity).

Pure-ish analytic methods over comment rows resolved through
``QueryService.resolve_latest_rows(entity="comment", ...)`` - which wires the
previously-unwired ``CommentFilter`` - with every statistic delegated to
``StatisticsService`` (ADR-0006: the single home for descriptive statistics).
Availability is always reported explicitly; no value is fabricated or
estimated (e.g. ages are only computed when both the video upload timestamp
and the comment publication time are known).

Owned by the B3 module agent.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.config.settings import SocialScienceSettings
from SocialScienceResearch.domain.query import CommentFilter, QueryContext
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.query_service import QueryService
from SocialScienceResearch.services.statistics_service import StatisticsService

#: Upper bound on the parent-chain walk used to recompute root comment ids,
#: guarding against malformed or cyclic parent references (never an infinite
#: loop: the walk also tracks visited ids).
_MAX_CHAIN_DEPTH = 100


class AuthorCommentCount(BaseModel):
    """Comment counts for one distinct author."""

    model_config = ConfigDict(extra="allow")

    author_id: str | None = None
    author_name: str | None = None
    comment_count: int


class ParticipationAnalytics(BaseModel):
    """Unique vs repeat author participation over a video's comments."""

    model_config = ConfigDict(extra="allow")

    video_id: str
    total_comments: int = 0
    unique_authors: int = 0
    repeat_authors: int = 0
    repeat_author_share: float | None = None
    participation_gini: float | None = None
    top_10pct_concentration: float | None = None
    author_comment_counts: list[AuthorCommentCount] = Field(default_factory=list)


class ThreadSizeBreakdown(BaseModel):
    """One comment thread (root plus its descendant replies)."""

    model_config = ConfigDict(extra="allow")

    root_comment_id: str
    size: int
    depth: int


class ReplyMetrics(BaseModel):
    """Reply-rate and thread-size structure of a video's comments."""

    model_config = ConfigDict(extra="allow")

    video_id: str
    total_comments: int = 0
    reply_count: int = 0
    reply_rate: float | None = None
    orphan_reply_count: int = 0
    thread_count: int = 0
    deepest_thread_depth: int = 0
    thread_size_mean: float | None = None
    thread_size_median: float | None = None
    threads: list[ThreadSizeBreakdown] = Field(default_factory=list)


class CommentAgeAnalytics(BaseModel):
    """Seconds between the video upload timestamp and each comment."""

    model_config = ConfigDict(extra="allow")

    video_id: str
    upload_timestamp: datetime | None = None
    upload_missing: bool = True
    total_comments: int = 0
    aged_comments: int = 0
    mean_age_seconds: float | None = None
    median_age_seconds: float | None = None
    negative_age_count: int = 0


class VelocityBucket(BaseModel):
    """Comment count for one published-at time bucket."""

    model_config = ConfigDict(extra="allow")

    bucket: str
    count: int


class VelocityDecay(BaseModel):
    """Comment counts per time bucket plus an upload-relative decay share."""

    model_config = ConfigDict(extra="allow")

    video_id: str
    bucket: str
    total_comments: int = 0
    timestamped_comments: int = 0
    missing_published_at: int = 0
    upload_missing: bool = True
    timeline: list[VelocityBucket] = Field(default_factory=list)
    first_24h_share: float | None = None
    first_7d_share: float | None = None


class CommentAnalyticsService:
    """Read-only comment analytics over the repository data."""

    _VALID_BUCKETS = ("hour", "day")

    def __init__(
        self, repos: Repositories, settings: SocialScienceSettings | None = None
    ) -> None:
        self._repos = repos
        self._settings = settings or SocialScienceSettings()
        self._query = QueryService(repos, self._settings)

    # ------------------------------------------------------------------
    def _rows(
        self, video_id: str, filter: CommentFilter | None = None
    ) -> list[dict[str, Any]]:
        rows = self._query.resolve_latest_rows(
            "comment", context=QueryContext(video_id=video_id)
        )
        if filter is not None:
            rows = self._query.filter_comments(filter, rows)
        return rows

    @staticmethod
    def _author_key(
        row: dict[str, Any],
    ) -> tuple[tuple[str, str], str | None, str | None]:
        author_id = row.get("author_id")
        author_name = row.get("author_name")
        if author_id is not None:
            return (("id", author_id), author_id, author_name)
        if author_name is not None:
            return (("name", author_name), None, author_name)
        return (("unknown", ""), None, None)

    # ------------------------------------------------------------------
    def participation(
        self, video_id: str, filter: CommentFilter | None = None
    ) -> ParticipationAnalytics:
        """Unique vs repeat author participation (Gini + top-k concentration)."""
        rows = self._rows(video_id, filter)
        counts: Counter = Counter()
        display: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key, author_id, author_name = self._author_key(row)
            counts[key] += 1
            if key not in display:
                display[key] = {"author_id": author_id, "author_name": author_name}
        values = sorted(counts.values(), reverse=True)
        gini = StatisticsService.gini(values)
        top10 = StatisticsService.top_k_concentration(values, 10)
        repeat_authors = sum(1 for v in values if v >= 2)
        return ParticipationAnalytics(
            video_id=video_id,
            total_comments=len(rows),
            unique_authors=len(values),
            repeat_authors=repeat_authors,
            repeat_author_share=StatisticsService.ratio(repeat_authors, len(values)),
            participation_gini=gini.value,
            top_10pct_concentration=top10.value,
            author_comment_counts=[
                AuthorCommentCount(
                    author_id=display[key]["author_id"],
                    author_name=display[key]["author_name"],
                    comment_count=count,
                )
                for key, count in counts.most_common()
            ],
        )

    # ------------------------------------------------------------------
    def reply_metrics(
        self, video_id: str, filter: CommentFilter | None = None
    ) -> ReplyMetrics:
        """Reply rate and thread-size distribution (root->replies grouping).

        ``root_comment_id`` is recomputed by walking the parent chain (bounded
        by ``_MAX_CHAIN_DEPTH`` and cycle-detection) so a stale or missing
        stored root id never yields an infinite loop. Replies whose parent is
        not present in the corpus are reported as ``orphan_reply_count`` and
        anchor a thread of their own.
        """
        rows = self._rows(video_id, filter)
        by_id = {row["comment_id"]: row for row in rows}
        reply_count = sum(1 for row in rows if row["is_reply"] is True)
        orphan_reply_count = sum(
            1
            for row in rows
            if row["is_reply"] is True
            and row["parent_comment_id"] is not None
            and row["parent_comment_id"] not in by_id
        )

        roots, depths = self._thread_roots(rows, by_id)
        sizes: Counter = Counter(roots.values())
        thread_ids = sorted(sizes)
        thread_sizes = [sizes[tid] for tid in thread_ids]
        thread_depths: dict[str, int] = {}
        for cid, depth in depths.items():
            rid = roots[cid]
            thread_depths[rid] = max(thread_depths.get(rid, 0), depth)

        mean = StatisticsService.mean(thread_sizes)
        median = StatisticsService.median(thread_sizes)
        return ReplyMetrics(
            video_id=video_id,
            total_comments=len(rows),
            reply_count=reply_count,
            reply_rate=StatisticsService.ratio(reply_count, len(rows)),
            orphan_reply_count=orphan_reply_count,
            thread_count=len(thread_ids),
            deepest_thread_depth=max(thread_depths.values(), default=0),
            thread_size_mean=mean.value,
            thread_size_median=median.value,
            threads=[
                ThreadSizeBreakdown(
                    root_comment_id=tid, size=sizes[tid], depth=thread_depths[tid]
                )
                for tid in thread_ids
            ],
        )

    def _thread_roots(
        self, rows: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
    ) -> tuple[dict[str, str], dict[str, int]]:
        """Recompute each comment's root id and chain depth via a bounded walk."""
        roots: dict[str, str] = {}
        depths: dict[str, int] = {}
        for row in rows:
            node = row
            depth = 1
            seen: set[str] = set()
            while node["parent_comment_id"] is not None:
                parent_id = node["parent_comment_id"]
                if parent_id in seen or parent_id not in by_id:
                    break
                seen.add(parent_id)
                if depth >= _MAX_CHAIN_DEPTH:
                    break
                depth += 1
                node = by_id[parent_id]
            roots[row["comment_id"]] = node["comment_id"]
            depths[row["comment_id"]] = depth
        return roots, depths

    # ------------------------------------------------------------------
    def comment_age_at_posting(
        self, video_id: str, filter: CommentFilter | None = None
    ) -> CommentAgeAnalytics:
        """Seconds between the video upload timestamp and each comment.

        Positive ages mean the comment was posted after the upload timestamp.
        Comments whose age is negative (published before the recorded upload
        metadata) are counted explicitly in ``negative_age_count`` - they are
        never silently dropped nor coerced. When the video has no upload
        timestamp no age is computed (``upload_missing``).
        """
        rows = self._rows(video_id, filter)
        video = self._repos.videos.get_video(video_id)
        upload = video.upload_timestamp if video is not None else None
        ages: list[float] = []
        negative = 0
        for row in rows:
            published = row.get("published_at")
            if upload is None or published is None:
                continue
            age = (published - upload).total_seconds()
            if age < 0:
                negative += 1
            ages.append(age)
        mean = StatisticsService.mean(ages)
        median = StatisticsService.median(ages)
        return CommentAgeAnalytics(
            video_id=video_id,
            upload_timestamp=upload,
            upload_missing=upload is None,
            total_comments=len(rows),
            aged_comments=len(ages),
            mean_age_seconds=mean.value,
            median_age_seconds=median.value,
            negative_age_count=negative,
        )

    # ------------------------------------------------------------------
    def velocity_decay(
        self,
        video_id: str,
        bucket: str = "day",
        filter: CommentFilter | None = None,
    ) -> VelocityDecay:
        """Comment counts per time bucket plus an upload-relative decay share.

        ``bucket`` is ``'hour'`` or ``'day'``. Comments without ``published_at``
        are counted separately (``missing_published_at``), never assigned a
        fabricated time. The decay shares (share of timestamped comments within
        24h / 7d of the upload timestamp) are only computed when the video has
        an upload timestamp.
        """
        if bucket not in self._VALID_BUCKETS:
            raise ValueError("bucket must be 'hour' or 'day'")
        rows = self._rows(video_id, filter)
        video = self._repos.videos.get_video(video_id)
        upload = video.upload_timestamp if video is not None else None
        counter: Counter = Counter()
        missing = 0
        timestamped = 0
        within_24h = 0
        within_7d = 0
        for row in rows:
            published = row.get("published_at")
            if published is None:
                missing += 1
                continue
            timestamped += 1
            if bucket == "hour":
                key = published.strftime("%Y-%m-%dT%H:00")
            else:
                key = published.date().isoformat()
            counter[key] += 1
            if upload is not None:
                if upload <= published <= upload + timedelta(hours=24):
                    within_24h += 1
                if upload <= published <= upload + timedelta(days=7):
                    within_7d += 1
        timeline = [VelocityBucket(bucket=k, count=v) for k, v in sorted(counter.items())]
        return VelocityDecay(
            video_id=video_id,
            bucket=bucket,
            total_comments=len(rows),
            timestamped_comments=timestamped,
            missing_published_at=missing,
            upload_missing=upload is None,
            timeline=timeline,
            first_24h_share=(
                StatisticsService.ratio(within_24h, timestamped)
                if upload is not None and timestamped
                else None
            ),
            first_7d_share=(
                StatisticsService.ratio(within_7d, timestamped)
                if upload is not None and timestamped
                else None
            ),
        )