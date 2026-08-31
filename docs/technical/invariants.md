# Invariants — Cross-Cutting Consistency Rules

> These are the invariants that keep the platform honest: a single exact source of truth per concern, so a change in one place never silently drifts from its consumers. Each "source of truth" is a committed file you can open.

## 1. API contract (the master invariant)

- **Source of truth:** `SocialScienceResearch/api/openapi.json`, generated from the live FastAPI app by `SocialScienceResearch/scripts/dump_openapi.py`.
- **Guard:** `SocialScienceResearch/tests/test_openapi_snapshot.py` fails CI when the live app drifts from the snapshot; also asserts every operation declares `responses` and the `Paginated` envelope exists (`SocialScienceResearch/CONTRACT.md`).
- **Rule:** After any backend API change, regenerate the snapshot and commit it together with the code. Docs never invent a path.

## 2. Single graph engine

- **Source:** `services/network_analytics_service.py` (`graph()`, `metrics()`, `centralities()`, `channel_graph()`, `merge_networks()`, `export_network()`) on top of `services/recommendation_graph_service.py:build_graph()`.
- **Invariant:** `metrics()`, `graph()`, `centralities()`, `export_network()`, `channel_graph()` all derive from the same node/edge set. Communities use Louvain `seed=42` over the displayed slice.
- **Rule:** Change a filter (channel scope, layer de-dup, seed) in all consumers together. E2E `tests/e2e/export_parity.spec.ts` guards export parity.

## 3. Provenance + availability

- **Source:** `domain/enums.py:137` (`available | missing | unsupported`) and the `*Observation` models in `domain/models.py` (each preserves `raw_json`).
- **Rule:** Never fabricate. `recommendation_unsupported` (0 edges) is a real outcome — surface an empty state, don't invent edges.

## 4. Deterministic research

- **Source:** `config/settings.py:129` (`SOCIAL_SAMPLING_SEED=42`) and `services/network_analytics_service.py` (Louvain `seed=42`, seeded `run_resampling_test`).
- **Rule:** Reproducible samples, communities, and p-values by construction.

## 5. Dataset / project scoping (scope = intersection)

- **Source:** `domain/dataset_models.py`, `domain/project_models.py`, `services/dataset_service.py` (`CreateDatasetInput{run_ids, channel_ids, video_ids, criteria, project_id}`).
- **Rule:** Multiple scopes combine as **AND**. Keep `project_id` scoping consistent across list/query + active workspace context.

## 6. Overlap set-ops (shared)

- **Source:** `services/commenter_overlap_service.py` (Jaccard, overlap coefficient, reach, bridge) and sampling overlap in `services/sampling_service.py`.
- **Rule:** Reuse these set-op helpers rather than re-implementing graph diff in new features.

## 7. Export serializers (one format, one place)

- **Source:** `export_network()` dispatcher + `_serialize_video_graph()` / `_serialize_channel_graph()` / `_aggregated_edges()` in `services/network_analytics_service.py`.
- **Rule:** Add a format in ONE place; don't maintain a second serializer.
- **Exposed at:** `GET /network/export`, `POST /network/export-to-project`.

## 8. Confidential data minimization

- **Source:** `config/settings.py` (comment ceiling `10000`, `SOCIAL_COLLECT_TRANSCRIPTS=False`, request delay `0.5s`) and `services/commenter_overlap_service.py` (`author_id`-first identity).
- **Rule:** Ceilings are recorded on the run config; transcripts are opt-in; an id is never fabricated.

## 9. E2E coverage

- **Source:** `playwright.config.ts` + `tests/e2e/*.spec.ts` (19 suites).
- **Rule:** UX/navigation changes extend an E2E spec so the Lab/network flows stay verified.

---

Back: [Technical Reference](../for-developers/index.md)
