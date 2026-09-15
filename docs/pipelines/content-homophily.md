# Content Homophily: Structure × Meaning

> The scientifically distinctive pipeline of this repository. It measures **network structure** and **semantic content independently**, then asks whether they coincide.

**Canonical source** for this pipeline. The [methodology summary](../for-researchers/methodology.md) (Semantic Content Analysis, Content Homophily Analysis) is an overview — this document is the full technical and scientific characterization.

**Code:** `SocialScienceResearch/services/content_homophily_service.py` (1637 lines) · chunking `Ingestion_Pipline/ingestion/chunking.py` · embedding model default `Ingestion_Pipline/config/settings.py` (`DEFAULT_EMBEDDING_MODEL`) · communities `SocialScienceResearch/services/network_analytics_service.py` · structures `SocialScienceResearch/services/structural_metrics.py`

---

## 1. Why this pipeline exists

Traditional network analysis answers: *which nodes are connected, and do they form structurally dense groups?* A community-detection algorithm like Louvain can show that two groups of videos are structurally separated in a recommendation graph — but it cannot say **what those videos are about**, or whether the two groups talk about similar things despite being structurally apart.

The intuitive fix — handing transcripts to an LLM and asking it to classify communities — fails on two counts that motivated this design:

1. **LLMs are probabilistic, not deterministic.** The same batch of videos can yield slightly different classifications on repeated calls, which is impractical for a measurement that must be reproducible.
2. **Context window and cost.** Large transcript corpora exceed context limits, forcing ad-hoc batching across calls (more inconsistency) at high token cost.

The pipeline therefore replaces *generation* with *representation*: embedding models convert each transcript into a numerical vector capturing its semantic properties, deterministically given the same model, input, and configuration. Vectors are then compared arithmetically. No LLM ever judges, labels, or explains a community.

The research question becomes precise: **given structurally defined communities (Louvain, seed=42), is content within a community more semantically similar than content across communities — beyond what chance would produce?**

Related framing: [Structure vs Meaning](../concepts/structure-vs-meaning.md).

---

## 2. Inputs

| Input | Source | Requirement |
|---|---|---|
| Community labels | Shared network engine: `NetworkAnalyticsService.graph()` → `louvain_communities(seed=42)` over the requested scope (`run_id` or `video_ids`) | ≥ 2 community-labeled videos, else `insufficient_sample` |
| Transcripts | Existing artifacts reused first; otherwise targeted acquisition via the routed provider (yt-dlp captions or FreeTranscriptAPI) — only for videos in sampled pairs | Per-video `available | missing | unsupported`; never imputed |
| Embedding model | Reused `Ingestion_Pipline` stack: `build_embeddings(EmbeddingSettings())`, default `gemini-embedding-2-preview` | Model name + version recorded per result |
| Researcher parameters | `sampling_fraction` (default `0.10`), `max_pair_cap` (default `10_000`, absolute ceiling `10_000`), `random_seed` (default `42`), `num_permutations` (default `1_000`), `max_videos_per_community` (default `40`), `max_transcript_videos` (default `200`, absolute ceiling `2000`) | Cost bounds, not representativeness claims |

---

## 3. Stages in order

```
1. dataset_preparation      communities from shared engine; group videos by label
2. per-community cap        truncate each community to max_videos_per_community (default 40)
3. transcript budget         select balanced ≤ max_transcript_videos set, transcript-holders first
4. pair sampling             seeded within/between pair draws ONLY from the selected set
5. transcript_collection     targeted fetch for pair videos (ThreadPoolExecutor, ≤5 workers)
6. replacement sampling      swap unavailable videos for same-community peers (bounded)
7. embedding_preparation     chunk → embed → mean-pool → cache per video
8. similarity_calculation    cosine per pair; mean within, mean between
9. observed_difference       within_mean − between_mean
10. null_model                1,000 label-shuffling permutations with identical constraints
11. statistical_summary       null mean/std, z-score, finite-sample-corrected p-value
12. results                   payload with disclaimers, coverage, provenance
```

Stage names mirror `STAGES` in `content_homophily_service.py:105-115`.

---

## 4. Representation changes

