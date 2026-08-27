"""Typed HTTP response models for the SocialScienceResearch API.

Every endpoint declares a ``response_model`` built from these schemas. Field
names and shapes mirror the previous hand-built payloads exactly (``extra``
is allowed so nothing is silently stripped), except where a proven defect was
fixed (e.g. ``/top`` now annotates MISSING rows with ``availability``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.domain.layer_models import ScrapeFilters
from SocialScienceResearch.services.pagination import Paginated

__all__ = [
    "ChannelCountPayload",
    "ChannelOverviewPayload",
    "ChannelPayload",
    "CollectionErrorPayload",
    "CollectionResultPayload",
    "CollectionResultsPayload",
    "CommentPayload",
    "CommentStatsPayload",
    "CommentTreePayload",
    "DatasetSummaryPayload",
    "EchoContinueRequest",
    "EchoDetectRequest",
    "EchoDetectionStartPayload",
    "ErrorPayload",
    "ExportRequest",
    "ExportResponse",
    "FolderPathsPayload",
    "JobCancelPayload",
    "JobFailurePayload",
    "JobPayload",
    "JobResultPayload",
    "JobSubmitPayload",
    "JobTagsRequest",
    "LayerBootstrapRequest",
    "LayerScrapeRequest",
    "NetworkExportToProjectRequest",
    "NetworkMergeRequest",
    "NetworkScopeRequest",
    "NetworkSummaryPayload",
    "OperatorInfoPayload",
    "Paginated",
    "PercentilesPayload",
    "QueryPreviewResponse",
    "QueryResolveResponse",
    "RawVideoPayload",
    "RecommendationPayload",
    "RunPayload",
    "RunVideosPayload",
    "SamplingResultPayload",
    "SystemFoldersPayload",
    "ThreadPayload",
    "TopVideosPayload",
    "TopVideoRow",
    "UpdateRunRequest",
    "VariableMetaPayload",
    "VelocityPoint",
    "VideoEngagementPayload",
    "VideoNetworkContextPayload",
    "VideoObservationPayload",
    "VideoPayload",
]


class _Base(BaseModel):
    """Extra fields pass through unchanged (frontend-compatible payloads)."""

    model_config = ConfigDict(extra="allow")


class ValuePayload(_Base):
    value: float | int | None = None
    availability: str = "available"


class CollectionErrorPayload(_Base):
    error_id: str
    run_id: str
    entity_type: str
    entity_id: str | None = None
    error_type: str
    message: str
    occurred_at: datetime
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class CollectionResultPayload(_Base):
    run_id: str
    run_type: str
    status: str
    target_url: str
    target_id: str | None = None
    entities_discovered: int = 0
    entities_created: int = 0
    entities_existing: int = 0
    entities_failed: int = 0
    comments_collected: int = 0
    errors: list[CollectionErrorPayload] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CollectionResultsPayload(_Base):
    target_count: int
    results: list[CollectionResultPayload] = Field(default_factory=list)


class JobSubmitPayload(_Base):
    job_id: str


class JobPayload(_Base):
    job_id: str
    kind: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    cancel_requested: bool = False
    tags: list[str] = Field(default_factory=list)
    # J1 additive fields: nested run provenance (grouped children) + the
    # persisted row's params/result summary when the job came from storage.
    runs: list[dict[str, Any]] = Field(default_factory=list)
    result_json: dict[str, Any] = Field(default_factory=dict)


class JobTagsRequest(_Base):
    """Body for ``PATCH .../jobs/{job_id}/tags`` (``extra="forbid"``)."""

    model_config = ConfigDict(extra="forbid")

    tags: list[str] = Field(default_factory=list)


class JobCancelPayload(_Base):
    job_id: str
    cancelled: bool


class JobFailurePayload(_Base):
    error: str


class JobResultPayload(_Base):
    """Union-shaped job result (single result, many results, or failure)."""

    error: str | None = None
    target_count: int | None = None
    results: list[CollectionResultPayload] | None = None
    run_id: str | None = None
    run_type: str | None = None
    status: str | None = None
    target_url: str | None = None
    target_id: str | None = None
    entities_discovered: int | None = None
    entities_created: int | None = None
    entities_existing: int | None = None
    entities_failed: int | None = None
    comments_collected: int | None = None
    errors: list[CollectionErrorPayload] | None = None
    skipped: list[dict[str, Any]] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    dataset_id: str | None = None


class RunPayload(_Base):
    run_id: str
    run_type: str
    target_url: str
    target_channel_id: str | None = None
    target_video_id: str | None = None
    parent_run_id: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    provider: str = "yt-dlp"
    provider_version: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)
    entities_discovered: int = 0
    entities_succeeded: int = 0
    entities_existing: int | None = None
    entities_failed: int = 0
    comments_collected: int | None = None
    notes: list[str] = Field(default_factory=list)
    name: str | None = None
    layer_index: int | None = None
    job_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class UpdateRunRequest(_Base):
    """Body for ``PATCH .../runs/{run_id}`` (``extra="forbid"``).

    Only explicitly provided fields are applied; editable fields are the
    researcher-provided ``name`` label and ``tags``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    tags: list[str] | None = None


