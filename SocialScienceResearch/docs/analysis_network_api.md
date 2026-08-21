# Network Feature — API + Data-Model Analysis (for refactor)

Scope: research only. No code changes. Findings are grounded in the current
codebase (`SocialScienceResearch` at commit time of this analysis). All paths
are relative to `SocialScienceResearch/`. Line numbers were read from the
working tree and should be re-verified when the refactor starts.

API prefix everywhere below is `/api/v1/social-science` (default,
`api/app.py:220`, `settings.api.prefix`).

---

## 1. Data model inventory

### 1.1 `CollectionRun` — `domain/models.py:39-66`
Fields: `run_id`, `run_type`, `target_url`, `target_channel_id`,
`target_video_id`, `started_at`, `finished_at`, `status`, `provider`,
`provider_version`, `config_json`, `entities_discovered/succeeded/existing/failed`,
`comments_collected`, `notes`, `name`.

- `run_type: RunType` (`domain/enums.py:30-35`): `CHANNEL="channel"`,
  `VIDEO="video"`, `RECOMMENDATION="recommendation"`.
- `target_channel_id` is set for channel runs (`services/collection_service.py:399`);
  `target_video_id` for video and recommendation runs
  (`collection_service.py:775`, `services/recommendation_service.py:80`).
- `name` is the researcher-editable label (`api/app.py:441-449`).

### 1.2 `Video` — `domain/models.py:127-157`
`video_id`, `url`, `channel_id`, `title`, `description`, `duration` (seconds),
`upload_date`, `upload_timestamp`, `tags`, `categories`, `language`,
`live_status`, `availability`, `age_limit`, `is_short`, `thumbnail_url`,
`chapters_json`, `transcript_path/status/lang`, `first_observed_run_id`, `raw_json`.

Time-varying stats live on `VideoObservation` — `domain/models.py:160-173`:
`view_count`, `like_count`, `comment_count`, `favorite_count`.

### 1.3 `Channel` — `domain/models.py:89-109`
`channel_id`, `url`, `title`, `description`, `handle`, `is_verified`,
`avatar_url`, `banner_url`, `country`, `joined_date`, `first_observed_run_id`,
`raw_json`. Time-varying stats on `ChannelObservation` (`models.py:112-124`).

### 1.4 `RecommendationObservation` (the edge row) — `domain/models.py:215-235`
```
observation_id, collection_run_id, source_video_id, recommended_video_id,
position, status, channel_id, title, observed_at, raw_json
```
Crucial semantics:
- **`channel_id` and `title` describe the RECOMMENDED (target) video only.**
  The source video's identity is just `source_video_id`. The observation row
  carries **no source metadata at all** and **no target thumbnail/views/likes/
  duration**.
- `channel_id`/`title` are populated at scrape time by
  `acquisition/normalization.py:342-375` (`normalize_recommendations`); they
  come from whatever the provider returned and are frequently `None`
  (see §3.3).
- `raw_json` holds the mapped provider entry dict (usually just
  `id`/`title`/`channel_id`, per `acquisition/up_next.py:145-179`), so even
  the raw payload rarely carries thumbnails/stats.

### 1.5 How entities relate to edges
- A recommendation edge is a pure observed relationship
  `(collection_run_id, source_video_id, recommended_video_id)` — unique tuple
  (`models.py:218-221`). It is **not** a foreign-key to `Video`/`Channel`.
- **Source videos** are usually persisted as `Video` rows: a recommendation
  run upserts the source video + a `VideoObservation`
  (`services/recommendation_service.py:76-79`); a channel run with
  `scrape_recommendations` persists every channel video first
  (`collection_service.py:494`).
- **Recommended (target) videos are NOT persisted as `Video` rows.** Only the
  edge is saved (`recommendation_service.py:119-121`,
  `collection_service.py:584-586`). Consequently `repos.videos.get_video(rec_id)`
  returns `None` for nearly all targets, and no `VideoObservation` exists for
  them. This is the single biggest constraint on node metadata (see §4).
