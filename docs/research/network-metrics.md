# Network Metrics

Metrics are computed by `NetworkAnalyticsService` on a `networkx.DiGraph` built
from persisted `RecommendationObservation` edges (`RecommendationGraphService`),
optionally restricted to a single `collection_run_id` for temporal slices.

## Directed vs undirected (ADR-0009)

The recommendation graph is directed (source video → recommended video).
Measures that are only defined on undirected graphs are computed on
`to_undirected()` and documented as such:

| Metric | Graph | Definition |
|---|---|---|
| Node / edge count | directed | vertices and observed edges |
| Density | directed | edges / max possible edges |
| Reciprocity | directed | observed mutual edges / edges (0 for empty graphs) |
| Degree percentiles | undirected | P25/P75/P90/P95/P99 through `StatisticsService` |
| Avg / global clustering | undirected | Watts–Strogatz transitivity |
| Weakly connected components | directed | `weakly_connected_components` |
| Largest component share | undirected | fraction of nodes in the largest component |
| Communities | undirected | `greedy_modularity_communities` (from `networkx.algorithms.community`) |
| Modularity | undirected | modularity of the community partition |

## Centrality

- **HITS**: hubs + authorities on the directed graph.
- **PageRank**: directed, used in the network summary.
- **Most recommended / most active**: in-degree / out-degree rankings.

## Channel projection

`GET /network/channels` collapses edges onto `channel_id` (when disclosed on
the recommended side) for channel-level network research.

## Temporal slices

`GET /network/temporal?runs=a,b` returns per-run snapshots (node/edge counts,
density, reciprocity) plus between-slice growth (`Δ nodes`, `Δ edges`) so the
network can be studied across collection runs.

## Edge listing & exports

- `GET /network/edges` — cursor-paginated edge listing (ADR-0004).
- `GET /network/export?format=graphml|edgelist|gexf` — full-graph exports.
  GraphML/gexf sinks `None` edge attributes to `""` for schema validity.

## Observational caveats

Edges are only ever *observed* relationships. The yt-dlp recommendation
workflow records an explicit `recommendation_unsupported` error instead of
fabricating edges, so the graph reflects what the provider returned at
collection time. Temporal slices are therefore bounded by when runs actually
observed the network.
