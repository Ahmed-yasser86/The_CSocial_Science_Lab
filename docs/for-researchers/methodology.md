# Research Methodology

> How abstract research concepts are operationalized into computational procedures.

---

## Core Scientific Principle

The project never fabricates or estimates data. Every observation is collected from the source and preserved with explicit data-availability status. Missing data is `missing`, never zero. Unsupported data is `unsupported`, never imputed. This principle applies across all analytical components.

---

## Observation Types

The system distinguishes four observation types:

| Type | Description | Example |
|---|---|---|
| **Channel metadata** | Name, subscriber count, description | Collected via yt-dlp |
| **Video metadata** | Title, views, likes, upload date, duration | Collected via yt-dlp |
| **Comment** | Author, text, likes, timestamp, reply structure | Collected via YouTube Data API |
| **Recommendation** | Directed edge between videos with rank | Collected via three-layer fallback |
| **Transcript** | Video caption text | Collected via captions (opt-in) |

Every observation carries a `collection_run_id` linking it to its collection event, ensuring full provenance.

---

## Social Network Construction

### Input

Collected comments with author identifiers and video associations.

### Operationalization

Social interaction → co-comment participation. Two authors are connected if they comment on the same video. This is an indirect but observable proxy for social interaction within the platform.

### Representation

Weighted graph where:

- **Nodes:** Commenters (identified by `author_id` with `author_name` fallback)
- **Edges:** Co-comment participation (two authors commenting on the same video)
- **Edge weight:** Jaccard similarity, overlap coefficient, or co-comment frequency

### Computation

1. Group comments by video
2. For each video, identify all commenters
3. Create co-comment edges between all commenter pairs
4. Compute edge weights (Jaccard, overlap coefficient)
5. Build NetworkX graph

### Output

Commenter co-comment network with weighted edges, available in video-level and channel-level projections.

### Interpretation

Structural proximity in this network indicates shared audience participation. Bridge commenters (active across ≥2 communities) connect otherwise separate audience segments.

### Limitations

- Co-commenting is an indirect measure; it does not capture reply relationships, conversation quality, or interaction sentiment
- Only commenters who choose to comment are represented; lurkers are excluded
- Identity resolution depends on author name consistency

---

## Semantic Content Analysis

### Input

Video transcripts (collected or extracted).

### Operationalization

Content similarity → transcript embedding cosine similarity.

### Representation

- Vector embeddings per video (configurable embedding model)
- Pairwise similarity matrix

### Computation

1. **Text splitting:** RecursiveCharacterTextSplitter with tiktoken token counting
2. **Embedding generation:** Convert transcripts to vector representations
3. **Pair sampling:** Sample within-community and between-community video pairs (with same-community replacement sampling)
4. **Similarity computation:** Cosine similarity for each pair
5. **Null model:** Permutation test with label shuffling (seeded RNG)
6. **Statistical testing:** z-score and p-value computation

### Output

- Within-community and between-community similarity distributions
- Permutation null test results (z-score, p-value)
- Edge-level similarity scores

### Interpretation

Significantly higher within-community similarity relative to between-community similarity indicates content homophily. The permutation test establishes whether observed similarity patterns exceed what would be expected by chance.

### Limitations

- Embedding quality depends on the chosen model; different models may produce different similarity structures
- Transcript availability varies; not all videos have captions
- Semantic similarity measures topical relatedness, not ideological alignment
- The permutation test assumes exchangeability of labels

---

## Recommendation Network Collection

### Input

Seed video URLs.

### Operationalization

Platform recommendation → observable "Up Next" / related video edges.

### Representation

Directed graph where:

- **Nodes:** Videos (with metadata enrichment)
- **Edges:** Directed, source → recommended-video, with rank position
- **Edge attributes:** observation provenance (extraction layer), collection timestamp, layer index

### Computation

Three-layer fallback extraction:

1. **Primary:** yt-dlp native fields (`recommended_videos`, `related`)
2. **Secondary:** `yt-search-python` INNERTUBE `/next` endpoint
3. **Tertiary:** Page-dump parser for "Up Next" sections

BFS layered expansion with:

- Frontier management (which videos to crawl next)
- Snapshot classification (NEW_VIDEO, EXISTING_VIDEO, NEW_CHANNEL, CONNECTED, DISCONNECTED)
- Layer persistence (each layer is a discrete `LayerRun`)

### Output

Directed recommendation graph with per-layer provenance, frontier reports, and component analysis.

### Interpretation

Directed edges represent observed platform-mediated content connections. Layer expansion reveals how the recommendation network grows from a seed, not just its immediate neighbors.

