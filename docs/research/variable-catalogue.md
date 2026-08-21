# Variable Catalogue

Single source of truth: `services/variable_registry.py`. Every variable's
`name` matches the exact `domain.models` field it resolves from, and each entry
declares `data_type`, `source` (observed / derived / raw), `unit`, `limits`,
and `availability` (the `ModelName.field` that supplies the value). The
catalogue is served to the UI by `GET /research/variables?entity=` and drives
both the query builder and the explorer filter controls.

**Source semantics**
- `observed` — captured by the acquisition provider at collection time.
- `derived` — computed from observed values (or resolved identity).
- `raw` — copied verbatim from the source payload.

Missing values are never fabricated: they carry an explicit availability flag
and are reported, not imputed.

## Channel

| Variable | Type | Source | Notes |
|---|---|---|---|
| `title`, `description`, `handle` | str | observed | banner/display text |
| `is_verified` | bool | observed | platform verification flag |
| `avatar_url`, `banner_url` | str | observed | media URLs |
| `country` | str | observed | disclosed country (may be missing) |
| `joined_date` | datetime | observed | ISO date |
| `subscriber_count` | int | observed | latest observation, ≥ 0 |
| `video_count` | int | observed | latest observation, ≥ 0 |
| `view_count` | int | observed | latest observation, ≥ 0 |

## Video

| Variable | Type | Source | Notes |
|---|---|---|---|
| `channel_id` | str | observed | owning channel |
| `title`, `description` | str | observed | |
| `duration` | int | observed | seconds, ≥ 0 |
| `upload_date` / `upload_timestamp` | datetime | observed | date vs full timestamp (hour/weekday) |
| `tags`, `categories` | list | observed | as published |
| `language` | str | observed | detected/declared |
| `live_status` | str | observed | is_live / was_live / post_live / None |
| `availability`, `age_limit`, `is_short` | str/int/bool | observed | source metadata |
| `thumbnail_url` | str | observed | |
| `view_count`, `like_count`, `comment_count`, `favorite_count` | int | observed | latest observation, ≥ 0 |
| `transcript_status` | str | derived | available / missing / unsupported |
| `transcript_lang` | str | derived | extracted transcript language |
| `transcript_length_chars` | int | derived | artifact character length, ≥ 0 |

## Comment

| Variable | Type | Source | Notes |
|---|---|---|---|
| `author_id`, `author_name` | str | observed | |
| `comment_text` | str | observed | reported as `text` |
| `published_at` | datetime | observed | |
| `is_reply` | bool | observed | direct reply vs root |
| `parent_comment_id`, `root_comment_id` | str | observed | thread structure |
| `is_author` | bool | observed | uploader-authored |
| `like_count`, `reply_count` | int | observed | latest observation, ≥ 0 |
| `is_removed` | bool | observed | latest observation |

## Author (E1)

| Variable | Type | Source | Notes |
|---|---|---|---|
| `author_id` | str | derived | stable key (`author_id`, fallback name) |
| `author_name` | str | raw | best-known display name |
| `comment_count` | int | derived | corpus-wide, ≥ 0 |
| `video_ids` | list | derived | distinct commented videos |
| `first_seen_at` / `last_seen_at` | datetime | derived | earliest/latest comment time |
| `is_author` | bool | observed | ever authored a commented video |
| `first_seen_run_id` | str | derived | provenance anchor |

## Recommendation

| Variable | Type | Source | Notes |
|---|---|---|---|
| `source_video_id` | str | observed | source of the edge |
| `recommended_video_id` | str | observed | target of the edge |
| `position` | int | observed | reported ordering, ≥ 0 |
| `status` | str | observed | observed / unsupported / failed |
| `channel_id`, `title` | str | observed | of the recommended video if disclosed |
| `observed_at` | datetime | observed | edge observation time |
