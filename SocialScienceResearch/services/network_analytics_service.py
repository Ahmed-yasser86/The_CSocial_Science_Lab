"""Full network analytics over persisted recommendation edges (module B6).

Extends :class:`RecommendationGraphService` with:

* ``metrics`` - macro statistics for one network slice: density, reciprocity,
  degree-distribution percentiles, clustering, weak components, detected
  communities (greedy modularity) and the top HITS hubs/authorities;
* ``temporal`` - per-run ``NetworkSlice`` snapshots plus growth between
  consecutive requested runs;
* ``edges`` / ``export_edges`` / ``export_network`` - raw edge listing and
  graphml/edgelist/gexf/csv/json export for interoperability with external
  tools, scoped by run, run set (expansion action) or video ego;
* ``merge_networks`` - overlap (shared nodes/edges, Jaccard) + combined SNA
  statistics over the union of two scopes;
* ``graph`` - enriched node/edge payload that drives the interactive graph UI
  (every node carries ``[ID] + Channel Name + Video Title + metrics``);
* ``channel_projection`` - a lightweight channel-level projection.

NetworkX semantics (ADR-0009)
-----------------------------
* The recommendation network is built as a :class:`nx.DiGraph`
  (``RecommendationGraphService.build_graph``).
* Component analysis uses ``nx.weakly_connected_components`` - the directed
  equivalent of ``connected_components``, which raises
  ``NetworkXNotImplemented`` on a ``DiGraph``.
* Clustering coefficients are undirected-only measures, so
  ``avg_clustering`` and ``transitivity`` (global clustering) are computed on
  ``graph.to_undirected()``.
* ``reciprocity`` and ``degree`` are directed measures and run on the
  ``DiGraph`` as-is.
* Community detection uses ``louvain_communities`` (seeded for determinism)
  instead of the much slower ``greedy_modularity_communities``; ``modularity``
  is reported as ``None`` for an empty graph.
* ``nx.hits`` is a directed measure; hub/authority scores are returned
  unnormalised (the power iteration may yield small negative weights on
  graphs with zero-score sinks - the top-``n`` ranks remain meaningful).

Metadata resolution
-------------------
Node labels must never show a bare id without context. ``edges()`` and
``graph()`` enrich every row from persisted repositories (videos, video
observations, channels, runs) in a handful of batch reads - nothing is
fabricated. A recommended (target) video that was never persisted as a
``Video`` row keeps its observation-row ``title``/``channel_id`` and ``None``
for the statistics it has no row for.
"""

from __future__ import annotations

import csv
import functools
import io
import json
import time
from datetime import datetime
from io import StringIO
from threading import RLock
from typing import Any

import networkx as nx
from networkx.algorithms.community import (
    greedy_modularity_communities,
    louvain_communities,
    modularity,
)
from pydantic import BaseModel, ConfigDict, Field

from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.recommendation_graph_service import (
    RecommendationGraphService,
)
from SocialScienceResearch.services.statistics_service import StatisticsService
from SocialScienceResearch.services.weight_spec import (
    edge_weight_for_mode,
    normalize_weights,
    parse_weight_spec,
)

#: Default page size applied by list endpoints (mirrors ``api/app.py``).
DEFAULT_PAGE_SIZE = 50

#: Which endpoint of an edge a ``channel_id`` filter matches by default.
ChannelScope = str  # "source" | "target" | "either"


def centrality_battery(
    graph: "nx.Graph",
    *,
    weighted: bool = False,
    weight_attr: str = "weight",
) -> dict[str, dict[str, float]]:
    """Per-node centrality vector for an arbitrary networkx graph.

    Returns ``{node_id: {"degree", "closeness", "eigenvector",
    "betweenness"}}`` using networkx over ``graph`` (directed or undirected).

    Shared by the recommendation ``centralities()`` and the commenter-network
    service so the two network families compute identical math (no copy-paste
    drift, per the network-analysis expansion plan). ``community_id`` is added
    by the caller (it depends on the rendered slice, not just the graph).
    """
    if graph.number_of_nodes() == 0:
        return {}
    if weighted:
        total = sum(d for _, d in graph.degree(weight=weight_attr))
        degree = {
            n: (graph.degree(n, weight=weight_attr) / total if total else 0.0)
            for n in graph.nodes
        }
    else:
        degree = nx.degree_centrality(graph)
    closeness = nx.closeness_centrality(graph)
    try:
        eigenvector = nx.eigenvector_centrality(
            graph, max_iter=1000, weight=weight_attr if weighted else None
        )
    except (nx.PowerIterationFailedConvergence, nx.NetworkXError):
        eigenvector = {n: 0.0 for n in graph.nodes}
    betweenness = nx.betweenness_centrality(
        graph, weight=weight_attr if weighted else None
    )
    return {
        nid: {
            "degree": degree.get(nid, 0.0),
            "closeness": closeness.get(nid, 0.0),
            "eigenvector": eigenvector.get(nid, 0.0),
            "betweenness": betweenness.get(nid, 0.0),
        }
        for nid in graph.nodes
    }



def _hashable(value: Any) -> Any:
    """Best-effort hashable projection of cache keys (lists/dicts -> tuples)."""
    if isinstance(value, list):
        return tuple(_hashable(v) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((k, _hashable(v)) for k, v in value.items()))
    return value


_ttl_stores: list[dict[Any, tuple[float, Any]]] = []


def _ttl_cache(ttl_seconds: int):
    """Memoize a method result for ``ttl_seconds`` (per instance).

    Heavy network analytics (metrics / graph) are expensive to recompute on
    every auto-refresh. Caching keeps the API responsive and stops one slow
    endpoint from piling up and starving healthy endpoints such as ``/jobs`` -
    the same "don't let one slow/failed thing break everything" philosophy
    used elsewhere.
    """

    def decorator(fn):
        store: dict[Any, tuple[float, Any]] = {}
        _ttl_stores.append(store)
        lock = RLock()

        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            key = (
                id(self),
                fn.__name__,
                tuple(sorted((k, _hashable(v)) for k, v in kwargs.items())),
            )
            with lock:
                hit = store.get(key)
                if hit is not None and (time.time() - hit[0]) < ttl_seconds:
                    return hit[1]
            val = fn(self, *args, **kwargs)
            with lock:
                if len(store) > 500:
                    store.clear()
                store[key] = (time.time(), val)
            return val

        return wrapper

    return decorator


def _jaccard(intersection: int, union: int) -> float | None:
    """None/zero-safe Jaccard coefficient (mirrors StatisticsService.ratio)."""
    if not union:
        return None
    return round(intersection / union, 6)


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


