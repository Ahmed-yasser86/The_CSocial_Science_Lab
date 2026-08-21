# Network Expansion: Scrape-All + Filters + Auto-Organization

Status: implementation plan
Feature owner: graph-rag-agent

## 1. Goal

Let a researcher expand the recommendation network from the Network tab, with
full control over **what** gets scraped, and automatically **organize** every
scrape action into its own persisted Project.

Concretely (user requirements):

1. A **"Scrape all recommendations"** button.
2. Before ANY recommendation scrape (per-video **or** all), a **scrape-filters
   dialog** controls what is scraped from the recommendations.
3. Per-video **and** all-videos expansion: scrape a video → its recommendations
   become graph neighbours → repeat to form deeper, more complex nets.
4. **Stats** about the expanded network: **overall** (global) and
   **customized per video**.
5. **Automatic organized storage**: any scrape/expansion action that produces
   new data is auto-bound to a run and stored in an organized container
   (one Project per action).

## 2. Locked scope (user decisions)

- **"Scrape all recommendations" targets**: all videos in the **current network
  slice** (the run/graph scope the researcher is looking at).
- **Auto-organization**: **one auto Project per action**, grouping that action's
  runs + datasets with lineage and the filters used.
- **Expansion depth**: **one hop per action, repeatable** (A → A's
  recommendations become neighbours; re-run / chain to go deeper).

## 3. Design: reuse the layer-scrape engine

The existing `LayerScrapeService` (docs/analysis_next_layer_scrape.md) already
provides: single-video + bulk recommendation scrapes, deep-enrichment of new
target videos, snapshot-based classification (new/existing videos, channels,
edges, components), a persisted anchor record, per-run auto-datasets, and a
scoped graph. We **extend** it rather than build a parallel system:

- Expansion actions reuse the `LayerRun` anchor store (marked with
  `config_json["expansion"] = {"kind": "video"|"all", "project_id", "filters"}`),
  so they are cheap reads, survive restarts, and stay separate from crawl layers
  (crawl-layer listing excludes expansion rows).
- A new **`ScrapeFilters`** object is threaded through the recommendation scrape
  so it actually controls the network work:
  - `max_recommendations_per_video` (top-N of each feed)
  - `collect_comments` + comment criteria (`comment_min_likes`,
    `comment_date_from`, `comment_date_to`, `max_comments_per_video`)
  - `dedupe` (skip edges already observed in scope)
  - `concurrency`
  - `projection` (video | channel)
  - `only_new_targets` (deep-enrich only new videos vs. refresh existing too)
- After an action completes, an **auto Project** is created:
  `Network expansion · <video_id | N videos> · <timestamp>`, holding a project
  item that links the action's recommendation runs and auto-persisted datasets
  (`ProjectItemService.add_datasets`).

## 4. Backend

### 4.1 Models (`domain/layer_models.py` additions + schemas)

- `ScrapeFilters` (request-side, `extra="forbid"`, defaults: collect_comments
  true, dedupe true, only_new_targets true, projection video).
- `ExpansionActionPayload` (response) = `LayerRunPayload` +
  `kind`, `project_id`, `filters`, `video_count`, `edge_count`.
- `VideoExpansionStats` — per-video: `video_id`, `title`, `channel_id`,
  `channel_name`, `recommendation_count` (out-degree in scope),
  `in_degree`, `new_targets`, `new_channels`, `new_edges`, `comments_collected`,
  `first_seen_at`.
- `ExpansionStats` — `action` (payload), `overall` (graph metrics over the
  action's subgraph: node/edge/channel counts, weakly-connected components,
  density, avg out-degree, comments), `videos` (per-video stats, sorted by
  `recommendation_count` desc).

### 4.2 Service (`services/layer_scrape_service.py` additions)

- `expand_video(video_id, *, filters, reporter=None) -> LayerRun`
- `expand_all_videos(video_ids, *, filters, parent_run_id=None,
  reporter=None) -> LayerRun`
