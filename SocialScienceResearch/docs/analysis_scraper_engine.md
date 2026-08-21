# Analysis Spec — Recommendation Scraper Engine (Network Feature Overhaul)

**Owner:** Sub-Agent C (research + pipeline design) · **Scope:** design only, no application code.
**Root:** `SocialScienceResearch`
**Relevant code:** `acquisition/yt_dlp_adapter.py`, `acquisition/normalization.py`, `acquisition/retry.py`, `acquisition/errors.py`, `services/collection_service.py`, `services/recommendation_service.py`, `services/recommendation_graph_service.py`, `services/dataset_service.py`, `services/jobs.py`, `api/app.py`, `api/routers/network_ext.py`, `services/network_analytics_service.py`, `domain/models.py`, `domain/enums.py`, `persistence/base.py`, `ui/src/services/queries.ts`, `ui/src/components/features/ego-network-view.tsx`.

---

## 1. Current pipeline audit

### 1.1 Channel runs
`CollectionService._run_channel_target` (`services/collection_service.py:352`) creates one `CollectionRun` (`RunType.CHANNEL`), calls `provider.extract_channel(channel_url)`, normalizes/persists the channel + a `ChannelObservation`, then `_collect_videos` (`:439`) persists every discovered video (flat entries), and optionally deep-enriches concurrently (`_enrich_and_persist` with a `ThreadPoolExecutor` and a shared `_RateLimiter`). Run lifecycle (`_begin_run`/`_finish_run`/`_record_error`) records per-entity `CollectionError`s and a final status (`success`/`partial`/`failed`).

### 1.2 Recommendation scraping today
- **Inline in channel runs:** `_collect_videos` checks `effective["scrape_recommendations"]` and, per video, calls `_scrape_recommendations_for_video(run, video, errors)` (`collection_service.py:555`). **Design flaw:** the resulting edges are attributed to the **channel run's** `run_id` (`normalize_recommendations(..., run.run_id)`), so a single channel run conflates video entities with observation edges; a temporal slice `build_graph(run_id=channel_run)` then mixes edge types and the channel run's `entities_failed`/`entities_succeeded` counters are polluted with recommendation failures. Rate limiting here is a *new* `_RateLimiter` per call, so it does not share pacing with the concurrent enrichment workers.
- **Single-video runs:** `RecommendationService.collect_recommendations(video_url, reporter)` (`recommendation_service.py:41`) creates a `RunType.RECOMMENDATION` run, extracts the source video (persisting it + a `VideoObservation`), calls `provider.extract_recommendations`, normalizes edges (`normalize_recommendations(video_id, raws, run.run_id)`), saves each via `RecommendationRepository.save_recommendation`, then **auto-persists a dataset** inline and finishes the run. It correctly handles `RecommendationUnsupportedError` (recorded `RECOMMENDATION_UNSUPPORTED`, `retryable=False`, run status `partial`) and never fabricates edges.

### 1.3 Edge persistence + dedup semantics
`save_recommendation` (`persistence/excel_repository.py:338`) upserts by `observation_id`, which is a freshly generated `new_id("obs_rec")` per observation. The model docstring (`domain/models.py:215`) states the tuple `(collection_run_id, source_video_id, recommended_video_id)` is unique, but **there is no cross-run dedup**: a re-scrape under a *new* run writes a *new* row. Within one run the generated ids never collide, so duplicates within a run are also not collapsed. Any bulk design must therefore own its own dedup logic (see §4/§6).

### 1.4 Datasets
`DatasetService.create_dataset` (`services/dataset_service.py:78`) snapshots the **whole** `entity_type` population via `QueryService.resolve_latest_rows`, then narrows by `channel_ids`/`video_ids`/`member_ids`/`criteria`. **Critical:** the docstring and `_register` admit `run_ids` scoping is **not implemented** — `_recommendation_rows` (`query_service.py:334`) lists *all* edges with no run filter. Consequences:
1. The auto-persist in `recommendation_service.py:124-141` and `_persist_graph_as_dataset` both create a dataset that is a **full population snapshot**, not a per-run slice, making the `run_ids=[run.run_id]` argument a lie.
2. `member_ids` filtering uses `_ID_FIELD["recommendation"] = "recommended_video_id"`, so `member_ids` cannot scope by source video.