- Repo-level edge reads support **only** `source_video_id` + `run_id`
  (`persistence/base.py:253-260`, Excel impl `excel_repository.py:361-372`).
  There is **no repo-level channel filter** — channel filtering happens
  post-read in the service.

---

## 2. API endpoint inventory (everything that feeds the Network pages)

### 2.1 `api/routers/network_ext.py` (B6 router, lazy `NetworkAnalyticsService`)
| Endpoint | Params | Response shape |
|---|---|---|
| `GET /network/metrics` (line 79) | `run_id?`, `top_n?` (1..500, default 10) | `NetworkMetrics` (service model) |
| `GET /network/temporal` (line 93) | `runs` (comma-separated run ids) | `TemporalResult` |
| `GET /network/edges` (line 109) | `run_id?`, `channel_id?`, `cursor?`, `page_size?` (default 50) | `Paginated[EdgeRow]` |
| `GET /network/export` (line 133) | `format` (graphml/edgelist/gexf), `run_id?` | file download |
| `GET /network/channels` (line 153) | `run_id?` | `ChannelProjection` (`channels: string[]`, `edge_count`) |

`/network/edges` serialization: `paginated()` in `api/routers/common.py:39-61`
calls `e.model_dump()` per `EdgeRow`, so JSON items are **snake_case**
(`source_video_id`, `run_id`, …). `EdgeRow` fields today
(`services/network_analytics_service.py:60-73`): `source_video_id`,
`recommended_video_id`, `position`, `run_id`, `title`, `channel_id`,
`thumbnail_url`, `views`, `likes`, `duration`, `run_type`. The pagination key
(`network_ext.py:47-76`) is a 4-tuple `(source_video_id, position, run_id,
recommended_video_id)`.

### 2.2 `api/app.py` network routes
| Endpoint | Params | Response shape | Source |
|---|---|---|---|
| `GET /videos/{video_id}/recommendations` | `cursor?`, `page_size?` | `Paginated[RecommendationPayload]` (enriched with `run_type`) | `app.py:1050-1071` |
| `GET /network/recommendations/summary` | `run_id?`, `top_n?` | `NetworkSummaryPayload` | `app.py:1073-1082` |
| `GET /network/recommendations/{video_id}` | `run_id?` | `VideoNetworkContextPayload` (dataclass `__dict__`) | `app.py:1084-1090` |

`VideoNetworkContext` (`services/recommendation_graph_service.py:37-46`,
`app.py:1089-1090`) returns per-edge dicts with `source_video_id|recommended_video_id`,
`position`, `run_id`, `title`, `run_type` — **no channel, no thumbnail, no
stats** (`recommendation_graph_service.py:170-191`).

Notes:
- The UI no longer calls `/network/recommendations/summary`; `getNetworkSummary`
  in `ui/src/services/api.ts:366-373` points at `/network/metrics`. The old
  endpoint is orphaned dead weight.
- `/network/recommendations/{video_id}` *is* used by the ego-network page
  (`ui/src/services/api.ts:357-364`).

### 2.3 Collection / jobs endpoints
| Endpoint | Body/Params | Returns | Source |
|---|---|---|---|
| `POST /collect/channel`, `/collect/video`, `/collect/recommendations` | `{url}` | `CollectionResultPayload` | `app.py:315-339` |
| `POST /collect` (spec-driven) | `CollectionSpec` | `JobSubmitPayload` | `app.py:344-356` |
| `POST /scrape/recommendations` | `{video_url}` | `JobSubmitPayload` | `app.py:358-369` |
| `GET /jobs`, `/jobs/{id}`, `/jobs/{id}/result`, cancel | — | Job payloads | `app.py:371-420` |

The frontend click-to-scrape flow uses `POST /scrape/recommendations`
(`ui/src/components/features/ego-network-view.tsx:46-58`, builds
`https://www.youtube.com/watch?v=<id>`).

### 2.4 Runs / corpus pickers
- `GET /runs` (`app.py:425-432`): `run_type?`, cursor pagination →
  `Paginated[RunPayload]`. `RunPayload` (`api/schemas.py:156-175`) exposes
  `run_id`, `run_type`, `target_channel_id`, `target_video_id`, `name`, etc.
