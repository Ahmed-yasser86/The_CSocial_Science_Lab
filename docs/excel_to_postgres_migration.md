# Migration Plan: Excel → PostgreSQL persistence

## 1. Why

The Excel persistence backend (`persistence/excel_workbook.py`) has three structural problems:

1. **32k-cell limit → overflow sidecars.** Any `raw_json` (full yt-dlp payload) larger than ~32,000 chars is evicted to per-bucket JSON files keyed by `(sheet, header, entity_id)`. Those sidecars can grow to 90–160 MB per bucket.
2. **Sidecar corruption / data loss.** A truncation mid-write (as happened) leaves orphan `__CELL_OVERFLOW__` sentinels that crash `row_to_model` with `ValidationError` (the bug behind the failed `expansion` job). The whole file is also loaded into RAM on boot (`json.load` of ~250 MB → ~1 GB RSS).
3. **No delete / no joins / no transactions.** Deletes are "blank the cells in place", pagination scans the whole workbook, and observation "latest" resolution is an N+1 read-everything.

PostgreSQL removes all three: `JSONB` columns have no 32k limit (no sidecars, no sentinels), the data lives in one transactional database (no corruption window, no RAM spike), and `DISTINCT ON`/indexes give cheap latest-resolution and joins.

## 2. Scope

Implement the full repository contract in `persistence/base.py` against PostgreSQL, keep the Excel implementation untouched and working, and switch the app/CLI default to the Postgres backend via settings.

- New module: `persistence/sql/` (schema + repositories + builder).
- New settings: `DatabaseSettings` (DSN) on `RepositorySettings`.
- Data import: a one-shot script that reads the existing Excel workbook + overflow sidecars into Postgres.
- The **pydantic domain models and services do not change** — they already talk only to the ABCs in `persistence/base.py`.

## 3. Schema design (tables)

One table per persisted entity; `JSONB` for all dict/list fields (no chunking). All ids are `TEXT` PKs (existing ids are generated strings).

| Table | PK | Notable columns |
|---|---|---|
| `channels` | `channel_id` | url, title, description, handle, ..., `raw_json JSONB` |
| `channel_observations` | `observation_id` | `channel_id`, `collection_run_id`, `observed_at`, counts, `raw_json JSONB` |
| `videos` | `video_id` | url, channel_id, title, ..., `tags JSONB`, `categories JSONB`, `chapters_json JSONB`, `raw_json JSONB` |
| `video_observations` | `observation_id` | video_id, run, observed_at, view/like/comment/favorite, `raw_json JSONB` |
| `comments` | `comment_id` | video_id, author_*, text, thread fields, `raw_json JSONB` |
| `comment_observations` | `observation_id` | comment_id, run, like/reply counts, is_removed, `raw_json JSONB` |
| `collection_runs` | `run_id` | run_type, targets, status, provider, `config_json JSONB`, `notes JSONB`, counts |
| `collection_errors` | `error_id` | run_id, entity_type/id, error_type, message, `details JSONB` |
| `recommendations` | `observation_id` | **UNIQUE** `(collection_run_id, source_video_id, recommended_video_id)`, position, status, `raw_json JSONB` |
| `transcripts` | `transcript_id` | video_id, run, path, lang, status, message, observed_at |
| `datasets` | `dataset_id` | name, entity_type, `source_projection JSONB`, member_count, overflow |
| `dataset_members` | `row_id` | dataset_id, chunk_index, `member_json JSONB` (no 28k chunking needed) |
| `projects` | `project_id` | name, `targets JSONB`, `collection_spec JSONB`, `sampling_specs JSONB`, `research_query JSONB`, `variable_selection JSONB`, config_hash |
| `project_items` | `item_id` | project_id, name, item_type, `sample_ids JSONB`, `dataset_ids JSONB`, `tags JSONB` |
| `samples` | `sample_id` | entity_type, strategy, `criteria_json JSONB`, `member_ids JSONB`, `scope JSONB`, `filters_applied JSONB`, `labels JSONB` |
| `sample_members` | `chunk_key` | sample_id, chunk_index, member_ids (kept for compat; no 30k limit needed) |
| `sample_tombstones` | `sample_id` | — |
| `layer_runs` | `layer_run_id` | layer_index, projection, `frontier_video_ids JSONB`, `discovered_video_ids JSONB`, `run_ids JSONB`, `summary JSONB`, `config_json JSONB` |

