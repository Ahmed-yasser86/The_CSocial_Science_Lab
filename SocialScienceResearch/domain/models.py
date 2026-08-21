"""Domain models for the SocialScienceResearch module.

Design principles
-----------------
* **Stable identity + time-varying observations.** Time-varying statistics
  (views, likes, comments, subscribers) never live on the entity model; they
  live on per-run ``*Observation`` models. A second collection of the same
  entity therefore produces a new observation rather than overwriting history.
* **Raw vs derived.** Every entity/observation preserves ``raw_json`` (the
  sanitized source payload). Analytics never write derived values back into
  source rows.
* **Provenance.** Every row carries the ``collection_run_id`` (and
  ``observed_at``) that produced it, and ``first_observed_run_id`` records
  where an entity was first discovered.
* **No fabrication.** Optional fields default to ``None`` and stay ``None``
  when the source does not provide them.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    CollectionStatus,
    EntityType,
    ErrorType,
    RecommendationStatus,
    RunType,
    TranscriptStatus,
)

# Pydantic v2: allow dict types like RawSourceValue and keep ordering stable.
_MODEL_CONFIG = ConfigDict(extra="allow", arbitrary_types_allowed=False)


class CollectionRun(BaseModel):
    """A single acquisition run (channel, video or recommendation).

    Tracks what was collected, when, from which source, how many entities
    succeeded/failed, and which configuration produced it. This is the
    backbone of research reproducibility.
    """

    model_config = _MODEL_CONFIG

    run_id: str
    run_type: RunType
    target_url: str
    target_channel_id: str | None = None
    target_video_id: str | None = None
    parent_run_id: str | None = None  # the run that triggered this one (lineage)
    started_at: datetime
    finished_at: datetime | None = None
    status: CollectionStatus = CollectionStatus.PENDING
    provider: str = "yt-dlp"
    provider_version: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    entities_discovered: int = 0
    entities_succeeded: int = 0
    entities_existing: int | None = None
    entities_failed: int = 0
    comments_collected: int | None = None
    notes: list[str] = Field(default_factory=list)
    name: str | None = None  # researcher-provided display label (editable)
    layer_index: int | None = None  # the crawl layer this run was created in (None outside a crawl)


class CollectionError(BaseModel):
    """A per-entity failure recorded during a run.

    Failures are never silently discarded; each is observable and associated
    with its run and (where known) its entity.
    """

    model_config = _MODEL_CONFIG

    error_id: str
    run_id: str
    entity_type: EntityType
    entity_id: str | None = None
    error_type: ErrorType = ErrorType.UNKNOWN
    message: str
    occurred_at: datetime
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class Channel(BaseModel):
    """Stable identity and slow-changing metadata of a YouTube channel.

    Time-varying statistics (subscribers, video count, view count) live on
    :class:`ChannelObservation`.
    """

    model_config = _MODEL_CONFIG

    channel_id: str
    url: str
    title: str | None = None
    description: str | None = None
    handle: str | None = None
    is_verified: bool | None = None
    avatar_url: str | None = None
    banner_url: str | None = None
    country: str | None = None
    joined_date: date | None = None
    first_observed_run_id: str
    raw_json: dict[str, Any] = Field(default_factory=dict)


class ChannelObservation(BaseModel):
    """One observation of a channel's statistics during a run."""

    model_config = _MODEL_CONFIG

    observation_id: str
    collection_run_id: str
    channel_id: str
    observed_at: datetime
    subscriber_count: int | None = None
    video_count: int | None = None
    view_count: int | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)


class Video(BaseModel):
    """Stable identity and immutable-ish metadata of a YouTube video.

    ``upload_date``/``upload_timestamp`` are publication facts (from the
    source); view/like/comment counters live on :class:`VideoObservation`.
    """

    model_config = _MODEL_CONFIG

    video_id: str
    url: str
    channel_id: str | None = None
    title: str | None = None
    description: str | None = None
    duration: int | None = None  # seconds
    upload_date: date | None = None
    upload_timestamp: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    language: str | None = None
    live_status: str | None = None
    availability: str | None = None
    age_limit: int | None = None
    is_short: bool | None = None
    thumbnail_url: str | None = None
    chapters_json: list[dict[str, Any]] = Field(default_factory=list)
    transcript_path: str | None = None
    transcript_status: str | None = None
    transcript_lang: str | None = None
    first_observed_run_id: str
    recommendations_scraped: bool = False
    raw_json: dict[str, Any] = Field(default_factory=dict)


