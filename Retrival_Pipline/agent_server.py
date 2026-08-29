"""
Agent server for the Graph-RAG Research Agent.

Exposes:
  * POST /copilotkit            -> CopilotKit AGUI runtime wrapping the LangGraph
                                   intelligence pipeline (so the chat UI can drive it).
                                   Mounted only when the research graph imports successfully.
  * GET  /health                -> liveness
  * GET  /api/agent/logs?run_id -> Server-Sent-Events stream of backend activity
  * POST /api/agent/run         -> direct (no-LLM-needed) run of the pipeline
  * GET  /api/agent/runs        -> recent runs (best effort, from the SQLite store)

The research pipeline lives in Retrival_Pipline/Graph/intelligence_graph.py as a
LangGraph StateGraph compiled into `app`. We monkey-patch `app.ainvoke` / `app.astream`
so that every run (whether triggered by CopilotKit or by /api/agent/run) attaches a
ResearchLoggerCallbackHandler that emits structured, streamable events to the LogHub,
which the SSE endpoint relays to the UI. This upgrades the existing ad-hoc `print()`
markers into an "obvious", real-time log feed without editing the pipeline nodes.

NOTE: importing the full graph pulls in gpt-researcher and may fail in a minimal
environment. The server therefore imports the graph defensively: if it cannot be
imported, /health and the SSE scaffolding still work and /api/agent/run reports a
clear error instead of crashing the whole process.
"""

import os
import re
import sys
import uuid
import json
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Make the Graph package importable (it uses flat relative imports).
GRAPH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Graph")
if GRAPH_DIR not in sys.path:
    sys.path.insert(0, GRAPH_DIR)

from fastapi import FastAPI, Query, Request, HTTPException  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from sse_starlette.sse import EventSourceResponse  # noqa: E402
from langchain_core.callbacks import BaseCallbackHandler  # noqa: E402

# The project's real .env lives at the repository root, not in Retrival_Pipline.
# Load it explicitly so the runtime (and the in-app Env Setup UI) read/write the
# same file the user edits by hand.
ROOT_ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(ROOT_ENV):
    load_dotenv(dotenv_path=ROOT_ENV, override=False)
log = logging.getLogger("agent_server")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _name(serialized: Any) -> Optional[str]:
    if isinstance(serialized, dict):
        return serialized.get("name") or (
            "/".join(serialized["id"]) if serialized.get("id") else None
        )
    return None


def _model_name(serialized: Any) -> Optional[str]:
    if isinstance(serialized, dict):
        return serialized.get("name") or serialized.get("kwargs", {}).get("model")
    return None


