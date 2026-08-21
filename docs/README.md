# SocialScienceResearch — Documentation

Operational and methodological documentation for the research platform
(`SocialScienceResearch/`). Generated from the implementation state after
Phase E of the upgrade plan.

## Technical

| Document | Covers |
|---|---|
| [API reference](technical/api-reference.md) | Endpoint catalogue, pagination contract, error envelope, OpenAPI snapshot |
| [Data model](technical/data-model.md) | Entities, observations, repositories, overflow sidecars |
| [Configuration](technical/configuration.md) | Environment variables and settings reference |
| [Migration notes](technical/migration-notes.md) | Schema/behaviour changes introduced across phases |

## Research

| Document | Covers |
|---|---|
| [Variable catalogue](research/variable-catalogue.md) | Entity × variable inventory, data types, sources |
| [Sampling methods](research/sampling-methods.md) | Strategies, seeds, percentile/quantile semantics, reproducibility |
| [Network metrics](research/network-metrics.md) | Directed-graph semantics, communities, HITS, exports |
| [Ethics & data minimization](research/ethics.md) | Privacy surface, comment ceilings, author profiles |

## Also see

- `CodingPlans/phase2_research_platform_upgrade_plan.md` — the approved plan
- `CodingPlans/adr/0001_phase2_adr.md` — decision records (ADR-0001…0025)
- `CONTRACT.md` — the API contract summary
