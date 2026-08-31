# Troubleshooting

> Practical fixes for the situations most likely to trip you up. Each item points to the committed code that governs the behavior, so you can verify the fix.

## 1. "The graph is empty / no recommendations"

**Cause:** yt-dlp returned no recommendation edges (`recommendation_unsupported`). The system records this honestly instead of fabricating edges.

**Fix:**
- Confirm the run succeeded: `GET /runs/{run_id}` and `GET /runs/{run_id}/errors`.
- Check coverage: `GET /coverage`.
- Try a seed with a real crawling frontier. If the seed has no scaffoldable edge, the echo-chamber service reports `unsupported_stop` ("Seed has no crawlable frontier...") — a natural, honest stop (`echo_chamber_service.py:239-251`).

## 2. Comments were not collected

**Cause:** `SOCIAL_COLLECT_COMMENTS` was `False`, or the ceiling `SOCIAL_MAX_COMMENTS_PER_VIDEO` (`10000`) truncated pagination.

**Check:** `GET /videos/{video_id}/comments/stats` and the run's `config_json`. Comment-dependent signals (echo-chamber **S5**) are reported `unavailable` when comments weren't collected — that is expected, not a bug (`echo_chamber_service.py:682-705`).

## 3. Transcripts missing

**Cause:** transcript collection is **opt-in** by default (`SOCIAL_COLLECT_TRANSCRIPTS=False`). You must pass `collect_transcripts=True` on an explicit collection spec.

## 4. A network endpoint 400s on a "bad" projection / weight

**Cause:** the weight-spec or projection isn't valid.

**Fix:** validate the token against the grammar in `SocialScienceResearch/services/weight_spec.py` — form `edge_type:weight_mode[:param][:norm]`, e.g. `recommendation:observation_count:norm=min_max`. See `GET /network/weights/options`.

## 5. "hangs" / stuck long-running work

**Cause:** a job may be stuck after a crash.

**Fix:** `POST /jobs/kill-stuck` recovers it. Cancels are cooperative (honoured between work units). See `workspaces-and-jobs.md`.

## 6. The answer in the UI doesn't match the DB

- After an API change, regenerate the contract: `python SocialScienceResearch/scripts/dump_openapi.py` and commit `api/openapi.json` together. The snapshot test fails on drift (`tests/test_openapi_snapshot.py`, `CONTRACT.md`).
- If a network metric looks stale, note metrics are computed on demand from observed edges and are restricted to the selected run slice (`GET /network/temporal?runs=a,b` for per-run views).

## 7. The agent endpoints 404

**Cause:** the Graph-RAG graph failed to import, so the agent router is not mounted (the mount is guarded by a try/except at `app.py:1819`).

**Check:**
- LLM keys are set (`OPENAI_API_KEY`, `SMART_LLM`, etc.).
- The vendored `gpt-researcher` import succeeds (`pyproject.toml` pins it).
- `GET /health` and `/copilotkit/info` respond.

## 8. Documents not embedding / rate-limit errors

**Cause:** provider 429s or token-limit issues in ingestion.

**Fix:** the `ResilientEmbeddingPipeline` retries with backoff + jitter and parses rate-limit headers (`ingestion/embedding_pipeline.py:174`). Raise `GEMINI_EMBED_RPM` (default `90`) if free-tier throttled (`infra/embeddings.py:20`).

## 9. "workspace not found"

**Fix:** confirm the active workspace: `GET /workspaces` and `GET /workspaces/{id}`. The per-request middleware routes to the active workspace (`app.py:1565`); isolated DB-per-workspace means data is separate per workspace.

## 10. Want to see what actually failed?

`GET /runs/{run_id}/errors` lists collection errors; `GET /budget/events` and `GET /budget/circuit-breakers` show rate-limit and circuit-breaker activity.

---

- [Overview](index.md) · [Configuration](configuration.md) · [Workspaces & Jobs](workspaces-and-jobs.md)
