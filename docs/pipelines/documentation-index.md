# Documentation Index

> Every document in this site on one page: what it answers, who it is for, and where to go next. Start here if you are lost.

**Reading paths:** Researcher path: [README](../../README.md) → [Research Features](../for-researchers/research-features.md) → [Structure × Meaning](../concepts/structure-vs-meaning.md) → [Pipelines](index.md) → [Methodology](../for-researchers/methodology.md) → [Limitations](../for-researchers/limitations.md).
Developer path: [Quickstart](../for-developers/quickstart.md) → [Architecture](../for-developers/architecture.md) → [API Reference](../for-developers/api-reference.md) → pipeline doc for your task → code paths listed there.
Evaluator path (2 min): [For Recruiters](../for-recruiters/index.md) → [Case Study](../for-recruiters/case-study.md).

---

## Start here

| Document | Answers | For |
|---|---|---|
| [Home](../index.md) | What is this project, in one page (framework, three systems, honesty principles)? | Everyone |
| [README](../../README.md) | What is it / why exists / what achieved / where are details? (entry point, links out) | Everyone |
| **This index** (`pipelines/documentation-index.md`) | Where is everything? | Everyone lost |

## Concepts — the ideas everything else rests on

| Document | Answers | Go next |
|---|---|---|
| [Structure vs Meaning](../concepts/structure-vs-meaning.md) | Why measure network structure and semantic content independently instead of asking an LLM to classify? | [Content Homophily](content-homophily.md) |

## Pipelines — end-to-end analytical workflows

| Document | Answers | Go next |
|---|---|---|
| [Pipelines overview](index.md) | Which pipelines exist, how representations flow, AI vs deterministic rule? | Any pipeline below |
| [Content Homophily](content-homophily.md) | **Flagship.** Is content inside structural communities semantically similar? (chunk → embed → mean-pool → cosine → permutation null) | [Structure vs Meaning](../concepts/structure-vs-meaning.md), [Echo Chamber](../for-researchers/echo-chamber.md) |
| [Recommendation Crawling](recommendation-crawling.md) | What does the platform connect, layer by layer? (3-layer fallback, BFS, frontier reports) | [Context-Aware Acquisition](context-aware-acquisition.md) |
| [Context-Aware Acquisition](context-aware-acquisition.md) | How is collection context (cookies/proxy/impersonation) a controlled experimental variable? | [Recommendation Crawling](recommendation-crawling.md), [Reproducibility](../for-researchers/reproducibility.md) |
| [Ingestion & Agent](../for-developers/ingestion-and-agent.md) | **Generative track.** How does Tavily→Qdrant ingestion work, and how does the 5-node LangGraph agent (identity → profile → subject/audience/ecosystem) run? | [GPT-Researcher Customization](../for-developers/gpt-researcher-customization.md), [Architecture](../for-developers/architecture.md) |
| [Echo-Chamber Detection](../for-researchers/echo-chamber.md) | Do observed structures look like echo-chamber dynamics? (S1–S5 formulas, composite, verdict bands) | [Limitations](../for-researchers/limitations.md) |
| [Methodology](../for-researchers/methodology.md) (Social Network + Commenter Overlap sections) | Who interacts with whom? Do audiences span communities? | [Network Science](../for-researchers/network.md) |
| [Sampling](../for-researchers/sampling.md) | Which subset, chosen how, reproducibly? (17 strategies, seed=42, immutable samples) | [Reproducibility](../for-researchers/reproducibility.md) |

## Researchers — methodology, validity, ethics

| Document | Answers | Go next |
|---|---|---|
| [For Researchers](../for-researchers/index.md) | 15-minute overview: the five things a reviewer checks | [Research Features](../for-researchers/research-features.md) |
| [Research Features](../for-researchers/research-features.md) | What is genuinely novel here (11 code-grounded capabilities)? | [Structure vs Meaning](../concepts/structure-vs-meaning.md), [Pipelines](index.md) |
| [Methodology](../for-researchers/methodology.md) | How is each concept operationalized (inputs → computation → outputs → limits)? **Canonical per-method detail; pipelines docs point here and back.** | Method-specific pipeline doc |
| [Network Science](../for-researchers/network.md) | Two graph families, weight grammar, centrality battery, Louvain, merge/matrices, export | [Methodology](../for-researchers/methodology.md) |
| [Echo Chamber](../for-researchers/echo-chamber.md) | S1–S5 exact formulas, composite scoring, honest reporting | [Limitations](../for-researchers/limitations.md) |
| [Sampling](../for-researchers/sampling.md) | 17 strategies, determinism, feasibility, sample comparison | [Sampling Methods](../research/sampling-methods.md) (older parallel note) |
| [Limitations](../for-researchers/limitations.md) | What can go wrong / what cannot be claimed (consolidated threats to validity)? | Per-method canonical page |
| [Reproducibility](../for-researchers/reproducibility.md) | Seeds, provenance, weight specs, figure contract, checklist | [Configuration](../for-developers/configuration.md) |
| [Data Model](../for-researchers/data-model.md) | Entities vs observations, availability, identity, persistence | [Data Model (technical)](../technical/data-model.md) |
| [Ethics](../for-researchers/ethics.md) | Collection scope, ceilings, minimization, retention | [Ethics (research)](../research/ethics.md) (older parallel note) |
| [Citation](../for-researchers/citation.md) | How to cite software + datasets (methods-section snippet)? | `CITATION.cff` at repo root |

