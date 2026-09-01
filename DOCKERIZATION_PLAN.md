# Dockerization & Docker Compose Strategy: graph-rag-agent

## A. Current Architecture Assessment

### What Exists Today

The repository is a **monorepo** containing three Python packages that are tightly coupled at runtime:

```
graph-rag-agent/
├── SocialScienceResearch/          # YouTube data acquisition + computational social science
│   ├── api/app.py                  # FastAPI application factory (create_app)
│   ├── api/routers/                # 19 API router modules
│   ├── acquisition/                # yt-dlp adapter, transcript providers
│   ├── services/                   # 38 service modules
│   ├── persistence/                # PostgreSQL (psycopg3) + Excel backends
│   ├── config/settings.py          # All configuration via env vars
│   ├── concurrency/                # Budget controller, circuit breaker, priority queue
│   └── ui/                         # Next.js 16 frontend
├── RetrievalPipeline/              # LangGraph intelligence pipeline
│   ├── agent_server.py             # Merged INTO the main FastAPI backend
│   ├── Graph/intelligence_graph.py # LangGraph StateGraph
│   └── Graph/persistence.py        # SQLite persistence for runs
├── Ingestion_Pipline/              # Document extraction, chunking, embeddings → Qdrant
│   ├── config/settings.py          # Qdrant + embedding + chat model config
│   └── infra/vector_store.py       # QdrantVectorStore (external API)
└── gpt-researcher/                 # Customized fork (tracked, not from PyPI)
```

### Critical Architectural Finding

**The backend is a single-process monolith.** The RetrievalPipeline agent server routes are merged into the same FastAPI app. These three packages MUST run in the same container.

### Runtime Execution Flow

```
Browser
  ├──► Frontend (Next.js :3000)
  │       └──► rewrite proxy ──► Backend API (:8000)
  └──► Backend API (FastAPI + Uvicorn :8000)
          ├──► PostgreSQL (:5432) — social science data
          ├──► Qdrant (external API) — vector store
          ├──► SQLite (filesystem) — intelligence run persistence
          ├──► External LLM providers
          ├──► YouTube — via yt-dlp (needs Node.js)
          └──► Filesystem — transcripts, exports, proxy config
```

## B. Proposed Container Architecture

### Services (3 containers + 1 external)

| Service | Image | Purpose |
|---------|-------|---------|
| `backend` | Custom Python 3.11 | FastAPI monolith (social-science API + research agent + ingestion) |
| `frontend` | Custom Node 20 | Next.js 16 production server |
| `postgres` | `postgres:16` | PostgreSQL database |
| `qdrant` | **External API** | Vector database (NOT containerized) |

### What Stays Inside the Backend Container

- SocialScienceResearch (API + services + acquisition + persistence)
- RetrievalPipeline (LangGraph intelligence graph)
- Ingestion_Pipline (document extraction + embeddings)
- gpt-researcher (customized fork, imported via sys.path)

### What is NOT Introduced

- No Redis/Celery/RabbitMQ
- No separate worker container
- No Nginx/reverse proxy
- No Qdrant container (external API)

## C. Service Dependency Graph

```
                    ┌──────────────┐
                    │   Browser    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   frontend   │
                    │  (Next.js)   │
                    └──────┬───────┘
                           │ HTTP
                    ┌──────▼───────┐
                    │   backend    │
                    │  (FastAPI)   │
                    └──┬───────┬───┘
                       │       │
            ┌──────────┘       └──────────┐
     ┌──────▼──────┐              ┌───────▼───────┐
     │  postgres   │              │  Qdrant API   │
     │  (PostgreSQL)│              │  (External)   │
     └─────────────┘              └───────────────┘
```

## D. Port Strategy

| Service | Host Port | Internal Port | Exposure |
|---------|-----------|---------------|----------|
| `frontend` | `3000` | `3000` | Host-facing |
| `backend` | `8000` | `8000` | Host-facing (dev only) |
| `postgres` | `5432` (dev) | `5432` | Internal only (prod) |

## E. Volume / Persistence Strategy

| Volume | Container Path | Purpose |
|--------|---------------|---------|
| `pgdata` | `/var/lib/postgresql/data` | PostgreSQL data |
| `intelligence_data` | `/app/intelligence_data` | SQLite + research run files |
| `./data` (bind) | `/app/data` | Social science data (dev) |
| `./.env` (bind) | `/app/.env` | Environment config (dev) |

