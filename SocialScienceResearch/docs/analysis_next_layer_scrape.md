# Analysis — "Scrape All the New Layer Videos" (Crawl the Recommendation Layers)

**Scope: architecture analysis only. No application code is written or modified.**
All paths are relative to `SocialScienceResearch/`; UI paths under `ui/`. Line
references were read from the working tree and should be re-verified at build
time. API prefix everywhere is `/api/v1/social-science` (`api/app.py:304`).

This document extends the four prior analyses
(`docs/analysis_network_api.md`, `docs/analysis_network_ux.md`,
`docs/analysis_scraper_engine.md`, `docs/overhaul_implementation_plan.md`).
It assumes the overhaul's lineage work is present (`CollectionRun.parent_run_id`,
`run.config_json["trigger"]`, `collect_recommendations_for_videos`,
`POST /network/scrape/{video,run,channel}`) — all confirmed in the tree.

---

## 0. Feature statement (restated precisely)

The researcher repeatedly performs a **layer crawl**:

1. Take the *frontier* = the set of videos **newly added by the most recent
   layer** (for layer 0, the videos first discovered by the seed run).
2. Scrape the **next layer**: for each frontier video, observe its
   recommendations (one `RunType.RECOMMENDATION` run per video, exactly as
   `RecommendationService.collect_recommendations_for_videos` does today).
3. **Deep-enrich every *new* video** discovered this layer: full metadata
   (title, channel, thumbnail, duration, views/likes via `extract_video`) **and
   all its comments**, persisting `Video` + `VideoObservation` + `Comment` /
   `CommentObservation` rows and upserting the `Channel`.
4. Add the new videos + comments to the graph (both projections, §4).
5. **Classify** each newly scraped node/edge against the *pre-crawl* graph:
   `NEW_VIDEO` vs `EXISTING_VIDEO`, `NEW_CHANNEL` vs `EXISTING_CHANNEL`,
   and per new weak component `CONNECTED` (touches the existing network) vs
   `DISCONNECTED` (brand-new community). Surface the counts explicitly.
6. The researcher picks the graph projection to view: **(a) CHANNEL GRAPH**
   (nodes = channels, edges = "channel A's video recommended channel B's video",
   weighted by edge count) or **(b) VIDEO GRAPH** (nodes = videos with
   channel+title+thumbnail+metrics, edges = recommendation relationships).

---

## 1. Grounding — what already exists (verified in the tree)

| Concern | Current reality | File:line |
|---|---|---|
| Per-video recommendation scraping | `collect_recommendations_for_videos(video_ids, *, parent_run_id, channel_id, dedupe_run_ids, concurrency, reporter)` — one `RECOMMENDATION` run per source video, `ThreadPoolExecutor` + shared `_RateLimiter`, dedupe against `dedupe_run_ids`. | `services/recommendation_service.py:153-219` |
| Run lineage | `CollectionRun.parent_run_id` + `config_json["trigger"]={kind,parent_run_id,depth}`; `RunPayload.parent_run_id` exposed. | `domain/models.py:54`, `recommendation_service.py:404-419`, `api/schemas.py:162` |
| Edge persistence | `RecommendationObservation(observation_id, collection_run_id, source_video_id, recommended_video_id, position, channel_id, title, observed_at, raw_json)`; unique per run tuple; repo upserts by `observation_id`. | `domain/models.py:216-236`, `persistence/excel_repository.py:338-372` |
| Target metadata gap | Recommended (target) videos are **not** persisted as `Video` rows today; the graph UI enriches via repo batch reads (`_MetadataIndex`). | `docs/analysis_network_api.md §1.5/§4`, `services/network_analytics_service.py:246-290` |
| Comment collection | `CollectionService._persist_comments(run, raw_comments, video_id, errors, effective, reporter)` — applies min-likes/date/cap criteria, upserts comments + observations. **Only invoked by channel/video runs**, never by recommendation runs (`_complete_video_result` hardcodes `comments_collected=0`). | `services/collection_service.py:828-900`, `recommendation_service.py:384` |
| Graph payloads | `GET /network/graph` returns enriched video nodes + edges + run/channel facets (`NetworkGraph`). `GET /network/edges`, `/network/metrics`, `/network/temporal`, `/network/channels`. | `api/routers/network_ext.py:94-123`, `services/network_analytics_service.py:459-571` |
| Job infra | `JobManager.submit(fn, kind)` → `{job_id}`; poll `GET /jobs/{id}`, result `GET /jobs/{id}/result`. Job result envelope assumes a *list of CollectionResults* (`_collect_payload_many`). | `services/jobs.py:91-99`, `api/app.py:477-526` |
| Excel column migration | `headers_for(model)` derives columns from pydantic fields; `ensure_sheet` **appends missing columns** to existing sheets. Adding `layer_index` to a model auto-adds the column, legacy-safe. | `persistence/serialization.py:28-30`, `persistence/excel_workbook.py:128-149` |
| UI graph reuse | `NetworkGraph` is a unified, canvas-rendered component (`GraphNode`/`GraphLink`); `/network/full` has tabs metrics/temporal/edges/graph. | `ui/src/components/features/network-graph.tsx`, `full-network-view.tsx:195-337` |
| Bulk-scrape endpoints | `POST /network/scrape/run|channel|video` (job-backed). | `api/app.py:393-475` |
| Dataset auto-persist | `_persist_run_dataset` writes a run-scoped dataset with `lineage`; `run_ids` scoping now honored. | `recommendation_service.py:431-491`, `query_service.py:336-367` |