## Developers — run, build, extend

| Document | Answers | Go next |
|---|---|---|
| [For Developers](../for-developers/index.md) | 5-minute track map | [Quickstart](../for-developers/quickstart.md) |
| [Quickstart](../for-developers/quickstart.md) | Postgres → backend → frontend → first query | [Architecture](../for-developers/architecture.md) |
| [Architecture](../for-developers/architecture.md) | Three systems, service container, data flows (canonical software structure) | [API Reference](../for-developers/api-reference.md) |
| [API Reference](../for-developers/api-reference.md) | All 160 paths, generated from guarded OpenAPI contract | [Troubleshooting](../for-developers/troubleshooting.md) |
| [Ingestion & Agent](../for-developers/ingestion-and-agent.md) | Tavily→Qdrant ingestion + LangGraph agent + HTTP server + MCP wiring | [GPT-Researcher Customization](../for-developers/gpt-researcher-customization.md) |
| [GPT-Researcher Customization](../for-developers/gpt-researcher-customization.md) | Fork diff (15 files): rewritten prompts, rate-limited embedder, compression filters, env bootstrap, MCP normalization | `gpt-researcher/` vs `GPT-Researcher-Original/` |
| [Workspaces & Jobs](../for-developers/workspaces-and-jobs.md) | Multi-tenant isolation + long-running work lifecycle | [API Reference](../for-developers/api-reference.md) |
| [Configuration](../for-developers/configuration.md) | Every env var, defaults, providers | [Configuration (technical)](../technical/configuration.md) |
| [Performance Optimizations](../for-developers/performance-optimizations.md) | 12x enrichment win, AIMD/circuit-breaker/queue, test counts, pause/resume | [Scraper Architecture](../technical/scraper-architecture.md) |
| [Troubleshooting](../for-developers/troubleshooting.md) | 10 real fixes with code pointers | Relevant pipeline/method doc |

## Recruiters / evaluators — what was built

| Document | Answers | Go next |
|---|---|---|
| [For Recruiters](../for-recruiters/index.md) | 2-minute overview: what, why, scale, rigor | [Case Study](../for-recruiters/case-study.md) |
| [Case Study](../for-recruiters/case-study.md) | End-to-end journey: channel → collection → sample → network → hypothesis → echo report → publish (every step maps to a real endpoint) | [Architecture (recruiters)](../for-recruiters/architecture.md) |
| [Architecture (recruiters)](../for-recruiters/architecture.md) | Conceptual framework + system + resilience, evaluator-framed | [Architecture (developers)](../for-developers/architecture.md) |

## Technical reference — invariants and deep dives

| Document | Answers | Canonical for |
|---|---|---|
| [Invariants](../technical/invariants.md) | 9 cross-cutting rules (contract, single engine, provenance, determinism…) | Consistency checks |
| [Scraper Architecture](../technical/scraper-architecture.md) | Rate limiting, sessions, the five phases — implementation deep-dive | Tuning/collection internals |
| [Data Model (technical)](../technical/data-model.md) | Entities/observations, relations, repository layer | Storage internals |
| [Configuration (technical)](../technical/configuration.md) | Persistence/acquisition/collection/sampling settings | Env-level detail |
| [API Reference (legacy)](../technical/api-reference.md) | Older endpoint catalogue | Historical reference — prefer [API Reference](../for-developers/api-reference.md) |
| [Migration Notes](../technical/migration-notes.md) | Upgrading workbooks/codebase across phases | Operators |
| [Excel → Postgres](../excel_to_postgres_migration.md) | Why/how persistence moved (internal plan) | Operators |
| [Samples Guide](../samples-user-guide.md) | Sampling Workbench + Sample Library UI walkthrough | UI users |

## Research reference — lookup tables

| Document | Answers | Canonical for |
|---|---|---|
| [Variable Catalogue](../research/variable-catalogue.md) | Every variable: type, source (observed/derived/raw), limits (`services/variable_registry.py`) | Query builder / explorer |
| [Network Metrics](../research/network-metrics.md) | Directed vs undirected conventions, centrality, projection, exports (older note) | Metric conventions — prefer [Network Science](../for-researchers/network.md) |
| [Sampling Methods](../research/sampling-methods.md) | Strategy table, ADR-0007/0011 semantics (older note) | Sampling detail — prefer [Sampling](../for-researchers/sampling.md) |
| [Ethics (research)](../research/ethics.md) | Observed-never-estimated, ceilings, raw profiles (older note) | Ethics detail — prefer [Ethics](../for-researchers/ethics.md) |

---

## Notes on duplication

Two pairs of older parallel notes exist and are kept for history: `research/ethics.md` vs `for-researchers/ethics.md`, `research/sampling-methods.md` vs `for-researchers/sampling.md`, plus `research/network-metrics.md` vs `for-researchers/network.md` and `technical/api-reference.md` vs `for-developers/api-reference.md`. In each case the table above marks which to **prefer**; the other is not canonical. Do not add a third copy — extend the canonical page.