```
recommendation edges (observed platform behavior)
  → directed graph → Louvain communities (STRUCTURE: who connects to whom)
  → transcripts (CONTENT: what each video says)
  → chunks (8000-token windows, 200 overlap — tiktoken-segmented text)
  → chunk embeddings (one vector per chunk — learned semantic projection)
  → video vector = mean of chunk vectors (one vector per video)
  → pairwise cosine similarities (scalar in [-1, 1] per pair)
  → within-mean vs between-mean (two scalars + their difference)
  → null distribution + z + p (is the difference surprising under label exchangeability?)
```

Each arrow is a different kind of operation (graph algorithm → retrieval → deterministic splitting → learned projection → arithmetic aggregation → statistic). §7 labels each one.

---

## 5. Algorithms and parameters (verbatim)

### 5.1 Communities — Louvain, `seed=42`

Communities are **reused**, never recomputed ad hoc: the same `louvain_communities(graph.to_undirected(), seed=42)` used by every other service (`network_analytics_service.py:123,907,1280,2410`; `structural_metrics.py:272`; `commenter_network_service.py:1114`). The pipeline records `COMMUNITY_ALGORITHM = "louvain_communities(seed=42)"` (`content_homophily_service.py:92`). The (slower) `greedy_modularity_communities` is imported only to document that it was deliberately *not* used (`network_analytics_service.py:31-33`).

> There is **no separate "greedy network sampling" algorithm** in this codebase. Cost control is achieved by the transcript-budget + pair-cap machinery below, plus deterministic per-community caps. Do not describe a greedy sampler that does not exist.

### 5.2 Cap and transcript budget (cost-first ordering)

1. **Per-community cap** (`capped_groups[c][:40]`): no single large community can dominate the analysis.
2. **Balanced budget selection** (`_select_bounded_videos`, `:924-957`): round-robin allocation across communities up to `max_transcript_videos` (default 200), **prioritizing videos that already have transcripts** (`sorted(key=(has_transcript?0:1, vid))`) so rate-limited YouTube 429s are avoided by reuse rather than courage.
3. **Pairs sampled only from the selected set.** Transcript/embedding collection can therefore never exceed the budget — the expensive step (acquisition) is bounded before the cheap step (cosines) is even planned.

### 5.3 Pair sampling — balanced within, stratified between

`PairSamplingService` (`:130-264`), seeded `random.Random(seed)`:

- **Target:** `min(int(available_pairs × fraction), cap)`, at least 1 when anything is available (`_target`, `:154-160`).
- **Within-community** draws are **balanced** across communities (each community contributes proportionally to `math.comb(n,2)`), so one giant community cannot flood the sample (`:218-…`).
- **Between-community** draws are **stratified by community pair** (weight `lenA × lenB`), so every community-pair stratum is represented (`:218-264`).
- Identical inputs (communities / members / config / seed) yield identical pairs — determinism is by construction.

### 5.4 Transcript collection — targeted, concurrent, honest

Only videos appearing in sampled pairs are fetched (`needed`, `:1229-1241`), via existing artifacts first, else the routed provider under a run context, concurrently (`ThreadPoolExecutor(max_workers=min(5, len))`, `:1256`). A channel with > 7 failures is skipped (`:1288-1293`). Every video ends `available | missing | unsupported` — never zero-filled.

### 5.5 Replacement sampling — bounded repair

Videos without usable transcripts are swapped for same-community peers, preferring embedded-unused, then embedded-used, then fresh videos, avoiding duplicate pairs (`:989-1106`). Bounded by `REPLACEMENT_TRIES_PER_VIDEO = 5`, `MAX_REPLACEMENT_SWEEPS = 4`, budget `max(20, 2 × pairs)` — the pipeline repairs the sample without ever scraping a whole community hunting for replacements.

### 5.6 Chunking — reused splitter, CSS-scale windows

