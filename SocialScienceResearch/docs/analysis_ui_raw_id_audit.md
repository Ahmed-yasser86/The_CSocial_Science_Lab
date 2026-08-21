# Raw Entity-ID Display Audit — Research Workspace UI

**Deliverable:** Research + UI/UX audit only (no code changed).
**Scope:** Every place a raw entity id (`video_id`, `channel_id`, `run_id`, `dataset_id`,
`sample_id`, `comment_id`, `observation_id`) is rendered as user-facing display text
WITHOUT an accompanying human-readable label (video title, channel title/name, run name,
dataset name, sample name, comment author).

**Method:** Source of truth is `ui/src/app/**/*.tsx` (App Router pages) and
`ui/src/components/features/**/*.tsx`. Data shapes verified against `ui/src/lib/types.ts`,
`ui/src/lib/network-full-types.ts`, `ui/src/lib/sample-types.ts`, `ui/src/lib/dataset-types.ts`,
and `ui/src/services/api.ts`. Findings are classified **HIGH** (common page, prominent raw id,
fix readily available) / **MEDIUM** (less prominent, or fix requires a small lookup) / **LOW**
(adjacent metadata already present, or id is the only identifier the model exposes).

---

## 1. Run pickers — raw `run_id` as the only option label (HIGH)

Runs have a user-facing `name` field (`CollectionRun.name`, types.ts:65), but every run
selector across the network feature renders only the raw `run_id`.

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `network-summary-view.tsx` | 123, 132-133 | `<SelectItem>{r.run_id}</SelectItem>` | `{r.name ?? r.run_id}` (and same in the `items` array) |
| `ego-network-view.tsx` | 240, 249-250 | `<SelectItem>{r.run_id}</SelectItem>` | `{r.name ?? r.run_id}` |
| `network-full/full-network-view.tsx` (`RunPicker`) | 367, 374-377 | `<SelectItem>{id}</SelectItem>` | Map `id → name` from the already-loaded `useRuns()` data; render `name ?? id` |
| `network-full/full-network-view.tsx` (temporal toggles) | 246-257 | buttons render `{id}` | Same lookup; render `name ?? id` |

`network-graph.tsx:270-273` is the positive counter-example — it already renders
`[r.run_type, r.name, r.run_id].join(" · ")`.

**Impact:** On `/network`, `/network/videos/[videoId]`, and `/network/full`, users cannot tell
which collection run they are slicing by; a dozen opaque 20-char ids are indistinguishable.

---

## 2. Channel headers, h1s, and breadcrumbs — raw `channel_id` (HIGH)

A channel's human title is available via the `Channel` shape (`channel_id`, `title`,
api.ts:261-267) and via the channels list (`getChannels`, api.ts:257).

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `channel-workspace.tsx` | 41 | `<h1>{channelId}</h1>` | Resolve channel title (channels list lookup or a `title` on the overview payload) and render `title ?? channelId` |
| `app/channels/[channelId]/page.tsx` | 26 | breadcrumb `<span className="font-mono">{channelId}</span>` | Fetch channel metadata (server component) and render the title |
| `app/channels/[channelId]/history/page.tsx` | 26, 33 | breadcrumb + `<h1>{channelId}</h1>` | Same |

---

## 3. Video breadcrumbs — raw `video_id` (HIGH)

A video's `title` is available via `getVideo` (api.ts:292). The video workspace itself already
does the right thing (`video-workspace.tsx:42-44` renders `video?.title ?? videoId`).

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `app/videos/[videoId]/page.tsx` | 26 | breadcrumb `{videoId}` | Render `video.title ?? videoId` (server-side fetch, or keep the mono id but add the title beside it) |
| `app/network/videos/[videoId]/page.tsx` | 18 | breadcrumb `{videoId}` | Same |
| `app/videos/[videoId]/history/page.tsx` | 33-37 | breadcrumb `{videoId}` (h1 at 43-45 already uses `title ?? videoId`) | Same |

---

## 4. Run detail header and run breadcrumbs — raw `run_id` (HIGH)

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `run-detail.tsx` | 53 | header `<span className="font-mono text-sm">{run.run_id}</span>` | `{run.name ?? run.run_id}` next to the status badge |
| `app/runs/[runId]/page.tsx` | 18 | breadcrumb `{runId}` | Same |
| `research-desk.tsx` | 50 | recent-run cards `<code>{run.run_id}</code>` | `{run.name ?? run.run_id}` |
| `command-palette.tsx` | 212-218 | `{run.run_id} · {run.target_url}` | Prefer `run.name` when present; keep run_id as a mono suffix |

