# User Stories Gap Audit — Commenter Behavioral Tracking & Multi-User Cohort Analysis

**Date:** 2026-08-14
**Scope:** Gap audit (read-only) of two user stories against the current codebase.
**Sources audited:**
- `docs/user_story_commenter_behavioral_tracking.md` (Story 1, 17 capabilities / 21 acceptance criteria)
- `docs/user_story_multi_user_cohort_analysis.md` (Story 2, 20 capabilities / 28 acceptance criteria)
- Backend `domain/`, `services/`, `api/routers/`, `api/app.py`, `persistence/`, `acquisition/`
- Frontend `ui/src/app`, `ui/src/components/features/`

**Legend**
- **IMPLEMENTED** — capability exists and is reachable via a documented service/endpoint/UI.
- **PARTIAL** — underlying raw data exists and/or pieces exist, but the capability as specified (dedicated service, endpoint, or UI) is missing or incomplete.
- **MISSING** — no implementation; not derivable without new code.

---

## Executive Summary

| Area | Story 1 | Story 2 |
|---|---|---|
| Capabilities IMPLEMENTED | 2 / 17 | 2 / 20 |
| Capabilities PARTIAL | 8 / 17 | 11 / 20 |
| Capabilities MISSING | 7 / 17 | 7 / 20 |
| Acceptance criteria IMPLEMENTED | 8 / 21 | 6 / 28 |
| Acceptance criteria PARTIAL | 7 / 21 | 14 / 28 |
| Acceptance criteria MISSING | 6 / 21 | 8 / 28 |

**Key finding:** The data model is excellent — every raw interaction field the stories demand (author id + name, comment text, timestamp, like/reply counts, `is_reply`, `parent_comment_id`, `root_comment_id`, video/channel context, per-author aggregate) is already collected and persisted. What is missing is the **behavioral layer on top**: per-author interaction-history services, user-to-user reply-edge extraction, cross-video/channel aggregation, multi-user comparison, user networks, and temporal user analysis. The entire network stack today is recommendation-graph (video→video) only; no user/commenter graph exists.

---

# Story 1 — Advanced Commenter Behavioral Tracking & Cross-Video / Cross-Channel Analysis

## Capability-by-Capability Audit

### IMPLEMENTED

| # | Capability | Evidence | Notes |
|---|---|---|---|
| 1 | **Custom Video Cohort for Behavioral Analysis** | `VideoFilter` date/type/duration/views/upload-hour/weekday/keywords/tags/category (`domain/query.py:26-46`); strategies TOP/BOTTOM_VIEWS/LIKES/ENGAGEMENT, LONGEST/SHORTEST, LATEST/EARLIEST, DATE_RANGE, RANDOM, STRATIFIED (`domain/enums.py:89-108`; `services/sampling_service.py:63-163`); cross-channel/multi-video `AdvancedSamplingSpec` (`domain/query.py:104-170`; `services/sampling_service.py:386-525`); `POST /sampling/advanced` (`api/app.py:795-811`); **save/reuse** via persisted samples (ADR-0011, `services/sample_service.py:48-82`) and materialized datasets (`services/dataset_service.py:78-139`); UI `SamplingWorkbench` (`ui/.../sampling/SamplingWorkbench.tsx`) | All listed selection criteria (date period, single/multiple channels, random, stratified, highest/lowest viewed, highest/lowest engagement, duration range, upload time, specific count, other metadata) are implemented. Cohort reuse is possible via samples, datasets, and projects (`api/routers/datasets.py:138-330`). |
| 17 | **Future Extension — Semantic Comment Analysis (out of scope)** | Full comment text + raw payload preserved (`acquisition/normalization.py:288-329`; `domain/models.py:177-198`); conversation context (parent/root ids) preserved (`normalization.py:258-285`) | Correctly deferred; raw data retained. |

### PARTIAL