class VideoObservation(BaseModel):
    """One observation of a video's public statistics during a run."""

    model_config = _MODEL_CONFIG

    observation_id: str
    collection_run_id: str
    video_id: str
    observed_at: datetime
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    favorite_count: int | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)


class Comment(BaseModel):
    """Stable identity and slow-changing text of a comment.

    ``comment_text`` and ``published_at`` are publication facts captured at
    first observation. Time-varying behaviour (likes, reply count, removal)
    lives on :class:`CommentObservation` so comment evolution can be studied.
    """

    model_config = _MODEL_CONFIG

    comment_id: str
    video_id: str
    author_name: str | None = None
    author_id: str | None = None
    comment_text: str | None = None
    published_at: datetime | None = None
    is_reply: bool = False
    parent_comment_id: str | None = None
    root_comment_id: str | None = None
    is_author: bool | None = None  # True if the video uploader authored it
    first_observed_run_id: str
    raw_json: dict[str, Any] = Field(default_factory=dict)


class CommentObservation(BaseModel):
    """One observation of a comment's statistics during a run."""

    model_config = _MODEL_CONFIG

    observation_id: str
    collection_run_id: str
    comment_id: str
    observed_at: datetime
    like_count: int | None = None
    reply_count: int | None = None
    is_removed: bool | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)


class RecommendationObservation(BaseModel):
    """An observed recommendation relationship (source video -> video).

    Recommendations are *observed relationships*, not permanent properties.
    The tuple ``(collection_run_id, source_video_id, recommended_video_id)``
    is unique: repeated runs never overwrite earlier observations, which makes
    the data suitable for temporal network analysis (future NetworkX module).
    """

    model_config = _MODEL_CONFIG

    observation_id: str
    collection_run_id: str
    source_video_id: str
    recommended_video_id: str
    position: int | None = None  # ordering reported by the source, if any
    status: RecommendationStatus = RecommendationStatus.OBSERVED
    channel_id: str | None = None
    channel_name: str | None = None
    title: str | None = None
    observed_at: datetime | None = None  # when the edge was observed (migration-safe)
    layer_index: int | None = None  # denormalized producing-run layer (layer-filterable in one scan)
    raw_json: dict[str, Any] = Field(default_factory=dict)


class TranscriptRecord(BaseModel):
    """Metadata for an externally stored video transcript artifact.

    The transcript *content* lives in an external ``.txt`` file (never inside
    Excel); this row records the stable reference, provenance and status so a
    missing or unsupported transcript is explicit and auditable.
    """

    model_config = _MODEL_CONFIG

    transcript_id: str
    video_id: str
    collection_run_id: str
    path: str | None = None  # relative path to the external .txt artifact
    lang: str | None = None
    status: TranscriptStatus = TranscriptStatus.MISSING
    message: str | None = None
    observed_at: datetime | None = None  # optional: legacy workbooks lack this column


class AuthorProfile(BaseModel):
    """Aggregated author participation profile derived from comments (D4).

    A comment author is identified by ``author_id`` (falling back to
    ``author_name`` when the id is absent). The profile aggregates every
    persisted comment the author contributed: participation count, the set of
    videos commented on, first/last seen timestamps, the producing run, and a
    best-effort ``raw_json`` carrying the raw author metadata already collected
    with comments (ADR-0010: raw profiles are included for author/participation
    research and dataset/export use).

    The profile is *derived* data - it is rebuilt from the comments corpus on
    read (``AuthorRepository``) and is never written back into source rows.
    """

    model_config = _MODEL_CONFIG

    author_id: str
    author_name: str | None = None
    comment_count: int = 0
    video_ids: list[str] = Field(default_factory=list)
    first_seen_run_id: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    is_author: bool | None = None  # True if the author ever authored the video
    raw_json: dict[str, Any] = Field(default_factory=dict)
