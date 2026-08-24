"""Recommendation-network analysis over observed recommendation edges.

The recommendation repository stores *observed* relationships
(source video -> recommended video). This service loads those edges into a
directed :class:`networkx.DiGraph` and computes network metrics (degrees,
PageRank, hubs, reachable contexts) for the recommendation ecosystem.

The graph is rebuilt on demand from persisted observations - nothing is
fabricated, and edges are attributed to the run (or run set) that observed
them, so temporal network slices are possible (``run_id``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from SocialScienceResearch.persistence.base import Repositories
from SocialScienceResearch.services.dataset_service import DatasetService


@dataclass
class NetworkSummary:
    """Aggregate metrics over a recommendation network slice."""

    node_count: int = 0
    edge_count: int = 0
    source_count: int = 0
    target_count: int = 0
    most_recommended: list[dict[str, Any]] = field(default_factory=list)
    most_active_sources: list[dict[str, Any]] = field(default_factory=list)
    highest_pagerank: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class VideoNetworkContext:
    """Ego-network view for one video.

    ``recommended_by``/``recommends`` stay the canonical 1-hop neighbourhood
    (source -> video, video -> target). ``graph_edges`` is the *connected
    slice*: every observed edge whose source OR recommended target lies in the
    ego scope, so recommendations link to each other (shared/cross edges) and
    videos that are both a target of one edge and a source of another surface
    as their own central nodes instead of being pinned to the queried video.
    """

    video_id: str
    in_degree: int = 0
    out_degree: int = 0
    pagerank: float | None = None
    recommended_by: list[dict[str, Any]] = field(default_factory=list)
    recommends: list[dict[str, Any]] = field(default_factory=list)
    graph_edges: list[dict[str, Any]] = field(default_factory=list)
    node_channels: dict[str, str] = field(default_factory=dict)


class RecommendationGraphService:
    """Builds and analyzes the recommendation graph from stored edges."""

    # Built graphs are expensive (a full edge scan + DiGraph assembly) and the
    # underlying runs/observations are immutable once written, so we cache the
    # result. The whole-corpus slice (no run filter) can only grow when new runs
    # land, so it uses a short TTL to bound staleness; explicit run sets are
    # permanently cached because their inputs never change.
    _graph_cache: dict[tuple[int, bool, tuple[str, ...]], tuple[float, nx.DiGraph]] = {}
    _GRAPH_TTL_SECONDS = 300.0

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    # ------------------------------------------------------------------
    def build_graph(
        self,
        run_id: str | None = None,
        run_ids: list[str] | None = None,
    ) -> nx.DiGraph:
        """Build a directed graph from observed recommendation edges.

        ``run_id`` (single) or ``run_ids`` (list) scope which collection runs
        contribute edges; pass neither for the whole corpus. Pure read: never
        writes datasets or other state. Results are cached (see class note).
        """
        resolved = run_ids if run_ids is not None else ([run_id] if run_id else None)
        key = (
            id(self._repos),
            resolved is None,
            tuple(sorted(resolved)) if resolved else (),
        )
        cached = self._graph_cache.get(key)
        if cached is not None:
            stamp, graph = cached
            # Both whole-corpus and run-scoped slices expire after the TTL.
            # Run-scoped graphs are NOT cached forever: expansion/layer crawls
            # and recommendation scrapes append edges to existing runs, so a
            # permanent cache would serve a stale graph indefinitely. Writers
            # also call ``clear_graph_cache()`` to make new edges visible
            # immediately; the TTL is a safety net against a missed invalidation.
            if (time.time() - stamp) < self._GRAPH_TTL_SECONDS:
                return graph

        edges = self._repos.recommendations.list_recommendation_edges_graph(
            run_ids=resolved
        )
        graph = nx.DiGraph()
        for edge in edges:
            graph.add_edge(
                edge["source_video_id"],
                edge["recommended_video_id"],
                position=edge.get("position"),
                run_id=edge.get("collection_run_id"),
                title=edge.get("title"),
                channel_id=edge.get("channel_id"),
                channel_name=edge.get("channel_name"),
            )
        self._graph_cache[key] = (time.time(), graph)
        return graph

    @classmethod
    def clear_graph_cache(cls) -> None:
        """Invalidate cached graphs (call after any write that adds edges)."""
        cls._graph_cache.clear()

    def persist_graph_as_dataset(self, run_id: str | None = None) -> None:
        """Explicitly persist the current recommendation graph as a dataset.

        Idempotent snapshot utility for callers that genuinely want one; the
        read path never calls this automatically.
        """
        graph = self.build_graph(run_id)
        self._persist_graph_as_dataset(graph, run_id)

    def _persist_graph_as_dataset(self, graph: nx.DiGraph, run_id: str | None = None) -> None:
        """Persist the recommendation graph as a dataset."""
        dataset_service = DatasetService(self._repos)
        
        # Convert graph edges to rows for the dataset
        rows = []
        for source, target, data in graph.edges(data=True):
            rows.append({
                "source_video_id": source,
                "recommended_video_id": target,
                "position": data.get("position"),
                "run_id": data.get("run_id"),
                "title": data.get("title"),
                "channel_id": data.get("channel_id"),
            })
        
        # Create a dataset from the graph
        dataset_service.create_dataset(
            name=f"Recommendation Graph{' - Run ' + run_id if run_id else ''}",
            description=f"Recommendation graph for {'run ' + run_id if run_id else 'all runs'}",
            entity_type="recommendation",
            include_raw=False,
            run_ids=[run_id] if run_id else None,
            criteria=None,
            variable_selection=None,
        )

    # ------------------------------------------------------------------
    def summary(self, run_id: str | None = None, top_n: int = 10) -> NetworkSummary:
        """Compute aggregate metrics for a network slice."""
        graph = self.build_graph(run_id)
        if graph.number_of_nodes() == 0:
            return NetworkSummary()

        in_degree = dict(graph.in_degree())
        out_degree = dict(graph.out_degree())
        pagerank = nx.pagerank(graph)

        most_recommended = sorted(
            in_degree.items(), key=lambda item: item[1], reverse=True
        )[:top_n]
        most_active = sorted(
            out_degree.items(), key=lambda item: item[1], reverse=True
        )[:top_n]
        top_rank = sorted(
            pagerank.items(), key=lambda item: item[1], reverse=True
        )[:top_n]

        return NetworkSummary(
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
            source_count=sum(1 for d in out_degree.values() if d > 0),
            target_count=sum(1 for d in in_degree.values() if d > 0),
            most_recommended=[
                {"video_id": video, "times_recommended": count}
                for video, count in most_recommended
            ],
            most_active_sources=[
                {"video_id": video, "outgoing": count}
                for video, count in most_active
            ],
            highest_pagerank=[
                {"video_id": video, "pagerank": round(rank, 6)}
                for video, rank in top_rank
            ],
        )

    # ------------------------------------------------------------------
    def video_context(
        self,
        video_id: str,
        run_id: str | None = None,
        run_ids: list[str] | None = None,
        top_n: int = 50,
    ) -> VideoNetworkContext:
        """Ego-network context for one video (who recommends it, whom it recommends).

        ``run_id`` (single, legacy) or ``run_ids`` (list) scope which collection
        runs contribute the surrounding edges. Pass neither for the whole corpus.
        """
        resolved = run_ids if run_ids is not None else ([run_id] if run_id else None)
        graph = self.build_graph(run_ids=resolved)
        context = VideoNetworkContext(video_id=video_id)

        if graph.number_of_nodes() == 0:
            return context

        # Compute the ego scope (queried video + everyone who recommends it +
        # everything it recommends) up front so metadata is fetched only for
        # the slice's videos instead of the entire corpus.
        scope: set[str] = {video_id}
        if video_id in graph:
            for source, _, _ in graph.in_edges(video_id, data=True):
                scope.add(source)
            for _, target, _ in graph.out_edges(video_id, data=True):
                scope.add(target)

        node_meta = self._repos.videos.list_video_metadata(list(scope))
        context.node_channels = {
            vid: (meta.get("channel_id") or "")
            for vid, meta in node_meta.items()
        }

        # A video may be persisted in the corpus yet have no recommendation
        # edges; ``G.in_degree(v)`` returns an ``InDegreeView`` (not an int)
        # for a node absent from the graph, so guard the node membership.
        context.in_degree = int(graph.in_degree(video_id)) if video_id in graph else 0
        context.out_degree = int(graph.out_degree(video_id)) if video_id in graph else 0
        context.pagerank = round(float(nx.pagerank(graph).get(video_id, 0.0)), 6)

        # Cache run_type lookups to avoid repeated repo calls
        run_type_cache: dict[str, str | None] = {}

        def get_run_type(run_id: str | None) -> str | None:
            if not run_id:
                return None
            if run_id not in run_type_cache:
                run = self._repos.runs.get_run(run_id)
                run_type_cache[run_id] = run.run_type.value if run else None
            return run_type_cache[run_id]

        # Connected slice: the ego scope is the queried video plus everyone it
        # recommends and everyone who recommends it. Every edge touching that
        # scope is kept, so recommendations link to each other (e.g. a video
        # scraped as a recommendation that itself recommends a sibling appears
        # as its own node with a cross-edge) instead of a star around the
        # queried video. Scope comes from the graph (untruncated) so top_n
        # pagination of the tables never shrinks the rendered network.

        slice_edges: list[dict[str, Any]] = []
        for source, target, data in graph.edges(data=True):
            if source not in scope and target not in scope:
                continue
            edge_run_id = data.get("run_id")
            slice_edges.append(
                {
                    "source_video_id": source,
                    "recommended_video_id": target,
                    "position": data.get("position"),
                    "run_id": edge_run_id,
                    "title": data.get("title"),
                    "run_type": get_run_type(edge_run_id),
                }
            )
        # Deduplicate repeat observations of the same directed pair within the
        # slice (same feed slot across re-scrapes), keeping the first edge.
        seen_pairs: set[tuple[Any, ...]] = set()
        unique_slice_edges: list[dict[str, Any]] = []
        for edge in slice_edges:
            key = (
                edge["source_video_id"],
                edge["recommended_video_id"],
                edge["position"],
                edge["run_id"],
            )
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            unique_slice_edges.append(edge)
        context.graph_edges = self._by_feed_rank(
            unique_slice_edges, "recommended_video_id"
        )

        for source, _, data in graph.in_edges(video_id, data=True):
            run_id = data.get("run_id")
            context.recommended_by.append(
                {
                    "source_video_id": source,
                    "position": data.get("position"),
                    "run_id": run_id,
                    "title": data.get("title"),
                    "run_type": get_run_type(run_id),
                }
            )
        for _, target, data in graph.out_edges(video_id, data=True):
            run_id = data.get("run_id")
            context.recommends.append(
                {
                    "recommended_video_id": target,
                    "position": data.get("position"),
                    "run_id": run_id,
                    "title": data.get("title"),
                    "run_type": get_run_type(run_id),
                }
            )
        # Feed-rank ordering: position is the slot a recommendation occupied in
        # the source's "Up Next" rail, so the observed rail order (ranked items
        # first, unranked last) is the canonical display order everywhere.
        context.recommended_by = self._by_feed_rank(
            context.recommended_by, "source_video_id"
        )
        context.recommends = self._by_feed_rank(
            context.recommends, "recommended_video_id"
        )
        context.recommended_by = context.recommended_by[:top_n]
        context.recommends = context.recommends[:top_n]
        return context

    @staticmethod
    def _by_feed_rank(
        rows: list[dict[str, Any]], id_key: str
    ) -> list[dict[str, Any]]:
        """Order rows by ascending feed ``position`` (None/unknown last)."""
        return sorted(
            rows,
            key=lambda row: (
                row.get("position") is None,
                row.get("position") if row.get("position") is not None else 0,
                row.get("run_id") or "",
                str(row.get(id_key) or ""),
            ),
        )