## F. Environment Variable Strategy

### Secrets (NEVER baked into images)

- `OPENAI_API_KEY`, `TAVILY_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`
- `QDRANT_API_KEY`, `POSTGRES_PASSWORD`, `LANGSMITH_API_KEY`
- `SOCIAL_PROXY`, `FREETRANSCRIPTAPI_KEY`, `HF_TOKEN`
- `MCP_API_KEY`, `GDELT_MCP_API_KEY`, `SOCIALCRAWL_MCP_API_KEY`

### Non-Secret Configuration

- `SOCIAL_DATABASE_URL=postgresql://postgres:123456@postgres:5432/social_science`
- `SOCIAL_API_HOST=0.0.0.0`
- `QDRANT_URL=http://<external-qdrant-host>:6333`
- `QDRANT_COLLECTION_NAME=DocumentHelper`
- `BACKEND_URL=http://backend:8000`
- `NEXT_PUBLIC_AGENT_BACKEND_URL=http://backend:8000`

## G. Dockerfile Strategy

### Backend: `Dockerfile.backend`

```
Stage 1: python:3.11-slim-bookworm AS builder
  - System build deps (gcc, libpq-dev, libmagic-dev)
  - Python deps via uv pip install
  - gpt-researcher editable install
  - Node.js (for yt-dlp JS challenge solving)

Stage 2: python:3.11-slim-bookworm AS runtime
  - Runtime system libs (libpq5, libmagic1, node)
  - Installed Python packages from builder
  - Application code (4 packages at correct relative paths)
  - Non-root user
  - CMD: uvicorn SocialScienceResearch.api:create_app --factory
```

### Frontend: `Dockerfile.frontend`

```
Stage 1: node:20-alpine AS builder
  - npm ci
  - Build Next.js (NEXT_PUBLIC_* as build args)

Stage 2: node:20-alpine AS runtime
  - .next output + node_modules + package.json + public
  - CMD: npm start
```

## H. Compose Strategy

- `docker-compose.yml` — Base (all services)
- `docker-compose.dev.yml` — Dev overrides (bind mounts, hot reload)
- `docker-compose.prod.yml` — Prod overrides (resource limits, no host DB ports)

## I. Health Checks

- **PostgreSQL**: `pg_isready -U postgres -d social_science`
- **Backend**: `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`
- **Frontend**: `wget --spider -q http://localhost:3000`

## J. Security Hardening

- Non-root user in backend container
- No secrets in images
- PostgreSQL not exposed to host in production
- CORS configured for production domains

## K. Scraping-Specific Requirements

- **Node.js required** in backend container for yt-dlp JS challenge solving
- No browser binaries needed (yt-dlp uses HTTP extraction)
- Cookie file mode works in containers; browser cookie mode does not
- No ffmpeg needed (skip_download: True)

## L. Research Reproducibility

- Sampling seed via env var (SOCIAL_SAMPLING_SEED=42)
- Python deps pinned in pyproject.toml + uv.lock
- PostgreSQL schema created idempotently
- Pin base image digests for full reproducibility

## M. Backup / Recovery

- `docker compose down` — preserves volumes
- `docker compose down -v` — destroys all data
- PostgreSQL: `pg_dump` for backup
- Qdrant: Rebuild from source documents (external API)

## N. Risks and Migration Hazards

1. **sys.path manipulation** — directory structure must be preserved exactly in container
2. **gpt-researcher editable install** — must be installed, not just copied
3. **Heavy dependencies** — torch, transformers, docling, spacy → large image (5-10GB)
4. **Node.js requirement** — unusual for Python container, must be explicitly installed
5. **Frontend rewrite proxy** — BACKEND_URL read at runtime, must be available at start

## O. Implementation Order

1. Create `.dockerignore`
2. Create `Dockerfile.backend`
3. Build and test backend image
4. Create `Dockerfile.frontend`
5. Build and test frontend image
6. Update `docker-compose.yml`
7. Create `docker-compose.dev.yml`
8. Create `docker-compose.prod.yml`
9. Test complete stack
10. Test persistence
