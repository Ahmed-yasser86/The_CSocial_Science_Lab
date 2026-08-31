# Configuration

> All runtime behavior is controlled by environment variables read from the repository root `.env` (copy of `.env.example`). The backend reads these on boot; many are also editable from the in-app **AI Config** UI (`/api/agent/ai-config`).

## Where config lives

| Concern | Source |
|---|---|
| Environment | `.env.example` (copy to `.env`) |
| Settings model | `SocialScienceResearch/config/settings.py` |
| Docker / DB | `docker-compose.yml` (Postgres 16) |

## Database

| Variable | Default | Notes |
|---|---|---|
| `SOCIAL_DATABASE_URL` | `postgresql://postgres:123456@localhost:5432/social_science` | Schema + DB auto-created on first boot |
| `SOCIAL_REPOSITORY_BACKEND` | `sql` | `excel` available for offline/research/testing |

## LLM / embedding providers (agent)

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | OpenAI provider |
| `STRATEGIC_LLM`, `SMART_LLM`, `FAST_LLM` | Agent model tiers (subject/audience/ecosystem research) |
| `CHAT_MODEL_PROVIDER`, `CHAT_MODEL` | Chat model for the agent UI |
| `EMBEDDING`, `GPT_RESEARCHER_EMBEDDING` | Embedding provider (`provider:model`), default Google `gemini-embedding-2-preview` |

## Collection & sampling defaults

| Variable | Default | Purpose |
|---|---|---|
| `SOCIAL_SAMPLING_SEED` | `42` | Deterministic sampling |
| `SOCIAL_MAX_COMMENTS_PER_VIDEO` | `10000` | Comment ceiling |
| `SOCIAL_MAX_VIDEOS_TO_ENRICH` | `50` | Enrich budget (wall-clock bound) |
| `SOCIAL_MAX_ENRICH_TARGETS` | `100` | Layer/echo crawl target cap |
| `SOCIAL_REQUEST_DELAY_SECONDS` | `0.5` | Rate-limit compliance between requests |
| `SOCIAL_COLLECT_COMMENTS` | `True` | Comment collection on by default |
| `SOCIAL_COLLECT_TRANSCRIPTS` | `False` | Transcripts strictly opt-in (privacy) |
| `SOCIAL_TRANSCRIPT_LANG` | `en` | Transcript language |

## Frontend

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_AGENT_BACKEND_URL` | Where the Next.js frontend reaches the agent backend |

## OpenAI/Swagger

- Interactive docs at `/docs` (enabled by `settings.api.docs_enabled`) and alternate `/redoc`.
- CORS origins configured via `settings.api.cors_origins`.

---

- [Overview](index.md) · [Architecture](architecture.md) · [Troubleshooting](troubleshooting.md)
