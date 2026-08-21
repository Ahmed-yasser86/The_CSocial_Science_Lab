# Network Research Platform — Detailed User Stories
## (Scoped strictly to the three provided planning documents — no business model)

---

## 1. Master User Story

**As a** researcher,
**I want** to create a research project containing YouTube research data and use it to construct, explore, expand, analyze, and export research networks,
**so that** I can go from a research question to a reproducible research workflow without needing to understand the system's internals.

**Canonical pipeline every story below must fit into:**
```
Research Project → Research Data → Select Sources → Define Network Construction
→ Build Network (dedup + provenance) → Explore Network → Analyze Structure
→ Detect Communities → Analyze Community Relationships → Expand via Recommendations
→ Scrape New Layers (new nodes only) → Observe Evolution → Detect Convergence/Repetition
→ Analyze Potential Echo Chambers → Analyze Channels/Ecosystems → Generate Research Insights
→ Inspect Evidence → Export Network + Matrices + Data
```

---

## 2. Research Project & Data Foundation

**US-1.** As a researcher, I want to create a Research Project of type Video Project, Comment Project, or Hybrid Project, so that the tool's controls match my actual research population.
- Video Project: population is videos + metadata/relationships.
- Comment Project: population is comments/replies + relationships.
- Hybrid: combines relevant data from both.

**US-2.** As a researcher, I want each project to expose `Research Data / Collections / Analysis / Networks / Exports` as one coherent nested area, so that Networks feels like a natural continuation of the project, not a separate app.
- **Important framing note:** the Networks area inside a project is NOT a fixed "Network tab" with a static set of screens. It must be built as a **Network Analysis Lab** living inside the project — a flexible, open-ended workspace for network research, more adaptable than a rigid tab structure. The researcher should be able to move freely between sub-tools (Explore, Communities, Recommendation Expansion, Evolution, Echo-Chamber Analysis, Channels, Matrices, Insights, Evidence) as one lab environment rather than a predetermined linear tab bar — the exact internal layout is flexible as long as it stays inside the project and stays connected as one workflow (see pipeline in §1 and rules in §26).

**US-3.** As a researcher, I want to select one or more research sources across multiple projects/datasets before building a network, so I can combine e.g. a Videos dataset from Project A with a Comments dataset from Project B.
- Before "Build Network" is enabled, the system must show: which projects are used, which datasets, which records, which entities, which relationships can be constructed, and what time period is covered.

### 2.1 Network Analysis Lab — Additional Capabilities

**US-73.** As a researcher, I want to run multiple network analyses concurrently inside the same project as separate Lab instances (e.g. "Network A" for one topic, "Network B" for another), so that building or exploring one network never overwrites or interferes with another.
- Each Lab instance keeps its own network, layers, filters, and analysis state independently.
- The researcher can switch between Lab instances without losing the state of the one they left.

**US-74.** As a researcher, I want the Lab to save and resume my working session — open panels, active filters, current view, selected nodes/layers — so that if I stop mid-analysis I can come back later and pick up exactly where I left off.
- Session state persists per Lab instance, not just per project.
- Resuming restores the same layout/state, not just the underlying network data.

**US-75.** As a researcher, I want to compare two or more networks (or two iterations/experiments) side by side inside the Lab, so that I can ask questions like "how does Layer 3 expansion in Experiment 1 differ from Layer 3 in Experiment 2?" as a first-class Network-to-Network comparison, not just entity-level comparison (video/channel).
- Side-by-side view shows equivalent metrics, layers, and structural indicators for each network being compared.
- The comparison must make explicit which experiment/iteration/collection context each network came from (ties into provenance, §20).

**US-76.** As a researcher, I want to attach my own personal notes/annotations to a node, community, or layer inside the Lab, so that I can record my own research reasoning and methodological observations separately from the system-generated Insights.
- Annotations are clearly distinguished in the UI from system-generated Research Insights (§19) — one is human interpretation, the other is system-derived finding. They must never be visually or structurally merged.
- Annotations are traceable to the specific node/community/layer they were attached to and persist across sessions.

