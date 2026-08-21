# Ethics & Data Minimization

This platform collects, persists and analyzes publicly observable YouTube
metadata. The design rules that protect research subjects are:

## 1. Observed, never estimated

No metric is imputed or inferred. Missing values are reported with an explicit
availability flag (`available` / `missing` / `unsupported`), and statistics are
computed over available values with the evaluation population and `n`
disclosed. This prevents fabricated findings and keeps the analytical surface
honest.

## 2. Comment collection ceiling (ADR-0003)

yt-dlp comment pagination is not guaranteed exhaustive. The ceiling is a
**per-request, researcher-set** `max_comments_per_video` on the collection
spec (default `SOCIAL_MAX_COMMENTS_PER_VIDEO` = 10000). The ceiling is recorded
on the run for provenance so coverage can be audited; completeness is
documented as a limitation, never silently assumed.

## 3. Author profiles — raw data (D4, ADR-0010)

`AuthorRepository` stores raw author profiles — the metadata already collected
with comments (name, per-comment timestamps, video participation). The primary
analytical surface is **aggregates** (`comment_count`, `first_seen_at`,
`video_ids`, …); raw profile payloads are exposed only through the explorer
and dataset/export paths.

Privacy surface and controls:
- **Data minimization**: only fields the acquisition provider returned are
  stored; no enrichment from external sources.
- **No bulk profile scraping**: the platform does not query authors
  independently of comment collection.
- **Export discipline**: dataset/raw exports are explicit researcher actions,
  and chunked raw-json sidecars keep payloads auditable.
- **Deletion is the only mutation** for samples and datasets; deleting a
  sample removes its membership rows.

## 4. Failures are never silent

`CollectionError` rows record per-entity failures; `recommendation_unsupported`
edges are explicit; a video that could not be collected is recorded, not
omitted. Reproducibility depends on knowing exactly what was and was not
observed.

## 5. No credentials required

YouTube metadata is collected via yt-dlp without API keys, so there is no
token/secret handling surface and no third-party account is implicated.

## Researchers' responsibility

The platform enforces recording and transparency, not review. Researchers
should obtain appropriate institutional review for their study design, avoid
redistributing personally identifying profile data beyond the collected
scope, and treat the per-video comment ceiling and author-profile surface as
design decisions to disclose in methodology sections.
