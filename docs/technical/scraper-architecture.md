# Scraper Architecture: Rate Limiting, Session Management & the Five Phases

> Audience: researchers running large YouTube crawls and developers extending the
> acquisition layer.
>
> This document describes how the Social Science Research scrapers stay *polite*,
> *observable*, and *resilient* — the global rate limiter, the retry/backoff
> policy, the priority queue, the circuit breaker, and the proxy/cookie session
> management. All file references point at the `SocialScienceResearch` package.

---

## 1. Goals

1. **Globally rate-limit** every YouTube request from a single process, no matter
   how many jobs or services are running.
2. **Adapt** the rate to YouTube's actual behaviour (speed up when healthy, slow
   down on throttling) instead of using a blind fixed sleep.
3. **Prioritise** work (discovery before enrichment before recommendations before
   comments) so a stuck branch never starves the rest of the crawl.
4. **Isolate unhealthy sessions/proxies** behind a circuit breaker so one flagged
   identity doesn't take down the whole crawl.
5. **Observe everything** — every admission decision and rate-limit signal is an
   event that can be streamed to logs, an in-memory ring buffer, and a JSONL file.
6. **Route through a proxy with cookies** (Phase 6 / session management) so the
   operator's real IP is never the one YouTube sees, and the "Sign in to confirm
   you're not a bot" challenge can be cleared with account cookies.

---

## 2. Architecture at a glance

```
                       ┌──────────────────────────────────────────┐
  UI / API  ──────────▶│  collection / recommendation / echo services│
                       └───────────────┬──────────────────────────┘
                                       │ AcquisitionProvider
                                       ▼
                          RoutingAcquisitionProvider
                                       │ delegates
                                       ▼
                            YtDlpAcquisitionProvider
                 ┌──────────────────────┼────────────────────────┐
                 ▼                      ▼                        ▼
        PriorityTaskQueue        BudgetController           CircuitBreakerRegistry
        (orders + gates)        (pacing + AIMD)            (per-session health)
                 │                      │                        │
                 └──────────┬───────────┴───────────┬────────────┘
                           ▼                       ▼
                    retry_policy_budgeted      yt-dlp (YoutubeDL)
                    (tenacity + budget)              │
                                                    ▼
                                         YouTube  ◀── proxy + cookies
```

All four concurrency primitives live under `SocialScienceResearch/concurrency/`:
`budget_controller.py`, `priority_queue.py`, `circuit_breaker.py`, and
`ytdlp_semaphore.py` (a hard cap on simultaneously-open `YoutubeDL` contexts).

---

## 3. The five phases

### Phase 1 — Global Budget Controller (GBC) + semaphore + observability
`SocialScienceResearch/concurrency/budget_controller.py`

Replaced the old per-service rate limiters with **one** controller shared by every
service and job in the process. `acquire()` blocks until the controller admits one
unit of work, charges it, and returns the waited time. A separate
`ytdlp_semaphore` caps how many `YoutubeDL` contexts exist at once
(`max_ytdl_contexts`, default 4) so the process never opens hundreds of sockets.

Every decision is emitted as a `BudgetEvent` to pluggable `EventSink`s:
`LoggingSink` (INFO, human-visible), `RingBufferSink` (last 2000 events, queryable
via the API), and `JsonlFileSink` (append-only audit log). This satisfies the
research requirement that per-event detail is surfaced in real time, never
aggregated away.

### Phase 2 — Budgeted retries (tenacity)
`SocialScienceResearch/acquisition/retry.py`

`retry_policy_budgeted()` wraps each extraction so **every** attempt — first and
retries — is charged to the GBC (`budget.acquire`) and so rate-limit outcomes are
reported (`budget.on_rate_limited`). Only `NetworkError`/`RateLimitError` are
retried. Backoff is exponential with jitter, capped at `max_wait`, and **honours
the server's `Retry-After` exactly** when a `RateLimitError` carries one.

### Phase 3 — Weighted cost
`DEFAULT_OPERATION_COSTS` in `budget_controller.py`

Not all operations cost the same number of YouTube requests. The controller
charges a **weighted cost** so a heavy operation reserves proportionally more of
the shared timeline (`next_slot += min_interval * cost`):

| Operation                | Weight | Why |
|--------------------------|--------|-----|
| `extract_channel`        | 4.0    | multiple playlist tabs |
| `extract_video`          | 2.0    | metadata only |
| `extract_video_comments` | 6.0    | full comment pagination |
| `extract_transcript`     | 1.5    | caption track + one fetch |
| `extract_recommendations`| 1.5    | sidebar / innertube fallback |
| `retry`                  | 1.0    | ~one attempt's worth |