**US-77.** As a researcher, I want Lab-level workbench presets that configure the *layout* of the Lab itself (which panels open, in what arrangement), not just filter presets, so that I can quickly switch into a task-oriented view — e.g. an "Echo-Chamber-focused" preset that opens Explore + Echo-Chamber Analysis + Channels together.
- Layout presets are editable/savable by the researcher, same as filter presets (§26, "presets are starting points, never constraints").

**US-78.** As a researcher, I want the Lab's architecture to anticipate multi-researcher collaboration on the same project (even if not fully built in the first version), so that state, sessions, and annotations are modeled per-researcher from the start rather than assuming a single implicit user.
- Minimum requirement now: session/annotation/state data models should carry a researcher identity field, even if collaboration UI ships later.

---

## 3. Researcher-Controlled Collection Configuration

**US-4.** As a researcher, I want to choose my research target — channel, video, multiple channels, multiple videos, search/discovery result, or recommendation neighborhood — before collecting, so collection matches my study design.

**US-5.** As a researcher, I want to select which available video/channel/comment/reply variables to collect, based on everything the scraping library actually exposes (not a fixed hardcoded subset), so I only collect what I need.
- For every scraper capability: what info it provides, which research question it supports, which entity it belongs to, whether auto-collected or opt-in, whether it needs backend work, how it appears in the UI, whether it supports longitudinal/network research.

**US-6.** As a researcher, I want to define temporal boundaries (custom date ranges) and quantitative thresholds (top X%, bottom X%, min/max views/likes/comments, engagement thresholds, combinable) before running a collection.

**US-7.** As a researcher, I want to define a sampling strategy (population, method, sample size/percentage, stratification variable, random seed, inclusion/exclusion rules) as part of collection configuration.

**US-8.** As a researcher, I want every collection configuration saved as an inspectable, persisted object (target, selected variables, temporal range, quantitative criteria, sampling config, timestamp) so I can later answer "what exactly did I ask the system to collect?"

**US-9.** As a researcher, I want to monitor a long-running collection — what's running, criteria used, progress, items discovered/collected, failures, partial results, completion state, errors, retry/resume — instead of it behaving like a simple synchronous request.
- Post-run data-quality report: requested vs. collected vs. failed vs. unavailable counts.

---

## 4. Dynamic, Entity-Aware Variables & Filtering

**US-10.** As a researcher, I want the available controls to change automatically when I switch entity context (Video / Comment / Reply / Channel / Recommendation / Network / Dataset / Sample).
- Video controls: views, likes, comments, publication date, duration, engagement, comments, replies, recommendations, transcript/script, temporal behavior.
- Comment controls: comment date, likes, reply count, reply engagement, parent comment, reply depth, comment sampling, engagement percentiles, temporal criteria.
- Channel controls: video population, publication period, upload frequency, video performance, engagement, cohorts, content distribution, channel comparisons.
- No single giant generic filter panel with irrelevant fields.

**US-11.** As a researcher, I want a smart adaptive filtering system that behaves like a research query builder — dynamically changing based on entity type, selected object, available variables, dataset, analysis mode, and selected population.

**US-12.** As a researcher, I want to filter using statistically correct percentile/relative concepts — Top/Bottom 1/5/10/20/25/50%, First 10 percentile, quartiles Q1–Q4, median split — distinguishing percentile, percentile rank, quantile, quartile, and top/bottom percentage precisely (mathematically meaningful, not superficial labels).

**US-13.** As a researcher, I want to combine multiple filter criteria with AND / OR / NOT.
- Examples: `Videos AND published 2020–2023 AND top 10% by likes AND above median views AND ≥100 comments`; `Comments AND top 10% by likes AND posted between two dates AND ≥5 replies`; `Replies AND reply_count > X AND parent comment in top 20% engagement`.

**US-14.** As a researcher, I want a live filter preview showing how my population changes at each filtering step (e.g. `12,481 videos → 7,832 after date filter → 2,104 after engagement filter → 783 after top-10% filter`).

---

## 5. Researcher-Controlled Variables & Data Dictionary

**US-15.** As a researcher, I want to explicitly select which variables I want collected/included in a research dataset, rather than being forced into a fixed schema every project must use.

**US-16.** As a researcher, I want a data dictionary describing every available variable: name, meaning, source, data type, availability, observed-vs-derived, and known limitations.