class LayerBootstrapRequest(_Base):
    """Body for ``POST .../network/layer`` (``extra="forbid"``).

    Creates the seed ``LayerRun`` (layer 0) from an existing run whose videos/
    sources become the crawl frontier.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    projection: str = "video"


class LayerScrapeRequest(_Base):
    """Body for ``POST .../network/layer/scrape`` (``extra="forbid"``).

    Either ``parent_layer_run_id`` (advance an existing crawl) or a seed
    ``parent_run_id`` (start layer 1) is required. ``projection`` selects the
    graph view; ``collect_comments`` toggles comment enrichment for new videos.
    """

    model_config = ConfigDict(extra="forbid")

    parent_layer_run_id: str | None = None
    parent_run_id: str | None = None
    projection: str = "video"
    collect_comments: bool = True
    concurrency: int | None = None
    max_recommendations_per_video: int | None = Field(
        None,
        ge=1,
        le=2000,
        description=(
            "Optional cap on how many recommendations to keep per frontier "
            "video (speeds up wide crawls). Omit for no per-video limit."
        ),
    )
    discovery_mode: Literal["frontier", "rescrape_known"] = Field(
        "rescrape_known",
        description=(
            "How the resolved frontier is crawled. 'rescrape_known' (default, "
            "the historical behaviour) re-observes every resolved frontier "
            "video's recommendations even if that feed was already scraped "
            "earlier in this crawl family. 'frontier' skips videos whose "
            "recommendations were already observed anywhere and only scrapes "
            "genuinely unexplored nodes."
        ),
    )


class ContentHomophilyStartRequest(_Base):
    """Body for ``POST .../network/content-homophily`` (``extra="forbid"``).

    Opt-in, on-demand CONTENT evidence over ANY network scope: ``run_id``
    pins the analysis to one run's slice, ``video_ids`` to an explicit set;
    with neither, the whole persisted recommendation network is analyzed.
    Transcript collection is targeted at the sampled videos only.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    video_ids: list[str] = Field(default_factory=list)
    sampling_fraction: float = Field(
        0.10,
        gt=0,
        le=1.0,
        description=(
            "Computational pair-sampling fraction (5%/10%/20% typical). NOT "
            "a claim of statistical representativeness."
        ),
    )
    max_pair_cap: int = Field(
        10_000,
        ge=1,
        le=10_000,
        description=(
            "Hard cap on sampled pairs per pair-selection operation "
            "(never exceeded)."
        ),
    )
    random_seed: int | None = Field(
        None,
        description="Seeded sampling; recorded for reproducibility.",
    )
    num_permutations: int = Field(
        1000,
        ge=0,
        le=10_000,
        description="Community-label permutation count for the null model.",
    )
    max_videos_per_community: int = Field(
        40,
        ge=2,
        le=2000,
        description=(
            "Replacement-sampling limit per community when transcripts are "
            "missing."
        ),
    )
    max_transcript_videos: int = Field(
        200,
        ge=1,
        le=2000,
        description=(
            "Hard cap on UNIQUE videos for transcript/embedding collection in a "
            "single analysis. Selection picks a balanced, community-representative "
            "set of at most this many videos (prioritising those with existing "
            "transcripts) and samples pairs only from them, so collection never "
            "exceeds this budget. The dominant, rate-limited cost (YouTube 429s) "
            "is therefore bounded independently of the pair count."
        ),
    )
    include_edge_similarity: bool = Field(
        False,
        description=(
            "Optional separate recommendation-edge semantic similarity "
            "(kept distinct from community-level homophily)."
        ),
    )
    tags: list[str] = Field(default_factory=list)


class ContentHomophilyStartPayload(_Base):
    """Response of ``POST .../network/content-homophily``."""

    analysis_id: str
    job_id: str | None = None
    status: str = "pending"


class EchoDetectRequest(_Base):
    """Body for ``POST .../echo-chamber/detect`` (``extra="forbid"``).

    Identifies the seed (``video_url`` | ``video_id`` | ``seed_run_id``) and
    the crawl budget. ``collect_comments`` opts in to comment collection so
    the S5 commenter-overlap signal can be observed.
    """

    model_config = ConfigDict(extra="forbid")

    video_url: str | None = None
    video_id: str | None = None
    seed_run_id: str | None = None
    max_layers: int = Field(
        5, ge=1, le=10, description="Layers to crawl (hard cap 10)."
    )
    collect_comments: bool = False
    projection: Literal["video", "channel"] = Field(
        "video",
        description=(
            "Which node type the chamber analysis runs over: the seed "
            "video's recommendation graph of videos, or the channel-level "
            "graph (communities/concentration measured on channels)."
        ),
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Researcher labels applied to the job and its runs.",
    )


