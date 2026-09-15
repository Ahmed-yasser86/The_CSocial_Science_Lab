# Recommendation Crawling: Observing What the Platform Connects

> How observable YouTube recommendations become a directed, layered graph with full provenance.

**Code:** `SocialScienceResearch/services/layer_scrape_service.py` · `SocialScienceResearch/services/recommendation_graph_service.py` · `SocialScienceResearch/acquisition/yt_dlp_adapter.py` · resilience `SocialScienceResearch/concurrency/` (`budget_controller.py`, `circuit_breaker.py`, `priority_queue.py`, `ytdlp_semaphore.py`)

---

## 1. Why: recommendations as observable platform behavior

YouTube's recommendation system creates directed pathways between content. Unlike many platform mechanisms, these pathways are partially observable ("Up Next", related videos) and can be systematically recorded. A collected edge is **an observation of platform behavior at a point in time under a controlled context** — not a record of what any user watched, believed, or did. That distinction conditions everything downstream (see [Limitations](../for-researchers/limitations.md)).

Because recommendations are personalized and context-dependent, collection is designed for **comparative research**: the scraping context (authentication, network position, browser identity) is a controlled experimental variable, not an operational detail. See [Context-aware acquisition](context-aware-acquisition.md).

---

## 2. Inputs

Seed video URLs (or channel discovery), plus the collection context (cookies / proxy / impersonation / speed preset) and per-run caps (`SOCIAL_MAX_ENRICH_TARGETS = 100`, comment/transcript toggles).

---

## 3. Stages

```
seeds
  → per-video recommendation extraction (three-layer fallback)
  → directed edge recording (source → recommended, with rank + provenance)
  → BFS layered expansion (Layer 0 seeds → Layer 1 → Layer 2 → …)
  → frontier management + NewRelationsReport per layer
  → per-layer persistence (LayerRun) + graph construction (DiGraph + PageRank)
```

### 3.1 Three-layer fallback extraction

`acquisition/yt_dlp_adapter.py`: (1) yt-dlp native fields (`recommended_videos`, `related`); (2) `yt-search-python` INNERTUBE `/next` endpoint; (3) page-dump "Up Next" parser. Layers are tried in order so the observed edge set is as complete as possible; which layer produced each edge is recorded as provenance.

### 3.2 Edge recording

Nodes are videos (with metadata enrichment up to the enrich cap; beyond it, lightweight stubs that stay edge-complete and are enrichable later). Edges are directed `source → recommended_video` with rank position, extraction layer, collection timestamp, and layer index.

### 3.3 BFS layered expansion

`layer_scrape_service.py` expands breadth-first: scrape every frontier video's recommendations, classify the results, persist the layer, advance the frontier. Each layer is a discrete analytical unit (`LayerRun`) with its own provenance, classification, and metrics — which is what makes frontier-collapse (S1) and cross-layer repetition (S4) measurable rather than metaphorical.

### 3.4 Frontier management — `NewRelationsReport`

Each observed edge is classified: `NEW_VIDEO` / `EXISTING_VIDEO`, `NEW_CHANNEL` / `EXISTING_CHANNEL`, `CONNECTED` / `DISCONNECTED` (`SKIPPED_DUPLICATE` for re-observations). The report is both an operational frontier (what to crawl next) and an analytical artifact (how the network grows).

---

## 4. Representation changes

```
platform responses (JSON/HTML/API)
  → recommendation edges (directed, ranked, provenanced)
  → layered graph (BFS strata with per-layer reports)
  → NetworkX DiGraph (PageRank, ego-networks, components)
  → channel projection (video edges aggregated to channel edges, weighted by video_edge_count)
```

---

## 5. AI vs deterministic logic

No learned model participates. Extraction is retrieval with deterministic fallback ordering; crawling is deterministic orchestration (BFS + classification); graph metrics (PageRank, HITS, components) are deterministic algorithms. The only nondeterminism is the platform itself — hence provenance per edge and the snapshot framing.

---

## 6. Resilience (operational, with methodological payoff)

| Mechanism | Implementation | Why it matters for research |
|---|---|---|
| AIMD budget control | `concurrency/budget_controller.py` | Self-tuning throttle; large crawls complete without rate-limit collapse (6,500+ videos, 0 blocks) |
| Circuit breaker (CLOSED/OPEN/HALF_OPEN) | `concurrency/circuit_breaker.py` | Per-session/proxy health; failures degrade gracefully instead of corrupting the dataset |
| Priority queue (DISCOVERY > ENRICHMENT > RECOMMENDATIONS > COMMENTS) | `concurrency/priority_queue.py` | Structural completeness first: edges before enrichment |
| Process-global yt-dlp semaphore | `concurrency/ytdlp_semaphore.py` | Bounded contexts (`SOCIAL_BUDGET_MAX_YTDL_CONTEXTS = 4`) |
| Bounded enrichment (`max_enrich_targets = 100`) | collection settings | Separates edge completeness (cheap, complete) from metadata enrichment (expensive, capped) |
| Retry with backoff (`SOCIAL_RETRIES = 10`, backoff `5.0`) | acquisition/retry | Transient failures don't corrupt datasets |
| Job pause/resume, stall detection (`900`s), boot reconcile | jobs service | Long crawls survive rate limits and restarts |

---

## 7. Persistence and provenance

Every edge/observation carries `collection_run_id`; each layer persists as a `LayerRun`. PostgreSQL (default) or Excel-legacy via the repository abstraction. Transcript artifacts and embedding caches stay on disk by convention in both backends.

---

## 8. Failure modes

Provider failure → next fallback layer; all layers fail → edge recorded `missing`/`unsupported`, never invented. Rate limit (429) → budgeted wait + circuit break; channel with repeated failures skipped. Empty graph (e.g. `recommendation_unsupported`) surfaces as an explicit status — see [Troubleshooting](../for-developers/troubleshooting.md).

---

## 9. Limitations

- Snapshot, not longitudinal behavior: recommendations are time-varying and personalized; one crawl is one observation point. Longitudinal claims need repeated crawls (see `longitudinal_service.py`, run deltas).
- Extraction coverage is best-effort: the fallback chain maximizes it but cannot guarantee completeness.
- No user behavior is observed: edges show what the platform surfaced, not what anyone consumed.
- `MAX_LAYERS_TOTAL = 10` (`echo_chamber_service.py:39`) caps echo-analysis depth.

---

## 10. Related documents

- [Context-aware acquisition](context-aware-acquisition.md) — the experimental variable behind every crawl
- [Content homophily](content-homophily.md) — the semantic layer built on top of this graph
- [Echo-chamber signals](../for-researchers/echo-chamber.md) — S1–S5, the analytical consumer
- [Scraper architecture](../technical/scraper-architecture.md) — implementation deep-dive (canonical for tuning details)
