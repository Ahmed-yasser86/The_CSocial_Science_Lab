"""Recommendation observation workflow.

Collects the recommendations observable around a source video *to the extent
the selected library supports it*, persists them as observed relationships
(never as permanent properties), and records an explicit
``RECOMMENDATION_UNSUPPORTED`` error when the library cannot provide them.

yt-dlp does not expose recommendations reliably, so by default this workflow
correctly yields an unsupported status rather than fabricating edges.

Network-tab entry points
------------------------
* ``collect_recommendations`` - single-video scrape (click-to-scrape from a
  graph node). Accepts an optional ``video_id`` (reuses the persisted source
  video instead of re-fetching it) and ``parent_run_id`` (the run whose node
  started the scrape).
* ``collect_recommendations_for_videos`` - bulk depth-1 scrape for a set of
  source videos (re-scrape a run / a channel from the network tab). One
  ``RunType.RECOMMENDATION`` run per video so temporal slices stay
  meaningful; network work runs concurrently under ONE shared rate limiter.

Every run records ``parent_run_id`` and a ``config_json["trigger"]`` marker
for provenance, and its observed edges are auto-persisted as a run-scoped
dataset with lineage (``Dataset.source_projection["lineage"]``).
"""

from __future__ import annotations

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from SocialScienceResearch.acquisition import (
    AcquisitionError,
    AcquisitionProvider,
    RecommendationUnsupportedError,
)
from SocialScienceResearch.acquisition.normalization import (
    normalize_channel,
    normalize_recommendations,
    normalize_video,
    normalize_video_observation,
)
from SocialScienceResearch.domain.enums import (
    CollectionStatus,
    EntityType,
    ErrorType,
    RunType,
)
from SocialScienceResearch.utils.logger import get_logger

from .collection_service import CollectionService, ProgressReporter, _RateLimiter
from .network_analytics_service import NetworkAnalyticsService
from .recommendation_graph_service import RecommendationGraphService
from .results import CollectionResult

logger = get_logger(__name__)


def _watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