### Limitations

- Recommendations are personalized and time-varying; collected data represents a snapshot
- Not all recommendation sources may be captured by the three-layer fallback
- The observation is of the platform's behavior, not user behavior

---

## Echo-Chamber Detection

### Input

Recommendation network with community structure.

### Operationalization

Echo-chamber dynamics → five observable structural signals (S1-S5).

### Representation

Per-signal scores with status indicators; composite score with verdict bands.

### Computation

| Signal | Method |
|---|---|
| S1: Frontier collapse ratio | Measures whether recommendation expansion narrows over layers |
| S2: Seed-community concentration | Measures whether recommendations cluster around the seed community |
| S3: Top-channel share | Measures concentration of recommendation edges in few channels |
| S4: Cross-layer repetition | Measures whether the same channels persist across layers |
| S5: Commenter-overlap reinforcement | Measures whether commenters within recommendations are from the same community |

Composite scoring: s1=0.35, s2=0.30, s3=0.20, s4=0.15, s5=0.15

Verdict bands: <0.40 no_chamber_yet, 0.40-0.60 weak, 0.60-0.75 moderate, >0.75 strong

### Output

Echo-chamber detection with per-layer timeline, structural metrics (modularity, conductance, WCR), and composite score.

### Interpretation

Signals indicate structural patterns consistent with echo-chamber-like dynamics. These are observable proxies, not proof of echo chambers. The composite score is a heuristic combination, not a validated instrument.

### Limitations

- Structural signals cannot establish cognitive or attitudinal effects
- Personalized recommendations may differ from collected data
- The composite scoring weights are arbitrary, not empirically validated
- MAX_LAYERS_TOTAL=10 caps the analysis depth

---

## Content Homophily Analysis

### Input

Videos with transcripts and community labels.

### Operationalization

Content homophily → semantic similarity within vs. between communities.

### Representation

Pairwise similarity scores with community membership.

### Computation

1. Collect transcripts for videos in scope
2. Generate embeddings
3. Sample within-community and between-community pairs
4. Compute cosine similarity for each pair
5. Run permutation null test (label shuffling)
6. Compute z-score and p-value

### Output

Within-community and between-community similarity distributions with statistical significance.

### Interpretation

Significantly higher within-community similarity indicates content homophily.

### Limitations

- Depends on transcript availability and embedding quality
- Permutation test assumes exchangeability
- Results are specific to the chosen embedding model

---

## Commenter Overlap Analysis

### Input

Comments with author and video associations.

### Operationalization

Audience overlap → shared commenters between videos/channels.

### Representation

Pairwise overlap metrics (Jaccard, overlap coefficient, intersection).

### Computation

1. Chunked streaming scan (5000 chunks) for memory efficiency
2. Identity resolution: `author_id` first, `author_name` fallback
3. Memoization with short TTL (60s) and entry cap (128)
4. Overlap metrics computation
5. Bridge-commenter identification (active across ≥ min_entities distinct units)

### Output

Overlap scores, bridge-commenter profiles, co-commenter network edges.

### Interpretation

High overlap indicates shared audience. Bridge commenters span multiple communities, potentially facilitating cross-community information flow.

### Limitations

- Commenting is voluntary and may not represent the full audience
- Identity resolution depends on name consistency
- Memoization introduces short-term caching effects

---

## Operationalization Table

| Research Concept | Computational Representation | Implementation |
|---|---|---|
| Social interaction | Commenter co-comment network | `services/commenter_network_service.py` |
| Content similarity | Transcript embedding cosine similarity | `services/content_homophily_service.py` |
| Content community | Louvain community on content graph | `services/network_analytics_service.py` |
| Recommendation relationship | Directed source → recommended-video edge | `services/recommendation_graph_service.py` |
| Recommendation expansion | BFS layered crawl with frontier | `services/layer_scrape_service.py` |
| Community connectivity | Cross-community edge density, conductance | `services/structural_metrics.py` |
| Information fragmentation | Structural/semantic separation measures | Community metrics (WCR, modularity) |
| Recommendation exposure | Observable recommendation pathways | `services/recommendation_graph_service.py` |
| Echo-chamber dynamics | Five observable signals (S1-S5) | `services/echo_chamber_service.py` |
| Audience overlap | Jaccard/overlap coefficient on commenters | `services/commenter_overlap_service.py` |
| Bridge users | Commenters active across ≥2 communities | `services/commenter_overlap_service.py` |
| Semantic homophily | Within vs. between community similarity | `services/content_homophily_service.py` |