class EchoContinueRequest(_Base):
    """Body for ``POST .../echo-chamber/{id}/continue`` (``extra="forbid"``)."""

    model_config = ConfigDict(extra="forbid")

    extra_layers: int = Field(
        1, ge=1, le=10, description="Additional layers to append (lifetime cap 10)."
    )


class EchoDetectionStartPayload(_Base):
    """Response of ``POST .../echo-chamber/detect``."""

    detection_id: str
    job_id: str | None = None
    status: str = "pending"


class ExpansionScrapeVideoRequest(_Base):
    """Body for ``POST .../network/expansion/scrape-video``.

    One-hop expansion of a single video; ``filters`` controls what is scraped
    from its recommendations.
    """

    model_config = ConfigDict(extra="forbid")

    video_id: str
    filters: ScrapeFilters = Field(default_factory=ScrapeFilters)


class ExpansionScrapeAllRequest(_Base):
    """Body for ``POST .../network/expansion/scrape-all``.

    One-hop expansion of the current network slice: either an explicit
    ``video_ids`` list or a ``run_id`` whose videos/sources form the scope.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    video_ids: list[str] = Field(default_factory=list)
    filters: ScrapeFilters = Field(default_factory=ScrapeFilters)


class NetworkScopeRequest(_Base):
    """A video-network scope (``extra="forbid"``).

    ``run_id`` pins the slice to one collection run, ``action_id`` to a
    network-expansion action (its runs), ``video_ids`` to the ego edges
    touching any listed video. An empty scope = the whole persisted network.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    action_id: str | None = None
    video_ids: list[str] = Field(default_factory=list)


