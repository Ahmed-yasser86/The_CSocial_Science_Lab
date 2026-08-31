# API Reference

> Generated from the committed OpenAPI contract `SocialScienceResearch/api/openapi.json` - the single source of truth, guarded by `SocialScienceResearch/tests/test_openapi_snapshot.py`. There are **160 paths** in one FastAPI app: the CSS workbench under the base prefix `/api/v1/social-science`, plus the agent routes and `/health`.

Interactive docs: `GET /docs` on a running backend. To regenerate the snapshot from the live app run `python SocialScienceResearch/scripts/dump_openapi.py`; never hand-edit it (see `SocialScienceResearch/CONTRACT.md`).

## Endpoint groups

### agent &nbsp; _Graph-RAG intelligence agent + health (B)_

| Method | Path |
|---|---|
| GET | `/api/agent/ai-config` |
| GET,POST | `/api/agent/env` |
| GET | `/api/agent/logs` |
| POST | `/api/agent/run` |
| POST | `/api/agent/run/{run_id}/cancel` |
| GET | `/api/agent/runs` |
| GET | `/api/agent/runs/{run_id}` |
| GET | `/api/agent/runs/{run_id}/reports/{report_key}` |
| POST | `/copilotkit/agent/research_agent/connect` |
| POST | `/copilotkit/agent/research_agent/stop/{threadId}` |
| GET | `/copilotkit/info` |

### budget &nbsp; _Collection budget / rate-limit control_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/budget/circuit-breakers` |
| POST | `/api/v1/social-science/budget/circuit-breakers/reset` |
| GET | `/api/v1/social-science/budget/events` |
| GET | `/api/v1/social-science/budget/queue` |
| GET | `/api/v1/social-science/budget/state` |

### channels &nbsp; _Channel corpus & channel-level analytics_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/channels` |
| GET | `/api/v1/social-science/channels/{channel_id}` |
| GET | `/api/v1/social-science/channels/{channel_id}/history` |
| GET | `/api/v1/social-science/channels/{channel_id}/overview` |
| GET | `/api/v1/social-science/channels/{channel_id}/videos` |
| GET | `/api/v1/social-science/channels/{channel_id}/videos/count` |
| POST | `/api/v1/social-science/channels/{channel_id}/videos/sample` |
| GET | `/api/v1/social-science/channels/{channel_id}/videos/top` |

### collect &nbsp; _Collection jobs_

| Method | Path |
|---|---|
| POST | `/api/v1/social-science/collect` |
| POST | `/api/v1/social-science/collect/channel` |
| POST | `/api/v1/social-science/collect/recommendations` |
| POST | `/api/v1/social-science/collect/video` |

### comparison &nbsp; _Compare videos / runs / channels / periods_

| Method | Path |
|---|---|
| POST | `/api/v1/social-science/comparison/channels` |
| POST | `/api/v1/social-science/comparison/cohorts` |
| POST | `/api/v1/social-science/comparison/jobs` |
| POST | `/api/v1/social-science/comparison/periods` |
| POST | `/api/v1/social-science/comparison/runs` |
| POST | `/api/v1/social-science/comparison/videos` |

### coverage &nbsp; _Dataset availability coverage_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/coverage` |

### dataset &nbsp; _Dataset summary_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/dataset/summary` |

### datasets &nbsp; _Research datasets (create, export, combine)_

| Method | Path |
|---|---|
| GET,POST | `/api/v1/social-science/datasets` |
| POST | `/api/v1/social-science/datasets/combine` |
| DELETE,GET,PATCH | `/api/v1/social-science/datasets/{dataset_id}` |
| GET | `/api/v1/social-science/datasets/{dataset_id}/export` |
| GET | `/api/v1/social-science/datasets/{dataset_id}/members` |
| GET | `/api/v1/social-science/datasets/{dataset_id}/quality` |

### echo-chamber &nbsp; _Echo-chamber detection_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/echo-chamber` |
| POST | `/api/v1/social-science/echo-chamber/detect` |
| GET | `/api/v1/social-science/echo-chamber/{detection_id}` |
| GET | `/api/v1/social-science/echo-chamber/{detection_id}/audience` |
| POST | `/api/v1/social-science/echo-chamber/{detection_id}/continue` |
| GET | `/api/v1/social-science/echo-chamber/{detection_id}/lens` |
| POST | `/api/v1/social-science/echo-chamber/{detection_id}/stop` |
| GET | `/api/v1/social-science/echo-chamber/{detection_id}/structure` |