**US-17.** As a researcher, I want variable metadata to flow through `Available Variables → Selected Variables → Collection/Analysis` consistently.

---

## 6. Advanced Sampling System

**US-18.** As a researcher, I want to choose from multiple sampling methods appropriate to my population/entity: random, stratified, systematic, top/bottom engagement, percentile-based, temporal/date-window, quota-based, cohort, balanced, or custom-criteria sampling.
- Comment sampling variables: likes, replies, reply engagement, comment date, parent/child relationships, engagement percentile, temporal period.
- Video sampling variables: views, likes, comments, publication date, engagement, channel, duration, performance percentile.
- System must verify feasibility of a requested method and explain limitations rather than silently producing an invalid sample.

**US-19.** As a researcher, I want a dataset-builder workflow: `Collected population → criteria → filtered population → sampling → validation → research dataset`, with a preview before finalizing.

---

## 7. Complete Raw Data Visibility (Data Explorer)

**US-20.** As a researcher, I want a dedicated Data Explorer to browse, search, sort, filter, and select fields on individual collected records across entity types.

**US-21.** As a researcher, I want to open an individual record and see all its fields, collection timestamp, source URL, identifiers, relationships, provenance, and missing values.

**US-22.** As a researcher, I want to move from a record → related entity → the analysis that used it, and back, without losing research context.

**US-23.** As a researcher, I want observed/source data, derived/calculated data, and research artifacts (samples, datasets, comparisons, network representations) kept visibly separate everywhere in the UI.

---

## 8. Video Research Workspace

**US-24.** As a researcher, I want a video research workspace exposing observed metadata, statistics, script/transcript, comments, comment distributions, comment engagement, temporal behavior, recommendation context, related videos, and comparisons — all discoverable.

**US-25.** As a researcher, I want to define a video population (not a single fixed item) using date ranges and percentile/engagement thresholds (e.g. "top 10% by views," "bottom 20% by engagement," combined date + percentile rules).

---

## 9. Channel Research Workspace

**US-26.** As a researcher, I want to define a channel's video population — all videos, a date range, top/bottom X%, most recent X%, or a minimum engagement threshold, or combinations.

**US-27.** As a researcher, I want channel-level analysis of publishing patterns, engagement/performance distributions, temporal behavior, content cohorts, outliers, comment behavior, audience participation, and recommendation relationships for the defined population.

**US-28.** As a researcher, I want channel comparison support with comparable periods, comparable video population rules, normalized metrics where appropriate, distribution comparison, temporal comparison, engagement comparison, and recommendation-relationship comparison.

---

## 10. Video-to-Video and Channel-to-Channel Comparison

**US-29.** As a researcher, I want to select multiple videos (not limited to two) and compare views, likes, comments, engagement, publication timing, comment activity/distributions, performance relative to channel baseline, temporal behavior, and recommendation relationships — via direct, normalized, distribution, and temporal comparisons.

**US-30.** As a researcher, I want to select multiple channels and compare publishing behavior, video volume, engagement, performance distributions, audience participation, comment behavior, temporal patterns, recommendation connectivity, and content cohorts.

**US-31.** As a researcher, I want the comparison population made explicit in the UI at all times — never silently comparing e.g. 10 years of Channel A videos against 1 year of Channel B videos.
- Support explicit comparable research contexts: same date range, same video population rule, same percentile rule, same engagement criteria.

---

## 11. Comment & Reply Research

**US-32.** As a researcher, I want to build comment populations beyond "top N comments" using rules like: top/bottom 10% by likes, comments with highest reply count, comments from a specific time period, comments with ≥X replies, comments in top 20% of engagement, replies to highly-engaged comments — and combinations of these.

**US-33.** As a researcher, I want to explore reply relationships, reply depth, parent-child structure, comment temporal patterns, engagement distributions, and participation patterns where data is available.

---

## 12. Network Construction Foundation

**US-34.** As a researcher, I want to select relevant sources and see, before building, exactly which projects, datasets, records, entities, relationships, and time period will participate in the network.

**US-35.** As a researcher, I want network construction to identify entities, relationships, source provenance, duplicate entities, relationship types, metadata, and temporal context — not just "create nodes" — preserving the link between the graph and the original research data.

