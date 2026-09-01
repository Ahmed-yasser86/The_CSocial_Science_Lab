# Content Homophily — Architecture Analysis & Embedding Pipeline Spec

Scope: **architecture analysis.** This document describes the content homophily
analysis pipeline — video selection, embedding, similarity computation, and
statistical testing — as implemented in `SocialScienceResearch/`. All paths are
relative to `SocialScienceResearch/`. Line numbers were read from the working
tree and should be re-verified at implementation time.

Primary source files:

- `services/content_homophily_service.py` — main pipeline, null model, replacement sampling
- `services/dataset_service.py` — dataset preparation helpers
- `services/collection_service.py` — transcript fetching, artifact I/O

---

## 1. Video Selection & Sampling

The content homophily analysis selects a stratified sample of videos from the
network, grouped by community membership. Selection proceeds through four
cascading filters, each applying a budget cap.

### 1.1 Entry point

`ContentHomophilyService.start()` validates parameters, creates an analysis
record with `"status": "pending"`, and submits a background worker. The worker
calls `_run_analysis()` → `_pipeline()`, which orchestrates the full flow.

### 1.2 Dataset preparation

`_pipeline()` first builds the eligible video pool:

1. Calls `NetworkAnalyticsService.graph()` to obtain the full network graph.
2. Filters to nodes where `community_id is not None` — videos without a
   community assignment are excluded.
3. Builds two lookup structures:
   - `labels: dict[str, int]` — maps each `video_id` to its `community_id`.
   - `groups: dict[int, list[str]]` — maps each `community_id` to its member
     video IDs.

If fewer than 2 eligible videos exist, the analysis returns early with an
"insufficient data" status.

### 1.3 Per-community cap

Each community is truncated to `max_videos_per_community` (default **40**).
This prevents any single large community from dominating the sample. The
capped groups are stored as `capped_groups`.

### 1.4 Transcript-video budget

`_select_bounded_videos(capped_groups, max_transcript_videos)` distributes a
total budget of `max_transcript_videos` (default **200**) across communities
proportionally using `_allocate_balanced()`. Within each community, videos
are sorted by:

```python
(0 if has_transcript else 1, video_id)
```

This gives **transcript-first priority** — videos that already have a
cached transcript are preferred, reducing API calls. The tie-break by
`video_id` ensures deterministic selection.

`_video_has_transcript()` checks by reading the artifact file directly
(artifact store), not by querying the database status.

### 1.5 Pair sampling

After budget allocation, `PairSamplingService` draws comparison pairs from
the selected video set:

- **Within-community pairs**: `sample_within()` computes all unique pairs
  within each community (`math.comb(n, 2)`), then draws a balanced sample
  across communities.
- **Between-community pairs**: `sample_between()` computes all cross-community
  pairs (product of member counts for each community pair), then draws
  similarly.

The target sample size per stratum is:

```python
min(int(available * sampling_fraction), max_pair_cap)
```

where `sampling_fraction` defaults to **10%** and `max_pair_cap` defaults
to **10,000**. A minimum of 1 pair is guaranteed if any exist.

Pairs are drawn via `_draw()`:
- Small spaces (≤ `max(4k, 50,000)` available): all pairs materialized,
  deduplicated, then `rng.sample()`.
- Large spaces: rejection sampling with a limit of `k * 50 + 100` attempts.

### 1.6 Exclusion filters

Videos are excluded at various stages by:

1. Missing `community_id` — no community assignment from Louvain detection.
2. Per-community cap (default 40).
3. Transcript-video budget (default 200).
4. Transcript fetch failure with no available replacement.
5. **Channel-level circuit breaker**: after **>7** transcript failures from
   one channel, remaining videos from that channel are skipped to avoid
   wasting quota on a consistently unavailable channel.

---

## 2. Embedding Pipeline

### 2.1 Model & provider

The embedding model is resolved via:

```python
from Ingestion_Pipline.infra.embeddings import build_embeddings
return build_embeddings(EmbeddingSettings())
```

By default this produces a **Gemini** embedding model (configured via the
`EMBEDDING` environment variable, default `google_genai:gemini-embedding-2-preview`).

Rate limiting is applied when `CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE`
is set (> 0). The default budget is **900,000 tokens/minute**, enforced by
wrapping the embedder in a `RateLimitedEmbedder`.

### 2.2 `VideoEmbeddingAdapter`

This class (defined at line 456 of `content_homophily_service.py`) manages
per-video embedding with caching. Its core method is `video_vector(video_id, text)`.

**Processing steps:**

1. **Cache lookup**: computes a SHA-256 digest of
   `f"{model_name}|{model_version}|{text}"` and checks the on-disk cache.
   On hit, increments `embeddings_reused` and returns the cached vector
   immediately.

