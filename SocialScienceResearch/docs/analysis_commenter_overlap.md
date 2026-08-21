# Commenters Overlap — Architecture Analysis & Implementation Spec

Scope: **architecture analysis only. No application code was written.** This
document is grounded in the working tree of `SocialScienceResearch/` (FastAPI
backend) and `SocialScienceResearch/ui/` (Next.js App Router). All paths are
relative to `SocialScienceResearch/`. Line numbers were read from the working
tree and should be re-verified at implementation time.

API prefix everywhere below is `/api/v1/social-science` (default,
`api/app.py:304`, `settings.api.prefix`).

Related user stories: `docs/user_story_commenter_behavioral_tracking.md`
(cross-video/cross-channel commenter tracking, identity resolution, reply
context) and `docs/user_story_multi_user_cohort_analysis.md` (shared
audiences, user×channel matrix, bridge users, Jaccard/similarity §8).

---

## 1. Grounding — how comments, authors and the graph actually work today

### 1.1 The `Comment` model (the only author-identity source)

`domain/models.py:177-198`:

```
comment_id: str
video_id: str
author_name: str | None
author_id: str | None          # STRONGEST IDENTIFIER, when present
comment_text: str | None
published_at: datetime | None
is_reply: bool = False
parent_comment_id: str | None
root_comment_id: str | None
is_author: bool | None          # True if the video uploader wrote it
first_observed_run_id: str
raw_json: dict[str, Any]
```

* **`author_id` is the strongest available platform identifier.** At
  collection time it is resolved as
  `raw.get("author_id") or raw.get("author_channel_id")`
  (`services/collection_service.py:179`, `_comment_criteria_row`), so a
  YouTube channel handle id (`author_channel_id`) is folded into `author_id`.
* **`author_name` is the display name only** (`raw.get("author")`,
  `collection_service.py:180`) and must never be used as the *identity*
  when `author_id` exists.
* `is_reply` / `parent_comment_id` exist → **threads are persisted**. `root_comment_id`
  is captured at first observation but is recomputed defensively by
  `CommentAnalyticsService._thread_roots` (`comment_analytics_service.py:248-269`).
* Excel persistence is fully round-tripped through
  `persistence/serialization.py` (`model_to_row`/`row_to_model`, datetime →
  ISO string, dict/list → JSON). The `comments` sheet is keyed by `comment_id`
  (`persistence/excel_repository.py:217-283`).

### 1.2 The author-identity convention already used in three places (and its drift risk)

| Location | Key rule |
|---|---|
| `persistence/author_repository.py:82-88` | `author_id or author_name` → single string key; `None` → excluded |
| `services/comment_analytics_service.py:150-159` | triple `(("id", author_id) or ("name", author_name) or ("unknown", ""))` — distinguishes id-backed vs name-backed rows |
| `services/sampling_service.py:798-800` (`_author_key`) | `author_id or author_name` |

`AuthorProfile` (`domain/models.py:259-283`) is the derived aggregate — one
row per key with `comment_count`, `video_ids`, first/last seen, `is_author`,
and the union of `author*` raw keys from `raw_json`. `AuthorRepository`
(`persistence/author_repository.py`) is a read-only projection; the `author`
entity is registered in `VariableRegistry` (`services/variable_registry.py:290-329`),
`ExplorerService` (`services/explorer_service.py:47-64`) and `QueryService`
(`services/query_service.py:369-385`).

**Conclusion:** a new overlap service must reuse the same priority —
`author_id` first, `author_name` fallback, exclude anonymous. I recommend a
single shared key function (see §4 D1) to stop the three existing copies
drifting.

### 1.3 Comment read paths available to a service (no new persistence needed)

`CommentRepository` (`persistence/base.py:148-204`, Excel impl
`excel_repository.py:217-283`):
* `list_comments(video_id=None)` → all comments (research scale, in-memory list)
* `list_root_comments`, `list_replies`, `list_replies_by_ids`
* `get_latest_comment_observations(ids)` → one batch scan for
  `like_count/reply_count/is_removed`

