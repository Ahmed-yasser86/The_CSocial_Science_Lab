"""Commenter-overlap analytics over persisted comments (audience duplication).

Given a research scope (videos and/or channels), this module answers "who is
active across which audience units":

* per-entity commenter sets keyed by the **strongest identifier** (``author_id``
  first, ``author_name`` fallback - never display-name alone, never fabricated);
* pairwise Jaccard / Szymkiewicz-Simpson overlap / reach-overlap metrics;
* the set of shared commenters per pair with per-side activity;
* bridge commenters (active across >= ``min_entities`` distinct units) and
  top shared commenters by activity;
* overlap-edge rows (shared_commenter_count >= ``min_shared``) that the UI can
  render as a co-occurrence graph overlay;
* a per-commenter drill-down profile with full evidence comments.

All data derives from a chunked ``iter_comments()`` scan + the video->channel
map; no new persistence. Statistics reuse ``StatisticsService.ratio`` (None/zero-safe, the
module's "observed, never estimated" rule).
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.domain.models import Comment
from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.statistics_service import StatisticsService

IdentityKind = Literal["id", "name"]

Metric = Literal["jaccard", "overlap_coefficient", "intersection"]

_METRICS: set[str] = {"jaccard", "overlap_coefficient", "intersection"}


def resolve_author(
    comment: Comment,
) -> tuple[IdentityKind | None, str | None, str | None]:
    """``(kind, key, display_name)`` for a comment's author.

    kind="id"   -> key = ``author_id``,           display = ``author_name``
    kind="name" -> key = ``author_name``,         display = ``author_name``
    else        -> ``(None, None, None)`` (anonymous, excluded from sets).

    The **key** is what populates identity sets; the display name is what the
    UI renders. An id-backed author whose display name changes across videos
    stays the same identity.
    """
    if comment.author_id:
        return "id", comment.author_id, comment.author_name
    if comment.author_name:
        return "name", comment.author_name, comment.author_name
    return None, None, None


def _earlier(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if a <= b else b


def _later(a: datetime | None, b: datetime | None) -> datetime | None:
    if a is None:
        return b
    if b is None:
        return a
    return a if a >= b else b


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _argmax(items: list, key: Callable) -> Any | None:
    if not items:
        return None
    return min(items, key=key)


class _Base(BaseModel):
    """``extra="allow"`` response-model base (matches network analytics)."""

    model_config = ConfigDict(extra="allow")


class OverlapEntity(_Base):
    entity_id: str
    entity_type: str  # "video" | "channel"
    title: str | None = None
    channel_id: str | None = None  # video projection only
    channel_name: str | None = None
    commenter_count: int = 0  # distinct commenters
    comment_count: int = 0  # total comments
    identity_coverage: float | None = None  # identifiable / total comments
    avg_jaccard: float | None = None  # mean metric vs all other entities


class SharedCommenter(_Base):
    author_key: str
    author_name: str | None = None
    identity_kind: str  # "id" | "name"
    count_a: int = 0
    count_b: int = 0
    total_comments: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class PairOverlap(_Base):
    entity_a: str
    entity_b: str
    set_size_a: int = 0
    set_size_b: int = 0
    intersection_size: int = 0
    union_size: int = 0
    unique_a: int = 0
    unique_b: int = 0
    jaccard: float | None = None
    overlap_coefficient: float | None = None
    reach_overlap_pct: float | None = None
    shared_commenters: list[SharedCommenter] = Field(default_factory=list)
    total_shared: int = 0


class BridgeCommenter(_Base):
    author_key: str
    author_name: str | None = None
    identity_kind: str
    entity_count: int = 0
    comment_count: int = 0
    video_count: int = 0
    channel_count: int = 0
    entities: list[dict[str, Any]] = Field(default_factory=list)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class TopSharedCommenter(_Base):
    author_key: str
    author_name: str | None = None
    identity_kind: str
    entity_count: int = 0
    comment_count: int = 0
    video_count: int = 0
    channel_count: int = 0


class ProjectionSummary(_Base):
    entity_type: str
    entity_count: int = 0
    commenter_count: int = 0
    comment_count: int = 0
    unidentified_comments: int = 0
    pair_count: int = 0
    average_jaccard: float | None = None
    max_jaccard_pair: dict[str, Any] | None = None
    max_shared_pair: dict[str, Any] | None = None
    bridge_commenter_count: int = 0


class CommenterProjection(_Base):
    entity_type: str
    entities: list[OverlapEntity] = Field(default_factory=list)
    pairs: list[PairOverlap] = Field(default_factory=list)
    heatmap: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    overlap_edges: list[dict[str, Any]] = Field(default_factory=list)
    bridge_commenters: list[BridgeCommenter] = Field(default_factory=list)
    top_shared_commenters: list[TopSharedCommenter] = Field(default_factory=list)
    summary: ProjectionSummary


class CommenterOverlapResult(_Base):
    scope: dict[str, list[str]] = Field(default_factory=dict)
    metric: str = "jaccard"
    videos: CommenterProjection | None = None
    channels: CommenterProjection | None = None
    global_summary: dict[str, Any] = Field(default_factory=dict)


class ProfileVideoRow(_Base):
    video_id: str
    channel_id: str | None = None
    channel_name: str | None = None
    title: str | None = None
    comment_count: int = 0
    root_count: int = 0
    reply_count: int = 0
    reply_to_count: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class ProfileChannelRow(_Base):
    channel_id: str
    channel_name: str | None = None
    comment_count: int = 0
    video_count: int = 0
    root_count: int = 0
    reply_count: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class ProfileComment(_Base):
    comment_id: str
    video_id: str
    comment_text: str | None = None
    published_at: datetime | None = None
    is_reply: bool = False
    parent_comment_id: str | None = None
    parent_author_name: str | None = None
    like_count: int | None = None
    is_author: bool | None = None


class CommenterProfile(_Base):
    author_key: str
    author_name: str | None = None
    identity_kind: str
    total_comments: int = 0
    video_count: int = 0
    channel_count: int = 0
    is_author: bool | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    videos: list[ProfileVideoRow] = Field(default_factory=list)
    channels: list[ProfileChannelRow] = Field(default_factory=list)
    comments: list[ProfileComment] = Field(default_factory=list)


@dataclass
class _AuthorAgg:
    display_name: str | None
    count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    is_author: bool | None = None


@dataclass
class _ProjectionAgg:
    """Compact per-projection aggregates built in one streaming pass.

    Only identity keys, counts and timestamps are retained -- never the
    comment rows themselves -- so memory stays proportional to distinct
    authors per entity rather than corpus size.
    """

    authors: dict[str, dict[str, _AuthorAgg]] = field(default_factory=dict)
    kinds: dict[str, IdentityKind] = field(default_factory=dict)
    comment_count: Counter[str] = field(default_factory=Counter)
    unidentified: Counter[str] = field(default_factory=Counter)

    def add(self, unit: str, c: Comment) -> None:
        self.comment_count[unit] += 1
        kind, key, display = resolve_author(c)
        if key is None:
            self.unidentified[unit] += 1
            return
        self.kinds.setdefault(key, kind or "name")
        agg = self.authors.setdefault(unit, {}).setdefault(
            key, _AuthorAgg(display_name=display)
        )
        agg.count += 1
        if c.published_at:
            agg.first_seen = _earlier(agg.first_seen, c.published_at)
            agg.last_seen = _later(agg.last_seen, c.published_at)
        if c.is_author is True:
            agg.is_author = True


def _metric_value(metric: str, pair: "PairOverlap") -> float | None:
    if metric == "intersection":
        return float(pair.intersection_size)
    return getattr(pair, metric)  # jaccard | overlap_coefficient


class CommenterOverlapService:
    """Commenter-overlap analytics. Pure reads; no writes."""

    # The overlap scan reads every comment plus the video/channel maps, which is
    # the dominant cost for audience-duplication analytics. The underlying
    # comments are immutable between scrapes, so we memoize per scope; a short
    # TTL bounds staleness and writers call ``clear_overlap_cache()`` (pitfall
    # A1/R1: writers invalidate, readers never trust stale). The entry cap
    # keeps the per-scope keys from growing without bound.
    _overlap_cache: dict[tuple, tuple[float, "CommenterOverlapResult"]] = {}
    _OVERLAP_TTL_SECONDS = 60.0
    _OVERLAP_CACHE_MAX_ENTRIES = 128
    _CHUNK_SIZE = 5000

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def overlap(
        self,
        *,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        metric: str = "jaccard",
        min_entities: int = 2,
        min_shared: int = 1,
        top_n: int = 50,
    ) -> CommenterOverlapResult:
        """Both video + channel projections in one response."""
        if metric not in _METRICS:
            raise ValueError(
                f"metric must be one of {sorted(_METRICS)}, got {metric!r}"
            )
        if min_entities < 1:
            raise ValueError("min_entities must be >= 1")
        if min_shared < 1:
            raise ValueError("min_shared must be >= 1")
        if not (1 <= top_n <= 500):
            raise ValueError("top_n must be in 1..500")

        video_ids = list(video_ids or [])
        channel_ids = list(channel_ids or [])
        if not video_ids and not channel_ids:
            raise ValueError("Provide at least one of video_ids or channel_ids")

        # The leading repos identity keeps workspaces (each with its own
        # repository binding) from reading each other's cached overlaps;
        # activation additionally clears this class-level cache wholesale
        # (workspace_isolation_plan §2.3 step 4, pitfall R1/A1).
        cache_key = (
            id(self._repos),
            tuple(sorted(video_ids)),
            tuple(sorted(channel_ids)),
            metric,
            min_entities,
            min_shared,
            top_n,
        )
        cached = self._overlap_cache.get(cache_key)
        if cached is not None and (time.time() - cached[0]) < self._OVERLAP_TTL_SECONDS:
            return cached[1]

        result = self._compute_overlap(
            video_ids=video_ids,
            channel_ids=channel_ids,
            metric=metric,
            min_entities=min_entities,
            min_shared=min_shared,
            top_n=top_n,
        )
        self._overlap_cache[cache_key] = (time.time(), result)
        while len(self._overlap_cache) > self._OVERLAP_CACHE_MAX_ENTRIES:
            self._overlap_cache.pop(next(iter(self._overlap_cache)))
        return result

    @classmethod
    def clear_overlap_cache(cls) -> None:
        """Invalidate cached overlaps (call after any comment write)."""
        cls._overlap_cache.clear()

    def _compute_overlap(
        self,
        *,
        video_ids: list[str],
        channel_ids: list[str],
        metric: str,
        min_entities: int,
        min_shared: int,
        top_n: int,
    ) -> CommenterOverlapResult:
        """Uncached overlap computation (see :meth:`overlap`)."""
        videos = {v.video_id: v for v in self._repos.videos.list_videos()}
        channels = {c.channel_id: c for c in self._repos.channels.list_channels()}
        video_channel = {v.video_id: v.channel_id for v in videos.values()}

        video_set = set(video_ids)
        channel_set = set(channel_ids)

        # One chunked, column-projected scan feeds both projections and the
        # global maps; only compact aggregates are retained (never the rows).
        video_agg = _ProjectionAgg()
        channel_agg = _ProjectionAgg()
        global_videos: dict[str, set[str]] = {}
        global_channels: dict[str, set[str]] = {}
        global_comment_count = 0
        columns = ["author_id", "author_name", "is_author", "published_at"]
        for chunk in self._repos.comments.iter_comments(
            chunk_size=self._CHUNK_SIZE, columns=columns
        ):
            for c in chunk:
                vid = c.video_id
                ch = video_channel.get(vid)
                in_video_scope = vid in video_set
                in_channel_scope = ch is not None and ch in channel_set
                if not (in_video_scope or in_channel_scope):
                    continue
                global_comment_count += 1
                _, key, _ = resolve_author(c)
                if key is not None:
                    global_videos.setdefault(key, set()).add(vid)
                    if ch is not None:
                        global_channels.setdefault(key, set()).add(ch)
                if in_video_scope:
                    video_agg.add(vid, c)
                if in_channel_scope:
                    channel_agg.add(ch, c)

        videos_projection = (
            self._projection(
                aggregation=video_agg,
                unit_type="video",
                entity_ids=video_set,
                entity_meta={
                    vid: {
                        "title": (videos[vid].title if vid in videos else None),
                        "channel_id": (
                            videos[vid].channel_id if vid in videos else None
                        ),
                        "channel_name": (
                            channels[videos[vid].channel_id].title
                            if vid in videos
                            and videos[vid].channel_id in channels
                            else None
                        ),
                    }
                    for vid in video_ids
                },
                metric=metric,
                min_entities=min_entities,
                min_shared=min_shared,
                top_n=top_n,
                global_videos=global_videos,
                global_channels=global_channels,
            )
            if video_set
            else None
        )
        channels_projection = (
            self._projection(
                aggregation=channel_agg,
                unit_type="channel",
                entity_ids=channel_set,
                entity_meta={
                    cid: {
                        "title": channels[cid].title if cid in channels else None,
                    }
                    for cid in channel_ids
                },
                metric=metric,
                min_entities=min_entities,
                min_shared=min_shared,
                top_n=top_n,
                global_videos=global_videos,
                global_channels=global_channels,
            )
            if channel_set
            else None
        )

        bridge_keys: set[str] = set()
        for projection in (videos_projection, channels_projection):
            if projection is not None:
                bridge_keys.update(
                    b.author_key for b in projection.bridge_commenters
                )

        return CommenterOverlapResult(
            scope={"video_ids": video_ids, "channel_ids": channel_ids},
            metric=metric,
            videos=videos_projection,
            channels=channels_projection,
            global_summary={
                "unique_commenters": len(global_videos),
                "comment_count": global_comment_count,
                "bridge_commenter_count": len(bridge_keys),
            },
        )

    def profile(
        self,
        author_key: str,
        *,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        limit: int = 200,
    ) -> CommenterProfile:
        """Per-commenter drill-down with full evidence comments."""
        if not (1 <= limit <= 500):
            raise ValueError("limit must be in 1..500")

        videos = {v.video_id: v for v in self._repos.videos.list_videos()}
        channels = {c.channel_id: c for c in self._repos.channels.list_channels()}
        video_channel = {v.video_id: v.channel_id for v in videos.values()}

        video_set = set(video_ids or [])
        channel_set = set(channel_ids or [])

        # Pass 1 (streaming, identity columns only): find the matched comments
        # without materializing the corpus. Only compact per-comment dicts are
        # kept, sized by the matched author's activity.
        matched: list[dict[str, Any]] = []
        parent_ids: set[str] = set()
        identity_kind: IdentityKind | None = None
        author_name: str | None = None
        is_author: bool | None = None
        first_seen: datetime | None = None
        last_seen: datetime | None = None
        columns = ["author_id", "author_name", "is_reply", "is_author", "published_at"]
        for chunk in self._repos.comments.iter_comments(
            chunk_size=self._CHUNK_SIZE, columns=columns
        ):
            for c in chunk:
                kind, key, display = resolve_author(c)
                if key != author_key:
                    continue
                if video_set and c.video_id not in video_set:
                    continue
                ch = video_channel.get(c.video_id)
                if channel_set and (ch is None or ch not in channel_set):
                    continue
                matched.append(
                    {
                        "comment_id": c.comment_id,
                        "video_id": c.video_id,
                        "published_at": c.published_at,
                        "is_reply": c.is_reply,
                        "parent_comment_id": c.parent_comment_id,
                        "is_author": c.is_author,
                    }
                )
                if c.parent_comment_id:
                    parent_ids.add(c.parent_comment_id)
                identity_kind = identity_kind or kind
                author_name = author_name or display
                if c.published_at:
                    if first_seen is None or c.published_at < first_seen:
                        first_seen = c.published_at
                    if last_seen is None or c.published_at > last_seen:
                        last_seen = c.published_at
                if c.is_author is True:
                    is_author = True

        if not matched:
            raise KeyError(author_key)

        # Pass 2: fetch evidence text for the matched comments and author
        # context for their parents only -- never the whole corpus.
        wanted_ids = {m["comment_id"] for m in matched} | parent_ids
        by_id: dict[str, Comment] = {}
        ref_columns = ["author_id", "author_name", "comment_text"]
        for chunk in self._repos.comments.iter_comments(
            chunk_size=self._CHUNK_SIZE, columns=ref_columns
        ):
            for c in chunk:
                if c.comment_id in wanted_ids:
                    by_id[c.comment_id] = c

        video_rows: dict[str, dict[str, Any]] = {}
        channel_rows: dict[str, dict[str, Any]] = {}
        for m in matched:
            vrow = video_rows.setdefault(
                m["video_id"],
                {
                    "comment_count": 0,
                    "root_count": 0,
                    "reply_count": 0,
                    "reply_to": set(),
                    "first": None,
                    "last": None,
                },
            )
            vrow["comment_count"] += 1
            if m["is_reply"]:
                vrow["reply_count"] += 1
            else:
                vrow["root_count"] += 1
            if m["is_reply"] and m["parent_comment_id"] in by_id:
                parent = by_id[m["parent_comment_id"]]
                _, parent_key, _ = resolve_author(parent)
                if parent_key is not None:
                    vrow["reply_to"].add(parent_key)
            if m["published_at"]:
                vrow["first"] = _earlier(vrow["first"], m["published_at"])
                vrow["last"] = _later(vrow["last"], m["published_at"])
            ch_id = video_channel.get(m["video_id"])
            if ch_id is not None:
                crow = channel_rows.setdefault(
                    ch_id,
                    {
                        "comment_count": 0,
                        "root_count": 0,
                        "reply_count": 0,
                        "videos": set(),
                        "first": None,
                        "last": None,
                    },
                )
                crow["comment_count"] += 1
                crow["videos"].add(m["video_id"])
                if m["is_reply"]:
                    crow["reply_count"] += 1
                else:
                    crow["root_count"] += 1
                if m["published_at"]:
                    crow["first"] = _earlier(crow["first"], m["published_at"])
                    crow["last"] = _later(crow["last"], m["published_at"])

        profile_videos = [
            ProfileVideoRow(
                video_id=vid,
                channel_id=(videos[vid].channel_id if vid in videos else None),
                channel_name=(
                    channels[videos[vid].channel_id].title
                    if vid in videos and videos[vid].channel_id in channels
                    else None
                ),
                title=(videos[vid].title if vid in videos else None),
                comment_count=agg["comment_count"],
                root_count=agg["root_count"],
                reply_count=agg["reply_count"],
                reply_to_count=len(agg["reply_to"]),
                first_seen_at=agg["first"],
                last_seen_at=agg["last"],
            )
            for vid, agg in sorted(
                video_rows.items(),
                key=lambda kv: (-kv[1]["comment_count"], kv[0]),
            )
        ]
        profile_channels = [
            ProfileChannelRow(
                channel_id=cid,
                channel_name=channels[cid].title if cid in channels else None,
                comment_count=agg["comment_count"],
                video_count=len(agg["videos"]),
                root_count=agg["root_count"],
                reply_count=agg["reply_count"],
                first_seen_at=agg["first"],
                last_seen_at=agg["last"],
            )
            for cid, agg in sorted(
                channel_rows.items(),
                key=lambda kv: (-kv[1]["comment_count"], kv[0]),
            )
        ]

        latest_likes = self._repos.comments.get_latest_comment_observations(
            [m["comment_id"] for m in matched]
        )
        recent = sorted(
            matched,
            key=lambda m: (m["published_at"] is None, m["published_at"]),
            reverse=True,
        )[:limit]
        profile_comments = [
            ProfileComment(
                comment_id=m["comment_id"],
                video_id=m["video_id"],
                comment_text=by_id[m["comment_id"]].comment_text,
                published_at=m["published_at"],
                is_reply=m["is_reply"],
                parent_comment_id=m["parent_comment_id"],
                parent_author_name=(
                    by_id[m["parent_comment_id"]].author_name
                    if m["parent_comment_id"] in by_id
                    else None
                ),
                like_count=(
                    latest_likes[m["comment_id"]].like_count
                    if m["comment_id"] in latest_likes
                    else None
                ),
                is_author=m["is_author"],
            )
            for m in recent
        ]

        return CommenterProfile(
            author_key=author_key,
            author_name=author_name,
            identity_kind=identity_kind or "name",
            total_comments=len(matched),
            video_count=len(video_rows),
            channel_count=len(channel_rows),
            is_author=is_author,
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            videos=profile_videos,
            channels=profile_channels,
            comments=profile_comments,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _projection(
        self,
        *,
        aggregation: _ProjectionAgg,
        unit_type: str,
        entity_ids: set[str],
        entity_meta: dict[str, dict[str, Any]],
        metric: str,
        min_entities: int,
        min_shared: int,
        top_n: int,
        global_videos: dict[str, set[str]],
        global_channels: dict[str, set[str]],
    ) -> CommenterProjection:
        authors = aggregation.authors
        kinds = aggregation.kinds
        comment_count = aggregation.comment_count
        unidentified = aggregation.unidentified

        ordered_units = sorted(entity_ids)
        entities: list[OverlapEntity] = []
        avg_metric: dict[str, list[float | None]] = {}
        pairs: list[PairOverlap] = []
        pair_metric: dict[tuple[str, str], float | None] = {}

        for a, b in combinations(ordered_units, 2):
            set_a = set(authors.get(a, {}))
            set_b = set(authors.get(b, {}))
            shared = set_a & set_b
            union = set_a | set_b
            intersection = len(shared)
            # A pair where either entity has no commenters has no meaningful
            # overlap ratio - report None (never 0).
            if not set_a or not set_b:
                jaccard = overlap_coefficient = reach_overlap_pct = None
            else:
                jaccard = StatisticsService.ratio(intersection, len(union))
                overlap_coefficient = StatisticsService.ratio(
                    intersection, min(len(set_a), len(set_b))
                )
                reach_overlap_pct = StatisticsService.ratio(
                    intersection, max(len(set_a), len(set_b))
                )
            pair = PairOverlap(
                entity_a=a,
                entity_b=b,
                set_size_a=len(set_a),
                set_size_b=len(set_b),
                intersection_size=intersection,
                union_size=len(union),
                unique_a=len(set_a - set_b),
                unique_b=len(set_b - set_a),
                jaccard=jaccard,
                overlap_coefficient=overlap_coefficient,
                reach_overlap_pct=reach_overlap_pct,
                total_shared=intersection,
            )
            shared_rows = []
            for key in sorted(
                shared, key=lambda k: (-authors[a][k].count, -authors[b][k].count, k)
            ):
                agg_a = authors[a][key]
                agg_b = authors[b][key]
                shared_rows.append(
                    SharedCommenter(
                        author_key=key,
                        author_name=agg_a.display_name or agg_b.display_name,
                        identity_kind=kinds[key],
                        count_a=agg_a.count,
                        count_b=agg_b.count,
                        total_comments=agg_a.count + agg_b.count,
                        first_seen_at=_earlier(agg_a.first_seen, agg_b.first_seen),
                        last_seen_at=_later(agg_a.first_seen, agg_b.first_seen),
                    )
                )
            pair.shared_commenters = shared_rows[:top_n]
            pairs.append(pair)
            value = _metric_value(metric, pair)
            pair_metric[(a, b)] = value
            avg_metric.setdefault(a, []).append(value)
            avg_metric.setdefault(b, []).append(value)

        def _metric_key(p: PairOverlap) -> float | None:
            return _metric_value(metric, p)

        pairs.sort(
            key=lambda p: (
                _metric_key(p) is None,
                -(_metric_key(p) or 0),
                p.entity_a,
                p.entity_b,
            )
        )

        for unit in ordered_units:
            total = comment_count[unit]
            identified = total - unidentified[unit]
            metas = entity_meta.get(unit, {})
            entities.append(
                OverlapEntity(
                    entity_id=unit,
                    entity_type=unit_type,
                    title=metas.get("title"),
                    channel_id=metas.get("channel_id"),
                    channel_name=metas.get("channel_name"),
                    commenter_count=len(authors.get(unit, {})),
                    comment_count=total,
                    identity_coverage=StatisticsService.ratio(identified, total),
                    avg_jaccard=_mean(avg_metric.get(unit)),
                )
            )

        heatmap: dict[str, dict[str, float | None]] = {}
        for a, b in combinations(ordered_units, 2):
            value = pair_metric.get((a, b))
            heatmap.setdefault(a, {})[b] = value
            heatmap.setdefault(b, {})[a] = value

        overlap_edges = [
            {
                "entity_a": p.entity_a,
                "entity_b": p.entity_b,
                "shared_commenter_count": p.intersection_size,
                "jaccard": p.jaccard,
            }
            for p in pairs
            if p.intersection_size >= min_shared
        ]

        bridges, top_shared = self._author_rankings(
            authors=authors,
            kinds=kinds,
            min_entities=min_entities,
            top_n=top_n,
            global_videos=global_videos,
            global_channels=global_channels,
        )

        pair_values = [
            v for v in (_metric_key(p) for p in pairs) if v is not None
        ]
        max_jaccard = _argmax(
            pairs, key=lambda p: (p.jaccard is None, -(p.jaccard or 0))
        )
        max_shared = _argmax(
            pairs, key=lambda p: (-p.intersection_size, p.entity_a, p.entity_b)
        )
        summary = ProjectionSummary(
            entity_type=unit_type,
            entity_count=len(ordered_units),
            commenter_count=len(
                {key for unit_authors in authors.values() for key in unit_authors}
            ),
            comment_count=sum(comment_count.values()),
            unidentified_comments=sum(unidentified.values()),
            pair_count=len(pairs),
            average_jaccard=_mean(pair_values),
            max_jaccard_pair=(
                {
                    "entity_a": max_jaccard.entity_a,
                    "entity_b": max_jaccard.entity_b,
                    "jaccard": max_jaccard.jaccard,
                    "intersection_size": max_jaccard.intersection_size,
                }
                if max_jaccard is not None
                else None
            ),
            max_shared_pair=(
                {
                    "entity_a": max_shared.entity_a,
                    "entity_b": max_shared.entity_b,
                    "intersection_size": max_shared.intersection_size,
                }
                if max_shared is not None
                else None
            ),
            bridge_commenter_count=len(bridges),
        )

        return CommenterProjection(
            entity_type=unit_type,
            entities=entities,
            pairs=pairs,
            heatmap=heatmap,
            overlap_edges=overlap_edges,
            bridge_commenters=bridges,
            top_shared_commenters=top_shared,
            summary=summary,
        )

    def _author_rankings(
        self,
        *,
        authors: dict[str, dict[str, _AuthorAgg]],
        kinds: dict[str, IdentityKind],
        min_entities: int,
        top_n: int,
        global_videos: dict[str, set[str]],
        global_channels: dict[str, set[str]],
    ) -> tuple[list[BridgeCommenter], list[TopSharedCommenter]]:
        per_author: dict[str, dict[str, int]] = {}
        first_agg: dict[str, _AuthorAgg] = {}
        for unit, unit_authors in authors.items():
            for key, agg in unit_authors.items():
                per_author.setdefault(key, {})[unit] = agg.count
                first_agg.setdefault(key, agg)

        bridges: list[BridgeCommenter] = []
        for key, units in per_author.items():
            if len(units) < min_entities:
                continue
            agg = first_agg[key]
            bridges.append(
                BridgeCommenter(
                    author_key=key,
                    author_name=agg.display_name,
                    identity_kind=kinds[key],
                    entity_count=len(units),
                    comment_count=sum(units.values()),
                    video_count=len(global_videos.get(key, set())),
                    channel_count=len(global_channels.get(key, set())),
                    entities=sorted(
                        (
                            {"entity_id": u, "comment_count": n}
                            for u, n in units.items()
                        ),
                        key=lambda e: (-e["comment_count"], e["entity_id"]),
                    ),
                    first_seen_at=agg.first_seen,
                    last_seen_at=agg.last_seen,
                )
            )
        bridges.sort(key=lambda b: (-b.entity_count, -b.comment_count, b.author_key))

        top_shared: list[TopSharedCommenter] = []
        for key, units in per_author.items():
            agg = first_agg[key]
            top_shared.append(
                TopSharedCommenter(
                    author_key=key,
                    author_name=agg.display_name,
                    identity_kind=kinds[key],
                    entity_count=len(units),
                    comment_count=sum(units.values()),
                    video_count=len(global_videos.get(key, set())),
                    channel_count=len(global_channels.get(key, set())),
                )
            )
        top_shared.sort(
            key=lambda t: (-t.comment_count, -t.entity_count, t.author_key)
        )
        return bridges[:top_n], top_shared[:top_n]