2. **Chunking**: the full transcript text is passed to `_ingestion_chunker()`,
   which wraps it in a LangChain `Document` and calls `split_text()` with
   `chunk_size=8000` and `chunk_overlap=200`.

3. **Embedding**: calls `embed_documents(chunks)` on the LangChain embedder.
   Retries up to `CONTENT_HOMOPHILY_EMBED_MAX_RETRIES` (default **5**) times
   with exponential backoff or parsed Gemini retry-delay messages.

4. **Mean pooling**: all chunk vectors are averaged into a single video-level
   vector via `np.mean(np.asarray(vectors, dtype=float), axis=0)`.

5. **Cache write**: the pooled vector is persisted to disk. Increments
   `embeddings_generated`.

6. **Failure handling**: any exception increments `embedding_failures` and
   returns `None`. A failed video never aborts the overall run.

### 2.3 Transcript fetching

`_ensure_transcript(video_id, analysis_id)`:

1. Checks for an existing artifact file via `_read_artifact_text(video_id)`.
2. If available and non-empty, returns immediately (no API call).
3. Otherwise, constructs a YouTube URL and calls
   `self._provider.extract_transcript(url, lang=lang)`.
4. On success, writes the artifact to the transcript store and persists a
   `TranscriptRecord`.
5. On failure, saves a record with `TranscriptStatus.UNSUPPORTED`.

### 2.4 Unavailable transcripts

When a transcript cannot be fetched:

- The video is added to a `known_missing` set and is never re-attempted
  as a replacement candidate.
- During replacement sampling, a same-community peer with a valid transcript
  is substituted into the pair.
- If the replacement also fails, it too is added to `known_missing`.
- After all replacements, any pair where either video lacks a vector is
  **dropped** (counted in `meta["pairs_dropped"]`).
- Missing transcripts are **never treated as zero similarity** — they are
  excluded from the computation entirely.

---

## 3. Embedding Cache

### 3.1 Structure

Cached embeddings are stored as JSON files at:

```
{data_dir}/embedding_cache/{safe_model}/{video_id}.json
```

where `safe_model` is the model name with non-alphanumeric characters
stripped. Each file contains:

```json
{
  "video_id": "...",
  "model": "...",
  "model_version": "1",
  "digest": "<sha256hex>",
  "vector": [0.123, -0.456, ...]
}
```

### 3.2 Cache key

The cache key is a SHA-256 hash of `f"{model_name}|{model_version}|{text}"`.
This means:

- Same transcript + same model → cache hit.
- Different model or different transcript text → cache miss (new entry created,
  old entry left as orphan).

### 3.3 Invalidation

Cache invalidation is **implicit via digest mismatch**. Changing the model,
model version, or transcript text produces a new digest, so the old entry is
simply unused. Orphan files are not cleaned up automatically.

### 3.4 Counters

| Counter | Incremented when |
|---|---|
| `embeddings_reused` | Cache hit — `_load_cache()` returns a valid vector |
| `embeddings_generated` | Fresh embedding computed and written to cache |
| `embedding_failures` | No chunks produced, `embed_documents()` returns empty, or any exception |

---

## 4. Similarity Computation

### 4.1 Within-community similarity

`PairSamplingService.sample_within()` generates comparison pairs where both
videos belong to the same community. The number of pairs per community is
proportional to the community's size, distributed via `_allocate_balanced()`.

### 4.2 Between-community similarity

`PairSamplingService.sample_between()` generates pairs where videos come
from different communities. Each unique community pair `(a, b)` forms a
stratum, with available pairs = `|members_a| × |members_b|`.

### 4.3 Cosine similarity

`SemanticSimilarityService.cosine()` computes standard cosine similarity:

```python
value = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
return max(-1.0, min(1.0, value))
```

The result is clamped to `[-1, 1]` to guard against floating-point drift.

`SemanticSimilarityService.mean_similarity(matrix, pairs)` iterates over all
pairs, computes cosine for each, and returns the mean. Pairs with zero-norm
vectors (uncomputable) are **skipped, never treated as zero**.

### 4.4 Pair cap logic

`_target(available)` computes the desired sample size:

```python
min(int(available * sampling_fraction), max_pair_cap)
```

The fraction (default 10%) is applied first, then the cap (default 10,000).
An absolute ceiling of `ABSOLUTE_MAX_PAIR_CAP = 10,000` is enforced at
parameter validation time.

---

## 5. Statistical Testing

### 5.1 Null model

`ContentHomophilyNullModelService.run()` performs a permutation test to
assess whether the observed within-community similarity exceeds what would
be expected under random community assignment.

**Procedure:**

1. For each of `num_permutations` (default **1,000**) iterations:
   - Create a deterministic RNG: `random.Random(f"{seed}:{index}")`.
   - Shuffle the community labels across all videos.
   - Regroup videos by the shuffled labels.
   - Apply the same per-community cap (default 40).
   - Sample within- and between-community pairs using the **same sampling
     policy** as the observed analysis.
   - Compute the difference: `within_mean - between_mean`.