**US-36.** As a researcher, I want duplicate entity resolution to be automatic and mandatory: the same entity across multiple datasets (e.g. Video X collected via Dataset A, B, C) must resolve into ONE node using reliable source identifiers — I should never manually clean duplicates just because I combined datasets.

**US-37.** As a researcher, I want only relationships actually supported by collected evidence to appear (e.g. `Video → recommends → Video`, `Comment → replies_to → Comment`, `Comment → belongs_to → Video`, `Video → belongs_to → Channel`, `Channel → associated_with → Video`), derived from available data — never invented relationships.

---

## 13. Network Exploration & Structural Analysis

**US-38.** As a researcher, I want the Network Research Workspace to be an analytical environment exposing nodes, edges, node/edge metadata, communities, channels, recommendation layers, network statistics, central nodes, bridge nodes, network matrices, and research insights — the graph is one view into the data, not the whole product.

**US-39.** As a researcher, I want structural metrics computed appropriately for the network type, not blindly calculated: node count, edge count, density, degree distribution, in/out-degree, connected components, average degree, isolated nodes, path measures, and centrality (degree, betweenness, closeness, eigenvector, PageRank) where meaningful.

**US-40.** As a researcher, I want full graph interaction: search, zoom, pan, node selection, edge inspection, community highlighting, channel filtering, layer filtering, relationship filtering, neighborhood exploration, centrality highlighting, bridge-node highlighting, cycle highlighting, recommendation-path exploration.

**US-41.** As a researcher, I want to move fluidly `Graph → Community → Channel → Video → Recommendation → Underlying research record` and in reverse `Research Record → Video → Recommendation edges → Community → Network`.

---

## 14. Community Detection & Overlap / Channel Ecosystem Analysis

**US-42.** As a researcher, I want communities identified using appropriate detection methods, with each community showing size, density, central nodes, dominant channels, internal relationships, external relationships, members, and cross-community relationships.

**US-43.** As a researcher, I want cross-community structure identified: cross-community edges, bridge nodes, bridge channels, shared channels, shared content, nodes appearing across ecosystems, and community-to-community connectivity.

**US-44.** As a researcher, I want to move `Network → Community → Channels` and answer: which channels dominate this community? which appear in multiple communities? which connect different communities? which are highly centralized/isolated? which repeatedly appear in recommendation paths? — integrated as part of network interpretation, not a separate dashboard.

---

## 15. Iterative Recommendation Expansion Engine

**US-45.** As a researcher, I want to launch an Iterative Recommendation Exploration experiment starting from an existing network, choosing the seed nodes exploration begins from.

**US-46.** As a researcher, I want the system to explicitly understand recommendation layers (`Layer 0` = original research videos, `Layer 1` = recommendations observed from Layer 0, `Layer 2` = recommendations from newly discovered Layer 1 nodes, etc.), preserving per layer: source node, newly discovered nodes, existing nodes, new edges, repeated nodes, channels, observation time, collection context.

**US-47.** As a researcher, I want the system to scrape ONLY newly discovered nodes at each layer — already-observed nodes must not be re-scraped within the same exploration experiment.
- Example: Layer 1 = {A,B,C,D,E}; Layer 2 discovers {B,C,D,F,G} → B,C,D already observed → only F,G enter the next scraping queue.

**US-48.** As a researcher, I want to configure stopping conditions: max depth, max nodes, max scraping operations, stop when no new nodes appear, stop when discovery rate falls below threshold, stop when repetition becomes very high, resource/time constraints.

**US-49.** As a researcher, I want live progress shown as research information, e.g. `Layer 0 → 20 seeds / Layer 1 → 143 discovered / Layer 2 → 91 new / Layer 3 → 24 new / Layer 4 → 3 new / Layer 5 → 0 new`.

**US-50.** As a researcher, I want every scraping experiment to explicitly declare its scraping context — Anonymous (no persistent logged-in identity) or Single-user (consistent researcher-provided session identity).

**US-51.** As a researcher using single-user mode, I want session context (cookies, browser profile, auth state) preserved consistently across layers, with expiration/failure recovery handled, and cookies/session data NEVER exposed in logs or UI.

