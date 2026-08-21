# Network Graph UX Redesign — Research & Design Doc

**Sub-Agent B deliverable (research + UI/UX design only, no code).**
Scope: redesign the YouTube "Recommendation Network" graph for researcher-grade readability,
provable metadata, stable layout, distinct visual roles, and safe interactions.

---

## 1. Audit of the current graph

Source of truth: `ui/src/components/features/network-graph.tsx`, `ego-network-view.tsx`,
`full-network-view.tsx`. Verified against data types in `ui/src/lib/types.ts`,
`ui/src/lib/network-full-types.ts`, and `ui/src/services/api.ts`.

### 1.1 Node rendering — raw IDs and 5px dots
- `NetworkNode` (network-graph.tsx:15-25) *declares* `channel`, `thumbnail`, `views`, `likes`,
  `duration` — but the only producer, `EgoNetworkView`, populates **only** `id`, `title`, `kind`,
  `value` (ego-network-view.tsx:68-87). `channel`, `thumbnail`, `views`, `likes`, `duration`
  are always `undefined`, so every node is drawn as an anonymous `arc(x, y, 5)` dot or a
  16×16 thumbnail blit (network-graph.tsx:197-209). Users see raw YouTube IDs with zero context.
- The custom `nodeCanvasObject` **disables** the library's built-in rendering, so the
  `nodeLabel` accessor (network-graph.tsx:193-196) never draws permanent text either. There is
  no label painting anywhere on the canvas.
- Thumbnail drawing is broken by construction: `new Image(); img.src = ...; ctx.drawImage(img,…)`
  (network-graph.tsx:200-202) reads the image **before it has loaded**, so frames are blank, and a
  fresh `Image` is allocated every frame (GC pressure + no redraw on load).
- `nodePointerAreaPaint` uses a fixed 8px radius (network-graph.tsx:210-215) that is smaller than
  the labels we need; hit-targets and visuals are inconsistent.

### 1.2 Layout — no label/overlap control
- Only `nodeRelSize={5}` and `cooldownTicks={120}` are tuned (network-graph.tsx:174, 217).
  Defaults for `linkDistance`/`charge`/`collisionRadius` leave nodes overlapping; no seeding, no
  hierarchical placement, no pre-simulation positioning. On hundreds of nodes this is a hairball.
- `value` is 1–3 (ego) and feeds `nodeVal`, but sizing is not visually legible and no radius
  accessor is defined.