- `GET /runs/{run_id}` / `PATCH` / `/errors` / `/videos` (`app.py:434-481`).
- `GET /channels` — **duplicate route**: one in `api/app.py:486-507`
  (search `q`, `Paginated[ChannelPayload]`) and one in
  `api/routers/channels.py:76-93` (same path, richer `Channel` with
  subscriber/video/view counts). The router is included first
  (`app.py:302`), so the `channels.py` variant wins at runtime. This should be
  reconciled during the refactor.
- `GET /videos` (`app.py:577-593`), `GET /videos/{video_id}` (`app.py:595-600`).

### 2.5 Summary of who feeds what
- `/network/full` page → `/network/metrics`, `/network/temporal`,
  `/network/edges`, `/network/channels`, `/network/export`
  (`ui/src/app/network/full/page.tsx`, `ui/src/components/features/network-full/full-network-view.tsx`).
- `/network` page → `/network/metrics` (via `getNetworkSummary`) + `/runs`
  (`ui/src/components/features/network-summary-view.tsx:35-37`).
- `/network/videos/[videoId]` page → `/network/recommendations/{video_id}` +
  `/runs` + click-to-scrape via `/scrape/recommendations`
  (`ego-network-view.tsx`).
- `/videos/[videoId]` page → `/videos/{video_id}/recommendations`
  (`recommendations-explorer.tsx:17`).

---

## 3. Root-cause analysis of the broken filters

### 3.1 "Filter by Channel" and "Filter by Run" dropdowns are EMPTY
The dropdown options in `ui/src/components/features/network-graph.tsx` are
derived entirely from graph data:
- channels ← `nodes[].channel` (lines 63-64, 79-81)
- runs ← `links[].runId` (lines 67-68, 83-85)

But the only consumer that renders `NetworkGraph`,
`ui/src/components/features/ego-network-view.tsx`, builds:
- nodes as `{ id, title?, kind, value }` — **no `channel`, no `thumbnail`,
  no `views/likes/duration`** (lines 68, 76, 85);
- links as `{ source, target }` — **no `runId`** (lines 89-92).

So `availableChannels` and `availableRuns` are always `[]`; both `<Select>`s
render zero options and can never filter anything. The filters therefore "don't
work at all" by construction, regardless of backend behaviour.

### 3.2 Field-name mismatch `runId` vs `run_id`
`NetworkLink` declares `runId` (`network-graph.tsx:30`), but every backend
payload uses `run_id` (`EdgeRow`, `VideoNetworkContext.recommended_by[].run_id`,
`RecommendationEdge.run_id`). Even if `ego-network-view.tsx` mapped the API
`run_id` onto links it would have to translate to `runId`; it does neither
today. Standardize on one name (see §5/§6).

### 3.3 Backend `channel_id` filter semantic is wrong for the use case
`/network/edges` filters edges as
`if channel_id and edge.channel_id != channel_id: continue`
(`services/network_analytics_service.py:257`). Two independent problems:

1. **Semantic**: `edge.channel_id` is the channel of the **recommended**
   (target) video (`models.py:232`). Filtering on it yields "edges whose
   *target* belongs to channel X", not "videos of channel X and their
   recommendation trees". The requirement (§4/§6 of this doc, and
   `OVERHAUL_PLAN.md:29`) is the reverse — show channel X's videos as *sources*
   with their 1→N out-trees.
2. **Data availability**: on real scrapes `edge.channel_id` is frequently
   `None`. yt-dlp's own `recommended_videos`/`related` entries rarely carry a
   `channel_id`; the yt-search-python layer only maps `channel.id` when present
   (`yt_dlp_adapter.py:484-490`); the page-dump parser only sometimes resolves a
   byline channel id (`up_next.py:128-142`). With `channel_id=None`, the
   `!=` comparison drops **every** edge, so "filter by channel" returns an empty
   list even when the user somehow managed to pick a channel.