---

## 16. Network Evolution & Saturation

**US-52.** As a researcher, I want per-layer evolution metrics: new nodes per layer, new edges per layer, repeated nodes per layer, unique channels per layer, community diversity per layer, cross-community transitions per layer.

**US-53.** As a researcher, I want cycle/repeated-structure detection (e.g. `A→B→C→A`, `A→B→C→D→A`) identifying cycles, repeated paths, strongly connected regions, recurrent recommendations, and repeated channel exposure — presented as an observed structural property, NEVER automatically labeled an "echo chamber."

**US-54.** As a researcher, I want to compare multiple iterations/observations over time, identifying persistent nodes, new nodes, missing nodes, persistent edges, new edges, community changes, centrality changes, channel changes, and echo-chamber-indicator changes.

---

## 17. Echo-Chamber Research

**US-55.** As a researcher, I want to run "Analyze Potential Echo Chambers" and receive analysis based on multiple independent indicators: internal connectivity, external connectivity, recommendation reinforcement, source concentration, cross-community exposure, repetition, convergence, and persistence.

**US-56.** As a researcher, I want the system to strictly distinguish community ("a structurally cohesive region of the observed network") from echo chamber ("a research interpretation supported by multiple indicators suggesting repeated, internally reinforced, relatively isolated exposure").
- Hard rule: never state "This is definitely an echo chamber." Instead: "This community exhibits strong characteristics associated with recommendation isolation," followed by supporting evidence.

**US-57.** As a researcher, I want a multidimensional Echo-Chamber Profile per ecosystem (e.g. Internal Connectivity: High, External Connectivity: Low, Source Concentration: High, Recommendation Reinforcement: High, Cross-Community Exposure: Low, Repetition: High, Persistence: High), never collapsed into one mysterious composite score — if a composite score is introduced, its components must remain inspectable.

**US-58.** As a researcher, I want per-ecosystem channel analysis: dominant channels, central channels, bridge channels, peripheral channels, channels appearing across multiple communities, channels responsible for cross-community exposure, channels repeatedly recommended, channels concentrated within one ecosystem — clickable to inspect underlying evidence.

**US-59.** As a researcher, I want to observe echo-chamber-relevant structure evolving across layers (e.g. Layer 0: High diversity → Layer 4: Very strong concentration), presented as evidence for me to interpret, NOT automatically labeled as an echo chamber.

---

## 18. Network Matrices

**US-60.** As a researcher, I want matrices generated appropriately for my network context: node adjacency matrix, weighted adjacency matrix, recommendation matrix (source video → recommended video), community matrix (community → community), channel-community matrix, channel-channel matrix, layer-transition matrix (Layer N → Layer N+1), and cross-community matrix — system determines which are appropriate rather than generating all blindly.

**US-61.** As a researcher, I want a dedicated Echo-Chamber Matrix per detected ecosystem with: community size, internal density, external connectivity, internal edge ratio, external edge ratio, channel concentration, recommendation reinforcement, cross-community exposure, repeated exposure, new node discovery, community persistence, central channels, bridge channels — comparable across ecosystems.

---

## 19. Research Insights

**US-62.** As a researcher, I want the system to generate research-oriented findings automatically at network, community, recommendation, and bridge level (e.g. "The network is highly concentrated around three channels," "Community A has substantially higher internal than external connectivity," "Layer 3 introduces significantly fewer new channels than Layer 1," "Channel X connects otherwise weakly connected communities").
- Every insight must include: Finding → Supporting metrics → Visualization → Underlying nodes/edges → Source research data.

**US-63.** As a researcher, I want Observed data, Derived metrics, and Analytical interpretation kept explicitly distinct at all times.
- Example — Observed: "85% of recommendation edges remain inside Community A." Derived: "Internal recommendation ratio = 0.85." Interpretation: "Community A exhibits strong internal recommendation concentration." These three levels must never collapse into one statement.

---

## 20. Provenance, Evidence & Reproducibility

**US-64.** As a researcher, I want every node traceable: `Node → Video → Source Dataset → Collection → Observation`.