### 1.5 `_persist_graph_as_dataset` side effect (flag — design flaw)
`RecommendationGraphService.build_graph` (`recommendation_graph_service.py:56`) calls `_persist_graph_as_dataset(graph, run_id)` on **every** build. `build_graph` is invoked by `summary`, `video_context`, and `NetworkAnalyticsService.metrics`/`_slice`/`export_edges` — i.e. a plain **GET read** writes a new `Dataset` row every time the network tab renders metrics or an ego view. This is wasteful, pollutes the dataset ledger with read-traffic snapshots, and couples the read path to the write path. **Fix:** remove the side effect; make dataset persistence an explicit, idempotent, opt-in call (the scraper engine below). Optionally keep `_persist_graph_as_dataset` as a named public method for callers that genuinely want a snapshot.

### 1.6 `NetworkAnalyticsService._get_video_metadata` (flag — violates "never fabricate")
`network_analytics_service.py:296` returns a hard-coded mock dict keyed by sample ids. This injects fabricated titles/channels/views into `EdgeRow`s for the network tab. It must be replaced by the real `YtDlpAcquisitionProvider.get_video_metadata(video_id)` (`yt_dlp_adapter.py:401`) (or a persisted-metadata fallback), never mock data. Out of scope for this spec's build work, but recorded here because it is in the same Network feature.

### 1.7 Run lineage today
`CollectionRun` (`domain/models.py:39`) has no parent/trigger pointer. A recommendation run's only link to the channel run that produced its source video is incidental (the video's `first_observed_run_id`). Provenance across a channel→recommendation tree is therefore not directly traceable from run records.

---

## 2. Recursive video + recommendation scraping (depth=1 from channel videos)

**Goal:** when a CHANNEL run executes (or a channel is bulk-scraped from the network tab), each discovered source video's top recommendations are scraped (`Video_i -> Recs_1..N`), persisted as edges attributed to their **own** recommendation run(s), deduplicated, rate-limited, and progress-reported through the JobManager.

### 2.1 Lineage model (recommended)
Create **one `RunType.RECOMMENDATION` run per source video**, each with:
- `target_url = https://www.youtube.com/watch?v=<video_id>`, `target_video_id = <video_id>`
- **new field** `parent_run_id: str | None = None` on `CollectionRun` (migration-safe default; schema addition required in `domain/models.py`, `persistence/base.py` row mapping, and `api/schemas.py` `RunPayload`) set to the **channel run id** (or the trigger run for re-scrapes)
- `config_json["trigger"] = {"kind": "channel_collect" | "node_click" | "run_bulk", "parent_run_id": ..., "depth": 1}`
- `name` optional researcher label.

Why one run per video: it reuses the existing `collect_recommendations` code path, keeps `build_graph(run_id=...)` / `/network/temporal` slicing per-video meaningful, and preserves the current UI assumption (`useRuns("recommendation")` lists per-video runs). For very large channels this yields many rows; if that is unacceptable, a single **batch run** per channel is an acceptable alternative (see §2.4) — but per-video runs are the recommended default.

### 2.2 Service surface (extend `RecommendationService`)
Add to `services/recommendation_service.py` (all below are public; private helpers follow the `_` convention):

```python
def collect_recommendations(
    self,
    video_url: str,
    *,
    video_id: str | None = None,        # NEW: accept an id instead of building a URL
    parent_run_id: str | None = None,   # NEW: the triggering run (channel run / node trigger)
    dedupe_run_ids: list[str] | None = None,  # NEW: existing runs whose (source,target) to treat as "already observed"
    reporter: ProgressReporter | None = None,
) -> CollectionResult:
    """Scrape recommendations for one video. Backwards compatible: video_id is
    derived from video_url when omitted (and vice versa). Sets run.parent_run_id
    and config_json['trigger']; auto-persists a scoped dataset (see §5)."""

def collect_recommendations_for_videos(
    self,
    video_ids: list[str],
    *,
    parent_run_id: str | None = None,
    channel_id: str | None = None,
    dedupe_run_ids: list[str] | None = None,
    concurrency: int | None = None,      # defaults to settings.scraper.enrichment_concurrency
    reporter: ProgressReporter | None = None,
) -> list[CollectionResult]:
    """Bulk depth-1 scrape for a set of source videos. Creates one recommendation
    run per video (see 2.4 for the batch-run variant). Network work runs in a
    ThreadPoolExecutor bounded by `concurrency`, paced by ONE shared _RateLimiter;
    persistence + error recording happen on the caller thread. Returns one result
    per source video, ordered by input. Partial failures never abort siblings."""

def _scrape_video_task(
    self,
    video_id: str,
    parent_run_id: str | None,
    dedupe_run_ids: list[str] | None,
    throttle: _RateLimiter,
) -> dict[str, Any]:
    """Worker-thread network phase for one video (mirrors _enrich_video_task):
    throttle.wait(); provider.extract_recommendations(video.url). Returns a result
    dict consumed by the main thread for run bookkeeping + persistence, or a typed
    error payload (RecommendationUnsupportedError recorded with retryable=False)."""
```

