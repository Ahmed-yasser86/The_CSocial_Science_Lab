# Sampling Methods

Sampling is **reproducible and transparent**: every call records the strategy,
size/percent, seed, strata and date range in `criteria_json`, and persisted
samples store the population definition + hash at creation (ADR-0011).

## Strategies

| Strategy | Meaning |
|---|---|
| `top_views` / `bottom_views` | Highest / lowest latest view counts |
| `top_likes` / `bottom_likes` | Highest / lowest latest like counts |
| `top_engagement` | Highest engagement metric |
| `top_comments` / `top_comment_rate` / `top_like_rate` | Engagement variants |
| `longest` / `shortest` | By duration |
| `random` | Seeded uniform draw |
| `stratified` | Seeded, stratified by year/month/weekday |
| `latest` / `earliest` | By upload/publication time |
| `date_range` | Population restricted to a date window |

Entities whose ranking metric is unavailable are ranked last and reported via
`missing_metric_count` — never assigned a fabricated value. Comment sampling
accepts only comment-meaningful strategies; a video-only strategy raises an
explicit `UnsupportedSamplingError`.

## Reproducibility

- The default seed is `SOCIAL_SAMPLING_SEED` (42); a per-call `seed` overrides
  it. The seeded RNG is used for both `random` and `stratified` (shuffling
  within strata).
- The exact criteria (strategy, size/percent, seed, strata, date range) are
  recorded on the sample; a persisted sample's membership can be re-derived
  from its recorded definition.

## Percentile / quantile semantics (ADR-0007)

Rank-based operators are computed against the **current filtered population** —
the same population the query preview reports:

- `percentile(p)` — value threshold at the p-th percentile (linear
  interpolation between ordered values).
- `percentile_rank(x)` — a record's position as a percentage within the
  population.
- `quartile(q)` — equal-sized groups by value.
- `quantile(q)` — equal-sized groups by count.

The evaluation population and `n` are returned with every result so the
interpretation is unambiguous.

## Missing-metric policy

Percentiles, rates and strata are computed over available values only. When a
metric is unavailable for some units, they are ranked last and counted in
`missing_metric_count`; the availability flag distinguishes
`available` / `missing` / `unsupported` at every step.