Batch metadata resolvers (reuse the `_MetadataIndex` pattern from
`network_analytics_service.py:246-290`):
* `repos.videos.list_videos()`, `get_latest_video_observations(ids)`
* `repos.channels.list_channels()`, `get_latest_channel_observations(ids)`
* `repos.runs.list_runs()`

No new repository method is required for the overlap feature. All overlap data
derives from `list_comments()` + the video→channel map
(`Video.channel_id`, `models.py:139`).

### 1.4 How the network graph is built

`RecommendationGraphService.build_graph` (`services/recommendation_graph_service.py`)
builds an `nx.DiGraph` over **recommendation edges** (source video →
recommended video, `RecommendationObservation` `models.py:216-236`).
`NetworkAnalyticsService.graph()` (`services/network_analytics_service.py:459-571`)
returns the enriched `NetworkGraph` payload (nodes with `[ID] + Channel Name +
Video Title + metrics`, run/channel facets) served by `GET /network/graph`
(`api/routers/network_ext.py:94-123`). **The existing graph is a video×video
recommendation projection — it contains no comment/author dimension.**

`/network/full` renders it (`ui/src/app/network/full/page.tsx` →
`FullNetworkView` → `NetworkGraph`, `full-network-view.tsx:195-337`).

### 1.5 Existing analytics services (what we build on, what to mimic)

* `services/analytics_service.py` — channel/video engagement, comment
  percentiles, velocity. Uses `StatisticsService`; "observed, never
  estimated" ethos (`models.py` docstring, `analytics_service.py:10-12`).
* `services/comment_analytics_service.py` — per-video participation
  (unique/repeat authors, Gini), reply/thread metrics, velocity decay. Has the
  `_author_key` triple convention (§1.2) and `StatisticsService.ratio` reuse.
* `services/comparison_service.py` — entity tables with explicit normalization
  (`none|per_1k|z_score`), percentile ranks, outliers. Good template for the
  pair-table + stat models (`EntityComparison`, `ComparisonMetricRow`,
  `_Base` with `extra="allow"`).
* `services/longitudinal_service.py` — run deltas/growth.
* `services/explorer_service.py` + `services/query_service.py` — row
  resolution (`resolve_latest_rows`) and pagination.
* `services/sampling_service.py:802-848` — **prior art for overlap**: an
  `AdvancedSamplingSpec.overlap` ("video"|"channel") filter that keeps
  comments whose author is active across ≥ `overlap_min` distinct
  video/channel units. This validates the video-vs-channel unit semantics we
  reuse, but it is a *sampling filter*, not an analytics surface.

**Statistics primitives** (`services/statistics_service.py`): `ratio(n,d)` is
None-safe (`statistics_service.py:353-362`); `mean`, `median`, `percentile`,
`gini`, `top_k_concentration`, `outliers` exist. Jaccard / overlap-coefficient
must be implemented in the new service (or added to `StatisticsService`).

### 1.6 Existing UI tabs/routes

* Nav (`ui/src/components/layout/app-shell.tsx:13-22`): `/network` is one nav
  entry; sub-pages are `/network/full` (tabs `Metrics|Temporal|Edges|Graph`,
  `full-network-view.tsx:195-201`), `/network/videos/[videoId]`.
* `NetworkGraph` (`ui/src/components/features/network-graph.tsx`) is the
  reusable force-graph canvas (props `nodes/links/runs/channels`, node drawer,
  tooltip, scrape actions).
* API layer: `ui/src/services/api.ts` (`getCommentThreads`, `getVideoComments`,
  `getNetworkSummary`), `ui/src/services/networkFull.ts` (react-query hooks for
  `/network/*`), types in `ui/src/lib/network-full-types.ts` and
  `ui/src/lib/types.ts`.
* Charts/colors: `ui/src/lib/colors.ts` (`CHART_VARS`, `resolveChartColors`)
  for theme-aware canvas/DOM colors; `ui/src/components/features/data-table.tsx`
  `DataTable` for sortable tables; `Card/Badge/Tabs/Select` primitives under
  `ui/src/components/ui/`.

### 1.7 Testing conventions

* Backend: `pytest` (`python -m pytest SocialScienceResearch/tests -q`),
  `tests/conftest.py` provides real Excel-backed repos on `tmp_path`
  (`excel_repos` fixture) plus `sample_*` entities. OpenAPI snapshot gate at
  `tests/test_openapi_snapshot.py` (regenerate via
  `python SocialScienceResearch/scripts/dump_openapi.py`).
