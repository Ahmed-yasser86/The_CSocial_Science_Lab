import json

from gpt_researcher import GPTResearcher
from colorama import Fore, Style
from .utils.views import print_agent_output
from .shared_prompt_instructions import NON_EMPIRICAL_REPORTING_INSTRUCTIONS


class ResearchAgent:
    def __init__(self, websocket=None, stream_output=None, tone=None, headers=None, mcp_configs=None, mcp_strategy=None):
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers or {}
        self.tone = tone
        self.mcp_configs = mcp_configs
        self.mcp_strategy = mcp_strategy

    async def research(
        self,
        query: str,
        research_report: str = "research_report",
        parent_query: str = "",
        verbose=True,
        source="web",
        tone=None,
        headers=None,
        mcp_configs=None,
        mcp_strategy=None,
    ):
        reporting_instruction = (
            "\n\nIMPORTANT REPORTING RULE: "
            f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS} "
            "Do not present the findings as a formal empirical study, survey, or quantitative proof "
            "unless the evidence clearly supports that framing."
        )

        # Initialize the researcher
        researcher = GPTResearcher(
            query=f"{query}{reporting_instruction}",
            report_type=research_report,
            parent_query=parent_query,
            verbose=verbose,
            report_source=source,
            tone=tone,
            websocket=self.websocket,
            headers=self.headers,
            mcp_configs=mcp_configs if mcp_configs is not None else self.mcp_configs,
            mcp_strategy=mcp_strategy if mcp_strategy is not None else self.mcp_strategy,
        )
        # Conduct research on the given query
        await researcher.conduct_research()
        # Write the report
        report = await researcher.write_report()

        return report

    async def run_subtopic_research(self, parent_query: str, subtopic: str, verbose: bool = True, source="web", headers=None):
        normalized_subtopic = self._normalize_subtopic(subtopic)
        try:
            report = await self.research(parent_query=parent_query, query=normalized_subtopic,
                                         research_report="subtopic_report", verbose=verbose, source=source, tone=self.tone, headers=headers)
        except Exception as e:
            print(f"{Fore.RED}Error in researching topic {normalized_subtopic}: {e}{Style.RESET_ALL}")
            report = None
        return {normalized_subtopic: report}

    def _normalize_subtopic(self, subtopic: any) -> str:
        if isinstance(subtopic, str):
            return subtopic.strip()
        if isinstance(subtopic, list):
            normalized_items = []
            for item in subtopic:
                if isinstance(item, str) and item.strip():
                    normalized_items.append(item.strip())
                    continue
                if isinstance(item, dict):
                    for value in item.values():
                        if isinstance(value, str) and value.strip():
                            normalized_items.append(value.strip())
                            break
                    else:
                        normalized_items.append(json.dumps(item, ensure_ascii=False))
                    continue
                if item is not None:
                    normalized_items.append(str(item).strip())
            return " | ".join(normalized_items)
        if isinstance(subtopic, dict):
            for value in subtopic.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return json.dumps(subtopic, ensure_ascii=False)
        return str(subtopic)

    async def run_initial_research(self, research_state: dict):
        task = research_state.get("task")
        query = task.get("query")
        source = task.get("source", "web")

        if self.websocket and self.stream_output:
            await self.stream_output("logs", "initial_research", f"Running initial research on the following query: {query}", self.websocket)
        else:
            print_agent_output(f"Running initial research on the following query: {query}", agent="RESEARCHER")
        return {"task": task, "initial_research": await self.research(query=query, verbose=task.get("verbose"),
                                                                      source=source, tone=self.tone, headers=self.headers)}

    async def run_depth_research(self, draft_state: dict):
        task = draft_state.get("task")
        topic = draft_state.get("topic")
        parent_query = task.get("query")
        source = task.get("source", "web")
        verbose = task.get("verbose")
        if self.websocket and self.stream_output:
            await self.stream_output("logs", "depth_research", f"Running in depth research on the following report topic: {topic}", self.websocket)
        else:
            print_agent_output(f"Running in depth research on the following report topic: {topic}", agent="RESEARCHER")
        normalized_topic = self._normalize_subtopic(topic)
        research_draft = await self.run_subtopic_research(parent_query=parent_query, subtopic=normalized_topic,
                                                          verbose=verbose, source=source, headers=self.headers)
        return {"draft": research_draft}