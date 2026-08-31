# Workspaces & Jobs

> Two horizontal concerns: **workspace isolation** (multi-tenant data separation) and **jobs** (long-running collection / detection / network work). Both are real API surfaces in `SocialScienceResearch/api/openapi.json`.

## Workspaces (`/workspaces`)

Workspaces provide **database-level isolation** (DB-per-workspace). Each workspace has its own repository view, so one instance can serve multiple independent projects without cross-contamination.

```
GET  /api/v1/social-science/workspaces
POST /api/v1/social-science/workspaces
GET  /api/v1/social-science/workspaces/{workspace_id}
PATCH /api/v1/social-science/workspaces/{workspace_id}
```

- A per-request HTTP middleware (`route_to_active_workspace`, `app.py:1565`) routes each request to the active workspace, syncing it before handling.
- Deleting a workspace removes its data fully (its own DB + `data_dir`).

## Jobs (`/jobs`)

Long-running work — collection, network scraping, echo-chamber detection, content homophily — is submitted as **jobs** with a real lifecycle.

```
GET   /api/v1/social-science/jobs                       # list
POST  /api/v1/social-science/jobs/kill-stuck            # recover stuck jobs
GET   /api/v1/social-science/jobs/{job_id}              # status
POST  /api/v1/social-science/jobs/{job_id}/cancel       # cooperative cancel
GET   /api/v1/social-science/jobs/{job_id}/result       # final payload
GET   /api/v1/social-science/jobs/{job_id}/stream       # SSE progress
PATCH /api/v1/social-science/jobs/{job_id}/tags         # label / group
```

Job-driven flows include:

- **Collection**: `POST /collect` → `GET /jobs/{id}` → `GET /jobs/{id}/result`.
- **Network scrape**: `POST /network/scrape/run`, `/network/scrape/video`, `/network/scrape/channel`.
- **Layer / echo work**: `POST /network/layer/scrape`, `POST /echo-chamber/detect`.
- **Content homophily**: `POST /network/content-homophily`.

Cancels are **cooperative** (honoured between work units), and stuck jobs can be recovered with `kill-stuck`.

## Budget & concurrency

Long-running work is constrained by a deliberately designed budget system:

```
GET  /api/v1/social-science/budget/state
GET  /api/v1/social-science/budget/queue
GET  /api/v1/social-science/budget/events
GET  /api/v1/social-science/budget/circuit-breakers
POST /api/v1/social-science/budget/circuit-breakers/reset
```

Tightly coupled to the scraper's `request_delay` and enrich ceilings (see [Configuration](configuration.md)).

## Runs

A **run** is a collection execution; a job may drive multiple runs. Inspect runs with full provenance:

```
GET  /api/v1/social-science/runs
GET  /api/v1/social-science/runs/{run_id}
GET  /api/v1/social-science/runs/delta
GET  /api/v1/social-science/runs/{run_id}/deltas
GET  /api/v1/social-science/runs/{run_id}/errors
GET  /api/v1/social-science/runs/{run_id}/sub-runs
GET  /api/v1/social-science/runs/{run_id}/videos
```

---

- [Overview](index.md) · [Configuration](configuration.md) · [Troubleshooting](troubleshooting.md)