* UI unit: vitest (`ui/src/components/features/*.test.tsx`).
* E2E: Playwright specs under `SocialScienceResearch/tests/e2e/` (e.g.
  `network_visualizer.spec.ts`; `@playwright/test` is a root dependency, no
  checked-in config — specs target `localhost:3000` UI + `localhost:8000` API).

---

## 2. Feature requirements (restated, engineering-shaped)

Given a research scope (selected videos and/or channels in the graph), show:

1. **Commenter sets** per video and per channel
   (distinct comment authors keyed by the strongest identifier, **not** display
   name alone).
2. **Pair/triangle overlap metrics**: Jaccard, Szymkiewicz–Simpson overlap
   coefficient, shared counts, unique-vs-overlap breakdown, reach overlap %.
3. **The set of shared commenters** per pair (display names + comment counts
   on each side).
4. **Marketing/politics/social-science stats**: shared-audience size,
   unique-vs-overlap, top shared commenters by activity, overlap heatmap,
   **bridge commenters** (active across many videos/channels).
5. **Integration with the existing network graph** (commenters as an extra
   node/edge dimension) for both **video-graph** and **channel-graph**
   projections.

---

## 3. Design decisions

### D1 — Commenter identity resolution (single, shared key)

Define one module-level helper in the new service (and, to stop drift,
refactor the three existing copies to delegate to it):

```python
IdentityKind = Literal["id", "name"]          # "unknown" rows are excluded

def resolve_author(comment) -> tuple[IdentityKind | None, str | None, str | None]:
    """(kind, key, display_name) for a comment.
    kind="id"   -> key = author_id,            display = author_name
    kind="name" -> key = author_name,          display = author_name
    else        -> (None, None, None)          # anonymous, excluded
    """
    if comment.author_id:
        return "id", comment.author_id, comment.author_name
    if comment.author_name:
        return "name", comment.author_name, comment.author_name
    return None, None, None
```

* The **key** is what populates sets (identity); the **display name** is what
  the UI renders (research field, per user story §2).
* Comments with no key are counted (`unidentified_comments`) and excluded from
  sets — never fabricated.
* Bridge/pair memberships are keyed on this key, so an id-backed author whose
  display name changes across videos is still tracked (the explicit user-story
  requirement: "must not treat display name alone as sufficient identity").
* Keys are URL-encoded when used in a path segment (`author_key` can be a
  non-ASCII display name).

### D2 — Backend service shape

New `services/commenter_overlap_service.py`, constructed with only `Repositories`
(matching `NetworkAnalyticsService.__init__`, `network_analytics_service.py:295-297`),
so it is injectable via the same `get_service` lazy pattern
(`api/routers/common.py`, `network_ext.py:40-45`).

**Public API (all pure functions over repo reads; no writes):**

```python
class CommenterOverlapService:
    def __init__(self, repos: Repositories) -> None: ...

    def overlap(self, *, video_ids: list[str], channel_ids: list[str],
                metric: str = "jaccard", min_entities: int = 2,
                top_n: int = 50) -> CommenterOverlapResult:
        """Video + channel projections in one response (see §4 models)."""

    def profile(self, author_key: str, *, video_ids: list[str] | None = None,
                channel_ids: list[str] | None = None,
                limit: int = 200) -> CommenterProfile:
        """Per-commenter drill-down with full evidence comments."""
```

**Internal pipeline (one comment sweep, then pure math):**

1. `comments = repos.comments.list_comments()` (one sweep).
2. Build `video → channel` map via `repos.videos.list_videos()` (one sweep).
3. Scope filtering: keep comments whose `video_id ∈ video_ids` (video
   projection) and/or whose `video→channel ∈ channel_ids` (channel projection).
   If both lists are given, **both projections are returned** in one response.
4. Resolve author keys (`resolve_author`); drop anonymous.
5. Build `entity → {author_key: {display, count, first_seen, last_seen}}`:
   * video projection: unit = `comment.video_id`
   * channel projection: unit = `video_channel[comment.video_id]`
