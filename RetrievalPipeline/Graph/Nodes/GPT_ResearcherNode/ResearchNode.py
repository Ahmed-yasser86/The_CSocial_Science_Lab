import inspect
from typing import Any, Dict
import logging

# Add the workspace root and RetrievalPipeline to the Python path
import os
import sys

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
RETRIVAL_PIPELINE_PATH = os.path.join(WORKSPACE_ROOT, "RetrievalPipeline")

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)
if RETRIVAL_PIPELINE_PATH not in sys.path:
    sys.path.insert(0, RETRIVAL_PIPELINE_PATH)

# Import from RetrievalPipeline.Graph.Chains.GPT_Researcher
from RetrievalPipeline.Graph.Chains.GPT_Researcher import conduct_multi_agent_research
from RetrievalPipeline.Graph.StateGraph import GraphState, ProfileCandidate

logger = logging.getLogger(__name__)


def _normalize_raw_result(raw_result: Any) -> dict:
    """
    Normalize the raw result from conduct_multi_agent_research into a consistent dictionary format.
    """
    if isinstance(raw_result, dict):
        return raw_result
    if isinstance(raw_result, str):
        return {"report": raw_result}
    if isinstance(raw_result, list):
        for item in raw_result:
            if isinstance(item, dict):
                return item
        return {"report": " ".join(str(x) for x in raw_result)}
    return {}


def _as_title(section: Any) -> str:
    if isinstance(section, str):
        return section
    if isinstance(section, dict):
        return section.get("title", "")
    return str(section)


def _extract_section_map(item: Any) -> Dict[str, str]:
    if isinstance(item, dict) and item:
        return item
    if isinstance(item, str):
        return {"unrecognized_section": item}
    return {}


async def make_research(state: GraphState) -> Dict[str, Any]:
    chain_input = state.get("chain_input", {})
    mcp_configs = chain_input.get("mcp_configs") or state.get("mcp_configs")
    mcp_strategy = chain_input.get("mcp_strategy") or state.get("mcp_strategy")
    prompt_type = state.get("prompt_type") or chain_input.get("prompt_type")
    guidelines = chain_input.get("guidelines") or state.get("guidelines")

    # Redacted logging to help debug whether MCP configs are reaching this node.
    try:
        redacted = None
        if mcp_configs:
            redacted = []
            for cfg in mcp_configs:
                rc = dict(cfg)
                if "connection_token" in rc:
                    rc["connection_token"] = "<REDACTED>"
                if "connection_headers" in rc and isinstance(rc["connection_headers"], dict):
                    rh = {}
                    for hk, hv in rc["connection_headers"].items():
                        if hk.lower() == "authorization":
                            rh[hk] = "<REDACTED>"
                        else:
                            rh[hk] = hv
                    rc["connection_headers"] = rh
                redacted.append(rc)
        logger.debug(f"make_research: mcp_configs (redacted)={redacted}, mcp_strategy={mcp_strategy}")
    except Exception:
        logger.exception("Failed to redact or log mcp_configs")

    call_kwargs: Dict[str, Any] = {
        "query": chain_input["query"],
        "max_sections": chain_input.get("max_sections", 5),
        "follow_guidelines": chain_input.get("follow_guidelines", True),
        "verbose": chain_input.get("verbose", True),
        "prompt_type": prompt_type,
        "mcp_configs": mcp_configs,
        "mcp_strategy": mcp_strategy,
    }

    try:
        signature = inspect.signature(conduct_multi_agent_research)
    except (TypeError, ValueError):
        signature = None

    if signature is not None:
        accepts_guidelines = "guidelines" in signature.parameters or any(
            param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()
        )
        if accepts_guidelines:
            call_kwargs["guidelines"] = guidelines

    raw_result = await conduct_multi_agent_research(**call_kwargs)

    if raw_result is None:
        raise RuntimeError("run_research_task() رجّع None")

    raw_result = _normalize_raw_result(raw_result)

    section_content: Dict[str, str] = {}
    for item in raw_result.get("research_data", []):
        section_content.update(_extract_section_map(item))

    candidate: ProfileCandidate = {
        "title": raw_result.get("title", ""),
        "summary": "",
        "full_report": raw_result.get("report", ""),
        "introduction": raw_result.get("introduction", ""),
        "conclusion": raw_result.get("conclusion", ""),
        "initial_research": raw_result.get("initial_research", ""),
        "sub_topics": [_as_title(s) for s in raw_result.get("sections", [])],
        "section_content": section_content,
        "table_of_contents": raw_result.get("table_of_contents", ""),
        "sources": raw_result.get("sources", []),
        "costs": raw_result.get("costs", 0.0),
    }

    existing_candidates = state.get("profile_candidates", [])

    return {
        "profile_candidates": existing_candidates + [candidate],
        "research_iteration": state.get("research_iteration", 0) + 1,
    }