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
        reinforced = 0
        for e in edges:
            target = self._repos.videos.get_video(e.recommended_video_id)
            if target is not None and target.channel_id == seed_channel:
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
        detail = {
            "top1": top1,
            "top3": top3,
            "seed_channel_share": seed_share,
            "seed_channel_id": seed_channel,
            "weighted_edge_total": total,
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