6. All pairwise unions/intersections via set ops over the author-key sets.
   Pure `itertools.combinations` — O(k²) pairs, fine at research scale.
7. Bridge commenters: authors whose distinct-entity count ≥ `min_entities`,
   ranked by `(entity_count desc, comment_count desc, key asc)`.
8. Top shared commenters: rank by total comment count across the selected
   projection.

**Statistics reuse:** `StatisticsService.ratio(n, d)` for the None/zero-safe
division; every ratio is `None` (not `0`) when a denominator is zero — the
module's "never fabricate" rule.

**Performance note:** one `list_comments()` sweep + one `list_videos()` sweep +
in-memory set math. No N+1. `top_n` caps payload size; shared-commenter lists
per pair can be paginated or capped (design: return top `top_n` per pair and
a `total_shared` count).

### D3 — Graph integration (commenters as a node/edge dimension)

Two orthogonal, additive surfaces — **do not mutate** the existing
`RecommendationGraphService`/`NetworkGraph` contract:

1. **Overlap-edge overlay (weighted co-occurrence graph).** `CommenterOverlapResult`
   carries `projection.overlap_edges: [{entity_a, entity_b, shared_commenter_count,
   jaccard}]` (only pairs with `shared_commenter_count >= min_shared`). The
   existing `NetworkGraph` component gains optional props
   `overlapEdges?: OverlapLink[]` + `overlayKind: "recommendation" | "commenter_overlap"`
   — the same canvas renders either the recommendation DiGraph or the commenter
   co-occurrence graph (edge width ∝ shared count, node size ∝ commenter count).
   This keeps one component, one legend, two data modes.
2. **Commenter-node bipartite dimension (optional extension to `/network/graph`).**
   Add query param `dimension=commenters` to `GET /network/graph`: when set, the
   response is a second payload shape whose nodes are `video` and `commenter`
   nodes and edges are `video —COMMENTED_BY— commenter`. Implemented as a new
   method `NetworkAnalyticsService.graph_with_commenters(video_ids|channel_ids)`
   (or a separate `CommenterOverlapService.graph_dimension(...)`) returning
   `CommenterGraphPayload`. The UI renders it via the same `NetworkGraph`
   component with a `dimension="commenters"` prop. This is the graph-native
   representation of user-story §15 (`User ─COMMENTED_ON─ Video`).

Both projections (video-graph and channel-graph) work in both surfaces: the
overlay/bipartite construction is parameterized by the same unit resolution as
§D2 step 5.

### D4 — Response models (exact schemas, `_Base` = `ConfigDict(extra="allow")`)

Defined in `services/commenter_overlap_service.py` (service-owned models, the
established pattern in `network_analytics_service.py:68-244`), re-exported for
the router.

