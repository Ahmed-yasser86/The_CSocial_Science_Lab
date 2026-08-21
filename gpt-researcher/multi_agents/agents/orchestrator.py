import os
import time
import datetime
from typing import Optional
from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.memory import MemorySaver
from .utils.views import print_agent_output
from ..memory.research import ResearchState
from .utils.utils import sanitize_filename
from .plan_review import (
    DEFAULT_MAX_PLAN_REVISIONS,
    route_human_feedback,
)
from .fact_review import (
    DEFAULT_MAX_FACT_CHECK_REVISIONS,
    route_fact_check,
)

# Import agent classes
from . import \
    WriterAgent, \
    EditorAgent, \
    PublisherAgent, \
    ResearchAgent, \
    HumanAgent, \
    FactCheckerAgent, \
    VisualizerAgent

# embedding registry for cross-agent embedding coordination
from gpt_researcher.utils.embedding_registry import wait_all as embedding_wait_all, pending_count as embedding_pending_count


# Default GDELT Cloud MCP settings
DEFAULT_GDELT_API_KEY = "gdelt_sk_9d4b2e96b110d802756c73d35c60fb008e2381dd58ccb7efb51f3562f991123f"
DEFAULT_GDELT_MCP_URL = "https://gdelt-cloud-mcp.fastmcp.app/mcp"


def get_gdelt_mcp_config(api_key: Optional[str] = None, url: Optional[str] = None):
    """
    Get MCP configuration list for GDELT Cloud MCP server.
    
    Args:
        api_key (optional): GDELT Cloud API Key. Defaults to GDELT_API_KEY env var or fallback default key.
        url (optional): MCP server endpoint URL. Defaults to GDELT_MCP_URL env var or fallback default URL.
        
    Returns:
        list: List of MCP configuration dicts for GPTResearcher / MultiServerMCPClient.
    """
    token = api_key or os.environ.get("GDELT_API_KEY", DEFAULT_GDELT_API_KEY)
    mcp_url = url or os.environ.get("GDELT_MCP_URL", DEFAULT_GDELT_MCP_URL)
    return [
        {
            "name": "gdelt-cloud",
            "connection_type": "streamable_http",
            "connection_url": mcp_url,
            "url": mcp_url,
            "connection_headers": {
                "Authorization": f"Bearer {token}"
            },
            "headers": {
                "Authorization": f"Bearer {token}"
            },
            "connection_token": token
        }
    ]


