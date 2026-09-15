# Context-Aware Acquisition: Collection Context as Experimental Variable

> The same seed yields different recommendation networks under different user and network contexts. This document explains how the system controls that context — and why that control is a research capability, not an operational convenience.

**Code:** `SocialScienceResearch/acquisition/` · `SocialScienceResearch/config/settings.py` (`ScraperSettings`) · proxy/scraper-config API (`api/routers/scraper_config.py`) · persistence `proxy_config.json`

---

## 1. Why: recommendations are context-dependent

YouTube's recommendation system responds to *who is asking and from where*: authentication state, geographic network position, and browser fingerprint all plausibly shift what the platform surfaces. A blind, context-free scrape therefore captures exactly one slice of the recommendation environment and silently generalizes from it.

The collection infrastructure treats context as a **controlled variable**: researchers configure the identity and position under which observation happens, persist that configuration, and compare recommendation networks collected under different contexts. Anonymous vs authenticated, region A vs region B, Chrome vs Firefox — each becomes an observable, comparable recommendation environment.

---

## 2. Context dimensions

| Dimension | Options | Research value |
|---|---|---|
| **Authentication** | Anonymous (no cookies) · browser cookies · `cookies.txt` file | Compare logged-in vs anonymous recommendation pathways |
| **Network position** | Direct · proxy (rotating residential, e.g. Decodo) with sticky sessions | Compare recommendations across geographic locations |
| **Browser identity** | Chrome / Firefox / Safari via yt-dlp impersonation (`SOCIAL_IMPERSONATE`) | Control for fingerprint effects |
| **Speed profile** | Fast / Balanced / Careful presets | Balance collection speed vs rate-limit risk per experiment |

---

## 3. Operation

- All context is **runtime-configurable** via the `/scraper/proxy` API endpoint (or Proxy Setup UI) — no server restart.
- Configuration persists to disk (`proxy_config.json`) and survives restarts.
- Every observation records the context it was collected under (via `collection_run_id` → run provenance), so cross-context comparisons are traceable.

---

## 4. What this enables (and what it does not)

Enables: controlled comparative studies of recommendation environments; reproducing collection under fixed conditions for longitudinal work; auditing platform behavior across contexts.

Does not: identify *why* the platform responds differently (no access to the ranking model); observe any real user's experience (contexts are researcher-constructed, not user traces); guarantee the platform response is stable within a context (still a snapshot — see [Recommendation crawling](recommendation-crawling.md)).

---

## 5. Related documents

- [Recommendation crawling](recommendation-crawling.md) — the crawl this context parameterizes
- [Reproducibility](../for-researchers/reproducibility.md) — configuration persistence and provenance
- [Limitations](../for-researchers/limitations.md) — snapshot and generalizability caveats
- [Scraper architecture](../technical/scraper-architecture.md) — implementation (canonical for tuning details)