`run-ledger.tsx` is the positive counter-example — it already has a dedicated editable `Name`
column (`RunNameCell`, run-ledger.tsx:22-77) next to the `Run` column.

---

## 5. Ego-network Run table columns — raw `run_id` in cells (HIGH)

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `ego-network-view.tsx` | 158-159, 202-203 | `cell: (e) => <code>{e.run_id ?? "—"}</code>` | The component already loads `recommendationRuns` (useRuns) at line 38-40; build a `run_id → name` map and render `name ?? e.run_id` in the cell |

---

## 6. Project breadcrumbs — raw `project_id` / `item_id` (HIGH)

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `app/projects/[projectId]/page.tsx` | 18 | breadcrumb `{projectId}` | Render `project.name` (available via `useProject`) |
| `app/projects/[projectId]/items/[itemId]/page.tsx` | 22, 25 | breadcrumb `{projectId}` + `{itemId}` | Render project/item names (item has `name`, dataset-types.ts) |

---

## 7. Network-full slice badge & temporal labels — raw `run_id` (MEDIUM)

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `full-network-view.tsx` | 215-219 | `<code>{runId}</code>` slice badge | `runName ?? runId` from the loaded runs list |
| `network-full/temporal-overlay.tsx` | 75 | chart x-axis `label: slice.run_id` | Use run name as the axis tick when available |
| `network-full/temporal-overlay.tsx` | 133 | Run column `{slice.run_id}` | `name ?? run_id` |
| `network-full/edge-table.tsx` | 98 | Run cell `{edge.run_id ?? "—"}` | `edge.run_name ?? edge.run_id` (`GraphEdge` already carries `run_name`, network-full-types.ts:103) |

---

## 8. Dataset ids in project/manager lists — raw `dataset_id` (MEDIUM)

Datasets have a `name` (dataset-types.ts:8, shown correctly in `dataset-library.tsx:214`).

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `ProjectManager.tsx` | 277 | expanded project card `{datasetId}` mono | Map `datasetId → dataset.name` via `useDatasetList()` (already loaded) |
| `datasets/project-item-detail.tsx` | 214 | datasets list `{datasetId}` mono | Same |
| `datasets/quality-panel.tsx` | 54 | header `{quality.dataset_id}` mono | Pass the dataset name from the parent dialog (already selected) and render `name` with the id as a secondary line |

---

## 9. Collection result feedback — raw `run_id` (MEDIUM)

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `collect-target-form.tsx` | 486 | single-result `{r.run_id}` mono | The result payload only has `run_id`; enrich with the run name from `useRuns()` or leave id but add "View run details" context (button already present at 489-496) |
| `collect-target-form.tsx` | 531-535 | multi-result cards `{r.run_id}` | Same |

---

## 10. Sample cards / pickers — `sample_id` used where a name could exist (LOW → data-model gap)

The `Sample` type (sample-types.ts:72-85) exposes **no `name` field**, so `sample_id` is currently
the only identifier. These renderings are therefore defensible but worth flagging because a
friendlier label is cheap to add.

| Location | Line(s) | Renders | Suggested fix |
|---|---|---|---|
| `samples/sample-card.tsx` | 56 | card title `<p>{sample.sample_id}</p>` | Add a `name` field to `Sample`; render `name ?? sample_id`; until then compose `{entity_type} · {strategy}` as a human label |
| `samples/sample-overlap.tsx` | 49 | select buttons `{sample.sample_id}` | Same |
| `features/DatasetBuilder.tsx` | 233, 243 | sample rows `{sample.sample_id}` (entity badge + size adjacent) | Same; adjacent metadata already mitigates |
| `datasets/project-item-detail.tsx` | 170, 475 | sample ids in lists / add-dialog | Same |

---

## 11. Metadata-adjacent id columns (LOW — acceptable as-is)

These render a raw id but a human-readable column (title/name) is present in the same table,
so a user can always resolve what the id refers to:

- `recommendations-explorer.tsx:34-41` — `recommended_video_id` link with adjacent `Title`
  column (:44-49).
- `run-videos-browser.tsx:42-43` — `video_id` column with adjacent `Title` column (:26-38).
- `network-full/edge-table.tsx:83-85` — `source_video_id` / `recommended_video_id` mono cells
  with adjacent `Title` (:92-94) and `Channel` (:95-97) columns.
- `video-corpus-browser.tsx:157-162` — `video_id` column with adjacent `Title` (:143-155).
- `comparison-table.tsx:74-77` — `entity_id` with inline `row.title` when present; RunTable
  (:231) shows `run_id` (snapshot has no name field).
