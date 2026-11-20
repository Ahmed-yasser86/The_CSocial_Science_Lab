# Screenshot gallery

For a single scrolling view of every image, open [GALLERY.md](GALLERY.md).

Real UI captures from the running Social Science Research Workbench, taken
against the **Legacy** workspace unless noted. The corpus counters visible in
the captures are the workspace's own rows: 2,431 collection runs, 1,705 videos,
153,531 comments and 39 projects. The five `analyze-*` and `echo-*`/`commenters-*`
images were captured earlier in the same workspace and are included here so the
gallery is complete. No placeholder or fabricated screens are included.

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

## Notes

- Counters in a screenshot are per workspace; the README reports both the
  Legacy workspace figures and totals across every workspace database.
- No data was collected, approved, or mutated while capturing these images.
