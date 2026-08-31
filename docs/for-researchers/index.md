# For Researchers

> **15 minutes.** This is the track for a reviewer deciding whether a paper backed by this platform is **rigorous and reproducible**. Every claim is grounded in committed code and cited with an exact `file:line` — none of which are git-ignored planning docs.

## The five things a reviewer checks

| # | Check | Where it's true (committed code) |
|---|---|---|
| 1 | **Observed, never estimated** — missing data is flagged, not zeroed | `domain/enums.py:137` (`available | missing | unsupported`); observations keep `raw_json` (`domain/models.py`) |
| 2 | **Reproducible** — deterministic seeds and provenance per run | `config/settings.py` (`SOCIAL_SAMPLING_SEED=42`), `network_analytics_service.py` (Louvain `seed=42`) |
| 3 | **Correct network measures** — validated against a reference | `tests/test_centrality_benchmark.py` (Zachary's Karate Club, matches `networkx` to `1e-6`) |
| 4 | **Honest echo-chamber / signal definitions** — S1–S5 over observed edges | `services/echo_chamber_service.py` |
| 5 | **Ethical data minimization** — ceilings, opt-in transcripts, identity handling | `config/settings.py` + `services/commenter_overlap_service.py` |

## Follow the journey

1. [Methodology](methodology.md) — how data is collected & represented
2. [Reproducibility](reproducibility.md) — seeds, provenance, figures
3. [Network Science](network.md) — weight grammar, centrality battery, communities, roles
4. [Echo Chamber](echo-chamber.md) — the S1–S5 detection signals
5. [Sampling](sampling.md) — strategies, seeding, feasibility
6. [Ethics & Data Minimization](ethics.md) — what is/isn't collected
7. [Data Model](data-model.md) — entities, observations, availability
8. [Citation](citation.md) — how to cite the software and datasets

## A benchmark we satisfy (from the code)

`tests/test_centrality_benchmark.py` seeds **Zachary's Karate Club** (34 nodes, 78 edges) as a directed recommendation network and asserts:

- degree / closeness / eigenvector / betweenness match `networkx` reference values (`rel=1e-6` / `1e-9`) — `test_centrality_benchmark.py:73`,
- the two faction leaders (nodes 0 and 33) land in **different communities**, and the instructor is the highest-betweenness actor — `:96`,
- community count `>= 3` and modularity `> 0.3` — `:114`,
- the `/network/centralities`, `/network/roles`, `/network/communities`, `/network/community-insights`, and `/network/test-difference` endpoints all agree with the service layer — `:166`–`:298`.

Run it yourself:

```bash
python -m pytest SocialScienceResearch/tests/test_centrality_benchmark.py -q
# 11 passed
```

## The API is the source of truth

`SocialScienceResearch/api/openapi.json` defines **160 paths**. It is generated from the live app by `scripts/dump_openapi.py` and guarded by `tests/test_openapi_snapshot.py`, which fails CI on any drift (`SocialScienceResearch/CONTRACT.md`). When you see an endpoint below, it exists in that snapshot — verified, not aspirational.

---

Start with [Methodology](methodology.md).