### 1.1 Gaps this feature must fill
1. **Targets are not persisted as videos.** A layer crawl must deep-enrich new
   recommended videos so they (a) become the *next* layer's frontier (they need
   a `Video.url` to scrape), (b) carry thumbnails/metrics/comments into the
   graph. This is the central behavioural addition.
2. **No notion of "layer".** Frontier tracking, per-layer edge attribution and
   per-layer summaries do not exist.
3. **No channel-level projection.** Only `ChannelProjection` (distinct ids +
   edge coverage); no co-occurrence graph of channels.
4. **No new-vs-existing classification.** `/network/temporal` compares run
   slices; nothing reports which nodes/edges/channels are *new* relative to a
   snapshot, or which new components are disconnected from the existing graph.
5. **Comment collection is not wired into recommendation runs** (§ table row 4).

---

## 2. Data-model design

### 2.1 Layer index on runs and edges (migration-safe, no new relation table)
Add `layer_index: int | None = None` to:

- **`CollectionRun`** (`domain/models.py:39`) — the layer a recommendation run
  was created in. `None` for ordinary runs created before/outside a crawl
  (seed runs from the network tab remain layer-agnostic).
- **`RecommendationObservation`** (`domain/models.py:216`) — denormalized copy
  of the producing run's layer, so edges are filterable by layer in **one
  scan** without joining `runs` (the repo reads are sheet-wide scans;
  `excel_repository.py:361-372`).

Both are `None`-defaulted. Because `headers_for` derives columns from the
pydantic model and `WorkbookStore.ensure_sheet` appends missing headers, this
is a safe additive migration (`persistence/serialization.py:28-30`,
`persistence/excel_workbook.py:140-149`). No change to `RecommendationRepository`
or to existing row mappings.

### 2.2 A lightweight `LayerRun` record (the crawl anchor)
Modelling layers purely as `layer_index` on runs/edges makes "resume the
crawl" and "show the summary of layer N" require recomputing frontiers and
counts from raw rows every request. A dedicated record — written **after** a
crawl completes, like datasets are — gives the UI a cheap anchor and stores
the classification result. New module `domain/layer_models.py`:

```
class LayerRun(_Base):                      # persisted to a new "layer_runs" sheet
    layer_run_id: str                      # new_id("lyr")
    layer_index: int                       # 0 = seed, 1 = first crawl, ...
    parent_run_id: str | None              # run expanded (the trigger)
    parent_layer_run_id: str | None        # previous LayerRun id (None for seed)
    projection: str                        # "channel" | "video" (chosen at crawl time)
    started_at: datetime
    finished_at: datetime | None
    status: CollectionStatus
    frontier_video_ids: list[str]          # the frontier that was expanded
    discovered_video_ids: list[str]        # NEW videos deep-enriched this layer
    run_ids: list[str]                     # the RECOMMENDATION runs created
    comments_collected: int
    summary: dict[str, Any]                # NewRelationsReport.counts (see §5)
    config_json: dict[str, Any] = Field(default_factory=dict)   # comment criteria snapshot, concurrency
```

- New repository `LayerRunRepository` (ABC in `persistence/base.py`, added to
  the `Repositories` container; Excel impl `persistence/layer_repository.py`
  mirroring `dataset_repository.py`: `ensure_sheet("layer_runs",
  headers_for(LayerRun))`, upsert by `layer_run_id`, `list/get`).