| # | Capability | Evidence | Gap |
|---|---|---|---|
| 2 | **Individual Commenter Identification** | Author id from `author_id`/`author_channel_id` (`normalization.py:313`); `Comment.author_id`/`author_name` (`domain/models.py:189-190`); search `GET /search?entity=author` (`api/routers/search.py:33-50`; `services/search_service.py:29-56,167-175`); aggregated `AuthorProfile` (`domain/models.py:259-284`; `persistence/author_repository.py:48-118`); `author_ids`/`author_names` filters in advanced sampling (`domain/query.py:134-137`) | Identity + search exist and correctly prefer `author_id` over name (`author_repository.py:82-88`). **Gap:** no endpoint returns a consolidated per-author view ("which videos/channels, when, how, what they wrote, who they replied to / who replied to them"). `AuthorProfile.video_ids` lists videos but has no channel breakdown; parent-author is never joined in any author-facing payload. |
| 3 | **Complete Commenter Interaction History** | All required fields stored on `Comment`/`CommentObservation` (`domain/models.py:177-213`); rows resolved with full context (`services/query_service.py:283-308`) | **Gap:** no service/endpoint returns a full interaction history organized Channel→Video→Interaction→Comment/Reply. Parent comment text/author are **not** stored on the reply row — they require a join that no endpoint performs. |
| 4 | **Comment vs Reply Identification** | `is_reply` + `parent_comment_id` + `root_comment_id` (`domain/models.py:193-195`); root/reply repository methods (`persistence/excel_repository.py:238-256`); `CommentFilter.only_roots/only_replies` (`domain/query.py:97-98`); thread/root metrics (`services/comment_analytics_service.py:162-269`); `GET /videos/{id}/comments/{id}/tree` (`api/routers/comments.py:86-94`) | Root-vs-reply distinction is fully implemented. **Gap:** "same-author reply vs other-author reply" requires parent-author lookup that is not exposed anywhere. |
| 5 | **Complete Conversation Context** | `ThreadPayload` root+replies (`api/schemas.py:275-277`); `CommentTreePayload` nested (`api/schemas.py:280-285`); tree endpoint + builder (`api/app.py:886-937`; `api/routers/comments.py:164-215`); UI thread modal (`ui/.../comment-tree-modal.tsx`) | Replies are returned nested under their root, so thread context is visible in the tree UI. **Gap:** a reply returned outside a tree (e.g. flat `GET .../comments`) carries no parent text/author; no dedicated parent-context field; the "navigate both directions" requirement has no structured object. |
| 6 | **Cross-Video User Tracking** | `AuthorProfile.video_ids` + `comment_count` + first/last seen (`domain/models.py:276-283`; `persistence/author_repository.py:91-118`) | **Gap:** no consolidated behavioral view — total interactions, root/reply counts, interaction frequency, most-active periods, most-interacted-with videos, engagement received, comment-vs-reply distribution are all derivable but never computed/served. |
| 12 | **User-to-User Interaction Relationships** | Reply evidence derivable from `parent_comment_id` + all fields (reply id, parent id, texts, authors, video/channel, timestamp) on `Comment` (`domain/models.py:187-198`) | **Gap:** no service extracts user→user reply edges with the required evidence payload; nothing consumes reply relationships. |
| 15 | **Graph Integration** | Full graph infrastructure exists but for **recommendations only**: `RecommendationGraphService` (`services/recommendation_graph_service.py`), `NetworkAnalyticsService` (`services/network_analytics_service.py`), graph/edges/export endpoints (`api/routers/network_ext.py:80-203`), graphml/edgelist/gexf export (`network_analytics_service.py:574-611`) | **Gap:** no `User ─COMMENTED_ON/WROTE/REPLIED_TO/WRITTEN_BY→ ...` edges; the graph stack must be extended (or paralleled) to ingest reply relationships. |
| 16 | **Temporal Social-Interaction Analysis** | Per-run temporal network slices + growth exist for the **recommendation graph**: `GET /network/temporal` (`api/routers/network_ext.py:126-139`; `services/network_analytics_service.py:356-378`) | **Gap:** temporal analysis of **user interaction** networks (2020→2021→… community/density changes) is not implemented. |

### MISSING