def _dedupe_edge_rows(rows: list[EdgeRow]) -> list[EdgeRow]:
    """Drop duplicate ``(source, target)`` edge rows keeping the first seen.

    The union graph de-duplicates edges; the merged edge listing must agree
    with it (a shared edge observed by both scopes is one union edge).
    """
    seen: set[tuple[str, str]] = set()
    unique: list[EdgeRow] = []
    for row in rows:
        key = (row.source_video_id, row.recommended_video_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


class _Base(BaseModel):
    """:class:`ConfigDict` ``extra="allow"`` base for response models."""

    model_config = ConfigDict(extra="allow")


class EdgeRow(_Base):
    """One serialized recommendation edge for listing / export.

    Carries metadata for BOTH endpoint videos so the UI can render composite
    labels (``[ID] + Channel Name + Video Title + metrics``) without a second
    round-trip. Target fields also fall back to the observation row's own
    ``title``/``channel_id`` (populated at scrape time).
    """

    source_video_id: str
    recommended_video_id: str
    position: int | None = None
    run_id: str | None = None
    run_type: str | None = None  # "channel" | "video" | "recommendation"
    run_name: str | None = None  # researcher-provided label from CollectionRun
    observed_at: Any = None
    layer_index: int | None = None  # producing crawl layer (layer-crawl feature)

    # Source (the video that made the recommendation) metadata.
    source_title: str | None = None
    source_channel_id: str | None = None
    source_channel_name: str | None = None
    source_thumbnail_url: str | None = None
    source_views: int | None = None
    source_likes: int | None = None
    source_duration: int | None = None

    # Target (the recommended video) metadata.
    title: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    thumbnail_url: str | None = None
    views: int | None = None
    likes: int | None = None
    duration: int | None = None


class DegreeDistribution(_Base):
    """Percentile summary of a directed degree distribution."""

    min: float | None = None
    max: float | None = None
    mean: float | None = None
    median: float | None = None
    p25: float | None = None
    p75: float | None = None
    p90: float | None = None
    p95: float | None = None
    p99: float | None = None


class NetworkMetrics(_Base):
    """Aggregate statistics for one recommendation-network slice."""

    run_id: str | None = None
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0
    is_directed: bool = True
    reciprocity: float = 0.0
    degree_distribution: dict[str, DegreeDistribution] = {}
    avg_clustering: float = 0.0
    global_clustering: float = 0.0
    weakly_connected_components: int = 0
    largest_component_size: int = 0
    largest_component_share: float = 0.0
    community_count: int = 0
    modularity: float | None = None
    top_hubs: list[dict[str, Any]] = []
    top_authorities: list[dict[str, Any]] = []
    most_recommended: list[dict[str, Any]] = []
    most_active_sources: list[dict[str, Any]] = []


class TemporalGrowth(_Base):
    """Delta between two consecutive requested runs."""

    from_run_id: str
    to_run_id: str
    node_growth: int = 0
    edge_growth: int = 0
    density_growth: float = 0.0


class NetworkSlice(_Base):
    """NetworkSummary-like snapshot for a single run."""

    run_id: str
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0
    reciprocity: float = 0.0
    top_ranked: list[dict[str, Any]] = []


class TemporalResult(_Base):
    """Per-run slices and consecutive-run growth."""

    slices: list[NetworkSlice] = []
    growth: list[TemporalGrowth] = []


class ChannelFacet(_Base):
    """A distinct channel observed on the network slice (id + name)."""

    channel_id: str
    channel_name: str | None = None


class ChannelProjection(_Base):
    """Lightweight channel-level projection (documented in the module doc).

    ``channels`` lists the distinct channels observed on edges (with their
    resolved names when a ``Channel`` row exists) and ``edge_count`` counts
    the edges carrying a channel attribution.
    """

    channels: list[ChannelFacet] = []
    edge_count: int = 0


class ChannelGraphNode(_Base):
    """One channel-projection node (doc ``analysis_next_layer_scrape.md`` §4.2).

    ``video_count`` counts the distinct videos of this channel in the slice;
    ``in_degree``/``out_degree`` count distinct channel neighbours; provenance
    (``run_ids``/``run_types``) mirrors ``GraphNode``.
    """

    channel_id: str
    channel_name: str | None = None
    avatar_url: str | None = None
    subscriber_count: int | None = None  # latest ChannelObservation
    video_count: int = 0
    in_degree: int = 0
    out_degree: int = 0
    run_ids: list[str] = []
    run_types: list[str] = []


class ChannelGraphEdge(_Base):
    """One channel-projection edge: weighted aggregation of video edges A->B.

    ``video_edge_count`` counts the underlying video-level edges;
    ``sample_video_pairs`` holds the first few ``{source_video_id,
    recommended_video_id, position}`` pairs as evidence.
    """

    source: str  # channel_id
    target: str  # channel_id
    video_edge_count: int = 0
    run_ids: list[str] = []
    sample_video_pairs: list[dict[str, Any]] = []


class ChannelGraphPayload(_Base):
    """Channel-projection graph payload (doc §4.2).

    ``channels`` carries the ``ChannelFacet`` list plus ``unattributed_edges``
    in a facet's metadata dict when present (edges dropped because either
    endpoint's channel could not be resolved are counted, never synthetic).
    """

    projection: str = "channel"
    nodes: list[ChannelGraphNode] = []
    edges: list[ChannelGraphEdge] = []
    channels: list[ChannelFacet] = []
    runs: list[dict[str, Any]] = []  # {run_id, run_type, name}
    node_count: int = 0
    edge_count: int = 0
    unattributed_edges: int = 0


class GraphNode(_Base):
    """One enriched network node for the interactive graph.

    ``kind`` describes the node's structural role: ``source`` (out-edges only),
    ``target`` (in-edges only), ``both`` or ``other``. ``runs``/``run_types``
    list the provenance of the edges touching this node.
    """

    video_id: str
    title: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    thumbnail_url: str | None = None
    views: int | None = None
    likes: int | None = None
    duration: int | None = None
    kind: str = "other"
    in_degree: int = 0
    out_degree: int = 0
    run_ids: list[str] = []
    run_types: list[str] = []
    community_id: int | None = None
    recommendations_scraped: bool = False


class GraphEdge(_Base):
    """One enriched graph edge (provenance + role of the recommendation)."""

    source: str
    target: str
    position: int | None = None
    run_id: str | None = None
    run_type: str | None = None
    run_name: str | None = None
    title: str | None = None
    weight: float = 1.0  # weight_spec-derived edge weight (1.0 = structural default)
    relationship_type: str = "recommendation"  # semantic edge type (recommendation | co_comment | ...)


class NetworkGraph(_Base):
    """Full graph payload: enriched nodes + edges + run/channel facets.

    Served by ``GET /network/graph`` so the UI renders readable nodes
    (``[ID] + Channel Name + Video Title + metrics``) and populates the
    run/channel filter dropdowns from real facets - never from the rendered
    graph.
    """

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    runs: list[dict[str, Any]] = []  # {run_id, run_type, name}
    channels: list[ChannelFacet] = []
    node_count: int = 0
    edge_count: int = 0
    weight_spec: dict | None = None  # echoed weight spec, when a non-default one was applied


class NetworkScope(_Base):
    """A video-network scope for export / merge operations.

    ``run_id`` pins the slice to one collection run; ``run_ids`` pins it to a
    set of runs (a network-expansion action's runs); ``video_ids`` keeps only
    the ego edges touching any of the listed videos. When every field is empty
    the scope is the whole persisted recommendation network.
    """

    run_id: str | None = None
    run_ids: list[str] = Field(default_factory=list)
    video_ids: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.run_id and not self.run_ids and not self.video_ids


class OverlapStats(_Base):
    """Shared/exclusive node & edge counts between two network scopes.

    ``jaccard_*`` is ``None`` when the union is empty (no meaningful ratio),
    never fabricated as 0. Edge identity is directed (``source->target``).
    """

    scope_a_node_count: int = 0
    scope_b_node_count: int = 0
    scope_a_edge_count: int = 0
    scope_b_edge_count: int = 0
    shared_node_count: int = 0
    shared_edge_count: int = 0
    union_node_count: int = 0
    union_edge_count: int = 0
    nodes_only_in_a: int = 0
    nodes_only_in_b: int = 0
    edges_only_in_a: int = 0
    edges_only_in_b: int = 0
    jaccard_node_overlap: float | None = None
    jaccard_edge_overlap: float | None = None


class MergedDegreeNode(_Base):
    """A top-degree node of a merged network with resolvable labels.

    Follows the module's label-hygiene rule: a bare video id is never shown
    without context, so titles/channel names are resolved from persisted
    repositories when available (``None`` only when nothing was persisted).
    """

    video_id: str
    title: str | None = None
    channel_id: str | None = None
    channel_name: str | None = None
    in_degree: int = 0
    out_degree: int = 0
    total_degree: int = 0


class MergedGraphStats(_Base):
    """Combined SNA statistics over the union of two scopes.

    Mirrors ``NetworkMetrics`` so the merged-graph report reads like any other
    network slice, plus ``top_degree_nodes`` (labeled, deterministically
    ordered by total degree then id).
    """

    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0
    is_directed: bool = True
    reciprocity: float = 0.0
    degree_distribution: dict[str, DegreeDistribution] = {}
    avg_clustering: float = 0.0
    global_clustering: float = 0.0
    weakly_connected_components: int = 0
    largest_component_size: int = 0
    largest_component_share: float = 0.0
    community_count: int = 0
    modularity: float | None = None
    top_degree_nodes: list[MergedDegreeNode] = []


class MergedNetworkResult(_Base):
    """Overlap report + merged SNA stats for two network scopes.

    ``nodes``/``edges`` carry the enriched union graph (labels resolved, same
    shape as ``NetworkGraph``) so the UI can render the merged net, while
    ``overlap`` answers "how much do these two nets share?".
    """

    scope_a: NetworkScope
    scope_b: NetworkScope
    overlap: OverlapStats
    merged: MergedGraphStats
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    node_count: int = 0
    edge_count: int = 0


class NetworkMergeOptions(_Base):
    """Picker payload for ``GET /network/merge/options``.

    Lists the run and expansion-action scopes the UI can merge. Videos are
    intentionally omitted (could be huge); the video-ego scope is entered as
    free-form ``video_ids``.
    """

    runs: list[dict[str, Any]] = []  # {run_id, run_type, name}
    expansions: list[dict[str, Any]] = []  # {action_id, kind, project_id, video_ids, run_ids, started_at}


class _MetadataIndex:
    """Batch-resolved metadata caches shared across one edge-list call.

    Built with a handful of repository scans (no per-edge N+1) using the
    column-projected ``list_video_metadata``/``latest_observation_metrics``/
    ``list_channel_titles`` reads so heavy ``raw_json`` TOAST blobs (up to
    ~200KB/row) are never fetched on the analytics hot path.
    """

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos
        self._videos = repos.videos.list_video_metadata()
        self._metrics = repos.videos.latest_observation_metrics(list(self._videos))
        self._channels = repos.channels.list_channel_titles()
        self._runs = {r.run_id: r for r in repos.runs.list_runs()}

    def video(self, video_id: str) -> dict[str, Any]:
        video = self._videos.get(video_id)
        if video is None:
            return {}
        metrics = self._metrics.get(video_id, {})
        channel_id = video.get("channel_id")
        return {
            "title": video.get("title"),
            "channel_id": channel_id,
            "channel_name": self._channels.get(channel_id) if channel_id else None,
            "thumbnail_url": video.get("thumbnail_url"),
            "views": metrics.get("view_count"),
            "likes": metrics.get("like_count"),
            "duration": video.get("duration"),
            "recommendations_scraped": video.get("recommendations_scraped", False),
        }

    def run(self, run_id: str | None) -> tuple[str | None, str | None]:
        if not run_id:
            return None, None
        run = self._runs.get(run_id)
        if run is None:
            return None, None
        return run.run_type.value if run.run_type else None, run.name


class NetworkAnalyticsService:
    """Network-wide analytics built on ``RecommendationGraphService``."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos
        self._graph_service = RecommendationGraphService(repos)

    @classmethod
    def clear_analytics_cache(cls) -> None:
        """Invalidate cached metrics/graph payloads (writers must call this)."""
        for store in _ttl_stores:
            store.clear()

    # ------------------------------------------------------------------
    @_ttl_cache(300)
    def metrics(self, run_id: str | None = None, top_n: int = 10) -> NetworkMetrics:
        """Compute aggregate network statistics for one slice.

        The graph is built from the *same* edge pipeline that drives the
        interactive graph UI (``edges`` -> ``_raw_edges``), NOT the cached raw
        ``build_graph``. This guarantees the Metrics panel (density,
        reciprocity, clustering, components, communities, HITS) always matches
        what is rendered, and avoids serving a stale cached graph after a layer
        crawl appends edges.
        """
        rows = self.edges(run_id=run_id)
        graph = nx.DiGraph()
        for row in rows:
            graph.add_edge(row.source_video_id, row.recommended_video_id)
        return self._metrics_for_graph(graph, run_id=run_id, top_n=top_n)

    def _metrics_for_graph(
        self,
        graph: nx.DiGraph,
        *,
        run_id: str | None = None,
        top_n: int = 10,
    ) -> NetworkMetrics:
        """Aggregate statistics for an already-built ``nx.DiGraph``.

        Shared by :meth:`metrics` (one run / whole network) and
        :meth:`merge_networks` (the union of two scopes) so the merged report
        reads exactly like any other network slice.
        """
        metrics = NetworkMetrics(
            run_id=run_id,
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
            is_directed=True,
        )
        if graph.number_of_edges() == 0:
            return metrics

        metrics.density = float(nx.density(graph))
        # Directed measure; ``nx.reciprocity`` is undefined on empty graphs,
        # already guarded by the edge-count check above.
        metrics.reciprocity = float(nx.reciprocity(graph))

        in_degrees = [d for _, d in graph.in_degree()]
        out_degrees = [d for _, d in graph.out_degree()]
        metrics.degree_distribution = {
            "in_degree": self._degree_distribution(in_degrees),
            "out_degree": self._degree_distribution(out_degrees),
        }

        # Clustering is undirected-only (ADR-0009): average clustering on the
        # undirected projection and transitivity for the global coefficient.
        undirected = graph.to_undirected()
        metrics.avg_clustering = float(nx.average_clustering(undirected))
        metrics.global_clustering = float(nx.transitivity(undirected))

        components = list(nx.weakly_connected_components(graph))
        metrics.weakly_connected_components = len(components)
        metrics.largest_component_size = max((len(c) for c in components), default=0)
        metrics.largest_component_share = (
            metrics.largest_component_size / metrics.node_count
        )

        communities = list(louvain_communities(graph.to_undirected(), seed=42))
        metrics.community_count = len(communities)
        metrics.modularity = (
            float(modularity(graph, communities)) if graph.number_of_edges() else None
        )

        hubs, authorities = nx.hits(graph)
        metrics.top_hubs = self._top_scores(hubs, top_n)
        metrics.top_authorities = self._top_scores(authorities, top_n)

        metrics.most_recommended = self._top_counts(
            dict(graph.in_degree()), top_n, "times_recommended"
        )
        metrics.most_active_sources = self._top_counts(
            dict(graph.out_degree()), top_n, "outgoing"
        )
        return metrics

    # ------------------------------------------------------------------
    def temporal(self, run_ids: list[str]) -> TemporalResult:
        """Per-run slices plus growth between consecutive requested runs."""
        slices: list[NetworkSlice] = []
        for run_id in run_ids:
            slices.append(self._slice(run_id))

        growth: list[TemporalGrowth] = []
        for left, right in zip(slices, slices[1:]):
            density_growth = (
                round(right.density - left.density, 6)
                if (left.node_count or right.node_count)
                else 0.0
            )
            growth.append(
                TemporalGrowth(
                    from_run_id=left.run_id,
                    to_run_id=right.run_id,
                    node_growth=right.node_count - left.node_count,
                    edge_growth=right.edge_count - left.edge_count,
                    density_growth=density_growth,
                )
            )
        return TemporalResult(slices=slices, growth=growth)

    # ------------------------------------------------------------------
    def _raw_edges(
        self,
        *,
        run_id: str | None = None,
        run_ids: list[str] | None = None,
        video_ids: list[str] | None = None,
        channel_id: str | None = None,
        channel_ids: list[str] | None = None,
        channel_scope: ChannelScope = "source",
        layer_index: int | None = None,
    ) -> list[Any]:
        """Raw recommendation edges matching the given scope filters.

        ``video_ids`` keeps only the ego edges touching any listed video
        (``source`` or ``target`` in the set); ``run_ids`` limits to a set of
        runs; the channel filters mirror :meth:`edges`. ``channel_id`` is the
        legacy single-channel filter; ``channel_ids`` is the multi-channel
        equivalent (an edge matches if its scoped endpoint channel is in the
        set). Used by the enriched ``edges()``/``graph()`` paths and the
        export/merge machinery so every view of a slice agrees on the same
        edge set.
        """
        video_set = set(video_ids or [])
        channel_set = set(channel_ids) if channel_ids else None
        if channel_id:
            channel_set = {channel_id}
        metadata = _MetadataIndex(self._repos) if channel_set else None
        edges: list[Any] = []
        for edge in self._repos.recommendations.list_recommendation_edges(
            run_id=run_id if run_id else None,
            run_ids=run_ids if not run_id and run_ids else None,
        ):
            if layer_index is not None and edge.layer_index != layer_index:
                continue
            if run_ids is not None and edge.collection_run_id not in run_ids:
                continue
            if video_set and (
                edge.source_video_id not in video_set
                and edge.recommended_video_id not in video_set
            ):
                continue
            if channel_set:
                source_meta = metadata.video(edge.source_video_id)
                target_meta = metadata.video(edge.recommended_video_id)
                source_channel = source_meta.get("channel_id")
                target_channel = target_meta.get("channel_id") or edge.channel_id
                if channel_scope == "target":
                    if target_channel not in channel_set:
                        continue
                elif channel_scope == "either":
                    if (
                        source_channel not in channel_set
                        and target_channel not in channel_set
                    ):
                        continue
                else:  # default "source"
                    if source_channel not in channel_set:
                        continue
            edges.append(edge)
        return edges

    # ------------------------------------------------------------------
    def run_family(self, run_id: str) -> list[str]:
        """Return ``run_id`` plus the run_ids of every descendant sub-run.

        A sub-run is any ``CollectionRun`` whose ``parent_run_id`` links back
        to ``run_id`` directly or transitively. Drives the interactive graph's
        "include sub-runs" toggle so a main run can be visualised together with
        the entire lineage it spawned, distinct from the graph of a single
        sub-run.
        """
        if not run_id:
            return []
        family: list[str] = [run_id]
        seen: set[str] = {run_id}
        queue = [run_id]
        while queue:
            current = queue.pop()
            for child in self._repos.runs.list_sub_runs(current):
                if child.run_id not in seen:
                    seen.add(child.run_id)
                    family.append(child.run_id)
                    queue.append(child.run_id)
        return family

    # ------------------------------------------------------------------
    def edges(
        self,
        run_id: str | None = None,
        channel_id: str | None = None,
        channel_scope: ChannelScope = "source",
        layer_index: int | None = None,
        run_ids: list[str] | None = None,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
    ) -> list[EdgeRow]:
        """Serialize all observed edges for a slice (export/listing).

        Rows are ordered by feed rank: grouped by source video, then by the
        ``position`` the recommendation occupied in that source's rail (so the
        edge listing and exports reflect the observed feed order).

        Supports filtering by ``run_id`` and ``channel_id``. ``channel_id``
        matches the **source** channel by default (show channel X's videos and
        their 1->N recommendation trees); pass ``channel_scope="target"`` or
        ``"either"`` for the other endpoint semantics. ``layer_index`` limits
        the slice to edges produced by a specific crawl layer (``None`` = all);
        ``run_ids`` limits the slice to a set of runs (network expansions);
        ``video_ids`` keeps the ego edges touching any of the listed videos.
        """
        metadata = _MetadataIndex(self._repos)
        rows: list[EdgeRow] = []
        for edge in self._raw_edges(
            run_id=run_id,
            run_ids=run_ids,
            video_ids=video_ids,
            channel_id=channel_id,
            channel_ids=channel_ids,
            channel_scope=channel_scope,
            layer_index=layer_index,
        ):
            source_meta = metadata.video(edge.source_video_id)
            target_meta = metadata.video(edge.recommended_video_id)
            run_type, run_name = metadata.run(edge.collection_run_id)

            rows.append(
                EdgeRow(
                    source_video_id=edge.source_video_id,
                    recommended_video_id=edge.recommended_video_id,
                    position=edge.position,
                    run_id=edge.collection_run_id,
                    run_type=run_type,
                    run_name=run_name,
                    observed_at=edge.observed_at,
                    layer_index=edge.layer_index,
                    source_title=source_meta.get("title"),
                    source_channel_id=source_meta.get("channel_id"),
                    source_channel_name=source_meta.get("channel_name"),
                    source_thumbnail_url=source_meta.get("thumbnail_url"),
                    source_views=source_meta.get("views"),
                    source_likes=source_meta.get("likes"),
                    source_duration=source_meta.get("duration"),
                    title=edge.title or target_meta.get("title"),
                    channel_id=edge.channel_id or target_meta.get("channel_id"),
                    channel_name=edge.channel_name or target_meta.get("channel_name"),
                    thumbnail_url=target_meta.get("thumbnail_url"),
                    views=target_meta.get("views"),
                    likes=target_meta.get("likes"),
                    duration=target_meta.get("duration"),
                )
            )
        return sorted(
            rows,
            key=lambda row: (
                row.source_video_id,
                row.position is None,
                row.position if row.position is not None else 0,
                row.run_id or "",
                row.recommended_video_id,
            ),
        )

    # ------------------------------------------------------------------
    def _earliest_layer_by_pair(self) -> dict[tuple[str, str], int]:
        """Map ``(source, target)`` to the earliest ``layer_index`` observed.

        Used by the layer-scoped graph to attribute each recommendation edge to
        the layer that first discovered it, so a later layer merely re-observing
        an already-known edge does not render a duplicate of the previous
        layer's graph. Observations remain in the data for temporal analysis;
        this only de-duplicates what the layer graph displays.
        """
        min_layer: dict[tuple[str, str], int] = {}
        for edge in self._repos.recommendations.list_recommendation_edges():
            li = getattr(edge, "layer_index", None)
            if li is None:
                continue
            key = (edge.source_video_id, edge.recommended_video_id)
            if key not in min_layer or li < min_layer[key]:
                min_layer[key] = li
        return min_layer

    @_ttl_cache(300)
    def graph(
        self,
        run_id: str | None = None,
        channel_id: str | None = None,
        channel_scope: ChannelScope = "source",
        layer_index: int | None = None,
        run_ids: list[str] | None = None,
        video_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        connected: str | None = None,
        scraped: str | None = None,
        weight_spec: str | None = None,
    ) -> NetworkGraph:
        """Enriched node/edge payload driving the interactive graph UI.

        Nodes carry composite-label metadata (``[ID] + Channel Name + Video
        Title + thumbnails/metrics``) plus structural info (degree, kind) and
        provenance (run_ids/run_types). Facets (runs, channels) let the filter
        bar populate from real data without a second request. ``layer_index``
        limits the slice to one crawl layer (``None`` = all); ``run_ids``
        limits the slice to a set of runs (network expansions); ``video_ids``
        keeps the ego edges touching any of the listed videos. ``connected``
        keeps only connected (``"only"``) or only isolated (``"isolated"``)
        nodes; ``scraped`` keeps only scraped (``"scraped"``) or only
        never-scraped (``"unscraped"``) nodes.
        """
        rows = self.edges(
            run_id=run_id,
            channel_id=channel_id,
            channel_ids=channel_ids,
            channel_scope=channel_scope,
            layer_index=layer_index,
            run_ids=run_ids,
            video_ids=video_ids,
        )

        # Layer-scoped view: attribute each (source, target) pair to the EARLIEST
        # layer that observed it, so a later layer that merely re-observes an
        # already-known recommendation edge does not render a duplicate of the
        # previous layer's graph. Observations are retained in the data (for
        # temporal analysis); this is purely a de-duplication of what the layer
        # graph displays.
        if layer_index is not None:
            _min_layer = self._earliest_layer_by_pair()
            rows = [
                r
                for r in rows
                if _min_layer.get((r.source_video_id, r.recommended_video_id))
                == layer_index
            ]

        in_degree: dict[str, int] = {}
        out_degree: dict[str, int] = {}
        run_ids_by_node: dict[str, set[str]] = {}
        run_types_by_node: dict[str, set[str]] = {}

        edges: list[GraphEdge] = []
        for row in rows:
            edges.append(
                GraphEdge(
                    source=row.source_video_id,
                    target=row.recommended_video_id,
                    position=row.position,
                    run_id=row.run_id,
                    run_type=row.run_type,
                    run_name=row.run_name,
                    title=row.title,
                )
            )
            out_degree[row.source_video_id] = out_degree.get(row.source_video_id, 0) + 1
            in_degree[row.recommended_video_id] = (
                in_degree.get(row.recommended_video_id, 0) + 1
            )
            for video_id, edge_run_id, edge_run_type in (
                (row.source_video_id, row.run_id, row.run_type),
                (row.recommended_video_id, row.run_id, row.run_type),
            ):
                if edge_run_id:
                    run_ids_by_node.setdefault(video_id, set()).add(edge_run_id)
                if edge_run_type:
                    run_types_by_node.setdefault(video_id, set()).add(edge_run_type)

        # Apply the optional weight spec (N1): each observation edge gets a raw
        # weight from its mode, then the whole slice is normalized so weights are
        # comparable. Default (no spec) leaves every edge at 1.0, preserving
        # today's structural behaviour exactly.
        ws = parse_weight_spec(weight_spec) if weight_spec else None
        if ws is not None:
            raw = [
                edge_weight_for_mode(ws.weight_mode, getattr(e, "position", None))
                for e in edges
            ]
            norm = normalize_weights(raw, ws.normalization)
            for e, w in zip(edges, norm):
                e.weight = w
        weight_echo = ws.to_dict() if ws is not None else None

        # Node metadata: sources first (they may also be targets), then any
        # targets that are not already present. Metadata comes from the
        # repository-backed resolver - never fabricated. Targets that were
        # never persisted still carry whatever the provider observed on the
        # edge row itself (channel id/name, title).
        connected_ids = list(dict.fromkeys(
            [row.source_video_id for row in rows]
            + [row.recommended_video_id for row in rows]
        ))
        connected_set = set(connected_ids)

        # Isolated (non-connected) nodes: videos persisted in the corpus with
        # no edge in the slice. They render detached. Included when the caller
        # explicitly asks for the isolated view, OR - for a *run-scoped* slice
        # with no edges yet (e.g. a seed Layer 0 that hasn't scraped
        # recommendations) - the run's own videos, so the graph isn't empty
        # even before the first crawl. A non-run slice with no edges stays
        # empty (there is genuinely nothing to show).
        isolated_ids: list[str] = []
        if connected == "isolated":
            corpus = set(self._repos.videos.list_video_metadata())
            isolated_ids = sorted(corpus - connected_set)
        elif not rows and run_id:
            run_videos = self._repos.videos.list_videos_by_run(run_id)
            isolated_ids = sorted({v.video_id for v in run_videos} - connected_set)
        video_ids = (
            isolated_ids
            if (connected == "isolated" or (not rows and run_id))
            else connected_ids
        )

        edge_meta: dict[str, dict[str, Any]] = {}
        for row in rows:
            edge_meta.setdefault(
                row.recommended_video_id,
                {"channel_id": row.channel_id, "channel_name": row.channel_name,
                 "title": row.title},
            )
        metadata = _MetadataIndex(self._repos)

        # Community detection over the undirected projection of *this slice's
        # displayed edges* (not the raw cached build_graph), so community_id is
        # consistent with the nodes/edges actually rendered and exported.
        comm_graph = nx.DiGraph()
        for e in edges:
            comm_graph.add_edge(e.source, e.target)
        if comm_graph.number_of_edges() > 0:
            undirected = comm_graph.to_undirected()
            communities = sorted(
                louvain_communities(undirected, seed=42),
                key=len,
                reverse=True,
            )
            node_community = {
                video_id: idx
                for idx, community in enumerate(communities)
                for video_id in community
            }
        else:
            node_community = {}

        nodes: list[GraphNode] = []
        for video_id in video_ids:
            info = metadata.video(video_id)
            fallback = edge_meta.get(video_id, {})
            n_in = in_degree.get(video_id, 0)
            n_out = out_degree.get(video_id, 0)
            kind = "other"
            if n_out > 0 and n_in > 0:
                kind = "both"
            elif n_out > 0:
                kind = "source"
            elif n_in > 0:
                kind = "target"
            nodes.append(
                GraphNode(
                    video_id=video_id,
                    title=info.get("title") or fallback.get("title"),
                    channel_id=info.get("channel_id") or fallback.get("channel_id"),
                    channel_name=info.get("channel_name") or fallback.get("channel_name"),
                    thumbnail_url=info.get("thumbnail_url"),
                    views=info.get("views"),
                    likes=info.get("likes"),
                    duration=info.get("duration"),
                    kind=kind,
                    in_degree=n_in,
                    out_degree=n_out,
                    run_ids=sorted(run_ids_by_node.get(video_id, set())),
                    run_types=sorted(run_types_by_node.get(video_id, set())),
                    community_id=node_community.get(video_id),
                    recommendations_scraped=bool(info.get("recommendations_scraped")),
                )
            )

        # Selection filter on scrape state: 'scraped' keeps only nodes whose
        # recommendation feed has been scraped; 'unscraped' keeps the rest
        # (the candidates for a next expansion).
        if scraped == "scraped":
            nodes = [n for n in nodes if n.recommendations_scraped]
        elif scraped == "unscraped":
            nodes = [n for n in nodes if not n.recommendations_scraped]

        channel_rows = self._repos.channels.list_channel_titles()
        channel_ids = sorted({n.channel_id for n in nodes if n.channel_id})
        channels = [
            ChannelFacet(
                channel_id=cid,
                channel_name=channel_rows.get(cid),
            )
            for cid in channel_ids
        ]

        runs_by_id = {r.run_id: r for r in self._repos.runs.list_runs()}
        runs = [
            {
                "run_id": r.run_id,
                "run_type": r.run_type.value if r.run_type else None,
                "name": r.name,
            }
            for r in runs_by_id.values()
            if run_id is None or r.run_id == run_id
        ]

        return NetworkGraph(
            nodes=nodes,
            edges=edges,
            runs=runs,
            channels=channels,
            node_count=len(nodes),
            edge_count=len(edges),
            weight_spec=weight_echo,
        )

    # ------------------------------------------------------------------
    def centralities(
        self,
        *,
        run_id: str | None = None,
        channel_id: str | None = None,
        channel_ids: list[str] | None = None,
        channel_scope: str = "source",
        layer_index: int | None = None,
        video_ids: list[str] | None = None,
        projection: str = "video",
        weight_spec: str | None = None,
        weighted: bool = False,
    ) -> dict[str, dict[str, float]]:
        """Per-node centrality vector for the visible graph (benchmarkable).

        Returns ``{node_id: {"degree", "closeness", "eigenvector",
        "betweenness", "community_id"}}`` for the same subgraph that
        ``/network/graph`` would render. Centralities use networkx over the
        directed slice; ``community_id`` is copied from the graph view so the
        output doubles as a labelled benchmark fixture (e.g. Zachary's karate
        club). Empty slices return ``{}``.

        When ``weighted`` is true and a ``weight_spec`` is supplied, edge
        ``weight`` attributes (from the same spec the graph renders) drive
        eigenvector/betweenness and a weighted degree centrality - so the
        weight change propagates consistently into the centrality battery.
        """
        if projection == "channel":
            payload = self.channel_graph(
                run_id=run_id,
                layer_index=layer_index,
                channel_id=channel_id,
                channel_ids=channel_ids,
                channel_scope=channel_scope,
            )
        else:
            payload = self.graph(
                run_id=run_id,
                channel_id=channel_id,
                channel_ids=channel_ids,
                channel_scope=channel_scope,
                layer_index=layer_index,
                video_ids=video_ids,
                weight_spec=weight_spec,
            )
        use_weight = bool(weighted and weight_spec)
        G = nx.DiGraph()
        for e in payload.edges:
            w = getattr(e, "weight", None)
            if use_weight and w is not None:
                G.add_edge(e.source, e.target, weight=w)
            else:
                G.add_edge(e.source, e.target)
        if G.number_of_nodes() == 0:
            return {}
        battery = centrality_battery(G, weighted=use_weight)
        result: dict[str, dict[str, float]] = {}
        for node in payload.nodes:
            nid = node.channel_id if projection == "channel" else node.video_id
            vals = battery.get(nid, {})
            result[nid] = {
                "degree": vals.get("degree", 0.0),
                "closeness": vals.get("closeness", 0.0),
                "eigenvector": vals.get("eigenvector", 0.0),
                "betweenness": vals.get("betweenness", 0.0),
                "community_id": float(node.community_id if node.community_id is not None else -1),
            }
        return result

    # ------------------------------------------------------------------
    def export_edges(
        self, run_id: str | None = None, format: str = "graphml"
    ) -> tuple[str, str, str]:
        """Serialize the network into a file-format string (backwards compat).

        Thin wrapper over :meth:`export_network` keeping the historical
        single-``run_id`` signature; new scopes (run sets, video egos) and the
        ``csv``/``json`` formats are available there.
        """
        return self.export_network(format, run_id=run_id)

    def export_network(
        self,
        format: str = "graphml",
        *,
        run_id: str | None = None,
        run_ids: list[str] | None = None,
        video_ids: list[str] | None = None,
        channel_id: str | None = None,
        channel_ids: list[str] | None = None,
        channel_scope: str = "source",
        layer_index: int | None = None,
        connected: str | None = None,
        scraped: str | None = None,
        projection: str = "video",
        weight_spec: str | None = None,
    ) -> tuple[str, str | bytes, str]:
        """Serialize the *visible* scoped network into a file-format payload.

        The export mirrors exactly what ``/network/graph`` (or ``/network/
        graph?projection=channel``) would render for the same filters, so the
        downloaded file always matches the Active Filter View: the same nodes
        (with ``connected``/``scraped`` pruning), the same edges (with the
        layer de-duplication that attributes each pair to the layer that first
        discovered it), and the same channel/run scoping. No out-of-view or
        orphaned nodes leak in.

        Returns ``(suggested_filename, content, media_type)``. Supported
        formats:

        * ``graphml`` / ``edgelist`` / ``gexf`` - networkx serializations with
          node attributes ``id``, ``label``, ``degree``, ``community_id`` and
          ``centrality``;
        * ``json`` - Cytoscape/D3 ``{"nodes": [...], "links": [...]}``;
        * ``csv`` - edge list ``source,target,weight,relationship_type``;
        * ``xlsx`` - labeled edge table (readable titles/channels).

        Text formats return ``str``; ``xlsx`` returns ``bytes``. Raises
        ``ValueError`` for an unsupported ``format`` or ``projection``.
        """
        if projection not in ("video", "channel"):
            raise ValueError(
                f"Unsupported projection '{projection}' (expected video or channel)"
            )

        # Build the exact subgraph the UI would render for these filters.
        if projection == "channel":
            payload = self.channel_graph(
                run_id=run_id,
                layer_index=layer_index,
                run_ids=run_ids,
                channel_id=channel_id,
                channel_ids=channel_ids,
                channel_scope=channel_scope,
            )
            return self._serialize_channel_graph(payload, format)
        payload = self.graph(
            run_id=run_id,
            channel_id=channel_id,
            channel_ids=channel_ids,
            channel_scope=channel_scope,
            layer_index=layer_index,
            run_ids=run_ids,
            video_ids=video_ids,
            connected=connected,
            scraped=scraped,
            weight_spec=weight_spec,
        )
        weight_echo = (
            parse_weight_spec(weight_spec).to_dict() if weight_spec else None
        )
        return self._serialize_video_graph(payload, format, weight_echo)

    # -- export serializers -------------------------------------------------
    def _aggregated_edges(self, edges):
        """Collapse observation rows into weighted, de-duplicated edges.

        Returns a dict keyed by ``(source, target)`` -> ``{"weight", "run_ids",
        "positions", "title", "run_id"}``. Collapsing guarantees the exported
        edge set is exactly the visible edge set (no parallel edges from
        repeated observations) and provides the ``weight`` the formats need.

        ``weight`` sums each edge's ``weight`` attribute, which ``graph()`` has
        already resolved from the active weight spec (default 1.0 per
        observation -> identical to the old observation count for the default
        spec, so exports stay byte-for-byte stable).
        """
        agg: dict[tuple[str, str], dict[str, Any]] = {}
        for e in edges:
            key = (e.source, e.target)
            rec = agg.get(key)
            if rec is None:
                rec = {
                    "weight": 0,
                    "run_ids": [],
                    "positions": [],
                    "title": getattr(e, "title", None),
                    "run_id": getattr(e, "run_id", None),
                    "relationship_type": getattr(e, "relationship_type", "recommendation"),
                }
                agg[key] = rec
            rec["weight"] += getattr(e, "weight", 1.0)
            # Whole-number weights (the default observation count) stay int so
            # the default export is byte-for-byte identical to the pre-weight
            # payloads; fractional weights (a real spec) stay float.
            if float(rec["weight"]).is_integer():
                rec["weight"] = int(rec["weight"])
            rid = getattr(e, "run_id", None)
            if rid and rid not in rec["run_ids"]:
                rec["run_ids"].append(rid)
            pos = getattr(e, "position", None)
            if pos is not None:
                rec["positions"].append(pos)
        return agg

    def _serialize_video_graph(
        self, payload: "NetworkGraph", format: str, weight_spec: dict | None = None
    ):
        fmt = (format or "").strip().lower()
        nodes = {n.video_id: n for n in payload.nodes}
        agg = self._aggregated_edges(payload.edges)

        # Graph for centrality + networkx writers.
        G = nx.DiGraph()
        for (s, t) in agg:
            G.add_edge(s, t)
        centrality = nx.degree_centrality(G) if G.number_of_nodes() else {}

        def _node_attrs(n):
            degree = (n.in_degree or 0) + (n.out_degree or 0)
            return {
                "id": n.video_id,
                "label": n.title or n.video_id,
                "kind": n.kind,
                "degree": degree,
                "in_degree": n.in_degree or 0,
                "out_degree": n.out_degree or 0,
                "community_id": n.community_id if n.community_id is not None else -1,
                "centrality": round(centrality.get(n.video_id, 0.0), 6),
                "channel_id": n.channel_id or "",
                "scraped": bool(n.recommendations_scraped),
            }

        graph_formats = {
            "graphml": ("recommendations.graphml", "application/xml"),
            "edgelist": ("recommendations.edgelist", "text/plain"),
            "gexf": ("recommendations.gexf", "application/gexf+xml"),
        }
        if fmt in graph_formats:
            filename, media_type = graph_formats[fmt]
            export = nx.DiGraph()
            for vid, n in nodes.items():
                attrs = _node_attrs(n)
                export.add_node(vid, **{k: ("" if v is None else v) for k, v in attrs.items()})
            for (s, t), rec in agg.items():
                export.add_edge(
                    s,
                    t,
                    relationship_type=rec["relationship_type"],
                    weight=rec["weight"],
                    position=rec["positions"][0] if rec["positions"] else -1,
                    run_id=";".join(rec["run_ids"]),
                )
            if weight_spec is not None:
                export.graph["weight_spec"] = json.dumps(
                    weight_spec, ensure_ascii=False, default=str
                )
            buffer = io.BytesIO()
            if fmt == "graphml":
                nx.write_graphml(export, buffer)
            elif fmt == "edgelist":
                nx.write_edgelist(export, buffer)
            else:
                nx.write_gexf(export, buffer)
            return filename, buffer.getvalue().decode("utf-8"), media_type

        if fmt == "json":
            out: dict[str, Any] = {
                "nodes": [
                    {"data": _node_attrs(n)} for n in payload.nodes
                ],
                "links": [
                    {
                        "data": {
                            "id": f"{s}->{t}",
                            "source": s,
                            "target": t,
                            "weight": rec["weight"],
                            "relationship_type": rec["relationship_type"],
                            "position": (rec["positions"][0] if rec["positions"] else None),
                            "run_ids": rec["run_ids"],
                        }
                    }
                    for (s, t), rec in agg.items()
                ],
            }
            if weight_spec is not None:
                out["weight_spec"] = weight_spec
            return (
                "recommendations.json",
                json.dumps(out, ensure_ascii=False, default=str),
                "application/json",
            )

        if fmt == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer, dialect="excel")
            if weight_spec is not None:
                writer.writerow(
                    [
                        "source",
                        "target",
                        "weight",
                        "relationship_type",
                        "weight_definition",
                    ]
                )
                definition = (
                    weight_spec.get("edge_type", "")
                    + ":"
                    + weight_spec.get("weight_mode", "")
                )
                for (s, t), rec in agg.items():
                    writer.writerow(
                        [s, t, rec["weight"], rec["relationship_type"], definition]
                    )
            else:
                writer.writerow(
                    ["source", "target", "weight", "relationship_type"]
                )
                for (s, t), rec in agg.items():
                    writer.writerow([s, t, rec["weight"], rec["relationship_type"]])
            return "recommendations.csv", buffer.getvalue(), "text/csv"

        if fmt == "xlsx":
            from openpyxl import Workbook
            from openpyxl.styles import Font

            columns = [
                "source_video_id",
                "recommended_video_id",
                "weight",
                "relationship_type",
                "source_title",
                "target_title",
                "source_channel_id",
                "source_channel_name",
                "target_channel_id",
                "target_channel_name",
                "positions",
                "run_ids",
            ]
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Recommendations"
            sheet.append(columns)
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            meta = {
                n.video_id: n
                for n in payload.nodes
            }
            for (s, t), rec in agg.items():
                sn = meta.get(s)
                tn = meta.get(t)
                sheet.append(
                    [
                        s,
                        t,
                        rec["weight"],
                        rec["relationship_type"],
                        sn.title if sn else None,
                        tn.title if tn else None,
                        sn.channel_id if sn else None,
                        sn.channel_name if sn else None,
                        tn.channel_id if tn else None,
                        tn.channel_name if tn else None,
                        ",".join(str(p) for p in rec["positions"]),
                        ";".join(rec["run_ids"]),
                    ]
                )
            buffer = io.BytesIO()
            workbook.save(buffer)
            return "recommendations.xlsx", buffer.getvalue(), (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        valid = sorted(set(graph_formats) | {"csv", "json", "xlsx"})
        raise ValueError(
            f"Unsupported export format '{fmt}' (expected one of: "
            f"{', '.join(valid)})"
        )

    def _serialize_channel_graph(self, payload: "ChannelGraphPayload", format: str):
        fmt = (format or "").strip().lower()
        nodes = {n.channel_id: n for n in payload.nodes}
        G = nx.DiGraph()
        for e in payload.edges:
            G.add_edge(e.source, e.target)
        centrality = nx.degree_centrality(G) if G.number_of_nodes() else {}

        def _node_attrs(n):
            degree = (n.in_degree or 0) + (n.out_degree or 0)
            return {
                "id": n.channel_id,
                "label": n.channel_name or n.channel_id,
                "degree": degree,
                "in_degree": n.in_degree or 0,
                "out_degree": n.out_degree or 0,
                "centrality": round(centrality.get(n.channel_id, 0.0), 6),
            }

        graph_formats = {
            "graphml": ("channels.graphml", "application/xml"),
            "edgelist": ("channels.edgelist", "text/plain"),
            "gexf": ("channels.gexf", "application/gexf+xml"),
        }
        if fmt in graph_formats:
            filename, media_type = graph_formats[fmt]
            export = nx.DiGraph()
            for cid, n in nodes.items():
                attrs = _node_attrs(n)
                export.add_node(cid, **{k: ("" if v is None else v) for k, v in attrs.items()})
            for e in payload.edges:
                export.add_edge(
                    e.source,
                    e.target,
                    relationship_type="co-occurrence",
                    weight=e.video_edge_count,
                )
            buffer = io.BytesIO()
            if fmt == "graphml":
                nx.write_graphml(export, buffer)
            elif fmt == "edgelist":
                nx.write_edgelist(export, buffer)
            else:
                nx.write_gexf(export, buffer)
            return filename, buffer.getvalue().decode("utf-8"), media_type

        if fmt == "json":
            out = {
                "nodes": [{"data": _node_attrs(n)} for n in payload.nodes],
                "links": [
                    {
                        "data": {
                            "id": f"{e.source}->{e.target}",
                            "source": e.source,
                            "target": e.target,
                            "weight": e.video_edge_count,
                            "relationship_type": "co-occurrence",
                        }
                    }
                    for e in payload.edges
                ],
            }
            return (
                "channels.json",
                json.dumps(out, ensure_ascii=False, default=str),
                "application/json",
            )

        if fmt == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer, dialect="excel")
            writer.writerow(
                ["source", "target", "weight", "relationship_type"]
            )
            for e in payload.edges:
                writer.writerow([e.source, e.target, e.video_edge_count, "co-occurrence"])
            return "channels.csv", buffer.getvalue(), "text/csv"

        valid = sorted(set(graph_formats) | {"csv", "json"})
        raise ValueError(
            f"Unsupported export format '{fmt}' for channel projection "
            f"(expected one of: {', '.join(valid)})"
        )
    # ------------------------------------------------------------------
    def merge_networks(
        self,
        scope_a: NetworkScope,
        scope_b: NetworkScope,
        *,
        top_n: int = 10,
    ) -> MergedNetworkResult:
        """Merge two scoped networks: overlap report + combined SNA stats.

        The union graph is built over the directed edges of both scopes
        (edge attrs are copied, never shared), overlap is measured on node
        sets and directed ``(source, target)`` edge sets, and the merged
        statistics come from the same ``_metrics_for_graph`` path as
        :meth:`metrics`. Enriched nodes/edges (labels resolved) are included
        so the UI can render the merged net.
        """
        edges_a = self._raw_edges(
            run_id=scope_a.run_id, run_ids=scope_a.run_ids or None, video_ids=scope_a.video_ids or None
        )
        edges_b = self._raw_edges(
            run_id=scope_b.run_id, run_ids=scope_b.run_ids or None, video_ids=scope_b.video_ids or None
        )
        graph_a = self._graph_from_edges(edges_a)
        graph_b = self._graph_from_edges(edges_b)

        nodes_a, nodes_b = set(graph_a.nodes), set(graph_b.nodes)
        edges_a_set, edges_b_set = set(graph_a.edges()), set(graph_b.edges())
        shared_nodes = nodes_a & nodes_b
        shared_edges = edges_a_set & edges_b_set
        union_nodes = nodes_a | nodes_b
        union_edges = edges_a_set | edges_b_set

        overlap = OverlapStats(
            scope_a_node_count=len(nodes_a),
            scope_b_node_count=len(nodes_b),
            scope_a_edge_count=len(edges_a_set),
            scope_b_edge_count=len(edges_b_set),
            shared_node_count=len(shared_nodes),
            shared_edge_count=len(shared_edges),
            union_node_count=len(union_nodes),
            union_edge_count=len(union_edges),
            nodes_only_in_a=len(nodes_a - nodes_b),
            nodes_only_in_b=len(nodes_b - nodes_a),
            edges_only_in_a=len(edges_a_set - edges_b_set),
            edges_only_in_b=len(edges_b_set - edges_a_set),
            jaccard_node_overlap=_jaccard(len(shared_nodes), len(union_nodes)),
            jaccard_edge_overlap=_jaccard(len(shared_edges), len(union_edges)),
        )

        union = nx.DiGraph()
        for source, target, data in graph_a.edges(data=True):
            union.add_edge(source, target, **dict(data))
        for source, target, data in graph_b.edges(data=True):
            union.add_edge(source, target, **dict(data))

        merged = self._metrics_for_graph(union, top_n=top_n)
        merged_stats = MergedGraphStats(
            node_count=merged.node_count,
            edge_count=merged.edge_count,
            density=merged.density,
            is_directed=True,
            reciprocity=merged.reciprocity,
            degree_distribution=merged.degree_distribution,
            avg_clustering=merged.avg_clustering,
            global_clustering=merged.global_clustering,
            weakly_connected_components=merged.weakly_connected_components,
            largest_component_size=merged.largest_component_size,
            largest_component_share=merged.largest_component_share,
            community_count=merged.community_count,
            modularity=merged.modularity,
            top_degree_nodes=self._top_degree_nodes(union, top_n),
        )

        graph_payload = self._graph_payload_from_rows(
            _dedupe_edge_rows(
                self.edges(run_id=scope_a.run_id, run_ids=scope_a.run_ids or None, video_ids=scope_a.video_ids or None)
                + self.edges(run_id=scope_b.run_id, run_ids=scope_b.run_ids or None, video_ids=scope_b.video_ids or None)
            ),
            union=union,
        )
        return MergedNetworkResult(
            scope_a=scope_a,
            scope_b=scope_b,
            overlap=overlap,
            merged=merged_stats,
            nodes=graph_payload[0],
            edges=graph_payload[1],
            node_count=len(graph_payload[0]),
            edge_count=len(graph_payload[1]),
        )

    # ------------------------------------------------------------------
    def merge_options(self) -> NetworkMergeOptions:
        """Runs + expansion actions the UI can pick as merge scopes."""
        runs = [
            {
                "run_id": r.run_id,
                "run_type": r.run_type.value if r.run_type else None,
                "name": r.name,
            }
            for r in self._repos.runs.list_runs()
        ]
        expansions = []
        for layer in self._repos.layers.list_layer_runs():
            if layer.config_json.get("expansion") is None:
                continue
            expansion = layer.config_json["expansion"]
            expansions.append(
                {
                    "action_id": layer.layer_run_id,
                    "kind": expansion.get("kind", "all"),
                    "project_id": expansion.get("project_id"),
                    "video_ids": list(layer.frontier_video_ids),
                    "run_ids": list(layer.run_ids),
                    "started_at": layer.started_at.isoformat(),
                }
            )
        expansions.sort(key=lambda e: e["started_at"], reverse=True)
        return NetworkMergeOptions(runs=runs, expansions=expansions)

    # ------------------------------------------------------------------
    def _top_degree_nodes(
        self, graph: nx.DiGraph, top_n: int
    ) -> list[MergedDegreeNode]:
        """Top-``n`` nodes by total (in+out) degree, labels resolved."""
        metadata = _MetadataIndex(self._repos)
        ranked = sorted(
            graph.nodes(),
            key=lambda node: (
                -(graph.in_degree(node) + graph.out_degree(node)),
                node,
            ),
        )
        rows: list[MergedDegreeNode] = []
        for node in ranked[:top_n]:
            info = metadata.video(node)
            rows.append(
                MergedDegreeNode(
                    video_id=node,
                    title=info.get("title"),
                    channel_id=info.get("channel_id"),
                    channel_name=info.get("channel_name"),
                    in_degree=graph.in_degree(node),
                    out_degree=graph.out_degree(node),
                    total_degree=graph.in_degree(node) + graph.out_degree(node),
                )
            )
        return rows

    # ------------------------------------------------------------------
    def _graph_payload_from_rows(
        self, rows: list[EdgeRow], union: nx.DiGraph
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Enriched nodes/edges for the merged graph (labels resolved).

        Mirrors the node building of :meth:`graph` (degree/kind/provenance/
        community) over the caller-supplied ``union`` graph so community ids
        reflect the merged network, not either scope alone.
        """
        in_degree: dict[str, int] = {}
        out_degree: dict[str, int] = {}
        run_ids_by_node: dict[str, set[str]] = {}
        run_types_by_node: dict[str, set[str]] = {}

        edges: list[GraphEdge] = []
        for row in rows:
            edges.append(
                GraphEdge(
                    source=row.source_video_id,
                    target=row.recommended_video_id,
                    position=row.position,
                    run_id=row.run_id,
                    run_type=row.run_type,
                    run_name=row.run_name,
                    title=row.title,
                )
            )
            out_degree[row.source_video_id] = out_degree.get(row.source_video_id, 0) + 1
            in_degree[row.recommended_video_id] = (
                in_degree.get(row.recommended_video_id, 0) + 1
            )
            for video_id, edge_run_id, edge_run_type in (
                (row.source_video_id, row.run_id, row.run_type),
                (row.recommended_video_id, row.run_id, row.run_type),
            ):
                if edge_run_id:
                    run_ids_by_node.setdefault(video_id, set()).add(edge_run_id)
                if edge_run_type:
                    run_types_by_node.setdefault(video_id, set()).add(edge_run_type)

        video_ids = list(
            dict.fromkeys(
                [row.source_video_id for row in rows]
                + [row.recommended_video_id for row in rows]
            )
        )
        edge_meta: dict[str, dict[str, Any]] = {}
        for row in rows:
            edge_meta.setdefault(
                row.recommended_video_id,
                {"channel_id": row.channel_id, "channel_name": row.channel_name,
                 "title": row.title},
            )
        metadata = _MetadataIndex(self._repos)

        if union.number_of_edges() > 0:
            undirected = union.to_undirected()
            communities = sorted(
                louvain_communities(undirected, seed=42),
                key=len,
                reverse=True,
            )
            node_community = {
                video_id: idx
                for idx, community in enumerate(communities)
                for video_id in community
            }
        else:
            node_community = {}

        nodes: list[GraphNode] = []
        for video_id in video_ids:
            info = metadata.video(video_id)
            fallback = edge_meta.get(video_id, {})
            n_in = in_degree.get(video_id, 0)
            n_out = out_degree.get(video_id, 0)
            kind = "other"
            if n_out > 0 and n_in > 0:
                kind = "both"
            elif n_out > 0:
                kind = "source"
            elif n_in > 0:
                kind = "target"
            nodes.append(
                GraphNode(
                    video_id=video_id,
                    title=info.get("title") or fallback.get("title"),
                    channel_id=info.get("channel_id") or fallback.get("channel_id"),
                    channel_name=info.get("channel_name") or fallback.get("channel_name"),
                    thumbnail_url=info.get("thumbnail_url"),
                    views=info.get("views"),
                    likes=info.get("likes"),
                    duration=info.get("duration"),
                    kind=kind,
                    in_degree=n_in,
                    out_degree=n_out,
                    run_ids=sorted(run_ids_by_node.get(video_id, set())),
                    run_types=sorted(run_types_by_node.get(video_id, set())),
                    community_id=node_community.get(video_id),
                    recommendations_scraped=bool(info.get("recommendations_scraped")),
                )
            )
        return nodes, edges

    # ------------------------------------------------------------------
    @staticmethod
    def _graph_from_edges(edges: list[Any]) -> nx.DiGraph:
        """Build the canonical ``nx.DiGraph`` from raw recommendation edges."""
        graph = nx.DiGraph()
        for edge in edges:
            graph.add_edge(
                edge.source_video_id,
                edge.recommended_video_id,
                position=edge.position,
                run_id=edge.collection_run_id,
                title=edge.title,
                channel_id=edge.channel_id,
            )
        return graph

    # ------------------------------------------------------------------
    def channel_projection(
        self, run_id: str | None = None
    ) -> ChannelProjection:
        """Distinct channels observed on edges and their edge coverage.

        Lightweight projection: no co-occurrence graph is built between
        channels (see model docstring). Returns channel names when a ``Channel``
        row exists so the picker is human-readable.
        """
        edges = self._repos.recommendations.list_recommendation_edges(run_id=run_id)
        channel_rows = self._repos.channels.list_channel_titles()
        channels = sorted({e.channel_id for e in edges if e.channel_id})
        edge_count = sum(1 for e in edges if e.channel_id)
        return ChannelProjection(
            channels=[
                ChannelFacet(
                    channel_id=cid,
                    channel_name=channel_rows.get(cid),
                )
                for cid in channels
            ],
            edge_count=edge_count,
        )

    # ------------------------------------------------------------------
    def channel_graph(
        self,
        run_id: str | None = None,
        layer_index: int | None = None,
        run_ids: list[str] | None = None,
        channel_id: str | None = None,
        channel_ids: list[str] | None = None,
        channel_scope: ChannelScope = "source",
    ) -> ChannelGraphPayload:
        """Co-occurrence graph of channels over the (layer-scoped) video edges.

        Nodes are channels; a directed edge A->B aggregates the video-level
        edges whose source video belongs to channel A and recommended video to
        channel B (weighted by ``video_edge_count`` with the first few video
        pairs kept as evidence). Video-level edges whose **either** endpoint's
        channel cannot be resolved are dropped and counted in
        ``unattributed_edges`` - never invented as a synthetic node.

        Node metadata: channel name/avatar from the ``Channel`` row and latest
        subscriber count from the channel observations, all in batch reads.
        ``channel_id``/``channel_scope`` mirror the video-graph semantics:
        ``source`` keeps edges whose source channel matches (default),
        ``target`` keeps edges whose target channel matches, ``either`` keeps
        edges touching the channel on either endpoint.
        """
        metadata = _MetadataIndex(self._repos)
        channel_videos: dict[str, set[str]] = {}
        out_neighbours: dict[str, set[str]] = {}
        in_neighbours: dict[str, set[str]] = {}
        channel_run_ids: dict[str, set[str]] = {}
        channel_run_types: dict[str, set[str]] = {}
        pair_counts: dict[tuple[str, str], int] = {}
        pair_runs: dict[tuple[str, str], set[str]] = {}
        pair_samples: dict[tuple[str, str], list[dict[str, Any]]] = {}
        unattributed = 0
        # When layer-scoped, attribute each video edge to the EARLIEST layer that
        # observed its (source, target) pair, so re-observations in later layers
        # don't re-add the same channel-channel co-occurrence there.
        _min_layer = self._earliest_layer_by_pair() if layer_index is not None else None

        for edge in self._repos.recommendations.list_recommendation_edges(
            run_id=run_id
        ):
            if layer_index is not None and edge.layer_index != layer_index:
                continue
            if (
                _min_layer is not None
                and _min_layer.get((edge.source_video_id, edge.recommended_video_id))
                != layer_index
            ):
                continue
            if run_ids is not None and edge.collection_run_id not in run_ids:
                continue
            run_type, _ = metadata.run(edge.collection_run_id)
            source_channel = metadata.video(edge.source_video_id).get("channel_id")
            target_channel = (
                metadata.video(edge.recommended_video_id).get("channel_id")
                or edge.channel_id
            )
            if not source_channel or not target_channel:
                unattributed += 1
                continue
            channel_set = set(channel_ids) if channel_ids else None
            if channel_id:
                channel_set = {channel_id}
            if channel_set:
                if channel_scope == "target":
                    if target_channel not in channel_set:
                        continue
                elif channel_scope == "either":
                    if (
                        source_channel not in channel_set
                        and target_channel not in channel_set
                    ):
                        continue
                else:  # default "source"
                    if source_channel not in channel_set:
                        continue

            channel_videos.setdefault(source_channel, set()).add(edge.source_video_id)
            channel_videos.setdefault(target_channel, set()).add(
                edge.recommended_video_id
            )
            out_neighbours.setdefault(source_channel, set()).add(target_channel)
            in_neighbours.setdefault(target_channel, set()).add(source_channel)
            if edge.collection_run_id:
                channel_run_ids.setdefault(source_channel, set()).add(
                    edge.collection_run_id
                )
                channel_run_ids.setdefault(target_channel, set()).add(
                    edge.collection_run_id
                )
            if run_type:
                channel_run_types.setdefault(source_channel, set()).add(run_type)
                channel_run_types.setdefault(target_channel, set()).add(run_type)

            pair = (source_channel, target_channel)
            pair_counts[pair] = pair_counts.get(pair, 0) + 1
            if edge.collection_run_id:
                pair_runs.setdefault(pair, set()).add(edge.collection_run_id)
            samples = pair_samples.setdefault(pair, [])
            if len(samples) < 3:
                samples.append(
                    {
                        "source_video_id": edge.source_video_id,
                        "recommended_video_id": edge.recommended_video_id,
                        "position": edge.position,
                    }
                )

        channel_rows = self._repos.channels.list_channel_descriptors()
        latest_observations = self._repos.channels.latest_channel_metrics(
            list(channel_videos)
        )
        nodes: list[ChannelGraphNode] = []
        for channel_id in sorted(channel_videos):
            channel = channel_rows.get(channel_id) or {}
            obs = latest_observations.get(channel_id) or {}
            nodes.append(
                ChannelGraphNode(
                    channel_id=channel_id,
                    channel_name=channel.get("title"),
                    avatar_url=channel.get("avatar_url"),
                    subscriber_count=obs.get("subscriber_count"),
                    video_count=len(channel_videos[channel_id]),
                    in_degree=len(in_neighbours.get(channel_id, set())),
                    out_degree=len(out_neighbours.get(channel_id, set())),
                    run_ids=sorted(channel_run_ids.get(channel_id, set())),
                    run_types=sorted(channel_run_types.get(channel_id, set())),
                )
            )

        edges: list[ChannelGraphEdge] = []
        for (source, target), count in pair_counts.items():
            edges.append(
                ChannelGraphEdge(
                    source=source,
                    target=target,
                    video_edge_count=count,
                    run_ids=sorted(pair_runs.get((source, target), set())),
                    sample_video_pairs=pair_samples.get((source, target), []),
                )
            )
        edges.sort(key=lambda e: (e.source, e.target))

        channel_ids = sorted({n.channel_id for n in nodes})
        channels = [
            ChannelFacet(
                channel_id=cid,
                channel_name=channel_rows.get(cid, {}).get("title"),
            )
            for cid in channel_ids
        ]

        runs_by_id = {r.run_id: r for r in self._repos.runs.list_runs()}
        runs = [
            {
                "run_id": r.run_id,
                "run_type": r.run_type.value if r.run_type else None,
                "name": r.name,
            }
            for r in runs_by_id.values()
            if run_id is None or r.run_id == run_id
        ]

        return ChannelGraphPayload(
            nodes=nodes,
            edges=edges,
            channels=channels,
            runs=runs,
            node_count=len(nodes),
            edge_count=len(edges),
            unattributed_edges=unattributed,
        )

    # ------------------------------------------------------------------
    def _slice(self, run_id: str) -> NetworkSlice:
        """Build one per-run ``NetworkSlice`` (PageRank ``top_ranked``)."""
        graph = self._graph_service.build_graph(run_id)
        slice_model = NetworkSlice(
            run_id=run_id,
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
            density=float(nx.density(graph)),
        )
        if graph.number_of_edges():
            slice_model.reciprocity = float(nx.reciprocity(graph))
            top_pagerank = sorted(
                nx.pagerank(graph).items(), key=lambda item: item[1], reverse=True
            )
            slice_model.top_ranked = [
                {
                    "video_id": video,
                    "pagerank": round(rank, 6),
                }
                for video, rank in top_pagerank
            ]
        return slice_model

    @staticmethod
    def _degree_distribution(
        degrees: list[int],
    ) -> DegreeDistribution:
        """Percentile summary (linear interpolation via StatisticsService)."""
        if not degrees:
            return DegreeDistribution()
        return DegreeDistribution(
            min=float(min(degrees)),
            max=float(max(degrees)),
            mean=round(sum(degrees) / len(degrees), 6),
            median=StatisticsService.percentile(degrees, 50),
            p25=StatisticsService.percentile(degrees, 25),
            p75=StatisticsService.percentile(degrees, 75),
            p90=StatisticsService.percentile(degrees, 90),
            p95=StatisticsService.percentile(degrees, 95),
            p99=StatisticsService.percentile(degrees, 99),
        )

    @staticmethod
    def _top_scores(
        scores: dict[str, float], top_n: int
    ) -> list[dict[str, Any]]:
        """Top-``n`` name/score rows with deterministic tie-breaking."""
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [
            {"video_id": video, "score": round(float(score), 6)}
            for video, score in ranked[:top_n]
        ]

    @staticmethod
    def _top_counts(
        counts: dict[str, int], top_n: int, value_key: str
    ) -> list[dict[str, Any]]:
        """Top-``n`` name/count rows with deterministic tie-breaking."""
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return [
            {"video_id": video, value_key: count} for video, count in ranked[:top_n]
        ]