# Reproducibility Protocol

> Deterministic seeds, provenance tracking, weight specifications, and the figure-reproducibility contract.

---

## Deterministic Seeds

All stochastic operations in the system use fixed seeds to ensure reproducibility:

| Operation | Seed | Configuration |
|---|---|---|
| Sampling | `seed=42` | `SOCIAL_SAMPLING_SEED` environment variable |
| Louvain community detection | `seed=42` | Hardcoded in `network_analytics_service.py` |
| Permutation null tests | `seed=42` | Seeded RNG in `content_homophily_service.py` |
| Structural metrics null model | `COMMUNITY_SEED = 42` | `DEFAULT_N_RANDOMIZATIONS = 10` |
| Pair sampling | `seed=42` | Inherited from sampling service |

**To reproduce any analysis:** same seed + same parameters + same data = same results.

---

## Provenance

Every observation carries its collection context:

- **`collection_run_id`** — links every video, comment, recommendation, and transcript to the run that collected it
- **Layer index** — recommendation edges record which crawl layer they were observed in
- **Extraction provider** — recommendation edges record which extraction method captured them (yt-dlp, yt-search-python, page-dump)
- **Timestamp** — collection timestamp for temporal reasoning

This provenance chain ensures that every data point can be traced back to its collection event.

---

## Weight Specifications

Edge weights are encoded using a formal grammar:

```
edge_type:weight_mode[:param=value,...][:norm=...]
```

This makes weight computation explicit and reproducible. Two researchers using the same weight specification on the same data will produce identical results.

Examples:

- `recommendation:rank` — weight based on recommendation rank position
- `commenter:jaccard` — weight based on Jaccard similarity
- `commenter:overlap_coefficient` — Szymkiewicz-Simpson coefficient

---

## Data Availability

Every observation carries an explicit data-availability status:

| Status | Meaning |
|---|---|
| `available` | Data was successfully collected |
| `missing` | Data was requested but not available from the source |
| `unsupported` | Data type is not supported by the current collection method |

This prevents conflating unavailable observations with zero values — a critical methodological safeguard.

---

## Figure-Reproducibility Contract

Any network figure can be reproduced from 4 inputs:

1. **Scope** — which videos/channels/comments are included
2. **Weight specification** — how edge weights are computed
3. **Community detection parameters** — algorithm and seed
4. **Layout parameters** — if applicable

Given these 4 inputs, the same network visualization will be produced.

---

## Reproducibility Checklist

To reproduce an analysis:

1. ✅ **Clone the repository** at the same commit
2. ✅ **Install dependencies** via `pyproject.toml`
3. ✅ **Configure environment** — same `.env` settings (especially `SOCIAL_SAMPLING_SEED`)
4. ✅ **Start PostgreSQL** — `docker compose up -d`
5. ✅ **Collect data** — use the same collection endpoints with the same parameters
6. ✅ **Build networks** — use the same network construction endpoints
7. ✅ **Run analysis** — use the same analytics endpoints with the same parameters
8. ✅ **Compare results** — all metrics should match to floating-point precision

---

## Model and Version Tracking

| Component | Tracking |
|---|---|
| Embedding model | Recorded per content homophily analysis |
| LLM providers | Configured via environment, persisted per run |
| Python version | 3.11 (specified in `pyproject.toml`) |
| Key dependencies | Locked in `uv.lock` |

---

## Configuration Persistence

All analytical parameters are configurable via environment variables and persisted with each run:

| Parameter | Default | Purpose |
|---|---|---|
| `SOCIAL_SAMPLING_SEED` | `42` | Deterministic sampling |
| `SOCIAL_COLLECT_COMMENTS` | `True` | Comment collection toggle |
| `SOCIAL_COLLECT_TRANSCRIPTS` | `False` | Transcript collection toggle |
| `SOCIAL_MAX_COMMENTS_PER_VIDEO` | `500` | Comment ceiling |
| `SOCIAL_SCRAPER_RETRIES` | `3` | Acquisition retry count |
| `SOCIAL_SCRAPER_REQUEST_DELAY` | `1.0` | Seconds between requests |
| `SOCIAL_NETWORK_EXPORT_FORMATS` | graphml,edgelist,gexf,csv,json,xlsx | Export formats |

---

## API Contract

The OpenAPI specification is:

1. **Generated** from code via `scripts/dump_openapi.py`
2. **CI-guarded** via `tests/test_openapi_snapshot.py`
3. **Never invented** — documented endpoints match implemented functionality

This ensures that the API surface is reproducible and that documentation never diverges from implementation.
