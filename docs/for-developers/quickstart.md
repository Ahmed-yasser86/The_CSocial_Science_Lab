# Quickstart — Backend, Frontend, First Query

> Run the whole platform locally in a few minutes. Everything below reflects the real runbook in the repo (`docker-compose.yml`, `.env.example`, `pyproject.toml`).

## Prerequisites

- Python 3.11 (`pyproject.toml` declares `requires-python`; a `.venv` is recommended)
- Node 20+/21 for the Next.js UI (`SocialScienceResearch/ui/package.json`)
- Docker for Postgres (or point `SOCIAL_DATABASE_URL` at an existing Postgres)

## 1. Start Postgres

```bash
docker compose up -d
```

`docker-compose.yml` provisions a `postgres:16` container with the database (`social_science`) and credentials matching the default `SOCIAL_DATABASE_URL`. The schema (and the database itself) is created automatically on first backend boot — no manual `createdb`.

## 2. Configure environment

```bash
cp .env.example .env
# edit .env: add LLM/embedding keys as needed
```

Key variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `SOCIAL_DATABASE_URL` | Postgres URL (default `postgresql://postgres:123456@localhost:5432/social_science`) |
| `OPENAI_API_KEY`, `STRATEGIC_LLM`, `SMART_LLM`, `FAST_LLM`, `CHAT_MODEL`, `EMBEDDING` | LLM/embedding providers for the agent (also editable in the in-app AI Config UI) |
| `NEXT_PUBLIC_AGENT_BACKEND_URL` | Agent backend URL for the frontend |

## 3. Start the backend

The **same FastAPI process** serves the CSS workbench and the Graph-RAG agent:

```bash
uvicorn SocialScienceResearch.api:create_app --factory --host 0.0.0.0 --port 8000
```

- Interactive API docs: `http://127.0.0.1:8000/docs`
- Health: `GET http://127.0.0.1:8000/health`
- All 160 paths under `/api/v1/social-science/*`, `/api/agent/*`, `/copilotkit/*`

## 4. Start the frontend

```bash
cd SocialScienceResearch/ui
npm install
npm run dev
# → http://127.0.0.1:3000
```

The Next.js app proxies `/api/v1/social-science` → the backend.

## 5. Your first query

**Collect a channel** (enqueues a job):

```
POST /api/v1/social-science/collect
```

**Watch the job:**

```
GET /api/v1/social-science/jobs/{job_id}
```

**Build a network graph:**

```
GET /api/v1/social-science/network/graph?weight=recommendation:observation_count
```

**Centralities:**

```
GET /api/v1/social-science/network/centralities
```

**Export:**

```
GET /api/v1/social-science/network/export?format=graphml
```

## Trying the Graph-RAG agent

With LLM keys configured, the agent is reachable at:

```
GET  /api/agent/ai-config        # what providers the agent sees
POST /api/agent/run              # { "user_query": "...", "stages": ["subject"] }
GET  /api/agent/run/{run_id}/reports/{report_key}
```

or through the CopilotKit UI at `/agent`.

## Running the docs locally

```bash
pip install mkdocs-material
mkdocs serve   # http://127.0.0.1:8000
```

## Running the tests

```bash
# backend
python -m pytest SocialScienceResearch/tests -q

# openapi contract gate (must stay green)
python -m pytest SocialScienceResearch/tests/test_openapi_snapshot.py -q

# e2e (Playwright)
cd SocialScienceResearch/ui && npx playwright test
```

---

- [Architecture](architecture.md) — full layer breakdown
- [API Reference](api-reference.md) — all 160 paths
- [Ingestion & Agent](ingestion-and-agent.md) — the other two systems
- [Troubleshooting](troubleshooting.md) — common issues