Enums (`RunType`, `CollectionStatus`, `EntityType`, `ErrorType`, `RecommendationStatus`, `TranscriptStatus`) are stored as `TEXT` (values are already strings; a native enum adds migration friction with no query win).

Indexes: all PKs (automatic), plus `videos(channel_id)`, `comments(video_id)`, `comment_observations(comment_id)`, observations `(entity_id, observed_at DESC)` for latest-resolution, `recommendations(source_video_id)`, `recommendations(collection_run_id)`, `dataset_members(dataset_id)`, `sample_members(sample_id)`, `project_items(project_id)`.

## 4. Code layout

```
persistence/sql/
  __init__.py          # re-export build_sql_repositories, SqlRepositories
  database.py          # engine factory, DDL (create_all), session handling
  repositories.py      # SQL implementations of all base.py ABCs + dataset/sample/project/project_item/layer repos
  factory.py           # build_sql_repositories(settings) -> SqlRepositories
```

## 5. Settings

Add to `RepositorySettings` (env-driven, so existing tests that build Excel repos still work):

- `backend: str` — `SOCIAL_REPOSITORY_BACKEND`, default `"excel"`.
- `database_url: str | None` — `SOCIAL_DATABASE_URL`, default `None` (then `postgresql://postgres:123456@localhost:5432/social_science` when backend is `"sql"`).

`build_excel_repositories` stays; a new `build_sql_repositories(settings)` is added. `SocialScienceSettings` exposes a helper `build_repositories()` that dispatches on `backend`.

## 6. Behavior parity requirements (verified against Excel impl)

- `UpsertResult.created` must be accurate (INSERT ... ON CONFLICT DO NOTHING returns rowcount).
- Observation latest-resolution: `DISTINCT ON (entity_id) ... ORDER BY observed_at DESC` preserves the "latest wins, ties → last scanned" semantics of `_latest_obs_by_id`.
- `list_runs` sorted by `started_at`; `list_transcripts` sorted with `observed_at` NULL last.
- Deletes: real `DELETE` rows (Excel blanking semantics are invisible to callers — `read_rows` already skips blank rows).
- Dataset/Sample chunking: SQL tables have no cell limit, but keep the `chunk_index`/`chunk_key` columns and the same `save_members`/`list_members` signatures so `DatasetService`/`SampleService` are untouched; store one chunk = full list (single chunk) is fine.
- `AuthorRepository` is a read-side projection over `comments` — SQL version does the same aggregation query over the `comments` table.
- Transcript artifacts remain external `.txt` files; only metadata goes to the `transcripts` table.

## 7. Migration steps (executed now)

1. `CREATE DATABASE social_science` (done).
2. Implement `persistence/sql/*`.
3. `scripts/migrate_excel_to_sql.py` — open Excel repos, read all sheets, insert into Postgres (chunked batches, `ON CONFLICT DO NOTHING`), then copy transcript artifacts (files already shared via `transcripts_dir`).
4. Switch app/CLI to `backend="sql"` via env (`SOCIAL_REPOSITORY_BACKEND=sql`).
5. Restart backend; verify `GET /videos/-fUgMrxDfWo?tab=network` no longer crashes (raw_json now reads from `JSONB`, no sentinel possible).
6. Run backend pytest suite against both backends (Excel tests stay green; new SQL smoke tests added).

## 8. Rollback

`SOCIAL_REPOSITORY_BACKEND=excel` restores the previous Excel behavior with zero code change (both backends implement the same ABCs). The Excel workbook is **not deleted** — it remains the source of truth backup until the SQL import is verified.

## 9. Risks / notes

- psycopg 3.3.4 installed (`psycopg[binary]`); SQLAlchemy 2.1 already present but unused — the SQL layer uses **raw SQL + psycopg** to avoid adding an ORM dependency.
- `extra="allow"` on pydantic models means unknown columns in DDL are fine, but the SQL layer only maps declared fields.
- The Postgres server runs as a Windows service (`postgresql-x64-17`); connection `postgres` / `123456` (set during setup).