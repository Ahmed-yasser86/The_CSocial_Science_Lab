# For Recruiters — 2-Minute Overview

> What was built, why it matters, and what it demonstrates.

---

## What I Built

A **computational social-science research platform** that jointly analyzes three network representations of YouTube data to investigate platform-mediated information environments.

This is not a simple scraping tool. It is a research-engineering artifact that operationalizes concepts from computational social science into reproducible computational procedures.

---

## The Problem

Contemporary platforms simultaneously function as social environments, content-distribution systems, recommendation engines, and information landscapes. Studying how these mechanisms interact requires infrastructure that can represent and compare multiple analytical perspectives on the same data. No single network representation captures the full picture.

---

## What the System Does

| Capability | What It Means |
|---|---|
| **Social network analysis** | Who interacts with whom (co-comment patterns, Jaccard similarity, bridge detection) |
| **Semantic content analysis** | What content is related (transcript embeddings, within/between community similarity) |
| **Recommendation network analysis** | What YouTube connects (directed edges, layered crawling, PageRank) |
| **Context-aware collection** | Same content observed under different user/geo contexts (cookies, proxy, impersonation) |
| **Echo-chamber detection** | Five observable signals with composite scoring |
| **Cross-network comparison** | How social, semantic, and recommendation structures correspond |
| **Reproducible sampling** | 17 deterministic strategies with seed=42 |

---

## Key Achievements

1. **Built a layered recommendation-network crawler** that expands seed networks across successive recommendation layers with frontier management, snapshot classification, and full provenance.

2. **Implemented five observable echo-chamber signals** (S1-S5) computed exclusively from observed edges, each with data-availability status and weighted composite scoring.

3. **Developed semantic content analysis** with transcript collection, embedding generation, within/between-community pair sampling, and permutation null testing.

4. **Integrated social, semantic, and recommendation network perspectives** within a single computational environment for cross-network comparison.

5. **Engineered multi-source data acquisition** with three-layer fallback extraction, AIMD rate control, circuit breakers, and priority scheduling.

6. **Built context-aware data acquisition** with runtime-configurable cookies, proxy positioning with sticky sessions, and browser impersonation—enabling comparative analysis of recommendation environments across different user and geographic contexts.

6. **Constructed a full SNA battery** with 10 centrality measures, Louvain community detection (seed=42), structural role classification, and 6 export formats.

---

## Technical Complexity

| Area | Implementation |
|---|---|
| **Data Engineering** | Multi-provider acquisition with fallback, AIMD rate control, circuit breakers, priority queues |
| **Graph/Network Analysis** | Full NetworkX SNA, community detection, directed graphs, ego-networks, network merge |
| **AI/ML** | LangGraph state machine, embedding-based semantic similarity, structured intelligence compression |
| **Backend** | FastAPI with 160+ endpoints, workspace isolation, dual persistence (PostgreSQL + Excel) |
| **Frontend** | Next.js 16 with network visualization, agent console, AI configuration |
| **Resilience** | Circuit breakers, retry with backoff, rate limiting, bounded enrichment |

---

## Tech Stack

Python 3.11, FastAPI, NetworkX, LangGraph, PostgreSQL, Qdrant, Next.js, yt-dlp, Pydantic, NumPy, SciPy.

---

## Scale

- **160+ API endpoints** across 18 routers
- **36 analytical services**
- **18 database tables**
- **17 sampling strategies**
- **5 echo-chamber signals**
- **10 centrality measures**
- **6 graph export formats**
- **75+ test modules**

---

## Rigor

- Deterministic seeds (`seed=42`) across sampling, community detection, and permutation testing
- Validated against Zachary's Karate Club (centrality matches NetworkX to 1e-6)
- API contract enforcement via CI-guarded OpenAPI specification
- Explicit data-availability status (`available | missing | unsupported`) — missing data is never zeroed
- Provenance tracking on every observation

---

## Documentation

- [Architecture](architecture.md) — system design and conceptual framework
- [Case Study](case-study.md) — end-to-end research workflow
- [For Researchers](../for-researchers/index.md) — methodology, reproducibility, network science
- [For Developers](../for-developers/quickstart.md) — setup and API reference
