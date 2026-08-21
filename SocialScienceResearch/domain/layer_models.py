"""Layer-crawl domain models (docs/analysis_next_layer_scrape.md).

A :class:`LayerRun` is the crawl anchor written *after* a crawl step
completes (like datasets): it records the frontier that was expanded, the
videos newly deep-enriched this layer, the recommendation runs created and
the NewRelationsReport counts, so "resume the crawl" and "show the summary of
layer N" are cheap reads instead of O(edges) scans.

Response/record models use ``extra="allow"`` (the UI never silently loses a
column); request models live in ``api/schemas.py`` and use ``extra="forbid"``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import CollectionStatus

_RESPONSE_CONFIG = ConfigDict(extra="allow")


class LayerRun(BaseModel):
    """A completed crawl layer: the anchor record for layer research.

    ``frontier_video_ids`` is the frontier that was expanded (layer 0: the seed
    run's videos/sources); ``discovered_video_ids`` are the NEW videos
    deep-enriched by this layer; ``summary`` carries the NewRelationsReport
    ``counts`` dict verbatim so ``GET /network/layer/{id}`` returns counts
    without recomputation.
    """

    model_config = _RESPONSE_CONFIG

    layer_run_id: str  # new_id("lyr")
    layer_index: int  # 0 = seed, 1 = first crawl, ...
    parent_run_id: str | None = None  # run expanded (the trigger)
    parent_layer_run_id: str | None = None  # previous LayerRun id (None for seed)
    projection: str = "video"  # "channel" | "video" chosen at crawl time
    started_at: datetime
    finished_at: datetime | None = None
    status: CollectionStatus = CollectionStatus.PENDING
    frontier_video_ids: list[str] = Field(default_factory=list)
    discovered_video_ids: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    comments_collected: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)
    config_json: dict[str, Any] = Field(default_factory=dict)


class ComponentSummary(BaseModel):
    """One connected component of a layer's new-edge subgraph."""

    model_config = _RESPONSE_CONFIG

    component_id: str  # lexicographically smallest node id (deterministic)
    node_count: int
    edge_count: int
    touches_channels: list[str] = Field(default_factory=list)
    node_video_ids: list[str] = Field(default_factory=list)


class NewVideoEntry(BaseModel):
    """One newly discovered video in a NewRelationsReport."""

    model_config = _RESPONSE_CONFIG

    video_id: str
    title: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    thumbnail_url: str | None = None
    classification: str = "new_video"


class NewChannelEntry(BaseModel):
    """One newly discovered channel in a NewRelationsReport."""

    model_config = _RESPONSE_CONFIG

    channel_id: str
    channel_name: str | None = None
    avatar_url: str | None = None


class ExistingVideoEntry(BaseModel):
    """One existing video referenced by the layer (classification info)."""

    model_config = _RESPONSE_CONFIG

    video_id: str
    title: str | None = None
    channel_id: str | None = None


class NewRelationsReport(BaseModel):
    """The "what did this crawl add?" classification report (doc §5.4).

    ``counts`` is authoritative; every list is capped so a large layer does
    not produce a megabyte response (caps documented per field).
    """

    model_config = _RESPONSE_CONFIG

    layer_run_id: str
    layer_index: int
    projection: str
    generated_at: datetime
    counts: dict[str, int] = Field(default_factory=dict)
    new_videos: list[NewVideoEntry] = Field(default_factory=list)  # capped at 200
    existing_videos: list[ExistingVideoEntry] = Field(default_factory=list)  # capped
    new_channels: list[NewChannelEntry] = Field(default_factory=list)  # capped
    connected_components: list[ComponentSummary] = Field(default_factory=list)
    disconnected_components: list[ComponentSummary] = Field(default_factory=list)
    sample_edges: list[dict[str, Any]] = Field(default_factory=list)  # first <=50 edges (EdgeRow shape)


class LayerFrontier(BaseModel):
    """The frontier of a layer (drives the layer stepper UI)."""

    model_config = _RESPONSE_CONFIG

    layer_index: int
    video_ids: list[str] = Field(default_factory=list)
    video_count: int = 0


class LayerRunPayload(BaseModel):
    """API serialization of :class:`LayerRun` (doc §6 payloads)."""

    model_config = _RESPONSE_CONFIG

    layer_run_id: str
    layer_index: int
    parent_run_id: str | None = None
    parent_layer_run_id: str | None = None
    projection: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    frontier_video_ids: list[str] = Field(default_factory=list)
    discovered_video_ids: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    comments_collected: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)
    config_json: dict[str, Any] = Field(default_factory=dict)


class ScrapeFilters(BaseModel):
    """What a network-expansion scrape should collect from the recommendations.

    Request-side (``extra="forbid"``). Defaults mirror the click-to-scrape
    behaviour: collect comments, skip already-observed edges, deep-enrich only
    videos the corpus does not know yet, project onto the video graph.
    """

    model_config = ConfigDict(extra="forbid")

    max_recommendations_per_video: int | None = Field(
        default=None, ge=1, description="Keep only the top-N recommendations per feed"
    )
    collect_comments: bool = True
    comment_min_likes: int | None = Field(default=None, ge=0)
    comment_date_from: str | None = None
    comment_date_to: str | None = None
    max_comments_per_video: int | None = Field(default=None, ge=1)
    dedupe: bool = True
    only_new_targets: bool = True
    concurrency: int | None = Field(default=None, ge=1)
    projection: str = "video"


class ExpansionActionPayload(BaseModel):
    """API serialization of a network-expansion action anchor.

    An expansion action reuses the :class:`LayerRun` store with
    ``config_json["expansion"]`` marking the kind / filters / auto-project; the
    payload flattens those fields for the UI.
    """

    model_config = _RESPONSE_CONFIG

    action_id: str
    kind: str  # "video" | "all"
    parent_run_id: str | None = None
    projection: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    video_ids: list[str] = Field(default_factory=list)  # frontier/source videos
    discovered_video_ids: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    comments_collected: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None


class VideoExpansionStats(BaseModel):
    """Per-video stats within a network-expansion action (doc §4.1)."""

    model_config = _RESPONSE_CONFIG

    video_id: str
    title: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    recommendation_count: int = 0  # out-degree within the action's subgraph
    in_degree: int = 0
    new_targets: int = 0  # target videos this source newly discovered
    new_channels: int = 0
    new_edges: int = 0
    comments_collected: int = 0


class ExpansionOverallStats(BaseModel):
    """Overall (global) statistics over an expansion action's subgraph."""

    model_config = _RESPONSE_CONFIG

    node_count: int
    edge_count: int
    channel_count: int
    source_count: int
    component_count: int
    avg_out_degree: float | None = None
    density: float | None = None
    comment_count: int = 0


class ExpansionStats(BaseModel):
    """Overall + per-video stats for one network-expansion action."""

    model_config = _RESPONSE_CONFIG

    action: ExpansionActionPayload
    overall: ExpansionOverallStats
    videos: list[VideoExpansionStats] = Field(default_factory=list)