- **Frontier resolution is then trivial**: the next crawl's frontier = the
  last `LayerRun.discovered_video_ids` (ordered by `layer_index`); a seed
  layer's frontier = `list_videos_by_run(run_id)` (channel run) or distinct
  `source_video_id`s of the run's edges (recommendation run) — the same
  resolution `POST /network/scrape/run` already uses (`api/app.py:422-433`).

Trade-off recorded: the alternative "derive everything from runs/edges" avoids
the new sheet but forces O(edges) scans on every layer request and cannot
retain the classification report (which is cheap to persist now and genuinely
derived-only-once data). The `LayerRun` record wins.

### 2.3 How comments attach to newly scraped videos
Comments are already keyed per video (`Comment.video_id`,
`CommentObservation.comment_id`, `repos.comments.list_comments(video_id)`).
The only work is to **produce** them for new targets: the layer service runs
`provider.extract_video(url)` per new video (returns `info["comments"]` when
the provider is configured, `acquisition/base.py:66-67`) and pipes them through
the existing `CollectionService._persist_comments(...)` with the resolved
`effective` config (module defaults + `collect_comments` from the request).
`comments_collected` is folded into the `LayerRun` and surfaced per layer.
Existing `_persist_comments` already applies min-likes/date-window/cap criteria,
so researcher comment policy is honored without new logic.

---

## 3. Backend service design — `LayerScrapeService`

New file `services/layer_scrape_service.py`:

```python
class LayerScrapeService(RecommendationService):
    # inherits provider, repos, settings, _RateLimiter, _begin_run/_finish_run,
    # _record_error/_report, _persist_comments, _persist_flat_observation,
    # _begin_recommendation_run (override to set layer_index), _persist_run_dataset.
```

Public surface:

- `bootstrap_layer(run_id, projection="video") -> LayerRun`
  Create layer 0 from an existing run: frontier = the run's videos/sources
  (§2.2), `discovered_video_ids = frontier`, `status=SUCCESS`, no scrape.
- `list_layers() -> list[LayerRun]`, `get_layer(layer_run_id) -> LayerRun`
  (404 if missing).
- `scrape_next_layer(*, parent_layer_run_id=None, parent_run_id=None,
   projection="video", collect_comments=True, concurrency=None,
   reporter=None) -> list[CollectionResult]`
  The job worker. Steps:
  1. **Snapshot pre-crawl state** (§5.1): existing video ids, channel ids,
     edge pairs, and the weakly-connected components of the existing graph
     (from `repos` before any writes). `layer_index = parent.layer_index + 1`.
  2. **Scrape the frontier**: reuse
     `collect_recommendations_for_videos(frontier, parent_run_id=parent_run_id,
     dedupe_run_ids=None, concurrency=concurrency, reporter=reporter)` with a
     `layer_index` threaded through the per-video runs and their edges
     (`_begin_recommendation_run` gains a `layer_index` kwarg; edges get
     `edge.layer_index = layer_index` in `_complete_video_result`).
  3. **Deep-enrich new targets**: distinct `recommended_video_id`s of newly
     saved edges that have **no `Video` row yet** → one `extract_video` per id
     under the shared throttle → `normalize_video`/`normalize_video_observation`
     upserts + `normalize_comments`/`_persist_comments`. Persist `Channel`
     when resolvable. Collect created ids into `discovered_video_ids`.
  4. **Classify** new nodes/edges/components vs the snapshot (§5).
  5. **Persist** the `LayerRun` record (frontier, discovered ids, run_ids,
     `comments_collected`, `summary`) and, when edges exist, a layer-scoped
     dataset via `_persist_run_dataset` (name `Recommendation Layer <N> —
     source <parent_run_id>`, `lineage={"layer_index": N, ...}`).
  6. Return the list of per-video `CollectionResult`s (keeps
     `GET /jobs/{id}/result` unchanged — it already expects a list).

Because `LayerScrapeService` extends `RecommendationService` and inherits the
thread-pool/rate-limiter pattern, network work for a layer (frontier
recommendations + target enrichment) shares one `_RateLimiter` paced at
`settings.scraper.request_delay_seconds`.

### 3.1 `RecommendationService` changes (small, backward compatible)
- `collect_recommendations(..., layer_index: int | None = None)` and
  `collect_recommendations_for_videos(..., layer_index: int | None = None)`.
