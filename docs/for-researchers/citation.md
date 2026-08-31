# Citation Guide

> How to cite the software and the datasets it produces. The software citation lives in `CITATION.cff` at the repository root (GitHub renders it automatically).

## Citing the software

`CITATION.cff`:

```text
title: Graph RAG Agent — Computational Social Science Research Workbench
type: software
version: 0.1.0
license: MIT
repository-code: https://github.com/anomalyco/graph-rag-agent
```

Suggested BibTeX:

```bibtex
@software{graphragagent2026,
  author  = {{Graph RAG Agent Contributors}},
  title   = {Graph RAG Agent --- Computational Social Science Research Workbench},
  year    = {2026},
  version = {0.1.0},
  url     = {https://github.com/anomalyco/graph-rag-agent},
  note    = {YouTube recommendation \& audience network analysis with full provenance},
  license = {MIT}
}
```

## Citing a dataset

Research datasets are first-class, lineage-tracked artifacts:

```
POST /api/v1/social-science/datasets
GET  /api/v1/social-science/datasets/{id}          # metadata + provenance
GET  /api/v1/social-science/datasets/{id}/export   # portable artifact
GET  /api/v1/social-science/datasets/{id}/members
GET  /api/v1/social-science/datasets/{id}/quality
```

When publishing a dataset, record in the methods section:

- the `collection_run_id`s (provenance),
- the weight-spec token(s) used for any network,
- the seeds (sampling `SOCIAL_SAMPLING_SEED=42`, Louvain/permutation `seed=42`),
- the availability flags for each variable (`available | missing | unsupported`).

This is the minimum needed to make any figure reproducible — see [Reproducibility](reproducibility.md).

## Recommended methods-section snippet

> Video and comment data were collected from YouTube via the platform's public recommendation interface and stored with full provenance (per-run observations preserving the raw provider payload; missing or unsupported values flagged explicitly rather than estimated). Communities were detected with Louvain using seed 42; sampling used seed 42. Differences were tested with a seeded permutation test reporting p-values and 95% confidence intervals. Echo-chamber signals (frontier collapse, seed-community concentration, top-channel share, cross-layer repetition, commenter overlap) were computed only from observed edges, with unavailable signals reported as such.

This snippet corresponds exactly to the committed behavior in `domain/enums.py`, `services/network_analytics_service.py`, `services/echo_chamber_service.py`, and `services/sampling_service.py`.

---

Previous: [Data Model](data-model.md) · [Back to researchers overview](index.md)