class ChiefEditorAgent:
    """Agent responsible for managing and coordinating editing tasks."""

    def __init__(self, task: dict, websocket=None, stream_output=None, tone=None, headers=None):
        self.task = task
        self.websocket = websocket
        self.headers = headers or self.task.get("headers", {}) or {}
        self.stream_output = stream_output
        self.tone = tone
        self.task_id = self._generate_task_id()
        self.output_dir = self._create_output_directory()

    def _generate_task_id(self):
        # Currently time based, but can be any unique identifier
        return int(time.time())

    def _create_output_directory(self):
        import uuid
        unique_id = uuid.uuid4().hex
        output_dir = os.path.join(".", "outputs", f"run_{unique_id}")
        
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _initialize_agents(self):
        mcp_configs = self.task.get("mcp_configs")
        if mcp_configs is None and self.task.get("use_gdelt_mcp"):
            mcp_configs = get_gdelt_mcp_config()

        return {
            "writer": WriterAgent(self.websocket, self.stream_output, self.headers),
            "editor": EditorAgent(
                self.websocket,
                self.stream_output,
                self.tone,
                self.headers,
                mcp_configs=mcp_configs,
                mcp_strategy=self.task.get("mcp_strategy"),
            ),
            "research": ResearchAgent(
                self.websocket,
                self.stream_output,
                self.tone,
                self.headers,
                mcp_configs=mcp_configs,
                mcp_strategy=self.task.get("mcp_strategy"),
            ),
            "publisher": PublisherAgent(self.output_dir, self.websocket, self.stream_output, self.headers),
            "human": HumanAgent(self.websocket, self.stream_output, self.headers),
            "fact_checker": FactCheckerAgent(self.websocket, self.stream_output, self.headers),
            "visualizer": VisualizerAgent(self.websocket, self.stream_output, self.headers)
        }

    def _create_workflow(self, agents):
        workflow = StateGraph(ResearchState)

        # Add nodes for each agent
        workflow.add_node("browser", agents["research"].run_initial_research)
        workflow.add_node("planner", agents["editor"].plan_research)
        workflow.add_node("researcher", agents["editor"].run_parallel_research)
        # Barrier node: wait for all outstanding embeddings to finish before proceeding
        workflow.add_node("embeddings_barrier", self._wait_for_embeddings)
        workflow.add_node("writer", agents["writer"].run)
        workflow.add_node("fact_checker", agents["fact_checker"].run)
        workflow.add_node("visualizer", agents["visualizer"].run)
        workflow.add_node("publisher", agents["publisher"].run)
        workflow.add_node("human", agents["human"].review_plan)

        # Add edges
        self._add_workflow_edges(workflow)

        return workflow

    def _add_workflow_edges(self, workflow):
        workflow.add_edge('browser', 'planner')
        workflow.add_edge('planner', 'human')
        # research -> embeddings barrier -> writer
        workflow.add_edge('researcher', 'embeddings_barrier')
        workflow.add_edge('embeddings_barrier', 'writer')
        workflow.add_edge('writer', 'fact_checker')
        workflow.add_edge('visualizer', 'publisher')
        workflow.set_entry_point("browser")
        workflow.add_edge('publisher', END)

        # Add human in the loop
        MAX_REVISIONS = 5
        workflow.add_conditional_edges(
            'human',
            lambda state: (
                "accept" if state['human_feedback'] is None
                else "force_accept" if state.get('revisions_count', 0) >= MAX_REVISIONS
                else "revise"
            ),
            {"accept": "researcher", "force_accept": "researcher", "revise": "planner"}
        )

        # Fact-checker loop — bounded via task.max_fact_check_revisions
        workflow.add_conditional_edges(
            'fact_checker',
            lambda state: route_fact_check(
                state,
                self.task.get("max_fact_check_revisions", DEFAULT_MAX_FACT_CHECK_REVISIONS),
            ),
            {"accept": "visualizer", "revise": "writer"}
        )

    def _route_fact_check(self, state):
        max_fact_check_revisions = self.task.get(
            "max_fact_check_revisions", DEFAULT_MAX_FACT_CHECK_REVISIONS
        )
        return route_fact_check(state, max_fact_check_revisions)

    def _route_human_feedback(self, review):
        max_plan_revisions = self.task.get(
            "max_plan_revisions", DEFAULT_MAX_PLAN_REVISIONS)
        return route_human_feedback(review, max_plan_revisions)

    def init_research_team(self):
        """Initialize and create a workflow for the research team."""
        agents = self._initialize_agents()
        return self._create_workflow(agents)

    async def _wait_for_embeddings(self, state):
        """Barrier node: wait for all outstanding embedding tasks to complete before proceeding.

        Reads optional timeout from task config: 'embeddings_barrier_timeout' (seconds).
        """
        timeout = self.task.get("embeddings_barrier_timeout", 300)
        # log current pending count if available
        try:
            pending = await embedding_pending_count()
        except Exception:
            pending = None
        message = f"Waiting for outstanding embedding tasks to complete (pending={pending}) with timeout={timeout}s..."
        if self.websocket and self.stream_output:
            await self.stream_output("logs", "embeddings_barrier", message, self.websocket)
        else:
            print_agent_output(message, "MASTER")

        try:
            await embedding_wait_all(timeout=timeout)
        except Exception as e:
            err_msg = f"Error while waiting for embeddings: {e}"
            if self.websocket and self.stream_output:
                await self.stream_output("logs", "embeddings_barrier_error", err_msg, self.websocket)
            else:
                print_agent_output(err_msg, "MASTER")

        done_msg = "Embeddings barrier released, proceeding to next stage."
        if self.websocket and self.stream_output:
            await self.stream_output("logs", "embeddings_barrier_done", done_msg, self.websocket)
        else:
            print_agent_output(done_msg, "MASTER")
        return state

    async def _log_research_start(self):
        message = f"Starting the research process for query '{self.task.get('query')}'..."
        if self.websocket and self.stream_output:
            await self.stream_output("logs", "starting_research", message, self.websocket)
        else:
            print_agent_output(message, "MASTER")

    async def run_research_task(self, task_id=None, prompt_type: Optional[str]=None):
        """
        Run a research task with the initialized research team.

        Args:
            task_id (optional): The ID of the task to run.

        Returns:
            The result of the research task.
        """
        research_team = self.init_research_team()
        chain = research_team.compile()

        await self._log_research_start()

        config = {
            "configurable": {
                "thread_id": task_id,
                "thread_ts": datetime.datetime.utcnow()
            }
        }

        # If a prompt_type is provided (e.g., 'audience'), forward it to the task
        if prompt_type is not None:
            try:
                # do not overwrite original unless set
                self.task = dict(self.task)
                self.task["prompt_type"] = prompt_type
            except Exception:
                pass

        result = await chain.ainvoke({"task": self.task}, config=config)
        return result