| # | Capability | Gap |
|---|---|---|
| 7 | **Cross-Channel User Tracking** | No channel-level aggregation for an author, no per-channel interaction/video counts, no "same commenter across channels" comparison. (`AuthorProfile` stores only `video_ids`, not channels.) |
| 8 | **User Behavioral Timeline** | No per-commenter chronological timeline service/endpoint (activity growth/decline, active/inactive periods, root/reply changes over time). |
| 9 | **User × Video Comparison** | No analysis of a user's behavior relative to video characteristics (high/low views, duration, period, channel). |
| 10 | **User × Cohort Analysis** | Cohorts exist as named `VideoFilter` sets (`ComparisonService.compare_cohorts`, `services/comparison_service.py:426-489`) but are not applied to a specific commenter's behavior. |
| 11 | **Multiple User Comparison** | No multi-user comparison endpoint/service (totals, ratios, channel distribution, temporal activity, engagement). |
| 13 | **Cross-Video / Cross-Channel Interaction Comparison** | No interaction-level comparison across videos/channels/users. |
| 14 | **User Behavioral Comparison Over Time** | Period comparison exists for videos/channels only (`services/comparison_service.py:373-424`); nothing divides a user's activity into arbitrary periods and compares them. |

## Acceptance Criteria Coverage (Story 1)

| AC | Criterion | Status | Evidence / Gap |
|---|---|---|---|
| 1 | Define video cohort via existing filtering/sampling | ✅ IMPLEMENTED | `domain/query.py:26-46`, `sampling_service.py:63-163` |
| 2 | Select one or more specific commenters | ✅ IMPLEMENTED | `author_ids`/`author_names` in `AdvancedSamplingSpec` (`domain/query.py:134-137`, `sampling_service.py:574-603`); author search `search_service.py:167-175` |
| 3 | Retrieve all observable interactions within selected corpus | ⚠️ PARTIAL | Comment rows have full context (`query_service.py:283-308`) but no dedicated author-history endpoint |
| 4 | Preserve complete text of every interaction | ✅ IMPLEMENTED | `comment_text` stored (`domain/models.py:191`) |
| 5 | Distinguish root comments from replies | ✅ IMPLEMENTED | `is_reply`/`parent_comment_id` (`domain/models.py:193-194`) |
| 6 | Identify parent comment of every reply | ✅ IMPLEMENTED | `parent_comment_id` (`domain/models.py:194`) |
| 7 | Retrieve parent comment's complete text | ⚠️ PARTIAL | Requires join to parent; not exposed |
| 8 | Identify parent comment's author | ⚠️ PARTIAL | Requires join to parent; not exposed |
| 9 | Determine same-author vs other-author reply | ⚠️ PARTIAL | Derivable via join; not computed/served |
| 10 | Retrieve complete video context for every interaction | ✅ IMPLEMENTED | `Comment.video_id` + `Video` rows; explorer provides video context (`api/routers/explorer.py:103-146`) |
| 11 | Track commenter across multiple videos in same channel | ⚠️ PARTIAL | `AuthorProfile.video_ids` (`author_repository.py:103-106`) but no per-video breakdown/timeline |
| 12 | Track across multiple channels when reliably matchable | ❌ MISSING | No channel tracking for authors |
| 13 | Compare same commenter across channels | ❌ MISSING | — |
| 14 | Compare same commenter across video cohorts | ❌ MISSING | — |
| 15 | Compare same commenter across time periods | ❌ MISSING | — |
| 16 | Compare multiple selected commenters | ❌ MISSING | — |
| 17 | Identify observable user-to-user reply relationships | ⚠️ PARTIAL | Derivable from `parent_comment_id`; no extractor service |
| 18 | Preserve underlying interaction evidence for every relationship | ⚠️ PARTIAL | Fields stored; not assembled into an evidence payload |
| 19 | Export/expose relationships for graph construction | ❌ MISSING | Only recommendation edges exportable (`network_analytics_service.py:574-611`) |
| 20 | Preserve timestamps for longitudinal analysis | ✅ IMPLEMENTED | `published_at` + `observed_at` (`domain/models.py:192,206`) |
| 21 | Keep semantic/NLP out of scope while preserving raw data | ✅ IMPLEMENTED | Raw text + `raw_json` retained (`normalization.py:288-329`) |

---

# Story 2 — Multi-User Cohort Behavioral Analysis, Interaction Networks & Cross-Channel Profiling

## Capability-by-Capability Audit

