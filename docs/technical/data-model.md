# Data Model

The platform persists **stable identity + time-varying observation** data. A
re-collection produces a *new observation row* instead of overwriting history.

## Entities and observations

| Entity | Stable metadata | Observation (time-varying) |
|---|---|---|
| Channel | title, handle, description, country, joined_date, avatar/banner, verified flag | subscriber/video/view counts, `observed_at` |
| Video | channel_id, title, description, duration, upload_date, tags, categories, language, availability, age_limit, is_short | view/like/comment/favorite counts, transcript status |
| Comment | author_name/id, text, published_at, is_reply, parent/root ids | like/reply counts, is_removed |
| Recommendation | — | source→recommended edge, position, status, `observed_at`, run attribution |
| Author (E1) | raw profile JSON (collected with comments) | aggregates: comment_count, first_seen_run, video_ids |

Every entity/observation preserves the raw source payload in `raw_json`.

## Key relations

- `CollectionRun` / `CollectionError`: what ran, what succeeded, what failed —
  failures are never silently dropped; each run snapshots its config.
- `TranscriptRecord`: `.txt` artifact + path reference; transcript-derived
  variables are flagged as derived.
- `VideoObservation.transcript_status` carries the documented transcript
  limitations (language best-effort, missing transcripts reported, not inferred).

## Repository layer (Excel, D5)

No SQL. `persistence/base.py` defines the repository interfaces; the Excel
implementation (`persistence/excel/…`) is the only provider. A config-keyed
factory (`build_repositories(provider=…)`) keeps replacement possible in
principle. Single-writer discipline is enforced at `WorkbookStore` (ADR-0009).

### Added repositories across phases

| Repository | Sheet(s) | Notes |
|---|---|---|
| `SampleRepository` | `samples` + `sample_members` | Immutable; members newline-joined + chunked into `{sample_id}::{chunk_index}` sidecar rows (Excel ~32k char cell limit) |
| `DatasetRepository` | `datasets` + `dataset_members` | Chunked members; optional raw-json sidecar files |
| `ProjectRepository` | `projects` | Targets, collection/sampling specs, research query, variable selection, notes, `config_hash` |
| `AuthorRepository` | `authors` | Raw profile JSON + aggregates (D4) |

Overflow sidecars exist because a single Excel cell cannot hold large member
lists; chunking is tested at 50k ids. Datasets created with overflow report a
`chunked storage` quality flag.

## Derived vs observed

Values are either **observed** (captured by the acquisition provider) or
**derived** (computed from observed values, e.g. engagement rates). Nothing is
estimated or imputed: missing values carry an explicit availability flag
(`available` / `missing` / `unsupported`), and statistics are computed over the
values that are actually available, with `n` and the evaluation population
returned alongside every result.