```python
class OverlapEntity(_Base):
    entity_id: str
    entity_type: str                       # "video" | "channel"
    title: str | None = None
    channel_id: str | None = None          # video projection only
    channel_name: str | None = None
    commenter_count: int = 0               # distinct commenters
    comment_count: int = 0                 # total comments
    identity_coverage: float | None = None # identifiable / total comments
    avg_jaccard: float | None = None       # mean Jaccard vs all other entities (audience duplication)

class SharedCommenter(_Base):              # one row of a pair's shared list
    author_key: str
    author_name: str | None = None
    identity_kind: str                     # "id" | "name"
    count_a: int = 0                       # comments on entity_a
    count_b: int = 0                       # comments on entity_b
    total_comments: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

class PairOverlap(_Base):
    entity_a: str
    entity_b: str
    set_size_a: int = 0
    set_size_b: int = 0
    intersection_size: int = 0
    union_size: int = 0
    unique_a: int = 0                      # |A \ B|
    unique_b: int = 0                      # |B \ A|
    jaccard: float | None = None           # |A∩B| / |A∪B|
    overlap_coefficient: float | None = None # |A∩B| / min(|A|,|B|)  (Szymkiewicz–Simpson)
    reach_overlap_pct: float | None = None # |A∩B| / max(|A|,|B|) — share of larger audience
    shared_commenters: list[SharedCommenter] = []   # capped at top_n
    total_shared: int = 0                  # full shared count (pagination/cap bookkeeping)

class BridgeCommenter(_Base):
    author_key: str
    author_name: str | None = None
    identity_kind: str
    entity_count: int = 0                  # distinct videos (or channels) participated in
    comment_count: int = 0
    video_count: int = 0                   # distinct videos (always meaningful)
    channel_count: int = 0
    entities: list[dict[str, Any]] = []    # [{entity_id, comment_count}] per unit
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

class TopSharedCommenter(_Base):
    author_key: str
    author_name: str | None = None
    identity_kind: str
    entity_count: int = 0
    comment_count: int = 0
    video_count: int = 0
    channel_count: int = 0

class ProjectionSummary(_Base):
    entity_type: str
    entity_count: int = 0
    commenter_count: int = 0               # distinct authors across the projection
    comment_count: int = 0
    unidentified_comments: int = 0
    pair_count: int = 0
    average_jaccard: float | None = None
    max_jaccard_pair: dict[str, Any] | None = None   # {entity_a, entity_b, jaccard, intersection_size}
    max_shared_pair: dict[str, Any] | None = None    # {entity_a, entity_b, intersection_size}
    bridge_commenter_count: int = 0

class CommenterProjection(_Base):
    entity_type: str
    entities: list[OverlapEntity] = []
    pairs: list[PairOverlap] = []         # sorted jaccard desc (metric param)
    heatmap: dict[str, dict[str, float | None]] = {}  # entity_a -> entity_b -> metric value
    overlap_edges: list[dict[str, Any]] = []           # {entity_a, entity_b, shared_commenter_count, jaccard}
    bridge_commenters: list[BridgeCommenter] = []
    top_shared_commenters: list[TopSharedCommenter] = []
    summary: ProjectionSummary

class CommenterOverlapResult(_Base):
    scope: dict[str, list[str]] = {}      # {video_ids: [...], channel_ids: [...]}
    metric: str = "jaccard"               # echo of the requested metric
    videos: CommenterProjection | None = None
    channels: CommenterProjection | None = None
    global_summary: dict[str, Any] = {}   # {unique_commenters, comment_count, bridge_commenter_count}
```

**Profile endpoint models:**

```python
class ProfileVideoRow(_Base):
    video_id: str
    channel_id: str | None = None
    channel_name: str | None = None
    title: str | None = None
    comment_count: int = 0
    root_count: int = 0                   # root comments written by the author
    reply_count: int = 0                  # replies written by the author
    reply_to_count: int = 0               # distinct authors the user replied to (user-story §12)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

class ProfileChannelRow(_Base):
    channel_id: str
    channel_name: str | None = None
    comment_count: int = 0
    video_count: int = 0                  # distinct videos participated in
    root_count: int = 0
    reply_count: int = 0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

class ProfileComment(_Base):
    comment_id: str
    video_id: str
    comment_text: str | None = None
    published_at: datetime | None = None
    is_reply: bool = False
    parent_comment_id: str | None = None
    parent_author_name: str | None = None  # parent author display (reply context)
    like_count: int | None = None          # latest observation
    is_author: bool | None = None          # uploader flag

class CommenterProfile(_Base):
    author_key: str
    author_name: str | None = None
    identity_kind: str
    total_comments: int = 0
    video_count: int = 0
    channel_count: int = 0
    is_author: bool | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    videos: list[ProfileVideoRow] = []
    channels: list[ProfileChannelRow] = []
    comments: list[ProfileComment] = []    # most recent first, capped by limit
```

### D5 — Endpoint spec (new router `api/routers/commenters.py`)

| Endpoint | Params | Response | Notes |
|---|---|---|---|
| `GET /network/commenters/overlap` | `video_ids` (comma list), `channel_ids` (comma list) — **at least one required**; `metric=jaccard\|overlap_coefficient\|intersection` (default `jaccard`); `min_entities` (int ≥ 1, default 2); `min_shared` (int ≥ 1, default 1, overlay edge threshold); `top_n` (int 1..500, default 50) | `CommenterOverlapResult` | 400 via `ValueError` when both id lists empty (app handler maps to `invalid_argument`, `app.py:297-302`). |
| `GET /network/commenters/{author_key}/profile` | path: URL-encoded author key; query: `video_ids?`, `channel_ids?`, `limit` (1..500, default 200) | `CommenterProfile` | 404 when no comments match the key. |
| `GET /network/graph` (existing, extended) | add `dimension=recommendations\|commenters` (default `recommendations`); when `commenters`, also `video_ids?`/`channel_ids?` | existing `NetworkGraph` **or** `CommenterGraphPayload` (§D3.2) | Existing callers unchanged (default). |