### IMPLEMENTED

| # | Capability | Evidence | Notes |
|---|---|---|---|
| 2 | **Video Selection Must Be Fully Controllable** | Same machinery as Story 1: `VideoFilter` (`domain/query.py:26-46`), strategies (`domain/enums.py:89-108`), `AdvancedSamplingSpec` (`domain/query.py:104-170`; `sampling_service.py:386-525`), cohort reuse via samples/datasets/projects (`sample_service.py`, `dataset_service.py:78-195`) | "All videos by Channels A,B,C 2020–2023, >10min, top 20% by views" is fully expressible. |
| 20 | **Future Semantic Analysis Layer (out of scope)** | Raw text + contextual data retained (`normalization.py:288-329`; `dataset_service.py:373-399` raw sidecar) | Correctly deferred. |

### PARTIAL

| # | Capability | Evidence | Gap |
|---|---|---|---|
| 1 | **Multi-User Cohort Selection** | By video: `video_ids` (`domain/query.py:133`); by date: `date_from/to`; by channel(s): `channel_ids`/`include_all_channels` (`query.py:131,170`); predefined ids: `author_ids` (`query.py:134`); random/stratified comment sampling (`sampling_service.py:351-361,649-658`); author-overlap (min videos/channels) `overlap`/`overlap_min` (`query.py:163-166`; `sampling_service.py:802-848`); UI author scope/filters (`ui/.../ScopeSelector.tsx`, `FilterPanel.tsx`) | **Gap:** no persisted "user cohort" entity and no direct criteria for *minimum number of interactions* (only min distinct videos/channels via overlap) or *participation pattern*. Samples/datasets are the only persistence mechanism and samples do **not** support `author` as an entity type (`services/sample_service.py:24-26`). |
| 3 | **Full Comment-Level Filtering** | Temporal date range (`CommentFilter.date_from/to`, `query.py:91-92`; `_apply_comment_filters`, `sampling_service.py:789-793`); type root/reply (`query.py:97-98`; `sampling_service.py:777-780`); engagement min/max likes/replies + TOP_LIKES/TOP_REPLIES (`query.py:93-96`; `sampling_service.py:763-775,621-648`); author filters (`query.py:99-100,134-137`); keywords (`query.py:101`, `sampling_service.py:785-787`) | **Gap:** no year/month bucket filter (only full date range); no relative-period-after-publication or before/after-event; no top/bottom **percentile** filter (only rank strategies); no comment text-length filter; no thread-depth filter. |
| 4 | **User Cohort → Complete Interaction Dataset** | `DatasetService.create_dataset` with `entity_type="comment"` + `member_ids` from a sample (`dataset_service.py:78-139`); `create_from_project` (`dataset_service.py:141-195`); comment rows carry full context (author, text, ids, timestamps, engagement, `is_reply`, `parent_comment_id`, `root_comment_id`) (`query_service.py:283-308`) | **Gap:** parent-comment text/author are not flattened into rows (only `parent_comment_id`); channel requires a join through video. Rows are per-comment (never user-level stats) which matches the story, but context fields are incomplete. |
| 5 | **Population-Level Behavioral Analysis** | Per-video author participation (unique/repeat, Gini, top-10% concentration) (`services/comment_analytics_service.py:162-194`); reply/thread metrics (`comment_analytics_service.py:197-246`) | **Gap:** no cohort-level aggregation — comment/reply ratio, videos/channels per user, interaction frequency, active periods, comment length, unique conversation partners/videos/channels. |
| 8 | **Audience / User Overlap** | Author-overlap selection filter (distinct videos/channels) (`sampling_service.py:802-848`); sample overlap/Jaccard (`services/sample_service.py:87-128`, `api/routers/samples.py:74-78`) | **Gap:** overlap is a *selection filter* or a *sample-set* metric; there is no per-user-pair/group measure of shared videos, channels, creators, or time periods with Jaccard similarity. |
| 12 | **User Interaction Profile** | `AuthorProfile`: comment count, distinct videos, first/last seen, `is_author` (`domain/models.py:259-284`; `author_repository.py:91-118`) | **Gap:** profile lacks comment/reply distribution, channel participation, temporal activity detail, engagement received, conversation partners, shared videos/channels. |
| 13 | **Observable Linguistic / Interaction Pattern Dataset** | Raw comment text preserved; datasets materialize comment rows (`dataset_service.py:78-139`); reply/parent context stored as ids (`domain/models.py:194-195`) | **Gap:** parent-comment text/author joinable but not materialized into the pattern dataset; no dedicated "conversation partner" column. |
| 16 | **Cohort-to-Cohort Comparison** | Video cohorts compared by means (`services/comparison_service.py:426-489`, `POST /comparison/cohorts`); sample Jaccard compare (`sample_service.py:87-128`) | **Gap:** no **user** cohort comparison (network structure, reply behavior, shared channels/videos, user overlap, temporal activity). |
| 17 | **Network Analysis** | Rich metrics on the **recommendation** graph: density, reciprocity, degree distribution, clustering, components, greedy-modularity communities, modularity, HITS (`services/network_analytics_service.py:300-353`) | **Gap:** metrics are for video→video recommendation edges, not user reply networks. Betweenness/closeness/eigenvector centrality are also absent even for the recommendation graph. |
| 18 | **Temporal Network Analysis** | Per-run slices + growth on the **recommendation** graph (`network_analytics_service.py:356-378`) | **Gap:** no temporal analysis of user interaction networks (relationships emerging/disappearing, centrality changes, community evolution, cross-channel changes). |
| 19 | **Future Behavioral Simulation Foundation** | Raw observable evidence preserved (interaction history fields, video/channel context, timestamps, engagement, reply ids) (`domain/models.py:177-213`; `query_service.py:283-308`) | **Gap:** fields exist but no assembled per-user behavioral dataset; simulation layer correctly not implemented. |

