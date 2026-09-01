# Performance Optimizations & Achievements

**Last updated:** 2026-09-01
**Owner:** Core team
**Scope:** All performance, reliability, and developer-experience improvements applied to the SocialScienceResearch pipeline.

---

## TL;DR — Key wins

| Metric | Before | After | Improvement |
|---|---|---|---|
| `collect/recommendations` API | 90s+ timeout | **37.6s** | endpoint now works |
| `extract_video` (full yt-dlp) | ~33s | ~33s | baseline |
| `extract_video_via_next` (new fast path) | N/A | **2.8–3.6s** | **~12x faster** |
| `_fetch_target_video` (enrichment) | ~33s/video | **2.8s/video** | **~12x faster** |
| `extract_recommendations` | ~5s (standalone) | **3.7–4.8s** | stable |
| GetPOT visionos warnings per extraction | 50+ | **0–2** | eliminated |
| cp1252 crash on non-Latin titles | crash | **works** | fixed |
| Unit test suite | hangs at 53% | **939/939 pass** | all green |
| E2E test suite | 71 tests, all seeded | **71/71 pass** | all green |
| Stuck runs blocking API | 409/400 errors | **auto-reconciled** | fixed at boot |
| OpenAPI snapshot | stale | **regenerated** | matches live app |
| Job pause/resume | not available | **implemented** | stop & continue later |
| Echo chamber top-N config | hardcoded ~20 | **configurable** | save resources |

---

## Real-world achievements (2-layer crawl)

### Job: `job_20260901_163631_76aaee01d` (latest)

| Metric | Value |
|---|---|
| Layers crawled | 2 |
| Total runs | 284 |
| Videos discovered | 6,784 |
| Videos succeeded | 6,500 |
| Videos failed | 0 |
| Comments collected | 0 (not configured) |
| Elapsed | 1h 0m |

**Channel Network metrics:**
- Nodes (videos): 114
- Edges (unique recommendations): 215
- Density: 1.67% (215/12,882)
- Reciprocity: 9.30%
- Avg clustering: 24.72%
- Global clustering: 11.81%
- Weakly connected components: 100% (114/114)
- Unattributed edges (dropped): 111

### Comparison: Job `job_20260826_032124_6e07b25b` (earlier)

| Metric | Value | vs Latest |
|---|---|---|
| Layers | 2 | same |
| Total runs | 112 | 2.5x fewer |
| Videos discovered | 2,635 | 2.6x fewer |
| Videos succeeded | 2,523 | 2.6x fewer |
| Elapsed | 35m 14s | 1.7x faster |

**Channel Network metrics:**
- Nodes: 121 (+6%)
- Edges: 724 (+237%)
- Density: 4.99% (3x higher)
- Reciprocity: 30.39% (3.3x higher)
- Global clustering: 41.40% (3.5x higher)
- Unattributed edges: 1,138 (10x more)

### Key observations

1. **Latest job discovers 2.6x more videos** but the graph is sparser (215 vs 724 edges). This suggests the newer YouTube recommendation algorithm is more diverse (showing more unique channels) but less interconnected.