Router registration: add `commenters` to the import block and
`app.include_router(commenters.router, prefix=prefix)` in
`api/app.py:312-332`. No service wiring needed beyond `get_service`
(lazy, `commenters` key).

### D6 — Stats for marketing / politics / social science

Exposed aggregates (all derived, all traced to comments):

1. **Reach overlap %** — `jaccard` (union-normalized) and `reach_overlap_pct`
   (larger-audience share) per pair; `average_jaccard` per entity = audience
   duplication rate.
2. **Unique-vs-overlap breakdown** — `unique_a/unique_b/intersection_size`
   per pair; `commenter_count` per entity.
3. **Shared-audience size** — `intersection_size`, plus `max_shared_pair` and
   `max_jaccard_pair` in `ProjectionSummary` (which pair shares the most /
   most concentrated audience).
4. **Top shared commenters by activity** — `top_shared_commenters` ranked by
   comments (cross-video/cross-channel super-participants).
5. **Overlap heatmap** — `heatmap` matrix (metric-configurable) for the
   "ecosystem overlap" view (media/political cross-audience map).
6. **Bridge commenters** — `bridge_commenters` (active in ≥ `min_entities`
   distinct videos/channels); the multi-user-cohort §8 "shared users" / §9
   user×channel matrix analogue. `entity_count/video_count/channel_count`
   distinguish multi-video (same creator) from multi-channel (cross-ecosystem)
   bridges — directly answers "same user, different channel behavior".
7. **Identity hygiene** — `identity_coverage` per entity and
   `unidentified_comments` (how much of the corpus is name-only or anonymous;
   a validity caveat researchers need).
8. **Provenance preserved** — every row retains `first/last_seen_at` and
   comment ids; the profile endpoint returns full comment text + reply context,
   so the data supports future temporal overlap analysis and the "raw
   evidence behind every result" acceptance criteria.

### D7 — UI placement

**New route** `/network/commenters` (`ui/src/app/network/commenters/page.tsx`,
metadata "Commenter Overlap") — a standalone analysis page under the existing
`/network` nav entry (nav item unchanged; active-state logic in
`app-shell.tsx:45-47` already highlights parent for nested routes).

**Page layout** (`ui/src/components/features/commenters/commenter-overlap-view.tsx`):
* Scope picker (multi-select videos + channels from `/videos` and `/channels`),
  or deep-link via query params `?video_ids=...&channel_ids=...`.
* Projection toggle **Video graph | Channel graph** → renders
  `result.videos` or `result.channels`.
* Tabs: **Overview** (KPI tiles: commenter count, unique, avg Jaccard, max
  shared pair, bridge count; identity-coverage badge) · **Heatmap** · **Pairs**
  (sortable `DataTable`) · **Shared commenters / Bridges**.
* `OverlapHeatmap` component: CSS-grid matrix cell color ∝ metric value using
  `resolveChartColors().accent` with alpha steps (theme-aware, no new deps);
  hover tooltip = pair stat card; click = select pair → filters pairs table.
* `CommenterProfileView` at `/network/commenters/[authorKey]` (dynamic route):
  header stats, videos table, channels table, comment history (with
  `parent_author_name` context line, `like_count`, `is_reply` badge).

**Integration into existing graph surfaces:**
1. Add a **"Commenters"** tab to `FullNetworkView` (`full-network-view.tsx:90,195-201`)
   embedding `CommenterOverlapView` (or a graph-scoped variant bound to the
   current `graphRunId`/`graphChannelId`).
2. Add an **"Commenter overlap"** action to the `NetworkGraph` node drawer
   (`network-graph.tsx:489-566`, drawer at line 489) → `/network/commenters?video_ids=<id>`; and a
   channel-scoped link from the channel facet → `/network/commenters?channel_ids=`.