- `_begin_recommendation_run(..., layer_index)` sets `run.layer_index` and
  `run.config_json["trigger"]["depth"] = layer_index`.
- `_complete_video_result` stamps `edge.layer_index = layer_index` on each
  saved edge (edges carry the run's layer denormalized).
- No signature breaks: `layer_index=None` for all existing callers
  (`/network/scrape/*`, legacy `/scrape/recommendations`, channel fan-out).

### 3.2 `NetworkAnalyticsService` changes
- `edges(...)` / `graph(...)` gain an optional `layer_index: int | None`
  filter applied during the edge scan (cheap, mirrors `run_id`).
- New `channel_graph(layer_index=None) -> ChannelGraphPayload` (§4.2) built
  from the same underlying edges — no new repository reads.

---

## 4. Projections — one edge store, two views

Both projections are **derived** from the same `RecommendationObservation`
rows at read time (nothing new is persisted for the graph).

### 4.1 VIDEO GRAPH (existing, layer-scoped)
Exactly the current `NetworkGraph` from `NetworkAnalyticsService.graph()`:
video nodes (`video_id`, `title`, `channel_id/name`, `thumbnail_url`,
`views/likes/duration`, degree/kind, run provenance) + directed edges
(`source`→`target`, `position`, `run_id/type/name`). Add `layer_index` scoping
(§3.2) so the researcher can view "the graph as of layer N". This is what the
existing `NetworkGraph` component already renders — **zero UI graph work**.

### 4.2 CHANNEL GRAPH (new)
New response models (in `services/network_analytics_service.py`, alongside the
existing `GraphNode`/`GraphEdge`):

```
class ChannelGraphNode(_Base):
    channel_id: str
    channel_name: str | None
    avatar_url: str | None
    subscriber_count: int | None = None     # latest ChannelObservation
    video_count: int = 0                    # distinct videos of this channel in the slice
    in_degree: int = 0                      # distinct channels recommending into it
    out_degree: int = 0
    run_ids: list[str] = []
    run_types: list[str] = []

class ChannelGraphEdge(_Base):
    source: str                              # channel_id
    target: str
    video_edge_count: int = 0                # # of video-level edges A→B
    run_ids: list[str] = []
    sample_video_pairs: list[dict] = []      # [{source_video_id, recommended_video_id, position}] (first few)

class ChannelGraphPayload(_Base):
    projection: str = "channel"
    nodes: list[ChannelGraphNode]
    edges: list[ChannelGraphEdge]
    channels: list[ChannelFacet] = []        # reuse
    runs: list[dict] = []                    # reuse
    node_count: int = 0
    edge_count: int = 0
```

Construction (`NetworkAnalyticsService.channel_graph`):
1. Read the layer-scoped edges once; resolve source/target channel ids via
   `_MetadataIndex.video()` (batch, no N+1; target falls back to
   `edge.channel_id`).
2. Drop video-level edges whose **either** endpoint's channel is unresolved
   (count them and record in `channels` facet metadata as `unattributed_edges`);
   do **not** invent a synthetic "unknown" node.
3. Aggregate: `video_count[channel]`, `out_degree/in_degree` over distinct
   channel neighbours, `video_edge_count[(A,B)]`, union of `run_ids`, and the
   first ≤3 video pairs per channel pair as sample evidence.
4. Node labels: channel name, avatar as thumbnail, latest subscriber count from
   `repos.channels.get_latest_channel_observations` (batch).

Serving: `GET /network/layer/{layer_run_id}/graph?projection=video|channel`
(§6). The video projection reuses the existing `NetworkGraph`; the channel
projection is mapped to the same `NetworkGraph` component by translating
`ChannelGraphNode → GraphNode` (id=`channel_id`, `title=channel_name`,
`thumbnail=avatar_url`, kind from in/out-degree, `channel=channel_name`) — so
**one graph component serves both projections**.

---

## 5. New-relations detection (exact algorithm) + schema

### 5.1 Snapshot (taken at the start of `scrape_next_layer`, before writes)
```
preexisting_video_ids   = {v.video_id for v in repos.videos.list_videos()}
preexisting_channel_ids = {c.channel_id for c in repos.channels.list_channels()}
preexisting_edge_pairs  = {(e.source_video_id, e.recommended_video_id)
                           for e in repos.recommendations.list_recommendation_edges()}
old_graph               = nx.DiGraph built from preexisting edges
old_nodes               = set(old_graph.nodes)          # may exceed preexisting_video_ids (targets never persisted)
old_components          = list(nx.weakly_connected_components(old_graph))
```

### 5.2 Per-node / per-edge classification (after the crawl)
For each newly persisted `Video` id `v` in `discovered_video_ids`:
- `EXISTING_VIDEO` if `v in preexisting_video_ids or v in old_nodes`
  else `NEW_VIDEO`.

For each distinct channel id `c` newly seen on a new node/edge:
- `EXISTING_CHANNEL` if `c in preexisting_channel_ids` else `NEW_CHANNEL`.

For each newly saved edge `(s → t)`:
- `NEW_EDGE` if `(s,t) not in preexisting_edge_pairs` else `SKIPPED_DUPLICATE`
  (re-observation in a new layer of an already-seen pair is reported as a
  dedup skip count, never an error — consistent with scraper-spec §4.3).

### 5.3 Component connectivity (CONNECTED vs DISCONNECTED)
Build `G_new` = DiGraph over **only the new edges** (this layer's saved edges).
For each `C` in `weakly_connected_components(G_new)`:
- `CONNECTED` iff `C ∩ old_nodes ≠ ∅` (any node of the component exists in the
  pre-crawl graph). Because a crawl expands the *previous frontier*, the
  source of every new edge is an existing node, so most components are
  CONNECTED by construction.
- `DISCONNECTED` iff `C ∩ old_nodes == ∅` — a brand-new community. Arises only
  when a new video's observed edges all point at other *new* videos and no edge
  touches the old graph (e.g. a new video is enriched and its own
  recommendations are also recorded in the same pass, or a seed scrape of a
  URL outside the current graph). The classifier must handle it; the UI must
  surface it (`disconnected_components`).

Channels are treated as *membership* of nodes, not components: a component is
"new-channel-heavy" when ≥1 of its new nodes carries a `NEW_CHANNEL`.

### 5.4 Response schema — `NewRelationsReport`
```
{
  "layer_run_id": str,
  "layer_index": int,
  "projection": "channel" | "video",
  "generated_at": iso-datetime,
  "counts": {
    "new_videos": int,                       # NEW_VIDEO
    "existing_videos_referenced": int,       # EXISTING_VIDEO targets touched
    "new_channels": int,
    "existing_channels_referenced": int,
    "new_edges": int,
    "edges_connecting_to_existing_nodes": int,   # edges with ≥1 endpoint in old_nodes
    "edges_without_source_channel": int,         # channel-graph attribution losses
    "skipped_edges_duplicate": int,
    "new_components": int,                   # len(disconnected_components)
    "connected_components": int,             # len(connected_components)
    "comments_collected": int
  },
  "new_videos": [ {"video_id", "title", "channel_id", "channel_name",
                   "thumbnail_url", "classification": "NEW_VIDEO"} ],      # capped at 200 + total
  "existing_videos": [ {"video_id", "title", "channel_id"} ],              # capped
  "new_channels": [ {"channel_id", "channel_name", "avatar_url"} ],        # capped
  "connected_components":   [ {"component_id", "node_count", "edge_count", "touches_channels": [...] } ],
  "disconnected_components":[ {"component_id", "node_count", "edge_count", "node_video_ids": [...] } ],
  "sample_edges": [ EdgeRow ],               # first ≤50 new edges, reuse EdgeRow
}
```
`component_id` = the lexicographically smallest node id in the component
(stable, deterministic). Lists are capped (counts are authoritative; caps
documented in the endpoint docstring) so a large layer does not produce a
megabyte response. The full `counts` dict is persisted verbatim in
`LayerRun.summary` so `GET /network/layer/{id}` returns counts instantly.

---

## 6. Endpoint spec (final)

New router `api/routers/layer_network.py` (keeps `network_ext.py` focused),
included in `api/app.py` alongside the other routers (`app.py:312-332`).
Request models in `api/schemas.py`; response models in
`domain/layer_models.py` + `services/network_analytics_service.py`.

| Endpoint | Method/body | Response |
|---|---|---|
| `POST /network/layer` | `{run_id, projection:"video"\|"channel"}` | `LayerRunPayload` (layer 0) |
| `POST /network/layer/scrape` | `{parent_layer_run_id?, parent_run_id?, projection, collect_comments?=true, concurrency?}` | `JobSubmitPayload {job_id}` |
| `GET /network/layers` | `cursor?`, `page_size?` | `Paginated[LayerRunPayload]` (ordered by `layer_index` desc) |
| `GET /network/layer/{layer_run_id}` | — | `LayerRunPayload` incl. `summary.counts` + frontier + run_ids |
| `GET /network/layer/{layer_run_id}/relations` | — | `NewRelationsReport` |
| `GET /network/layer/{layer_run_id}/graph` | `projection="video"\|"channel"` (default `video`) | `NetworkGraph` \| `ChannelGraphPayload` |
| `GET /network/layer/{layer_run_id}/frontier` | — | `{layer_index, video_ids: [...], video_count}` (drives the stepper) |

`POST /network/layer/scrape` wiring (mirrors `app.py:393-475`):

```python
@app.post(f"{prefix}/network/layer/scrape", tags=["network"], response_model=JobSubmitPayload)
def layer_scrape(body: LayerScrapeRequest):
    def _worker(reporter):
        return services["layer_scrape"].scrape_next_layer(
            parent_layer_run_id=body.parent_layer_run_id,
            parent_run_id=body.parent_run_id,
            projection=body.projection,
            collect_comments=body.collect_comments,
            concurrency=body.concurrency,
            reporter=reporter,
        )
    job = services["jobs"].submit(_worker, kind="layer")
    return {"job_id": job.job_id}
```

**Job→UI flow (no change to the job endpoints):**
1. UI posts → `{job_id}`.
2. UI polls `GET /jobs/{job_id}` (existing `useJob` auto-refresh).
3. On `succeeded`, UI fetches `GET /network/layer/{id}` (from a previous
   `GET /network/layers` list to learn the new id, or the job's
   `CollectionResult`s carry `run_id`s) then `GET /network/layer/{id}/relations`
   and `GET /network/layer/{id}/graph`. Invalidates keys: `["network","layer",
   ...]`, `["jobs"]`, `["runs"]`, `["network","full",...]`, `["network","graph",...]`.

**Payloads the UI needs** (all snake_case, pydantic-serialized):
- `LayerRunPayload`: `layer_run_id, layer_index, parent_run_id, parent_layer_run_id, projection, status, started_at, finished_at, frontier_video_ids, discovered_video_ids, run_ids, comments_collected, summary`.
- `JobSubmitPayload` / `JobPayload`: existing.

---

## 7. UI shape

### 7.1 Placement
Add a **"Layers" tab** to `/network/full` (`full-network-view.tsx:90,195-337`),
tab union becomes `"metrics" | "temporal" | "edges" | "graph" | "layers"`.
Keeps every existing tab; the layers flow lives beside the graph it feeds.
A "Bootstrap" action is offered when no `LayerRun` exists yet (pick a run from
`useRuns()` → `POST /network/layer`).

### 7.2 Components (new dir `ui/src/components/features/network-layer/`)
- **`layer-stepper.tsx`** — the "crawl next layer" control:
  - Reads `useLayers()`; shows the current `layer_index` as a step indicator
    (Layer 0 seed → Layer 1 → …), the frontier size, and per-layer
    `comments_collected`/`discovered_video_ids` counts.
  - **"Crawl next layer"** button → `useCrawlNextLayer()` mutation posts
    `POST /network/layer/scrape`, polls `useJob(job_id)`, and on success
    invalidates layer/graph/runs/jobs queries and refetches the new layer +
    relations (the `NewRelationsPanel`).
  - Checkbox "Collect comments for new videos" (→ `collect_comments`) and a
    projection picker (→ `projection`, shared with the graph tab).
- **`new-relations-panel.tsx`** — renders `NewRelationsReport`: count tiles
  (New videos / New channels / New edges / Edges connecting to existing nodes /
  New components / Connected components / Comments), a capped list of
  `new_channels` and `new_videos`, and two component groups — **Connected**
  chips (green) and **Disconnected / new community** chips (amber, with node
  count) — each clickable to highlight the component in the graph.
- **`layer-graph.tsx`** — a **channel/video projection toggle** (`Segmented`
  "Channel graph" | "Video graph") + the `NetworkGraph` component:
  - video projection → `useLayerGraph(id, "video")` mapped via the existing
    `mapGraphPayload` (`full-network-view.tsx:32-84`);
  - channel projection → `useLayerGraph(id, "channel")` mapped by translating
    `ChannelGraphNode → GraphNode` (§4.2) so the *same* `NetworkGraph` renders
    both. Channel node click still opens the inspection drawer (scrape disabled
    for synthetic channel nodes, or routed to `POST /network/scrape/channel`).
- **`networkLayer.ts`** service module + `ui/src/lib/network-layer-types.ts`:
  `useLayers`, `useLayer`, `useLayerFrontier`, `useLayerRelations`,
  `useLayerGraph(id, projection)`, `useBootstrapLayer`, `useCrawlNextLayer`
  (mutation that submits + polls the job and invalidates on terminal state).

### 7.3 Reuse of the redesigned `NetworkGraph`
No changes to `network-graph.tsx` are required for the video projection. The
channel projection only needs the type-mapping adapter in `layer-graph.tsx`.
The filters (`runs`, `channels` facets), tooltip, drawer, and scrape action all
work as-is because channel nodes are fed as ordinary `GraphNode`s
(`channel_id` as id, `channel_name` as title).

---

## 8. Verification plan

### 8.1 Backend unit tests
- **`tests/test_layer_scrape_service.py`** (new; fake provider — no network):
  - seed a run + videos → `bootstrap_layer` creates layer 0 with correct frontier;
  - `scrape_next_layer` on a fake provider returning fixed recommendation
    payloads: per-video runs created with `layer_index=1`, edges stamped with
    `layer_index=1`, new target videos persisted as `Video` +
    `VideoObservation`, comments persisted via `_persist_comments`
    (assert `comments_collected`), channels upserted;
  - classification: a target already in the corpus → `EXISTING_VIDEO`; brand-new
    → `NEW_VIDEO`; a component of only-new nodes (feed the fake provider a case
    where a new video's own recommendation is also recorded) →
    `DISCONNECTED`, everything else → `CONNECTED`; dedup skip counted when the
    pair already existed;
  - `channel_graph`: edges aggregated to weighted channel pairs with
    `video_edge_count`, unattributed edges counted;
  - determinism of `component_id` and list caps.
- **`tests/test_layer_network_api.py`** (new; `TestClient`): bootstrap 201/200,
  scrape job `{job_id}`, layer list/summary/relations/graph for both
  projections, 404 on unknown `layer_run_id`, `channel_scope`-style 400s on
  bad `projection`.
- **`tests/test_network_analytics_service.py`** (update): `graph(layer_index=1)`
  scoping; `channel_graph` node/edge counts on the existing seeded network.
- **`tests/test_recommendation_service.py`** (update): `layer_index` propagation
  to runs + edges; default `None` for legacy callers.
- **`tests/test_collection_service.py`** (update, minimal): unchanged behaviour
  with `layer_index=None`.

### 8.2 UI checks
- `cd ui && npm run typecheck && npm run lint` (new types + hooks must pass).
- Manual: seed → bootstrap → crawl → relations panel counts update → toggle
  projection → component highlight.

### 8.3 Playwright E2E — `tests/e2e/network_layers.spec.ts` (new; mirror
`network_visualizer.spec.ts` against a seeded local API + UI):
1. Seed data (via API), open `/network/full`, switch to the Layers tab →
   stepper shows layer 0.
2. Click "Crawl next layer" → assert a `POST /network/layer/scrape` request,
   job completes (poll), and the relations panel renders count tiles + a
   non-zero `new_videos` count.
3. Assert the **channel/video toggle**: switching to "Channel graph" renders
   the canvas with channel-labelled nodes (no change of component).
4. Assert the relations panel lists `new_channels` and shows a "Connected"
   component chip; if the fixture includes a disconnected community, assert a
   "Disconnected" chip appears.
5. Assert scrape fires only from the graph drawer (same one-action-per-gesture
   rule as `network_visualizer.spec.ts`).

---

## 9. File-by-file implementation checklist

### New files (backend)
1. `domain/layer_models.py` — `LayerRun`, `LayerScrapeRequest`/`LayerRunPayload`/
   `NewRelationsReport`/`LayerFrontier` pydantic models (mirror
   `domain/dataset_models.py`).
2. `persistence/layer_repository.py` — Excel-backed `LayerRunRepository`
   (`ensure_sheet("layer_runs", headers_for(LayerRun))`, upsert by
   `layer_run_id`, list/get).
3. `services/layer_scrape_service.py` — `LayerScrapeService(RecommendationService)`:
   bootstrap/scrape/classify/channel-graph helpers (§3).
4. `api/routers/layer_network.py` — endpoints of §6.
5. `tests/test_layer_scrape_service.py`, `tests/test_layer_network_api.py`.

### Modified files (backend)
6. `domain/models.py` — add `layer_index: int | None = None` to `CollectionRun`
   and `RecommendationObservation`.
7. `domain/enums.py` — add `GraphProjection` (`CHANNEL`/`VIDEO`) and
   `RelationStatus` (`NEW_VIDEO`/`EXISTING_VIDEO`/`NEW_CHANNEL`/
   `EXISTING_CHANNEL`/`CONNECTED`/`DISCONNECTED`/`SKIPPED_DUPLICATE`).
8. `persistence/base.py` — `LayerRunRepository` ABC; add `layers` to
   `Repositories`.
9. `persistence/excel_repository.py` — construct `LayerRunRepository` in
   `build_excel_repositories`; `layer_index` columns arrive automatically via
   `headers_for`/`ensure_sheet` (§2.1).
10. `services/recommendation_service.py` — `layer_index` kwarg on
    `collect_recommendations`/`collect_recommendations_for_videos`,
    `_begin_recommendation_run`, `_complete_video_result` (stamp edges).
11. `services/network_analytics_service.py` — `layer_index` filter on `edges()`/
    `graph()`; new `channel_graph()` + `ChannelGraphNode`/`ChannelGraphEdge`/
    `ChannelGraphPayload`.
12. `api/schemas.py` — request models (`LayerBootstrapRequest`,
    `LayerScrapeRequest`) + `LayerRunPayload` aliases if not in `layer_models.py`.
13. `api/app.py` — wire `"layer_scrape": LayerScrapeService(provider, repos,
    settings=settings)` into `_services()` (`app.py:138-161`); include
    `layer_network.router` (`app.py:312-332`).

### New files (frontend)
14. `ui/src/lib/network-layer-types.ts` — `LayerRun`, `NewRelationsReport`,
    `ChannelGraphPayload`, request/response types.
15. `ui/src/services/networkLayer.ts` — API + react-query hooks (§7.2).
16. `ui/src/components/features/network-layer/layer-stepper.tsx`.
17. `ui/src/components/features/network-layer/new-relations-panel.tsx`.
18. `ui/src/components/features/network-layer/layer-graph.tsx`.
19. `tests/e2e/network_layers.spec.ts`.

### Modified files (frontend)
20. `ui/src/components/features/network-full/full-network-view.tsx` — add the
    `"layers"` tab; wire stepper + relations panel + layer graph; add
    layer-query invalidation to the existing scrape mutations.

### No-change files (verified)
- `services/jobs.py` — generic, unchanged.
- `api/routers/network_ext.py` — unchanged (layer router is separate).
- `ui/src/components/features/network-graph.tsx` — reused as-is for both
  projections.
- `services/collection_service.py` — unchanged; its `_persist_comments` is
  reused via inheritance.

---

## 10. Decisions log / open questions

- **Layers = `layer_index` on runs+edges + a `LayerRun` summary record.** Chosen
  over (a) layer on `RecommendationObservation` only (loses run-level
  provenance) and (b) a full relational layer table (overkill for the Excel
  store; the report is the only derived data worth persisting).
- **Classification snapshot is taken before the crawl writes**, so
  new-vs-existing is always relative to the *pre-crawl* network, matching the
  researcher's mental model ("what did this crawl add?").
- **Job result stays a list of `CollectionResult`** so `GET /jobs/{id}/result`
  is untouched; the layer report lives in the `LayerRun` record.
- **Target metadata + comments are fetched live per new video.** Accepts
  per-layer `extract_video` cost under the shared rate limiter. Open question:
  should comment criteria for layers use `CollectionSettings` defaults or a
  full `CollectionSpec` (per-video criteria) in `LayerScrapeRequest`?
- **Disconnected components are rare but real** (§5.3). Confirm the "record a
  new video's own recommendations in the same layer pass" behaviour: if layer
  crawls are strictly frontier-only, `DISCONNECTED` will almost never fire —
  keep the classifier anyway (it is cheap and the researcher explicitly asked
  for it).
- **Layer scoping of existing `/network/graph`/`/network/metrics`**: the layer
  graph endpoint serves the layer slice; the global network tabs keep their
  existing `run_id` semantics. Should `/network/graph` also accept
  `layer_index` for cross-tab consistency? (Recommended yes, trivial filter.)
- **Bootstrapping**: a seed `LayerRun` may be created from any run (channel/
  video/recommendation). Confirm the seed run is the *most recent* run when the
  researcher does not pick one.
