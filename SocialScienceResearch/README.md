# SocialScienceResearch

A research-oriented **YouTube data acquisition and computational social science
analytics module**. It collects structured, reproducible YouTube data and
persists it to support longitudinal, quantitative social-science research.

## Purpose

* Acquire channel, video and comment data from YouTube through a swappable
  acquisition provider (default: `yt-dlp`).
* Persist a **stable identity + time-varying observation** data model so that
  re-collection produces a *new observation* instead of overwriting history.
* Provide **reproducible research sampling** (top/bottom, stratified, random,
  date-range, ...) with the exact criteria recorded for every sample.
* Provide **read-only analytics** that never fabricate or estimate missing
  values: every metric carries an explicit availability flag.
* Track full **provenance** per run (provider, provider version, config
  snapshot, per-entity errors) for reproducibility.

## Architecture

Layers depend only on interfaces, so the Excel backend and the yt-dlp adapter
can be replaced without touching business logic.

```
acquisition/   provider interface + yt-dlp adapter + normalization
domain/        enums, entity/observation models, query & sampling specs
persistence/   repository interfaces (base) + Excel implementation
services/      collection workflows, sampling, analytics, recommendation network
api/           FastAPI application factory
config/        typed settings (env-configurable)
utils/         id generation, logging
```

### Data model

* **Entities** (`Channel`, `Video`, `Comment`) hold stable identity and
  slow-changing metadata.
* **Observations** (`ChannelObservation`, `VideoObservation`,
  `CommentObservation`) hold time-varying statistics, one row per collection
  run.
* **RecommendationObservation** stores *observed* relationships
  (source video → recommended video) for future network analysis.
* **CollectionRun / CollectionError** record what ran, what succeeded and what
  failed - failures are never silently dropped.

Every entity and observation preserves the raw source payload (`raw_json`).

## Configuration

Typed settings in `SocialScienceResearch/config/settings.py`, all
environment-configurable:

| Variable | Purpose |
| --- | --- |
| `SOCIAL_DATA_DIR` | directory for the Excel workbook |
| `SOCIAL_DATASET_NAME` | workbook filename (default `dataset.xlsx`) |
| `SOCIAL_MAX_ROWS_PER_SHEET` | sheet split threshold for large datasets |
| `SOCIAL_SAMPLING_SEED` | default RNG seed for reproducible sampling |
| `SOCIAL_TOP_N` | default top-N for list endpoints |
| `SOCIAL_API_*` | FastAPI layer settings (reserved) |

## CLI usage

```bash
python -m SocialScienceResearch collect channel https://www.youtube.com/@channel
python -m SocialScienceResearch collect video  https://www.youtube.com/watch?v=VIDEO_ID
python -m SocialScienceResearch collect recommendations https://www.youtube.com/watch?v=VIDEO_ID
python -m SocialScienceResearch runs list
python -m SocialScienceResearch runs errors <run_id>
python -m SocialScienceResearch analytics channel <channel_id>
python -m SocialScienceResearch analytics video <video_id>
python -m SocialScienceResearch sample videos <channel_id> --strategy top_views --size 10
python -m SocialScienceResearch sample comments <video_id> --strategy random --size 10
```

All data is written to the configured Excel workbook.

## Sampling

Sampling is **reproducible and transparent**: every call records the strategy,
size/percent, seed, strata and date range in `criteria_json`.

Strategies: `top_views`, `bottom_views`, `top_likes`, `bottom_likes`,
`top_engagement`, `top_comments`, `top_comment_rate`, `top_like_rate`,
`longest`, `shortest`, `random`, `stratified` (by year/month/weekday),
`latest`, `earliest`, `date_range`.

Entities whose ranking metric is unavailable are ranked last and reported via
`missing_metric_count` - never assigned a fabricated value. Comment sampling
supports only comment-meaningful strategies; requesting a video-only strategy
raises an explicit `UnsupportedSamplingError`.

## Analytics

* `channel_overview` - latest channel statistics with availability flags.
* `top_videos` - top/bottom videos by views, likes or comments.
* `video_engagement` - engagement/like/comment rates.
* `comment_like_percentiles` - P75/P90/P95/P99 like-count bands.
* `comment_velocity` - comment publication timeline per day/hour.

Every value carries a `DataAvailability`: `available`, `missing`, or
`unsupported` (e.g. division by zero views). Nothing is estimated or inferred.

## Recommendation network analysis

Observed recommendation edges are loaded into a `networkx.DiGraph`
(`RecommendationGraphService`):

* `summary` - node/edge counts, most-recommended videos (in-degree), most
  active sources (out-degree) and PageRank leaders.
* `video_context` - ego-network for one video: who recommends it and whom it
  recommends, with per-edge run attribution.
* Network slices can be restricted to a single `run_id` for temporal analysis.

## HTTP API (FastAPI)

```bash
uvicorn SocialScienceResearch.api:create_app --factory
```

All endpoints live under the configured prefix (default
`/api/v1/social-science`):

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/collect/channel` | run a channel collection |
| POST | `/collect/video` | run a video collection |
| POST | `/collect/recommendations` | observe recommendation edges |
| POST | `/collect` | submit a spec-driven collection (async job) |
| GET | `/jobs`, `/jobs/{id}`, `/jobs/{id}/cancel`, `/jobs/{id}/result` | async job lifecycle |
| GET | `/runs`, `/runs/{id}`, `/runs/{id}/errors` | provenance |
| GET | `/channels/{id}/overview` | latest channel stats |
| GET | `/channels/{id}/videos` | corpus with `VideoFilter` query params |
| GET | `/channels/{id}/videos/top` | top videos by engagement metric |
| POST | `/channels/{id}/videos/sample` | reproducible video sampling |
| POST | `/videos/{id}/comments/sample` | reproducible comment sampling |
| GET | `/videos/{id}`, `/videos/{id}/engagement` | video metadata / engagement |
| GET | `/videos/{id}/observations`, `/videos/{id}/raw` | per-run observations / raw payload |
| GET | `/videos/{id}/comments`, `.../percentiles`, `.../velocity`, `.../threads` | comment analytics |
| GET | `/videos/{id}/recommendations` | observed edges for a video |
| GET | `/network/recommendations/summary` | network-wide metrics |
| GET | `/network/recommendations/{id}` | ego-network for a video |
| GET | `/coverage`, `/dataset/summary` | dataset completeness / quality |


Interactive docs at `/docs`.

## Known library limitations

* `yt-dlp` cannot reliably provide video recommendations. The recommendation
  workflow records an explicit `recommendation_unsupported` error instead of
  fabricating edges or silently treating the result as zero.
* Statistics are captured *as observed*; historical values are only available
  after repeated runs.

## Testing

```bash
python -m pytest SocialScienceResearch/tests -q
```

All tests are offline: the acquisition provider is a deterministic in-memory
fake and persistence uses a temporary workbook.
