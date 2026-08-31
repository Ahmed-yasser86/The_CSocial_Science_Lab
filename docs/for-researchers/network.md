# Network Science

> Two network families, weight specifications, centrality battery, community detection, and cross-network comparison.

---

## Two Network Families

The project constructs two primary network types from YouTube data:

### Recommendation Network

| Property | Description |
|---|---|
| **Nodes** | Videos |
| **Edges** | Directed, source → recommended-video |
| **Edge weight** | Rank position, observation count, or binary |
| **Construction** | Three-layer fallback extraction + BFS layered crawling |
| **Core question** | What does YouTube connect? |

### Audience/Commenter Network

| Property | Description |
|---|---|
| **Nodes** | Commenters (or videos/channels in projection) |
| **Edges** | Undirected, co-comment participation |
| **Edge weight** | Jaccard similarity, overlap coefficient, or co-comment frequency |
| **Construction** | Group comments by video, create co-comment edges |
| **Core question** | Who interacts with whom? |

**Important:** The social network represents social/interaction relationships, not semantic relationships or recommendation relationships.

---

## Weight Grammar

Edge weights are encoded using a formal grammar:

```
edge_type:weight_mode[:param=value,...][:norm=...]
```

Examples:

- `recommendation:rank` — weight based on recommendation rank position
- `commenter:jaccard` — weight based on Jaccard similarity
- `commenter:overlap_coefficient` — weight based on Szymkiewicz-Simpson coefficient

This grammar makes weight computation explicit and reproducible.

---

## Centrality Battery

The system computes 10 centrality measures:

| Measure | What It Captures |
|---|---|
| **Degree** | Number of connections |
| **Closeness** | Average distance to all other nodes |
| **Eigenvector** | Connection to well-connected nodes |
| **Betweenness** | Role as intermediary on shortest paths |
| **PageRank** | Importance in directed networks |
| **Harmonic** | Average inverse distance to all other nodes |
| **Constraint** | Degree of enclosure in local neighborhood |
| **Effective size** | Non-redundant connections |
| **Bridging** | Tendency to connect different groups |
| **Clustering** | Density of local neighborhood |

All measures are validated against NetworkX on Zachary's Karate Club (tolerance 1e-6).

---

## Structural Roles

Nodes are classified into structural roles based on centrality rankings:

| Role | Definition |
|---|---|
| **Core** | Eigenvector centrality in top quartile |
| **Broker** | Betweenness centrality in top decile |
| **Bridge** | Between core and periphery |
| **Periphery** | Degree centrality in bottom quartile |

---

## Community Detection

### Louvain Algorithm

- **Implementation:** NetworkX `louvain_communities`
- **Determinism:** `seed=42` ensures reproducible community assignments
- **Modularity:** Computed as the quality metric for community detection

### Community Metrics

| Metric | Description |
|---|---|
| **Modularity** | Strength of community division |
| **Within-community rate (WCR)** | Proportion of edges within communities |
| **Conductance** | Ratio of external to total edges per community |
| **Internal/external ratio** | Edge density within vs. between communities |

### Null Model

The `null_model_wcr()` function implements degree-preserving double-edge swaps to establish statistical baselines for within-community rate comparisons.

---

## Comparative Network Analysis

The system enables direct comparison of network types:

| Network | Represents | Core Question |
|---|---|---|
| Social Network | User interaction | Who interacts with whom? |
| Semantic Network | Content relationships | What content is related? |
| Recommendation Network | Platform-mediated connections | What does YouTube connect? |

### What Becomes Possible

When these networks are compared:

- **Overlap** — communities aligned across social, semantic, and recommendation structures
- **Divergence** — structures that differ, revealing information-environment asymmetries
- **Bridges** — nodes connecting separate communities across layers
- **Isolated communities** — communities separated in one layer but connected in another
- **Cross-community edges** — edges crossing boundaries in one layer but not another

### Network Merge

The `merge_networks()` operation combines two network scopes into a unified view, computing:

- Overlap statistics (shared nodes and edges)
- Combined SNA metrics
- Cross-network community comparison

### Community Matrices

The network matrix service computes:

- **Channel-channel matrix** — shared-commenter counts between channels (audience duplication)
- **Layer matrix** — recommendation-edge structure per crawl layer

---

## Graph Export

Networks can be exported in 6 formats:

| Format | Extension | Use Case |
|---|---|---|
| GraphML | `.graphml` | Gephi, NetworkX |
| Edge List | `.edgelist` | Simple text format |
| GEXF | `.gexf` | Gephi |
| CSV | `.csv` | Spreadsheet analysis |
| JSON | `.json` | Web visualization |
| XLSX | `.xlsx` | Excel analysis |

---

## Temporal Analysis

The longitudinal service tracks:

- **Channel/video histories** — per-run observations with growth percentages
- **Run deltas** — diff two runs: new, changed, disappeared entities
- **Observation gaps** — detect gaps longer than a threshold between observations

---

## Validation

The centrality battery is validated against Zachary's Karate Club:

- All 10 centrality measures match NetworkX ground truth to tolerance 1e-6
- Community detection produces expected community structure
- Structural role classification matches expected patterns

This validation is implemented in `tests/test_centrality_benchmark.py`.