def _token_usage(response: Any) -> Optional[Dict[str, int]]:
    try:
        out = getattr(response, "llm_output", None) or {}
        usage = out.get("token_usage") or out.get("usage") or {}
        return {
            "prompt": int(usage.get("prompt_tokens", 0) or 0),
            "completion": int(usage.get("completion_tokens", 0) or 0),
            "total": int(usage.get("total_tokens", 0) or 0),
        }
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Log hub: in-process pub/sub with replay buffer per run
# --------------------------------------------------------------------------- #
class LogHub:
    def __init__(self) -> None:
        self._runs: Dict[str, Dict[str, Any]] = {}
        # Global fan-out: a single stream of every event, used when the UI
        # does not (yet) know a specific run_id.
        self._global_events: List[Dict[str, Any]] = []
        self._global_subs: List["asyncio.Queue"] = []

    def subscribe(self, run_id: str) -> "asyncio.Queue":
        run = self._runs.setdefault(run_id, {"events": [], "subs": [], "done": False})
        q: "asyncio.Queue" = asyncio.Queue()
        for ev in run["events"]:
            q.put_nowait(ev)
        if run["done"]:
            q.put_nowait({"type": "done", "run_id": run_id})
        run["subs"].append(q)
        return q

    def subscribe_global(self) -> "asyncio.Queue":
        q: "asyncio.Queue" = asyncio.Queue()
        for ev in self._global_events:
            q.put_nowait(ev)
        self._global_subs.append(q)
        return q

    async def put(self, run_id: str, event: Dict[str, Any]) -> None:
        run = self._runs.setdefault(run_id, {"events": [], "subs": [], "done": False})
        run["events"].append(event)
        if len(run["events"]) > 2000:
            run["events"] = run["events"][-2000:]
        for q in list(run["subs"]):
            try:
                q.put_nowait(event)
            except Exception:
                pass
        # Global fan-out (capped replay buffer).
        self._global_events.append(event)
        if len(self._global_events) > 4000:
            self._global_events = self._global_events[-4000:]
        for q in list(self._global_subs):
            try:
                q.put_nowait(event)
            except Exception:
                pass

    async def done(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if not run or run["done"]:
            return
        run["done"] = True
        ev = {"type": "done", "run_id": run_id, "ts": _now()}
        run["events"].append(ev)
        for q in list(run["subs"]):
            try:
                q.put_nowait(ev)
            except Exception:
                pass


LOG_HUB = LogHub()


# --------------------------------------------------------------------------- #
# Callback handler -> structured backend events
# --------------------------------------------------------------------------- #
class ResearchLoggerCallbackHandler(BaseCallbackHandler):
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    async def on_chain_start(self, serialized, prompts, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "stage_start", "stage": name or _name(serialized),
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_chain_end(self, outputs, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "stage_done", "stage": name,
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_tool_start(self, serialized, input_str, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "tool_call", "tool": name or _name(serialized),
            "input": (input_str[:500] if isinstance(input_str, str) else input_str),
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_tool_end(self, output, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "tool_done", "tool": name,
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_retriever_start(self, serialized, query, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "retriever", "action": "start",
            "tool": name or "retriever", "query": query,
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_retriever_end(self, documents, *, name=None, **kwargs):
        try:
            count = len(documents)
        except Exception:
            count = None
        await LOG_HUB.put(self.run_id, {
            "type": "retriever", "action": "end", "count": count,
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_llm_start(self, serialized, prompts, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "llm", "action": "start", "model": _model_name(serialized),
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_llm_end(self, response, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "llm", "action": "end", "model": _model_name(serialized),
            "tokens": _token_usage(response),
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_llm_error(self, error, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "error", "stage": f"llm:{name}", "message": str(error),
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_chain_error(self, error, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "error", "stage": name or "chain", "message": str(error),
            "run_id": self.run_id, "ts": _now(),
        })

    async def on_tool_error(self, error, *, name=None, **kwargs):
        await LOG_HUB.put(self.run_id, {
            "type": "error", "stage": f"tool:{name}", "message": str(error),
            "run_id": self.run_id, "ts": _now(),
        })


# --------------------------------------------------------------------------- #
# Defensive graph import
# --------------------------------------------------------------------------- #
research_graph = None
create_initial_state = None
get_store = None
try:
    import intelligence_graph as ig  # noqa: F401
    from intelligence_graph import app as research_graph, create_initial_state  # noqa: E402
    from intelligence_graph import prepare_resume_state, normalize_report_plan  # noqa: E402
    from persistence import get_store  # noqa: E402
    log.info("Research graph imported successfully.")
except Exception as e:  # pragma: no cover - environment dependent
    log.warning("Research graph could not be imported (%s). /copilotkit not mounted.", e)


def _flesh_out_state(state: Any) -> Any:
    if not isinstance(state, dict):
        try:
            state = dict(state)
        except Exception:
            return state
    if state.get("run_folder") or create_initial_state is None:
        return state
    ip = state.get("input_paths") or {}
    ip = ip if isinstance(ip, dict) else {}
    return create_initial_state(
        user_query=state.get("user_initial_query") or state.get("user_query") or "",
        subject_profile_path=ip.get("subject_profile_path", "") or "",
        briefing_1_path=ip.get("briefing_1_path", "") or "",
        briefing_2_path=ip.get("briefing_2_path", "") or "",
        report_plan=state.get("report_plan"),
    )


def _try_json(value, default=None):
    if default is None:
        default = []
    if isinstance(value, (list, dict)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _resolve_run_state(body: dict):
    """Build a GraphState for a fresh run or resume an existing run.

    Returns (state, run_id). Honors body['stages'] (subset of REPORT_KEYS,
    auto-expanded to prerequisites) and body['resume_run_id'].
    """
    plan = normalize_report_plan(body.get("stages"))
    resume_run_id = body.get("resume_run_id")
    if resume_run_id:
        store = get_store()
        session = store.get_session(resume_run_id)
        if not session:
            raise ValueError(f"run '{resume_run_id}' not found")
        reports = {}
        for rec in store.list_reports(resume_run_id):
            if not rec.get("completed"):
                continue
            path = rec.get("path")
            content = ""
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                except Exception:
                    content = ""
            reports[rec["report_type"]] = {"content": content, "path": path}
        loaded = {
            "session_id": resume_run_id,
            "run_folder": session.get("run_folder"),
            "reports": reports,
        }
        state = prepare_resume_state(loaded, report_plan=plan)
        state["run_folder"] = session.get("run_folder") or state.get("run_folder")
        return state, resume_run_id

    ip = body.get("input_paths") or {}
    ip = ip if isinstance(ip, dict) else {}
    state = create_initial_state(
        user_query=body.get("user_query") or body.get("user_initial_query") or "",
        subject_profile_path=ip.get("subject_profile_path", "") or "",
        briefing_1_path=ip.get("briefing_1_path", "") or "",
        briefing_2_path=ip.get("briefing_2_path", "") or "",
        report_plan=plan,
    )
    return state, state.get("session_id") or f"run_{uuid.uuid4().hex[:8]}"


def _patch_config(config: Any):
    if not isinstance(config, dict):
        config = {}
    configurable = dict(config.get("configurable") or {})
    run_id = configurable.get("thread_id") or f"run_{uuid.uuid4().hex[:8]}"
    configurable["thread_id"] = run_id
    handlers = list(config.get("callbacks") or [])
    handlers.append(ResearchLoggerCallbackHandler(run_id))
    return {**config, "configurable": configurable, "callbacks": handlers}, run_id


async def _wrapped_ainvoke(state, config=None, **kwargs):
    if research_graph is None:
        raise RuntimeError("research graph unavailable")
    state = _flesh_out_state(state)
    patched, run_id = _patch_config(config)
    await LOG_HUB.put(run_id, {"type": "run_start", "run_id": run_id, "ts": _now()})
    try:
        result = await research_graph.ainvoke(state, config=patched, **kwargs)
    except Exception as e:
        await LOG_HUB.put(run_id, {"type": "error", "stage": "pipeline",
                                   "message": str(e), "run_id": run_id, "ts": _now()})
        await LOG_HUB.done(run_id)
        raise
    await LOG_HUB.done(run_id)
    return result


def _wrapped_astream(state, config=None, **kwargs):
    patched, run_id = _patch_config(config)
    state = _flesh_out_state(state)

    async def _gen():
        await LOG_HUB.put(run_id, {"type": "run_start", "run_id": run_id, "ts": _now()})
        try:
            async for chunk in research_graph.astream(state, config=patched, **kwargs):
                yield chunk
        except Exception as e:
            await LOG_HUB.put(run_id, {"type": "error", "stage": "pipeline",
                                       "message": str(e), "run_id": run_id, "ts": _now()})
            raise
        finally:
            await LOG_HUB.done(run_id)

    return _gen()


def _wrapped_astream_events(state, config=None, **kwargs):
    patched, run_id = _patch_config(config)
    state = _flesh_out_state(state)

    async def _gen():
        await LOG_HUB.put(run_id, {"type": "run_start", "run_id": run_id, "ts": _now()})
        try:
            async for chunk in research_graph.astream_events(state, config=patched, **kwargs):
                yield chunk
        except Exception as e:
            await LOG_HUB.put(run_id, {"type": "error", "stage": "pipeline",
                                       "message": str(e), "run_id": run_id, "ts": _now()})
            raise
        finally:
            await LOG_HUB.done(run_id)

    return _gen()


if research_graph is not None:
    research_graph.ainvoke = _wrapped_ainvoke
    research_graph.astream = _wrapped_astream
    if hasattr(research_graph, "astream_events"):
        research_graph.astream_events = _wrapped_astream_events


# --------------------------------------------------------------------------- #
# FastAPI app
# --------------------------------------------------------------------------- #
app = FastAPI(title="Research Agent Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "graph_loaded": research_graph is not None}


# CopilotKit's browser client discovers agents via GET {runtimeUrl}/info.
# The AGUI runtime only serves the manifest at GET /copilotkit/, so expose /info too.
# NOTE: the client expects `agents` as an OBJECT keyed by agent name (not an array).
AGENT_MANIFEST = {
    "actions": {},
    "agents": {
        "research_agent": {
            "description": (
                "Runs the Graph-RAG intelligence pipeline: identity research, then "
                "subject / audience / ecosystem intelligence. Provide a user_query and "
                "optional input_paths (subject profile + two briefings) and report_plan."
            ),
            "capabilities": {},
        }
    },
}


@app.get("/copilotkit/info")
async def agent_info():
    return AGENT_MANIFEST


@app.get("/api/agent/logs")
async def logs(run_id: str = Query(None)):
    queue = LOG_HUB.subscribe_global() if not run_id else LOG_HUB.subscribe(run_id)

    async def event_gen():
        yield {"event": "message", "data": json.dumps({"type": "connected", "run_id": run_id})}
        while True:
            event = await queue.get()
            yield {"event": "message", "data": json.dumps(event, default=str)}
            if event.get("type") == "done":
                break

    return EventSourceResponse(event_gen())


@app.post("/api/agent/run")
async def run_agent(request: Request):
    if research_graph is None:
        return {"ok": False, "error": "research graph not importable in this environment"}
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    try:
        state_in, run_id = _resolve_run_state(body)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    config = {"configurable": {"thread_id": run_id}}
    try:
        final_state = await _wrapped_ainvoke(state_in, config=config)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    reports = final_state.get("reports", {}) if isinstance(final_state, dict) else {}
    summary = {
        "run_folder": final_state.get("run_folder"),
        "reports": {
            k: {
                "path": (v.get("path") if isinstance(v, dict) else None),
                "chars": len(v.get("content", "")) if isinstance(v, dict) else 0,
                "sources": len(v.get("sources", [])) if isinstance(v, dict) else 0,
                "costs": v.get("costs") if isinstance(v, dict) else None,
            }
            for k, v in reports.items()
            if isinstance(v, dict)
        },
    }
    return {"ok": True, "run_id": run_id, "report_plan": normalize_report_plan(body.get("stages")), "summary": summary}


@app.get("/api/agent/runs")
async def list_runs():
    try:
        store = get_store()
        runs = store.list_sessions() if hasattr(store, "list_sessions") else []
        out = []
        for r in runs:
            r = dict(r)
            r["report_plan"] = _try_json(r.get("report_plan"), default=[])
            r["completed_reports"] = _try_json(r.get("completed_reports"), default=[])
            out.append(r)
        return {"runs": out}
    except Exception as e:  # pragma: no cover
        return {"runs": [], "error": str(e)}


@app.get("/api/agent/runs/{run_id}")
async def get_run(run_id: str):
    store = get_store()
    session = store.get_session(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="run not found")
    session = dict(session)
    session["report_plan"] = _try_json(session.get("report_plan"), default=[])
    session["completed_reports"] = _try_json(session.get("completed_reports"), default=[])
    reports = store.list_reports(run_id)
    return {"session": session, "reports": reports}


@app.get("/api/agent/runs/{run_id}/reports/{report_key}")
async def get_run_report(run_id: str, report_key: str):
    store = get_store()
    rec = store.get_report(run_id, report_key)
    if not rec:
        raise HTTPException(status_code=404, detail="report not found")
    path = rec.get("path")
    content = ""
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except Exception:
            content = ""
    return {
        "report_type": report_key,
        "path": path,
        "content": content,
        "summary": rec.get("summary", ""),
        "sources": rec.get("sources", []),
    }


# --------------------------------------------------------------------------- #
# Environment configuration (Env Setup UI)
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# AI service catalog (source of truth for the AI Configuration UI).
# The frontend renders this dynamically: no services, models or providers are
# hard-coded client-side. Each service maps to the env var(s) that actually
# drive it in the backend.
# --------------------------------------------------------------------------- #
AI_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {"label": "OpenAI (or OpenAI-compatible)", "chat": True, "embedding": True,
               "api_key_env": "OPENAI_API_KEY", "base_url_env": "OPENAI_BASE_URL",
               "base_url": "https://api.openai.com/v1"},
    "cohere": {"label": "Cohere", "chat": True, "embedding": True, "api_key_env": "COHERE_API_KEY"},
    "google_genai": {"label": "Google GenAI", "chat": True, "embedding": True, "api_key_env": "GOOGLE_API_KEY"},
    "anthropic": {"label": "Anthropic", "chat": True, "api_key_env": "ANTHROPIC_API_KEY"},
    "azure_openai": {"label": "Azure OpenAI", "chat": True, "embedding": True, "api_key_env": "AZURE_OPENAI_API_KEY"},
    "mistralai": {"label": "Mistral", "chat": True, "api_key_env": "MISTRAL_API_KEY"},
    "ollama": {"label": "Ollama (embedding)", "embedding": True, "api_key_env": ""},
    "huggingface": {"label": "HuggingFace (embedding)", "embedding": True, "api_key_env": "HF_TOKEN"},
    "custom": {"label": "Custom (embedding)", "embedding": True, "api_key_env": ""},
}

AI_SERVICES: List[Dict[str, Any]] = [
    {"category": "GPT Research (Multi-Agent)", "id": "gpt_strategic", "name": "Strategic LLM",
     "tier": "Large", "description": "Planning / reasoning agent.",
     "fields": [{"env": "STRATEGIC_LLM", "label": "Model", "kind": "chat_model"}]},
    {"category": "GPT Research (Multi-Agent)", "id": "gpt_smart", "name": "Smart LLM",
     "tier": "Medium", "description": "Researcher / writer agents.",
     "fields": [{"env": "SMART_LLM", "label": "Model", "kind": "chat_model"}]},
    {"category": "GPT Research (Multi-Agent)", "id": "gpt_fast", "name": "Fast LLM",
     "tier": "Small", "description": "Browser / editor agents.",
     "fields": [{"env": "FAST_LLM", "label": "Model", "kind": "chat_model"}]},
    {"category": "Research Graph + Ingestion", "id": "chat_model", "name": "Chat / Summarization Model",
     "description": "Used by graph pipeline nodes (subject / audience / ecosystem / compression / grader) and the ingestion pipeline.",
      "fields": [
          {"env": "CHAT_MODEL", "label": "Model name", "kind": "text"},
          {"env": "CHAT_MODEL_PROVIDER", "label": "Provider", "kind": "enum",
           "options": ["google_genai", "openai", "cohere", "anthropic", "mistralai"],
           "reveal_provider_credentials": True},
      ]},
    {"category": "Research Graph + Ingestion", "id": "embeddings", "name": "Embeddings",
     "description": "Used by ingestion and graph retrieval.",
     "fields": [{"env": "EMBEDDING", "label": "Embedding", "kind": "embedding"}]},
    {"category": "GPT Research (Multi-Agent)", "id": "gpt_embeddings", "name": "GPT Researcher Embeddings",
     "description": "Vector memory for the multi-agent researcher. Falls back to EMBEDDING when unset.",
     "fields": [{"env": "GPT_RESEARCHER_EMBEDDING", "label": "Embedding", "kind": "embedding"}]},
    {"category": "Search & Retrieval", "id": "search", "name": "Retriever",
     "description": "Web search / retrieval backend.",
     "fields": [
         {"env": "RETRIEVER", "label": "Retriever", "kind": "enum", "options": ["tavily", "mcp", "tavily,mcp"]},
         {"env": "TAVILY_API_KEY", "label": "Tavily API Key", "kind": "secret"},
     ]},
    {"category": "Vector Store", "id": "qdrant", "name": "Qdrant",
     "description": "Vector database for ingested documents.",
     "fields": [
         {"env": "QDRANT_URL", "label": "Qdrant URL", "kind": "url"},
         {"env": "QDRANT_API_KEY", "label": "Qdrant API Key", "kind": "secret"},
     ]},
    {"category": "MCP Servers", "id": "mcp", "name": "MCP Servers",
     "description": "Model-context-protocol tool servers.",
     "fields": [
         {"env": "MCP_API_KEY", "label": "MCP API Key", "kind": "secret"},
         {"env": "GDELT_MCP_API_KEY", "label": "GDELT MCP API Key", "kind": "secret"},
         {"env": "SOCIALCRAWL_MCP_API_KEY", "label": "SocialCrawl MCP API Key", "kind": "secret"},
     ]},
    {"category": "Observability", "id": "langsmith", "name": "LangSmith",
     "description": "Tracing & evaluation.",
     "fields": [
         {"env": "LANGSMITH_TRACING", "label": "Tracing", "kind": "enum", "options": ["true", "false"]},
         {"env": "LANGSMITH_ENDPOINT", "label": "Endpoint", "kind": "url"},
         {"env": "LANGSMITH_API_KEY", "label": "API Key", "kind": "secret"},
         {"env": "LANGSMITH_PROJECT", "label": "Project", "kind": "text"},
     ]},
    {"category": "Transcription", "id": "transcript", "name": "FreeTranscriptAPI",
     "description": "Transcript backend (used when SOCIAL_TRANSCRIPT_PROVIDER=freetranscriptapi).",
     "fields": [
         {"env": "FREETRANSCRIPTAPI_KEY", "label": "FreeTranscriptAPI Key", "kind": "secret"},
     ]},
]

# Derive the master list of env keys the UI may read/write.
_CATALOG_KEYS: set = set()
for _svc in AI_SERVICES:
    for _f in _svc["fields"]:
        _CATALOG_KEYS.add(_f["env"])
for _p in AI_PROVIDERS.values():
    if _p.get("api_key_env"):
        _CATALOG_KEYS.add(_p["api_key_env"])
    if _p.get("base_url_env"):
        _CATALOG_KEYS.add(_p["base_url_env"])
ENV_KEYS = sorted(_CATALOG_KEYS)
# Group keys by service category (for the raw env endpoint).
ENV_GROUPS: Dict[str, List[str]] = {}
for _svc in AI_SERVICES:
    ENV_GROUPS.setdefault(_svc["category"], [])
    for _f in _svc["fields"]:
        if _f["env"] not in ENV_GROUPS[_svc["category"]]:
            ENV_GROUPS[_svc["category"]].append(_f["env"])


def apply_env_values(values: Dict[str, str], path: str = ROOT_ENV) -> List[str]:
    """Persist env values to `path` (keeping comments + unknown keys) and apply
    them to the running process via os.environ so the next pipeline run uses them.
    """
    known = set(ENV_KEYS)
    existing = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    kept: List[str] = []
    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            kept.append(line)
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m and m.group(1) in known:
            continue  # drop active known-key lines; re-added below
        kept.append(line)
    body = "\n".join(kept).rstrip() + "\n"
    written: List[str] = []
    for k in ENV_KEYS:
        v = values.get(k)
        if v is None or v == "":
            # Explicitly cleared: drop from the process environment too so the
            # change is live without a restart.
            os.environ.pop(k, None)
            continue
        body += f"{k}={v}\n"
        os.environ[k] = v
        written.append(k)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return written


@app.get("/api/agent/env")
async def get_env():
    return {
        "groups": ENV_GROUPS,
        "values": {k: os.environ.get(k, "") for k in ENV_KEYS},
        "path": ROOT_ENV,
    }


@app.post("/api/agent/env")
async def post_env(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    values = body.get("values")
    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="expected { values: { KEY: VALUE } }")
    clean = {k: str(v) for k, v in values.items() if k in ENV_KEYS}
    written = apply_env_values(clean)
    return {"ok": True, "written": written, "path": ROOT_ENV}


@app.get("/api/agent/ai-config")
async def get_ai_config():
    """Dynamic AI service/provider catalog + current values (source of truth)."""
    return {
        "services": AI_SERVICES,
        "providers": AI_PROVIDERS,
        "values": {k: os.environ.get(k, "") for k in ENV_KEYS},
        "path": ROOT_ENV,
    }


# --------------------------------------------------------------------------- #
# CopilotKit AGUI runtime (only when the graph is available)
# --------------------------------------------------------------------------- #
if research_graph is not None:
    try:
        from copilotkit import LangGraphAGUIAgent
        from ag_ui_langgraph import add_langgraph_fastapi_endpoint

        research_agent = LangGraphAGUIAgent(
            name="research_agent",
            graph=research_graph,
            description=(
                "Runs the Graph-RAG intelligence pipeline: identity research, then "
                "subject / audience / ecosystem intelligence. Provide a user_query and "
                "optional input_paths (subject profile + two briefings) and report_plan."
            ),
        )
        # The AGUI runtime is served by ag_ui_langgraph's endpoint, which streams
        # AGUI events from agent.run(). This is the protocol the CopilotKit 1.x
        # React client expects (POST /agent/{name}/run).
        add_langgraph_fastapi_endpoint(app, research_agent, "/copilotkit/agent/research_agent/run")
        add_langgraph_fastapi_endpoint(app, research_agent, "/copilotkit/agent/research_agent")
        log.info("CopilotKit AGUI runtime mounted at /copilotkit/agent/research_agent")
    except Exception as e:  # pragma: no cover
        log.warning("CopilotKit endpoint could not be mounted: %s", e)


# Minimal stubs for the AGUI client's optional lifecycle calls so they don't 404.
@app.post("/copilotkit/agent/research_agent/connect")
async def agent_connect(request: Request):
    async def _gen():
        yield ": connected\n\n"
        try:
            while True:
                await asyncio.sleep(30)
                yield ": ping\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.post("/copilotkit/agent/research_agent/stop/{threadId}")
async def agent_stop(threadId: str):
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AGENT_BACKEND_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
