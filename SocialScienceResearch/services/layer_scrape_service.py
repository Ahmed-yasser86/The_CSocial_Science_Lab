"""Layer-crawl service (docs/analysis_next_layer_scrape.md).

A *layer crawl* lets a researcher repeatedly expand the recommendation
network:

1. **Bootstrap** a seed ``LayerRun`` (layer 0) from any existing run
   (``bootstrap_layer``) whose frontier is the run's videos/sources.
2. **Scrape the next layer** (``scrape_next_layer``): observe the frontier's
   recommendations (one ``RECOMMENDATION`` run per video, reusing
   ``RecommendationService.collect_recommendations_for_videos``), deep-enrich
   every newly seen target (``extract_video`` + comments via the inherited
   ``_persist_comments``), classify everything against the pre-crawl snapshot
   (``NEW_VIDEO``/``EXISTING_VIDEO``, ``NEW_CHANNEL``/``EXISTING_CHANNEL``,
   ``CONNECTED``/``DISCONNECTED`` components) and persist a ``LayerRun``
   anchor with the NewRelationsReport counts.

The crawl anchor (``LayerRun``) is written *after* the step completes (like
datasets), so frontier resolution and layer summaries are cheap reads. All
network work runs under ONE shared rate limiter (inherited throttling).

This service extends :class:`RecommendationService`, inheriting the provider,
repos, settings, run bookkeeping, comment persistence and rate limiter; the
only RecommendationService change is the ``layer_index`` threading (runs +
edges), which is fully backward compatible.
"""

from __future__ import annotations

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from SocialScienceResearch.acquisition.normalization import (
    normalize_channel,
    normalize_video,
    normalize_video_observation,
)
from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    EntityType,
    ErrorType,
    RunType,
)
from SocialScienceResearch.domain.layer_models import (
    ComponentSummary,
    ExistingVideoEntry,
    ExpansionActionPayload,
    ExpansionOverallStats,
    ExpansionStats,
    LayerFrontier,
    LayerRun,
    NewChannelEntry,
    NewRelationsReport,
    NewVideoEntry,
    ScrapeFilters,
    VideoExpansionStats,
)
from SocialScienceResearch.domain.models import CollectionRun
from SocialScienceResearch.utils.idgen import new_id, utcnow
from SocialScienceResearch.utils.logger import get_logger

from .collection_service import ProgressReporter, _RateLimiter
from .recommendation_service import RecommendationService
from .results import CollectionResult

logger = get_logger(__name__)


@dataclass
class _LayerSnapshot:
    """Pre-crawl state captured before any layer writes (doc §5.1)."""

    preexisting_video_ids: set[str] = field(default_factory=set)
    preexisting_channel_ids: set[str] = field(default_factory=set)
    preexisting_edge_pairs: set[tuple[str, str]] = field(default_factory=set)
    old_nodes: set[str] = field(default_factory=set)


