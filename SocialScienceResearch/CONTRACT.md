# API Contract & Drift Gate

The OpenAPI snapshot at `api/openapi.json` is the **source of truth** for the
frontend/backend contract. It is checked in and guarded by tests so that API
renames, removed endpoints, or orphaned UI wrappers fail CI instead of hiding.

## Regeneration

Change the backend API, then regenerate both artifacts and commit them together:

```bash
# 1. refresh the checked-in snapshot from the live FastAPI app
python SocialScienceResearch/scripts/dump_openapi.py

# 2. regenerate the TypeScript contract types for the UI
cd SocialScienceResearch/ui && npm run generate:api
```

## The drift rule

- `SocialScienceResearch/tests/test_openapi_snapshot.py` — regenerates the live
  app's OpenAPI and fails if it differs from `api/openapi.json`; also asserts
  every operation declares responses and the `Paginated` envelope + research
  endpoints exist.
- `ui/src/lib/contract.test.ts` (Vitest) — asserts every path the frontend calls
  exists in the snapshot, and flags **orphaned** exported API functions/hooks in
  `ui/src/services/`. The current *known/allowed* orphans are:
  - `api.ts`: `getVideoObservations`, `getVideoRaw`, `getCommentThreads`, `getChannelTopVideos`
  - `queries.ts`: `useCollect`, `useDatasetSummary`

The orphan scanner is `ui/scripts/find-orphans.mjs` (run standalone:
`node scripts/find-orphans.mjs`).

## Rules

1. Every endpoint must declare a pydantic `response_model`.
2. List endpoints use the cursor-pagination envelope (`items`, `next_cursor`,
   `has_more`, `total`).
3. After any API change, re-run both regeneration commands above.
4. New UI wrappers that replace orphaned ones may remove entries from the known
   orphan list (update `contract.test.ts` accordingly).