**US-65.** As a researcher, I want every edge traceable: `Edge → Observed recommendation → Source Video → Target Video → Collection iteration → Observation timestamp/context`.

**US-66.** As a researcher, I want to reconstruct, for any collection, filter, sample, or analysis step: "what data produced this result?" and "what criteria produced this dataset?"

---

## 21. Longitudinal Research

**US-67.** As a researcher, I want the system to distinguish "when content was published" from "when we observed/collected it" everywhere — data model, collection metadata, recommendation observations, analytics, UI, and comparisons.

**US-68.** As a researcher, I want to run and compare multiple observations/iterations over time, identifying persistent/new/missing nodes and edges, and changes in community structure, centrality, channels, and echo-chamber indicators.

---

## 22. Data Quality & Coverage

**US-69.** As a researcher, I want to see requested-vs-collected-vs-failed-vs-unavailable counts for any collection run, plus flags for duplicate, missing, partial, temporal-gap, or unsupported-field records.

---

## 23. Script/Transcript External Storage

**US-70.** As a researcher, I want video scripts/transcripts stored as external `.txt` files with deterministic, collision-safe naming, with the persistent record storing only a path/reference — never full transcript text inline in Excel or the primary store.
- Handle missing scripts and failed extraction gracefully; preserve video↔script relationship and provenance; make the file accessible where appropriate; never duplicate script content redundantly.

---

## 24. Repository / Persistence Architecture

**US-71.** As a researcher/maintainer, I want all research/business/analytics logic to depend only on repository abstractions (never directly on Excel-specific behavior), so Excel can later be replaced by SQL or another provider without rewriting the research layer.
- Audit existing services for direct Excel coupling and correct any violations found.

---

## 25. Export

**US-72.** As a researcher, I want to export nodes, edges, network metadata, communities, layers, matrices, channel/community relationships, echo-chamber analysis, and research insights in an Excel-compatible format that also remains usable for downstream NetworkX and statistical analysis — internal network representation kept independent of Excel.

---

## 26. Technical Reference for Network Analysis (implementation grounding)

This section exists because "compute appropriate metrics/detect communities/analyze structure" is too vague to implement correctly. It gives concrete definitions so metrics are computed correctly and consistently. Use `networkx` (Python) as the reference implementation library unless the existing stack dictates otherwise.

### 26.1 Graph model
- The network is generally a **directed, weighted multigraph** at the observation level (a recommendation can be observed more than once, at different timestamps, potentially with different collection contexts) but should be reducible to a **directed weighted simple graph** for most analyses, where edge weight = observation count (or another explicit, documented weighting rule).
- Distinguish **directed** interpretation (`Video A → recommends → Video B` is not symmetric) from any **undirected** view (e.g. co-occurrence in the same community) — never silently collapse direction when it's semantically meaningful (recommendation, reply-to). `belongs_to`/`associated_with` relationships are structurally different from `recommends`/`replies_to` and should not be merged into one generic "edge type" without a `relationship_type` attribute.
- Every node and edge must carry a `source_ids` / `observation_ids` attribute list for provenance (see §20), not just an aggregate weight.

### 26.2 Core structural metrics — exact definitions
- **Density** (directed graph): `density = |E| / (|V| * (|V| - 1))`.
- **Degree**: `in_degree(v)` = number of incoming edges; `out_degree(v)` = number of outgoing edges; `degree(v) = in_degree + out_degree` for undirected treatment.
- **Average degree**: `2|E| / |V|` (undirected) or report in/out separately (directed) — do not silently pick one without documenting it.
- **Connected components**: for directed graphs, distinguish **weakly connected components** (ignore direction) from **strongly connected components** (respect direction, used for cycle/SCC detection in §26.5). Report both where relevant — they answer different research questions.
- **Isolated nodes**: `degree(v) == 0`.

