from datetime import datetime
import asyncio
from typing import Dict, List, Optional 
from .prompt_type import PromptType
from .shared_prompt_instructions import NON_EMPIRICAL_REPORTING_INSTRUCTIONS

from langgraph.graph import StateGraph, END

from .utils.views import print_agent_output
from .utils.llms import call_model
from ..memory.draft import DraftState
from . import ResearchAgent, ReviewerAgent, ReviserAgent
from .draft_review import (
    DEFAULT_MAX_DRAFT_REVISIONS,
    route_draft_review,
)


class EditorAgent:
    """Agent responsible for editing and managing code."""

    def __init__(self, websocket=None, stream_output=None, tone=None, headers=None, mcp_configs=None, mcp_strategy=None):
        self.websocket = websocket
        self.stream_output = stream_output
        self.tone = tone
        self.headers = headers or {}
        self.mcp_configs = mcp_configs
        self.mcp_strategy = mcp_strategy

    async def plan_research(self, research_state: Dict[str, any]) -> Dict[str, any]:
        """
        Plan the research outline based on initial research and task parameters.

        :param research_state: Dictionary containing research state information
        :return: Dictionary with title, date, and planned sections
        """
        initial_research = research_state.get("initial_research")
        task = research_state.get("task")
        include_human_feedback = task.get("include_human_feedback")
        human_feedback = research_state.get("human_feedback")
        max_sections = task.get("max_sections")

        # Determine prompt type from the incoming task state first, then fall back
        # to the research state for backward compatibility.
        prompt_type_value = None
        task = research_state.get("task") or {}
        if isinstance(task, dict):
            prompt_type_value = task.get("prompt_type")
        if prompt_type_value is None:
            prompt_type_value = research_state.get("prompt_type")

        if isinstance(prompt_type_value, str):
            try:
                prompt_type = PromptType(prompt_type_value.lower())
            except Exception:
                prompt_type = PromptType.SUBJECT
        elif isinstance(prompt_type_value, PromptType):
            prompt_type = prompt_type_value
        else:
            prompt_type = PromptType.SUBJECT

        prompt = self._create_planning_prompt(
            initial_research, include_human_feedback, human_feedback, max_sections, prompt_type)

        print_agent_output(
            "Planning an outline layout based on initial research...", agent="EDITOR")
        plan = await call_model(
            prompt=prompt,
            model=task.get("model"),
            response_format="json",
        )

        return {
            "title": plan.get("title"),
            "date": plan.get("date"),
            "sections": self._normalize_sections(plan.get("sections")),
        }

    async def run_parallel_research(self, research_state: Dict[str, any]) -> Dict[str, List[str]]:
        """
        Execute parallel research tasks for each section.

        :param research_state: Dictionary containing research state information
        :return: Dictionary with research results
        """
        agents = self._initialize_agents()
        workflow = self._create_workflow()
        chain = workflow.compile()

        queries = self._normalize_sections(research_state.get("sections") or [])
        title = research_state.get("title")

        self._log_parallel_research(queries)

        final_drafts = [
            chain.ainvoke(self._create_task_input(
                research_state, query, title), config={"tags": ["gpt-researcher"]})
            for query in queries
        ]
        research_results = [
            result["draft"] for result in await asyncio.gather(*final_drafts)
        ]

        return {"research_data": research_results}

    def _create_planning_prompt(self, initial_research: str, include_human_feedback: bool,
                                human_feedback: Optional[str], max_sections: int, prompt_type: 'PromptType') -> List[Dict[str, str]]:
        """Create the prompt for research planning."""
        # Choose the appropriate system prompt based on prompt_type
        if prompt_type == PromptType.AUDIENCE:
            system_message = {
                "role": "system",
                "content": "You are an Audience Intelligence Architect, Social Network Analyst, "
                           "and Digital Ethnographer/Cyber-anthropologist. "
                           "Your goal is to design a concise, structured investigation outline "
                           "for a downstream RAG-enabled intelligence pipeline. "
                           "Treat the audience ecosystem as the primary object of analysis "
                           "and the subject as a source of influence. "
                           "Design section headers that capture audience segments, community structure, "
                           "social dynamics, network relationships, influence pathways, trust, motivations, "
                           "cultural norms, engagement patterns, diffusion mechanisms, vulnerabilities, "
                           "and resilience factors.\n"
                           "Think in terms of high-density intelligence extraction, not an article or academic outline. "
                           "Organize the investigation around analytical domains instead of chronology.\n"
                           "Group related concepts together, separate distinct intelligence domains, "
                           "and minimize overlap between sections. "
                           "Prioritize token-efficient structure and retrieval-friendly headings.\n"
                           "This plan is for an intelligence workflow, not an academic research protocol. "
                           "Do not include sections on research design, methodology, data collection, "
                           "longitudinal analysis, time-series analysis, mixed-methods integration, "
                           "triangulation, or network mapping procedures. "
                           "Do not add any section unrelated to audience intelligence, social network analysis, "
                           "influence ecosystems, or audience behavior modeling.\n"
                           f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS}\n"
                           "Avoid generic sections such as Introduction, Conclusion, Background, "
                           "Timeline, or References.\n"
                           "Do not perform research. "
                           "Do not analyze evidence. "
                           "Do not generate findings. "
                           "Your sole responsibility is to design the investigation structure.\n",
            }
        elif prompt_type == PromptType.ECOSYSTEM:
            system_message = {
                "role": "system",
                "content": "You are an Ecosystem Intelligence Architect and Social Systems Editor. "
                           "Your job is to design a compact investigation outline for an ecosystem-focused RAG pipeline. "
                           "Treat the surrounding ecosystem as the primary analytical object: communities, institutions, audiences, opposition, influence flows, resilience, and network structure. "
                           "The subject should be treated as a node within the ecosystem rather than the sole object of analysis. "
                           "Design section headers that capture controversy, opposition, audience communities, influence pathways, network structure, resilience, and observable ecosystem dynamics.\n"
                           "Think in terms of high-density intelligence extraction, not an article or academic outline. "
                           "Organize the investigation around analytical domains instead of chronology.\n"
                           "Group related concepts together, separate distinct ecosystem domains, "
                           "and minimize overlap between sections. "
                           "Prioritize token-efficient structure and retrieval-friendly headings.\n"
                           f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS}\n"
                           "Avoid generic sections such as Introduction, Conclusion, Background, Biography, "
                           "Timeline, or References.\n"
                           "Do not perform research. "
                           "Do not analyze evidence. "
                           "Do not generate findings. "
                           "Your sole responsibility is to design the investigation structure.\n",
            }
        else:
            system_message = {
                "role": "system",
                "content": "You are the Subject Intelligence Architect and Research Editor. "
                           "Your goal is to oversee the subject intelligence investigation "
                           "from inception to completion. "
                           "This run is explicitly scoped to the subject only. "
                           "Do not frame this work as a statistical report, survey, dashboard, or quantitative analysis. "
                           "Do not shift the focus toward audience composition, followers, communities, or ecosystem analysis. "
                           "Your main task is to plan the investigation section layout "
                           "based on an initial intelligence summary.\n"
                           "This is not a statistical report, survey, dashboard, or quantitative analysis. "
                           "Do not frame the work as metrics, percentages, rankings, or score-based findings unless evidence explicitly supports that framing.\n"
                           "Design investigation sections that collectively explain the subject "
                           "from multiple analytical perspectives. "
                           "The investigation may include identity, worldview, ideas, ideology, "
                           "epistemology, reasoning, philosophy, methodology, communication, "
                           "influence, and any other relevant dimensions supported by the available evidence.\n"
                           "Think like an intelligence architect rather than an article editor. "
                           "Organize the investigation around analytical dimensions instead of chronology.\n"
                           "Group related concepts together, separate distinct analytical domains, "
                           "and minimize overlap between sections. "
                           "Prioritize knowledge extraction over narrative organization.\n"
                           "The investigation structure should guide downstream intelligence agents "
                           "as they collect evidence and build an intelligence profile of the subject.\n"
                           f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS}\n"
                           "Avoid generic sections such as Introduction, Conclusion, Biography, "
                           "Timeline, Background, or References.\n"
                           "Do not perform research. "
                           "Do not analyze evidence. "
                           "Do not generate conclusions. "
                           "Your sole responsibility is to design the investigation structure.\n",
            }

        return [
            system_message,
            {
                "role": "user",
                "content": self._format_planning_instructions(initial_research, include_human_feedback,
                                                              human_feedback, max_sections),
            },
        ]

    def _format_planning_instructions(self, initial_research: str, include_human_feedback: bool,
                                      human_feedback: Optional[str], max_sections: int) -> str:
        """Format the instructions for research planning."""
        today = datetime.now().strftime('%d/%m/%Y')
        feedback_instruction = (
            f"Human feedback: {human_feedback}. You must plan the sections based on the human feedback."
            if include_human_feedback and human_feedback and human_feedback != 'no'
            else ''
        )

        return f"""Today's date is {today}
                   Research summary report: '{initial_research}'
                   {feedback_instruction}
                   \nYour task is to generate an outline of sections headers for the research project
                   based on the research summary report above.
                   You must generate a maximum of {max_sections} section headers.
                   You must focus ONLY on related research topics for subheaders and do NOT include introduction, conclusion and references.
                   You must return nothing but a JSON with the fields 'title' (str) and 
                   'sections' (maximum {max_sections} section headers) with the following structure:
                   '{{title: string research title, date: today's date, 
                   sections: ['section header 1', 'section header 2', 'section header 3' ...]}}'."""

    def _initialize_agents(self) -> Dict[str, any]:
        """Initialize the research, reviewer, and reviser skills."""
        return {
            "research": ResearchAgent(
                self.websocket,
                self.stream_output,
                self.tone,
                self.headers,
                mcp_configs=self.mcp_configs,
                mcp_strategy=self.mcp_strategy,
            ),
            "reviewer": ReviewerAgent(self.websocket, self.stream_output, self.headers),
            "reviser": ReviserAgent(self.websocket, self.stream_output, self.headers),
        }

    def _create_workflow(self) -> StateGraph:
        """Create the workflow for the research process."""
        agents = self._initialize_agents()
        workflow = StateGraph(DraftState)

        workflow.add_node("researcher", agents["research"].run_depth_research)
        workflow.add_node("reviewer", agents["reviewer"].run)
        workflow.add_node("reviser", agents["reviser"].run)

        workflow.set_entry_point("researcher")
        workflow.add_edge("researcher", "reviewer")
        workflow.add_edge("reviser", "reviewer")
        workflow.add_conditional_edges(
            "reviewer",
            lambda draft: route_draft_review(
                draft,
                self.headers.get("max_draft_revisions", DEFAULT_MAX_DRAFT_REVISIONS),
            ),
            {"accept": END, "revise": "reviser"},
        )

        return workflow

    def _log_parallel_research(self, queries: List[str]) -> None:
        """Log the start of parallel research tasks."""
        if self.websocket and self.stream_output:
            asyncio.create_task(self.stream_output(
                "logs",
                "parallel_research",
                f"Running parallel research for the following queries: {queries}",
                self.websocket,
            ))
        else:
            print_agent_output(
                f"Running the following research tasks in parallel: {queries}...",
                agent="EDITOR",
            )

    def _create_task_input(self, research_state: Dict[str, any], query: str, title: str) -> Dict[str, any]:
        """Create the input for a single research task."""
        return {
            "task": research_state.get("task"),
            "topic": query,
            "title": title,
            "headers": self.headers,
        }

    def _normalize_sections(self, sections: any) -> List[str]:
        """Normalize model plan sections into a flat list of strings."""
        if isinstance(sections, dict):
            # Some model outputs may use a dict wrapper around the sections list.
            if "sections" in sections and isinstance(sections["sections"], list):
                sections = sections["sections"]
            else:
                sections = list(sections.values())

        if not isinstance(sections, list):
            return []

        normalized = []
        for item in sections:
            if isinstance(item, str):
                item = item.strip()
                if item:
                    normalized.append(item)
                continue

            if isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, str) and value.strip():
                        normalized.append(value.strip())
                        break
                    if isinstance(value, list):
                        for element in value:
                            if isinstance(element, str) and element.strip():
                                normalized.append(element.strip())
                                break
                        if normalized:
                            break
                continue

            if item is not None:
                normalized.append(str(item).strip())

        return normalized




