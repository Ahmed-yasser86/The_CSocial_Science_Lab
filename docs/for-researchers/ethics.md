# Ethics & Data Minimization

> What is collected, how it is limited by default, and what must be stated in a paper. Grounded in `SocialScienceResearch/config/settings.py` and `services/commenter_overlap_service.py`.

## 1. What is collected (and what is not)

| Data | Collected | Not collected / not inferred |
|---|---|---|
| YouTube metadata | Channel/video/comment/recommendation observations, each with a `raw_json` copy of the sanitized provider payload | No private/age-restricted beyond what `yt-dlp` exposes publicly |
| Commenter identity | `author_id` preferred; `author_name` fallback via `resolve_author()` | Anonymous / handle-less comments are excluded — an id is **never fabricated** (`commenter_overlap_service.py`) |
| Transcripts | **Never auto-collected** by default (`SOCIAL_COLLECT_TRANSCRIPTS=False`) | No bulk transcript crawl |
| Recommendations | Observed `source→target + position + run_id` (structural only) | No personalization, no viewer beliefs |

## 2. Default ceilings & throttling

All defaults in `SocialScienceResearch/config/settings.py`:

| Ceiling | Default | Env var | Why |
|---|---|---|---|
| Comments per video | `10000` | `SOCIAL_MAX_COMMENTS_PER_VIDEO` (`:40,287`) | yt-dlp pagination is not guaranteed exhaustive; a hard cap would silently truncate |
| Videos to enrich | `50` | `SOCIAL_MAX_VIDEOS_TO_ENRICH` (`:56,312`) | Bounds wall-clock time |
| Enrich targets | `100` | `SOCIAL_MAX_ENRICH_TARGETS` (`:37,231`) | Same for layer/echo crawls |
| Request delay | `0.5s` | `SOCIAL_REQUEST_DELAY_SECONDS` (`:29,220`) | Rate-limit compliance with the platform |
| Collect transcripts | `False` (opt-in) | `SOCIAL_COLLECT_TRANSCRIPTS` (`:48,291`) | Privacy by default; UI ships opt-in |
| Collect comments | `True` | `SOCIAL_COLLECT_COMMENTS` (`:41,281`) | Needed for audience-family analysis |

## 3. Stem/identity minimization

- **Commenter identity is id-first**: `resolve_author()` returns an `author_id` when available, falling back to `author_name` only when the provider returns it — and never fabricating an id (`services/commenter_overlap_service.py`).
- Anonymous / handle-less comments are excluded, and analyses note when `identity_kind="name"` is used (fragility is surfaced, not hidden).

## 4. Provenance & availability

Every row carries `run_id` + `observed_at` + provider; failures become `CollectionError` rows. Missing signals are flagged `available | missing | unsupported` (`domain/enums.py:137`) — **never zeroed**. This makes the ethics of the dataset auditable.

## 5. What to state in a paper

Alongside [Reproducibility](reproducibility.md), a paper should state:

1. Which ceiling values were used and why (comment cap, video enrich cap).
2. Whether transcripts were collected (and for which opt-in scope).
3. Commenter identifiability: `author_id` vs `name` coverage, anonymous exclusion.
4. Collection dates, workspace id/name, and platform snapshot limitations.
5. The exact seeds used (sampling, Louvain, permutation) and the weight-spec tokens.

## 6. Retention & deletion

- Samples are immutable (ADR-0011); the only mutation is a tombstone.
- Datasets/projects support real `DELETE` in Postgres; workspaces are DB-per-workspace so deleting a workspace removes its data fully.

---

Previous: [Sampling](sampling.md) · Next: [Data Model](data-model.md)
