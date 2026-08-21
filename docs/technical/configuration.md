# Configuration Reference

All settings are typed in `SocialScienceResearch/config/settings.py` and are
environment-configurable. No secrets are required; YouTube metadata is
collected via yt-dlp without API credentials.

## Persistence

| Variable | Default | Purpose |
|---|---|---|
| `SOCIAL_DATA_DIR` | `<project>/data/social_science` | Directory for the Excel workbook + transcripts |
| `SOCIAL_DATASET_NAME` | `youtube_research` | Workbook filename (`{name}.xlsx`) |
| `SOCIAL_MAX_ROWS_PER_SHEET` | `1048570` | Sheet split threshold (Excel hard limit 1048576) |
| `SOCIAL_FLUSH_EVERY` | `1000` | Write-through rows before auto-saving the workbook |

## Acquisition

| Variable | Default | Purpose |
|---|---|---|
| `SOCIAL_RETRIES` / `SOCIAL_RETRY_BACKOFF` / `SOCIAL_SOCKET_TIMEOUT` / `SOCIAL_REQUEST_DELAY_SECONDS` | 3 / 2.0 / 30.0 / 0.5 | yt-dlp retry & throttling policy |
| `SOCIAL_IMPERSONATE` | — | yt-dlp impersonation target |
| `SOCIAL_PROXY` | — | HTTP(S) proxy |
| `SOCIAL_IGNORE_ERRORS` | `false` | Continue past per-entity failures |
| `SOCIAL_TRANSCRIPT_LANG` | `en` | Best-effort transcript language preference |

## Collection

| Variable | Default | Purpose |
|---|---|---|
| `SOCIAL_COLLECT_COMMENTS` | `true` | Collect comments in video/channel workflows |
| `SOCIAL_MAX_COMMENTS_PER_VIDEO` | `10000` | Documented per-video comment ceiling (ADR-0003) |
| `SOCIAL_MAX_VIDEOS_PER_CHANNEL` | `100000` | Channel pagination safety ceiling |
| `SOCIAL_ENRICH_VIDEO_STATS` | `false` | Deep per-video extraction in channel workflows |
| `SOCIAL_MAX_VIDEOS_TO_ENRICH` | `0` (unlimited) | Cap on deep enrichment |
| `SOCIAL_EXTRACT_FLAT` | `true` | Use fast flat playlist entries for discovery |

## Sampling, query, analytics

| Variable | Default | Purpose |
|---|---|---|
| `SOCIAL_SAMPLING_SEED` | `42` | Default RNG seed for reproducible sampling |
| `SOCIAL_LONG_VIDEO_THRESHOLD_SECONDS` | `300` | "Long video" threshold (`>=`) |
| `SOCIAL_TOP_N` | `10` | Default N for list/top-N endpoints |
| `SOCIAL_VELOCITY_BUCKET` | `hour` | Comment-velocity bucket granularity (`hour`/`day`) |

## API & jobs

| Variable | Default | Purpose |
|---|---|---|
| `SOCIAL_API_HOST` / `SOCIAL_API_PORT` | `127.0.0.1` / `8000` | uvicorn bind address |
| `SOCIAL_API_PREFIX` | `/api/v1/social-science` | Route prefix |
| `SOCIAL_API_DOCS_ENABLED` | `true` | Serve interactive docs at `/docs` |
| `SOCIAL_CORS_ORIGINS` | `http://localhost:3000, http://127.0.0.1:3000` | Comma-separated allowed origins |
| `SOCIAL_JOB_MAX_WORKERS` | `2` | Concurrent in-process collection jobs |

## Running the stack

```bash
# backend
uvicorn SocialScienceResearch.api:create_app --factory

# frontend (proxies /api/v1/social-science to the backend)
cd ui && npm run dev
```

The Next.js dev server rewrites the API prefix to `BACKEND_URL`
(default `http://127.0.0.1:8000`).