3. `NetworkGraph` gains optional `overlapEdges`/`overlayKind` props (§D3.1) so
   the same canvas renders the commenter co-occurrence graph; the "Commenters"
   tab offers the force-graph overlay as one of its views.
4. `/network/graph?dimension=commenters` (optional) feeds a
   `dimension="commenters"` mode rendering the bipartite author↔video graph.

**UI data layer:**
* `ui/src/services/commenters.ts` — `useCommenterOverlap(scope, opts)`,
  `useCommenterProfile(authorKey, scope)` (react-query hooks; key convention
  like `networkFullKeys`).
* `ui/src/lib/commenter-overlap-types.ts` — TS mirrors of §D4 models.
* `request`/`toQuery` from `ui/src/services/api.ts` reused; author keys
  `encodeURIComponent`-ed in the path segment.

---

## 4. File-by-file implementation checklist

### Backend — create
1. `services/commenter_overlap_service.py` — identity helper (§D1), all §D4
   models, `CommenterOverlapService` (§D2). Reuses `StatisticsService.ratio`.
   Add a `resolve_author`/`author_key` module function so §1.2 drift is fixed
   (optionally refactor `author_repository.py:82`, `comment_analytics_service.py:149`,
   `sampling_service.py:797` to delegate to it — separate low-risk change).
2. `api/routers/commenters.py` — the three routes of §D5 with `response_model`s,
   `_service()` via `get_service(request, "commenters", ...)`, comma-list query
   parsing, `ValueError` on empty scope, `HTTPException(404)` on unknown author.
3. `tests/test_commenter_overlap_service.py` — unit tests (below).
4. `tests/test_commenters_api.py` — endpoint tests (below).
5. `SocialScienceResearch/tests/e2e/commenter_overlap.spec.ts` — Playwright
   flows (below).

### Backend — modify
6. `api/app.py` — import + `app.include_router(commenters.router, prefix=prefix)`
   (block at `app.py:312-332`).
7. `services/network_analytics_service.py` — add `dimension` param + optional
   `graph_with_commenters(...)` for `/network/graph?dimension=commenters`
   (§D3.2), plus `CommenterGraphPayload`/`CommenterGraphNode` models. (Optional
   if D3.2 is deferred — the overlap overlay §D3.1 is sufficient for v1.)
8. `api/routers/network_ext.py` — thread the `dimension` query param to
   `network_graph`.
9. `api/openapi.json` — regenerate after router changes
   (`python SocialScienceResearch/scripts/dump_openapi.py`) or
   `tests/test_openapi_snapshot.py` fails.

### UI — create
10. `ui/src/app/network/commenters/page.tsx` — page shell (server component
    wrapping the view).
11. `ui/src/app/network/commenters/[authorKey]/page.tsx` — profile drill-down.
12. `ui/src/lib/commenter-overlap-types.ts` — TS models (§D4).
13. `ui/src/services/commenters.ts` — react-query hooks + request helpers.
14. `ui/src/components/features/commenters/commenter-overlap-view.tsx` — main
    view (scope picker, projection toggle, tabs, KPI tiles).
15. `ui/src/components/features/commenters/overlap-heatmap.tsx` — heatmap
    matrix component.
16. `ui/src/components/features/commenters/overlap-pairs-table.tsx` — sortable
    pair table (reuses `DataTable`).
17. `ui/src/components/features/commenters/shared-commenters-panel.tsx` —
    top-shared + bridge commenters lists with drill-down links.
18. `ui/src/components/features/commenters/commenter-profile-view.tsx` —
    profile view (videos/channels tables + comment history).
19. `ui/src/components/features/commenters/commenter-overlap-view.test.tsx` —
    vitest component test (heatmap cell rendering, projection toggle,
    drill-down link).

### UI — modify
20. `ui/src/components/features/network-full/full-network-view.tsx` — add
    "Commenters" tab (Tabs value `commenters`), bind to
    `graphRunId`/`graphChannelId` scope.
21. `ui/src/components/features/network-graph.tsx` — optional
    `overlapEdges`/`overlayKind`/`dimension` props (§D3) + "Commenter overlap"
    drawer action linking to `/network/commenters?video_ids=<id>`.
