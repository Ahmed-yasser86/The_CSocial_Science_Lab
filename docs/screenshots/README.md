# Screenshot gallery

For a single scrolling view of every image, open [GALLERY.md](GALLERY.md).

Real UI captures from the running Social Science Research Workbench, taken
against the **Legacy** workspace unless noted. These are isolated development
and testing databases populated during application development and the
continuous testing cycle — not a production deployment. The corpus counters
visible in the captures are the workspace's own rows: 2,431 collection runs,
1,705 videos, 153,531 comments and 39 projects. The five `analyze-*` and
`echo-*`/`commenters-*` images were captured earlier in the same workspace and
are included here so the gallery is complete. No placeholder or fabricated
screens are included.

Captures were taken at a 1600×1000 desktop viewport in light mode. The full
recommendation-network canvas was expanded before capture (the app panel is
480 px tall while the canvas is 1000 px); no application code was changed.

## Workspace and collection

| File | What it shows |
|---|---|
| [01-workspaces.png](01-workspaces.png) | Workspace picker with per-workspace run/video/dataset/project counters. |
| [02-workspace-legacy.png](02-workspace-legacy.png) | Legacy workspace: 2,431 runs, 1,705 videos, 153,531 comments, 895 datasets, 39 projects, and recent runs. |
| [03-collect.png](03-collect.png) | Collection form for channel, video, and recommendation runs with provenance note and recent runs. |

## Analyze — recommendation network and communities

| File | What it shows |
|---|---|
| [04-analyze-overview.png](04-analyze-overview.png) | Aggregate recommendation network rebuilt from persisted edges: 10,806 nodes, 34,770 edges, top recommended/source videos. |
| [05-network-lab.png](05-network-lab.png) | Full force-directed network graph colored by role, with Louvain communities listed. |
| [06-network-metrics.png](06-network-metrics.png) | Structural metrics and the per-node centrality table (degree, closeness, eigenvector, betweenness, PageRank, harmonic, bridging, clustering). |
| [07-echo-chambers.png](07-echo-chambers.png) | Observed S1–S5 structural signals; values appear only when a crawl completes, otherwise `unavailable`. |
| [08-echo-audience.png](08-echo-audience.png) | Audience/echo view over commenter overlap. |
| [09-echo-channels.png](09-echo-channels.png) | Channel-level echo view (top-channel share, community concentration). |
| [10-echo-videos.png](10-echo-videos.png) | Video-level echo view (frontier collapse, cross-layer repetition). |
| [11-commenters.png](11-commenters.png) | Shared-audience analysis: unique commenters, in-scope comments, Jaccard projection, overlap heatmap, bridge commenters. |
| [12-commenters-channels.png](12-commenters-channels.png) | Channel-scoped commenter overlap view. |
| [13-content-homophily.png](13-content-homophily.png) | Content-homophily measurement: within-vs-between cosine similarity with permutation null. |
| [14-compare.png](14-compare.png) | Side-by-side comparison of videos, channels, periods, cohorts or runs with explicit normalization and `missing` labels. |
| [15-query.png](15-query.png) | Condition funnel preview showing how many rows each condition dropped and kept. |
| [16-explorer.png](16-explorer.png) | Record explorer over the latest observed rows with query operators and collection provenance. |

## Data, provenance and projects

| File | What it shows |
|---|---|
| [17-data-coverage.png](17-data-coverage.png) | Corpus coverage: 745 channels, 1,705 videos, 153,531 comments, with comment/transcript coverage reported explicitly. |
| [18-provenance-runs.png](18-provenance-runs.png) | Provenance ledger: every collection run with source, configuration and success/failure counts. |
| [19-datasets.png](19-datasets.png) | Immutable dataset catalogue with per-dataset inspection, member browsing and CSV/JSON export. |
| [20-projects.png](20-projects.png) | Project list in the workspace. |
| [21-project-detail.png](21-project-detail.png) | Project detail with its items and links to evidence. |
| [22-data-library.png](22-data-library.png) | Data library coverage card: 745 channels, 1,705 videos, 267/1,705 videos with comment rows (16%), 0 with transcripts. |
| [23-samples.png](23-samples.png) | Research samples: reproducibility workbench with scope, filters, method and labels. |
| [24-docs.png](24-docs.png) | In-app documentation entry point. |
| [25-run-detail.png](25-run-detail.png) | A recommendation run: target URL/ID, provider, discovered/new/existing/failed counts and configuration snapshot. |
| [26-video-detail.png](26-video-detail.png) | Video detail with overview, network, engagement, comments and recommendations tabs. |