### 1.3 Tooltip — canvas coords vs page coords
- The tooltip is a DOM `<div id="node-tooltip">` styled `absolute` (network-graph.tsx:257) whose
  `left/top` are set to `node.x + 20 / node.y + 20` (network-graph.tsx:242-243). `node.x/y` are
  **internal graph units** (already transformed by the engine's zoom/pan), while `absolute`
  positioning resolves against the nearest positioned ancestor in **CSS page space**. The result is
  a tooltip that appears far from the node, or off-screen, and it jumps during pan/zoom.
- Content is injected via `element.innerHTML` (network-graph.tsx:231-239) — not React-idiomatic,
  an XSS surface for untrusted video titles, and defeats virtualized/portaled rendering. Visibility
  is toggled with raw `style.display`, which races with CSS `hidden`.

### 1.4 Filters — derived from data that lacks the fields
- Channel/run options are extracted **from the rendered nodes and links** (network-graph.tsx:75-88).
  Because ego nodes carry no `channel` and ego links carry no `runId`, **both dropdowns render
  empty** in the actual app. The filters cannot even show options for the data they must filter.
- The node filter (network-graph.tsx:90-101) drops any node that lacks a link in the selected run,
  while the link filter (network-graph.tsx:103-112) keeps a link if *either* endpoint's channel
  matches. This can keep edges whose endpoints were deleted → `react-force-graph` gets links to
  missing nodes → invisible geometry and a broken layout.
- Every filter toggle rebuilds `graphData` (network-graph.tsx:116-134) → the force simulation
  restarts from scratch → the layout "explodes" on each interaction.
- Dead code: a duplicate unused `useMemo` at network-graph.tsx:59-72.

### 1.5 Click handling — navigation AND scrape on one click
- `onNodeClick` (network-graph.tsx:219-225) calls **both** `onNodeClick(id)` — which does
  `window.location.href = /network/videos/{id}` (ego-network-view.tsx:60-62) — **and**
  `onScrapeClick(id)`, which starts a recommendation scrape job (ego-network-view.tsx:48-58).
  A single click therefore **navigates away and enqueues a collection run**. Both are heavy,
  deliberate actions; triggering them together is a UX hazard (accidental rescraping + page
  churn).

### 1.6 Supporting evidence
- The E2E spec (`tests/e2e/network_visualizer.spec.ts`) asserts a `CustomEvent('nodeClick')` that
  nothing dispatches and a `waitForResponse` for scrape on canvas click — it *codifies* the broken
  one-click behavior and never tests readability or filters.

---

## 2. Design principles

1. **Readability over density.** A node must be identifiable *without* clicking it: composite label
   (video ID + channel + title), thumbnail, and compact metrics. If labels don't fit at the current
   zoom, the graph must zoom *with* the label (labels scale with zoom) or degrade to a readable
   "focus mode" showing only the neighborhood.
2. **Provable metadata.** Every pixel carries provenance: run_id and run_type are displayed on the
   node/edge/tooltip, never hidden. A researcher must be able to state *"this edge was observed in
   run `r_123` at position #2"* from the canvas alone.
3. **No overlapping labels.** Use collision-based layout + label-aware node sizing + decluttering
   rules (hide labels below a zoom threshold; show title on hover/focus).
4. **Stable layout.** Simulation state must survive filter changes (position caching + seeding), so
   toggling a filter re-settles gently instead of "exploding".
5. **Distinct visual roles.** Role is encoded redundantly in shape, color, size, and legend so the
   graph is legible even in grayscale or for color-blind users.
6. **One action per gesture.** Navigate, scrape, and inspect are separate, deliberate actions.
7. **Accessible by construction.** DOM alternatives (node table), keyboard navigation, focus rings,
   reduced-motion fallback, theme-aware colors.

---

## 3. Node design

### 3.1 Composite datum (replace `NetworkNode`)
```
interface GraphNodeDatum {
  id: string;                     // video_id, or `channel:${channelId}` for hubs
  role: "root" | "channel" | "recommendation";
  videoId: string | null;
  channelId: string | null;
  channelTitle: string | null;    // resolved from useChannels()
  title: string | null;           // video title
  thumbnail: string | null;
  views: number | null; likes: number | null; duration: number | null;
  inDegree: number; outDegree: number;
  runs: string[];                 // run_ids that observed this node
  runTypes: RunType[];
  value: number;                  // derived, degree-scaled (drives radius)
}
```
Producers merge `VideoNetworkContext` / `useNetworkEdges` rows with `useChannels()` (titles) and,
where feasible, `getVideo(videoId)` (thumbnail/views/likes/duration). **Channel metadata is
available today via the edges endpoint** (`EdgeRow.channel_id`, edge-table.tsx:95-97) and
`/network/channels` (`ChannelProjection`) — it is simply not plumbed into the graph.

### 3.2 Node roles → shape/color/size
| Role | Meaning | Shape | Color (light / dark) | Size (r) |
|---|---|---|---|---|
| `root` | The video under inspection / run target | square with rounded corners + ring | `--chart-root` oklch(0.55 0.19 262.7) / oklch(0.72 0.17 262.7) | 14–18 (fixed) |
| `channel` | Synthetic hub for channel X (aggregates its videos) | hexagon | `--chart-channel` oklch(0.51 0.22 293.5) / oklch(0.66 0.20 293.5) | 10–16 (by video count) |
| `recommendation` | Video reached via an observed recommendation edge | circle | `--chart-rec` oklch(0.42 0.12 145) / oklch(0.62 0.14 145) | 6 + 10·√(degree/maxDegree), clamped ≤ 14 |

**New CHART_VARS to add** in `ui/src/lib/colors.ts` (+ `globals.css` custom props for both
themes): `root`, `channel`, `rec`. Reuse existing `accent`/`accent2` for auxiliary highlights and
`link` for edges. All colors resolve through `resolveChartColors()` (already theme-aware) at
accessor-call time; a `useTheme()`-keyed `useMemo` (the pattern already at network-graph.tsx:115)
forces re-resolve on toggle.

### 3.3 Canvas label drawing (label = pill + text)
Replace the 5px dot with a `nodeCanvasObject` that draws:
1. Thumbnail clipped to a rounded rect (12–28px), **only when `img.complete && img.naturalWidth`**,
   with thumbnails preloaded into a `thumbCache = useRef<Map<string, HTMLImageElement>>()` via
   `img.decode().then(() => forceRefresh())` — fixes the load-order bug and stops per-frame
   allocation.
2. Rounded pill behind the text: `roundRect(x, y, w, h, r)` filled with `canvasColors.card`
   (≈ `var(--card)` at 0.92 alpha), 1px stroke of the role color. Width = `measureText(ellipsized)`.
3. Text: **title (bold, `canvasColors.ink`)**, then a muted line `channelTitle`; the raw `id` is
   always present as monospace on the second line when no title/channel exist (never show a bare ID
   without a fallback explanation). Metrics line `views · likes · duration` using
   `formatCompact`/`formatDuration`.
4. A `HIDDEN_LABELS` rule: below `zoom < 0.6` draw dots + role color only; on hover/focus the full
   label re-appears. This satisfies "no overlapping labels" at scale.
5. `nodePointerAreaPaint` uses the *actual* rendered pill rect (label-width-aware), not a fixed 8px
   circle.

### 3.4 Edge classification
| Edge kind | Meaning | Style |
|---|---|---|
| `observed` | A recommendation observed in a run (`source → recommended`, `position` known) | solid, width = 1 + 0.5·√(observedCount), opacity 0.45 |
| `channel` | Ownership: video `belongs to` channel hub | dashed `[4,3]`, `canvasColors.faint` |
| `run` | Grouping: video `was collected in` run hub (only in cluster/full views) | dotted `[2,3]`, low opacity |
Run provenance rendered as a small `run:r_123 · #2` tag on the hover tooltip and inspection drawer,
never baked into the node.

---

## 4. Layout strategy

### 4.1 Mode A — hierarchical/tree layout for ego (1→N)
For `/network/videos/{id}` (small N), pre-seed positions by BFS depth around the root before the
simulation starts, then run a gentle settle:
- Seed: root at `(0,0)`, depth-1 (sources/recommendations) on ring radius `r₁ = 140`, depth-2 on
  `r₂ = 260`, angular slots = `2π / (children + 1)` with golden-angle jitter to de-overlap.
- `linkDistance = (link) => link.kind === "observed" ? 120 : 90` (observed chains push apart).
- `charge`: `d3.forceManyBody().strength(-220).distanceMax(320)`.
- `collisionRadius`: `node => radius(node) + 14` — the label margin guarantees label separation.
- `cooldownTicks = 120`, `cooldownTime = 2500`, `warmupTicks = 40`.
- `nodeCanvasObject` pill labels ride along (this is the 2d renderer — labels scale with zoom).

### 4.2 Mode B — degree-aware force layout for full network
For the `/network/full` graph tab (potentially thousands of nodes), never render all labels:
- Same charge/collision as Mode A but with **degree-scaled radius** and labels shown only for the
  top-K by degree, plus everything in the hovered neighborhood.
- Add a **Focus mode**: selecting a node isolates its 1-hop neighborhood (all other nodes dimmed to
  `canvasColors.faint` at 0.12 alpha, edges at 0.1 alpha) so a researcher can read a local
  structure at any density.
- Provide controls: **Fit view** (re-`centerAt`/`zoom`), zoom slider, "reset layout" button
  (`graphRef.current.zoomToFit(400, 60)`).

### 4.3 Simulation stability (the "no explosion on filter" rule)
1. Capture node positions continuously: `onNodeDragEnd` and a throttled `onEngineTick` store
   `posCache: Map<id, {x,y,vx,vy}>`.
2. When the filter changes, build the new `graphData` and **re-seed surviving nodes** from
   `posCache` (missing nodes get random positions near the centroid). `react-force-graph` accepts
   `x/y/vx/vy` on input nodes, so seeding is declarative.
3. On filter change set `cooldownTicks = 40` (short settle) instead of a full restart.
4. Keep one `graphRef`; do **not** remount `<ForceGraph2D>` (no `key={filter}`) — data mutation is
   enough.

---

## 5. Interaction model

### 5.1 Hover → rich tooltip (fixed position)
- Component `<NetworkNodeTooltip node={hovered} />` rendered in a `fixed` div (`z-50`,
  `pointer-events-none`, `w-64`), positioned at **`event.clientX/clientY`** captured from an
  `onPointerMove` handler on the container div — NOT `node.x/y`. Flip to the other side of the
  cursor when `clientX + 270 > innerWidth`. This directly fixes the canvas-vs-page coordinate bug.
- Content: 96px thumbnail, title (line-clamp-2), `channelTitle` + `channelId` (mono), metrics row
  (`formatCompact(views)` · `formatCompact(likes)` · `formatDuration`), and a provenance line
  `run:r_123 · #2 · type=recommendation`. Pure React JSX, no `innerHTML`.
- `onNodeHover` sets/clears `hovered` (id + enriched datum). Debounce mount ~80ms; clear on
  pointerleave of the container.
- The existing base-ui `Tooltip` primitive is for DOM triggers and doesn't suit canvas hover; the
  manual fixed tooltip is the correct fit (the primitive stays available for buttons/legends).

### 5.2 Click node → INSPECTION DRAWER (no navigation, no scrape)
- `onNodeClick` opens `<InspectionDrawer node={selected} />` via the existing
  `Drawer`/`DrawerContent side="right"` (max-w-sm) primitives. Clicking a node **only** opens the
  drawer.
- Drawer layout:
  - `DrawerHeader`: thumbnail (16:9), `DrawerTitle` = video title (fallback `id`), subtitle =
    `channelTitle (channelId)` + mono `video_id`.
  - `DrawerBody`: metrics grid (`views`, `likes`, `duration`, `in/out-degree` — tabular-nums),
    **Observed runs** list (each run chip: `run_type` badge + `run_id` code + position), and
    `Badge variant="outline"` for `role`.
  - `DrawerFooter`: primary action **"Scrape recommendations for this video"** (→
    `useScrapeRecommendations("https://www.youtube.com/watch?v="+id)`, disabled while pending,
    `Toast` on start), and a secondary **"Open ego page"** `<Link href="/network/videos/{id}">`
    (navigation is now an explicit, separate action). Close via `DrawerClose`/Escape.
- For CHANNEL nodes the drawer shows channel identity + member count + "Rescrape this channel".

### 5.3 Click run/cluster → bulk re-scrape
- In the full-network graph tab, optional run hub nodes (`role: "run"`, dotted grouping edges) are
  clickable → confirmation dialog ("Queue recommendation scrapes for all N videos in run `r_123`?")
  → loops `useScrapeRecommendations` per unique `videoId`, showing progress via `Toast`.
- Same affordance on the active-filter chips (§6.4): "Re-scrape this run slice".

### 5.4 Separation rule
No single gesture navigates *and* scrapes. Navigation only via drawer links / breadcrumbs / table
rows; scrape only via drawer button or explicit bulk action.

---

## 6. Dual-axis filtering UI

### 6.1 Component
`<NetworkFilterBar>` (new, `ui/src/components/features/network-graph/filter-bar.tsx`) used by both
the full graph tab and the ego view. Two `Select`s plus a summary chip row.

### 6.2 Run selector (grouped by run type)
- Options come from **`useRuns()`** (CollectionRun has `run_type`, `name?`, `target_video_id`,
  `target_channel_id` — types.ts:47-66), grouped into `SelectGroup`s labeled
  "Channel runs" / "Single-video runs" / "Recommendation runs".
- Item label: `run.name ?? run.target_video_id ?? run.target_channel_id ?? run.run_id`, with the
  `run_id` shown as trailing `<code>` so both human and machine identifiers are present.
- Default option `__all` labeled **"All runs"**. Selecting a run with no name still shows the run_id
  (never an empty-looking row).

### 6.3 Channel selector
- Options from **`useChannels()`** (channel_id + title) intersected with
  `getChannelProjection(runId)` when a run is active (so options reflect the slice). Label:
  `channel.title ?? channel.channel_id` + mono `(channel_id)`.
- Default option `__all` labeled **"All channels"**.

### 6.4 State management
```
interface FilterState { runId: string | "__all"; channelId: string | "__all"; }
```
- `useMemo`-derived option lists and a memoized `applyFilters(data, filterState)` pure function —
  **never derive options from the rendered graph** (the root cause of the current empty dropdowns).
- Intersection semantics: keep node `n` iff it participates in ≥1 edge whose `runIds` matches the
  selected run (if set) AND `n.channelId` matches the selected channel (if set). CHANNEL hubs are
  retained when any member video matches; ROOT nodes always retained when the view has a focus.
  Edges are emitted **only if both endpoints survive** (eliminates ghost links).
- Zero-result → `EmptyState` ("No nodes match the combined filters"), never a crash; the two
  `Select`s keep their values so the researcher can adjust.
- Active-filter summary: chip row below the selects —
  `<Badge variant="outline">{runLabel}<button aria-label="clear run" onClick={()=>clearRun()}/></Badge>`
  with an X on each non-default filter + a "Clear all" ghost button. The chips double as the bulk
  re-scrape trigger (§5.3).
- **Layout-engine safety**: filtering only replaces the `graphData` array; the `graphRef` persists,
  positions are re-seeded from `posCache` (§4.3), and the component never remounts on toggle.

---

## 7. Page architecture

### 7.1 `/network` (summary — `network-summary-view.tsx`)
- Keep KPIs + ranking charts/tables. No graph here — it's the aggregate landing page. Add a header
  CTA `<Link href="/network/full">` labelled **"Open full network analytics + graph"**.

### 7.2 `/network/full` (add a Graph tab to `full-network-view.tsx`)
- Extend the tab union to `"metrics" | "temporal" | "edges" | "graph"` (full-network-view.tsx:32,86-91).
- New tab content `<NetworkGraphTab runId={runId} />`:
  - **Data**: build nodes/edges from `useNetworkEdges(runId)` (paginate all pages; EdgeRow already
    carries `channel_id`, `title`, `position`, `run_id`) + `useChannelProjection(runId)` for hub
    aggregation + `useChannels()` for channel titles. Recommended (cleaner) backend addition:
    `GET /network/graph?run_id=` returning `{ nodes: GraphNodeDatum[], links: GraphLinkDatum[] }`
    so the client never assembles a thousand-node graph from paginated edges.
  - **Filters**: the page's existing `RunPicker` stays the server-side slice; inside the tab add
    `NetworkFilterBar` for the client-side channel subset. Layout Mode B (§4.2) + Focus mode.
  - Embed the redesigned `NetworkGraph` (new unified component) with `height = 520`.
- Temporal/edges/metrics tabs unchanged; their run slice selector is unaffected.

### 7.3 `/network/videos/{id}` (ego — `ego-network-view.tsx`)
- Keep the existing run `Select` as a **server-side data slice** (`useNetworkVideoContext(videoId,
  runId)` already refetches). Add `NetworkFilterBar` *below* it for client-side channel subsetting
  so the researcher can combine "run slice + channel subset".
- `NetworkGraph` fed by the merged context (now with channel/thumbnail/metrics enrichment), `role:
  root` for `videoId`; in/out neighborhoods in `role: recommendation`; optional CHANNEL hubs when
  multiple videos share a channel. Layout Mode A.
- Keep the existing "Recommended by / Recommends" `DataTable`s as the accessible DOM alternative and
  the secondary navigation surface (rows link to ego pages; no scrape on row click).

### 7.4 Component/file plan
- `ui/src/components/features/network-graph/network-graph.tsx` (rebuilt; unified, SSRed via
  `next/dynamic` as today).
- `network-graph/filter-bar.tsx`, `network-graph/node-tooltip.tsx`,
  `network-graph/inspection-drawer.tsx`, `network-graph/graph-datum.ts` (types + enrichment +
  `applyFilters`), `network-graph/use-graph-positions.ts` (posCache hook), `network-graph/legend.tsx`.
- `network-full/network-graph-tab.tsx` (the `/network/full` Graph tab).

---

## 8. Accessibility + dark mode

- **Colors**: all node/edge colors via `resolveChartColors()`; labels use `ink` on a `card`-tinted
  pill (contrast ≥ 4.5:1 for text, ≥ 3:1 for role fills). Role is always redundantly encoded by
  shape (square/hexagon/circle) so color is never the only channel. New `root`/`channel`/`rec`
  CHART_VARS get explicit oklch values per theme in `globals.css` (§3.2).
- **Keyboard**: the canvas wrapper gets `tabIndex={0}`, `role="application"`,
  `aria-label="Recommendation network graph"`. A hidden/offscreen node list (the existing
  DataTables on the ego page, plus a new DOM list on the graph tab) provides Tab order; arrow keys
  pan, `+`/`-` zoom, `Enter` on a focused node opens the drawer, `Escape` closes it (base-ui
  Drawer default). All buttons keep `focus-visible:ring-3 focus-visible:ring-ring/50` (existing
  convention throughout the codebase).
- **Reduced motion**: under `@media (prefers-reduced-motion: reduce)` disable force animation —
  seed positions deterministically, set `cooldownTicks = 0` and draw statically; suppress tooltip
  slide-in animations (the tw-animate-css classes are already gated in the primitives).
- **Dark mode**: colors are re-resolved on `useTheme()` change (existing pattern at
  network-graph.tsx:114-115); thumbnails and pills carry their own alpha so they read on both
  backgrounds. The tooltip and drawer use `bg-popover`/`text-popover-foreground` and
  `bg-card`/`text-card-foreground` respectively (theme tokens already defined).
- **E2E updates** (`tests/e2e/network_visualizer.spec.ts`): replace the fake `CustomEvent`/canvas-
  hover assertions with: (1) filter selects render non-empty grouped options; (2) clicking a node
  opens the inspection drawer and does **not** navigate; (3) scrape fires only from the drawer
  button, once; (4) tooltip appears near the pointer (fixed-position element with expected text);
  (5) active-filter chips appear and "Clear all" restores the full graph.

---

## Decision log / open questions
- `VideoNetworkContext` lacks `channel_id`/thumbnail — enrichment relies on `useNetworkEdges` +
  `useChannels()` today, or a new `GET /network/graph` endpoint (preferred for the full tab).
- Channel hubs ("synthetic nodes") are opt-in: default OFF on ego (keeps the 1→N tree clean), ON in
  the full graph tab where channel-level aggregation is the research question.
- Default network size guard: if a slice exceeds ~1,500 nodes, the graph tab offers "build anyway"
  (with Mode-B decluttering) instead of silently rendering a hairball.