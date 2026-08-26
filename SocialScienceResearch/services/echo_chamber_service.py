"""Echo-chamber detector service (echo_chamber_detector_plan.md phases E1).

Thin orchestration over :class:`LayerScrapeService` — NO parallel graph math.
The detector chains ``scrape_next_layer(discovery_mode="frontier")`` around a
seed video as ONE async job, and after every completed layer computes five
OBSERVED signal snapshots over the accumulated crawl-family graph using
:class:`NetworkAnalyticsService` (graph()/metrics()/louvain seed=42) plus
edge repetition stats. Signals that cannot be observed carry
``status="unavailable"`` and ``null`` values — never fabricated.

Natural stops (honesty, plan §2.2): frontier exhaustion raises inside
``scrape_next_layer`` -> status ``exhausted``; a zero-edge layer ->
``unsupported_stop``. The per-layer timeline is append-only: snapshots are
frozen at computation time and never recomputed retroactively (pitfall A5).

Writers inherit the R1 discipline through ``scrape_next_layer``, which calls
``RecommendationGraphService.clear_graph_cache()`` after every layer.
"""

from __future__ import annotations

from typing import Any

import networkx as nx

from SocialScienceResearch.domain.echo_models import EchoDetection
from SocialScienceResearch.services.echo_scoring import compute_score
from SocialScienceResearch.services.layer_scrape_service import LayerScrapeService
from SocialScienceResearch.services import structural_metrics as sm
from SocialScienceResearch.services.network_analytics_service import (
    NetworkAnalyticsService,
)
from SocialScienceResearch.utils.idgen import new_id, utcnow
from SocialScienceResearch.utils.logger import get_logger

logger = get_logger(__name__)

#: Absolute lifetime cap on layers per detection (plan §3 continue() bound).
MAX_LAYERS_TOTAL = 10

#: Default number of layers per detection request.
DEFAULT_MAX_LAYERS = 5

#: How many top-recommended videos feed the S5 commenter overlap.
S5_TOP_K = 5


class EchoChamberError(ValueError):
    """Raised for invalid detection requests (unknown id, bad state, cap)."""


