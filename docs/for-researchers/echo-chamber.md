# Echo-Chamber Detection

> Five observable signals, structural metrics, and honest reporting of what can and cannot be inferred.

---

## Critical Distinctions

Before interpreting echo-chamber analysis, these distinctions must be understood:

### Community ≠ Echo Chamber

A community detected through structural or semantic analysis represents cohesion — groups of nodes that are densely connected or semantically similar. This cohesion does not, by itself, constitute an echo chamber. An echo chamber implies a specific informational dynamic: reduced exposure to diverse perspectives, reinforcement of existing views, and isolation from alternative information.

### Similarity ≠ Polarization

Semantic similarity between content — measured through transcript embeddings — indicates topical or relatedness. This does not establish ideological polarization. Two videos may be semantically similar (discussing the same topic) without exhibiting the attitudinal divergence that characterizes polarization.

### Recommendation ≠ Causal Influence

An observed recommendation edge — a platform-mediated connection between two videos — does not demonstrate that a user watched, accepted, or was influenced by the recommended content. Recommendation edges represent observable platform behavior, not user behavior or cognitive effects.

### Network Separation ≠ Psychological Isolation

Structural separation between communities — measured through low inter-community edge density — does not automatically prove psychological or attitudinal isolation. Users may access content across structural boundaries through means not captured in the network (e.g., external links, search).

---

## Five Observable Signals (S1-S5)

The echo-chamber detection system computes five structural signals from observed recommendation and interaction data:

### S1: Frontier Collapse Ratio

**What it measures:** Whether recommendation expansion narrows over successive layers.

**Formula (implemented, `echo_chamber_service.py:423-482`):**

```
per layer L (L ≥ 2):  S1_L = collapsed_L / total_L
scored (cumulative):  S1   = Σ collapsed_L / Σ total_L   over all layers L ≥ 2
```

where `collapsed_L` = edges of layer L whose *target* video already appeared in any earlier layer's frontier/discovered sets. Undefined before layer 2 → `unavailable`.

**Interpretation:** A declining frontier may suggest reduced content diversity in deeper recommendation layers. This is a structural observation, not evidence of user experience.

### S2: Seed-Community Concentration

**What it measures:** Whether recommendations cluster around the seed community.

**Formula (implemented, `echo_chamber_service.py:533-567`):** Louvain (`seed=42`) community share of the seed video's community, with modularity in `detail`:

```
comm_share    = |seed community| / n_nodes
concentration = clamp01(comm_share / base),  base = |seed community| / n_nodes
```

**Known implementation quirk:** as written, `base` equals the unrounded `comm_share`, so the scored value saturates at ≈ 1.0 whenever it is available. The informative carriers are the accompanying `detail` fields (`community_share`, `community_size`, `modularity`) — read those, not just the headline value. Recorded here rather than silently "fixed" because this is a documentation task; see [Limitations](limitations.md).

**Interpretation:** High concentration may suggest that recommendations reinforce existing community boundaries. This is observable structure, not evidence of information isolation.

### S3: Top-Channel Share

**What it measures:** Concentration of recommendation edges in a few channels.

**Formula (implemented, `echo_chamber_service.py:585-630`):** on the channel projection (video edges aggregated, weighted by `video_edge_count`):

```
S3 = max_c weighted_in(c) / Σ_c weighted_in(c)   (top-1 share; top-3 and seed-channel share in detail)
```

**Interpretation:** High concentration may suggest reduced diversity in recommended sources. This is a structural property of the recommendation network, not evidence of user exposure patterns.

### S4: Cross-Layer Repetition

**What it measures:** Whether the same content persists across recommendation layers.

**Formula (implemented, `echo_chamber_service.py:633-677`):**

```
S4 = #{video pairs observed in ≥ 2 distinct layers} / #{distinct video pairs}
```

with the channel-pair analog (`channel_repeat`) in `detail`. Needs ≥ 2 crawled layers, else `unavailable`.

**Interpretation:** High repetition may suggest that the recommendation system repeatedly surfaces the same content across layers. This is observable platform behavior, not evidence of user consumption.

