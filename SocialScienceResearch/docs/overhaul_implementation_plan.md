# Network Overhaul — Consolidated Implementation Plan

Derived from the three analysis docs (`docs/analysis_network_api.md`,
`docs/analysis_network_ux.md`, `docs/analysis_scraper_engine.md`).

## Goals
1. **Readable graph**: every node label = `[ID] + Channel Name + Video Title
   (+ thumbnails/metrics)`; stable layout; distinct visual roles; fixed
   tooltip; inspection drawer; one-action-per-gesture.
2. **Working filters**: "Filter by Run" + "Filter by Channel" (combined),
   fed by real enriched data (server-side filtering; options never derived
   from the rendered graph).
3. **Click-to-scrape**: single video node → recommendation scrape; run/cluster
   → bulk re-scrape; auto-persist results as datasets with lineage.
4. **Verification**: backend tests + UI typecheck/lint + Playwright E2E.

## Backend
### B1. `services/network_analytics_service.py`
- Delete the `_get_video_metadata` **mock**; add a repo-backed batch resolver
  (`repos.videos.get_video`, `get_latest_video_observations`, `repos.channels.get_channel`).
- Enrich `EdgeRow` with source + target metadata and run taxonomy:
  `source_title/source_channel_id/source_channel_name/source_thumbnail_url/
  source_views/source_likes/source_duration`, `target_channel_name/
  target_thumbnail_url/target_views/target_likes/target_duration`,
  `run_name`, `observed_at`.
- Fix `edges()` channel semantics: `channel_scope` (`source|target|either`,
  default `source`), match on **source channel** via resolved video metadata.
- Upgrade `ChannelProjection` to `[{channel_id, channel_name}]`.
- Add `graph(run_id, channel_id, channel_scope)` returning enriched nodes
  (video_id, title, channel_name, thumbnail, views, likes, duration, kind,
  degrees, run_ids, run_types) + edges + run/channel facets.
- Batch resolve `run_type`/`run_name` (one `list_runs()` pass, no N+1).

### B2. `services/recommendation_graph_service.py`
- Remove `_persist_graph_as_dataset` call from `build_graph` (read path must
  not write); keep it as an explicit public method.

### B3. Domain / persistence / schemas
- `CollectionRun.parent_run_id: str | None` (`domain/models.py`) + Excel row
  mapping + `api/schemas.py` `RunPayload.parent_run_id`.

### B4. `services/query_service.py` + `services/dataset_service.py`
- Implement `run_ids` scoping for recommendation rows
  (`_recommendation_rows(run_ids)`; `resolve_latest_rows` forwards it).
- Add `lineage` (trigger_run_id/parent_run_id/source_kind) to
  `Dataset._register` `source_projection`.

### B5. `services/recommendation_service.py`
- Extend `collect_recommendations(video_url, *, video_id=None,
  parent_run_id=None, dedupe_run_ids=None, reporter=None)`.
- Add `collect_recommendations_for_videos(video_ids, *, parent_run_id=None,
  channel_id=None, dedupe_run_ids=None, concurrency=None, reporter=None)`
  (one recommendation run per video, shared rate limiter, thread pool).
- Add `_scrape_video_task` and `_persist_run_dataset` (unify the inline
  auto-persist; name/lineage conventions from the scraper spec).

### B6. `api/app.py` (+ `api/routers/network_ext.py`)
- `GET /network/graph` (network_ext router).
- `POST /network/scrape/video` `{video_id, trigger_run_id?}` → job.
- `POST /network/scrape/run` `{run_id, dedupe?}` → job.
- `POST /network/scrape/channel` `{channel_id, trigger_run_id?, dedupe?}` → job.

## Frontend (`ui/`)
### F1. `networkFull.ts` / `network-full-types.ts`
- Enriched `EdgeRow` types; `getNetworkGraph(runId?, channelId?, scope?)`;
  `networkScrapeVideo/Run/Channel` API calls; pass `channel_id` to edges.

### F2. Redesigned graph (`components/features/network-graph/`)
- `network-graph.tsx` (rebuilt): canvas pill labels
  `[ID] · Channel · Title` (+ thumbnail + metrics), role shapes/colors
  (`root` square, `channel` hexagon, `recommendation` circle), degree-scaled
  radius, position cache + re-seed (no layout explosion), zoom-aware label
  decluttering, fixed-position React tooltip, pointer-area == pill rect.
- `filter-bar.tsx`: Run selector (grouped by run_type, name+id) + Channel
  selector (name+id) + active-filter chips; options from `useRuns()` /
  channels facet, never from rendered graph; `applyFilters` pure function.
- `node-tooltip.tsx`, `inspection-drawer.tsx` (scrape button + ego link),
  `legend.tsx`, `graph-datum.ts` (types + enrichment + `applyFilters`),
  `use-graph-positions.ts`.
- Click node → open drawer only. Scrape only via drawer button.

### F3. Views
- `full-network-view.tsx`: add `"graph"` tab embedding the redesigned graph
  fed by `GET /network/graph`.
- `ego-network-view.tsx`: merge enriched context into graph nodes; keep the
  run `Select` as server-side slice; use the new `NetworkGraph`.
- Add `NetworkFilterBar` to both.

### F4. `queries.ts`
- `useNetworkGraph(runId?, channelId?)`; `useNetworkScrapeVideo/Run/Channel`
  mutations that poll the job and invalidate network + runs + datasets keys.

## Tests
- Update `tests/test_network_analytics_service.py` (new `EdgeRow` fields,
  source-channel filter semantics, `GET /network/graph`).
- Add `tests/test_network_scrape.py` for the new endpoints/service (no live
  network: use a fake provider returning fixed recommendations).
- UI: `npm run typecheck` / `npm run lint`.
- E2E: extend `tests/e2e/network_visualizer.spec.ts` (filters render options,
  node click opens drawer without navigation, scrape fires once from drawer,
  tooltip is fixed-position, chips/Clear all).