### MISSING

| # | Capability | Gap |
|---|---|---|
| 6 | **User-to-User Social Network Construction** | No reply-based user graph (User→User edges). Only recommendation graph exists. |
| 7 | **Interaction Weighting** | No weighted relationships (User A→B with reply counts, videos, channels, first/last, temporal distribution). |
| 9 | **User × Channel Behavioral Matrix** | No users×channels interaction-count matrix with drill-down. |
| 10 | **Same User, Different Channel Behavior** | No per-user per-channel comparison service. |
| 11 | **Same User, Different Videos Within One Channel** | No intra-channel per-video behavioral comparison. |
| 14 | **Creator-Specific Behavioral Analysis** | No analysis of a user/cohort across creators (root-vs-reply patterns per creator ecosystem). |
| 15 | **Cross-Channel User Movement** | No temporal channel-participation trajectories (2020: A; 2021: A+B; …). |

## Acceptance Criteria Coverage (Story 2)

| AC | Criterion | Status | Evidence / Gap |
|---|---|---|---|
| 1 | Select a large cohort of users via configurable criteria | ⚠️ PARTIAL | Author filters + overlap exist (`query.py:131-166`); no min-interactions/pattern criteria; no persisted user cohort |
| 2 | Define exact videos analyzed | ✅ IMPLEMENTED | `AdvancedSamplingSpec.video_ids/channel_ids` (`query.py:131-133`) |
| 3 | Apply independent comment-level filters after video selection | ⚠️ PARTIAL | `_apply_comment_filters` after video filters (`sampling_service.py:560-613`) |
| 4 | Root / replies / both / all | ✅ IMPLEMENTED | `only_roots`/`only_replies` (`query.py:157-158`; `sampling_service.py:777-780`) |
| 5 | Filter comments by arbitrary temporal criteria | ⚠️ PARTIAL | Date range only; no year/month bucket, relative period, event-relative |
| 6 | Filter by engagement and percentile criteria | ⚠️ PARTIAL | min/max likes/replies + TOP_LIKES/TOP_REPLIES; no top/bottom percentile filter |
| 7 | Retrieve complete observable interaction history for the cohort | ⚠️ PARTIAL | Rows exist (`query_service.py:283-308`); no per-author history endpoint |
| 8 | Preserve complete text of every relevant comment/reply | ✅ IMPLEMENTED | `comment_text` (`domain/models.py:191`) |
| 9 | Preserve parent-comment text and author for replies | ⚠️ PARTIAL | Stored as ids; text/author require join, not materialized |
| 10 | Determine root vs reply behavior | ✅ IMPLEMENTED | `is_reply` (`domain/models.py:193`) |
| 11 | Track users across multiple videos | ⚠️ PARTIAL | `AuthorProfile.video_ids` (`author_repository.py:103-106`) |
| 12 | Track users across channels when reliably identifiable | ❌ MISSING | No channel tracking per author |
| 13 | Compare same user across channels | ❌ MISSING | — |
| 14 | Compare same user across videos within one channel | ❌ MISSING | — |
| 15 | Compare multiple users | ❌ MISSING | — |
| 16 | Identify shared videos between users | ⚠️ PARTIAL | Overlap filter counts distinct videos (`sampling_service.py:832-841`) but no pair/group output |
| 17 | Identify shared channels between users | ⚠️ PARTIAL | Overlap channel filter (`sampling_service.py:824-841`) but no pair/group output |
| 18 | Calculate user overlap and similarity | ⚠️ PARTIAL | Jaccard on sample sets (`sample_service.py:87-128`), not user pairs |
| 19 | Construct user-to-user interaction networks from replies | ❌ MISSING | — |
| 20 | Weight relationships by interaction frequency | ❌ MISSING | — |
| 21 | Analyze network structure and communities | ⚠️ PARTIAL | Metrics exist but on recommendation graph only (`network_analytics_service.py:300-353`) |
| 22 | Analyze network evolution across time | ⚠️ PARTIAL | Temporal slices on recommendation graph (`network_analytics_service.py:356-378`) |
| 23 | Compare different user cohorts | ❌ MISSING | — |
| 24 | Compare different video cohorts | ✅ IMPLEMENTED | `compare_cohorts` (`services/comparison_service.py:426-489`) |
| 25 | Preserve raw interaction evidence behind every result | ⚠️ PARTIAL | Raw data preserved; not assembled behind results |
| 26 | Export user/interactions structure for future graph analysis | ❌ MISSING | Only recommendation exports (`network_ext.py:176-193`) |
| 27 | Preserve data for future behavioral-profile/simulation layer | ⚠️ PARTIAL | Fields exist; no assembled dataset |
| 28 | Keep semantic inference out of scope while preserving raw data | ✅ IMPLEMENTED | Raw text + `raw_json` retained |

