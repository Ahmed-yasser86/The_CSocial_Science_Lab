# Case Study — From a YouTube channel to a published network

> This is the end-to-end journey the platform is built for. Every step maps to a real endpoint in `SocialScienceResearch/api/openapi.json`.

## The research question

> *"Which channels form an audience community around a seed channel, and can I quantify whether that community is an echo chamber?"*

## Step 1 — Collect (observe, don't assume)

Start by collecting a seed channel's videos and the recommendations yt-dlp observes:

```
POST /api/v1/social-science/collect           # enqueue a collection job
GET  /api/v1/social-science/jobs/{job_id}     # track progress
GET  /api/v1/social-science/runs/{run_id}     # inspect the resulting run
GET  /api/v1/social-science/videos/{video_id}/recommendations  # the observed edges
```

- Every observation carries `collection_run_id` + `observed_at` + `raw_json` (`SocialScienceResearch/domain/models.py`).
- If the provider returns no recommendations, the system surfaces `recommendation_unsupported` — it never fabricates edges.

## Step 2 — Understand the dataset honestly

```
GET /api/v1/social-science/coverage            # availability per field
GET /api/v1/social-science/explore/records      # browse what was observed
GET /api/v1/social-science/dataset/summary      # size + health of the dataset
GET /api/v1/social-science/videos/{id}/observations
```

Missing data is flagged `available | missing | unsupported`, never zeroed (`domain/enums.py:137`).

## Step 3 — Sample deterministically

```
POST /api/v1/social-science/sampling/advanced   # stratified / top / random
GET  /api/v1/social-science/samples/{id}        # inspect the persisted sample
POST /api/v1/social-science/samples/compare     # overlap analysis
```

Sampling is **seeded** (`SOCIAL_SAMPLING_SEED=42`) so a colleague reproduces your exact sample (`sampling_service.py:356`).

## Step 4 — Build and analyze the network

```
GET  /api/v1/social-science/network/graph?weight=recommendation:observation_count
GET  /api/v1/social-science/network/centralities    # 10-measure battery
GET  /api/v1/social-science/network/metrics          # density, reciprocity, communities
GET  /api/v1/social-science/network/communities      # Louvain, seed=42
GET  /api/v1/social-science/network/roles            # core / broker / periphery / bridge
GET  /api/v1/social-science/network/commenters/graph # the audience network family
GET  /api/v1/social-science/network/commenters/overlap  # Jaccard / overlap coefficient
```

Change the lens: **recommendation** family (`recommendation:...` weights) or **audience** family (`commenters/*`). Weight grammar in `SocialScienceResearch/services/weight_spec.py`.

## Step 5 — Test a scientific hypothesis

```
POST /api/v1/social-science/network/test-difference
     # permutation / bootstrap, seeded, returns p_value + ci95
```

Two networks, ran at different times or under different weights, can be compared with a **seeded permutation test** that reports `p_value` and a 95% CI (`network_analytics_service.py` `run_resampling_test`).

## Step 6 — Detect an echo chamber

```
POST /api/v1/social-science/echo-chamber/detect
GET  /api/v1/social-science/echo-chamber/{detection_id}
```

The echo-chamber service crawls layers around a seed and computes **S1–S5 signals** over observed edges only — frontier collapse, seed-community concentration, top-channel share, cross-layer repetition, commenter-overlap — each explicitly `available` or `unavailable` (`echo_chamber_service.py`).

## Step 7 — Publish

```
GET  /api/v1/social-science/network/export?format=graphml
GET  /api/v1/social-science/export               # CSV / JSON / XLSX
POST /api/v1/social-science/datasets
GET  /api/v1/social-science/datasets/{id}/export
```

Exports are portable, lineage-tracked artifacts — the basis of a reproducible figure or published dataset.

---

## What this proves

1. **It's real.** Every step is a live endpoint in the guarded `openapi.json`.
2. **It's rigorous.** Observed-only data, explicit availability, deterministic seeds.
3. **It's reproducible.** Same seed → same sample → same community partition → same p-value.

[Back to overview](index.md) · [Run it yourself](../for-developers/quickstart.md)