class EchoChamberService(LayerScrapeService):
    """Multi-layer crawl + observed-signal timeline around one seed video."""

    def __init__(self, provider, repos, settings=None, *, jobs=None) -> None:
        super().__init__(provider, repos, settings=settings)
        self._jobs = jobs
        self._analytics = NetworkAnalyticsService(repos)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start(
        self,
        *,
        video_url: str | None = None,
        video_id: str | None = None,
        seed_run_id: str | None = None,
        max_layers: int = DEFAULT_MAX_LAYERS,
        collect_comments: bool = False,
        projection: str = "video",
        tags: list[str] | None = None,
    ) -> EchoDetection:
        """Create a detection record and queue its layered crawl as ONE job.

        The seed run (and its network fetch) is resolved inside the job
        worker unless ``seed_run_id`` names an existing run, so the POST
        returns immediately with ``{detection_id, job_id}``. ``projection``
        selects which node type the chamber signals are measured over
        ("video" recommendation graph or the "channel" graph).
        """
        if not (1 <= max_layers <= MAX_LAYERS_TOTAL):
            raise ValueError(
                f"max_layers must be between 1 and {MAX_LAYERS_TOTAL}"
            )
        if projection not in ("video", "channel"):
            raise ValueError("projection must be 'video' or 'channel'")
        if seed_run_id is None and not video_url and not video_id:
            raise ValueError("video_url, video_id or seed_run_id is required")
        if seed_run_id is not None and self._repos.runs.get_run(seed_run_id) is None:
            raise ValueError(f"Run {seed_run_id} not found")

        now = utcnow()
        job_id = new_id("job")
        detection = EchoDetection(
            detection_id=new_id("ech"),
            seed_run_id=seed_run_id,
            job_id=job_id,
            status="pending",
            params={
                "video_url": video_url,
                "video_id": video_id,
                "max_layers": max_layers,
                "discovery_mode": "frontier",
                "collect_comments": collect_comments,
                "projection": projection,
                "tags": list(tags or []),
            },
            created_at=now,
            updated_at=now,
        )
        self._save(detection)

        def _worker(reporter) -> dict[str, Any]:
            return self._crawl_layers(detection.detection_id, {"job_id": job_id}, reporter)

        self._jobs.submit(
            _worker, kind="echo_chamber", job_id=job_id, tags=tags
        )
        return detection

    def continue_detection(
        self, detection_id: str, extra_layers: int = 1
    ) -> EchoDetection:
        """Append more layers to a finished detection (plan §3.2)."""
        detection = self.get_detection(detection_id)
        if detection is None:
            raise KeyError(f"Echo detection {detection_id} not found")
        if detection.status not in ("completed", "exhausted", "stopped", "unsupported_stop"):
            raise ValueError(
                f"Detection {detection_id} is {detection.status!r}; "
                "only finished detections can be continued"
            )
        current_max = max(
            (snap.get("layer_index", 0) for snap in detection.layers), default=0
        )
        remaining = MAX_LAYERS_TOTAL - current_max
        if remaining <= 0:
            raise ValueError(
                f"Detection reached the hard cap of {MAX_LAYERS_TOTAL} layers"
            )
        extra = min(extra_layers, remaining)
        detection.status = "running"
        detection.updated_at = utcnow()
        job_id = new_id("job")
        detection.job_id = job_id
        self._save(detection)

        def _worker(reporter) -> dict[str, Any]:
            return self._crawl_layers(
                detection.detection_id, {"job_id": job_id}, reporter, extra_layers=extra
            )

        self._jobs.submit(_worker, kind="echo_chamber", job_id=job_id)
        return detection

    def stop(self, detection_id: str) -> EchoDetection:
        """Request a cooperative stop; honoured between layers."""
        detection = self.get_detection(detection_id)
        if detection is None:
            raise KeyError(f"Echo detection {detection_id} not found")
        if detection.job_id and self._jobs is not None:
            self._jobs.cancel(detection.job_id)
        detection.status = "stopped"
        detection.updated_at = utcnow()
        self._save(detection)
        return detection

    def get_detection(self, detection_id: str) -> EchoDetection | None:
        return self._repos.echo_detections.get_detection(detection_id)

    def list_detections(self) -> list[EchoDetection]:
        return self._repos.echo_detections.list_detections()

    # ------------------------------------------------------------------
    # The crawl worker (single implementation shared by start/continue)
    # ------------------------------------------------------------------
    def _crawl_layers(
        self,
        detection_id: str,
        job_id_holder: dict[str, str],
        reporter,
        *,
        extra_layers: int | None = None,
    ) -> dict[str, Any]:
        """Chain frontier layers, snapshotting signals after each one."""
        detection = self._require_detection(detection_id)
        detection.status = "running"
        detection.updated_at = utcnow()
        self._save(detection)
        try:
            summary = self._execute_crawl(
                detection, job_id_holder, reporter, extra_layers=extra_layers
            )
            return summary
        except Exception as exc:  # noqa: BLE001 - surface failure on the record
            logger.warning(
                "Echo detection %s failed: %s", detection_id, exc, exc_info=True
            )
            detection = self._require_detection(detection_id)
            detection.status = "failed"
            detection.error = str(exc)[:500]
            detection.updated_at = utcnow()
            self._save(detection)
            raise

    def _execute_crawl(
        self,
        detection: EchoDetection,
        job_id_holder: dict[str, str],
        reporter,
        *,
        extra_layers: int | None,
    ) -> dict[str, Any]:
        params = detection.params
        collect_comments = bool(params.get("collect_comments"))
        target_layers = extra_layers or int(params.get("max_layers") or DEFAULT_MAX_LAYERS)

        # 1. Resolve the seed run (network work happens here for URL seeds).
        seed_run_id = detection.seed_run_id
        if seed_run_id is None:
            result = self.collect_recommendations(
                video_url=params.get("video_url"),
                video_id=params.get("video_id"),
                reporter=reporter,
            )
            seed_run_id = result.run_id
            detection.seed_run_id = seed_run_id
            detection.seed_video_id = result.target_id
        if detection.seed_video_id is None:
            run = self._repos.runs.get_run(seed_run_id)
            detection.seed_video_id = run.target_video_id if run else None

        # 2. Layer 0 anchor (cheap, idempotent). An empty frontier (a seed
        # with neither persisted videos nor observable recommendation edges)
        # is an honest natural stop - nothing can be crawled.
        try:
            layer0 = self.bootstrap_layer(seed_run_id)
        except ValueError:
            detection.status = "unsupported_stop"
            detection.error = (
                "Seed has no crawlable frontier (no videos and no observed "
                "recommendation edges); there is nothing to detect on"
            )
            detection.updated_at = utcnow()
            self._save(detection)
            return {
                "detection_id": detection.detection_id,
                "status": detection.status,
                "layers": len(detection.layers),
            }
        if detection.seed_video_id is None and layer0.frontier_video_ids:
            # Channel-run seeds have no target_video_id; the seed video is
            # the first frontier member (deterministic sorted order).
            detection.seed_video_id = layer0.frontier_video_ids[0]
        detection.root_layer_run_id = layer0.layer_run_id
        if not any(s.get("layer_index") == 0 for s in detection.layers):
            detection.layers.append(self._layer_snapshot(detection, layer0))
        detection.score = self._score_for(detection)
        detection.updated_at = utcnow()
        self._save(detection)

        # 3. Chain frontier-mode layers until target/cap/cancel/natural stop.
        family = self.list_layers(seed_run_id)
        last_layer = family[-1]
        stop_status: str | None = None
        done = 0
        for _ in range(target_layers):
            if self._stop_requested(job_id_holder):
                stop_status = "stopped"
                break
            done += 1
            try:
                self.scrape_next_layer(
                    parent_layer_run_id=last_layer.layer_run_id,
                    discovery_mode="frontier",
                    collect_comments=collect_comments,
                    projection=str(
                        (detection.params or {}).get("projection") or "video"
                    ),
                    reporter=reporter,
                )
            except ValueError as exc:
                if "no unscraped videos" in str(exc):
                    stop_status = "exhausted"
                    done -= 1
                    break
                raise
            family = self.list_layers(seed_run_id)
            last_layer = family[-1]
            snapshot = self._layer_snapshot(detection, last_layer)
            detection = self._require_detection(detection.detection_id)
            detection.layers.append(snapshot)
            detection.score = self._score_for(detection)
            detection.updated_at = utcnow()
            self._save(detection)
            self._report(
                reporter,
                f"layer_{snapshot['layer_index']}_done",
                discovered=target_layers,
                succeeded=done,
                edges_saved=snapshot["edges_observed"],
                message=(
                    f"Layer {snapshot['layer_index']} done: "
                    f"{snapshot['edges_observed']} edge(s), "
                    f"{snapshot['nodes_discovered']} video(s) discovered"
                ),
            )
            if snapshot["edges_observed"] == 0:
                stop_status = "unsupported_stop"
                break

        detection = self._require_detection(detection.detection_id)
        if self._stop_requested(job_id_holder):
            detection.status = "stopped"
        else:
            detection.status = stop_status or "completed"
        if stop_status == "exhausted" and not detection.error:
            detection.error = (
                "Frontier exhausted: every reachable video's recommendations "
                "have been observed (natural stop, distinct from a verdict)"
            )
        detection.updated_at = utcnow()
        self._save(detection)
        return {
            "detection_id": detection.detection_id,
            "status": detection.status,
            "layers": len(detection.layers),
            "score": detection.score,
        }

    def _stop_requested(self, job_id_holder: dict[str, str]) -> bool:
        job_id = job_id_holder.get("job_id")
        return bool(job_id and self._jobs is not None and self._jobs.is_cancel_requested(job_id))

    # ------------------------------------------------------------------
    # Signal computation (observed - never estimated)
    # ------------------------------------------------------------------
    def _family_layers(self, seed_run_id: str | None):
        if seed_run_id is None:
            return []
        return self.list_layers(seed_run_id)

    def _layer_snapshot(
        self, detection: EchoDetection, layer
    ) -> dict[str, Any]:
        """Freeze one append-only timeline row for a completed layer."""
        family = [
            l for l in self._family_layers(detection.seed_run_id)
            if l.layer_index <= layer.layer_index
        ]
        family_run_ids = [rid for l in family for rid in (l.run_ids or [])]
        projection = str(
            (detection.params or {}).get("projection") or "video"
        )
        signals = self._compute_signals(
            detection, family_run_ids, projection=projection
        )
        graph_payload = self._analytics.graph(run_ids=family_run_ids or None)
        return {
            "layer_run_id": layer.layer_run_id,
            "layer_index": layer.layer_index,
            "nodes_discovered": len(layer.discovered_video_ids),
            "edges_observed": self._count_edges(layer.run_ids),
            "nodes_total": graph_payload.node_count,
            "signals": signals,
            "computed_at": utcnow().isoformat(),
        }

    def _compute_signals(
        self,
        detection: EchoDetection,
        family_run_ids: list[str],
        *,
        projection: str = "video",
    ) -> dict[str, Any]:
        """The five observed signals (plan §2.1) for the accumulated family.

        ``projection="video"`` measures S2 as louvain community concentration
        around the seed video; ``projection="channel"`` measures S2 as the
        share of family edges whose recommended video belongs to the seed
        video's channel (channel-level reinforcement), keeping the same
        observed-only honesty contract.
        """
        family = [
            l
            for l in self._family_layers(detection.seed_run_id)
            if not family_run_ids or any(rid in family_run_ids for rid in (l.run_ids or []))
        ]
        return {
            "s1": self._signal_s1(family),
            "s2": self._signal_s2(detection, family_run_ids)
            if projection == "video"
            else self._signal_s2_channel(detection, family_run_ids),
            "s3": self._signal_s3(detection, family_run_ids),
            "s4": self._signal_s4(family),
            "s5": self._signal_s5(detection, family_run_ids),
        }

    @staticmethod
    def _signal(value: float | None, detail: dict[str, Any]) -> dict[str, Any]:
        if value is None:
            return {"value": None, "status": "unavailable", "detail": detail}
        return {"value": value, "status": "available", "detail": detail}

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {"value": None, "status": "unavailable", "detail": {"reason": reason}}

    def _count_edges(self, run_ids: list[str] | None) -> int:
        if not run_ids:
            return 0
        return len(
            self._repos.recommendations.list_recommendation_edges(run_ids=list(run_ids))
        )

    # S1 -- Frontier collapse ratio ----------------------------------------
    def _signal_s1(self, family) -> dict[str, Any]:
        """Share of new edges whose TARGET an earlier layer already knew.

        Reported per-layer AND cumulative (cumulative is the scored value).
        Undefined before layer 2 (nothing can collapse yet) -> unavailable.
        """

        def _edge_collapse(layer, earlier: set[str]) -> tuple[int, int]:
            edges = self._repos.recommendations.list_recommendation_edges(
                run_ids=list(layer.run_ids or [])
            )
            collapsed = sum(1 for e in edges if e.recommended_video_id in earlier)
            return collapsed, len(edges)

        def _earlier_set(index: int) -> set[str]:
            earlier: set[str] = set()
            for previous in family:
                if previous.layer_index < index:
                    earlier.update(previous.frontier_video_ids or [])
                    earlier.update(previous.discovered_video_ids or [])
            return earlier

        current = family[-1] if family else None
        per_layer_value = None
        per_detail = {"collapsed": 0, "total": 0}
        if current is not None and current.layer_index >= 2:
            collapsed, total = _edge_collapse(current, _earlier_set(current.layer_index))
            if total:
                per_layer_value = round(collapsed / total, 6)
                per_detail = {"collapsed": collapsed, "total": total}

        # Cumulative over ALL layers >= 2 so far, against everything crawled
        # before each of them (the scored value).
        cum_value = None
        cum_detail = {"collapsed": 0, "total": 0}
        collapsed_total = 0
        edge_total = 0
        for layer in family:
            if layer.layer_index < 2:
                continue
            collapsed, total = _edge_collapse(layer, _earlier_set(layer.layer_index))
            collapsed_total += collapsed
            edge_total += total
        if edge_total:
            cum_value = round(collapsed_total / edge_total, 6)
            cum_detail = {"collapsed": collapsed_total, "total": edge_total}

        value = cum_value if cum_value is not None else per_layer_value
        if value is None:
            return self._unavailable(
                "no collapsible layers yet (needs >= 2 crawled layers)"
            )
        detail = {
            "per_layer": per_layer_value,
            "cumulative": cum_value,
            "per_layer_detail": per_detail,
            "cumulative_detail": cum_detail,
            "layer_index": current.layer_index if current else None,
        }
        return self._signal(value, detail)

    # S2 -- Seed-community concentration ------------------------------------
    def _signal_s2_channel(
        self, detection: EchoDetection, family_run_ids: list[str]
    ) -> dict[str, Any]:
        """Channel-projection S2: share of family edges reinforcing the seed
        video's channel.

        concentration = edge share of the seed's channel among ALL family
        recommendation targets (observed counts only). Unavailable when the
        seed video or its channel cannot be resolved - never estimated.
        """
        video_id = (detection.params or {}).get("video_id")
        seed_channel = None
        if video_id:
            video = self._repos.videos.get_video(str(video_id))
            seed_channel = video.channel_id if video is not None else None
            if video is not None and video.raw_json:
                pass
        if not seed_channel and detection.seed_run_id:
            run = self._repos.runs.get_run(detection.seed_run_id)
            if run is not None:
                seed_channel = None  # channel runs carry their own id
        if not seed_channel:
            return self._unavailable(
                "seed video's channel could not be resolved for "
                "channel-projection concentration"
            )
        edges = self._repos.recommendations.list_recommendation_edges(
            run_ids=list(family_run_ids) if family_run_ids else None
        ) if family_run_ids else []
        total = len(edges)
        if not total:
            return self._unavailable("no observed edges in this crawl yet")
        channel_map = self._video_channel_map()
        reinforced = 0
        for e in edges:
            if channel_map.get(e.recommended_video_id) == seed_channel:
                reinforced += 1
        value = round(reinforced / total, 6)
        return self._signal(
            value,
            {
                "projection": "channel",
                "seed_channel_id": seed_channel,
                "reinforcing_edges": reinforced,
                "total_edges": total,
            },
        )

    def _signal_s2(self, detection: EchoDetection, family_run_ids: list[str]) -> dict[str, Any]:
        """Louvain(seed=42) community share of the seed + normalized conc.

        concentration = community_share / (comm_size / n_nodes), clamped [0,1];
        raw share and modularity always travel in ``detail`` (plan §2.1 S2).
        """
        if not family_run_ids:
            return self._unavailable("no crawled runs yet")
        payload = self._analytics.graph(run_ids=family_run_ids)
        n_nodes = payload.node_count
        if n_nodes == 0 or payload.edge_count == 0:
            return self._unavailable("empty family graph")
        seed_community = next(
            (n.community_id for n in payload.nodes if n.video_id == detection.seed_video_id),
            None,
        )
        if seed_community is None:
            return self._unavailable("seed node missing from the family graph")
        members = [
            n for n in payload.nodes if n.community_id == seed_community
        ]
        comm_share = round(len(members) / n_nodes, 6)
        base = len(members) / n_nodes
        concentration = self._clamp01(comm_share / base) if base else None
        modularity = self._family_modularity(family_run_ids)
        detail = {
            "community_share": comm_share,
            "modularity": modularity,
            "community_size": len(members),
            "node_count": n_nodes,
            "community_id": seed_community,
        }
        if concentration is None:
            return self._unavailable("degenerate community sizes")
        return self._signal(concentration, detail)

    def _family_modularity(self, family_run_ids: list[str]) -> float | None:
        """Modularity via the shared engine (``_metrics_for_graph``), no re-math."""
        graph = nx.DiGraph()
        for row in self._analytics.edges(run_ids=family_run_ids):
            graph.add_edge(row.source_video_id, row.recommended_video_id)
        if graph.number_of_edges() == 0:
            return None
        return self._analytics._metrics_for_graph(graph).modularity

    @staticmethod
    def _clamp01(value: float | None) -> float | None:
        if value is None:
            return None
        return round(max(0.0, min(1.0, value)), 6)

    # S3 -- Top-channel share ------------------------------------------------
    def _signal_s3(self, detection: EchoDetection, family_run_ids: list[str]) -> dict[str, Any]:
        """Weighted in-degree shares on the channel projection of the family."""
        if not family_run_ids:
            return self._unavailable("no crawled runs yet")
        projection = self._analytics.channel_graph(run_ids=family_run_ids)
        weighted_in: dict[str, int] = {}
        total = 0
        for edge in projection.edges:
            weighted_in[edge.target] = weighted_in.get(edge.target, 0) + edge.video_edge_count
            total += edge.video_edge_count
        if total == 0:
            return self._unavailable("no channel-attributed edges in the family graph")
        ranked = sorted(weighted_in.values(), reverse=True)
        top1 = round(ranked[0] / total, 6)
        top3 = round(sum(ranked[:3]) / total, 6)
        seed_channel = None
        if detection.seed_video_id:
            video = self._repos.videos.get_video(detection.seed_video_id)
            seed_channel = video.channel_id if video else None
        seed_share = (
            round(weighted_in.get(seed_channel, 0) / total, 6)
            if seed_channel
            else None
        )
        # Full observed share distribution (desc), bounded at 500 entries.
        names = self._repos.channels.list_channel_titles()
        channel_shares = [
            {
                "channel_id": channel_id,
                "channel_name": names.get(channel_id),
                "weight": weight,
                "share": round(weight / total, 6),
            }
            for channel_id, weight in sorted(
                weighted_in.items(), key=lambda kv: (-kv[1], kv[0])
            )[:500]
        ]
        detail = {
            "top1": top1,
            "top3": top3,
            "seed_channel_share": seed_share,
            "seed_channel_id": seed_channel,
            "weighted_edge_total": total,
            "channel_shares": channel_shares,
        }
        return self._signal(top1, detail)

    # S4 -- Cross-layer repetition -------------------------------------------
    def _signal_s4(self, family) -> dict[str, Any]:
        """Distinct pairs observed in >= 2 different layers / distinct pairs.

        Video-pair value plus the channel-stability analog in ``detail``.
        """
        if len(family) < 2:
            return self._unavailable("needs at least 2 crawled layers")
        pair_layers: dict[tuple[str, str], set[int]] = {}
        channel_pair_layers: dict[tuple[str, str], set[int]] = {}
        channels = self._repos.videos.list_video_metadata()
        for l in family:
            for edge in self._repos.recommendations.list_recommendation_edges(
                run_ids=list(l.run_ids or [])
            ):
                pair_layers.setdefault(
                    (edge.source_video_id, edge.recommended_video_id), set()
                ).add(l.layer_index)
                source_channel = channels.get(edge.source_video_id, {}).get("channel_id")
                target_channel = (
                    channels.get(edge.recommended_video_id, {}).get("channel_id")
                    or edge.channel_id
                )
                if source_channel and target_channel:
                    channel_pair_layers.setdefault(
                        (source_channel, target_channel), set()
                    ).add(l.layer_index)
        if not pair_layers:
            return self._unavailable("no observed edges across layers")
        repeated = sum(1 for layers in pair_layers.values() if len(layers) >= 2)
        channel_repeated = sum(
            1 for layers in channel_pair_layers.values() if len(layers) >= 2
        )
        pair_repeat = round(repeated / len(pair_layers), 6)
        channel_repeat = (
            round(channel_repeated / len(channel_pair_layers), 6)
            if channel_pair_layers
            else None
        )
        detail = {
            "pair_repeat": pair_repeat,
            "channel_repeat": channel_repeat,
            "distinct_pairs": len(pair_layers),
            "repeated_pairs": repeated,
        }
        return self._signal(pair_repeat, detail)

    # S5 -- Commenter-overlap reinforcement (optional) -----------------------
    def _signal_s5(self, detection: EchoDetection, family_run_ids: list[str]) -> dict[str, Any]:
        """Mean Jaccard overlap between seed commenters and top rec commenters.

        Available ONLY when comments were collected during the crawl and at
        least one top-recommended video actually has persisted commenters;
        otherwise explicitly unavailable (never a fabricated 0).
        """
        if not detection.params.get("collect_comments"):
            return self._unavailable("comments were not collected during the crawl")
        if detection.seed_video_id is None:
            return self._unavailable("seed video unresolved")
        seed_commenters = self._commenters(detection.seed_video_id)
        if not seed_commenters:
            return self._unavailable("no comments collected on the seed video")
        payload = self._analytics.graph(run_ids=family_run_ids or None)
        targets = sorted(
            (n for n in payload.nodes if n.video_id != detection.seed_video_id),
            key=lambda n: (-(n.in_degree or 0), n.video_id),
        )[:S5_TOP_K]
        overlaps: list[dict[str, Any]] = []
        for node in targets:
            commenters = self._commenters(node.video_id)
            if not commenters:
                continue
            union = seed_commenters | commenters
            jaccard = round(len(seed_commenters & commenters) / len(union), 6) if union else None
            overlaps.append({"video_id": node.video_id, "jaccard": jaccard})
        if not overlaps:
            return self._unavailable(
                "none of the top-recommended videos has collected comments"
            )
        mean_jaccard = round(
            sum(o["jaccard"] for o in overlaps) / len(overlaps), 6
        )
        detail = {
            "mean_jaccard": mean_jaccard,
            "top_k": S5_TOP_K,
            "per_video": overlaps,
        }
        return self._signal(mean_jaccard, detail)

    def _commenters(self, video_id: str) -> set[str]:
        commenters: set[str] = set()
        for comment in self._repos.comments.list_comments(video_id):
            author = comment.author_id or comment.author_name
            if author:
                commenters.add(author)
        return commenters

    # ------------------------------------------------------------------
    # On-demand lenses (video | channel) over STORED crawl edges only
    # ------------------------------------------------------------------
    def _video_channel_map(self) -> dict[str, str]:
        """One-shot {video_id -> channel_id} map for lens computations.

        Replaces the per-edge ``get_video`` N+1 that crashed the connection
        pool on large crawls (2k+ edges) - a single query serves every
        channel resolution within one lens computation.
        """
        cached = getattr(self, "_lens_channel_map", None)
        if cached is not None:
            return cached
        meta = self._repos.videos.list_video_metadata()
        mapping = {
            vid: (entry or {}).get("channel_id")
            for vid, entry in meta.items()
            if entry
        }
        self._lens_channel_map = mapping
        return mapping

    def _channel_of(self, video_id: str, fallback: str | None = None) -> str | None:
        channels = self._video_channel_map()
        return channels.get(video_id) or fallback

    def _signal_s1_channel(self, family) -> dict[str, Any]:
        """Channel-projection S1: share of new channel-pairs whose TARGET
        channel an earlier layer already knew (same honesty rules as S1)."""

        def _layer_pairs(layer) -> list[tuple[str, str]]:
            pairs: list[tuple[str, str]] = []
            for e in self._repos.recommendations.list_recommendation_edges(
                run_ids=list(layer.run_ids or [])
            ):
                source_channel = self._channel_of(e.source_video_id)
                target_channel = self._channel_of(
                    e.recommended_video_id, getattr(e, "channel_id", None)
                )
                if source_channel and target_channel:
                    pairs.append((source_channel, target_channel))
            return pairs

        def _earlier_set(index: int) -> set[str]:
            earlier: set[str] = set()
            for previous in family:
                if previous.layer_index >= index:
                    continue
                for video_id in list(previous.frontier_video_ids or []) + list(
                    previous.discovered_video_ids or []
                ):
                    channel = self._channel_of(video_id)
                    if channel:
                        earlier.add(channel)
                for _src, target in _layer_pairs(previous):
                    earlier.add(target)
            return earlier

        current = family[-1] if family else None
        cum_value = None
        cum_detail = {"collapsed": 0, "total": 0}
        collapsed_total = 0
        pair_total = 0
        for layer in family:
            if layer.layer_index < 2:
                continue
            earlier = _earlier_set(layer.layer_index)
            pairs = _layer_pairs(layer)
            collapsed_total += sum(1 for _s, t in pairs if t in earlier)
            pair_total += len(pairs)
        if pair_total:
            cum_value = round(collapsed_total / pair_total, 6)
            cum_detail = {"collapsed": collapsed_total, "total": pair_total}
        if cum_value is None:
            return self._unavailable(
                "no collapsible channel-pair layers yet (needs >= 2 crawled layers)"
            )
        return self._signal(
            cum_value,
            {
                "projection": "channel",
                "cumulative": cum_value,
                "cumulative_detail": cum_detail,
                "layer_index": current.layer_index if current else None,
            },
        )

    def _signal_s4_channel(self, family) -> dict[str, Any]:
        """Channel-projection S4: distinct channel-pairs observed in >= 2
        different layers / distinct channel-pairs."""
        if len(family) < 2:
            return self._unavailable("needs at least 2 crawled layers")
        pair_layers: dict[tuple[str, str], set[int]] = {}
        for l in family:
            for edge in self._repos.recommendations.list_recommendation_edges(
                run_ids=list(l.run_ids or [])
            ):
                source_channel = self._channel_of(edge.source_video_id)
                target_channel = self._channel_of(
                    edge.recommended_video_id, getattr(edge, "channel_id", None)
                )
                if source_channel and target_channel:
                    pair_layers.setdefault(
                        (source_channel, target_channel), set()
                    ).add(l.layer_index)
        if not pair_layers:
            return self._unavailable("no channel-attributed edges across layers")
        repeated = sum(1 for layers in pair_layers.values() if len(layers) >= 2)
        value = round(repeated / len(pair_layers), 6)
        return self._signal(
            value,
            {
                "projection": "channel",
                "pair_repeat": value,
                "distinct_pairs": len(pair_layers),
                "repeated_pairs": repeated,
            },
        )

    def _top_videos(self, family_run_ids: list[str]) -> list[dict[str, Any]]:
        """Top-10 videos by in-degree within the stored crawl edges."""
        payload = self._analytics.graph(run_ids=family_run_ids or None)
        ranked = sorted(
            payload.nodes,
            key=lambda n: (-(n.in_degree or 0), n.video_id),
        )[:10]
        return [
            {
                "video_id": n.video_id,
                "title": n.title,
                "channel_id": n.channel_id,
                "channel_name": n.channel_name,
                "in_degree": n.in_degree,
                "out_degree": n.out_degree,
            }
            for n in ranked
        ]

    def _top_channels(self, family_run_ids: list[str]) -> list[dict[str, Any]]:
        """Top-10 channels by weighted in-degree within the stored crawl."""
        projection = self._analytics.channel_graph(run_ids=family_run_ids or None)
        weighted_in: dict[str, int] = {}
        total_edges = 0
        for edge in projection.edges:
            weighted_in[edge.target] = (
                weighted_in.get(edge.target, 0) + edge.video_edge_count
            )
            total_edges += edge.video_edge_count
        names = {n.channel_id: n.channel_name for n in projection.nodes}
        ranked = sorted(weighted_in.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
        return [
            {
                "channel_id": channel_id,
                "channel_name": names.get(channel_id),
                "weighted_in_degree": count,
                "share": round(count / total_edges, 6) if total_edges else None,
            }
            for channel_id, count in ranked
        ]

    def _seed_payload(self, detection: EchoDetection) -> dict[str, Any] | None:
        """The 'analysis started from' seed card data (observed rows only)."""
        video_id = detection.seed_video_id or (detection.params or {}).get("video_id")
        if not video_id:
            return None
        video = self._repos.videos.get_video(str(video_id))
        if video is None:
            return {"video_id": str(video_id)}
        channel_name = None
        if video.channel_id:
            channel_name = self._repos.channels.list_channel_titles().get(
                video.channel_id
            )
        return {
            "video_id": video.video_id,
            "title": video.title,
            "thumbnail_url": getattr(video, "thumbnail_url", None),
            "channel_id": video.channel_id,
            "channel_name": channel_name,
            "url": f"https://www.youtube.com/watch?v={video.video_id}",
        }

    def lens(self, detection_id: str, projection: str = "video") -> dict[str, Any]:
        """Recompute one lens on demand from the STORED crawl edges only.

        ``projection="video"`` is the signal math of the stored timeline;
        ``projection="channel"`` aggregates the same edges at channel level
        (S2 = seed-channel reinforcement share, S3 = top-channel share,
        S1/S4 on channel pairs, S5 unavailable unless comments exist).
        Nothing here re-crawls or estimates - every number comes from
        persisted observations of this detection's crawl-family runs.
        """
        detection = self.get_detection(detection_id)
        if detection is None:
            raise KeyError(f"Echo detection {detection_id} not found")
        if projection not in ("video", "channel"):
            raise ValueError("projection must be 'video' or 'channel'")
        family = self._family_layers(detection.seed_run_id)
        family_run_ids = [rid for layer in family for rid in (layer.run_ids or [])]
        # One shared video->channel map for the whole lens computation: kills
        # the per-edge N+1 that crashed the pool on large crawls.
        self._lens_channel_map = self._video_channel_map()
        if projection == "video":
            signals = {
                "s1": self._signal_s1(family),
                "s2": self._signal_s2(detection, family_run_ids),
                "s3": self._signal_s3(detection, family_run_ids),
                "s4": self._signal_s4(family),
                "s5": self._signal_s5(detection, family_run_ids),
            }
        else:
            signals = {
                "s1": self._signal_s1_channel(family),
                "s2": self._signal_s2_channel(detection, family_run_ids),
                "s3": self._signal_s3(detection, family_run_ids),
                "s4": self._signal_s4_channel(family),
            "s5": self._signal_s5(detection, family_run_ids),
        }
        self._lens_channel_map = None
        score = compute_score(
            {key: signals[key].get("value") for key in ("s1", "s2", "s3", "s4", "s5")},
            computed_at=utcnow(),
        )
        return {
            "detection_id": detection.detection_id,
            "projection": projection,
            "seed_run_id": detection.seed_run_id,
            "family_run_count": len(family),
            "edge_count": self._count_edges(family_run_ids),
            "signals": signals,
            "score": score,
            "top_videos": self._top_videos(family_run_ids),
            "top_channels": self._top_channels(family_run_ids),
            "seed": self._seed_payload(detection),
            "computed_at": utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Structural lenses (spec §5-§22) - computed from STORED edges only
    # ------------------------------------------------------------------
    #: Verbatim research disclaimers (spec §38) served with every structural
    #: payload so API consumers see them next to the numbers.
    DISCLAIMERS = [
        "The recommendation graph represents observed recommendation "
        "relationships between videos. These relationships do not directly "
        "represent viewer beliefs, social relationships, ideological "
        "agreement, or causation.",
        "Standard network metrics describe structural properties of the "
        "observed recommendation graph. They should not be interpreted "
        "individually as proof of an Echo Chamber.",
        "The Custom Lens Score is a researcher-defined index combining "
        "selected structural signals. Its weights are methodological choices "
        "made for this project and are not adopted from a universally "
        "validated Echo Chamber index.",
        "A strong structural signal does not by itself establish content "
        "homophily, shared beliefs, or psychological effects on viewers.",
    ]

    def _family_graph(self, family_run_ids: list[str]) -> nx.DiGraph:
        """Directed graph over unique stored crawl pairs (dedup policy §5.2)."""
        rows = self._analytics.edges(run_ids=family_run_ids) if family_run_ids else []
        graph = sm.build_graph(
            (row.source_video_id, row.recommended_video_id) for row in rows
        )
        return graph

    def _family_edge_rows(self, family_run_ids: list[str]):
        return self._analytics.edges(run_ids=family_run_ids) if family_run_ids else []

    def _channel_pairs(self, rows) -> list[tuple[str, str]]:
        """Channel->Channel projection rule (§18): video edge A(vX)->B(vY)
        becomes (channel(X), channel(Y)); edges whose either endpoint's
        channel is unresolvable are DROPPED and counted - never invented."""
        channel_map = self._video_channel_map()
        pairs: list[tuple[str, str]] = []
        self._unattributed_edges = 0
        for row in rows:
            source = channel_map.get(row.source_video_id)
            target = channel_map.get(row.recommended_video_id) or getattr(
                row, "channel_id", None
            )
            if not source or not target:
                self._unattributed_edges += 1
                continue
            pairs.append((source, target))
        return pairs

    def structure(self, detection_id: str) -> dict[str, Any]:
        """Full structural analysis (spec §37 sections) from stored edges.

        VIDEO LENS: standard stats / community structure / reinforcement
        (+ null model + persistence) / centrality. CHANNEL LENS: channel
        network + concentration (HHI). Every metric carries the §36
        metadata envelope; unavailable data never becomes a silent 0.
        """
        detection = self.get_detection(detection_id)
        if detection is None:
            raise KeyError(f"Echo detection {detection_id} not found")
        family = self._family_layers(detection.seed_run_id)
        family_run_ids = [rid for layer in family for rid in (layer.run_ids or [])]
        self._lens_channel_map = self._video_channel_map()
        try:
            rows = self._family_edge_rows(family_run_ids)
            graph = sm.build_graph(
                (r.source_video_id, r.recommended_video_id) for r in rows
            )

            # Per-layer unique directed pairs for community persistence (§15).
            per_layer: dict[int, list[tuple[str, str]]] = {}
            for row in rows:
                per_layer.setdefault(row.layer_index or 0, []).append(
                    (row.source_video_id, row.recommended_video_id)
                )
            layer_edges = sorted(per_layer.items())

            # Channel lens projection (§18).
            channel_pairs = self._channel_pairs(rows)
            channel_graph = sm.build_graph(channel_pairs)
            weighted_in: dict[str, int] = {}
            total_attributed = len(channel_pairs)
            for src, tgt in channel_pairs:
                weighted_in[tgt] = weighted_in.get(tgt, 0) + 1
            unattributed = getattr(self, "_unattributed_edges", 0)

            wcr_env = sm.within_community_rate(graph)
            null_payload: dict[str, Any]
            if wcr_env["value"] is None:
                null_payload = {
                    "metric": "within_community_recommendation_rate_null_model",
                    "status": sm.STATUS_UNAVAILABLE,
                    "detail": {"reason": "observed WCR unavailable"},
                }
            else:
                null_payload = sm.null_model_wcr(graph)

            payload = {
                "detection_id": detection.detection_id,
                "seed_run_id": detection.seed_run_id,
                "family_run_count": len(family),
                "computed_at": utcnow().isoformat(),
                "disclaimers": list(self.DISCLAIMERS),
                "video_lens": {
                    "lens": "video",
                    "network_statistics": sm.standard_statistics(graph),
                    "community_structure": sm.community_structure(
                        graph, seed_video_id=detection.seed_video_id
                    ),
                    "reinforcement": {
                        "within_community_recommendation_rate": wcr_env,
                        "null_model": null_payload,
                        "community_persistence": sm.community_persistence(
                            layer_edges, seed_video_id=detection.seed_video_id
                        ),
                    },
                    "centrality": sm.centrality_metrics(graph),
                },
                "channel_lens": {
                    "lens": "channel",
                    "projection_rule": (
                        "Video edge A(vX)->B(vY) projects to channel(X)->"
                        "channel(Y); repeated video edges between the same "
                        "channels collapse to ONE unique channel edge here "
                        "(weighted activity counted separately below); edges "
                        "with an unresolvable endpoint channel are dropped."
                    ),
                    "network": sm.standard_statistics(channel_graph),
                    "unattributed_edges": sm.envelope(
                        "channel_unattributed_edges",
                        unattributed,
                        category="standard_statistic",
                        lens="channel",
                        definition=(
                            "video edges dropped from the channel projection "
                            "because an endpoint's channel was unresolvable"
                        ),
                    ),
                    "concentration": sm.channel_concentration(weighted_in),
                    "weighted_activity_total": sm.envelope(
                        "channel_weighted_activity_total",
                        total_attributed,
                        category="standard_statistic",
                        lens="channel",
                    ),
                },
            }
        finally:
            self._lens_channel_map = None
        return payload

    def audience(self, detection_id: str) -> dict[str, Any]:
        """Audience/commenter lens (§22): Jaccard overlap within/between the
        detected communities of the crawl-family graph.

        Available ONLY where commenter identities exist; missing comment data
        yields ``status="unavailable"`` - never a fabricated zero.
        """
        detection = self.get_detection(detection_id)
        if detection is None:
            raise KeyError(f"Echo detection {detection_id} not found")
        family = self._family_layers(detection.seed_run_id)
        family_run_ids = [rid for layer in family for rid in (layer.run_ids or [])]

        def _env(metric, value, **kw):
            return sm.envelope(metric, value, lens="audience", **kw)

        base = {
            "detection_id": detection.detection_id,
            "computed_at": utcnow().isoformat(),
            "disclaimers": list(self.DISCLAIMERS),
            "commenter_overlap": {
                "jaccard_mean": _env("jaccard_mean", None, category="audience"),
                "within_community_jaccard_mean": _env(
                    "within_community_jaccard_mean", None, category="audience"
                ),
                "between_community_jaccard_mean": _env(
                    "between_community_jaccard_mean", None, category="audience"
                ),
                "videos_with_commenters": _env(
                    "videos_with_commenters", 0, category="audience"
                ),
                "status": sm.STATUS_UNAVAILABLE,
                "reason": "not evaluated yet",
            },
        }
        graph = self._family_graph(family_run_ids)
        communities = sm.detect_communities(graph)
        assignment: dict[str, int] = {}
        for idx, comm in enumerate(communities):
            for node in comm:
                assignment[node] = idx

        commenter_sets: dict[str, set[str]] = {}
        for node in graph.nodes:
            members = self._commenters(node)
            if members:
                commenter_sets[node] = members
        block = base["commenter_overlap"]
        block["videos_with_commenters"] = _env(
            "videos_with_commenters", len(commenter_sets), category="audience"
        )
        if not commenter_sets:
            block["reason"] = (
                "no collected comments with resolvable author identities on "
                "any crawled video"
            )
            return base

        within: list[float] = []
        between: list[float] = []
        pair_count = 0
        videos = sorted(commenter_sets)
        for i, a in enumerate(videos):
            for b in videos[i + 1 :]:
                union = commenter_sets[a] | commenter_sets[b]
                jaccard = (
                    round(len(commenter_sets[a] & commenter_sets[b]) / len(union), 6)
                    if union
                    else None
                )
                if jaccard is None:
                    continue
                pair_count += 1
                if assignment.get(a) is not None and assignment.get(a) == assignment.get(b):
                    within.append(jaccard)
                else:
                    between.append(jaccard)

        all_values = within + between
        block["pair_count"] = pair_count
        block["within_pair_count"] = len(within)
        block["between_pair_count"] = len(between)
        block["jaccard_mean"] = _env(
            "jaccard_mean",
            round(sum(all_values) / len(all_values), 6) if all_values else None,
            category="audience",
            numerator=round(sum(all_values), 6) if all_values else None,
            denominator=len(all_values) or None,
        )
        block["within_community_jaccard_mean"] = _env(
            "within_community_jaccard_mean",
            round(sum(within) / len(within), 6) if within else None,
            category="audience",
            numerator=round(sum(within), 6) if within else None,
            denominator=len(within) or None,
        )
        block["between_community_jaccard_mean"] = _env(
            "between_community_jaccard_mean",
            round(sum(between) / len(between), 6) if between else None,
            category="audience",
            numerator=round(sum(between), 6) if between else None,
            denominator=len(between) or None,
        )
        if not all_values:
            block["status"] = sm.STATUS_UNAVAILABLE
            block["reason"] = "no comparable video pairs with commenters"
        else:
            block["status"] = sm.STATUS_AVAILABLE
            block.pop("reason", None)
        return base

    # ------------------------------------------------------------------
    # Score
    # ------------------------------------------------------------------
    def _score_for(self, detection: EchoDetection) -> dict[str, Any] | None:
        """Composite score from the LATEST value of every signal."""
        latest_signals = (
            detection.layers[-1].get("signals") if detection.layers else None
        )
        keys = ("s1", "s2", "s3", "s4", "s5")
        if latest_signals is None:
            signals = {key: None for key in keys}
        else:
            signals = {key: latest_signals.get(key, {}).get("value") for key in keys}
        return compute_score(signals, computed_at=utcnow())

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _save(self, detection: EchoDetection) -> None:
        self._repos.echo_detections.save_detection(detection)

    def _require_detection(self, detection_id: str) -> EchoDetection:
        detection = self.get_detection(detection_id)
        if detection is None:
            raise KeyError(f"Echo detection {detection_id} not found")
        return detection