### 26.3 Centrality measures — when to use which
- **Degree centrality**: normalized degree, `degree(v) / (|V| - 1)`. Use for "who has the most direct connections" — cheap, always computable, good default.
- **Betweenness centrality**: fraction of shortest paths passing through a node. Use for identifying **bridge/broker nodes** between communities (directly relevant to Epic on bridge nodes, §14, §17 channel bridging). Computationally expensive (`O(VE)` unweighted) — for large graphs use `k`-sample approximation (`networkx.betweenness_centrality(G, k=...)`) and document that it's an approximation.
- **Closeness centrality**: inverse of average shortest-path distance to all other nodes. Only meaningful on (weakly) connected graphs or components — compute per-component if the graph is disconnected, never silently ignore disconnection.
- **Eigenvector centrality**: a node is important if connected to important nodes. Only well-defined on graphs where convergence conditions hold (may fail on graphs with many zero-in-degree nodes / directed acyclic structure) — use `numpy`-backed solver, and fall back to reporting failure rather than a wrong result if it doesn't converge.
- **PageRank**: directed-graph-appropriate alternative to eigenvector centrality, handles disconnected/directed graphs robustly. **Prefer PageRank over eigenvector centrality for directed recommendation networks** — this is the standard choice in recommendation-network literature.
- Rule for "don't compute blindly" (§10 of source docs): compute degree + PageRank always (cheap, always valid); compute betweenness/closeness/eigenvector only when graph size is under a documented threshold (e.g. configurable, default suggestion: full exact betweenness under ~5,000 nodes, approximate above that) — and always label which were skipped and why in the UI, not silently omitted.

### 26.4 Community detection — algorithm choices
- **Default algorithm: Louvain method** (`python-louvain` / `networkx.algorithms.community.louvain_communities`) — modularity-based, fast, works well on large graphs, standard first choice for social/recommendation networks.
- **Alternative for higher-quality partitions: Leiden algorithm** (via `python-igraph` or `leidenalg`) — fixes known Louvain resolution-limit and disconnected-community issues; consider as an upgrade path if Louvain output has disconnected or poorly-separated communities.
- **Girvan-Newman** (edge-betweenness based, hierarchical) — much slower (`O(m²n)`), only appropriate for small graphs or when a hierarchical/dendrogram view of community structure is specifically needed.
- **Modularity** (`Q`) is the standard metric to report alongside any detected partition: `Q = (1/2m) * Σ [A_ij - (k_i*k_j)/2m] * δ(c_i, c_j)`. Report `Q` so the researcher can judge partition quality (values roughly 0.3–0.7 typically indicate meaningful community structure; near 0 indicates no real structure).
- **Resolution parameter**: Louvain/Leiden take a `resolution` parameter controlling community granularity — this should be a researcher-exposed control (higher resolution = more, smaller communities), not hardcoded.
- Community detection should generally run on the **undirected projection** of the graph unless a directed-aware method is explicitly used — document which was used.

### 26.5 Cycles, SCCs, and repetition detection (for §16, US-53)
- Use **strongly connected components** (`networkx.strongly_connected_components`) to find cyclic/recurrent structures in a directed graph — an SCC of size > 1 indicates a cycle exists among those nodes.
- Use `networkx.simple_cycles` for enumerating actual cycles (careful: exponential in worst case — cap max cycle length or node count before running on large graphs).
- "Repetition" (a node/channel repeatedly appearing across layers or recommendation paths) is a **frequency count**, not a graph-theoretic cycle — keep this conceptually distinct from cycle detection even though both feed echo-chamber indicators.

### 26.6 Echo-chamber indicators — concrete formulas
These operationalize the qualitative indicators in §17 (US-55/57) so they're computable, not just descriptive labels:
- **Internal connectivity**: edge density *within* a community — `internal_edges / possible_internal_edges` for that community's node set.
- **External connectivity**: `external_edges (community ↔ rest of graph) / total_edges_touching_community`.
- **Internal edge ratio**: `internal_edges / (internal_edges + external_edges)` — the single most direct "isolation" signal; report this prominently.
- **Source/channel concentration**: use a concentration index over the channel distribution within a community — e.g. **Herfindahl-Hirschman Index (HHI)**: `HHI = Σ (share_i)²` where `share_i` is channel i's share of nodes/edges in the community (0 = perfectly diverse, 1 = single channel dominates). This is a standard, well-understood concentration measure — prefer it over an ad hoc "top channel %" number, though both can be shown.
- **Recommendation reinforcement**: proportion of a node's outgoing recommendation edges that land back inside the same community — `intra_community_out_edges(v) / total_out_edges(v)`, aggregated (mean/median) across the community.
- **Cross-community exposure**: inverse framing of external connectivity, computed per-node then aggregated — fraction of a node's neighbors that belong to a *different* community.
- **Repetition**: count of distinct layers/observations in which the same node or channel reappears, normalized by total layers observed.
- **Convergence**: trend (e.g. linear regression slope, or simple delta) of internal-edge-ratio or channel-HHI across successive layers — positive/increasing slope = increasing concentration.
- **Persistence**: Jaccard similarity of community membership (node sets) between two iterations/observations — `|C_t ∩ C_t+1| / |C_t ∪ C_t+1|`; high and stable over time = persistent structure.
- Each indicator should be bucketed into a qualitative label (Low/Moderate/High) using **documented, adjustable thresholds** (not hardcoded magic numbers buried in code) — expose the thresholds as configuration so methodology is auditable.