- `comments-browser.tsx:62` — `{video.channel_id}` as the "by" line; the `Video` type carries
  no channel title, so this is model-limited (LOW).
- `coverage-panel.tsx:116` — "Last collection" link `{c.last_run_id}` mono (only id in payload).
- `dataset-library.tsx:136-139` — dataset dialog shows `name` as title and `dataset_id` as the
  mono description line — this is the desired id-beside-name pattern.

---

## 12. Intentional raw-record surfaces (accepted — NOT defects)

The Explorer and provenance views are explicitly raw-record browsers; rendering the literal id
is their purpose and changing it would hide information:

- `explorer/paginated-data-table.tsx:33-46` — `formatCellValue` defaults to `String(value)` for
  id columns; the id cell is a navigation link (`record-explorer.tsx:221-231`).
- `explorer/detail-drawer.tsx:48-53` — `entityId` as `DrawerTitle` with an entity-type badge.
- `explorer/provenance-panel.tsx:56, 67, 70, 73, 104-106, 154` — provenance chains are defined
  by ids (`first_observed_run_id`, `channel_id`, `parent/root_comment_id`, per-observation
  `run_id`); no human label is intended.
- `sampling/LivePreview.tsx:213` — preview lists sampled member ids (that is the sample).
- `sampling/ScopeSelector.tsx:73-77, 126` and `sampling/FilterPanel.tsx:461-464, 760-764` —
  these already show `name (id)` / `title (channel_id)` / `run_type run id` — correct pattern.
- `comment-tree.tsx:70` and `comment-tree-modal.tsx:88` — render `author_name ?? author_id`,
  never the bare `comment_id`.
- `run-detail.tsx:85` — "Target id" field links `{targetId}` with an explicit `Target id` label;
  the target URL is shown separately at :72.

---

## Prioritized fix list (P0 / P1 / P2)

### P0 — one-line fixes on common pages; metadata already in memory
1. `network-summary-view.tsx:123,132-133` — run selector label → `r.name ?? r.run_id`.
2. `ego-network-view.tsx:240,249-250` — run selector label → `r.name ?? r.run_id`.
3. `network-full/full-network-view.tsx:367,374-377` — RunPicker labels → `name ?? id`.
4. `network-full/full-network-view.tsx:246-257` — temporal run buttons → `name ?? id`.
5. `ego-network-view.tsx:158-159,202-203` — Run column cells → `runIdToName.get(id) ?? id`.
6. `channel-workspace.tsx:41` — h1 → `channelTitle ?? channelId`.
7. `app/channels/[channelId]/page.tsx:26` — breadcrumb → channel title.
8. `app/channels/[channelId]/history/page.tsx:26,33` — breadcrumb + h1 → channel title.
9. `app/videos/[videoId]/page.tsx:26`, `app/network/videos/[videoId]/page.tsx:18`,
   `app/videos/[videoId]/history/page.tsx:33-37` — breadcrumbs → `video.title ?? videoId`.
10. `run-detail.tsx:53`, `app/runs/[runId]/page.tsx:18` — header/breadcrumb → `run.name ?? run_id`.
11. `research-desk.tsx:50`, `command-palette.tsx:212-218` — recent-run labels → `run.name ?? run_id`.
12. `app/projects/[projectId]/page.tsx:18`,
    `app/projects/[projectId]/items/[itemId]/page.tsx:22,25` — breadcrumbs → project/item names.

### P1 — needs a small lookup or prop threading
13. `network-full/full-network-view.tsx:215-219` — slice badge → run name.
14. `network-full/temporal-overlay.tsx:75,133` — axis/table labels → run name.
15. `network-full/edge-table.tsx:98` — run cell → `edge.run_name ?? edge.run_id`.
16. `ProjectManager.tsx:277`, `datasets/project-item-detail.tsx:214` — dataset ids → dataset names.
17. `datasets/quality-panel.tsx:54` — dataset id → dataset name (prop from parent).
18. `collect-target-form.tsx:486,531-535` — result run ids → run name enrichment.

### P2 — id is the only identifier today, or adjacent metadata exists
19. `samples/sample-card.tsx:56`, `samples/sample-overlap.tsx:49`,
    `features/DatasetBuilder.tsx:233,243`, `datasets/project-item-detail.tsx:170,475` —
    add a `name` to `Sample` (data-model change) and render `name ?? sample_id`.
20. Metadata-adjacent id columns in §11 — leave as-is; optionally make the id a secondary
    line under the title instead of a parallel column.