### explore &nbsp; _Explorer / provenance records_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/explore/provenance/{entity}/{entity_id}` |
| GET | `/api/v1/social-science/explore/records` |
| GET | `/api/v1/social-science/explore/records/{entity}/{entity_id}/raw` |

### export &nbsp; _Dataset export_

| Method | Path |
|---|---|
| POST | `/api/v1/social-science/export` |

### jobs &nbsp; _Jobs lifecycle, cancel, stream, tags_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/jobs` |
| POST | `/api/v1/social-science/jobs/kill-stuck` |
| GET | `/api/v1/social-science/jobs/{job_id}` |
| POST | `/api/v1/social-science/jobs/{job_id}/cancel` |
| GET | `/api/v1/social-science/jobs/{job_id}/result` |
| GET | `/api/v1/social-science/jobs/{job_id}/stream` |
| PATCH | `/api/v1/social-science/jobs/{job_id}/tags` |

### network &nbsp; _Network science (graph, metrics, centralities, roles, communities, commenters, test-difference)_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/network/centralities` |
| GET | `/api/v1/social-science/network/channels` |
| GET | `/api/v1/social-science/network/commenters/communities` |
| GET | `/api/v1/social-science/network/commenters/community-insights` |
| GET | `/api/v1/social-science/network/commenters/export` |
| GET | `/api/v1/social-science/network/commenters/graph` |
| GET | `/api/v1/social-science/network/commenters/metrics` |
| GET | `/api/v1/social-science/network/commenters/overlap` |
| GET | `/api/v1/social-science/network/commenters/roles` |
| GET | `/api/v1/social-science/network/commenters/{author_key}/profile` |
| GET | `/api/v1/social-science/network/commenters/{handle}/detail` |
| GET | `/api/v1/social-science/network/communities` |
| GET | `/api/v1/social-science/network/community-insights` |
| GET,POST | `/api/v1/social-science/network/content-homophily` |
| GET | `/api/v1/social-science/network/content-homophily/export-communities` |
| GET | `/api/v1/social-science/network/content-homophily/{analysis_id}` |
| GET | `/api/v1/social-science/network/content-homophily/{analysis_id}/export-sample` |
| GET | `/api/v1/social-science/network/edges` |
| GET | `/api/v1/social-science/network/expansion` |
| GET | `/api/v1/social-science/network/expansion/options` |
| POST | `/api/v1/social-science/network/expansion/scrape-all` |
| POST | `/api/v1/social-science/network/expansion/scrape-video` |
| GET | `/api/v1/social-science/network/expansion/{action_id}` |
| GET | `/api/v1/social-science/network/expansion/{action_id}/graph` |
| GET | `/api/v1/social-science/network/expansion/{action_id}/stats` |
| GET | `/api/v1/social-science/network/export` |
| POST | `/api/v1/social-science/network/export-to-project` |
| GET | `/api/v1/social-science/network/graph` |
| POST | `/api/v1/social-science/network/layer` |
| POST | `/api/v1/social-science/network/layer/scrape` |
| GET | `/api/v1/social-science/network/layer/{layer_run_id}` |
| GET | `/api/v1/social-science/network/layer/{layer_run_id}/frontier` |
| GET | `/api/v1/social-science/network/layer/{layer_run_id}/graph` |
| GET | `/api/v1/social-science/network/layer/{layer_run_id}/relations` |
| GET | `/api/v1/social-science/network/layers` |
| GET | `/api/v1/social-science/network/matrices` |
| POST | `/api/v1/social-science/network/merge` |
| GET | `/api/v1/social-science/network/merge/options` |
| GET | `/api/v1/social-science/network/metrics` |
| GET | `/api/v1/social-science/network/recommendations/summary` |
| GET | `/api/v1/social-science/network/recommendations/{video_id}` |
| GET | `/api/v1/social-science/network/roles` |
| GET | `/api/v1/social-science/network/sampling-feasibility` |
| POST | `/api/v1/social-science/network/scrape/channel` |
| POST | `/api/v1/social-science/network/scrape/run` |
| POST | `/api/v1/social-science/network/scrape/video` |
| GET | `/api/v1/social-science/network/temporal` |
| POST | `/api/v1/social-science/network/test-difference` |
| GET | `/api/v1/social-science/network/weights/options` |

### projects &nbsp; _Projects & project items (lineage)_