class LayerScrapeService(RecommendationService):
    """Layer-crawl orchestration over the recommendation network."""

    # ------------------------------------------------------------------
    # Layer anchors
    # ------------------------------------------------------------------
    def list_layers(self, run_id: str | None = None) -> list[LayerRun]:
        """All crawl layers, oldest (layer 0) first.

        Network-expansion anchors (marked ``config_json["expansion"]``) are
        excluded so the crawl stepper stays a pure crawl view.

        When ``run_id`` is supplied the result is scoped to that run's layer
        family: the seed layer(s) whose ``parent_run_id`` equals ``run_id`` plus
        every descendant reached through ``parent_layer_run_id``. This lets the
        Lab's network-slice selector drive the Layer tab instead of always
        showing the global newest layer.
        """
        layers = sorted(
            [
                layer
                for layer in self._repos.layers.list_layer_runs()
                if layer.config_json.get("expansion") is None
            ],
            key=lambda layer: layer.layer_index,
        )
        if run_id is None:
            return layers

        seeds = [
            layer
            for layer in layers
            if layer.layer_index == 0 and layer.parent_run_id == run_id
        ]
        if not seeds:
            return []
        family_ids = {layer.layer_run_id for layer in seeds}
        changed = True
        while changed:
            changed = False
            for layer in layers:
                if layer.layer_run_id in family_ids:
                    continue
                if layer.parent_layer_run_id in family_ids:
                    family_ids.add(layer.layer_run_id)
                    changed = True
        return [layer for layer in layers if layer.layer_run_id in family_ids]

    def get_layer(self, layer_run_id: str) -> LayerRun | None:
        """Return one crawl layer by id, or ``None``.

        Network-expansion anchors (marked ``config_json["expansion"]``) are
        excluded, mirroring :meth:`list_layers`, so a crawl layer is never
        confused with an expansion action (and ``scrape_next_layer`` cannot
        advance from an expansion anchor).
        """
        layer = self._repos.layers.get_layer_run(layer_run_id)
        if layer is None or layer.config_json.get("expansion") is not None:
            return None
        return layer

    def get_layer_frontier(self, layer_run_id: str) -> LayerFrontier | None:
        """The frontier of a layer (drives the UI stepper), or ``None``."""
        layer = self.get_layer(layer_run_id)
        if layer is None:
            return None
        return LayerFrontier(
            layer_index=layer.layer_index,
            video_ids=list(layer.discovered_video_ids),
            video_count=len(layer.discovered_video_ids),
        )

    def bootstrap_layer(
        self, run_id: str, projection: str = "video"
    ) -> LayerRun:
        """Create the seed layer (layer 0) from an existing run.

        The frontier (and discovered set) is the run's own videos/sources; no
        network work happens. Idempotent: a second bootstrap of the same run
        returns the existing layer-0 record.
        """
        run = self._repos.runs.get_run(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found")
        for existing in self.list_layers():
            if existing.layer_index == 0 and existing.parent_run_id == run_id:
                return existing
        frontier = self._resolve_run_frontier(run)
        layer = LayerRun(
            layer_run_id=new_id("lyr"),
            layer_index=0,
            parent_run_id=run_id,
            parent_layer_run_id=None,
            projection=projection,
            started_at=utcnow(),
            finished_at=utcnow(),
            status=CollectionStatus.SUCCESS,
            frontier_video_ids=frontier,
            discovered_video_ids=frontier,
            run_ids=[run_id],
            comments_collected=run.comments_collected or 0,
            summary={},
            config_json={},
        )
        self._repos.layers.save_layer_run(layer)
        return layer

    # ------------------------------------------------------------------
    # The crawl
    # ------------------------------------------------------------------
    def scrape_next_layer(
        self,
        *,
        parent_layer_run_id: str | None = None,
        parent_run_id: str | None = None,
        projection: str = "video",
        collect_comments: bool = True,
        concurrency: int | None = None,
        max_recommendations_per_video: int | None = None,
        reporter: ProgressReporter | None = None,
    ) -> list[CollectionResult]:
        """Scrape the next crawl layer (job worker entry point).

        Steps (doc §3):
        1. Resolve the layer: either from ``parent_layer_run_id`` (frontier =
           its ``discovered_video_ids``, ``layer_index + 1``) or from a seed
           ``parent_run_id`` (frontier = the run's videos/sources, layer 1).
        2. Snapshot the pre-crawl state for classification.
        3. Observe the frontier's recommendations (one run per video, edges
           stamped with the layer).
        4. Deep-enrich new targets: ``extract_video`` + comments for every
           recommended video without a ``Video`` row yet.
        5. Classify nodes/edges/components against the snapshot and persist
           the ``LayerRun`` anchor (with the counts in ``summary``) plus a
           layer-scoped aggregate dataset.

        Returns the per-video ``CollectionResult`` list (keeps the existing
        ``GET /jobs/{id}/result`` contract unchanged).
        """
        parent_layer, parent_layer_run_id = self._resolve_parent(
            parent_layer_run_id=parent_layer_run_id,
            parent_run_id=parent_run_id,
        )
        if parent_layer is not None:
            layer_index = parent_layer.layer_index + 1
            frontier = list(parent_layer.discovered_video_ids)
            # If no videos were newly discovered (e.g. all targets already
            # exist in the DB), fall back to the target videos from the
            # parent layer's edges so the crawl can expand deeper.
            if not frontier and parent_layer.run_ids:
                seen = set()
                for rid in parent_layer.run_ids:
                    for e in self._repos.recommendations.list_recommendation_edges(run_id=rid):
                        if e.recommended_video_id not in seen:
                            seen.add(e.recommended_video_id)
                            frontier.append(e.recommended_video_id)
            parent_run_id = parent_layer.parent_run_id or parent_run_id
        else:
            layer_index = 1
            run = self._repos.runs.get_run(parent_run_id)
            if run is None:
                raise ValueError(f"Run {parent_run_id} not found")
            frontier = self._resolve_run_frontier(run)
            parent_layer_run_id = None

        if not frontier:
            raise ValueError("Frontier is empty; nothing to scrape")

        started_at = utcnow()
        snapshot = self._snapshot()

        self._report(
            reporter,
            "layer/scrape",
            discovered=len(frontier),
            message=(
                f"Scraping layer {layer_index}: {len(frontier)} frontier video(s)"
            ),
        )
        results = self.collect_recommendations_for_videos(
            frontier,
            parent_run_id=parent_run_id,
            layer_index=layer_index,
            concurrency=concurrency,
            max_recommendations_per_video=max_recommendations_per_video,
            reporter=reporter,
        )
        run_ids = [r.run_id for r in results]

        new_edges = self._repos.recommendations.list_recommendation_edges(
            run_ids=run_ids,
        )
        throttle = _RateLimiter(self._request_delay())
        errors: list = []
        discovered = self._enrich_new_targets(
            new_edges,
            run_ids,
            layer_index,
            collect_comments=collect_comments,
            throttle=throttle,
            errors=errors,
            reporter=reporter,
        )
        comments_collected = sum(v["comments"] for v in discovered)

        # ``discovered_video_ids`` = the videos deep-enriched *by this layer*
        # (newly seen targets). Pre-existing targets can still add edges/channels
        # without being "discovered" again, which is why a layer may report
        # "0 discovered" yet several new edges - that is consistent, not a bug.
        discovered_video_ids = [v["video"].video_id for v in discovered]

        self._report(
            reporter,
            "layer/classify",
            succeeded=len(discovered),
            message=f"Classifying {len(new_edges)} edge(s) and {len(discovered)} enriched video(s)",
        )

        report = self._classify(
            snapshot,
            new_edges,
            discovered,
            layer_index,
            layer_run_id=new_id("lyr"),
            projection=projection,
        )

        layer = LayerRun(
            layer_run_id=report.layer_run_id,
            layer_index=layer_index,
            parent_run_id=parent_run_id,
            parent_layer_run_id=parent_layer_run_id,
            projection=projection,
            started_at=started_at,
            finished_at=utcnow(),
            status=CollectionStatus.PARTIAL if errors else CollectionStatus.SUCCESS,
            frontier_video_ids=frontier,
            discovered_video_ids=discovered_video_ids,
            run_ids=run_ids,
            comments_collected=comments_collected,
            summary=report.counts,
            config_json={
                "collect_comments": collect_comments,
                "concurrency": concurrency,
            },
        )
        self._repos.layers.save_layer_run(layer)

        if new_edges and run_ids:
            anchor = self._repos.runs.get_run(run_ids[0])
            if anchor is not None:
                self._persist_run_dataset(
                    anchor,
                    new_edges,
                    channel_id=None,
                    layer_index=layer_index,
                    reporter=reporter,
                )

        self._report(
            reporter,
            "layer/complete",
            succeeded=len(run_ids),
            message=(
                f"Layer {layer_index} complete: {len(run_ids)} run(s), "
                f"{len(new_edges)} edge(s), {len(discovered)} video(s) enriched"
            ),
        )

        # Warm the graph cache so the user's post-crawl requests are instant
        # instead of hitting a cold ~20s rebuild that the proxy times out on.
        try:
            from .recommendation_graph_service import RecommendationGraphService
            RecommendationGraphService.clear_graph_cache()
            RecommendationGraphService(self._repos).build_graph(run_id=None)
        except Exception:  # noqa: BLE001 – best-effort; never block the crawl result
            logger.debug("Graph cache warm-up after layer crawl failed", exc_info=True)

        return results

    def relation_report(
        self, layer_run_id: str, snapshot: _LayerSnapshot | None = None
    ) -> NewRelationsReport | None:
        """Recompute (or recall) the NewRelationsReport for a layer.

        When the layer's ``summary`` holds the counts, the full report is
        recomputed from persisted edges/videos so the capped lists stay fresh
        without storing a megabyte payload. Returns ``None`` for an unknown
        layer.
        """
        layer = self.get_layer(layer_run_id)
        if layer is None:
            return None
        new_edges = self._repos.recommendations.list_recommendation_edges(
            run_ids=list(layer.run_ids)
        )
        discovered = []
        for video_id in layer.discovered_video_ids:
            video = self._repos.videos.get_video(video_id)
            if video is not None:
                discovered.append(
                    {"video": video, "comments": 0, "run_id": None}
                )
        if snapshot is None:
            # Baseline = the state that existed BEFORE this layer was crawled.
            # Exclude this layer's own runs AND every *later* layer in the same
            # crawl family, so a layer's "what was added" report is stable and
            # independent of layers crawled afterwards. Otherwise layer N's
            # counts get polluted by layer N+1's edges/nodes and comparing
            # layers (layer 1 vs layer 2) yields contradictory matrices.
            exclude = set(layer.run_ids)
            family_root = layer.parent_run_id
            if family_root is not None:
                for sibling in self.list_layers(family_root):
                    if (
                        sibling.layer_run_id != layer.layer_run_id
                        and (sibling.layer_index or 0) > (layer.layer_index or 0)
                    ):
                        exclude |= set(sibling.run_ids)
            snap = self._snapshot(exclude_run_ids=exclude)
        else:
            snap = snapshot
        return self._classify(
            snap,
            new_edges,
            discovered,
            layer.layer_index,
            layer_run_id=layer.layer_run_id,
            projection=layer.projection,
        )

    # ------------------------------------------------------------------
    # Network expansion (docs/network_expansion_scrape_all.md)
    # ------------------------------------------------------------------
    def list_expansions(self) -> list[LayerRun]:
        """All network-expansion action anchors, newest first."""
        return sorted(
            [
                layer
                for layer in self._repos.layers.list_layer_runs()
                if layer.config_json.get("expansion") is not None
            ],
            key=lambda layer: layer.started_at,
            reverse=True,
        )

    def get_expansion(self, action_id: str) -> LayerRun | None:
        """One network-expansion anchor by id, or ``None``."""
        layer = self._repos.layers.get_layer_run(action_id)
        if layer is None or layer.config_json.get("expansion") is None:
            return None
        return layer

    def expand_video(
        self,
        video_id: str,
        *,
        filters: ScrapeFilters,
        reporter: ProgressReporter | None = None,
    ) -> LayerRun:
        """One-hop expansion of a single video (doc §3).

        Scrapes the video's recommendations, deep-enriches newly seen targets,
        classifies the additions and persists an expansion anchor plus an
        auto-created Project. Returns the anchor.

        The source video does NOT need a persisted ``Video`` row: a recommended
        video may exist only as a graph node (a target that was never
        deep-enriched). When missing, the bulk scrape extracts + persists it
        on the fly, mirroring :meth:`expand_all_videos`.
        """
        video = self._repos.videos.get_video(video_id)
        return self._expand(
            [video_id],
            filters=filters,
            kind="video",
            parent_run_id=video.first_observed_run_id if video else None,
            reporter=reporter,
        )

    def expand_all_videos(
        self,
        video_ids: list[str],
        *,
        filters: ScrapeFilters,
        parent_run_id: str | None = None,
        reporter: ProgressReporter | None = None,
    ) -> LayerRun:
        """One-hop expansion of a set of videos (the current network slice).

        ``video_ids`` may be empty when ``parent_run_id`` names a run whose
        videos/sources form the scope. Returns the anchor.
        """
        scope = self._resolve_slice(video_ids, parent_run_id)
        return self._expand(
            scope,
            filters=filters,
            kind="all",
            parent_run_id=parent_run_id,
            reporter=reporter,
        )

    def expansion_stats(self, layer: LayerRun) -> ExpansionStats:
        """Overall + per-video statistics for one expansion action."""
        action = self.expansion_payload(layer)
        edges = self._repos.recommendations.list_recommendation_edges(
            run_ids=layer.run_ids,
        )
        graph = nx.DiGraph()
        for edge in edges:
            graph.add_edge(edge.source_video_id, edge.recommended_video_id)
        videos = {v.video_id: v for v in self._repos.videos.list_videos()}
        channels = {c.channel_id: c for c in self._repos.channels.list_channels()}

        node_count = graph.number_of_nodes()
        overall = ExpansionOverallStats(
            node_count=node_count,
            edge_count=graph.number_of_edges(),
            channel_count=len(
                {
                    videos[n].channel_id
                    for n in graph.nodes
                    if n in videos and videos[n].channel_id
                }
            ),
            source_count=len({e.source_video_id for e in edges}),
            component_count=len(list(nx.weakly_connected_components(graph))),
            avg_out_degree=(
                round(graph.number_of_edges() / node_count, 4) if node_count else None
            ),
            density=float(nx.density(graph)) if node_count else None,
            comment_count=layer.comments_collected,
        )

        stored = (layer.config_json.get("expansion") or {}).get("video_stats") or {}
        video_rows: list[VideoExpansionStats] = []
        for video_id, stats in stored.items():
            video = videos.get(video_id)
            channel_name = None
            if video and video.channel_id and video.channel_id in channels:
                channel_name = channels[video.channel_id].title
            video_rows.append(
                VideoExpansionStats(
                    video_id=video_id,
                    title=video.title if video else None,
                    channel_id=video.channel_id if video else None,
                    channel_name=channel_name,
                    recommendation_count=int(stats.get("recommendation_count", 0)),
                    in_degree=int(stats.get("in_degree", 0)),
                    new_targets=int(stats.get("new_targets", 0)),
                    new_channels=int(stats.get("new_channels", 0)),
                    new_edges=int(stats.get("new_edges", 0)),
                    comments_collected=int(stats.get("comments_collected", 0)),
                )
            )
        video_rows.sort(key=lambda row: row.recommendation_count, reverse=True)
        return ExpansionStats(action=action, overall=overall, videos=video_rows)

    # ------------------------------------------------------------------
    # Expansion internals
    # ------------------------------------------------------------------
    def _expand(
        self,
        frontier: list[str],
        *,
        filters: ScrapeFilters,
        kind: str,
        parent_run_id: str | None,
        reporter: ProgressReporter | None,
    ) -> LayerRun:
        """One-hop expansion pipeline shared by per-video and scrape-all.

        Mirrors :meth:`scrape_next_layer` (snapshot → observe → enrich →
        classify → anchor), but threads ``filters`` into the network work and
        auto-persists a Project for the action.
        """
        if not frontier:
            raise ValueError("No videos in the expansion scope; nothing to scrape")

        started_at = utcnow()
        snapshot = self._snapshot()
        comment_config: dict[str, Any] = {
            "collect_comments": filters.collect_comments,
            "max_comments_per_video": filters.max_comments_per_video,
            "comment_min_likes": filters.comment_min_likes,
            "comment_date_from": filters.comment_date_from,
            "comment_date_to": filters.comment_date_to,
            "comment_criteria": None,
        }

        self._report(
            reporter,
            "expansion/start",
            discovered=len(frontier),
            message=f"Expanding {len(frontier)} video(s) ({kind})",
        )
        results = self.collect_recommendations_for_videos(
            frontier,
            parent_run_id=parent_run_id,
            dedupe_run_ids=(
                [parent_run_id] if (filters.dedupe and parent_run_id) else None
            ),
            max_recommendations_per_video=filters.max_recommendations_per_video,
            concurrency=filters.concurrency,
            reporter=reporter,
        )
        run_ids = [result.run_id for result in results]
        new_edges = self._repos.recommendations.list_recommendation_edges(
            run_ids=run_ids,
        )
        throttle = _RateLimiter(self._request_delay())
        errors: list = []
        discovered = self._enrich_new_targets(
            new_edges,
            run_ids,
            layer_index=0,
            collect_comments=filters.collect_comments,
            include_existing=not filters.only_new_targets,
            comment_config=comment_config,
            throttle=throttle,
            errors=errors,
            reporter=reporter,
        )
        comments_collected = sum(item["comments"] for item in discovered)
        discovered_ids = {item["video"].video_id for item in discovered}

        # ``discovered_video_ids`` = videos deep-enriched *by this expansion*.
        discovered_video_ids = list(discovered_ids)

        report = self._classify(
            snapshot,
            new_edges,
            discovered,
            0,
            layer_run_id=new_id("lyr"),
            projection=filters.projection,
        )

        layer = LayerRun(
            layer_run_id=report.layer_run_id,
            layer_index=0,
            parent_run_id=parent_run_id,
            parent_layer_run_id=None,
            projection=filters.projection,
            started_at=started_at,
            finished_at=utcnow(),
            status=CollectionStatus.PARTIAL if errors else CollectionStatus.SUCCESS,
            frontier_video_ids=frontier,
            discovered_video_ids=discovered_video_ids,
            run_ids=run_ids,
            comments_collected=comments_collected,
            summary=report.counts,
            config_json={
                "expansion": {
                    "kind": kind,
                    "project_id": None,
                    "filters": filters.model_dump(),
                    "video_stats": self._per_video_stats(new_edges, discovered_ids),
                }
            },
        )
        self._repos.layers.save_layer_run(layer)

        dataset_ids: list[str] = []
        if new_edges and run_ids:
            anchor = self._repos.runs.get_run(run_ids[0])
            if anchor is not None:
                dataset_id = self._persist_run_dataset(
                    anchor,
                    new_edges,
                    channel_id=None,
                    reporter=reporter,
                )
                if dataset_id:
                    dataset_ids.append(dataset_id)

        project_id = self._persist_expansion_project(layer, dataset_ids)
        if project_id:
            expansion = layer.config_json["expansion"]
            expansion["project_id"] = project_id
            self._repos.layers.save_layer_run(layer)

        self._report(
            reporter,
            "expansion/complete",
            succeeded=len(run_ids),
            message=(
                f"Expansion complete ({kind}): {len(run_ids)} run(s), "
                f"{len(new_edges)} edge(s), {len(discovered)} video(s) enriched"
            ),
        )

        # Warm the graph cache so the user's post-expansion requests are
        # instant instead of hitting a cold rebuild (mirrors scrape_next_layer:
        # enrichment runs after the mid-run clear, so without this the graph
        # would show stub metadata until the TTL lapses).
        try:
            from .recommendation_graph_service import RecommendationGraphService
            RecommendationGraphService.clear_graph_cache()
            RecommendationGraphService(self._repos).build_graph(run_id=None)
        except Exception:  # noqa: BLE001 – best-effort; never block the crawl result
            logger.debug("Graph cache warm-up after expansion failed", exc_info=True)

        return layer

    def _resolve_slice(
        self, video_ids: list[str], run_id: str | None
    ) -> list[str]:
        """Resolve the 'current network slice' (doc §4.2).

        When scoping by a run, the frontier includes EVERY node in that run's
        graph snapshot -- not just the source videos. A node may appear only as
        a recommended target (connected from 2-3 sources) without ever having
        had its own recommendations scraped; expanding only sources would leave
        those target-only nodes permanently un-scraped. Including all nodes of
        the snapshot (sources + targets) guarantees each is either already
        scraped (flag set) or gets scraped now.
        """
        if video_ids:
            return list(dict.fromkeys(video_ids))
        if run_id:
            run = self._repos.runs.get_run(run_id)
            if run is None:
                raise ValueError(f"Run {run_id} not found")
            if run.run_type == RunType.CHANNEL:
                return [
                    v.video_id
                    for v in self._repos.videos.list_videos_by_run(run.run_id)
                ]
            edges = self._repos.recommendations.list_recommendation_edges(
                run_id=run.run_id
            )
            nodes: set[str] = set()
            for edge in edges:
                nodes.add(edge.source_video_id)
                nodes.add(edge.recommended_video_id)
            return sorted(nodes)
        raise ValueError("Expansion scope requires video_ids or run_id")

    @staticmethod
    def _per_video_stats(
        new_edges, discovered_ids: set[str]
    ) -> dict[str, dict[str, int]]:
        """Per-source counts captured at crawl time for cheap later reads."""
        stats: dict[str, dict[str, int]] = {}
        for source in sorted({e.source_video_id for e in new_edges}):
            out = [e for e in new_edges if e.source_video_id == source]
            targets = {e.recommended_video_id for e in out}
            new_targets = targets & discovered_ids
            new_channels = {
                e.channel_id
                for e in out
                if e.recommended_video_id in new_targets and e.channel_id
            }
            stats[source] = {
                "recommendation_count": len(out),
                "in_degree": sum(
                    1 for e in new_edges if e.recommended_video_id == source
                ),
                "new_targets": len(new_targets),
                "new_channels": len(new_channels),
                "new_edges": len(out),
                "comments_collected": 0,
            }
        return stats

    def _persist_expansion_project(
        self, layer: LayerRun, dataset_ids: list[str]
    ) -> str | None:
        """Auto-create one Project per expansion action (doc §3).

        The Project groups the action's datasets (and records its runs via the
        description + item name). A persistence failure is logged and never
        fails the expansion action.
        """
        try:
            from SocialScienceResearch.domain.dataset_models import (
                CreateProjectItemRequest,
                Project,
            )
            from SocialScienceResearch.services.project_item_service import (
                ProjectItemService,
            )
            from SocialScienceResearch.services.project_service import ProjectService

            expansion = layer.config_json.get("expansion") or {}
            kind = expansion.get("kind", "all")
            if kind == "video" and layer.frontier_video_ids:
                label = layer.frontier_video_ids[0]
            else:
                label = f"{len(layer.frontier_video_ids)} videos"
            now = utcnow()
            project = Project(
                project_id=new_id("prj"),
                name=f"Network expansion · {label} · {now.strftime('%Y-%m-%d %H:%M')}",
                description=(
                    f"Auto-created for a {kind} network-expansion scrape "
                    f"({now.isoformat()}): {len(layer.frontier_video_ids)} source "
                    f"video(s), {len(layer.run_ids)} run(s), "
                    f"{len(layer.discovered_video_ids)} video(s) enriched, "
                    f"{layer.comments_collected} comment(s). "
                    f"Filters: {expansion.get('filters', {})}."
                ),
                targets=[],
                config_hash="",
                created_at=now,
                updated_at=now,
            )
            project = ProjectService(self._repos).create(project)
            if dataset_ids:
                ProjectItemService(self._repos).create_item(
                    project.project_id,
                    CreateProjectItemRequest(
                        name=f"Expansion data ({kind})",
                        description=(
                            f"{len(layer.run_ids)} recommendation run(s), "
                            f"{len(dataset_ids)} dataset(s)."
                        ),
                        item_type="dataset_group",
                        dataset_ids=dataset_ids,
                    ),
                )
            logger.info(
                "expansion %s auto-persisted project %s (%d dataset(s))",
                layer.layer_run_id,
                project.project_id,
                len(dataset_ids),
            )
            return project.project_id
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to auto-persist expansion project for %s: %s",
                layer.layer_run_id,
                exc,
            )
            return None

    @staticmethod
    def expansion_payload(layer: LayerRun) -> ExpansionActionPayload:
        """Flatten a LayerRun anchor into the expansion payload shape."""
        expansion = layer.config_json.get("expansion") or {}
        return ExpansionActionPayload(
            action_id=layer.layer_run_id,
            kind=expansion.get("kind", "all"),
            parent_run_id=layer.parent_run_id,
            projection=layer.projection,
            status=layer.status.value,
            started_at=layer.started_at,
            finished_at=layer.finished_at,
            video_ids=layer.frontier_video_ids,
            discovered_video_ids=layer.discovered_video_ids,
            run_ids=layer.run_ids,
            comments_collected=layer.comments_collected,
            summary=layer.summary,
            filters=expansion.get("filters") or {},
            project_id=expansion.get("project_id"),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _resolve_parent(
        self,
        *,
        parent_layer_run_id: str | None,
        parent_run_id: str | None,
    ) -> tuple[LayerRun | None, str | None]:
        """Resolve the parent layer (or ``(None, None)`` for a seed run)."""
        if parent_layer_run_id:
            parent = self.get_layer(parent_layer_run_id)
            if parent is None:
                raise ValueError(f"Layer run {parent_layer_run_id} not found")
            return parent, parent.layer_run_id
        if parent_run_id is None:
            raise ValueError(
                "parent_run_id is required when parent_layer_run_id is not given"
            )
        return None, None

    def _resolve_run_frontier(self, run: CollectionRun) -> list[str]:
        """The frontier of a seed run: its videos or distinct edge sources.

        Mirrors the resolution ``POST /network/scrape/run`` uses
        (``api/app.py``).  For CHANNEL runs the frontier includes videos
        scraped by the parent run *and* the source videos from all its
        sub-runs (child video scrapes), since the parent run itself never
        touches videos directly.
        """
        if run.run_type == RunType.CHANNEL:
            video_ids: set[str] = {
                v.video_id
                for v in self._repos.videos.list_videos_by_run(run.run_id)
            }
            # Also include source videos from sub-runs (the videos that were
            # actually scraped, not the enriched targets).
            for sub in self._repos.runs.list_sub_runs(run.run_id):
                for e in self._repos.recommendations.list_recommendation_edges(
                    run_id=sub.run_id
                ):
                    video_ids.add(e.source_video_id)
            return sorted(video_ids)
        return sorted(
            {
                e.source_video_id
                for e in self._repos.recommendations.list_recommendation_edges(
                    run_id=run.run_id
                )
            }
        )

    def _snapshot(
        self, exclude_run_ids: set[str] | None = None
    ) -> _LayerSnapshot:
        """Pre-crawl state: video/channel/edge ids + the existing graph nodes.

        When ``exclude_run_ids`` is given, rows created by those runs (e.g. the
        layer's own runs when reconstructing a report) are excluded so the
        snapshot reflects the state that existed before the layer crawled.
        """
        exclude = exclude_run_ids or set()
        edges = self._repos.recommendations.list_recommendation_edges(
            exclude_run_ids=list(exclude) if exclude else None,
        )
        old_graph = nx.DiGraph()
        for edge in edges:
            old_graph.add_edge(edge.source_video_id, edge.recommended_video_id)
        return _LayerSnapshot(
            preexisting_video_ids={
                v.video_id
                for v in self._repos.videos.list_videos()
                if v.first_observed_run_id not in exclude
            },
            preexisting_channel_ids={
                c.channel_id
                for c in self._repos.channels.list_channels()
                if c.first_observed_run_id not in exclude
            },
            preexisting_edge_pairs={
                (e.source_video_id, e.recommended_video_id) for e in edges
            },
            old_nodes=set(old_graph.nodes),
        )

    def _is_recommendation_stub(self, video) -> bool:
        """True when a Video row is a recommendation-stub placeholder.

        Recommended targets are persisted as minimal ``Video`` rows (marked in
        ``raw_json`` with ``_discovery.kind == "recommendation"``) so they are
        visible in the corpus. They are still considered *new* targets for
        deep-enrichment: enrichment overwrites the stub with the full metadata
        and the marker disappears, so the classification stays correct.
        """
        discovery = (video.raw_json or {}).get("_discovery")
        return isinstance(discovery, dict) and discovery.get("kind") == "recommendation"

    def _drop_failed_stub(self, video_id: str) -> None:
        """Delete a recommendation stub whose deep-enrichment failed.

        A target whose enrichment errored must revert to a graph-node-only
        entity (no ``Video`` row), matching the pre-stub behaviour: a failed
        target stays discoverable through edges but is not part of the corpus.
        Only stubs are removed -- an already enriched video is left intact.
        """
        try:
            video = self._repos.videos.get_video(video_id)
            if video is not None and self._is_recommendation_stub(video):
                self._repos.videos.delete_video(video_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to drop recommendation stub %s after enrichment error: %s",
                video_id,
                exc,
            )

    def _enrich_new_targets(
        self,
        new_edges,
        run_ids: list[str],
        layer_index: int,
        *,
        collect_comments: bool,
        include_existing: bool = False,
        comment_config: dict[str, Any] | None = None,
        throttle: _RateLimiter,
        errors: list,
        reporter: ProgressReporter | None,
    ) -> list[dict[str, Any]]:
        """Deep-enrich newly seen target videos (doc §2.3/§3 step 4).

        Runs one ``extract_video`` per target concurrently (worker threads
        under the shared throttle), persisting ``Video`` + ``VideoObservation``
        + comments (via the inherited ``_persist_comments``) and upserting the
        ``Channel`` when resolvable. Returns a list of ``{"video", "comments",
        "run_id"}`` for every target that was deep-enriched, in the
        deterministic ``new_targets`` (sorted) order. Per-target progress is
        reported after each target completes so long layer runs never appear
        stalled.

        ``include_existing`` expands the target set to videos already in the
        corpus (network-expansion refresh); ``comment_config`` overrides the
        module-default comment criteria (network-expansion filters).
        """
        target_ids = {e.recommended_video_id for e in new_edges}
        existing = {
            v.video_id
            for v in self._repos.videos.list_videos()
            if not self._is_recommendation_stub(v)
        }
        new_targets = sorted(
            target_ids if include_existing else (target_ids - existing)
        )
        if not new_targets:
            return []
        # Bound the heavy deep-enrichment so a layer crawl over hundreds of new
        # targets always completes (and forms the LayerRun) instead of hanging
        # on a slow/degraded yt-dlp. Edges are already persisted; only the
        # per-video enrichment is capped. 0 = unlimited.
        cap = self._max_enrich_targets()
        if cap and len(new_targets) > cap:
            logger.info(
                "Capping layer deep-enrichment to %d of %d new targets "
                "(raise max_enrich_targets to enrich more)",
                cap,
                len(new_targets),
            )
            new_targets = new_targets[:cap]

        target_run: dict[str, str | None] = {}
        for edge in new_edges:
            target_run.setdefault(edge.recommended_video_id, edge.collection_run_id)
        first_run_id = run_ids[0] if run_ids else None
        effective = comment_config or self._effective_comment_config()
        concurrency = max(1, self._enrichment_concurrency())
        total = len(new_targets)

        self._report(
            reporter,
            "layer/enrich",
            discovered=total,
            message=f"Deep-enriching {total} new target video(s)",
        )

        enriched: list[dict[str, Any]] = []
        completed = 0
        order = {video_id: index for index, video_id in enumerate(new_targets)}
        pending_futures: dict = {}
        pool = ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="layer-enrich"
        )
        try:
            for video_id in new_targets:
                pending_futures[
                    pool.submit(self._fetch_target_video, video_id, throttle)
                ] = video_id

            # Process futures in batches: wait up to 120 s per round so a
            # single stalled yt-dlp call never freezes the entire layer.
            _FUTURE_TIMEOUT = 120
            while pending_futures:
                done, _ = concurrent.futures.wait(
                    pending_futures, timeout=_FUTURE_TIMEOUT,
                )
                if not done:
                    # All pending futures stalled – cancel them and move on.
                    for fut in list(pending_futures):
                        fut.cancel()
                    for vid in pending_futures.values():
                        completed += 1
                        self._report(
                            reporter,
                            "layer/enrich",
                            succeeded=completed,
                            message=f"Enriched {completed}/{total} target video(s) (stalled videos skipped)",
                        )
                    break
                for future in done:
                    video_id = pending_futures.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:  # noqa: BLE001
                        completed += 1
                        self._report(
                            reporter,
                            "layer/enrich",
                            succeeded=completed,
                            message=f"Enriched {completed}/{total} target video(s)",
                        )
                        continue
                    run_id = target_run.get(video_id) or first_run_id
                    run = self._repos.runs.get_run(run_id) if run_id else None
                    if run is None:
                        completed += 1
                        self._report(
                            reporter,
                            "layer/enrich",
                            succeeded=completed,
                            message=f"Enriched {completed}/{total} target video(s)",
                        )
                        continue
                    if result["error"] is not None:
                        exc = result["error"]
                        self._record_error(
                            run,
                            EntityType.VIDEO,
                            video_id,
                            exc.error_type,
                            str(exc),
                        )
                        errors.append(exc)
                        self._drop_failed_stub(video_id)
                        completed += 1
                        self._report(
                            reporter,
                            "layer/enrich",
                            succeeded=completed,
                            message=f"Enriched {completed}/{total} target video(s)",
                        )
                        continue
                    info = result["info"]
                    video = normalize_video(info, run.run_id)
                    if video is None:
                        self._record_error(
                            run,
                            EntityType.VIDEO,
                            video_id,
                            ErrorType.VALIDATION,
                            "Could not resolve a video id for the layer target.",
                        )
                        self._drop_failed_stub(video_id)
                        completed += 1
                        self._report(
                            reporter,
                            "layer/enrich",
                            succeeded=completed,
                            message=f"Enriched {completed}/{total} target video(s)",
                        )
                        continue

                    # A target that already exists keeps its original provenance:
                    # the run that FIRST observed it, never the run that re-scraped.
                    existing = self._repos.videos.get_video(video_id)
                    if (
                        existing is not None
                        and existing.first_observed_run_id is not None
                    ):
                        video.first_observed_run_id = existing.first_observed_run_id
                    self._repos.videos.upsert_video(video)
                    obs = normalize_video_observation(info, run.run_id, video.video_id)
                    if obs is not None:
                        self._repos.videos.save_video_observation(obs)

                    channel = normalize_channel(info, run.run_id)
                    if channel is not None:
                        self._repos.channels.upsert_channel(channel)

                    comment_count = 0
                    if collect_comments and info.get("comments"):
                        comment_count = self._persist_comments(
                            run,
                            info["comments"],
                            video.video_id,
                            errors,
                            effective,
                            reporter,
                        )
                    enriched.append(
                        {
                            "video": video,
                            "comments": comment_count,
                            "run_id": run.run_id,
                        }
                    )
                    completed += 1
            self._report(
                reporter,
                "layer/enrich",
                succeeded=completed,
                message=f"Enriched {completed}/{total} target video(s)",
            )
        finally:
            pool.shutdown(wait=False)

        enriched.sort(key=lambda item: order[item["video"].video_id])
        return enriched

    def _classify(
        self,
        snapshot: _LayerSnapshot,
        new_edges,
        discovered: list[dict[str, Any]],
        layer_index: int,
        *,
        layer_run_id: str = "",
        projection: str = "video",
    ) -> NewRelationsReport:
        """Classify nodes/edges/components against the pre-crawl snapshot.

        Exact algorithm per ``docs/analysis_next_layer_scrape.md`` §5: every
        deep-enriched video is ``NEW_VIDEO`` unless it already existed as a
        persisted video or a pre-crawl graph node (``EXISTING_VIDEO``); edge
        pairs seen before are ``SKIPPED_DUPLICATE``; components of the
        new-edge subgraph are ``CONNECTED`` when they touch ``old_nodes`` and
        ``DISCONNECTED`` otherwise.
        """
        channel_rows = {c.channel_id: c for c in self._repos.channels.list_channels()}
        video_rows = {v.video_id: v for v in self._repos.videos.list_videos()}

        new_edges_new = [
            e
            for e in new_edges
            if (e.source_video_id, e.recommended_video_id)
            not in snapshot.preexisting_edge_pairs
        ]
        skipped = len(new_edges) - len(new_edges_new)

        # Per-node classification.
        new_video_entries: list[NewVideoEntry] = []
        existing_video_entries: list[ExistingVideoEntry] = []
        new_count = 0
        existing_count = 0
        for item in discovered:
            video = item["video"]
            is_existing = (
                video.video_id in snapshot.preexisting_video_ids
                or video.video_id in snapshot.old_nodes
            )
            channel = channel_rows.get(video.channel_id) if video.channel_id else None
            if is_existing:
                existing_count += 1
                if len(existing_video_entries) < 200:
                    existing_video_entries.append(
                        ExistingVideoEntry(
                            video_id=video.video_id,
                            title=video.title,
                            channel_id=video.channel_id,
                        )
                    )
            else:
                new_count += 1
                if len(new_video_entries) < 200:
                    new_video_entries.append(
                        NewVideoEntry(
                            video_id=video.video_id,
                            title=video.title,
                            channel_id=video.channel_id,
                            channel_name=channel.title if channel else None,
                            thumbnail_url=video.thumbnail_url,
                            classification="new_video",
                        )
                    )

        # Per-channel classification (channels seen on new edges/nodes).
        seen_channels: set[str] = {
            e.channel_id for e in new_edges_new if e.channel_id
        }
        seen_channels |= {
            video.channel_id
            for item in discovered
            for video in [item["video"]]
            if video.channel_id
        }
        new_channel_entries: list[NewChannelEntry] = []
        new_channel_count = 0
        existing_channel_count = 0
        for channel_id in sorted(seen_channels):
            is_new = channel_id not in snapshot.preexisting_channel_ids
            if is_new:
                new_channel_count += 1
                if len(new_channel_entries) < 200:
                    channel = channel_rows.get(channel_id)
                    new_channel_entries.append(
                        NewChannelEntry(
                            channel_id=channel_id,
                            channel_name=channel.title if channel else None,
                            avatar_url=channel.avatar_url if channel else None,
                        )
                    )
            else:
                existing_channel_count += 1

        # Per-edge connectivity vs the old graph.
        connecting_edges = sum(
            1
            for e in new_edges_new
            if e.source_video_id in snapshot.old_nodes
            or e.recommended_video_id in snapshot.old_nodes
        )
        no_source_channel = sum(1 for e in new_edges_new if not e.channel_id)

        # Component connectivity over the new-edge subgraph.
        g_new = nx.DiGraph()
        for e in new_edges_new:
            g_new.add_edge(e.source_video_id, e.recommended_video_id)
        connected: list[ComponentSummary] = []
        disconnected: list[ComponentSummary] = []
        for component in nx.weakly_connected_components(g_new):
            sub = g_new.subgraph(component)
            summary = self._component_summary(component, sub, channel_rows, video_rows)
            if component & snapshot.old_nodes:
                connected.append(summary)
            else:
                disconnected.append(summary)
        connected.sort(key=lambda c: c.component_id)
        disconnected.sort(key=lambda c: c.component_id)

        sample_edges = [
            {
                "source_video_id": e.source_video_id,
                "recommended_video_id": e.recommended_video_id,
                "position": e.position,
                "run_id": e.collection_run_id,
            }
            for e in new_edges_new[:50]
        ]

        counts = {
            "new_videos": new_count,
            "existing_videos_referenced": existing_count,
            "new_channels": new_channel_count,
            "existing_channels_referenced": existing_channel_count,
            "new_edges": len(new_edges_new),
            "edges_connecting_to_existing_nodes": connecting_edges,
            "edges_without_source_channel": no_source_channel,
            "skipped_edges_duplicate": skipped,
            "new_components": len(disconnected),
            "connected_components": len(connected),
            "comments_collected": sum(item["comments"] for item in discovered),
        }

        return NewRelationsReport(
            layer_run_id=layer_run_id,
            layer_index=layer_index,
            projection=projection,
            generated_at=utcnow(),
            counts=counts,
            new_videos=new_video_entries,
            existing_videos=existing_video_entries,
            new_channels=new_channel_entries,
            connected_components=connected,
            disconnected_components=disconnected,
            sample_edges=sample_edges,
        )

    @staticmethod
    def _component_summary(
        component: set[str],
        subgraph,
        channel_rows: dict[str, Any],
        video_rows: dict[str, Any],
    ) -> ComponentSummary:
        """One component summary with a deterministic ``component_id``."""
        node_list = sorted(component)
        channel_names: set[str] = set()
        for video_id in node_list:
            channel = video_rows.get(video_id)
            if channel and channel.channel_id and channel.channel_id in channel_rows:
                name = channel_rows[channel.channel_id].title
                if name:
                    channel_names.add(name)
        return ComponentSummary(
            component_id=node_list[0],
            node_count=len(node_list),
            edge_count=int(subgraph.number_of_edges()),
            touches_channels=sorted(channel_names),
            node_video_ids=node_list,
        )

    def _effective_comment_config(self) -> dict[str, Any]:
        """Module-default comment criteria for layer enrichment."""
        collection = self._settings.collection
        return {
            "collect_comments": collection.collect_comments,
            "max_comments_per_video": collection.max_comments_per_video,
            "comment_min_likes": None,
            "comment_date_from": None,
            "comment_date_to": None,
            "comment_criteria": None,
        }