### 2.3 Integration point (channel workflow)
Modify `CollectionService._run_channel_target` (and the spec-driven `CollectionService.collect`) so that after `_collect_videos` succeeds, if `effective["scrape_recommendations"]` is true **and** the discovery produced videos, it delegates to the recommendation layer instead of the current inline `_scrape_recommendations_for_video`:

```python
# inside _run_channel_target, after _collect_videos(...):
discovered_ids = [v.video_id for v in kept_videos_this_run]  # persisted videos of this channel run
if effective.get("scrape_recommendations") and discovered_ids:
    results = recommendation_service.collect_recommendations_for_videos(
        discovered_ids,
        parent_run_id=run.run_id,
        channel_id=channel.channel_id,
        reporter=reporter,
    )
    # fold per-video edge counts into the channel run's notes (not its entity counters):
    run.notes += [f"recommendation edges: {sum(r.entities_created for r in results)} across {len(results)} video run(s)"]
```

The channel run keeps `entities_*` counters scoped to videos/channel only; recommendation outcomes live on their own runs. The old `_scrape_recommendations_for_video` is removed/deprecated (its behavior of attributing edges to the channel run is the flaw this design fixes). Existing sync endpoint `POST /collect/channel` keeps its signature; it simply now fans out recommendation runs when `scrape_recommendations` is set (default false, unchanged).

### 2.4 Batch-run variant (optional alternative)
If per-video runs are too many rows for a channel: one `RunType.RECOMMENDATION` run whose `target_url` is the channel URL, `parent_run_id` = channel run, and `config_json["source_video_ids"]` lists every source. All edges are attributed to that single run id; `build_graph(run_id=batch_run)` then renders the entire channel tree. Trade-off: per-video temporal slices are lost and the network UI's per-video run filter (`useRuns("recommendation")`) shows one entry. Recommended default remains per-video runs (§2.1); the batch run is available via a `batch: bool = False` flag on `collect_recommendations_for_videos`.

---

## 3. Click-to-scrape single video

**Goal:** clicking a single video node in the graph triggers an instant recommendation scrape for that video, reusing the job infrastructure, with a response the UI can poll and then invalidate network queries.

### 3.1 Endpoint decision
`POST /scrape/recommendations` exists (`api/app.py:358`) but its body is `ScrapeRecommendationsRequest {video_url: str}`. Two options:

- **(A) Extend the existing endpoint** — add `video_id: str | None = None` to `ScrapeRecommendationsRequest`, resolve `video_url = f"https://www.youtube.com/watch?v={video_id}"` when `video_url` absent. Keeps one endpoint; the UI currently synthesizes the watch URL anyway (`ego-network-view.tsx:51`).
- **(B) New endpoint** `POST /network/scrape/video` with body `{video_id, trigger_run_id?}` that internally calls the same service method; leave `/scrape/recommendations` untouched for full backward compatibility.

**Recommendation: (B)** — a network-tab-specific route keeps the general scrape contract stable and lets us carry `trigger_run_id` (the run whose node was clicked) cleanly. `/scrape/recommendations` stays as-is (backward compat, §7).

### 3.2 Endpoint spec
```
POST {prefix}/network/scrape/video
Body: {
  "video_id": "dQw4w9WgXcQ",          # required
  "trigger_run_id": "run_xyz"         # optional: the run whose node/button started the scrape
}
Response 200: { "job_id": "job_abc" }   # reuse JobSubmitPayload
```

Handler (`api/app.py`, tags `["network"]`):
```python
@app.post(f"{prefix}/network/scrape/video", response_model=JobSubmitPayload)
def network_scrape_video(body: NetworkScrapeVideoRequest):
    def _worker(reporter):
        return services["recommendations"].collect_recommendations(
            f"https://www.youtube.com/watch?v={body.video_id}",
            video_id=body.video_id,
            parent_run_id=body.trigger_run_id,
            reporter=reporter,
        )
    job = services["jobs"].submit(_worker, kind="recommendation")
    return {"job_id": job.job_id}
```

