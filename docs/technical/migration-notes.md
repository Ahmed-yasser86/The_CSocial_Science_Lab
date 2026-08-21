# Migration Notes

Notes for anyone upgrading an existing workbook or codebase through the Phase 2
waves. All migrations are backward-compatible additive work; no schema was
broken.

## `observed_at` on observations (Phase A)

- `ChannelObservation` / `VideoObservation` / `CommentObservation` gained a
  single canonical `observed_at`. A legacy duplicate on `TranscriptRecord`
  (`domain/models.py`) was removed. New rows always write `observed_at`; old
  workbooks read with a sensible default.

## Workbooks created by an older version

Open the workbook with the current code once before writing: the Excel
provider lazily creates missing sheets (`authors`, `samples`, `datasets`,
`projects`, `sample_members`, `dataset_members`) on first use. No manual schema
step is required.

## Repository additions

| Wave | Added |
|---|---|
| Phase A | `ObservationRepository`/batch `get_latest_*_observations` |
| Phase B | `SampleRepository` (+ `sample_members`), `ExplorerService` |
| Phase C | network services (no new sheet) |
| Phase D | `DatasetRepository` (+ `dataset_members`), `ProjectRepository` (`projects`) |
| Phase E (E1) | `AuthorRepository` (`authors`) |

## Behaviour changes to know about

- **Cursor pagination (D3):** all list endpoints moved to cursor envelopes. A
  client passing the old `page`/`limit` params gets a `400`; use `cursor` +
  `page_size`.
- **Response models (ADR-0005):** every endpoint declares a pydantic
  `response_model`; unknown fields are dropped instead of forwarded.
- **`blank_row` fix (B7):** clearing a cell now sets `.value = None`
  (openpyxl `cell(value=None)` does not clear the cell).
- **Comment ceiling (D2):** collection now honors `max_comments_per_video`
  per request; completeness is documented, never silent.
- **Explorer default page size (E5):** `/explore/records` defaults to
  `page_size=25` (was 50). The upper bound remains 500.
- **Search (E2):** `GET /channels` and `GET /videos` accept an optional `q`
  like-search in addition to the new `GET /search`.

## Contract gate

`api/openapi.json` is the source of truth. After any endpoint change, run:

```bash
python -m SocialScienceResearch.scripts.dump_openapi
python -m pytest SocialScienceResearch/tests/test_openapi_snapshot.py
```

The UI types regenerate from the snapshot:
`cd ui && npm run generate:api`.
