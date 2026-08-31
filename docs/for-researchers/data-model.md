# Data Model

> Entities and observations, availability, identity, and persistence. Grounded in `SocialScienceResearch/domain/` and `persistence/`.

## Entities (nouns)

`SocialScienceResearch/domain/models.py`:

| Entity | Key fields |
|---|---|
| `Channel` | `channel_id`, `url`, `title` |
| `Video` | `video_id`, `url`, `channel_id`, `title` |
| `Comment` | `comment_id`, `video_id`, `author_id`, contents |
| `CollectionRun` | `run_id`, `run_type`, `target_url`, `status` |
| `Sample` | persisted with `strategy`, `seed`, `criteria_json` |

Entities carry stable identity + `raw_json`.

## Observations (measurements)

Time-varying statistics live **only** on per-run observations — never on the entity — so a measurement is always tied to when and how it was made (`models.py:5-16`):

| Observation | Measures |
|---|---|
| `ChannelObservation` | subscribers, video count, views (`models.py:115`) |
| `VideoObservation` | views, likes, comments, favorites (`models.py:164`) |
| `CommentObservation` | likes, replies, `is_removed` (`models.py:204`) |
| `RecommendationObservation` | `source→target`, `position`, `status` (`models.py:219`) |
| `TranscriptRecord` | path, lang, status, message (`models.py:244`) |

## Data availability everywhere

`domain/enums.py:137` — `available | missing | unsupported`. Missing = source didn't provide it; unsupported = method can't provide it. Both are explicit; **nothing is fabricated or estimated**.

## Identity resolution

Commenter identity is `author_id`-first with `author_name` fallback, via `resolve_author()` (`services/commenter_overlap_service.py`). Anonymous commenters are excluded, never given a fake id.

## Persistence (pluggable)

- **Default:** Postgres (`backend="sql"`, `config/settings.py:374`), URL `SOCIAL_DATABASE_URL`, schema auto-created on first boot.
- **Legacy / research:** Excel repositories (`persistence/excel_repository.py`) used in tests and offline research.
- **Vector:** Qdrant via `Ingestion_Pipline/infra/vector_store.py`.

The `Repositories` container (channels, videos, comments, recommendations, runs, samples, ...) is shared across all services (`services/`).

## Related API

```
GET  /api/v1/social-science/explore/records
GET  /api/v1/social-science/explore/records/{entity}/{id}/raw
GET  /api/v1/social-science/dataset/summary
GET  /api/v1/social-science/coverage
```

---

Previous: [Ethics & Data Minimization](ethics.md) · Next: [Citation](citation.md)
