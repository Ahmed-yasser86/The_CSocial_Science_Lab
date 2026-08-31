# Network Science

> Two network families, one explicit weight grammar, a validated measure battery, deterministic communities, and structural roles — all implemented in `SocialScienceResearch/services/network_analytics_service.py` and `commenter_network_service.py`.

## The two families

| Family | What nodes are | What edges mean | Service |
|---|---|---|---|
| **Recommendation** | videos (or channels via `projection=channel`) | video A recommends B | `network_analytics_service.py` |
| **Audience / commenter** | commenters | two commenters co-comment on the same video | `commenter_network_service.py` |

Change the lens with the `family` parameter on `/network/*` and `/network/test-difference`.

## Weight grammar

`SocialScienceResearch/services/weight_spec.py` defines the canonical form:

```
edge_type:weight_mode[:param=value,...][:norm=<none|min_max|log1p>]
```

| Family | `edge_type` | `weight_mode` |
|---|---|---|
| Recommendation | `recommendation` | `observation_count`, `reciprocal_position` |
| Audience | `co_comment` | `jaccard`, `overlap_coefficient`, `intersection`, counts |

- Normalizations: `none`, `min_max`, `log1p`.
- Parameters: `min_shared` (int), `top_n` (int), `position_decay` (float).
- Parser `parse_weight_spec()` accepts strings, dicts, or `WeightSpec` objects.

Example: `GET /network/graph?weight=recommendation:observation_count:norm=min_max`.

Network weights are also expressed as: `co_comment:jaccard:min_shared=2:norm=min_max`.

## Centrality battery — 10 measures

`network_analytics_service.py` `centrality_battery` computes (per node):

`degree`, `closeness`, `eigenvector`, `betweenness`, `pagerank`, `harmonic`, `constraint` (Burt), `effective_size` (Burt), `bridging` (normalized betweenness), `clustering`.

Exposed at:

```
GET /api/v1/social-science/network/centralities
```

## Community detection — deterministic

Louvain with a fixed `seed=42` produces a reproducible partition. The `/network/communities` endpoint returns communities with their member `node_ids`, `size`, and `label`, and the partition is exhaustive (every node in exactly one community — verified in `tests/test_centrality_benchmark.py:217`).

```
GET /api/v1/social-science/network/communities
GET /api/v1/social-science/network/community-insights   # composition per community
GET /api/v1/social-science/network/commenters/communities
```

## Structural roles

`network_analytics_service.py` `roles()` assigns each node one of four structural roles by percentile thresholds (`role_model="core_broker_periphery_bridge"`):

| Role | Rule |
|---|---|
| `core` | eigenvector ≥ 75th percentile |
| `broker` | betweenness ≥ 90th percentile |
| `periphery` | degree ≤ 25th percentile |
| `bridge` | otherwise |

```
GET /api/v1/social-science/network/roles
GET /api/v1/social-science/network/commenters/roles
```

## Overlap & audience metrics (Jaccard & friends)

`commenter_overlap_service.py`:

- **Jaccard** = |A ∩ B| / |A ∪ B|
- **Overlap coefficient** = |A ∩ B| / min(|A|, |B|)
- **Reach overlap** = |A ∩ B| / max(|A|, |B|)
- Empty-set pairs → `None` (**never `0`** — no fabricated overlap).

```
GET /api/v1/social-science/network/commenters/overlap?metric=jaccard
GET /api/v1/social-science/network/commenters/graph
```

## Temporal & matrices

```
GET /api/v1/social-science/network/temporal?runs=a,b   # per-run snapshots + Δ growth
GET /api/v1/social-science/network/matrices            # community & layer matrices
```

## Statistical comparison

```
POST /api/v1/social-science/network/test-difference
```

Seeded permutation / bootstrap (see [Reproducibility](reproducibility.md#4-deterministic-statistical-testing)) returning `observed_delta`, `p_value`, `ci95` — or an explicit `p_value=None` for global-only metrics.

## Validation

`tests/test_centrality_benchmark.py` validates the whole battery + endpoints on **Zachary's Karate Club** against `networkx` reference values. See the [researchers overview](index.md#a-benchmark-we-satisfy-from-the-code).

---

Previous: [Reproducibility](reproducibility.md) · Next: [Echo Chamber](echo-chamber.md)