class NetworkExportToProjectRequest(_Base):
    """Body for ``POST .../network/export-to-project`` (``extra="forbid"``).

    Serializes a scoped video network (graphml/edgelist/gexf/csv/json) and
    persists it as a :class:`ProjectItem` artifact under a Project. With no
    scope the whole persisted recommendation network is exported.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str
    format: str = "graphml"
    run_id: str | None = None
    action_id: str | None = None
    video_ids: list[str] = Field(default_factory=list)
    channel_id: str | None = None
    channel_ids: list[str] = Field(default_factory=list)
    channel_scope: str = "source"
    layer_index: int | None = None
    connected: str | None = None
    scraped: str | None = None
    projection: str = "video"
    name: str | None = None
    description: str | None = None


class NetworkMergeRequest(_Base):
    """Body for ``POST .../network/merge`` (``extra="forbid"``).

    Merges two scoped video networks and reports the overlap (shared
    nodes/edges, Jaccard) plus combined SNA statistics on the union graph.
    """

    model_config = ConfigDict(extra="forbid")

    scope_a: NetworkScopeRequest
    scope_b: NetworkScopeRequest
    top_n: int = Field(default=10, ge=1, le=500)


class ChannelPayload(_Base):
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


class VideoPayload(_Base):
    video_id: str
    url: str
    channel_id: str | None = None
    title: str | None = None
    description: str | None = None
    duration: int | None = None
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
    raw_json: dict[str, Any] = Field(default_factory=dict)


class VideoObservationPayload(_Base):
    observation_id: str
    collection_run_id: str
    video_id: str
    observed_at: datetime
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    favorite_count: int | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)


class CommentPayload(_Base):
    comment_id: str
    video_id: str
    author_name: str | None = None
    author_id: str | None = None
    comment_text: str | None = None
    published_at: datetime | None = None
    is_reply: bool = False
    parent_comment_id: str | None = None
    root_comment_id: str | None = None
    is_author: bool | None = None
    first_observed_run_id: str
    # Latest observation stats
    like_count: int | None = None
    reply_count: int | None = None
    is_removed: bool | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)


class RecommendationPayload(_Base):
    observation_id: str
    collection_run_id: str
    source_video_id: str
    recommended_video_id: str
    position: int | None = None
    status: str
    channel_id: str | None = None
    title: str | None = None
    run_type: str | None = None
    observed_at: datetime | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)


class ThreadPayload(_Base):
    comment: CommentPayload
    replies: list[CommentPayload] = Field(default_factory=list)


class CommentTreePayload(_Base):
    """Full comment tree with nested replies for a root comment."""
    comment: CommentPayload
    replies: list["CommentTreePayload"] = Field(default_factory=list)
    total_replies: int = 0
    max_depth: int = 0


CommentTreePayload.model_rebuild()


class ChannelOverviewPayload(_Base):
    channel_id: str
    observed_at: datetime | None = None
    subscribers: ValuePayload
    videos: ValuePayload
    views: ValuePayload


class VideoEngagementPayload(_Base):
    video_id: str
    observed_at: datetime | None = None
    views: ValuePayload
    likes: ValuePayload
    comments: ValuePayload
    engagement_rate: ValuePayload
    like_rate: ValuePayload
    comment_rate: ValuePayload


class PercentilesPayload(_Base):
    video_id: str
    availability: str
    observed_like_counts: list[int] = Field(default_factory=list)
    bands: dict[str, float | None] = Field(default_factory=dict)


class VelocityPoint(_Base):
    bucket: str
    count: int


class TopVideoRow(_Base):
    video_id: str
    title: str | None = None
    views: float | int | None = None
    likes: float | int | None = None
    comments: float | int | None = None
    observed_at: datetime | None = None
    availability: str = "available"


class TopVideosPayload(_Base):
    channel_id: str
    metric: str
    top: list[TopVideoRow] = Field(default_factory=list)


class SamplingResultPayload(_Base):
    strategy: str
    entity_type: str
    population_size: int
    sample_size: int
    entity_ids: list[str] = Field(default_factory=list)
    criteria_json: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None
    missing_metric_count: int = 0


class RawVideoPayload(_Base):
    video_id: str
    raw_json: dict[str, Any] = Field(default_factory=dict)


class ChannelCountPayload(_Base):
    channel_id: str
    count: int


class NetworkSummaryPayload(_Base):
    node_count: int = 0
    edge_count: int = 0
    source_count: int = 0
    target_count: int = 0
    most_recommended: list[dict[str, Any]] = Field(default_factory=list)
    most_active_sources: list[dict[str, Any]] = Field(default_factory=list)
    highest_pagerank: list[dict[str, Any]] = Field(default_factory=list)


class VideoNetworkContextPayload(_Base):
    video_id: str
    in_degree: int = 0
    out_degree: int = 0
    pagerank: float | None = None
    recommended_by: list[dict[str, Any]] = Field(default_factory=list)
    recommends: list[dict[str, Any]] = Field(default_factory=list)
    graph_edges: list[dict[str, Any]] = Field(default_factory=list)
    node_channels: dict[str, str] = Field(default_factory=dict)


class DatasetSummaryPayload(_Base):
    generated_at: datetime
    channels: int
    videos: int
    comments: int
    transcripts_available: int
    transcript_coverage: float
    runs: int


class ErrorPayload(_Base):
    """Machine-readable error envelope used by every 4xx/5xx response."""

    code: str
    message: str
    detail: str | None = None


class VariableMetaPayload(_Base):
    """One registered research variable of an entity."""

    entity: str
    name: str
    data_type: str
    source: str
    description: str
    unit: str | None = None
    availability: str
    limits: str | None = None


class OperatorInfoPayload(_Base):
    """One operator understood by the research query evaluator."""

    name: str
    description: str


class QueryPreviewStage(_Base):
    """A single funnel stage: cumulative = rows matching the prefix so far,
    matched = incremental drop caused by adding this condition."""

    condition: str
    matched: int
    cumulative: int


class QueryPreviewResponse(_Base):
    """Response of ``POST /research/query/preview``."""

    total: int
    stages: list[QueryPreviewStage] = Field(default_factory=list)
    population_size: int
    n: int


class QueryResolveResponse(_Base):
    """Count-only response of ``POST /research/query/resolve``."""

    total: int
    population_size: int


class RunVideosPayload(_Base):
    """Paginated list of videos collected in a run."""

    run_id: str
    items: list[VideoPayload] = Field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False
    total: int = 0


class CommentStatsPayload(_Base):
    """Comment statistics for a video."""

    video_id: str
    max_replies: int = 0
    max_unique_repliers: int = 0
    total_replies: int = 0
    total_unique_repliers: int = 0


class SystemFoldersPayload(_Base):
    """System folder paths."""

    workbook_path: str
    transcripts_dir: str
    datasets_dir: str
    samples_dir: str
    data_dir: str


class ExportRequest(_Base):
    """Request to export selected data to Excel.

    Provide ``entity_type`` (+ optional ``ids``/``columns``) for a single-entity
    sheet, or ``project_id`` to export *everything a project collected* as a
    multi-sheet workbook (Videos, Comments, Channels, Recommendations, Runs).
    """

    entity_type: str | None = None  # "video" | "comment" | "channel" | "run" | "sample" | "dataset"
    ids: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    filename: str | None = None
    project_id: str | None = None


class ExportResponse(_Base):
    """Response for export endpoint (file download handled separately)."""

    filename: str
    row_count: int