| Method | Path |
|---|---|
| GET,POST | `/api/v1/social-science/projects` |
| DELETE,GET,PATCH | `/api/v1/social-science/projects/{project_id}` |
| GET,POST | `/api/v1/social-science/projects/{project_id}/items` |
| DELETE,GET,PATCH | `/api/v1/social-science/projects/{project_id}/items/{item_id}` |
| DELETE,POST | `/api/v1/social-science/projects/{project_id}/items/{item_id}/datasets` |
| DELETE,POST | `/api/v1/social-science/projects/{project_id}/items/{item_id}/samples` |

### research &nbsp; _Query builder (variables, operators, preview, resolve)_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/research/operators` |
| POST | `/api/v1/social-science/research/query/preview` |
| POST | `/api/v1/social-science/research/query/resolve` |
| GET | `/api/v1/social-science/research/variables` |

### runs &nbsp; _Collection runs, deltas, errors, sub-runs, videos_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/runs` |
| GET | `/api/v1/social-science/runs/delta` |
| GET,PATCH | `/api/v1/social-science/runs/{run_id}` |
| GET | `/api/v1/social-science/runs/{run_id}/deltas` |
| GET | `/api/v1/social-science/runs/{run_id}/errors` |
| GET | `/api/v1/social-science/runs/{run_id}/sub-runs` |
| GET | `/api/v1/social-science/runs/{run_id}/videos` |

### samples &nbsp; _Immutable samples, compare, members_

| Method | Path |
|---|---|
| GET,POST | `/api/v1/social-science/samples` |
| POST | `/api/v1/social-science/samples/compare` |
| DELETE,GET | `/api/v1/social-science/samples/{sample_id}` |
| GET | `/api/v1/social-science/samples/{sample_id}/members` |

### sampling &nbsp; _Advanced sampling_

| Method | Path |
|---|---|
| POST | `/api/v1/social-science/sampling/advanced` |

### scrape &nbsp; _Network scrape (video / run / channel)_

| Method | Path |
|---|---|
| POST | `/api/v1/social-science/scrape/recommendations` |

### scraper &nbsp; _Scraper config & proxy_

| Method | Path |
|---|---|
| GET,PUT | `/api/v1/social-science/scraper/config` |
| POST | `/api/v1/social-science/scraper/config/preset` |
| GET,PUT | `/api/v1/social-science/scraper/proxy` |
| POST | `/api/v1/social-science/scraper/proxy/test` |

### search &nbsp; _Search_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/search` |

### session &nbsp; _Session context_

| Method | Path |
|---|---|
| GET,PUT | `/api/v1/social-science/session/context` |

### system &nbsp; _System folders_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/system/folders` |

### videos &nbsp; _Video corpus & comment analytics_

| Method | Path |
|---|---|
| GET | `/api/v1/social-science/videos` |
| GET | `/api/v1/social-science/videos/{video_id}` |
| GET | `/api/v1/social-science/videos/{video_id}/comments` |
| GET | `/api/v1/social-science/videos/{video_id}/comments/analytics/participation` |
| GET | `/api/v1/social-science/videos/{video_id}/comments/analytics/replies` |
| GET | `/api/v1/social-science/videos/{video_id}/comments/analytics/velocity` |
| GET | `/api/v1/social-science/videos/{video_id}/comments/percentiles` |
| POST | `/api/v1/social-science/videos/{video_id}/comments/sample` |
| GET | `/api/v1/social-science/videos/{video_id}/comments/stats` |
| GET | `/api/v1/social-science/videos/{video_id}/comments/threads` |
| GET | `/api/v1/social-science/videos/{video_id}/comments/velocity` |
| GET | `/api/v1/social-science/videos/{video_id}/comments/{comment_id}/tree` |
| GET | `/api/v1/social-science/videos/{video_id}/engagement` |
| GET | `/api/v1/social-science/videos/{video_id}/history` |
| GET | `/api/v1/social-science/videos/{video_id}/observations` |
| GET | `/api/v1/social-science/videos/{video_id}/raw` |
| GET | `/api/v1/social-science/videos/{video_id}/recommendations` |

### workspaces &nbsp; _Workspaces (DB isolation)_

| Method | Path |
|---|---|
| GET,POST | `/api/v1/social-science/workspaces` |
| GET,PATCH | `/api/v1/social-science/workspaces/{workspace_id}` |

### health &nbsp; _Liveness_

| Method | Path |
|---|---|
| GET | `/health` |