The backend unit tests pass only because they seed synthetic edges with explicit
`channel_id` values (`tests/test_network_analytics_service.py:35-58,186-198`)
and assert on target-channel semantics — the tests encode the buggy semantic and
never exercise real scrape output. `OVERHAUL_SUMMARY.md` ("channel filtering
✅ complete") is therefore misleading.

### 3.4 `networkFull.ts` never sends `channel_id`
`getNetworkEdges` builds `toQuery({ run_id: runId, cursor })` only
(`ui/src/services/networkFull.ts:40-47`); the `channel_id` query param the
backend exposes is never used by any UI code. The full-network edge table
(`edge-table.tsx`) therefore has no channel filtering at all.

### 3.5 Even if the UI mapped metadata, the backend would supply none
The ego-network graph (the only place the dropdowns render) is fed by
`/network/recommendations/{video_id}`, whose per-edge rows carry only
`position/run_id/title/run_type` (`recommendation_graph_service.py:170-191`).
There is no `channel_id` (source or target) and no run-level channel
information, so a channel filter would have nothing to match even after the
client-side wiring is fixed. The graph is also unreadable for the same reason:
nodes render as bare IDs (`ego-network-view.tsx:68`), titles only exist on the
single edge attribute, and no thumbnails/stats are present.

### 3.6 Minor defects found while tracing
- Dead duplicate `useMemo` computing and discarding channels/runs
  (`network-graph.tsx:59-72`).
- `NetworkAnalyticsService.edges()` performs a **N+1 `runs.get_run`** per edge
  to resolve `run_type` (`network_analytics_service.py:264-268`).
- `RecommendationGraphService.build_graph` calls
  `_persist_graph_as_dataset` on **every** call
  (`recommendation_graph_service.py:56-75,77-102`), i.e. every
  metrics/summary/temporal/video_context request creates a new dataset with an
  identical name ("Recommendation Graph — Run …"). `create_dataset` also
  ignores `run_ids` scoping (`services/dataset_service.py:98`). Not one of the
  two reported bugs, but it pollutes datasets and must be fixed in the same
  refactor.

---

## 4. Metadata gap (every node label must be `[ID] + Channel Name + Video Title (+ thumbnails/metrics)`)

### 4.1 What `EdgeRow` carries today
Only **target** metadata: `title`, `channel_id` (copied from the observation
row, `network_analytics_service.py:276-277`) and `thumbnail_url`, `views`,
`likes`, `duration` sourced from `_get_video_metadata`
(`network_analytics_service.py:278-281`). **`_get_video_metadata` is a MOCK**
(`network_analytics_service.py:296-316`) returning hardcoded dicts keyed on
the synthetic test ids `a/b/a2/…/v9`; for any real video id it returns `{}`, so
`thumbnail_url/views/likes/duration` are `None` in production.

A real `get_video_metadata` exists on the adapter (`acquisition/yt_dlp_adapter.py:401-416`)
but is **never invoked**: `NetworkAnalyticsService` is constructed with only
`repos` (`api/routers/network_ext.py:43`), and the provider is not wired in.

There is **no source metadata at all** on `EdgeRow` (no `source_title`,
`source_channel_id`, …). Neither endpoint video has a channel *name*.

### 4.2 What offline repository calls can supply (no live network)
- `repos.videos.get_video(video_id)` → `Video`: `title`, `channel_id`,
  `thumbnail_url`, `duration`, `upload_date`, `description`, `is_short`
  (`persistence/base.py:113-115`, model `domain/models.py:127-157`).
- `repos.videos.get_latest_video_observations([ids])` → one
  `VideoObservation` per id: `view_count`, `like_count`, `comment_count`
  (`persistence/base.py:137-145`, Excel impl `excel_repository.py:210-214`).
  **Batch — avoids N+1.**
- `repos.channels.get_channel(channel_id)` → `Channel.title` (= channel name),
  `handle`, `avatar_url` (`persistence/base.py:71-72`, model `models.py:89-109`).
- `repos.channels.get_latest_channel_observations([ids])` batch
  (`persistence/base.py:93-102`).

### 4.3 Reality check on coverage
- **Source videos: metadata is usually available offline.** Recommendation runs
  persist source video + observation (`recommendation_service.py:76-79`);
  channel-run sources are persisted and (when deep-enriched) observed
  (`collection_service.py:494,528-543`). So `source_title/source_channel_id/
  source_thumbnail/source_duration/source_views/source_likes` can be resolved
  from `repos.videos` + `repos.videos.get_latest_video_observations` for the
  1→N "channel X's videos" use case.
- **Recommended (target) videos: metadata is almost always absent offline.**
  They are never persisted as `Video` rows (§1.5). Offline you only have the
  edge's own `title`/`channel_id`/`raw_json`. Targets' thumbnails and
  views/likes/duration require either (a) live yt-dlp fetch per id
  (`yt_dlp_adapter.get_video_metadata`) — slow, rate-limit risk, should be
  batched/cached — or (b) a collection-time enrichment that persists target
  videos when edges are observed (design change in the collection workflow).
- **Channel names** require the channel entity; only ids exist on edges. When a
  channel was never collected (only its videos scraped via a channel run, or
  recommendations observed), `repos.channels.get_channel` returns `None` and the
  name is unknowable offline.

### 4.4 Blockers to flag
1. `_get_video_metadata` mock (`network_analytics_service.py:296-316`) must be
   deleted/replaced — it fabricates data, violating the module's
   "no fabrication" principle (`domain/models.py:16`).
2. `NetworkAnalyticsService` has no provider handle; if live metadata is wanted
   it must be injected via `get_service`/`create_app` wiring
   (`api/app.py:116-139`, `network_ext.py:39-44`).
3. Edge rows are the only truth for target metadata; persist `thumbnail_url`,
   `view_count`, `like_count`, `duration` (and channel name) onto
   `RecommendationObservation` at scrape time
   (`acquisition/normalization.py:342-375` + the provider mapping in
   `up_next.py`/`yt_dlp_adapter.py:456-491`) **or** accept live-fetch for
   targets.

---

## 5. Proposed API schema changes

### 5.1 New `EdgeRow` (backend `services/network_analytics_service.py:60-73`)
```
class EdgeRow(_Base):
    source_video_id: str
    source_title: str | None = None
    source_channel_id: str | None = None
    source_channel_name: str | None = None
    source_thumbnail_url: str | None = None
    source_views: int | None = None
    source_likes: int | None = None
    source_duration: int | None = None

    recommended_video_id: str
    target_title: str | None = None
    target_channel_id: str | None = None
    target_channel_name: str | None = None
    target_thumbnail_url: str | None = None
    target_views: int | None = None
    target_likes: int | None = None
    target_duration: int | None = None

    position: int | None = None
    run_id: str | None = None
    run_type: str | None = None          # "channel"|"video"|"recommendation"
    run_name: str | None = None          # CollectionRun.name (researcher label)
    observed_at: datetime | None = None
```
Keep `title`/`channel_id` as deprecated aliases only if needed for the edge
table; better to update the UI types in the same change.

**How to fill it** (service method, batch, offline):
1. `edges = repos.recommendations.list_recommendation_edges(run_id=run_id)`
   (already `excel_repository.py:361-372`).
2. Collect all distinct source + target ids; one
   `repos.videos.get_latest_video_observations(ids)` and one pass of
   `repos.videos.get_video(id)` (or a new batch `get_videos(ids)` if added to
   `VideoRepository`, `persistence/base.py:105-146`).
3. Collect distinct channel ids; one `repos.channels.get_channel(id)` pass (or
   `get_latest_channel_observations` if stats are wanted).
4. Run-type/name: one pass over `repos.runs.list_runs()` keyed by run_id
   (replaces the N+1 in `network_analytics_service.py:264-268`).
5. Target metadata falls back to the observation row's `title`/`channel_id`;
   targets with no `Video` row keep `None` thumbnails/stats (or trigger the
   optional live fetcher).

### 5.2 New enriched graph endpoint (serves the NetworkGraph directly)
Add e.g. `GET /network/graph` (in `network_ext.py`):
```
Query params: run_id?, channel_id?, channel_scope?=source|target|either,
              include_metrics?=false
Response (new pydantic model):
{
  "nodes": [ NetworkNodePayload ],
  "edges": [ EdgeRow ],                    # or slimmed {source,target,position,run_id}
  "runs":   [ {run_id, run_type, name} ],
  "channels":[ {channel_id, name} ],
  "summary": {node_count, edge_count, ...}  # optional, cheap re-use of metrics()
}
NetworkNodePayload {
  video_id, title, channel_id, channel_name, thumbnail_url,
  views, likes, duration, kind: "source"|"target"|"both"
}
```
This gives the UI **one call** to render nodes with `[ID] + Channel Name +
Video Title (+ thumbnails/metrics)` and populate the two filter dropdowns from
`nodes[].channel`/`edges[].run_id`. The graph service already rebuilds the
`nx.DiGraph` on demand (`recommendation_graph_service.py:56-75`); the new
endpoint enriches it with the batch metadata resolver instead of throwing
`model_dump`-of-dataclass rows at the client.

### 5.3 Filtering params that work together on the backend
`/network/edges` (and `/network/graph`) should accept:
- `run_id?: str` — restrict to edges observed in one run.
- `channel_id?: str` — see §6 for the exact semantic.
- `channel_scope?: "source" | "target" | "either"` (default `"source"`) —
  resolves the ambiguity once `channel_id` is present.
- `cursor?`, `page_size?` (edges only, keep the existing feed-rank key
  `network_ext.py:47-76`).

Both filters must be applied **server-side on the enriched rows** so pagination
stays correct, and so client code never has to reconstruct run/channel sets.

### 5.4 Run taxonomy exposure
`RunType` already distinguishes the three kinds (`domain/enums.py:30-35`).
Expose it consistently:
- `EdgeRow.run_type` (from `CollectionRun.run_type`, currently `network_analytics_service.py:263-268`).
- The `/runs` list already returns `run_type` + `target_channel_id` +
  `target_video_id` (`RunPayload`, `api/schemas.py:156-175`), so the UI can
  group runs into "channel runs / single-video runs / recommendation runs"
  without new endpoints. Add `run.name` (already on `RunPayload`, line 174) so
  dropdowns show the researcher label instead of opaque ids.
- The NetworkGraph can style nodes/edges by `run_type`
  (`network-graph.tsx` already has the plumbing concept per `OVERHAUL_SUMMARY.md:43`,
  but the data is never supplied today).

---

## 6. Filtering + pagination design

### 6.1 Combined semantics
`/network/edges` (and `/network/graph`) should apply, in order:
1. `run_id` filter on `edge.collection_run_id` (repo level, cheap,
   `excel_repository.py:370-371`).
2. Enrichment (batch video + channel metadata, §5.1).
3. `channel_id` filter on the **source channel** (default), i.e. keep an edge
   when `edge.source_channel_id == channel_id`. Because `RecommendationObservation`
   has no source channel column, resolve it via the metadata resolver
   (`repos.videos.get_video(source_id).channel_id`); fall back to the
   observation's `channel_id` only when the source row is missing and the
   source id equals the recommended id of a self-loop (rare). Provide
   `channel_scope=target|either` as an explicit opt-in so researchers can
   switch to "edges pointing into channel X" or "edges touching channel X".
4. Feed-rank sort + cursor pagination unchanged
   (`network_ext.py:47-76`, `services/pagination.py:104-136`).

Recommended default semantic: **`channel_id` matches the SOURCE channel**,
because the requirement is "show all videos of channel X with their 1→N
recommendation trees" (`OVERHAUL_PLAN.md:29`): every edge whose source belongs
to X, plus (for graph/tree rendering) the target nodes that edge points at —
even if those targets belong to other channels. This is the only reading that
keeps the tree rooted at channel X's videos. `target`/`either` are refinements,
never the default.

### 6.2 Why current behaviour is empty/incorrect (recap)
- Backend default matches `edge.channel_id` = **target** channel
  (`network_analytics_service.py:257`), which is usually `None` in real data
  (§3.3) → empty result set.
- UI filter options are derived from `nodes[].channel`/`links[].runId`, neither
  of which is populated (§3.1) → nothing selectable.

### 6.3 Channel filter should match channel NAMES, not just ids
The dropdown should display `channel_name` (from the channel repo) while the
query param stays `channel_id` (stable key). `/network/channels` should be
upgraded to return `[{channel_id, channel_name}]` instead of bare id strings
(currently `ChannelProjection.channels: list[str]`,
`network_analytics_service.py:141-153`), so the run-scoped channel picker is
human-readable. Keep the id as the value sent to `/network/edges`.

### 6.4 Pagination correctness notes
- `Paginated` envelope is fine (`services/pagination.py:75-87`); `total` is
  free because repositories return in-memory lists
  (`api/routers/common.py:39-61`).
- Filter first, then sort, then page (already the order in
  `network_analytics_service.edges()` + `paginated()`), so cursors remain
  stable for a fixed filter combo.
- When `run_id` is set, `edge.run_id` is constant per page; the sort key still
  includes it, which is fine but redundant. No change needed.
- Watch the position sort: `None` ranks must sort last and compare consistently
  between `_edge_key` (`network_ext.py:60-66`, uses `"~"`) and the service's
  final sort (`network_analytics_service.py:285-294`); they are consistent
  today — keep them in sync when extending `EdgeRow`.

---

## 7. Concrete refactor checklist (backend, derived from this analysis)

1. **Delete the mock**: replace `_get_video_metadata`
   (`network_analytics_service.py:296-316`) with a repository-backed batch
   resolver; optionally inject the acquisition provider for live target
   enrichment.
2. **Enrich `EdgeRow`** per §5.1; expose run taxonomy + `run.name`.
3. **Add `GET /network/graph`** (§5.2) returning nodes (with `[ID] + Channel
   Name + Title + thumbnails/metrics`) + edges + run/channel facets; add the
   `NetworkNodePayload`/graph response models to `api/schemas.py` (or the
   service module alongside `EdgeRow`).
4. **Fix `/network/edges` channel semantics** (§6): default source-channel
   match via enriched metadata, `channel_scope` param, and never drop edges on
   `None` when the filter is not actually matchable — return an explicit empty
   set only when the resolved channel genuinely has no edges.
5. **Upgrade `/network/channels`** to return names; add a `name` facet.
6. **Stop the dataset side-effect**: remove `_persist_graph_as_dataset` from
   `build_graph` (`recommendation_graph_service.py:56-75,77-102`) or gate it
   behind an explicit "persist graph" endpoint; decide run_ids scoping in
   `DatasetService.create_dataset` (`dataset_service.py:98`).
7. **UI (follow-on, for planning only)**: populate nodes with
   `channel`/`thumbnail`/`views`/`likes`/`duration` and links with `run_id`
   from the new `/network/graph` payload; fix the `runId`/`run_id` mismatch
   (`network-graph.tsx:30`); make `networkFull.ts` pass `channel_id`/`scope`.
8. **Tests**: update `tests/test_network_analytics_service.py` (channel filter
   semantics + real-metadata expectation, lines 186-198, 272-293) and add a
   `GET /network/graph` test; fix `OVERHAUL_SUMMARY.md`'s misleading
   "filtering complete" claim once real (non-synthetic) data is exercised.

---

## 8. Open questions for the refactor owner

- Do recommended (target) videos get persisted as `Video` rows going forward,
  or is live yt-dlp fetch (with cache) acceptable for target thumbnails/stats?
  This determines whether target metadata is offline or network-backed (§4.3).
- Should `channel_scope` be a single enum param or two booleans
  (`include_target_channel`, `include_source_channel`)? Enum is cleaner.
- Should `/network/recommendations/summary` be removed now that the UI uses
  `/network/metrics` (§2.2)?
- Should the duplicate `GET /channels` routes (`app.py:486` vs
  `channels.py:76`) be merged while touching this area?
- Dataset auto-persistence: per-request (today) is wrong; confirm the intended
  trigger (end of collection run only).