# Sampling

> 13 strategies, deterministic seeding, honest missing-value ranking, and persisted immutable samples. Implemented in `SocialScienceResearch/services/sampling_service.py`, `sample_service.py`, and `domain/enums.py`.

## Strategies

`SamplingStrategy` enum (`SocialScienceResearch/domain/enums.py:115-134`):

| Group | Strategies |
|---|---|
| Ranked (video) | `top_views`, `bottom_views`, `top_likes`, `bottom_likes`, `top_engagement`, `bottom_engagement`, `top_comments`, `top_comment_rate`, `top_like_rate`, `longest`, `shortest` |
| Randomized | `random` (video + comment) |
| Stratified | `stratified` (video + comment) |
| Time-based | `latest`, `earliest`, `date_range` (video + comment) |

Comment-allowed strategies are restricted to `{top_likes, top_replies, random, stratified, latest, earliest, date_range}` (`sampling_service.py:441-451`).

## Determinism

- Default seed `SOCIAL_SAMPLING_SEED=42` (`config/settings.py:129,399`).
- `_random()` seeds an independent `Random(spec.seed if spec.seed is not None else self._default_seed)` (`sampling_service.py:356-358`).
- `_stratified()` balances per-stratum with the same seeded RNG (`:388-409`).
- The resulting `seed` is stored on every `SamplingResult` and recorded in `criteria_json` (`:431`).

## Honest missing-value handling

`_rank()` sorts with **missing values ranked last, never fabricated** (`sampling_service.py:331-342`); `_cut()` applies size/percent/top_n after ranking (`:344-354`).

## Advanced / cross-channel sampling

`sample_advanced()` (`sampling_service.py:456`) supports multi-channel, multi-video, user-based sampling with a filter chain:

- video filters → `_apply_video_filters()` (`:800`)
- comment filters → `_apply_comment_filters()` (`:849`)
- author cross-unit overlap → `_apply_overlap()` (`:892`); author key = `author_id` with `author_name` fallback (`:888-890`).

```
POST /api/v1/social-science/sampling/advanced
```

## Feasibility planning

`feasibility()` (`sampling_service.py:229`) answers "how many units would each strategy actually yield before you commit" — avoiding impossible sampling requests.

```
GET /api/v1/social-science/network/sampling-feasibility
```

## Persisted, immutable samples

`SampleService.save()` persists a sample immutably with its full recipe — `strategy`, `seed`, `population_size`, `criteria_json`, and a hash; mutation is only ever a tombstone (ADR-0011) (`sample_service.py:47-65`).

```
GET  /api/v1/social-science/samples
GET  /api/v1/social-science/samples/{sample_id}
GET  /api/v1/social-science/samples/{sample_id}/members
DELETE /api/v1/social-science/samples/{sample_id}
```

## Comparing samples

`compare_samples()` reports overlap / union / Jaccard and diffs the criteria (`strategy`, `seed`, hash, `population_size`, `criteria_json`) (`sample_service.py:86-136`).

```
POST /api/v1/social-science/samples/compare
```

## Normalization (comparison context)

`Normalization` enum: `none | per_1k | z_score` (`services/comparison_service.py:52-57`).

---

Previous: [Echo Chamber](echo-chamber.md) · Next: [Ethics & Data Minimization](ethics.md)
