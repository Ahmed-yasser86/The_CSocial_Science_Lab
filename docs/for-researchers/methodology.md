# Methodology — Observed, Never Estimated

> The core scientific principle: **the system never fabricates or estimates data.** Whatever the provider did not return is recorded as missing or unsupported — never zeroed, never imputed silently.

## 1. Observations, not entity mutations

Time-varying statistics never live on the entity model; they live on per-run **`*Observation`** models (`SocialScienceResearch/domain/models.py:5-16`):

| Observation | Key time-varying fields |
|---|---|
| `ChannelObservation` | `subscriber_count`, `video_count`, `view_count` (`models.py:115`) |
| `VideoObservation` | `view_count`, `like_count`, `comment_count`, `favorite_count` (`models.py:164`) |
| `CommentObservation` | `like_count`, `reply_count`, `is_removed` (`models.py:204`) |
| `RecommendationObservation` | `source_video_id`, `recommended_video_id`, `position`, `status` (`models.py:219`) |

Every observation carries `collection_run_id` + `observed_at` + a **`raw_json`** copy of the sanitized provider payload. Analytics never write derived values back into source rows (`models.py:5-16`).

## 2. Explicit data availability

`SocialScienceResearch/domain/enums.py:137`:

```python
class DataAvailability(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"        # source did not provide it
    UNSUPPORTED = "unsupported"  # collection method cannot provide it at all
```

The docstring is explicit: *"Both are represented explicitly; nothing is fabricated or estimated."* A paper backed by this platform can state with confidence what was and wasn't observed.

## 3. Raw source preserved

`raw_json: dict[str, Any]` is stored on entities and observations so a reviewer can re-inspect what the provider actually returned for any row.

## 4. Failed / unsupported collection is surfaced, not hidden

- Scraper failures become `CollectionError` rows; a provider that returns no recommendations is recorded as `recommendation_unsupported` and surfaced in the UI as an empty state — the graph reflects what was observed, nothing more.

## 5. Determinism by design

Reproducibility is engineered in, not bolted on:

- Sampling seed: `SOCIAL_SAMPLING_SEED=42` (`config/settings.py:129,399`).
- Community detection: Louvain `seed=42` (`network_analytics_service.py`).
- Permutation tests: seeded, so the same comparison yields the same `p_value` (`services/network_analytics_service.py` `run_resampling_test`).

See [Reproducibility](reproducibility.md) for the full picture.

## 6. Known honest limits

- Statistics carry `population_size` + `n` + method so an estimate is never presented as a census.
- Sampling ranks missing values **last**, never fabricating them (`sampling_service.py:331-342`).
- Network slices are bounded by which runs actually observed the graph (`docs/research/network-metrics.md`).

---

Next: [Reproducibility](reproducibility.md).
