import os
import sys
import importlib
import inspect
from typing import Optional
import logging
import asyncio

# Prefer the local forked copy of the repo (not the installed package).
# Add the local gpt-researcher root to sys.path so Python resolves the local package.
LOCAL_GPT_RESEARCHER = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "gpt-researcher")
)
if LOCAL_GPT_RESEARCHER not in sys.path:
    sys.path.insert(0, LOCAL_GPT_RESEARCHER)

try:
    from multi_agents.agents import ChiefEditorAgent
    m = importlib.import_module("multi_agents.agents")
    print("Using ChiefEditorAgent from:", inspect.getsourcefile(m))
except ImportError as exc:
    raise ImportError(
        f"Failed to import ChiefEditorAgent from local gpt_researcher fork at {LOCAL_GPT_RESEARCHER}. "
        "Make sure the local repo path is correct and that the fork contains the expected multi_agents package."
    ) from exc



def _resolve_model_from_env() -> str | None:
    """
    Same logic as in multi_agents/main.py's open_task() -
    Reads STRATEGIC_LLM from .env and extracts the model name after the colon
    (example: "openai:moonshotai/Kimi-K2.6" -> "moonshotai/Kimi-K2.6").
    Without this, task["model"] returns None and shows "Model cannot be None" error.
    """
    strategic_llm = os.environ.get("STRATEGIC_LLM")
    if not strategic_llm:
        return None
    if ":" in strategic_llm:
        return strategic_llm.split(":", 1)[1]
    return strategic_llm



async def conduct_multi_agent_research(
    query: str,
    max_sections: int = 5,
    follow_guidelines: bool = True,
    guidelines: list[str] = [],
    verbose: bool = True,
    prompt_type: Optional[str] = None,
    mcp_configs: list[dict] | None = None,
    mcp_strategy: str | None = None,
) -> dict:
    """
    Runs the complete multi-agent pipeline:
    Browser -> Editor -> Researcher -> Reviewer -> Revisor -> Writer -> Publisher
    Returns the raw result as returned from run_research_task().

    Important: Keep query short (under ~400 characters) because it's sent to Tavily search
    internally and Tavily rejects any query longer than 400 characters with 400 Bad Request.
    Put detailed requirements and focus areas in guidelines instead of query.
    """
    task = {
        "query": query,
        "max_sections": max_sections,
        "publish_formats": {"markdown": True},
        "include_human_feedback": False,
        "follow_guidelines": follow_guidelines,
        "guidelines": guidelines or [],
        "verbose": verbose,
    }
    if mcp_configs is not None:
        task["mcp_configs"] = mcp_configs
    if mcp_strategy is not None:
        task["mcp_strategy"] = mcp_strategy

    model = _resolve_model_from_env()
    if model:
        task["model"] = model

    if prompt_type is not None:
        task["prompt_type"] = prompt_type

    logger = logging.getLogger(__name__)
    logger.debug("conduct_multi_agent_research: creating ChiefEditorAgent with task keys: %s", list(task.keys()))

    chief_editor = ChiefEditorAgent(task)
    logger.debug("conduct_multi_agent_research: ChiefEditorAgent created: %s", type(chief_editor))

    logger.debug("conduct_multi_agent_research: running research task")

    try:
        research_report: dict = await chief_editor.run_research_task(prompt_type=prompt_type)
        logger.debug("conduct_multi_agent_research: research task completed")
        return research_report
    except Exception as e:
        logger.exception("conduct_multi_agent_research: exception while running research task: %s", e)
        raise