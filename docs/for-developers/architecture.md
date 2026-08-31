# Architecture

> The full layer breakdown of the CSS workbench (`SocialScienceResearch/`), plus how the agent (`RetrievalPipeline/`) and ingestion (`Ingestion_Pipline/`) plug in.

## Layered architecture

`SocialScienceResearch/` is structured `acquisition → domain → persistence → services → api → ui`:

| Layer | Location | Responsibility |
|---|---|---|
| **acquisition/** | `SocialScienceResearch/acquisition/` | `yt-dlp` adapters; scraper retries, proxy config, rate limiting (`scraper/`) |
| **domain/** | `SocialScienceResearch/domain/` | entities, observations, enums (`models.py`, `enums.py`) — no infrastructure |
| **persistence/** | `SocialScienceResearch/persistence/` | Postgres repositories + Excel repositories |
| **services/** | `SocialScienceResearch/services/` | 30+ services: `network_analytics_service`, `sampling_service`, `echo_chamber_service`, `commenter_overlap_service`, `dataset_service`, ... |
| **api/** | `SocialScienceResearch/api/` | FastAPI `create_app()`, routers, schemas |
| **ui/** | `SocialScienceResearch/ui/` | Next.js 16 frontend |

## The single FastAPI app

`SocialScienceResearch/api/app.py:1299` `create_app()` builds one FastAPI app that includes:

- **18 CSS routers** under `/api/v1/social-science/*` (channels, commenters, comments, comparison, content_homophily, datasets, echo_chamber, explorer, expansion, layer_network, network_ext, project_items, samples, scraper_config, budget, search, session, workspaces) — registered at `app.py:1747-1781`.
- **Direct app routes** (`app.py:1853+`): `/collect*`, `/jobs*`, `/runs*`, `/channels*`, `/videos*`, `/sampling/advanced`, `/research/*`, `/export`, `/coverage`, `/dataset/summary`.
- **The agent router** (conditional, guarded): `RetrievalPipeline/agent_server.py:461` mounted if the graph imports (`app.py:1819-1833`). Serves `/api/agent/*`, `/copilotkit/*`, `/health`.

The result: **160 paths** in `api/openapi.json`.

## Services (container)

`build_services()` at `app.py:295` constructs the service container (`collection`, `recommendations`, `analytics`, `query`, `sampling`, `network`, `quality`, `jobs`, `layer_scrape`, `echo`) and shares a single `Repositories` object plus `JobsManager` / `BudgetController`.

## Middleware & cross-cutting

- **HTTP middleware** `route_to_active_workspace` (`app.py:1565`) syncs the active workspace per request (DB-per-workspace isolation).
- **CORS** (`app.py:1589`), **exception handlers** (`app.py:1611`), circuit breaker + priority task queue.

## The Graph-RAG agent (B)

`RetrievalPipeline/Graph/intelligence_graph.py:506` compiles a LangGraph `StateGraph` with **5 nodes** (`:561-565`):

- `identity_research` → `profile_summarization` → (`report_router`) → `subject_intelligence` / `audience_intelligence` / `ecosystem_intelligence`.

The `report_router` (`:92`) is a conditional edge that runs whichever report is missing, or returns `END`. Compiled with a `MemorySaver` checkpointer (`:588`) for resumable runs. Served over HTTP by `agent_server.py:461`.

See [Ingestion & Agent](ingestion-and-agent.md).

## Ingestion pipeline (C)

`Ingestion_Pipline/` is a **library**, not a service:

- Tavily map/crawl/extract → `ingestion/chunking.py` → `ingestion/embedding_pipeline.py` (`ResilientEmbeddingPipeline`) → Qdrant (`infra/vector_store.py`).
- Rate limiting (`infra/rate_limiter.py`), retry policies (`infra/retry_policies.py`), provider-agnostic embeddings (`infra/embeddings.py`).

See [Ingestion & Agent](ingestion-and-agent.md).

---

- [Overview](index.md) · [Quickstart](quickstart.md) · [API Reference](api-reference.md)