`_ingestion_chunker` (`:408-433`) calls the **existing** `Ingestion_Pipline.ingestion.chunking.split_text` — `RecursiveCharacterTextSplitter.from_tiktoken_encoder` (`chunking.py:23-28`) — with `CONTENT_HOMOPHILY_EMBED_CHUNK_SIZE = 8000`, overlap `200` (`SocialScienceResearch/config/settings.py:75-76`). The large window is deliberate: at the ingestion default of 1000 tokens/chunk, a long transcript fans out into ~12 `batchEmbedContents` requests per video and breaks the Gemini free-tier request quota; at 8000 it stays under ~100 chunks (one batch request) so the global request limiter stays accurate.

### 5.7 Embedding — one model, pooled, cached

`VideoEmbeddingAdapter.video_vector` (`:483-555`): `embed_documents(chunks)` with `CONTENT_HOMOPHILY_EMBED_MAX_RETRIES = 5` and `Retry-After`/`retryDelay` (else `min(2·2^attempt, 60)` backoff, `:557-573`), then:

```
video_vector(v) = (1/n) · Σᵢ embed(chunkᵢ)        — mean pooling, :542
```

i.e. `pooled = np.mean(np.asarray(vectors, dtype=float), axis=0)`. Vectors are cached at `data_dir/embedding_cache/<safe-model>/<vid>.json` keyed by `sha256(model|version|text)` (`:485-607`); counters distinguish `reused / generated / failures`. The model name and version travel with every result.

### 5.8 Similarity — cosine, means, difference

`SemanticSimilarityService` (`:270-296`):

```
cos(u, v) = (u · v) / (‖u‖ ‖v‖),   clamped to [-1, 1]; zero-norm → None (pair skipped, never zero)
```

`u`, `v` are mean-pooled video vectors; the score is the cosine of the angle between the two videos' semantic representations — 1 = identical direction (maximally similar), 0 = orthogonal, −1 = opposed. `mean_similarity` averages over computable pairs only. The observed effect is:

```
observed = within_mean − between_mean               (:1441-1444)
```

### 5.9 Null model — label permutation, identical constraints

`ContentHomophilyNullModelService.run` (`:321-390`): shuffle community labels, re-apply the **same** per-community cap and the **same** sampler, each permutation seeded `random.Random(f"{seed}:{index}")`. With `n` usable permutation differences:

```
null_mean = Σd / n
var       = Σ(d − mean)² / n        (population variance)
std       = √var
z         = (observed − null_mean) / std          (None when std == 0)
p         = (1 + #{d ≥ observed}) / (1 + num_permutations)   — directional, finite-sample corrected
```

---

## 6. Worked miniature

Two communities, A = {a1, a2, a3}, B = {b1, b2}. Within pairs: (a1,a2), (a1,a3), (a2,a3). Between pairs: all six a–b combinations. Suppose cosines average 0.62 within and 0.41 between → `observed = 0.21`. The null shuffles labels 1,000 times (e.g. {a1,b1,b2} vs {a2,a3}) and recomputes the same difference each time; if the null centers near 0.0 with std 0.05, then `z ≈ 4.2`, `p ≈ 0.001` — the semantic clustering is surprising under label exchangeability. The pipeline reports exactly these numbers plus transcript coverage, so a reader can judge substance alongside significance.

---

## 7. AI vs deterministic logic

| Step | Nature |
|---|---|
| Transcript retrieval (yt-dlp / FreeTranscriptAPI) | Retrieval — deterministic given the same platform response |
| Chunking (`RecursiveCharacterTextSplitter` + tiktoken) | Deterministic transformation |
| Chunk embedding (Gemini) | **Learned model — the single neural step** |
| Mean pooling, cosine, means, difference | Deterministic arithmetic |
| Pair sampling, permutation null, z / p | Deterministic statistics (seeded RNG) |
| Louvain communities | Deterministic graph algorithm (`seed=42`) |
| Caching, retry/backoff, replacement | Deterministic orchestration |

No LLM classifies, labels, or explains anything in this pipeline. The embedding model projects text to vectors; everything after that is arithmetic a reviewer can reimplement from the formulas above.

---

## 8. Persistence and provenance

- **Video vectors:** disk cache `embedding_cache/<model>/<vid>.json` (`{model, version=1, digest, vector}`) — content-hash keyed, model-scoped.
- **Analysis record:** persisted run with stages, `sample_videos`/roles, `replacement_map`, `embedding_model/version/reused/generated/failures`, `chunking_configuration`, scope, `community_algorithm`, sampling config, disclaimers.
- **Every observation** carries `collection_run_id`; orphan `running/pending` runs are marked `interrupted` at boot (`:642-660`); cancellation yields `stopped`, exceptions `failed` with truncated error.

