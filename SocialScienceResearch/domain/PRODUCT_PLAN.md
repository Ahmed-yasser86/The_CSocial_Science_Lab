# Product Plan — Unified Network Research Platform

> Scope: evolve the current SocialScienceResearch app into one connected research
> journey where every stage flows into the next, and implement the new user
> stories from `domain/userstory.md` (US-1 … US-78) **on top of** existing
> features (never deleting them). Explicit priority from the user: make Excel
> export of researcher-collected/made data **easy**, and unify the journey so no
> feature is an orphan.

## 1. Product Vision

A researcher moves through **one continuous lab inside a Project**:

```
Research Project → Research Data (collect / import) → Select Sources
→ Construct Network (dedup + provenance) → Explore → Analyze Structure
→ Communities / Channels / Echo-Chamber → Expand via Recommendations (layers)
→ Observe Evolution → Generate Insights → Inspect Evidence → Export (Excel + matrices)
```

Every screen answers: *what problem does it solve, what data does it consume,
what does it produce, where does the output go next, how is evidence inspected,
how does it connect onward.* No orphan routes.

The **Network Analysis Lab** (US-2, US-73–78) is the connective tissue: a single
in-project workspace hosting Explore, Communities, Recommendation Expansion,
Evolution, Echo-Chamber, Channels, Matrices, Insights, Evidence — with multiple
Lab instances, resumable sessions, side-by-side comparison, annotations, and
layout presets.

## 2. Current-State Inventory (what already exists)

**Solid foundation (keep, build on):**
- Projects (Video/Comment/Hybrid) + items (`/projects`, `/projects/[id]`)
- Collection config + long-running jobs + run ledger/provenance (`/collect`, `/runs`)
- Data Explorer with provenance (`/explore`, `record-explorer.tsx`)
- Video / Channel workspaces + longitudinal history
- Sampling Workbench + Dataset library (CSV/JSON export) + `datasets.combine` (dedup)
- Full network graph (`/network/full`): density, reciprocity, communities (Louvain,
  `community_id` on nodes), HITS, temporal slices, GraphML/edgelist/GEXF/CSV/JSON/xlsx export
- Ego network (`/network/videos/[id]`), Commenter overlap, Comparison workspace
- Recommendation expansion + layer scraping (new-nodes-only, `layer_index`, progress)
- Network merge / network-to-network comparison (`/network/merge`)
- Export-to-project artifact, `POST /export` (single entity → xlsx), `POST /network/export`
- Repo abstraction (`persistence/`) with `excel_workbook.py` isolating openpyxl

**Disconnections found (orphans):**
- `/query` and `/data` are unreachable (no nav/palette links)
- `/compare` and `/network/full` only via command palette
- Project pages do **not** link to their datasets/network (ProjectItemDetail shows
  names but no clickable links)
- Network summary (`/network`) does **not** link to the full network lab
- No browse/index pages for `/channels`, `/videos`, `/network/videos`, `/projects/[id]/items`
- Analysis stage not linked from Projects at all

**Gaps vs user stories:**
- US-72 Excel export works but is per-entity and buried → not "easy"
- US-55–59 Echo-chamber multidimensional profile: partial (only commenter overlap)
- US-62–63 Auto research insights (observed/derived/interpretation 3-layer): missing
- US-60–61 Matrices completeness (community/channel/layer-transition): partial
- US-73–78 Lab instances / sessions / compare / annotations / presets / researcher
  identity: mostly missing — the "Lab" is not yet a unified in-project workspace

## 3. Gap Analysis (US → status)

| Group | Stories | Status |
|---|---|---|
| Research Project & Data Foundation | US-1, US-2, US-3 | Done / Partial (Lab unification missing) |
| Collection Configuration | US-4…US-9 | Done |
| Dynamic Variables & Filtering | US-10…US-14 | Partial (percentile/AND-OR live preview) |
| Variables & Data Dictionary | US-15…US-17 | Partial |
| Advanced Sampling | US-18, US-19 | Done |
| Raw Data Visibility (Explorer) | US-20…US-23 | Done |
| Video / Channel / Comparison Workspaces | US-24…US-31 | Done (compare is orphaned) |
| Comment & Reply Research | US-32, US-33 | Partial |
| Network Construction | US-34…US-37 | Done |
| Exploration & Structural | US-38…US-41 | Done |
| Communities & Channel Ecosystem | US-42…US-44 | Partial |
| Recommendation Expansion | US-45…US-51 | Done |
| Evolution & Saturation | US-52…US-54 | Partial |
| Echo-Chamber Research | US-55…US-59 | Partial (needs full profile) |
| Matrices | US-60, US-61 | Partial |
| Research Insights | US-62, US-63 | Missing |
| Provenance & Reproducibility | US-64…US-66 | Done |
| Longitudinal | US-67, US-68 | Partial |
| Data Quality & Coverage | US-69 | Partial |
| Transcript External Storage | US-70 | Done |
| Repository Abstraction | US-71 | Done |
| Export (Excel) | US-72 | Partial → **prioritized fix** |
| Network Analysis Lab (instances/sessions/compare/annotations/presets/collab) | US-73…US-78 | Mostly Missing → **prioritized foundational work** |

## 4. Phased Roadmap

### Sprint 0 — Unify the journey (no new science, pure connectivity)  ← START HERE
- Add `/query`, `/data`, `/compare`, `/network/full` to top nav + command palette.
- Make Project → Data/Network clickable (ProjectItemDetail links to datasets/samples;
  Project page gets a "Networks" entry → `/network/full` scoped by project).
- Link Network summary → Full network lab.
- Add browse/index pages (or search entries) for channels/videos.
- **Deliverable tests:** e2e playwright navigation connectors + unit.

### Sprint 1 — Easy Excel export (explicit user ask)  ← START HERE (parallel)
- Backend: `POST /export` gains `project_id` → **multi-sheet workbook**
  (Videos, Comments, Channels, Recommendations, Runs/Provenance) of everything the
  researcher collected under that project. Keep single-entity mode.
- Frontend: prominent **"Export to Excel"** button on Project page (+ Network/analysis
  pages) that downloads the workbook in one click. Keep the per-entity `ExportTab`.
- **Deliverable tests:** backend unit (multi-sheet content) + e2e (button → download).

### Sprint 2 — Network Analysis Lab shell (US-2, US-73–78 foundation)
- Introduce Lab instances per project (multiple networks, independent state).
- Resumable session state (open panels, active filters, selected nodes/layers).
- Side-by-side network comparison entry point (reuse `/network/merge`).
- Annotations model + researcher identity field on session/annotation state.
- Layout presets (explore+echo+channels) — starting points, not constraints.

### Sprint 3 — Science completeness
- Research Insights auto-generation (US-62/63, 3-layer observed/derived/interpretation).
- Full Echo-Chamber profile (US-55–59, multidimensional + per-ecosystem channels).
- Matrices completeness (US-60/61: community, channel-channel, layer-transition).
- Evolution/cycles hardening (US-52–54).

### Sprint 4 — Variables & Sampling depth (US-10–19, US-32/33)
- Adaptive entity-aware filter builder, AND/OR/NOT, live population preview,
  percentile correctness, sampling feasibility checks.

## 5. Immediate Implementation (this session)

1. **Sprint 0 connectors** — navigation + project→data/network links.
2. **Sprint 1 Excel export** — project multi-sheet export + prominent buttons.
3. **Tests** — unit (backend export) + e2e (playwright: export download, nav connectors).

Definition of Done per story (from §28 of userstory.md) is the acceptance bar for
every implemented capability, plus unit + integration + e2e tests.