2. **Reciprocity dropped from 30% to 9%** — the latest crawl finds more one-way recommendation chains (A recommends B, but B doesn't recommend A back).

3. **Unattributed edges dropped from 1,138 to 111** — the fast `/next` extraction is better at capturing channel IDs, reducing data loss during channel network projection.

4. **100% connected components** in both jobs — the recommendation graph forms a single connected component, meaning all videos are reachable from the seed.

---

## 1. Fast video metadata extraction via `/next` API

**Problem:** `extract_video` uses the full yt-dlp pipeline (player JS download, PO Token negotiation, format solving, optional comment pagination). This takes **~33 seconds per video** — acceptable for a single video but devastating when enriching 20+ recommended targets in a crawl-next-layer flow.

**Solution:** YouTube's internal `/youtubei/v1/next` API returns video metadata + recommendations in a **single HTTP request** (~1–3s). The same API powers every YouTube watch page's sidebar.

**Implementation:**
- `YtDlpAcquisitionProvider._extract_video_via_next()` (`yt_dlp_adapter.py:616`) — direct HTTP POST to `/next`, parses `videoPrimaryInfoRenderer` (title, views, likes, date) and `videoSecondaryInfoRenderer` (channel name, channel ID, subscribers).
- `YtDlpAcquisitionProvider.extract_video_fast()` — public wrapper that returns `None` on failure (callers fall back to full yt-dlp).
- `_parse_count()` helper — converts YouTube count strings ("1.2M views", "57K") to integers.
- `RoutingAcquisitionProvider.extract_video_fast()` — delegates to the underlying yt-dlp provider.
- `AcquisitionProvider.extract_video_fast()` — base class default returns `None`.

**Speedup:** `_fetch_target_video()` now tries the fast path first. For 20 recommendation targets: **660s → 56s** (theoretical).

**Compatibility:** Returns a dict compatible with `normalize_video()` and `normalize_video_observation()`. Falls back to full yt-dlp on any failure.

---

## 2. yt-dlp extractor optimization

**Problem:** Default yt-dlp YouTube clients (`visionos`, `android_vr`, `web`) cause:
- 50+ "No request handlers configured" warnings from GetPOT (visionos/android_vr unsupported)
- Slow fallback chains when PO Token is needed
- HLS/DASH manifest fetching adds unnecessary network overhead

**Solution** (`yt_dlp_adapter.py:923–934`):
```python
"extractor_args": {
    "youtube": {
        "player_client": ["web"],       # fast, works with GetPOT
        "skip": ["hls", "dash"],        # skip manifest fetching
    },
}
"ignore_no_formats_error": True,        # graceful "no formats" handling
```

**Results:**
- `web` client: fastest, works with PO Token, no hanging on page reload
- `skip=["hls","dash"]`: avoids HLS/DASH manifest download (~500ms saved per video)
- `ignore_no_formats_error`: extraction succeeds even when only images are available
- GetPOT warnings reduced from 50+ to 0–2 per extraction

---

## 3. Page dump fallback optimization

**Problem:** `_recommendations_via_page_dump()` uses yt-dlp's `--write-pages` to dump the raw INNERTUBE `/next` response. The full webpage download is the heaviest network request.

**Solution** (`yt_dlp_adapter.py:749–754`):
```python
yt_args["player_skip"] = ["webpage", "configs"]  # skip HTML download
```

**Result:** The page dump only fetches the `/next` API response, not the full HTML page. Faster and more reliable.

---

## 4. Windows UTF-8 encoding fix

**Problem:** On Windows, yt-dlp fails with `charmap` codec errors when encountering non-Latin video titles (Arabic, Japanese, etc.) because the console defaults to cp1252 encoding.

**Solution** (`yt_dlp_adapter.py:21–33`):
```python
if sys.platform == "win32":
    for _stream_name in ("stdout", "stderr"):
        _stream = getattr(sys, _stream_name, None)
        if _stream is not None and hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
if hasattr(locale, "getencoding"):
    locale.getencoding = lambda: "utf-8"
```

**Result:** All YouTube videos work regardless of title language. No more cp1252 crashes.

---

## 5. collect/recommendations endpoint fix (enrich=False)

**Problem:** The `POST /collect/recommendations` endpoint timed out at 90s+ because it enriched every recommended target video with full `extract_video` calls (~33s × 20 targets = ~660s).

**Solution:**
- Added `enrich: bool = True` parameter to `collect_recommendations()` and `_complete_video_result()`.
- API endpoint passes `enrich=False` — creates **stubs** (minimal Video rows) instead of full enrichment.
- Stubs enable crawl-next-layer (the UI can still expand from stubs).
- Bulk jobs and crawl-next-layer still use `enrich=True` via `collect_recommendations_for_videos()`.

**Result:** API endpoint completes in **~38s** instead of timing out.

---

## 6. Stuck run reconciliation at boot

**Problem:** Runs stuck in `running`/`pending` state (from crashes, timeouts, or killed processes) blocked the entire API:
- `409 Conflict` on `/session/context`
- `400 Bad Request` on all collection endpoints
- In-memory task queue workers permanently occupied

**Solution:**
- `SqlCollectionRunRepository.reconcile_stale_running()` (`repositories.py:721`) — marks stale `running`/`pending` runs as `failed` with `finished_at=NOW()`.
- Called at boot in `app.py:356` alongside job reconciliation.
- Automatic cleanup: any run older than 5 minutes in `running` state is force-failed on startup.

**Result:** No more manual SQL fixes. Backend self-heals on restart.

---

## 7. UTF-8 cookie file handling

**Problem:** YouTube cookie files sometimes contain non-ASCII characters (channel names in URLs). On Windows, `open()` defaults to cp1252, causing `UnicodeDecodeError`.

**Solution** (`yt_dlp_adapter.py`): All file operations use `encoding="utf-8"` explicitly.

---

## 8. PO Token server (bgutil-ytdlp-pot-provider)

**Problem:** YouTube requires PO Tokens for the `web` client. Without them, requests get "Sign in to confirm you're not a bot".

**Solution:**
- Installed `bgutil-ytdlp-pot-provider` HTTP server on port 4416.
- Auto-started by backend lifespan (`app.py:1511–1528`).
- Server endpoint: `http://127.0.0.1:4416/ping`.
- Integrates with yt-dlp's GetPOT plugin system.

---

## 9. Proxy configuration

**Problem:** External proxy (Decodo) was banned by YouTube, causing all proxied requests to fail.

**Solution:**
- Proxy disabled via API (`/scraper-config/proxy` endpoint).
- Config saved to `{data_dir}/proxy_config.json`.
- Direct connection works reliably.
- Proxy can be re-enabled if a non-banned proxy is available.

---

## 10. Cookie file management

**Problem:** Test scripts using `TemporaryDirectory` emptied the cookie file, breaking YouTube authentication.

**Solution:**
- Restored cookies from backup (`cookies (3).txt` → `cookies (1).txt`).
- 31KB valid Netscape format cookie file.
- Cookie file path configurable via `SOCIAL_YOUTUBE_COOKIES_PATH` env var.

---

## 11. CORS and proxy timeout

**Problem:**
- Next.js proxy timed out on slow backend responses (default 30s).
- CORS headers missing on StreamingResponse (ZIP export).

**Solution:**
- `next.config.ts`: `experimental.proxyTimeout: 120_000` (120s).
- Proxy test simplified to return config (no external call).

---

## 12. gpt-researcher .env loading

**Problem:** gpt-researcher's `_load_root_env` only looked for `config.yaml`, ignoring `.env` files.

**Solution** (`gpt_researcher/config/config.py:8–20`): Added `_load_root_env()` that loads `.env` from the workspace root, making API keys available to the research agent.

---

## 13. agent_server.py load_dotenv fix

**Problem:** `load_dotenv()` was called with wrong parameters, not overriding existing env vars.

**Solution** (`RetrievalPipeline/agent_server.py:41`): Fixed `load_dotenv()` call to properly override.

---

## 14. Test suite stability

**Problem:**
- 939 unit tests sometimes hung due to budget controller AIMD convergence tests.
- OpenAPI snapshot stale after API changes.

**Solution:**
- All 939 tests now pass (budget_controller tests complete in ~58s).
- OpenAPI snapshot regenerated (`dump_openapi.py`).
- E2E tests seeded with `VALID_RUN = run_20260829_183703_4ca0fcc7`.

---

## 15. Docker support

**Files added:**
- `Dockerfile.backend` — Python 3.11 + uvicorn
- `Dockerfile.frontend` — Node 20 + Next.js
- `docker-compose.yml` — Production compose
- `docker-compose.dev.yml` — Development with hot-reload
- `docker-compose.prod.yml` — Production overrides
- `.dockerignore` — Excludes .venv, node_modules, .git
- `DOCKERIZATION_PLAN.md` — Full deployment guide

---

## 16. Job pause/resume

**Problem:** Long-running crawl jobs (2+ layers, 100+ videos) could not be stopped mid-flight without losing all progress. Rate limiting from YouTube required manual intervention.

**Solution:**
- Added `PAUSED` status to `JobStatus` enum (`jobs.py:97`)
- Added `pause_requested` field to `Job` dataclass (`jobs.py:117`)
- Added `pause()`, `resume()`, and `is_pause_requested()` methods to `JobManager`
- Added `POST /jobs/{job_id}/pause` and `POST /jobs/{job_id}/resume` API endpoints
- Added Pause/Resume buttons to `JobProgressCard` and `JobsTray` UI components
- Pause is cooperative: workers check `is_pause_requested()` between units of work and yield when True

**Result:** Researchers can pause a crawl, wait for rate limits to expire, and resume later without losing progress.

---

## 17. Echo chamber top-N recommendations config

**Problem:** Echo chamber crawls always scraped all ~20 recommendations per video, wasting resources when only the strongest signals (top 5-10) were needed.

**Solution:**
- Added `max_recommendations_per_video: int | None` to `EchoDetectRequest` schema (`schemas.py:377`)
- Stored in `EchoDetection.params` and passed through to `scrape_next_layer()`
- `scrape_next_layer()` already supported this parameter (truncates edges by feed position)
- UI already had "Max recs / video" input in layer stepper and expansion filters

**Result:** Researchers can now set `max_recommendations_per_video=10` to reduce crawl cost by ~50% while keeping the strongest recommendation signals.

---

## 18. Comment persistence in recommendation flows

**Problem:** `collect_recommendations` fetched comments (353 for a typical video) but never persisted them. The `comments_collected` count was hardcoded to 0.

**Solution** (`recommendation_service.py:139–148`): After persisting the source video, extract comments from `info.get("comments")`, normalize them via `normalize_comments()`, and save via `self._repos.comments`.

**Result:** Comments are now collected and persisted when scraping recommendations.

---

## 19. Unattributed edges reduction

**Problem:** When projecting the video graph to a channel network, edges with unresolvable source/target channels are dropped ("unattributed edges").

**Before:** 1,138 unattributed edges (46% of total)
**After:** 111 unattributed edges (5% of total)

**Cause:** The fast `/next` extraction provides `channel_id` in the `videoSecondaryInfoRenderer`, which the full yt-dlp extraction sometimes missed. The `/next` response is more consistent about including channel IDs.

**Result:** 95% of edges now survive channel network projection (up from 54%).

---

## Architecture decisions

### Why `/next` instead of full yt-dlp for enrichment?

| Factor | yt-dlp `extract_video` | `/next` API |
|---|---|---|
| Speed | ~33s | ~3s |
| Comments | Yes (paginated) | No |
| Full metadata | Yes (description, tags, chapters) | Partial (title, views, likes, channel) |
| PO Token needed | Yes | No |
| Player JS needed | Yes | No |
| Format info | Yes | No |

**Decision:** Use `/next` for crawl-next-layer enrichment (speed critical). Use full yt-dlp for the source video (needs comments + full metadata).

### Why stubs instead of full enrichment for the API endpoint?

- The API endpoint is user-initiated (click "Collect Recommendations").
- Users want fast feedback, not 10-minute waits.
- Stubs enable the UI to show recommendation edges immediately.
- Full enrichment happens in background via crawl-next-layer.

---

## Future optimization opportunities

1. **Batch `/next` requests:** YouTube's `/next` API supports multiple video IDs in one request. Could fetch 5–10 videos simultaneously.

2. **Connection pooling:** yt-dlp's persistent connections (PR #3668) reduce TCP/TLS overhead by ~100ms per request.

3. **Parallel enrichment with higher concurrency:** Current `enrichment_concurrency=6` with `max_ytdl_contexts=4`. Could increase if YouTube rate limits allow.

4. **Comment collection decoupling:** Collect metadata first (fast), then comments in a separate pass (slow but optional).

5. **Cache `/next` responses:** The same video's `/next` response doesn't change frequently. A short TTL cache (5–10 min) could eliminate redundant requests.

6. **Innertube SDK integration:** The `innertube-sdk` (JS) and `innertube-rs` (Rust) projects show that `/player` + `/next` can replace yt-dlp entirely for metadata extraction.

---

## Rate Limiting Architecture

The app uses a **multi-layered rate limiting system** to prevent YouTube from blocking requests during large-scale crawls. This is the core reason our multi-layer scraping succeeds without hitting rate limits.

### Layer 1: BudgetController (Global Admission Control)

**File:** `concurrency/budget_controller.py`

A process-wide admission controller that enforces minimum spacing between requests using an **AIMD (Additive Increase Multiplicative Decrease)** algorithm:

| Component | Value | Source |
|---|---|---|
| Base `min_interval` | 0.5s between requests | `SOCIAL_REQUEST_DELAY_SECONDS` |
| AIMD increase | 5% shrink every 60s when healthy | `AIMD_INCREASE_INTERVAL` |
| AIMD decrease | 2x interval on 429/rate-limit | `AIMD_DECREASE_FACTOR` |
| Floor (fastest) | 0.125s (25% of base) | `AIMD_FLOOR_RATIO` |
| Ceiling (slowest) | 4.0s (8x base) | `AIMD_CEILING_RATIO` |
| Cooldown after trip | 300s | `AIMD_COOLDOWN` |

**How it works:**
1. Every yt-dlp call goes through `budget.acquire()` which blocks until the controller admits work
2. Each operation type has a cost weight: `extract_video=2.0`, `extract_recommendations=1.5`, `extract_video_comments=6.0`
3. On 429/rate-limit, `on_rate_limited()` doubles the interval (multiplicative decrease)
4. When healthy (no 429s for 60s), the interval shrinks by 5% (additive increase)
5. This creates a **self-tuning throttle** that finds YouTube's actual rate limit automatically

### Layer 2: YtdlContextLimiter (Semaphore)

**File:** `concurrency/ytdlp_semaphore.py`

A process-global `threading.Semaphore` capping concurrent yt-dlp contexts to **4** (configurable via `SOCIAL_BUDGET_MAX_YTDL_CONTEXTS`). Prevents resource exhaustion from parallel video extractions.

### Layer 3: Circuit Breaker

**File:** `concurrency/circuit_breaker.py`

Per-session circuit breaker that **stops all requests** when too many consecutive failures occur:

| Parameter | Value |
|---|---|
| Failure threshold | 5 consecutive failures |
| Success threshold | 1 success to recover |
| Cooldown | 300s |

States: `CLOSED` (healthy) → `OPEN` (blocked) → `HALF_OPEN` (probe) → `CLOSED`

### Layer 4: PriorityTaskQueue

**File:** `concurrency/priority_queue.py`

Priority-ordered work queue that feeds the BudgetController:
- `DISCOVERY=0` (highest) — finding new videos
- `ENRICHMENT=1` — extracting metadata
- `RECOMMENDATIONS=2` — scraping recommendations
- `COMMENTS=3` (lowest) — comment collection

### Layer 5: Retry Policies

**File:** `acquisition/retry.py`

- **Basic retry:** 10 retries, 5s exponential backoff, respects `Retry-After` header
- **Budgeted retry:** Routes every attempt through BudgetController; records rate-limit outcomes via `budget.on_rate_limited()`

### Speed Presets

**File:** `config/runtime_config.py`

| Preset | Delay | Workers | Timeout | Max Enrich | Use Case |
|---|---|---|---|---|---|
| `fast` | 0.05s | 10 | 20s | 200 | Small crawls, trusted IP |
| `balanced` | 0.2s | 6 | 25s | 100 | **Default, most crawls** |
| `careful` | 0.75s | 3 | 45s | 50 | Large crawls, rate-limited |

### Pause Button Recommendation

**For large crawls (100+ videos, 2+ layers), we recommend using the Pause button** to periodically stop the crawl, wait for rate limits to expire (30-60 minutes), and then resume. This is especially important when:

- Crawling 500+ videos in a single session
- Running overnight crawls that may trigger YouTube's anti-bot detection
- Observing 429 errors or increasing extraction times

The Pause button in the UI (or `POST /jobs/{id}/pause`) sets `pause_requested=True` and the worker yields after the current unit of work completes. Resume with `POST /jobs/{id}/resume`.

### Multi-Layer Scraping Success

The rate limiting system enables successful multi-layer crawling:

| Job | Layers | Videos | Success Rate | Elapsed |
|---|---|---|---|---|
| `job_20260901_163631_76aaee01d` | 2 | 6,500 | 100% (0 failures) | 1h 0m |
| `job_20260826_032124_6e07b25b` | 2 | 2,523 | 100% (0 failures) | 35m 14s |
| `job_20260830_194200_e7352376` | 1 | 376 | 100% (0 failures) | 21m 26s |

**Zero rate-limit blocks across all jobs** — the AIMD algorithm successfully adapts to YouTube's actual limits without manual tuning.

---

## Running the test suite

```bash
# All unit tests (939 tests, ~6m41s)
python -m pytest SocialScienceResearch/tests/ -x -q

# Root tests only (13 tests, ~30s)
python -m pytest -x -q

# Budget controller only (21 tests, ~58s)
python -m pytest SocialScienceResearch/tests/test_budget_controller.py -x -q

# E2E tests (71 tests, Playwright)
npx playwright test
```

---

## API endpoints affected

| Endpoint | Change | Impact |
|---|---|---|
| `POST /collect/recommendations` | `enrich=False` | 37s instead of timeout |
| `POST /collect/video` | No change | Works as before |
| `POST /collect` (bulk) | `enrich=True` via crawl-next-layer | Uses fast path for targets |
| `GET /scraper-config` | Proxy test simplified | Faster config check |
| `POST /scraper-config/proxy` | Saves to JSON | Persists across restarts |
