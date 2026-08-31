# Reproducibility

> A figure is reproducible when the exact recipe — algorithm, seed, data, and parameters — is recorded and re-runnable. This platform records all four.

## 1. Deterministic seeds

| Concern | Seed / default | Env var | Source |
|---|---|---|---|
| Sampling | `42` | `SOCIAL_SAMPLING_SEED` | `config/settings.py:129,399` |
| Community detection (Louvain) | `42` | — | `services/network_analytics_service.py` |
| Permutation / bootstrap tests | `42` (default) | — | `services/network_analytics_service.py` `run_resampling_test` |

The same inputs + the same seed produce the same sample, the same community partition, and the same test statistic and `p_value`.

## 2. Provenance per run

Every collection is a **run** with a UUID `collection_run_id` (`SocialScienceResearch/domain/models.py`). Observations reference their run; runs reference their config. The API exposes:

```
GET  /api/v1/social-science/runs                 # list runs
GET  /api/v1/social-science/runs/{run_id}        # run + config snapshot
GET  /api/v1/social-science/runs/{run_id}/errors # what failed & why
GET  /api/v1/social-science/runs/{run_id}/sub-runs
```

This lets a reviewer trace any measurement back to the exact collection that produced it.

## 3. Weight specifications are encoded, not implicit

Network weights are selected with an explicit **weight-spec** token rather than hidden defaults (`SocialScienceResearch/services/weight_spec.py`):

```
edge_type:weight_mode[:param=value,...][:norm=<none|min_max|log1p>]
```

Example: `recommendation:observation_count:norm=min_max`.

Two families + modes:

| Family | Weight modes |
|---|---|
| `recommendation` | `observation_count`, `reciprocal_position` |
| `co_comment` | `jaccard`, `overlap_coefficient`, `intersection`, counts |

Parameters: `min_shared`, `top_n`, `position_decay`. Full grammar + parser in `SocialScienceResearch/services/weight_spec.py`.

## 4. Deterministic statistical testing

`run_resampling_test()` performs a **seeded permutation/bootstrap** with a `+1` correction, `n_iter` capped at 1000, and default `seed=42`. Node-decomposable metrics return a `p_value`; global-only metrics (e.g. modularity) return the observed delta with `p_value=None` and an explanatory note — **no fabricated p-value** (see `tests/test_centrality_benchmark.py:270`).

```
POST /api/v1/social-science/network/test-difference
# body: metric, method (permutation|bootstrap), n_iter, seed
# returns: observed_delta, p_value, ci95
```

## 5. Sample identity

Samples are persisted immutably and carry their recipe: `strategy`, `seed`, `population_size`, `criteria_json`, plus a hash (`services/sample_service.py:47`). `compare_samples()` diffs two samples' criteria (`:86`).

```
GET  /api/v1/social-science/samples
POST /api/v1/social-science/sampling/advanced
POST /api/v1/social-science/samples/compare
```

## 6. The figure-reproducibility contract

To reproduce any network figure:

1. Note the `collection_run_id`s (provenance).
2. Note the weight-spec token (encoding).
3. Note the seed (`42` by default).
4. Re-run with the same three inputs — the `networkx`-level results are deterministic.

See the network measures validated against Zachary's Karate Club in [Network Science](network.md#validation) and `tests/test_centrality_benchmark.py`.

---

Previous: [Methodology](methodology.md) · Next: [Network Science](network.md)