Weights are constructor-overridable per deployment.

### Phase 4 — AIMD adaptive rate
Same module. The GBC starts at the operator-selected `min_interval` and learns the
highest safe rate:

- **Additive increase** — while healthy (no recent 429), shrink the interval by
  `AIMD_INCREASE_FACTOR` (5%) every `AIMD_INCREASE_INTERVAL` (60 s), down to a
  floor of `baseline * AIMD_FLOOR_RATIO` (4× faster than baseline).
- **Multiplicative decrease** — on the **first** 429 within a cooldown window,
  double the interval (halve the budget) and block increases for
  `AIMD_COOLDOWN` (300 s). Subsequent 429s in that window are still observed but
  don't re-halve.
- Bounds: `AIMD_FLOOR_RATIO = 0.25`, `AIMD_CEILING_RATIO = 8.0`.

This is classic TCP-style congestion control applied to scraping: probe faster
when safe, back off hard when throttled.

### Phase 5 — Dashboard + Circuit Breaker + Priority Queue + stall hotfix
`priority_queue.py`, `circuit_breaker.py`, and the dashboard endpoints.

- **Priority Queue** — all scraping flows through one queue ordered
  `DISCOVERY(0) > ENRICHMENT(1) > RECOMMENDATIONS(2) > COMMENTS(3)`. Workers pull
  the highest-priority ready task, charge it to the GBC, then run it. Queue state
  (queued/running/waiting by type) is observable.
- **Circuit Breaker** — a *separate* concern from the budget: it tracks the
  *health* of an individual session/proxy identity. On repeated 429s it moves
  `CLOSED → OPEN` (blocked for `cooldown`, default 300 s), then `OPEN →
  HALF_OPEN` (one probe allowed), and back to `CLOSED` on success. Thresholds:
  `failure_threshold = 5`, `success_threshold = 1`, `cooldown = 300`. The
  breaker only trips when the GBC is **already saturated** at its ceiling
  (`min_interval >= ceiling * 0.9`) — a transient throttle during the normal
  backoff ramp must not freeze the session.
- **Stall hotfix** — when the breaker is `OPEN`, the provider calls
  `cb.wait_until_allowed(key)` *cooperatively* (bounded wait) instead of raising.
  This prevents the earlier failure mode where a single throttle event raised a
  `RateLimitError` that tenacity retried forever, freezing the whole session for
  the cooldown window. The breaker is now a *self-healing bounded backoff*.

