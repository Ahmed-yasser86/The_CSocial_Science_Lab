# Docs Router — Find Anything in 30 Seconds

> This page is a router, not a summary. Pick a row and go — every page states its question and where to go next. For the complete per-page map, see [Documentation Index](pipelines/documentation-index.md).

---

## Tracks (start here)

| Track | Time | Start | You get |
|---|---|---|---|
| **Evaluators** (hiring, review) | 2 min | [For Recruiters](for-recruiters/index.md) | What was built, technical complexity, achievements |
| **Researchers** (method, validity) | 15 min | [For Researchers](for-researchers/index.md) | Methodology, reproducibility, network science, echo chambers |
| **Developers** (run, build, extend) | 5 min | [Quickstart](for-developers/quickstart.md) | Setup, architecture, API reference |
| **Achievements** (what's proven) | 3 min | [Achievements](achievements.md) | Numbers, wins, integrations — each linked to evidence |

---

## Researchers

| Page | Question |
|---|---|
| [Research Features](for-researchers/research-features.md) | What is genuinely novel here? (11 code-grounded capabilities) |
| [Methodology](for-researchers/methodology.md) | How is each concept operationalized? (canonical per-method detail) |
| [Network Science](for-researchers/network.md) | Graph families, weight grammar, centrality, Louvain, merge/matrices, export |
| [Echo Chamber](for-researchers/echo-chamber.md) | S1–S5 exact formulas, composite scoring, verdict bands |
| [Sampling](for-researchers/sampling.md) | Which subset, chosen how, reproducibly? (17 strategies, seed=42) |
| [Limitations](for-researchers/limitations.md) | What can go wrong / what cannot be claimed? |
| [Reproducibility](for-researchers/reproducibility.md) | Seeds, provenance, weight specs, figure contract, checklist |
| [Data Model](for-researchers/data-model.md) | Entities vs observations, availability, identity, persistence |
| [Ethics](for-researchers/ethics.md) | Collection scope, ceilings, minimization, retention |
| [Citation](for-researchers/citation.md) | How to cite software + datasets? |

## Concepts & pipelines

| Page | Question |
|---|---|
| [Structure vs Meaning](concepts/structure-vs-meaning.md) | Why measure structure and content independently? (the core idea) |
| [Pipelines](pipelines/index.md) | Which pipelines exist, how representations flow, AI vs deterministic rule? |
| [Content Homophily](pipelines/content-homophily.md) | **Flagship.** Is content inside structural communities semantically similar? |
| [Recommendation Crawling](pipelines/recommendation-crawling.md) | What does the platform connect, layer by layer? |
| [Context-Aware Acquisition](pipelines/context-aware-acquisition.md) | How is collection context a controlled experimental variable? |
| [Documentation Index](pipelines/documentation-index.md) | Every page on the site — question, audience, next step |

## Developers

| Page | Question |
|---|---|
| [Quickstart](for-developers/quickstart.md) | Postgres → backend → frontend → first query |
| [Architecture](for-developers/architecture.md) | Three systems, service container, data flows (canonical software structure) |
| [API Reference](for-developers/api-reference.md) | All 160 paths (generated, guarded OpenAPI contract) |
| [Ingestion & Agent](for-developers/ingestion-and-agent.md) | Tavily→Qdrant ingestion + 5-node LangGraph agent + HTTP/MCP |
| [GPT-Researcher Customization](for-developers/gpt-researcher-customization.md) | Fork diff: prompts, rate limiting, compression, MCP normalization |
| [Workspaces & Jobs](for-developers/workspaces-and-jobs.md) | Multi-tenant isolation + long-running work lifecycle |
| [Configuration](for-developers/configuration.md) | Every env var, defaults, providers |
| [Performance Optimizations](for-developers/performance-optimizations.md) | Wins, throttling, pause/resume (canonical numbers behind [Achievements](achievements.md)) |
| [Troubleshooting](for-developers/troubleshooting.md) | 10 real fixes with code pointers |

## Evaluators

| Page | Question |
|---|---|
| [For Recruiters](for-recruiters/index.md) | 2-minute overview — what, why, scale, rigor |
| [Case Study](for-recruiters/case-study.md) | Channel → collection → sample → network → hypothesis → echo report → publish |
| [Architecture (recruiters)](for-recruiters/architecture.md) | Framework + system + resilience, evaluator-framed |
| [Achievements](achievements.md) | Numbers and integrations with evidence links |

## Technical reference & research lookup

| Page | Question |
|---|---|
| [Invariants](technical/invariants.md) | 9 cross-cutting consistency rules |
| [Scraper Architecture](technical/scraper-architecture.md) | Rate limiting, sessions, five phases (implementation deep-dive) |
| [Data Model (technical)](technical/data-model.md) | Storage internals |
| [Configuration (technical)](technical/configuration.md) | Env-level detail |
| [Migration Notes](technical/migration-notes.md) / [Excel → Postgres](excel_to_postgres_migration.md) | Upgrades, persistence move |
| [Samples Guide](samples-user-guide.md) | Sampling Workbench + Sample Library UI |
| [Variable Catalogue](research/variable-catalogue.md) | Every variable: type, source, limits |
| [Legacy notes](pipelines/documentation-index.md) | `research/` + `technical/api-reference.md` older parallels — which page to prefer |

---

## Honesty principles (apply everywhere)

- **Observed, never estimated** — `available | missing | unsupported`, never zeroed.
- **Deterministic** — `seed=42`; seeded, reproducible permutation tests.
- **Validated** — centrality battery matches NetworkX (Karate Club) to 1e-6.
- **Contract is law** — OpenAPI generated + CI-guarded; docs never invent a path.

---

## About this project (one paragraph)

A research-engineering artifact for investigating platform-mediated information environments through joint analysis of social interaction, content semantics, recommendation structures, and community dynamics on YouTube. Three systems (CSS workbench, Graph-RAG agent, ingestion pipeline), one repository — full identity lives in the [README](https://github.com/Ahmed-yasser86/The_CSocial_Science_Lab#readme). Citation: [Researchers → Citation](for-researchers/citation.md) (`CITATION.cff` at repo root). License: MIT.

---

## Project overview (where the archived content lives)

The long-form overview that used to sit here — problem statement, research challenge, conceptual framework, three-systems diagram, end-to-end pipeline, quick start — now lives where it belongs:

| Content | Canonical location |
|---|---|
| Project identity, goal, problem, achievements | [README](https://github.com/Ahmed-yasser86/The_CSocial_Science_Lab#readme) (repo root) |
| Achievements with evidence links | [Achievements](achievements.md) |
| Conceptual framework + methodology | [Methodology](for-researchers/methodology.md), [Research Features](for-researchers/research-features.md) |
| Quick start / runbook | [Quickstart](for-developers/quickstart.md) |
| Tracks (recruiter / researcher / developer) | Tables at the top of this page |
