# For Developers

> **5 minutes to run.** This track gets you from zero to a working graph + research dataset. It's written for engineers and business/programming users who want to run, integrate, or extend the platform.

## In this track

| Page | What you'll get |
|---|---|
| [Quickstart](quickstart.md) | Postgres → backend → frontend → first query |
| [Architecture](architecture.md) | The full layer breakdown + the single FastAPI app |
| [API Reference](api-reference.md) | All **160 paths** (generated from the guarded OpenAPI contract) |
| [Ingestion & Agent](ingestion-and-agent.md) | The Tavily→Qdrant pipeline and the LangGraph agent |
| [Workspaces & Jobs](workspaces-and-jobs.md) | Multi-tenant isolation + long-running work |
| [Configuration](configuration.md) | Every env var, defaults, providers |
| [Performance Optimizations](performance-optimizations.md) | Rate limiting, fast extraction, pause/resume, all optimizations |
| [GPT-Researcher Customization](gpt-researcher-customization.md) | Customized fork, system prompts, embedding rate limiting |
| [Troubleshooting](troubleshooting.md) | 10 real fixes |

## What you can do in 5 minutes

1. `docker compose up -d` — Postgres.
2. `uvicorn SocialScienceResearch.api:create_app --factory --port 8000` — the whole API (CSS + agent) in one process.
3. `GET /api/v1/social-science/network/graph` — a network graph.
4. `GET /api/v1/social-science/network/centralities` — network measures.
5. `GET /api/v1/social-science/network/export?format=graphml` — a portable artifact.

## Honest developer notes

- **One process, two concerns.** The CSS workbench and the Graph-RAG agent share a single FastAPI app. If the agent fails to import, the agent routes 404 but the workbench still works (the mount is guarded).
- **The API is generated, not hand-documented.** `openapi.json` is the contract; CI fails on drift. Never regenerate it without committing the new snapshot together with the code.
- **Persist heavy artifacts.** Ingestion writes to Qdrant; analytics read observed edges from Postgres/Excel. Both are cheap to blow away and rebuild.

---

- Start at the [Quickstart](quickstart.md).
- Recruiter/reviewer? [Recruiters](../for-recruiters/index.md) · [Researchers](../for-researchers/index.md)