### 26.7 Matrices — construction notes
- **Adjacency matrix**: `A[i][j] = 1` if edge exists (or weight if weighted); order rows/columns by a stable, documented node ordering (e.g. node ID ascending) so exports are reproducible and diffable across runs.
- **Layer-transition matrix**: rows = Layer N node set, columns = Layer N+1 node set, cell = whether/how-many edges connect them — this is effectively a bipartite adjacency matrix between consecutive layers, not the full-graph adjacency matrix restricted arbitrarily.
- **Channel-channel matrix**: aggregate video-level edges up to channel level — cell `[i][j]` = count (or normalized rate) of recommendation edges from any video of channel i to any video of channel j. Decide and document whether self-loops (same-channel recommendations) are included or reported separately (they matter a lot for concentration/reinforcement analysis).
- All matrices should be exportable as both raw counts and normalized/weighted versions — raw counts preserve reproducibility, normalized versions support cross-network comparison (ties into US-75, Network-to-Network comparison).

### 26.8 Complexity / scale guardrails
- Betweenness (exact): `O(V*E)` — flag as expensive above a configurable node-count threshold.
- Girvan-Newman: `O(m²n)` — small graphs only.
- `simple_cycles`: exponential worst case — bound before running.
- Louvain: near-linear, generally safe at scale — default choice for that reason.
- Always report which metrics were computed exactly vs. approximated vs. skipped-due-to-size in the UI/export metadata, so a researcher never mistakes an approximation for an exact value without knowing it.

---

## 27. Product-Wide Behavior Rules (apply to every story above)

- No orphan features: every feature must answer — what research problem does it solve? what data does it consume? what does it produce? where does its output go next? how is evidence inspected? how does it connect to the rest of the workflow?
- A route existing ≠ feature complete — verify real behavior, not endpoint names.
- Progressive disclosure: more researcher control ≠ more simultaneous UI surface — context-aware controls, advanced/collapsed sections, editable presets, never one giant generic panel.
- Presets are starting points, never constraints.
- Terminology discipline: always "Observed Recommendation Network," never "the YouTube Recommendation Algorithm Network."
- No GenAI unless it delivers genuine, explainable research value.
- UI must be built against real backend capability, never fake/static data — fix backend gaps before building frontend around them.
- Every capability needs tests (unit + integration, E2E where relevant) before being considered done.
- Every capability needs two-layer documentation: technical ("how it works") + research ("what the result means scientifically").
- Performance validated under domain-specific load: small/medium/large graphs, high duplication, high branching factor, deep recommendation layers — queue must not explode uncontrollably, duplicates removed efficiently, partial progress persisted, failed scraping resumable, UI stays usable.

---

## 28. Definition of Done

```
I have research data
 → I choose my research sources
 → I construct a network (duplicate-free, provenance-tracked)
 → I explore the network and understand communities and channels
 → I choose seed nodes and launch recommendation exploration
 → The network expands layer-by-layer, scraping only newly discovered nodes
 → Observation context (anonymous/single-user, session) is preserved
 → I observe network evolution, repetition, and convergence
 → I investigate potential echo chambers with multidimensional evidence
 → I inspect the channels and communities involved
 → I inspect matrices
 → I read research insights and trace every one back to evidence
 → I export the complete research artifacts for downstream NetworkX/statistical work
```