### 3.3 Flow / job lifecycle
1. UI `useMutation` posts to `/network/scrape/video`, stores `job_id`, shows a "scrape started" toast (as `handleScrapeClick` does today).
2. UI polls `GET /jobs/{job_id}` via the existing `useJob` (`queries.ts:294`, auto-refresh every 1500 ms while pending/running) and on terminal state fetches `GET /jobs/{job_id}/result` (returns a single `CollectionResultPayload`, including `dataset_id`).
3. On success the UI invalidates network queries so new edges appear:
   - `queryKeys.networkVideoContext(videoId, runId)`
   - `queryKeys.videoRecommendations(videoId)`
   - `queryKeys.networkSummary(runId)`
   - `queryKeys.runs("recommendation")` (new run appears in the run selector)
   - `queryKeys.jobs()` (job registry)

### 3.4 Response shape the UI needs
- `POST` → `{ job_id }` (`JobSubmitPayload`).
- Poll → `JobPayload` (`status` in `pending|running|succeeded|failed|cancelled`, `progress.stage/discovered/succeeded/failed/message`).
- `GET /jobs/{job_id}/result` → single `CollectionResultPayload` with `run_id`, `run_type="recommendation"`, `status`, `entities_created` (edge count), `errors[]`, `dataset_id`.

---

## 4. Bulk re-scrape of a run

**Goal:** re-scrape recommendations for every source video observed in run R (or every video belonging to a channel), enqueued as a job, deduped against existing edges, rate-limited + retried, with progress.

### 4.1 Source-video discovery
For a **run** trigger, the source videos are the videos first discovered by run R. If R is a recommendation run, the sources are its own `source_video_id`s (via `RecommendationRepository.list_recommendation_edges(run_id=R)` → distinct `source_video_id`). If R is a channel run, sources are `VideoRepository.list_videos_by_run(R)`. For a **channel** trigger, sources are `VideoRepository.list_videos(channel_id)`.

### 4.2 Endpoints
```
POST {prefix}/network/scrape/run
Body: { "run_id": "run_abc", "dedupe": true }          # optional dedupe flag
Response 200: { "job_id": "job_abc" }

POST {prefix}/network/scrape/channel
Body: { "channel_id": "UC...", "trigger_run_id": "run_xyz", "dedupe": true }
Response 200: { "job_id": "job_abc" }
```
Handlers follow the same `JobManager.submit` shape as §3.2, calling:

```python
def _worker(reporter):
    sources = resolve_source_video_ids(scope)          # run- or channel-based, see 4.1
    return services["recommendations"].collect_recommendations_for_videos(
        sources,
        parent_run_id=body.run_id or body.trigger_run_id,
        channel_id=channel_id_if_known,
        dedupe_run_ids=[body.run_id] if body.dedupe else None,
        reporter=reporter,
    )
job = services["jobs"].submit(_worker, kind="recommendation")
```

### 4.3 Dedup semantics
- **Within-run:** normalize once per (source, target, position); a single provider pass must not double-write (the layered providers in `_extract_recommendations` return one list, so this is naturally satisfied; guard anyway in `_scrape_video_task`).
- **Against existing edges:** when `dedupe_run_ids` is provided, skip saving any edge whose `(source_video_id, recommended_video_id)` already exists in any of those runs (query via `list_recommendation_edges(run_id=...)`). This is a *skip* decision — counted in progress and recorded as a note, not an error. **Important design note:** re-observation in a NEW run is the research value of a temporal network (§1.3), so `dedupe` defaults to `true` for the *skip-existing-within-the-same-batch* case and only when explicitly requested does it skip edges already observed by an earlier run. Un-asked, a bulk re-scrape creates fresh observations attributed to fresh runs (which is what a researcher wants for longitudinal slices).

### 4.4 Progress reporting
Reuse `ProgressReporter` (`collection_service.py:70`) which is structurally identical to `jobs._ProgressSink`. The JobManager's `_progress_cb` is passed straight through as `reporter`. Stages:
- `recommendation/batch/start` — `discovered = len(video_ids)`
- `recommendation/video/<id>` — per-video `succeeded` (edges saved) / `failed` (typed errors) increments
- `recommendation/batch/dataset` — dataset persisted
- Final `message` summarizes `saved`, `skipped`, `failed`, `unsupported`.

---

## 5. Dataset auto-persistence + lineage