22. `ui/src/app/network/videos/[videoId]/page.tsx` (if a link is desired from
    the ego-network page) — optional "Audience overlap" link.

### Verification (see §5 for content)

---

## 5. Verification plan

### 5.1 Backend unit tests — `tests/test_commenter_overlap_service.py`
* **Identity**: id preferred over name; name-only fallback; anonymous excluded;
  `identity_kind` values correct; `identity_coverage` math.
* **Set math**: exact Jaccard / overlap-coefficient / reach % on hand-computed
  synthetic sets; empty-set pairs → `None` (never `0`); `unique_a/unique_b`.
* **Projections**: same corpus → video projection (units = videos) vs channel
  projection (units = channels) produce expected different pairings; both
  returned together when both scopes given.
* **Bridge commenters**: author in 3/5 videos ranks above author in 2/5;
  `min_entities` threshold; multi-channel bridge has `channel_count > 1`.
* **Top shared commenters** ranked by total activity with deterministic ties.
* **Overlay edges**: only pairs with `shared >= min_shared`; correct
  `shared_commenter_count`.
* **Profile**: video/channel rows, root/reply split, `reply_to_count`,
  comment history capped by `limit`, parent author context.
* Uses the `excel_repos` fixture (`tests/conftest.py:30-39`) + seeded comments;
  mirrors the synthetic-edge style of `tests/test_network_analytics_service.py`.

### 5.2 API tests — `tests/test_commenters_api.py`
* 400 on empty `video_ids`+`channel_ids` (error envelope `invalid_argument`).
* 200 `CommenterOverlapResult` shape on seeded repos; heatmap symmetric
  (`m[a][b] == m[b][a]`), diagonal absent/`None`.
* 200 profile for an id-backed and a name-backed author; 404 for unknown key.
* `metric` param switches heatmap/pair ordering; `top_n` caps shared lists.
* OpenAPI: regenerate snapshot; new paths present.

### 5.3 UI component tests (vitest)
* Heatmap renders a cell per pair with correct aria-label (`overlap 0.42 ...`);
  projection toggle switches data source; drill-down link href encodes the
  author key.

### 5.4 Playwright flows — `SocialScienceResearch/tests/e2e/commenter_overlap.spec.ts`
(Model on `network_visualizer.spec.ts`; requires UI :3000 + API :8000 with
comments in the workbook.)
1. `/network/commenters` loads, scope picker shows videos, overlap result
   renders KPI tiles + heatmap (locator `[data-testid="overlap-heatmap"]`).
2. Projection toggle Video → Channel swaps the pair table rows.
3. Clicking a shared commenter navigates to `/network/commenters/[authorKey]`
   and the comment history renders the first comment text.
4. `/network/full` → "Commenters" tab renders the same view scoped to the
   selected run/graph.
5. (If D3.1 shipped) Graph tab with `overlayKind="commenter_overlap"` renders a
   canvas and the legend shows the overlap role.

---

## 6. Open questions for the implementation owner

1. **Share the identity helper now?** Refactoring the three existing `author_key`
   copies to a single helper touches sampling/analytics/repository code; the new
   feature can ship self-contained and the de-dup done as a follow-up. Recommend
   self-contained now, de-dup tracked.
2. **`/network/graph?dimension=commenters` (D3.2) or overlay-only (D3.1) for
   v1?** D3.1 (overlap-edge overlay in `NetworkGraph`) is cheap and covers the
   "additional edge dimension" requirement; D3.2 (bipartite author nodes) is
   the fuller "node dimension" and should be its own increment.
3. **Heatmap color scale**: diverging (accent → accent2) or sequential
   (faint → accent)? Sequential reads better for single-metric overlap.
4. **Pair-list pagination**: `total_shared` + `top_n` cap per pair is the
   recommendation; confirm whether a `cursor` per pair is needed for very
   large shared lists.
5. **Run/date scoping**: overlap currently spans the whole corpus for the
   requested entities. A `run_ids`/date-range scope (user stories §1/§14) is a
   natural follow-up reusing `CommentFilter` (`domain/query.py:82-101`) on the
   pre-aggregation comment sweep.