2. The result is a null distribution of `num_permutations` difference values.

### 5.2 Z-score

```python
z_score = (observed_difference - null_mean) / null_std
```

where `null_std` uses **population variance** (`/ num`, not `/ (num - 1)`).
With 1,000 permutations the distinction is negligible, but technically
incorrect for small permutation counts.

When `std == 0.0` (all permutations produce identical differences), the
z-score is set to `None`.

### 5.3 P-value

```python
exceed = sum(1 for d in differences if d >= observed_difference)
p_value = (1 + exceed) / (1 + num_permutations)
```

This is a **one-sided, finite-sample corrected** p-value with the `+1`
numerator/denominator correction per spec §17. It tests whether the observed
difference exceeds the null distribution.

---

## 6. Configuration Reference

### 6.1 Tunable parameters

| Parameter | Default | Hard Cap | Env Variable |
|---|---|---|---|
| Sampling fraction | 10% | — | `CONTENT_HOMOPHILY_SAMPLING_FRACTION` |
| Max pair cap | 10,000 | 10,000 | `CONTENT_HOMOPHILY_MAX_PAIR_CAP` |
| Max videos per community | 40 | — | `CONTENT_HOMOPHILY_MAX_VIDEOS_PER_COMMUNITY` |
| Max transcript videos | 200 | 2,000 | `CONTENT_HOMOPHILY_MAX_TRANSCRIPT_VIDEOS` |
| Permutations | 1,000 | 10,000 | `CONTENT_HOMOPHILY_NUM_PERMUTATIONS` |
| Embed chunk size | 8,000 chars | — | `CONTENT_HOMOPHILY_EMBED_CHUNK_SIZE` |
| Embed chunk overlap | 200 chars | — | `CONTENT_HOMOPHILY_EMBED_CHUNK_OVERLAP` |
| Embed max retries | 5 | — | `CONTENT_HOMOPHILY_EMBED_MAX_RETRIES` |
| Embed TPM budget | 900,000 | — | `CONTENT_HOMOPHILY_EMBED_MAX_TOKENS_PER_MINUTE` |
| Channel failure threshold | 7 | — | hardcoded |

### 6.2 Replacement sampling

When a video in a pair has no transcript, a same-community peer is
substituted. The replacement logic is bounded by:

- `REPLACEMENT_TRIES_PER_VIDEO = 5` — attempts per video before giving up.
- `MAX_REPLACEMENT_SWEEPS = 4` — full passes over all pairs.
- `REPLACEMENT_BUDGET_MIN = 20` — minimum videos eligible for replacement.

Replacement candidates are drawn from `capped_groups` (the per-community
capped pool), not from `selected_groups` (the transcript-budget subset).
This means a replacement video may require a fresh transcript fetch beyond
the original budget.

---

## 7. Known Limitations & Design Notes

1. **Z-score dead-code**: When `std == 0.0`, the code conditionally computes
   a z-score then unconditionally overwrites it with `None`. The
   `float("-inf")` case (all null differences < observed) is lost.

2. **Population vs sample variance**: The null standard deviation uses
   `/ num` (population), not `/ (num - 1)` (sample). Effectively negligible
   at 1,000 permutations.

3. **Mean pooling**: All chunk embeddings are averaged regardless of chunk
   count or content quality. A very long transcript with many chunks may
   dilute signal compared to a short transcript's single chunk.

4. **`model_version` hardcoded to `"1"`**: No mechanism to bump it when
   chunking or embedding parameters change. Changing `chunk_size` or
   `chunk_overlap` could silently produce vectors mismatched with the cache
   unless the model name also changes.

5. **No transcript length filter**: Transcripts of any length are accepted.
   A 1-second auto-generated transcript with a single word still produces
   an embedding.

6. **Replacement budget leakage**: Replacement candidates come from
   `capped_groups`, not `selected_groups`, so a replacement may trigger a
   fresh transcript fetch beyond the original budget.

7. **In-memory channel failure tracking**: The `channel_failures` dict resets
   if the analysis is restarted, so a flaky channel could be retried from
   scratch.

8. **Rejection sampling limit**: `k * 50 + 100` attempts for large spaces.
   For `k` near the 10,000 cap this is 500,100 attempts — adequate but could
   fail in extremely sparse spaces.

9. **Seed independence**: `_select_bounded_videos` is deterministic by data
   order (seed-independent), while `sample_within`/`sample_between` are
   seeded. The transcript budget selection is not reproducible across data
   changes, but pair sampling is.

10. **Cache orphan accumulation**: Old cache entries are never cleaned up.
    Changing the model or transcript text leaves orphan files on disk.