### 5.1 Fix the scope first (prerequisite)
The whole-population-snapshot behavior (§1.4) makes per-run datasets meaningless. Required changes (design, not code here):
1. `QueryService._recommendation_rows` accepts a `run_id`/`run_ids` filter and `DatasetService.create_dataset` forwards `run_ids` into it (implement the "not yet implemented" scoping). This also fixes `_persist_graph_as_dataset`'s snapshots if it ever returns.
2. `_ID_FIELD["recommendation"]` stays `recommended_video_id` for `member_ids`; add an explicit `source_video_ids`-style scope via the existing `video_ids` parameter by mapping edges to `source_video_id` rows (recommendation rows already carry `source_video_id`, so `video_ids` can filter on it).
3. `_register` records `scope` (`run_ids`, `channel_ids`, `video_ids`, `member_ids`) — keep, and add `"lineage"` (below).

### 5.2 A single, unified persistence helper
Extract the inline auto-persist block from `recommendation_service.py:124-141` into one reusable method so every path (single scrape, batch, bulk re-scrape, channel collect) shares it:

```python
def _persist_run_dataset(
    self,
    run: CollectionRun,          # the recommendation run that produced the edges
    edges: list[RecommendationObservation],
    *,
    trigger_run_id: str | None,  # run whose node/button started the scrape (may equal parent_run_id)
    parent_run_id: str | None,
    source_kind: str,            # "single" | "channel_collect" | "node_click" | "run_bulk"
) -> str | None:                 # returns dataset_id (None on failure, logged, non-fatal)
```

### 5.3 Naming conventions
- Single video scrape / node click: `Recommendation Run <rec_run_id> - <video_id> [source <trigger_run_id>]`
- Channel collect fan-out: `Recommendation Run <rec_run_id> - <video_id> [source <channel_run_id>]`
- Bulk re-scrape of run R: `Recommendation Run <rec_run_id> - <video_id> [source run <R>]`
- (Batch-run variant §2.4): `Recommendation Run <batch_run_id> - <channel_id or "batch"> [source <channel_run_id>]`

`description` = `"Auto-persisted dataset for recommendation run <rec_run_id> of <video_id>; triggered by <trigger_run_id> (<source_kind>); <len(edges)> edge(s)."`

### 5.4 Dataset fields
```
create_dataset(
    name=<per 5.3>,
    description=<per 5.3>,
    entity_type="recommendation",
    include_raw=False,
    run_ids=[run.run_id],                        # edges of THIS recommendation run (now actually honored)
    channel_ids=[channel_id] if known else None, # channel of the source video
    video_ids=[source_video_id],                 # the source video id(s) the edges originate from
    member_ids=[e.recommended_video_id for e in edges],  # exact recommended set (honored via _ID_FIELD)
    criteria=None,
    variable_selection=None,
)
```
`_register` additionally stores `source_projection["lineage"] = {"trigger_run_id", "parent_run_id", "source_kind", "depth": 1}` so provenance is machine-queryable, not just embedded in the name. The **triggering run** is always recorded: `trigger_run_id` is the run whose node/button started the scrape (for a node click, the run slice the user was viewing; for channel collect, the channel run; for run bulk, run R).

### 5.5 Unifying the existing auto-persist
`RecommendationService.collect_recommendations` currently inlines dataset creation. Replace the inline block with `_persist_run_dataset(...)` (trigger_run_id = `parent_run_id or run.run_id`, source_kind `"single"`). `CollectionResult.dataset_id` is set from the return value and flows through `JobResultPayload`/`_collection_payload` unchanged.

---

## 6. Concurrency & failure handling

