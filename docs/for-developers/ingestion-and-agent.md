# Ingestion & the Graph-RAG Agent

> The two systems besides the CSS workbench. **C. Ingestion** is a library that harvests and embeds web content; **B. Agent** is a LangGraph research agent served over HTTP and CopilotKit.

## C. Ingestion pipeline (`Ingestion_Pipline/`)

A **library** (no HTTP) that turns websites into Qdrant vector data.

### Flow

```
Tavily map / crawl / extract
   → ingestion/chunking.py      SplitText (tiktoken, clip100k)
   → ingestion/embedding_pipeline.py  ResilientEmbeddingPipeline
   → infra/vector_store.py      QdrantVectorStore (Cosine, prefer_grpc)
```

Main entry: `Ingestion_Pipline/ingestion_service.py:162 EmbedDocumentsToVectoreDb(urls, Collection_Name)`:

1. `ExtractAllBatches` (`:150`) — concurrent Tavily extraction,
2. `BuildDocuments` (`:154`) — wrap results as `Document(page_content, metadata={"source": url})`,
3. `SplitText` (`:166`) — chunk,
4. `createEmptyCollection` (`:167`) — Qdrant collection (vector size, `Distance.COSINE`),
5. `EmbedDocumentsInBatches` (`:168`) — embed & store via the resilient pipeline.

### Resilience & rate limiting

- `ResilientEmbeddingPipeline` (`ingestion/embedding_pipeline.py:39`): token-bucket based batching, a worker queue, retries with exponential backoff + jitter, and parses provider rate-limit headers.
- `TokenRateLimiter` (`infra/rate_limiter.py:18`) and `RequestRateLimiter` (`:185`).
- Retry policies (`infra/retry_policies.py`): `vector_dimension_retry` (3), `document_add_retry` (5, 1–60s), `url_extraction_retry` (5).
- Provider-agnostic embeddings (`infra/embeddings.py:136`): `EMBEDDING` env as `provider:model` — supports `cohere:`, `openai:`/`openai_compatible:`, and defaults to Google `gemini-embedding-2-preview` with a shared RPM guard (free-tier 429 protection).

### Direct use

```python
from Ingestion_Pipline.ingestion_service import EmbedDocumentsToVectoreDb
# await EmbedDocumentsToVectoreDb(urls=["https://..."], Collection_Name="my_collection")
```

## B. Graph-RAG Intelligence Agent (`RetrievalPipeline/`)

### The state machine

`RetrievalPipeline/Graph/intelligence_graph.py:506` compiles a LangGraph `StateGraph` (`GraphState` in `StateGraph.py:87`) with **5 nodes** (`:561-565`):

| Node | Function | `add_node` line |
|---|---|---|
| `identity_research` | `make_identity_research` (`Nodes/IdentityResearchNode/`) | `:561` |
| `profile_summarization` | `summarize_profile`/`summarize_briefings` (`ProfileSummarizationNode/`) | `:562` |
| `subject_intelligence` | `run_subject_intelligence` (`SubjectIntelligenceNode/`) | `:563` |
| `audience_intelligence` | `run_audience_intelligence` (`AudienceIntelligenceNode/`) | `:564` |
| `ecosystem_intelligence` | `run_ecosystem_intelligence` (`EcosystemIntelligenceNode/`) | `:565` |

- Entry: `set_entry_point(IDENTITY_RESEARCH)` (`:568`); edge to `profile_summarization` (`:569`).
- Conditional `report_router` (`:92`) routes to whichever report (`subject | audience | ecosystem`) is still missing, or `END`.
- Compiled with a `MemorySaver` checkpointer (`:587-588`) → thread-id resume.

### The HTTP server (`agent_server.py`)

`RetrievalPipeline/agent_server.py:461` defines `agent_router`, conditionally mounted inside the main FastAPI app (`app.py:1819`):

```
GET  /health                                  liveness
GET  /copilotkit/info                         AGUI manifest
POST /copilotkit/agent/research_agent/connect CopilotKit runtime
POST /api/agent/run                           run the pipeline
GET  /api/agent/run/{run_id}/cancel           stop
GET  /api/agent/runs                          recent runs (SQLite)
GET  /api/agent/runs/{run_id}/reports/{report_key}
GET  /api/agent/logs?run_id                   SSE backend activity
GET  /api/agent/ai-config                     provider config
GET  /api/agent/env  / POST                   env inspection
```

Observability: `RetrievalPipeline/loghub.py` + `_stage_wrap` in `intelligence_graph.py:519` emit `stage_start`/`stage_done` events to the UI.

### Sample inputs

`RetrievalPipeline/samples/` ships `briefing_1.txt`, `briefing_2.txt`, and `sample_profile.txt` used to bootstrap profile summarization.

### MCP

The repo includes an `.mcp.json` (MCP server config). The agent's research wired through the LangGraph nodes uses MCP tools for retrieval — see `RetrievalPipeline/Graph/Nodes/web_search.py` and `retrive.py`.

---

- [Architecture](architecture.md) · [API Reference](api-reference.md) · [Configuration](configuration.md)