- shared `_expand(...)` implementing the one-hop expansion pipeline:
  1. `_snapshot()` pre-crawl state;
  2. scrape recommendations for the source set (thread `filters` →
     `max_recommendations_per_video`, comment criteria, dedupe, concurrency);
  3. `_enrich_new_targets(...)` deep-enrich new targets (comment filters applied);
  4. `_classify(...)` → counts;
  5. persist the `LayerRun` anchor (config_json carries kind/filters/project_id);
  6. `_persist_expansion_project(action, run_ids, dataset_ids)` → auto Project +
     project item (never fails the action; logged on error).
- `list_expansions()`, `get_expansion(action_id)`.
- `expansion_stats(action) -> ExpansionStats` (networkx over the action's edges
  + persisted videos).
- `_resolve_slice(video_ids, run_id)` — resolve the "current network slice"
  (explicit video ids win; else the run's videos/sources).

### 4.3 `RecommendationService` small backward-compatible additions

- `collect_recommendations(..., max_recommendations_per_video=None)` and
  `collect_recommendations_for_videos(..., max_recommendations_per_video=None)`
  → passed to `_complete_video_result`, which truncates the normalized edge
  list to the top-N by feed `position` before persistence.

### 4.4 API (`api/routers/expansion.py`, registered in `api/app.py`)

- `POST /network/expansion/scrape-video` — body `{video_id, filters}` → job.
- `POST /network/expansion/scrape-all` — body `{run_id?, video_ids?, filters}`
  → job (scope = current network slice).
- `GET /network/expansion` — paginated actions (newest first).
- `GET /network/expansion/{action_id}` — one action payload.
- `GET /network/expansion/{action_id}/stats` — overall + per-video stats.
- `GET /network/expansion/{action_id}/graph` — the action's graph (video|channel).
- Validation: unknown action → 404; invalid filter values / empty scope →
  `ValueError` → 400 `invalid_argument` (app-level handler).

## 5. Frontend

- `ui/src/lib/network-expansion-types.ts` — TS mirrors.
- `ui/src/services/networkExpansion.ts` — hooks:
  `useExpansions`, `useExpansion`, `useExpansionStats`, `useExpansionGraph`,
  `useScrapeVideo`, `useScrapeAll` (job-submit + poll, mirroring
  `useCrawlNextLayer`).
- `ui/src/components/features/network-expansion/scrape-filters-dialog.tsx` —
  the pre-scrape dialog: scope summary, `max_recommendations_per_video`,
  `collect_comments` + min likes / date window, `dedupe`, `only_new_targets`,
  concurrency, projection; submit → job + toast + navigate to Expansion tab.
- `ui/src/components/features/network-expansion/expansion-panel.tsx` — a new
  **Expansion** tab in `full-network-view`: action list + per-action stats
  (overall KPI tiles + per-video stats table + link to the auto-created Project
  + the action graph).
- Wiring:
  - "**Scrape all recommendations**" button in the Graph tab toolbar
    (full-network-view) → opens the dialog scoped to the current slice.
  - The network-graph drawer's "Scrape recommendations" action now opens the
    same dialog for that video (via `onScrapeClick` → dialog), then submits to
    `POST /network/expansion/scrape-video`.

## 6. Testing

- **Backend unit** (`tests/test_expansion_service.py`): one-hop expand creates
  anchor + auto-project + item; filters applied (top-N truncation, dedupe,
  comment min-likes/date filters, only_new_targets); expand-all scope
  resolution; stats computation; crawl-layer listing excludes expansions.
- **Backend API** (`tests/test_expansion_api.py`): job-submit endpoints (400
  invalid_argument on bad scope/filters, 404 unknown action), GET action /
  stats / list contract. Regenerate OpenAPI snapshot; full backend suite green.
- **Frontend**: vitest for `ScrapeFiltersDialog` + `ExpansionPanel` (mocked
  hooks); `tsc --noEmit` + `npm run lint` clean.
- **E2E** (`tests/e2e/network_expansion.spec.ts`): page renders the Expansion
  tab; filter dialog opens from the graph drawer and from the Scrape-all
  button; stats endpoint contract; defensive skips when no videos/comments.