### 6.1 Rate limiting
- One shared `_RateLimiter(self._settings.scraper.request_delay_seconds)` per batch job (`collect_recommendations_for_videos`), shared across all worker threads — never one limiter per call (the current inline path's defect). `throttle.wait()` runs on the worker thread immediately before `provider.extract_recommendations`.
- Single-video scrape (`collect_recommendations`) creates its own limiter for its single request (matches today's behavior).

### 6.2 Retries
- Transient retries already live at the adapter boundary: `extract_recommendations` is wrapped by `retry_policy(retries=settings.scraper.retries, backoff=settings.scraper.retry_backoff)` (`acquisition/retry.py`), retrying only `NetworkError`/`RateLimitError` with exponential backoff. **Do not add a second retry layer** in the service.
- Batch-level resilience: a failed video records a `CollectionError` (via `_record_error`) and continues; one worker's failure never aborts siblings (`_scrape_video_task` returns an error payload instead of raising, mirroring `_enrich_video_task`).

### 6.3 `RecommendationUnsupportedError` (never fabricate)
Handled in `_scrape_video_task`/`collect_recommendations` exactly as today: record `EntityType.RECOMMENDATION`, `ErrorType.RECOMMENDATION_UNSUPPORTED`, `retryable=False`, mark that video failed (non-fatal), **no edges are invented**. The resulting run status is `partial`; the batch result reports `failed` in progress.

### 6.4 Partial failures surfaced
- Job progress `failed` counter increments per failing source video.
- Each per-video `CollectionResult.status` is `success`/`partial`; batch `job.result` is a list (`_collect_payload_many` → `{target_count, results[]}`), so the UI's `CollectJobResult` rendering already shows per-target status and `errors[]`.
- `CollectionError` rows are persisted via `run.record_error` for auditability.

### 6.5 Concurrency ceiling
Batch internal threads are capped at `settings.scraper.enrichment_concurrency`; the JobManager still has its own `max_workers` pool for concurrent jobs. Document that a channel collect + a bulk re-scrape running simultaneously double the request rate, and that the shared `request_delay_seconds` is the aggregate bound.

---

## 7. Backward compatibility

| Existing surface | Status | Notes |
|---|---|---|
| `POST /scrape/recommendations` (`{video_url}`) | **Untouched** | Body contract unchanged; routes to `collect_recommendations(video_url)` (still works; new kwargs default off). |
| `POST /collect/recommendations` (sync) | **Untouched** | Calls `collect_recommendations(body.url)`; signature unchanged. |
| `POST /collect` (spec-driven, job) | **Behavior-compatible** | `scrape_recommendations` still honored; now fans out proper per-video recommendation runs instead of attributing edges to the channel run. Same observed edges, cleaner lineage. |
| `POST /collect/channel`, `POST /collect/video` | **Untouched signatures** | Channel may now fan out recommendation runs when the flag is set (default off). |
| `GET /jobs`, `/jobs/{id}`, `/jobs/{id}/cancel`, `/jobs/{id}/result` | **Untouched** | New jobs reuse `kind="recommendation"`. |
| `ui/src/app/collect/page.tsx` + `CollectTargetForm` | **Untouched** | Uses `useSubmitCollect` spec-driven flow; no changes required. |
| `useScrapeRecommendations` | **Untouched** | Still posts `{video_url}`; the network tab may add a new mutation for `POST /network/scrape/video` without removing the old one. |
| `RecommendationGraphService.build_graph` | **Changed** | Remove the `_persist_graph_as_dataset` side effect (read paths must not write). Keep `_persist_graph_as_dataset` as an explicit method. |

### 7.1 Schema additions (summarised)
- `CollectionRun.parent_run_id: str | None` (+ row mapping + `RunPayload`).
- `ScrapeRecommendationsRequest` unchanged; new `NetworkScrapeVideoRequest {video_id, trigger_run_id?}` and `NetworkScrapeRunRequest {run_id, dedupe?}` / `NetworkScrapeChannelRequest {channel_id, trigger_run_id?, dedupe?}`.
- `Dataset.source_projection["lineage"]` (+ optional display in datasets UI).
- No change to `RecommendationObservation`, `RecommendationRepository` contracts, or the Excel store shape beyond the `runs` sheet column.

---

## 8. Implementation checklist (for the build agent)

1. `domain/models.py` + `persistence/excel_repository.py` + `api/schemas.py`: add `parent_run_id` to `CollectionRun`/`RunPayload`.
2. `services/query_service.py` + `services/dataset_service.py`: implement `run_ids` scoping for recommendation rows and `video_ids` (source) scoping; add `lineage` to `_register`.
3. `services/recommendation_service.py`: add `video_id`/`parent_run_id`/`dedupe_run_ids` kwargs to `collect_recommendations`; add `collect_recommendations_for_videos`, `_scrape_video_task`, `_persist_run_dataset`; remove/replace inline auto-persist and the misattributing `_scrape_recommendations_for_video`.
4. `services/collection_service.py`: wire channel-run fan-out after `_collect_videos`.
5. `services/recommendation_graph_service.py`: remove `_persist_graph_as_dataset` call from `build_graph`.
6. `api/app.py`: add `POST /network/scrape/video`, `/network/scrape/run`, `/network/scrape/channel` (job-backed); add request models.
7. `ui/src/services/api.ts` + `queries.ts`: add `networkScrapeVideo/run/channel` calls + job-polling mutation; add network-query invalidation on success.
8. `services/network_analytics_service.py`: replace `_get_video_metadata` mock with `YtDlpAcquisitionProvider.get_video_metadata` (flagged, §1.6).