---

## 9. Failure modes

| Condition | Behavior |
|---|---|
| < 2 community-labeled videos / selected videos / pair videos | `insufficient_sample` / `insufficient_data` with reason — never a fabricated zero |
| No transcript for a video | Video skipped (or replaced same-community); counted in `without_transcript` |
| Embedding failure (incl. exhausted retries) | `None` + `embedding_failures` counter; pairs needing it are uncomputable and skipped |
| Zero-norm vector | Cosine `None`; pair skipped |
| Degenerate null (all permutations identical) | `z = None`, percentile-style `p` still reported |
| Empty chunk list | Warning + `None` |
| Cancelled / crashed | `stopped` / `failed` / boot-time `interrupted` |

---

## 10. Limitations — what this can and cannot establish

- **Similarity is topical, not ideological.** High cosine means the transcripts project nearby — shared topic, vocabulary, framing — not shared belief or attitude. See [Structure vs Meaning](../concepts/structure-vs-meaning.md).
- **Embedding-model dependence.** A different model projects differently; results are model-relative. The model travels with the result so comparisons stay within-model.
- **Transcript coverage.** Videos without captions drop out (or are replaced same-community); coverage is reported — read the effect size next to it.
- **Sampling fractions are cost bounds.** `0.10` / `10_000` / `40` / `200` bound computation; they are not a claim of statistical representativeness (disclaimer served verbatim with every payload, `:95-103`).
- **Permutation assumes exchangeability.** The null shuffles labels; if labels correlate with transcript availability or length, the null is approximate.
- **Mean pooling discards order and emphasis.** A video vector is an unweighted average of chunk vectors — long digressions count as much as the thesis. Fine for topical clustering; wrong tool for argument analysis.
- **Structure comes from one algorithm at one seed.** Louvain `seed=42` gives one partition; other algorithms/resolutions give others. The finding is conditional on that partition.
- **Observed difference ≠ causal effect, ≠ echo chamber.** See the verbatim disclaimers: evidence about observed content structure only — not proof of echo chambers, causality, user beliefs, or platform intent.

---

## 11. Parameters reference

| Parameter | Default | Absolute ceiling | Why it matters |
|---|---|---|---|
| `sampling_fraction` | `0.10` | — | Target share of available pairs; cost control |
| `max_pair_cap` | `10_000` | `10_000` | Hard ceiling per pair-selection op |
| `random_seed` | `42` | — | Full reproducibility (pairs + null) |
| `num_permutations` | `1_000` | — | Null resolution (min p ≈ 0.001) |
| `max_videos_per_community` | `40` | — | No community dominates; replacement limit |
| `max_transcript_videos` | `200` | `2000` | Dominant cost (YouTube 429s) bounded first |
| `CONTENT_HOMOPHILY_EMBED_CHUNK_SIZE` / `_OVERLAP` | `8000` / `200` | — | One batch request per video; quota-accurate |
| `CONTENT_HOMOPHILY_EMBED_MAX_RETRIES` | `5` | — | Transient 429s waited out, never dropped |
| `CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE` | `900_000` | — | Token pacing via shared `RateLimitedEmbedder` |
| `CONTENT_HOMOPHILY_EMBED_MAX_REQUESTS_PER_MINUTE` | `90` | — | Genuine Gemini free-tier 429 guard |

---

## 12. Related documents

- [Structure vs Meaning](../concepts/structure-vs-meaning.md) — the methodological distinction this pipeline operationalizes
- [Recommendation crawling](recommendation-crawling.md) — how the underlying graph is built
- [Echo-chamber signals](../for-researchers/echo-chamber.md) — the downstream S1–S5 consumer
- [Sampling](../for-researchers/sampling.md) — the reproducible-sampling substrate
- [Reproducibility](../for-researchers/reproducibility.md) — seeds, provenance, availability contract
- [Limitations](../for-researchers/limitations.md) — consolidated threats to validity