### S5: Commenter-Overlap Reinforcement

**What it measures:** Whether commenters within recommended videos are from the same community.

**Formula (implemented, `echo_chamber_service.py:680-719`):** mean Jaccard overlap between the seed video's commenter set and each of the top-`S5_TOP_K = 5` recommended videos' sets (ranked by in-degree), skipping videos without collected comments:

```
S5 = mean_v |C_seed ∩ C_v| / |C_seed ∪ C_v|
```

Available only when comments were collected and at least one top video has commenters — otherwise `unavailable`, never zero.

**Interpretation:** High overlap may suggest that recommendations connect videos with similar audiences. This is a structural observation about audience composition, not evidence of social reinforcement.

---

## Structural Metrics

The echo-chamber analysis includes structural metrics beyond the five signals:

| Metric | Description |
|---|---|
| **Modularity** | Strength of community division in the recommendation network |
| **Conductance** | Ratio of external to total edges per community |
| **Within-community rate (WCR)** | Proportion of directed edges within communities |
| **Null-model WCR** | Degree-preserving random graph comparison |
| **Community persistence** | Jaccard overlap of communities across layers |
| **Channel concentration** | Top Channel Share + Herfindahl-Hirschman Index (HHI) |

---

## Composite Scoring

The five signals are combined into a weighted composite score (`services/echo_scoring.py:72-149`) — a weighted mean over **available** signals only, weights renormalized over what was observed:

```
score = Σ_{available k} w_k · clamp01(value_k) / Σ_{available k} w_k
```

Any missing core signal (S1–S4) forces the verdict to `inconclusive` while the indicative score is still shown and labeled.

| Signal | Weight |
|---|---|
| S1: Frontier collapse | 0.35 |
| S2: Seed-community concentration | 0.30 |
| S3: Top-channel share | 0.20 |
| S4: Cross-layer repetition | 0.15 |
| S5: Commenter-overlap reinforcement | 0.15 |

### Verdict Bands

| Score Range | Verdict |
|---|---|
| < 0.40 | no_chamber_yet |
| 0.40 – 0.60 | weak |
| 0.60 – 0.75 | moderate |
| > 0.75 | strong |

**Important:** The composite score is a heuristic combination, not a validated instrument. The weights are arbitrary, not empirically derived. The verdict bands are reasonable thresholds, not established cutoffs.

---

## Data Availability

Every signal is wrapped with `status: available | unavailable`, ensuring honest reporting:

- If data is insufficient to compute a signal, the status is `unavailable`
- The composite score only includes signals with `available` status
- Missing signals do not default to zero

---

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `MAX_LAYERS_TOTAL` | 10 | Maximum total layers across all continuations |
| `DEFAULT_MAX_LAYERS` | 5 | Default layers per detection run |
| `S5_TOP_K` | 5 | Number of top recommended videos for S5 |

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `POST /echo-chamber/detect` | Start a detection job |
| `GET /echo-chamber` | Paginated detection list |
| `GET /echo-chamber/{id}` | Status + timeline + composite score |
| `GET /echo-chamber/{id}/lens` | Recompute lens (video/channel projection) |
| `GET /echo-chamber/{id}/structure` | Full structural analysis |
| `GET /echo-chamber/{id}/audience` | Commenter overlap lens |
| `POST /echo-chamber/{id}/continue` | Append more layers |
| `POST /echo-chamber/{id}/stop` | Cooperative stop between layers |

---

## Honest Reporting

The system reports what it can observe and explicitly flags what it cannot:

**Can observe:**

- Structural patterns in recommendation networks
- Community cohesion and separation
- Recommendation concentration and repetition
- Commenter overlap within and between communities

**Cannot observe (from structural data alone):**

- Whether users actually consumed recommended content
- Whether users experienced information isolation
- Whether content similarity reflects ideological alignment
- Whether community separation reflects psychological effects

Claims about echo chambers, polarization, or information fragmentation require behavioral or experimental evidence beyond the structural observations this system provides.