---

# Prioritized Implementation Plan

All items assume the existing "observed, never estimated" ethos and the `Repositories`/`QueryService` read-side patterns already in place.

## P0 — Foundational (unlocks most of both stories)

1. **Parent-comment context resolver + enriched comment rows**
   - New: extend `QueryService.resolve_latest_rows("comment")` (`services/query_service.py:283-308`) to attach `parent_text`, `parent_author_id`, `parent_author_name` via one batch lookup (reuse `ExcelCommentRepository.list_replies_by_ids` pattern, `persistence/excel_repository.py:248-256`).
   - Effect: AC1-7/8/9, S1-5, S2-9, S2-13 become directly available everywhere (explorer, datasets, exports).
   - Touch: `services/query_service.py`, `services/variable_registry.py`, `api/schemas.py` (`CommentPayload`), `ui/src/lib/types.ts`.

2. **Per-author interaction-history service**
   - New `services/author_service.py` + `api/routers/authors.py`:
     - `GET /authors/{author_id}/interactions` — full list of the author's comments with video + channel context (batch-joined), `is_reply`, parent context (from P0-1).
     - `GET /authors/{author_id}/summary` — total interactions, distinct videos, distinct channels, root/reply counts, first/last interaction, most-active periods, most-interacted videos, comment-vs-reply distribution, engagement received.
   - Effect: S1-3/6, S1-AC-3/11, S2-4/7/12.
   - Touch: new service + router; reuse `AuthorRepository` (`persistence/author_repository.py`) and `QueryService`.

3. **User-to-user reply-edge extractor**
   - New `services/reply_relationship_service.py`: derive `(reply_author, parent_author, reply_comment_id, parent_comment_id, reply_text, parent_comment_text, video_id, channel_id, timestamp)` edges from comments by joining replies to parents.
   - Effect: S1-12/17/18, S2-6/19/26; the foundation for weighting, overlap, networks, and graph export.
   - Touch: new service + unit tests (pattern: `sample_service.py`).