## Two-layer crawl job and echo analysis

The headline crawl is `job_20260901_163631_76aae01d` in workspace
`ws_6f6ebf52` ("E2E Bootstrap mt86prs3"): 284 runs, 6,784 videos discovered,
6,500 succeeded, 0 failed. The job's final bookkeeping hit a 3600s timeout
after persisting "Layer 2 done: 6,018 edges, 258 videos"; the crawl data and
its completed echo detection (`ech_20260901_163631_d4b7faa6`) remain stored.
The documented channel-projection improvement is **1,138 → 111 unattributed
edges**. The current echo-lens projection is computed over all family edges and
reports 3,575 unattributed edges for this detection. Source:
[Performance Optimizations](../for-developers/performance-optimizations.md).

A separate echo analysis in workspace `ws_431eeb72`
(`ech_20260825_075655_612d47ae`), seeded from an Arabic-language video, shows
311 nodes / 380 edges in its video lens, WCR 80.26% (z = 44.5), and layer-2
frontier collapse 5.00%.

| File | What it shows |
|---|---|
| [27-jobs-two-layer.png](27-jobs-two-layer.png) | Jobs tray listing the headline crawl job and its persisted state. |
| [28-correct-workspace.png](28-correct-workspace.png) | The workspace holding the 6,500-video crawl. |
| [29-echo-correct-header.png](29-echo-correct-header.png) | Completed echo detection, seed video and per-layer crawl result. |
| [30-echo-correct-network.png](30-echo-correct-network.png) | Network statistics, community structure and centrality from the video lens. |
| [31-echo-correct-communities.png](31-echo-correct-communities.png) | Within-community recommendation rate, null model, per-layer persistence and centrality. |
| [32-agent-console.png](32-agent-console.png) | Graph-RAG research agent console with previous subject/audience/ecosystem runs. |
| [33-echo-result-6500.png](33-echo-result-6500.png) | The echo-chamber Videos tab for the headline crawl: 2,447 nodes and **6,500 unique recommendation edges**, with 20 Louvain communities (seed community 284). The 1,138 → 111 unattributed-edge optimization is documented in [Performance Optimizations](../for-developers/performance-optimizations.md). |
| [34-echo-channel-network.png](34-echo-channel-network.png) | The echo-chamber Channels tab: channel→channel projection of the same detection, 182 nodes / 1,518 unique channel edges, "Unattributed edges (dropped) 3,575", plus channel concentration and signal availability. This lens is computed over all family edges; the 1,138 → 111 benchmark describes the optimized projection. |
| [35-full-network-metrics-small.png](35-full-network-metrics-small.png) | Full network analytics → Metrics on a single run slice (`run_20260901_173455_bb5ca014`): 31 nodes, 30 edges, density 0.032, one weakly connected component, one community — a small, fully observed recommendation slice with degree percentiles, top hubs, authorities and most-recommended videos. |
| [36-echo-per-layer-signals.png](36-echo-per-layer-signals.png) | The echo-chamber Videos tab's per-layer signal table for the headline crawl: layer 2 = 258 nodes / 6,018 edges with frontier collapse 18.49%, top-channel share 9.40%, community share 11.61%; custom signals show frontier collapse 18.49% and seed concentration 100% as `available`, commenter overlap `unavailable`. |

## Notes

- Counters in a screenshot are per workspace; the README reports both the
  Legacy workspace figures and totals across every workspace database.
- "Unattributed edges (dropped)" counts **edges** whose endpoint channel
  cannot be resolved, not dropped nodes. The 1,138 → 111 comparison is the
  documented optimized-channel projection; the current echo lens is computed over
  all family edges and reports a larger figure. The same projection in Full
  network analytics → Graph → Channel graph → Layer 1 shows 114 nodes and 107
  unattributed edges; the documented benchmark is 114 nodes / 215 edges /
  111 unattributed edges.
- 34 and 36 are from workspace `ws_6f6ebf52` and detection
  `ech_20260901_163631_d4b7faa6`; 35 is a single-run slice of the same
  workspace. None of these views shows an estimated value.
- The detected echo-chamber analyses are completed. No data was collected,
  approved, or mutated while capturing these images.
