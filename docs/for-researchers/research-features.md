# Scientifically Distinctive Features

> Capabilities of this repository that are genuinely methodological — not ordinary engineering — each grounded in the implementation. Ordinary CRUD, auth, and UI work is deliberately excluded.

---

## 1. Structure × meaning integration (flagship)

The [content-homophily pipeline](../pipelines/content-homophily.md) measures network structure (Louvain communities, `seed=42`) and semantic content (transcript embeddings, mean pooling, cosine) independently, then tests whether they coincide (within-minus-between difference + label-permutation null). The scientific move is the *separation*: structure never stands in for meaning. See [Structure vs Meaning](../concepts/structure-vs-meaning.md).

## 2. Context-aware acquisition as experimental variable

Collection context — authentication (anonymous / browser / file cookies), network position (direct / rotating-residential proxy with sticky sessions), browser impersonation — is runtime-configurable, persisted (`proxy_config.json`), and recorded per observation. The same seed can therefore be observed under different contexts and the resulting recommendation networks compared. The scraper is an instrument with controlled settings, not a harvester. See [Context-Aware Acquisition](../pipelines/context-aware-acquisition.md). Code: `SocialScienceResearch/acquisition/`, `config/settings.py` (`ScraperSettings`), `api/routers/scraper_config.py`.

## 3. Layered crawling as discrete analytical process

BFS expansion where each layer is a persisted `LayerRun` with its own frontier classification (`NEW_VIDEO / EXISTING_VIDEO / NEW_CHANNEL / CONNECTED / DISCONNECTED`) and metrics. Layering is what makes frontier-collapse (S1) and cross-layer repetition (S4) measurable quantities rather than metaphors. See [Recommendation Crawling](../pipelines/recommendation-crawling.md). Code: `services/layer_scrape_service.py`.

## 4. Five-signal echo-chamber operationalization with honesty contract

Echo-chamber *dynamics* → five observable structural ratios (S1–S5), each with exact formula, each wrapped `available | unavailable`, composite = renormalized weighted mean over available signals only, missing core signal ⇒ `inconclusive` verdict. The honesty contract (never zero-fill, weights disclosed as heuristic) is part of the method, not packaging. See [Echo-Chamber Detection](echo-chamber.md). Code: `services/echo_chamber_service.py`, `services/echo_scoring.py`.

## 5. Permutation-null discipline for similarity claims

Both the content-homophily null (label shuffling, `seed:index` per permutation, identical sampling constraints re-applied) and the WCR null (degree-preserving randomization, `DEFAULT_N_RANDOMIZATIONS = 10`) give every "higher than expected" claim a computed baseline with z-score and finite-sample-corrected p-value. Significance is always reported next to coverage and effect size, with the exchangeability assumption stated. Code: `services/content_homophily_service.py` (`ContentHomophilyNullModelService`), `services/structural_metrics.py` (`null_model_wcr`).

## 6. Deterministic-by-construction analysis

`seed=42` across sampling (`SOCIAL_SAMPLING_SEED`), Louvain (`COMMUNITY_SEED`), permutation tests, and approximate betweenness — plus immutable persisted samples with generation recipes (`criteria_json`) and content-hash-keyed embedding caches. Reproducibility is an architectural property, not a checklist item. See [Reproducibility](reproducibility.md).

## 7. Explicit availability typing (anti-fabrication rule)

Every observation and every signal carries `available | missing | unsupported` (analyses: `insufficient_sample`). Absence is a first-class state that propagates through means (pairs skipped, never zeroed), composites (renormalized, never zero-filled), and verdicts (`inconclusive`). This is a methodological safeguard against the most common quantitative error: treating unobserved as zero. Code: `domain/enums.py`, enforced per service.

## 8. Weight-spec grammar (explicit edge semantics)

`edge_type:weight_mode[:param]` makes graph-construction decisions — what counts as an edge and how much it counts — explicit, parseable, and reproducible instead of buried in code. Rare in applied network-analysis tooling; it turns a usually-tacit decision into a reportable methods detail. Code: `services/weight_spec.py`. See [Network Science](network.md).

## 9. Channel projection with attribution accounting

Video-level recommendation edges aggregate to channel-level graphs weighted by `video_edge_count`, with unattributed-edge accounting (95% of edges survive projection, up from 54%). Cross-level analysis (video wiring vs channel concentration, S3) is therefore quantified rather than hand-waved. Code: `services/network_analytics_service.py` (`channel_graph`), `services/structural_metrics.py` (`channel_concentration`, HHI).

## 10. Bridge and cross-community machinery

Bridge commenters (active across ≥ `min_entities` units), inter-community edges, community interaction matrices, network merge with overlap statistics, community persistence (Jaccard across layers), conductance/WCR per community. The project analyzes *between* communities as a first-class object, not just membership. Code: `services/commenter_overlap_service.py`, `services/network_matrix_service.py`, `services/comparison_service.py`, `services/structural_metrics.py`.

## 11. Longitudinal and comparative substrate

Run deltas, observation gaps, growth tracking, period/cohort comparison with normalization and outlier detection — the scaffolding for "how did this environment change?" on top of snapshot collection. Young relative to the features above (less exercised), documented as enabled rather than established. Code: `services/longitudinal_service.py`, `services/comparison_service.py`.

---

## Deliberately not listed

Multi-source fallback extraction, AIMD throttling, circuit breakers, dual persistence, workspace isolation, job pause/resume, the LangGraph intelligence agent, Tavily→Qdrant ingestion — all real engineering, all documented elsewhere ([Architecture](../for-developers/architecture.md), [Recommendation Crawling](../pipelines/recommendation-crawling.md)) — but engineering robustness, not scientific method. The test counts (939 unit + 71 E2E) and latency wins (33s → 2.8s) are achievements, not findings.
