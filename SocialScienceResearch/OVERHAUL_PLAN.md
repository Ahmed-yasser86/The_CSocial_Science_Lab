# YouTube Scraper & Network Visualizer Overhaul Plan

## 1. Overview & Goals
Transform the Network Visualizer and Scraping Pipeline into a researcher-friendly system with:
- Metadata-rich node rendering (titles, thumbnails, metrics).
- Dual-axis filtering (Channel/Run).
- Interactive click-to-scrape functionality.
- Automated persistence into Datasets.

---

## 2. Tasks Breakdown

### 2.1 Network Page UI & API Refactor
#### **Metadata Resolution**
- **Objective**: Replace raw YouTube IDs with full metadata (title, channel, thumbnail, views/likes/duration).
- **Files to Modify**:
  - `ui/src/components/features/network-graph.tsx` (node rendering logic).
  - `ui/src/services/networkFull.ts` (data fetching).
  - `api/routers/network_ext.py` (API endpoint for metadata).
  - `services/network_analytics_service.py` (data processing).
- **Steps**:
  1. Extend `network_ext.py` to fetch metadata from `yt_dlp_adapter.py` via `EdgeRow`.
  2. Update `network_analytics_service.py` to include metadata (e.g., `title`, `channel_id`) in `EdgeRow`.
  3. Modify `network-graph.tsx` to render metadata (e.g., tooltips, labels).
  4. Update `networkFull.ts` to fetch enriched metadata from `network_ext.py`.

#### **Dual-Axis Filtering**
- **Objective**: Enable filtering by **Channel** (show all videos + recommendation trees) and **Run** (scrape run ID).
- **Files to Modify**:
  - `ui/src/components/features/network-graph.tsx` (filter UI/logic).
  - `api/routers/network_ext.py` (filter endpoints).
  - `services/network_analytics_service.py` (filter logic).
- **Steps**:
  1. Add filter dropdowns in `network-graph.tsx` for `channel_id` and `run_id`.
  2. Extend `network_ext.py` to support `channel_id` and `run_id` query params in `/network/edges`.
  3. Update `network_analytics_service.py` to filter edges by `channel_id` and `run_id`.
  4. Update `networkFull.ts` to pass filters to the API.

#### **Run Taxonomy & Differentiation**
- **Objective**: Visually distinguish **Single Video Scrape Runs** vs. **Channel Scrape Runs**.
- **Files to Modify**:
  - `ui/src/components/features/network-graph.tsx` (node styling).
  - `services/network_analytics_service.py` (data processing).
- **Steps**:
  1. Add a `run_type` field to `EdgeRow` in `network_analytics_service.py`.
  2. Style nodes in `network-graph.tsx` based on `run_type` (e.g., color-coding).

---

### 2.2 Scraping Engine Upgrades
#### **Channel + Recommendation Scraping**
- **Objective**: For every video on a channel, scrape its recommendations ($1 \rightarrow N$ tree).
- **Files to Modify**:
  - `services/scraping_service.py` (scraping logic).
  - `services/recommendation_graph_service.py` (graph generation).
  - `acquisition/yt_dlp_adapter.py` (scraping implementation).
- **Steps**:
  1. Extend `yt_dlp_adapter.py` to recursively scrape recommendations for channel videos.
  2. Update `recommendation_graph_service.py` to build trees from scraped data.
  3. Persist recommendation edges via `dataset_service.py`.

#### **Interactive Click-to-Scrape**
- **Objective**: Trigger scrapes by clicking nodes/runs in the Network tab.
- **Files to Modify**:
  - `ui/src/components/features/network-graph.tsx` (click handlers).
  - `api/routers/scraping_ext.py` (scrape endpoints).
  - `services/dataset_service.py` (persistence).
- **Steps**:
  1. Add click handlers in `network-graph.tsx` to call scrape endpoints.
  2. Extend `scraping_ext.py` to accept `video_id`/`run_id` as input.
  3. Persist results via `dataset_service.py` (using `create_dataset` or `create_from_project`).

---

### 2.3 Dataset Integration
#### **Automated Persistence**
- **Objective**: Auto-persist scrape outputs into Datasets.
- **Files to Modify**:
  - `services/dataset_service.py` (dataset creation).
  - `api/routers/datasets.py` (export endpoints).
  - `services/recommendation_graph_service.py` (persistence logic).
- **Key Methods**:
  - `DatasetService.create_dataset()`: Snapshots entire entity populations (e.g., videos, channels).
  - `DatasetService.create_from_project()`: Snapshots rows matching a project's research query.
  - `DatasetService.export()`: Exports datasets as CSV/JSON.
- **Steps**:
  1. Call `create_dataset` in `recommendation_graph_service.py` after scraping.
  2. Extend `datasets.py` to support streaming exports of scrape results.

---

### 2.4 Verification & Testing
#### **Historical Context Audit**
- **Objective**: Ensure no prior functionality is broken.
- **Files to Review**:
  - `tests/test_network_analytics_service.py`
  - `tests/test_recommendation_graph_service.py`
  - `tests/test_dataset_service.py`

#### **Playwright MCP Testing**
- **Objective**: Automate E2E verification of:
  1. Metadata rendering (titles, channels).
  2. Filtering (Channel/Run).
  3. Click-to-scrape persistence.
- **Files to Create**:
  - `tests/e2e/network_visualizer.spec.ts`
  - `tests/e2e/scraping_pipeline.spec.ts`

---

## 3. Execution Strategy
1. **Phase 1: Backend Refactor**
   - Extend API endpoints (`network_ext.py`, `scraping_ext.py`).
   - Upgrade scraping logic (`yt_dlp_adapter.py`, `recommendation_graph_service.py`).
   - Integrate Dataset persistence (`dataset_service.py`).

2. **Phase 2: Frontend Refactor**
   - Update `network-graph.tsx` for metadata rendering.
   - Add filtering UI/logic.
   - Implement click-to-scrape handlers.

3. **Phase 3: Testing**
   - Write Playwright tests for E2E validation.
   - Run tests and iterate on fixes.

---

## 4. Dependencies
- **Scraping Library**: `yt-dlp` (via `youtubeScraper.md`).
  - Key features: Metadata extraction, recommendation scraping.
  - Integration: Call `yt-dlp` via `yt_dlp_adapter.py`.

---

## 5. Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | Audit tests, incremental changes. |
| Performance bottlenecks | Lazy-load metadata, paginate API responses. |
| Scraping rate limits | Implement retries, exponential backoff. |