# {
#     "role": "system",
#     "content": "You are the Audience Intelligence Architect and Research Editor. "
#                "Your goal is to oversee the audience intelligence investigation "
#                "from inception to completion. "
#                "Your main task is to plan the investigation section layout "
#                "based on an initial intelligence summary.\n"
#                "Design investigation sections that collectively explain the audience "
#                "ecosystem from multiple analytical perspectives. "
#                "The investigation may include audience composition, communities, "
#                "culture, values, motivations, identities, behavior, communication, "
#                "social dynamics, influence, diffusion, trust, engagement, polarization, "
#                "and any other relevant dimensions supported by the available evidence.\n"
#                "Think like an audience intelligence architect rather than an article editor. "
#                "Organize the investigation around analytical dimensions instead of chronology.\n"
#                "Group related concepts together, separate distinct analytical domains, "
#                "and minimize overlap between sections. "
#                "Prioritize knowledge extraction over narrative organization.\n"
#                "The investigation structure should guide downstream intelligence agents "
#                "as they collect evidence and build an intelligence profile of the audience ecosystem.\n"
#                "Avoid generic sections such as Introduction, Conclusion, Background, "
#                "Timeline, or References.\n"
#                "Do not perform research. "
#                "Do not analyze evidence. "
#                "Do not generate findings. "
#                "Your sole responsibility is to design the investigation structure.\n",
# }