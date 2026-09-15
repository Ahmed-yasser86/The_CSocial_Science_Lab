# Achievements

> What the project has demonstrably accomplished — numbers, wins, and integrations, each linked to its canonical evidence. Claims without a link are not claims.

---

## Performance

- **Video enrichment: 33s → 2.8s (~12x faster)** — YouTube `/next` API bypass.
- **collect/recommendations endpoint: 90s+ timeout → 38s** — stub-based enrichment.
- **Multi-layer crawling**: 2+ layers, 6,500+ videos, 0 failures, 0 rate-limit blocks in 1 hour.
- **Advanced rate limiting**: AIMD BudgetController (self-tuning throttle), CircuitBreaker, YtdlContextLimiter, PriorityTaskQueue, speed presets (fast/balanced/careful).

Canonical evidence: [Performance Optimizations](for-developers/performance-optimizations.md), [Scraper Architecture](technical/scraper-architecture.md), [Recommendation Crawling](pipelines/recommendation-crawling.md).

## Transcript retrieval

- **Configured transcript service**: routes transcript fetching to FreeTranscriptAPI (when configured) instead of yt-dlp — **10x faster** transcript retrieval, no PO Token required.
- **Routing provider**: `RoutingAcquisitionProvider` selects the optimal transcript backend based on runtime config.

Canonical evidence: [Context-Aware Acquisition](pipelines/context-aware-acquisition.md), [Troubleshooting](for-developers/troubleshooting.md) (§3).

## Reliability

- **939/939 unit tests passing** + 71/71 E2E tests.
- **Auto-reconcile stuck runs** at boot (SQL `reconcile_stale_running`).
- **Job pause/resume**: stop long crawls, wait for rate limits, resume later.
- **UTF-8 / cp1252 crash fix**: non-Latin titles no longer crash the pipeline.

Canonical evidence: [Performance Optimizations](for-developers/performance-optimizations.md), [Workspaces & Jobs](for-developers/workspaces-and-jobs.md).

## Echo-chamber analysis

- **Configurable top-N recommendations**: scrape only top 5–10 per video (was hardcoded ~20).
- **Channel network projection**: 100% weakly connected components, 9.3% reciprocity, 11.8% global clustering.
- **Unattributed edge reduction**: 95% of edges survive channel projection (up from 54%).

Canonical evidence: [Echo-Chamber Detection](for-researchers/echo-chamber.md), [Network Science](for-researchers/network.md).

## GPT-Researcher integration

- **Customized fork** of [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) — tailored for this project's needs.
- **Customized system prompts**: every agent prompt rewritten for domain-specific use cases (audience intelligence, subject analysis, ecosystem mapping).
- **Key customizations**: embedding rate limiting, MCP tool selection improvements, context compression hardening, `.env` bootstrapping.
- **Not a divergent rewrite** — surgical additions to upstream codebase (15 files, 1028 insertions).

Canonical evidence: [GPT-Researcher Customization](for-developers/gpt-researcher-customization.md), [Ingestion & Agent](for-developers/ingestion-and-agent.md).

## Research capabilities

- **Reproducible sampling**: every sample records strategy, seed, strata, date range.
- **Read-only analytics**: no fabrications, every metric carries explicit availability flag.
- **Full provenance**: provider, version, config snapshot, per-entity errors per run.
- **Validated correctness**: centrality battery matches NetworkX on Zachary's Karate Club to 1e-6; deterministic reproducibility across runs at `seed=42`.

Canonical evidence: [Sampling](for-researchers/sampling.md), [Reproducibility](for-researchers/reproducibility.md), [Research Features](for-researchers/research-features.md).

---

## What these are not

Latency wins and test counts are **engineering achievements, not scientific findings**. They show the instrument works; they say nothing about YouTube, echo chambers, or polarization. For what the instrument enables scientifically, see [Research Features](for-researchers/research-features.md) and [Limitations](for-researchers/limitations.md).