> **Known failure mode (layer-1 collapse).** If every scrape in a layer stalls
> past its per-task budget (e.g. the operator's IP is blocked and yt-dlp hangs),
> `collect_recommendations_for_videos` returns `[]`, the layer records zero runs
> and zero edges, and the crawl stops with `unsupported_stop`. This is an
> *environment* failure (IP block), not a code bug — it is exactly what the proxy
> in Phase 6 is designed to avoid. The stall is bounded: each task is cancelled
> after its timeout rather than hanging the process.

---

## 4. Session & proxy management (Phase 6)

All proxy/cookie state lives in `RuntimeScraperConfig`
(`config/runtime_config.py`) and is surfaced through the **Proxy IP** tab in the
UI and the `/scraper/proxy` API.

### 4.1 Proxy (Decodo / rotating residential)

`RuntimeScraperConfig` proxy fields: `proxy_enabled`, `proxy_host`, `proxy_port`,
`proxy_username`, `proxy_password`, `proxy_verify`. `proxy_url()` builds
`http://user:pass@host:port`. The adapter's `YtDlpAcquisitionProvider.
_resolve_proxy()` returns the runtime proxy URL (runtime config wins over the
frozen settings value) and `_base_opts()` passes it to yt-dlp as `opts["proxy"]`.

- **Sticky sessions** — `proxy_session` is appended to the username as
  `-session-<id>`, so the egress IP stays constant across requests (avoids
  YouTube IP hopping, which itself triggers challenges).
- **Persistence** — proxy fields are written to `<data_dir>/proxy_config.json`
  (git-ignored) so credentials survive restarts and are never logged verbatim.
  `save_proxy_fields()` / `load_proxy_fields()` handle this; `init_proxy_persistence()`
  points them at the workspace data dir at startup.
- **Live updates** — `PUT /scraper/proxy` mutates the *same* config object the
  provider holds (`set_runtime_config`), so changes apply to the next request
  with no restart.

### 4.2 YouTube cookies (clearing the bot challenge)

Even a clean proxy IP receives YouTube's *"Sign in to confirm you're not a bot"*
challenge unless authenticated cookies are supplied. Two modes:

| `youtube_cookies_mode` | yt-dlp option            | Notes |
|------------------------|--------------------------|-------|
| `none`                 | —                        | default |
| `browser`              | `cookiesfrombrowser`     | reads the cookie store of a browser **on the backend machine** (e.g. `chrome`). Works when backend + browser are the same machine (local run). |
| `file`                 | `cookiefile`             | loads a Netscape `cookies.txt`. Portable — use this for any remote/deployed backend. |

> `cookiesfrombrowser` reads the browser's on-disk cookie database; it does **not**
> talk to the user's client browser over the network. On a remote backend it reads
> that machine's browser (which has no YouTube login), so use the `file` method
> there: export `cookies.txt` from a logged-in account and point `youtube_cookies_path` at it.

Cookies are **account-specific**. Use a throwaway account, never a primary, and
keep the file local — the app reads it from disk; nothing is sent to a third
party (only Decodo and YouTube see the traffic).

### 4.3 Test endpoint

`POST /scraper/proxy/test` validates the proxy by requesting YouTube's public
`oembed` endpoint **through the proxy** (the real target, not Decodo's own
meta-endpoint). It also tries a few IP-echo services to report the egress IP, but
a missing `egress_ip` is *not* a failure — many IP-echo hosts are blocked by
residential proxies while YouTube works fine. The YouTube 200 is the signal that
matters.

---

## 5. Tuning reference

### Speed presets (`PRESETS` in `runtime_config.py`)
| Preset    | delay | concurrency | socket | max targets |
|-----------|-------|-------------|--------|-------------|
| `fast`    | 0.05  | 10          | 20     | 200         |
| `balanced`| 0.2   | 6           | 25     | 100         |
| `careful` | 0.75  | 3           | 45     | 50          |

### Endpoints (all under `/api/v1/social-science`)
| Method | Path | Purpose |
|--------|------|---------|
| GET/PUT | `/scraper/config` | read / update runtime scraper settings (delay, concurrency, retries, backoff, max targets) |
| GET/PUT | `/scraper/proxy` | read / update proxy + cookie config |
| POST    | `/scraper/proxy/test` | verify proxy reaches YouTube |
| GET     | `/budget/state` | current `min_interval`, AIMD floor/ceiling, admits, rate-limited count, cooldown remaining, circuit-breaker states |
| GET     | `/budget/events` | recent `BudgetEvent`s (ring buffer) for a run |

### AIMD constants (override via `BudgetController(...)`)
`AIMD_INCREASE_INTERVAL=60`, `AIMD_INCREASE_FACTOR=0.05`,
`AIMD_DECREASE_FACTOR=2.0`, `AIMD_COOLDOWN=300`, `AIMD_FLOOR_RATIO=0.25`,
`AIMD_CEILING_RATIO=8.0`.

---

## 6. Developer notes

- **Source map**
  - `concurrency/budget_controller.py` — GBC, weighted cost, AIMD, event sinks.
  - `concurrency/priority_queue.py` — priority ordering + budget gating.
  - `concurrency/circuit_breaker.py` — per-session health.
  - `concurrency/ytdlp_semaphore.py` — cap on concurrent `YoutubeDL` contexts.
  - `acquisition/retry.py` — tenacity policies that route through the GBC.
  - `acquisition/yt_dlp_adapter.py` — applies proxy + cookies in `_base_opts()`,
    resolves the session key in `_session_key()`, cooperatively waits on an open
    breaker in `_guarded()`.
  - `config/runtime_config.py` — `RuntimeScraperConfig` (proxy + cookies + presets).
  - `api/routers/scraper_config.py` — `/scraper/config` and `/scraper/proxy` APIs.
  - `ui/src/app/proxy/page.tsx` — the Proxy IP setup tab.
- **Extending to multiple proxies** — the circuit-breaker registry is already
  keyed by session/proxy identity (the "Phase 6" slot). Add a proxy pool by
  varying the `key` in `_session_key()` (e.g. hash the proxy URL) so each proxy
  gets its own breaker; no other changes required.
- **Observability first** — when something looks stuck, read `/budget/events`
  and `/budget/state` before changing code. A `rate_limit` event followed by an
  `aimd_multiplicative_decrease` and a `circuit_breaker` transition tells you
  exactly which session YouTube throttled and when.
- **Tests** — `tests/test_proxy_config.py` (proxy URL builder, adapter
  resolution, test endpoint) and `tests/test_layer1_stall_simulation.py`
  (reproduces the layer-1 collapse with a stall-friendly `concurrent.futures.wait`)
  document the two hardest-to-observe behaviours.