class RecommendationService(CollectionService):
    """Extends the collection service with recommendation observation runs."""

    # ------------------------------------------------------------------
    def collect_recommendations(
        self,
        video_url: str | None = None,
        *,
        video_id: str | None = None,
        parent_run_id: str | None = None,
        dedupe_run_ids: list[str] | None = None,
        layer_index: int | None = None,
        max_recommendations_per_video: int | None = None,
        reporter: ProgressReporter | None = None,
    ) -> CollectionResult:
        """Collect the source video plus its observable recommendations.

        Backwards compatible: ``video_url`` alone works (legacy callers). When
        ``video_id`` is supplied and the video is already persisted, the source
        video is reused instead of re-fetched; otherwise it is extracted and
        persisted. ``parent_run_id`` records the run that triggered this scrape
        and ``dedupe_run_ids`` skips edges already observed by those runs.
        ``layer_index`` stamps the run (and its edges) with a crawl layer, or
        ``None`` for layer-agnostic scrapes. ``max_recommendations_per_video``
        keeps only the top-N observed edges (by feed position) for this run.
        """
        if not video_url and video_id:
            existing = self._repos.videos.get_video(video_id)
            video_url = existing.url if existing else _watch_url(video_id)
        if not video_url:
            raise ValueError("video_url or video_id is required")

        run = self._begin_recommendation_run(
            video_url, parent_run_id, "node_click", layer_index=layer_index
        )
        errors: list = []

        # 1. Resolve the source video (its id anchors edges).
        video = self._repos.videos.get_video(video_id) if video_id else None
        if video is None:
            try:
                info = self._provider.extract_video(video_url)
            except AcquisitionError as exc:
                self._record_error(run, EntityType.VIDEO, None, exc.error_type, str(exc))
                self._finish_run(
                    run, CollectionStatus.FAILED, errors,
                    discovered=1, succeeded=0, entities_existing=0, comments_collected=0, failed=1
                )
                return self._result(run, errors)

            video = normalize_video(info, run.run_id)
            if video is None:
                self._record_error(
                    run,
                    EntityType.VIDEO,
                    None,
                    ErrorType.VALIDATION,
                    "Could not resolve a video id for the recommendation source.",
                )
                self._finish_run(
                    run, CollectionStatus.FAILED, errors,
                    discovered=1, succeeded=0, entities_existing=0, comments_collected=0, failed=1
                )
                return self._result(run, errors)

            self._repos.videos.upsert_video(video)
            obs = normalize_video_observation(info, run.run_id, video.video_id)
            if obs is not None:
                self._repos.videos.save_video_observation(obs)
            run.target_video_id = video.video_id
            self._repos.runs.update_run(run)

        self._report(reporter, "recommendation/start", message=f"Starting recommendation scrape for {video_url}")

        # 2. Attempt recommendation observation.
        payload: dict[str, Any] = {
            "video_id": video.video_id,
            "video": video,
            "raw": None,
            "error": None,
            "unsupported": None,
            "missing": False,
        }
        try:
            payload["raw"] = self._provider.extract_recommendations(
                video.url or video_url
            )
        except RecommendationUnsupportedError as exc:
            payload["unsupported"] = exc
        except AcquisitionError as exc:
            payload["error"] = exc
        return self._complete_video_result(
            run,
            payload,
            channel_id=None,
            dedupe_run_ids=dedupe_run_ids,
            layer_index=layer_index,
            max_recommendations_per_video=max_recommendations_per_video,
            reporter=reporter,
        )

    # ------------------------------------------------------------------
    def collect_recommendations_for_videos(
        self,
        video_ids: list[str],
        *,
        parent_run_id: str | None = None,
        channel_id: str | None = None,
        dedupe_run_ids: list[str] | None = None,
        dedupe_all_history: bool = False,
        layer_index: int | None = None,
        concurrency: int | None = None,
        max_recommendations_per_video: int | None = None,
        enrich_targets: bool = True,
        reporter: ProgressReporter | None = None,
    ) -> list[CollectionResult]:
        """Bulk depth-1 recommendation scrape for a set of source videos.

        Creates one :class:`RunType.RECOMMENDATION` run per video (lineage via
        ``parent_run_id``), network work running concurrently under ONE shared
        rate limiter. Returns one result per source video, ordered by input.
        A single video's failure never aborts its siblings. ``layer_index``
        stamps each run (and its edges) with a crawl layer, or ``None`` for
        layer-agnostic scrapes. ``max_recommendations_per_video`` keeps only
        the top-N observed edges per source feed. ``enrich_targets=False``
        skips the trailing deep-enrichment pass (callers that enrich
        themselves, e.g. the layer crawl, avoid fetching every target twice).

        ``dedupe_run_ids`` skips edges already observed in those runs. When
        ``dedupe_all_history`` is set, edges already observed in ANY previous
        run are skipped as well, so re-scraping a source only ever yields the
        genuinely new recommendations rather than re-saving the same edges
        under a fresh run each time.
        """
        if not video_ids:
            return []
        # Read the mutable runtime config (UI-tunable without restart), not
        # the frozen settings - otherwise the Speed presets never affect the
        # bulk phase that dominates large crawls.
        concurrency = max(1, concurrency or self._enrichment_concurrency())
        throttle = _RateLimiter(self._request_delay())

        # Every bulk scrape is registered as sub-runs under ONE parent (the run
        # that triggered it, or a synthetic anchor run when none is given) so
        # per-video runs are never orphaned and stay visible via the run's
        # sub-runs listing.
        parent_run_id = self._ensure_bulk_parent(
            parent_run_id,
            source_url=_watch_url(video_ids[0]),
            layer_index=layer_index,
        )
        existing_pairs = self._existing_pairs_all() if dedupe_all_history else None

        self._report(
            reporter,
            "recommendation/batch/start",
            discovered=len(video_ids),
            message=f"Scraping recommendations for {len(video_ids)} video(s)",
        )

        results: list[CollectionResult] = []
        pending_targets: dict[str, dict[str, Any]] = {}
        completed = 0
        saved_total = 0
        failed_total = 0
        pool = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="rec")
        try:
            pending_futures: dict = {}
            for video_id in video_ids:
                pending_futures[
                    pool.submit(
                        self._scrape_video_task,
                        video_id,
                        parent_run_id,
                        dedupe_run_ids,
                        existing_pairs,
                        throttle,
                    )
                ] = video_id

            _FUTURE_TIMEOUT = 120
            while pending_futures:
                done, _ = concurrent.futures.wait(
                    pending_futures, timeout=_FUTURE_TIMEOUT,
                )
                if not done:
                    for fut in list(pending_futures):
                        fut.cancel()
                    break
                for future in done:
                    video_id = pending_futures.pop(future)
                    # yt-dlp philosophy: one video's failure must never abort the
                    # whole batch. Skip-and-continue so a single bad URL / network
                    # glitch degrades gracefully instead of 500-ing the crawl.
                    try:
                        payload = future.result()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "recommendation scrape failed for %s, skipping: %s",
                            video_id,
                            exc,
                        )
                        failed_total += 1
                        completed += 1
                        self._report(
                            reporter,
                            "recommendation/batch/progress",
                            discovered=len(video_ids),
                            succeeded=completed,
                            failed=failed_total,
                            message=(
                                f"Scraped {completed}/{len(video_ids)} video(s), "
                                f"{saved_total} edge(s) saved (1 failed)"
                            ),
                        )
                        continue
                    video_id = payload["video_id"]
                    run = self._begin_recommendation_run(
                        _watch_url(video_id),
                        parent_run_id,
                        "run_bulk",
                        layer_index=layer_index,
                    )
                    run.target_video_id = video_id
                    self._repos.runs.update_run(run)
                    result = self._complete_video_result(
                        run,
                        payload,
                        channel_id=channel_id,
                        dedupe_run_ids=dedupe_run_ids,
                        existing_pairs=existing_pairs,
                        layer_index=layer_index,
                        max_recommendations_per_video=max_recommendations_per_video,
                        reporter=reporter,
                        pending_targets=pending_targets,
                    )
                    results.append(result)
                    completed += 1
                    saved_total += result.entities_created
                    failed_total += len(result.errors)
                    # Aggregate progress: each video's _complete_video_result
                    # reports its own per-video counts, so we re-assert the
                    # running totals here. Without this the banner only ever
                    # reflects a single video's "complete" snapshot.
                    self._report(
                        reporter,
                        "recommendation/batch/progress",
                        discovered=len(video_ids),
                        succeeded=completed,
                        failed=failed_total,
                        message=(
                            f"Scraped {completed}/{len(video_ids)} video(s), "
                            f"{saved_total} edge(s) saved"
                        ),
                    )
        finally:
            pool.shutdown(wait=False)

        # Deep-enrich every newly seen recommended target in ONE concurrent
        # pass (not per-video), so a big network never looks stalled on the
        # first video: the bulk loop only saved edges + runs above. Best-effort:
        # a failure here must not undo the edges/runs already persisted above.
        # Callers that run their own enrichment pass right after (the layer
        # crawl, which also collects comments) set ``enrich_targets=False`` so
        # targets are fetched exactly once instead of twice.
        if pending_targets and enrich_targets:
            try:
                # Bound the heavy per-video enrichment (full stats + comments)
                # so a fan-out over hundreds of recommendations completes in
                # predictable time instead of hanging on a degraded yt-dlp.
                # Edges are already saved for every recommendation; only the
                # deep enrichment is capped. 0 = unlimited.
                cap = self._max_enrich_targets()
                targets = pending_targets
                if cap and len(targets) > cap:
                    targets = dict(list(pending_targets.items())[:cap])
                    logger.info(
                        "Capping deep-enrichment to %d of %d recommended targets "
                        "for this scrape (raise max_enrich_targets to enrich more)",
                        cap,
                        len(pending_targets),
                    )
                self._enrich_recommended_targets(targets)
            except Exception as exc:  # noqa: BLE001
                logger.warning("deep-enrichment pass failed, continuing: %s", exc)

        results.sort(
            key=lambda r: video_ids.index(r.target_id)
            if r.target_id in video_ids
            else len(video_ids)
        )
        # All per-video edges are persisted by now; invalidate the cached
        # recommendation graph so the bulk-scraped edges surface in the UI.
        RecommendationGraphService.clear_graph_cache()
        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _max_enrich_targets(self) -> int:
        """Cap on deep-enriched target videos for this scrape (0 = unlimited)."""
        if (
            self._runtime_config is not None
            and getattr(self._runtime_config, "max_enrich_targets", None) is not None
        ):
            return self._runtime_config.max_enrich_targets
        return self._settings.scraper.max_enrich_targets

    def _scrape_video_task(
        self,
        video_id: str,
        parent_run_id: str | None,
        dedupe_run_ids: list[str] | None,
        existing_pairs: set[tuple[str, str]] | None,
        throttle: _RateLimiter,
    ) -> dict[str, Any]:
        """Worker-thread network phase for one video.

        Only the slow network calls run here (rate-limited). Persistence and
        run bookkeeping happen on the caller thread via
        :meth:`_complete_video_result`.

        The source video does NOT need a persisted ``Video`` row: a video may
        exist only as a graph node (e.g. a recommended target that was never
        deep-enriched). When missing, the raw info is resolved and returned in
        ``source_info`` so the caller can persist it; recommendations are
        scraped by watch URL regardless. A failed source resolution never
        aborts the recommendation scrape.
        """
        video = self._repos.videos.get_video(video_id)
        payload: dict[str, Any] = {
            "video_id": video_id,
            "video": video,
            "source_info": None,
            "raw": None,
            "error": None,
            "unsupported": None,
            "missing": video is None,
        }
        if video is None:
            try:
                throttle.wait()
                payload["source_info"] = self._provider.extract_video(
                    _watch_url(video_id)
                )
                payload["missing"] = False
            except AcquisitionError:
                pass
        try:
            throttle.wait()
            payload["raw"] = self._provider.extract_recommendations(
                video.url if video else _watch_url(video_id)
            )
            payload["missing"] = False
        except RecommendationUnsupportedError as exc:
            payload["unsupported"] = exc
        except AcquisitionError as exc:
            payload["error"] = exc
        return payload

    def _complete_video_result(
        self,
        run,
        payload: dict[str, Any],
        *,
        channel_id: str | None,
        dedupe_run_ids: list[str] | None,
        existing_pairs: set[tuple[str, str]] | None = None,
        layer_index: int | None = None,
        max_recommendations_per_video: int | None = None,
        reporter: ProgressReporter | None,
        pending_targets: dict[str, dict[str, Any]] | None = None,
    ) -> CollectionResult:
        """Persist one video's recommendation outcome + run + dataset.

        Shared by single-video (click-to-scrape) and bulk paths. ``run`` is
        already begun with its ``target_video_id`` and lineage set.
        ``layer_index`` stamps each saved edge with the producing crawl layer.
        ``max_recommendations_per_video`` truncates the observed feed to the
        top-N edges (by position) before persistence. ``pending_targets``
        (bulk path) collects the recommended targets to deep-enrich in ONE
        concurrent pass after the loop, so enrichment never blocks the loop on
        the first video. ``existing_pairs`` (from ``dedupe_all_history``)
        additionally skips edges already observed in any earlier run.
        """
        errors: list = []
        video_id = payload["video_id"]

        # The source video existed only as a graph node (never deep-enriched).
        # Best-effort: persist it now that we have its raw info, so edges
        # anchor to a real Video row and the graph gains proper metadata. A
        # persistence failure never fails the run (edges anchor by id anyway).
        source_info = payload.get("source_info")
        if source_info is not None and payload["video"] is None:
            try:
                normalized = normalize_video(source_info, run.run_id)
                if normalized is not None:
                    self._repos.videos.upsert_video(normalized)
                    obs = normalize_video_observation(
                        source_info, run.run_id, normalized.video_id
                    )
                    if obs is not None:
                        self._repos.videos.save_video_observation(obs)
                    payload["video"] = normalized
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to persist source video %s for run %s: %s",
                    video_id,
                    run.run_id,
                    exc,
                )

        if payload["missing"]:
            err = self._record_error(
                run,
                EntityType.RECOMMENDATION,
                video_id,
                ErrorType.VALIDATION,
                "Source video is not persisted; cannot scrape recommendations.",
            )
            errors.append(err)
            self._finish_run(
                run, CollectionStatus.FAILED, errors,
                discovered=1, succeeded=0, entities_existing=0, comments_collected=0, failed=1
            )
            result = self._result(run, errors)
            result.entities_created = 0
            return result

        if payload["unsupported"] is not None:
            exc = payload["unsupported"]
            err = self._record_error(
                run,
                EntityType.RECOMMENDATION,
                video_id,
                exc.error_type,
                str(exc),
                retryable=False,
            )
            errors.append(err)
            self._finish_run(
                run, CollectionStatus.PARTIAL, errors,
                discovered=1, succeeded=0, entities_existing=0, comments_collected=0, failed=1
            )
            result = self._result(run, errors)
            result.entities_created = 0
            return result

        if payload["error"] is not None:
            exc = payload["error"]
            err = self._record_error(
                run,
                EntityType.RECOMMENDATION,
                video_id,
                exc.error_type,
                str(exc),
            )
            errors.append(err)
            self._finish_run(
                run, CollectionStatus.PARTIAL, errors,
                discovered=1, succeeded=0, entities_existing=0, comments_collected=0, failed=1
            )
            result = self._result(run, errors)
            result.entities_created = 0
            return result

        self._report(
            reporter,
            "recommendation/extracting",
            message="Extracting recommendations...",
        )
        edges = normalize_recommendations(
            video_id, payload["raw"], run.run_id
        )
        for edge in edges:
            edge.layer_index = layer_index
        if max_recommendations_per_video is not None:
            edges = sorted(
                edges,
                key=lambda e: e.position if e.position is not None else float("inf"),
            )
            if len(edges) > max_recommendations_per_video:
                self._report(
                    reporter,
                    "recommendation/top_n",
                    discovered=len(edges),
                    message=(
                        f"Keeping top {max_recommendations_per_video} of "
                        f"{len(edges)} recommendation(s) for {video_id}"
                    ),
                )
                edges = edges[:max_recommendations_per_video]
        if dedupe_run_ids or existing_pairs:
            existing: set[tuple[str, str]] = set(existing_pairs or ())
            if dedupe_run_ids:
                existing |= self._existing_pairs(dedupe_run_ids)
            kept = [
                e
                for e in edges
                if (e.source_video_id, e.recommended_video_id) not in existing
            ]
            if len(kept) != len(edges):
                self._report(
                    reporter,
                    "recommendation/dedup",
                    succeeded=len(kept),
                    message=(
                        f"skipped {len(edges) - len(kept)} edge(s) already "
                        "observed in an earlier run"
                    ),
                )
            edges = kept

        self._report(
            reporter,
            "recommendation/edges_found",
            discovered=len(edges),
            message=f"Found {len(edges)} recommendations",
        )
        saved = []
        for edge in edges:
            result = self._repos.recommendations.save_recommendation(edge)
            if result.created:
                saved.append(edge)

        # This source video's recommendation feed has now been scraped (even if
        # nothing new was saved, the snapshot was observed). Kept as a flag so
        # graph expansion can distinguish already-scraped nodes from
        # target-only nodes that were never expanded.
        self._repos.videos.mark_recommendations_scraped(video_id)

        if pending_targets is not None:
            # Bulk path: defer enrichment - merge this video's new targets into
            # the shared accumulator (enriched once after the whole loop).
            targets = self._collect_recommendation_targets(edges, run)
            for video_id, marker in targets.items():
                pending_targets[video_id] = marker
        else:
            # Single-video path: enrich on the spot (this run only).
            self._persist_recommended_targets(edges, run)

        dataset_id = self._persist_run_dataset(
            run,
            saved,
            channel_id=channel_id,
            layer_index=layer_index,
            reporter=reporter,
        )

        status = CollectionStatus.PARTIAL if errors else CollectionStatus.SUCCESS
        self._finish_run(
            run,
            status,
            errors,
            discovered=len(edges) + 1,
            succeeded=len(edges),
            entities_existing=0,
            comments_collected=0,
            failed=len(errors),
        )
        result = self._result(run, errors)
        result.entities_created = len(saved)
        result.dataset_id = dataset_id
        self._report(
            reporter,
            "recommendation/complete",
            succeeded=len(saved),
            message=f"Recommendation scrape complete: {len(saved)} edge(s) saved",
        )
        logger.info(
            "recommendation run %s: %d edge(s) for source %s",
            run.run_id,
            len(saved),
            video_id,
        )
        # Invalidate the cached recommendation graph so the freshly scraped
        # edges become visible to the network-tab UI immediately. Without this,
        # build_graph() keeps serving the stale (often empty) pre-scrape graph
        # for the whole corpus (300s TTL) and forever for run-scoped slices.
        RecommendationGraphService.clear_graph_cache()
        NetworkAnalyticsService.clear_analytics_cache()
        return result

    def _begin_recommendation_run(
        self,
        target_url: str,
        parent_run_id: str | None,
        source_kind: str,
        layer_index: int | None = None,
    ):
        """Begin a recommendation run with provenance (parent + trigger).

        ``layer_index`` stamps the run with a crawl layer and records it in the
        trigger's ``depth``; ``None`` (legacy callers) keeps ``depth=1``.
        """
        run = self._begin_run(RunType.RECOMMENDATION, target_url)
        run.parent_run_id = parent_run_id
        run.layer_index = layer_index
        run.config_json["trigger"] = {
            "kind": source_kind,
            "parent_run_id": parent_run_id,
            "depth": layer_index if layer_index is not None else 1,
        }
        self._repos.runs.update_run(run)
        return run

    def _ensure_bulk_parent(
        self,
        parent_run_id: str | None,
        *,
        source_url: str,
        layer_index: int | None,
    ) -> str | None:
        """Resolve the parent run a bulk scrape's sub-runs register under.

        When the caller already supplies a parent run id it is used as-is;
        otherwise a synthetic anchor run is created so every per-video run is
        registered as a sub-run (never an orphan) and the anchor shows up in
        the runs ledger as the bulk operation's parent.
        """
        if parent_run_id is not None:
            return parent_run_id
        try:
            anchor = self._begin_recommendation_run(
                source_url,
                None,
                "run_bulk_anchor",
                layer_index=layer_index,
            )
            self._finish_run(
                anchor,
                CollectionStatus.SUCCESS,
                [],
                discovered=0,
                succeeded=0,
                notes=["Anchor run grouping a bulk recommendation scrape."],
            )
            return anchor.run_id
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Could not create bulk anchor run; sub-runs will be top-level: %s",
                exc,
            )
            return None

    def _existing_pairs(self, run_ids: list[str]) -> set[tuple[str, str]]:
        """(source, target) pairs already observed in the given runs."""
        pairs: set[tuple[str, str]] = set()
        for run_id in run_ids:
            for edge in self._repos.recommendations.list_recommendation_edges(
                run_id=run_id
            ):
                pairs.add((edge.source_video_id, edge.recommended_video_id))
        return pairs

    def _existing_pairs_all(self) -> set[tuple[str, str]]:
        """Every (source, target) pair observed across ALL runs.

        Used by ``dedupe_all_history`` so a re-scrape of a source only saves
        edges that have never been seen before, instead of re-persisting the
        same edges under a fresh run each time.
        """
        pairs: set[tuple[str, str]] = set()
        for edge in self._repos.recommendations.list_recommendation_edges():
            pairs.add((edge.source_video_id, edge.recommended_video_id))
        return pairs

    def _persist_run_dataset(
        self,
        run,
        edges: list,
        *,
        channel_id: str | None,
        layer_index: int | None = None,
        reporter: ProgressReporter | None,
    ) -> str | None:
        """Auto-persist the run's observed edges as a scoped dataset.

        The dataset is scoped to this recommendation run (``run_ids`` is now
        honored for recommendation rows) and records machine-queryable lineage
        (trigger run, parent run, source kind). When ``layer_index`` is set the
        name and lineage carry the crawl layer. A persistence failure is logged
        and never fails the collection run.
        """
        if not edges:
            return None
        try:
            from SocialScienceResearch.services.dataset_service import DatasetService

            dataset_service = DatasetService(self._repos)
            trigger_run_id = run.parent_run_id or run.run_id
            source_kind = (run.config_json.get("trigger") or {}).get("kind", "single")
            if layer_index is not None:
                name = (
                    f"Recommendation Layer {layer_index} - source {trigger_run_id}"
                )
                description = (
                    f"Auto-persisted layer {layer_index} recommendation edges for "
                    f"run {run.run_id} of {run.target_video_id or 'video'}; "
                    f"triggered by {trigger_run_id} ({source_kind}); "
                    f"{len(edges)} edge(s)."
                )
                lineage = {
                    "trigger_run_id": trigger_run_id,
                    "parent_run_id": run.parent_run_id,
                    "source_kind": source_kind,
                    "layer_index": layer_index,
                    "depth": layer_index,
                }
            else:
                name = (
                    f"Recommendation Run {run.run_id} - {run.target_video_id or 'video'} "
                    f"[source {trigger_run_id}]"
                )
                description = (
                    f"Auto-persisted dataset for recommendation run {run.run_id} "
                    f"of {run.target_video_id or 'video'}; triggered by "
                    f"{trigger_run_id} ({source_kind}); {len(edges)} edge(s)."
                )
                lineage = {
                    "trigger_run_id": trigger_run_id,
                    "parent_run_id": run.parent_run_id,
                    "source_kind": source_kind,
                    "depth": 1,
                }
            dataset = dataset_service.create_dataset(
                name=name,
                description=description,
                entity_type="recommendation",
                include_raw=False,
                run_ids=[run.run_id],
                channel_ids=[channel_id] if channel_id else None,
                video_ids=[run.target_video_id] if run.target_video_id else None,
                member_ids=[e.recommended_video_id for e in edges],
                criteria=None,
                variable_selection=None,
                lineage=lineage,
            )
            self._report(
                reporter,
                "recommendation/dataset_persisted",
                message="Persisted recommendation results as a dataset",
            )
            return dataset.dataset_id
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to auto-persist recommendation run %s as dataset: %s",
                run.run_id,
                exc,
            )
            return None

    def _persist_recommended_targets(self, edges: list, run) -> None:
        """Persist recommended target videos as Video rows (if missing).

        Recommended targets normally exist only as graph edges. Persisting them
        as ``Video`` rows (marked as recommendations with provenance in
        ``raw_json``) makes them visible in the run's Videos tab, the corpus
        and the record explorer, while the edge table keeps the temporal
        observation.

        New targets (no ``Video`` row yet, or a recommendation stub) are
        deep-enriched on the spot -- concurrently under one shared rate
        limiter -- so the corpus carries full metadata + engagement stats
        instead of "Not observed" placeholders. The ``_discovery`` marker is
        preserved so the UI's "recommended" badge and the layer-scrape stub
        logic keep working. A target whose extraction/validation fails is not
        left as a broken stub (it is dropped when a stub existed) and stays
        discoverable via recommendation edges only. Existing full videos are
        never re-fetched (their provenance is preserved, never overwritten).
        """
        try:
            targets = self._collect_recommendation_targets(edges, run)
            if targets:
                self._enrich_recommended_targets(targets)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to persist recommended target videos for run %s: %s",
                run.run_id,
                exc,
            )

    def _collect_recommendation_targets(
        self, edges: list, run
    ) -> dict[str, dict[str, Any]]:
        """Build the target-enrichment map for a run's edges (no network work).

        For each edge whose target is missing or a true stub, records the
        ``_discovery`` marker the enriched row will carry. Already-enriched
        recommendation videos are excluded so their provenance (the run that
        first observed them) is never rewritten by a later scrape.
        """
        targets: dict[str, dict[str, Any]] = {}
        for edge in edges:
            target_id = edge.recommended_video_id
            raw = dict(edge.raw_json or {})
            raw["_discovery"] = {
                "kind": "recommendation",
                "source_video_id": edge.source_video_id,
                "position": edge.position,
                "run_id": run.run_id,
                "stub": True,
            }
            if target_id in targets:
                targets[target_id] = raw  # last edge wins for the marker
                continue
            existing = self._repos.videos.get_video(target_id)
            if existing is not None and not self._is_recommendation_stub(
                existing
            ):
                continue  # already a full video - never re-fetch it
            targets[target_id] = raw
        return targets

    @staticmethod
    def _is_recommendation_stub(video) -> bool:
        """True when a Video row is a *true* recommendation stub.

        Only placeholder rows created before deep-enrichment (``_discovery
        {"kind": "recommendation", "stub": True}``) qualify. A video that was
        already deep-enriched carries ``stub: False``, so it is treated as a
        full video and never re-fetched (and its ``first_observed_run_id`` is
        never overwritten by a later scrape).
        """
        discovery = (video.raw_json or {}).get("_discovery")
        return (
            isinstance(discovery, dict)
            and discovery.get("kind") == "recommendation"
            and discovery.get("stub") is True
        )

    def _drop_recommendation_stub(self, video_id: str) -> None:
        """Delete a recommendation stub whose deep-enrichment failed.

        Only stubs are removed -- an already enriched video is left intact --
        so a failed target reverts to a graph-node-only entity (discoverable
        through edges, never a "Not observed" corpus row).
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

    def _fetch_target_video(
        self, video_id: str, throttle: _RateLimiter
    ) -> dict[str, Any]:
        """Network phase for deep-enriching one recommended target.

        Runs on a worker thread: only the rate-limited ``extract_video`` call
        happens here; persistence and error recording stay on the caller
        thread so the store is never written concurrently.
        """
        try:
            throttle.wait()
            info = self._provider.extract_video(_watch_url(video_id))
        except AcquisitionError as exc:
            return {"video_id": video_id, "info": None, "error": exc}
        return {"video_id": video_id, "info": info, "error": None}

    def _enrich_recommended_targets(
        self,
        targets: dict[str, dict[str, Any]],
    ) -> None:
        """Deep-enrich recommended targets concurrently (one shared limiter).

        For every target that is missing or a stub, runs one ``extract_video``
        under the shared throttle and persists ``Video`` + ``VideoObservation``
        + ``Channel`` (mirroring the layer-scrape ``_enrich_new_targets``
        pattern). The ``_discovery`` marker recorded for the target is merged
        back into the enriched row (with ``stub: False``, so the video is
        recognised as a full recommendation, not a re-fetchable placeholder)
        keeping the "recommended" badge working. A target that already has a
        ``Video`` row keeps its original ``first_observed_run_id`` -- a later
        scrape never rewrites which run first observed it. A failed target
        never leaves a broken stub behind.
        """
        concurrency = max(1, self._enrichment_concurrency())
        throttle = _RateLimiter(self._request_delay())
        pool = ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="rec-enrich"
        )
        try:
            pending_futures: dict = {}
            for video_id in targets:
                pending_futures[
                    pool.submit(self._fetch_target_video, video_id, throttle)
                ] = video_id

            _FUTURE_TIMEOUT = 120
            while pending_futures:
                done, _ = concurrent.futures.wait(
                    pending_futures, timeout=_FUTURE_TIMEOUT,
                )
                if not done:
                    for fut in list(pending_futures):
                        fut.cancel()
                    break
                for future in done:
                    video_id = pending_futures.pop(future)
                    try:
                        result = future.result()
                    except Exception:  # noqa: BLE001
                        continue
                    video_id = result["video_id"]
                    marker = targets[video_id]["_discovery"]
                    run_id = marker.get("run_id")
                    if result["error"] is not None:
                        logger.warning(
                            "Failed to deep-enrich recommended target %s (run %s): %s",
                            video_id,
                            run_id,
                            result["error"],
                        )
                        self._drop_recommendation_stub(video_id)
                        continue
                    video = normalize_video(result["info"], run_id)
                    if video is None:
                        logger.warning(
                            "Could not resolve a video id for recommended target %s "
                            "(run %s); dropping any stub",
                            video_id,
                            run_id,
                        )
                        self._drop_recommendation_stub(video_id)
                        continue
                    # A target that already exists keeps its original provenance:
                    # the run that FIRST observed it, never the run that re-scraped.
                    existing = self._repos.videos.get_video(video_id)
                    if (
                        existing is not None
                        and existing.first_observed_run_id is not None
                    ):
                        video.first_observed_run_id = existing.first_observed_run_id
                    marker = {**marker, "stub": False}
                    video.raw_json = {**video.raw_json, "_discovery": marker}
                    self._repos.videos.upsert_video(video)
                    obs = normalize_video_observation(
                        result["info"], run_id, video.video_id
                    )
                    if obs is not None:
                        self._repos.videos.save_video_observation(obs)
                    channel = normalize_channel(result["info"], run_id)
                    if channel is not None:
                        self._repos.channels.upsert_channel(channel)
        finally:
            pool.shutdown(wait=False)