## P1 — Core analysis capabilities

4. **Cross-video / cross-channel / timeline aggregation** (S1-7, S1-8, S2-10, S2-11, S2-15)
   - Extend `AuthorService` with per-channel and per-video breakdowns, and a chronological activity timeline (bucketed by day/week/month) reusing `StatisticsService` (`services/statistics_service.py`). Channel transitions (S2-15) computed from the timeline.

5. **Multi-user comparison** (S1-11, S1-AC-16, S2-15)
   - New `services/author_comparison_service.py` + `POST /authors/compare`: totals, root/reply ratios, channel distribution, temporal activity, engagement, cohort participation, per normalization (`none`/`per_1k`/`z_score`, pattern `services/comparison_service.py:52-57`).

6. **User cohort selection + persistence** (S2-1, S2-AC-1)
   - Add `author` entity support to `SampleService` (`services/sample_service.py:24-26`) and `DatasetService` (`_ID_FIELD` already has `"author": "author_id"`, `dataset_service.py:51-57`). Add cohort criteria: minimum interactions, minimum videos, participation pattern (root-heavy/reply-heavy), plus a persisted user-cohort model alongside `Sample` (ADR-0011 pattern).

7. **User × channel matrix + user overlap/similarity** (S2-8, S2-9, S2-AC-16/17/18, S1-13)
   - Extend `AuthorService` with a users×channels interaction-count matrix (with per-pair drill-down), and a pair/group overlap report: shared videos, shared channels, Jaccard (reuse `StatisticsService` / `sample_service.py:87-128` math).

8. **User × cohort and user × time-period comparison** (S1-10, S1-14, S2-23)
   - Reuse `ComparisonService.compare_cohorts`/`compare_periods` machinery (`services/comparison_service.py:373-489`) with an author entity: behavior of one author across named video cohorts and arbitrary time periods.

9. **User interaction network + weighting + metrics + temporal + export** (S1-15/16, S2-6/7/17/18/21/22/26)
   - New `services/user_network_service.py` building an `nx.DiGraph` from reply edges (P0-3) with edge weights (reply frequency) and temporal slices (run/period), mirroring `NetworkAnalyticsService` (`services/network_analytics_service.py:300-378`) but on user nodes. Add betweenness/closeness/eigenvector centrality (absent even for recommendation graph). Add graphml/edgelist/gexf export reusing `export_edges` pattern (`network_analytics_service.py:574-611`). Routes under `api/routers/network_ext.py`.

## P2 — Surface, polish, and remaining criteria

10. **Commenter UI** (S1/S2 research workflow)
    - New `ui/src/app/authors/` pages (author search/results, interaction history with channel/video drill-down, timeline chart, thread context) reusing `RecordExplorer` (`ui/.../explorer/record-explorer.tsx`), `CommentTreeModal`, and `DataTable` patterns. Add user-network view alongside `/network`.

11. **Dataset/export enhancements** (S2-25/26/27, S1-19)
    - Include parent-context columns (P0-1) in `DatasetService` comment projections (`dataset_service.py:334-340`) and in `export-tab.tsx` columns (`ui/.../export-tab.tsx:53-60`). Export user interaction structure for external graph tools.

12. **Filter completeness** (S2-AC-5/6, S2-3)
    - Add to `CommentFilter` (`domain/query.py:82-101`): year/month bucket, top/bottom percentile engagement, comment text-length, thread depth; wire through `QueryService.filter_comments` (`services/query_service.py:149-199`).

---

## Suggested Implementation Order (dependencies)

```
P0-1 parent context ──► P0-2 author history ──► P0-3 reply edges
                                              │
            ┌──────────────────────────────────┘
            ▼
P1-4 timeline/channel    P1-5 multi-user compare   P1-6 user cohorts
            │                    │                        │
            ▼                    ▼                        ▼
P1-7 matrix/overlap      P1-8 user×cohort/period   P1-9 user network
                                                          │
                                                          ▼
                              P2-10..12  UI, exports, filter completeness
```