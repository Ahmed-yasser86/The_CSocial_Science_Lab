from datetime import datetime
import json5 as json
from .utils.views import print_agent_output
from .utils.llms import call_model
from .shared_prompt_instructions import NON_EMPIRICAL_REPORTING_INSTRUCTIONS

sample_json = """
{
  "table_of_contents": A table of contents in markdown syntax (using '-') based on the research headers and subheaders,
  "introduction": An indepth introduction to the topic in markdown syntax and hyperlink references to relevant sources,
  "conclusion": A conclusion to the entire research based on all research data in markdown syntax and hyperlink references to relevant sources,
  "sources": A list with strings of all used source links in the entire research data in markdown syntax and apa citation format. For example: ['-  Title, year, Author [source url](source)', ...]
}
"""


class WriterAgent:
    def __init__(self, websocket=None, stream_output=None, headers=None):
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers

    def get_headers(self, research_state: dict):
        return {
            "title": research_state.get("title"),
            "date": "Date",
            "introduction": "Introduction",
            "table_of_contents": "Table of Contents",
            "conclusion": "Conclusion",
            "references": "References",
        }

    async def write_sections(self, research_state: dict):
        query = research_state.get("title")
        data = research_state.get("research_data")
        task = research_state.get("task") or {}
        prompt_type_value = task.get("prompt_type") or research_state.get("prompt_type")
        prompt_type = getattr(prompt_type_value, "value", prompt_type_value)
        if isinstance(prompt_type, str):
            prompt_type = prompt_type.lower()
        follow_guidelines = task.get("follow_guidelines", False)
        guidelines = task.get("guidelines")

        fact_notes = research_state.get('fact_check_notes')
        fact_notes_str = f"Fact Checker Notes: {fact_notes}. You MUST revise the introduction and conclusion to address these issues.\n" if fact_notes else ""

        if prompt_type == "audience":
            system_content = (
                "You are an Audience Intelligence Analyst, Social Network Analyst, "
                "and Digital Ethnographer/Cyber-anthropologist.\n"
                "Your mission is to convert collected research into a compact, high-density intelligence report optimized for RAG ingestion and embeddings.\n"
                "The output must be concise, structured, token-efficient, and suitable for downstream indexing.\n"
                "Write only evidence-supported audience intelligence findings, community insights, influence relationships, and social network behavior observations.\n"
                "Do not use academic research paper style, narrative storytelling, or process-oriented language.\n"
                "Do not add introductions, conclusions, background, methodology, source selection, or research process descriptions.\n"
                "Do not create sections about research design, methodology, longitudinal analysis, mixed-methods, triangulation, network mapping, or academic process content.\n"
                "Do not create sections that function as academic research design, methodology, or process descriptions.\n"
                "Treat each sentence as a discrete knowledge item that supports retrieval and analysis.\n"
                "Avoid filler, transitions, summaries, and repeated commentary.\n"
                "Use short structured paragraphs or bullet-style analytical statements when appropriate.\n"
                "Preserve uncertainty whenever evidence is incomplete.\n"
                "Clearly distinguish evidence from inference.\n"
                "Do not create sections unrelated to audience intelligence, social network analysis, influence dynamics, community structure, or ecosystem behavior.\n"
                f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS}\n"
                "This report is a downstream embedding artifact, not a human-readable essay.\n"
            )
        elif prompt_type == "ecosystem":
            system_content = (
                "You are an Ecosystem Intelligence Writer and Social Systems Analyst.\n"
                "Your mission is to convert collected evidence into a compact, high-density ecosystem intelligence report optimized for RAG ingestion and embeddings.\n"
                "Write only evidence-supported findings about communities, institutions, influence flows, opposition, network structure, resilience, and observable ecosystem behavior.\n"
                "Do not turn the report into biography, subject-only ideology analysis, or abstract theory.\n"
                "Do not use academic research paper style, narrative storytelling, or process-oriented language.\n"
                "Do not add introductions, conclusions, background, methodology, or research process descriptions.\n"
                "Treat each sentence as a discrete knowledge item that supports retrieval and analysis.\n"
                "Preserve uncertainty whenever evidence is incomplete.\n"
                "Clearly distinguish evidence from inference.\n"
                f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS}\n"
                "This report is a downstream embedding artifact, not a human-readable essay.\n"
            )
        else:
            system_content = (
                "You are the Subject Intelligence Writer.\n"
                "This run is explicitly scoped to the subject only.\n"
                "Your main task is to transform the collected research into a clear, structured subject intelligence report.\n"
                "\n"
                "Write only what is supported by the collected evidence.\n"
                "Focus on knowledge extraction rather than narrative writing.\n"
                "Prefer analysis over storytelling.\n"
                "Prefer mechanisms, patterns, relationships, and evidence over commentary.\n"
                "\n"
                "Keep the report tightly centered on the subject itself: worldview, identity, ideas, methodology, communication style, positioning, and subject-specific evidence.\n"
                "Do not turn the report into audience composition, followers, community, ecosystem, diffusion, or social-network behavior analysis unless those points appear only as secondary context.\n"
                "Do not frame the report as a statistical report, survey, dashboard, or quantitative analysis unless the evidence clearly supports such framing.\n"
                "Do not add unnecessary introductions, transitions, summaries, filler, or stylistic commentary.\n"
                "Every paragraph should contribute directly to understanding the subject.\n"
                "Avoid repeating information across sections.\n"
                "\n"
                "Preserve uncertainty whenever evidence is incomplete.\n"
                "Clearly distinguish evidence from inference.\n"
                "\n"
                "This report is not the final research output.\n"
                "It will serve as source material for a separate scientific research agent that will perform deeper analysis, hypothesis generation, and academic reasoning.\n"
                "Therefore, prioritize completeness, traceability, evidence density, and analytical clarity over writing style.\n"
                "Produce a report that is information-dense, well organized, and optimized for downstream intelligence analysis rather than human-oriented storytelling.\n"
                "Do not include a methodology section explaining how data was collected, searched, sampled, or analyzed.\n"
                "Do not discuss research methods, search strategy, evidence collection workflow, source selection, or the analytical pipeline unless explicitly requested.\n"
                "Focus on presenting verified findings and analysis, not the research process.\n"
                "Prioritize a dense, information-rich report that maximizes understanding of the subject.\n"
                "Every section should contribute substantive knowledge supported by traceable evidence.\n"
                "Do not spend report space evaluating the research process or discussing source availability unless it materially affects confidence in a finding.\n"
                f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS}\n"
                "Use concise source attribution only where necessary."
            )

        prompt = [
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                "content": f"Today's date is {datetime.now().strftime('%d/%m/%Y')}\n."
                f"Query or Topic: {query}\n"
                f"Research data: {str(data)}\n"
                f"{fact_notes_str}"
                f"Your task is to write an in depth, well written and detailed report based on the research data.\n"
                f"Do not include headers in the results.\n"
                f"{f'You must follow the guidelines provided: {guidelines}' if follow_guidelines else ''}"
                f"You MUST return nothing but a JSON in the following format (without json markdown):\n"
                f"{sample_json}\n\n"
                f"Do not add unnecessary introductions, conclusions, transitions, recommendations, or stylistic commentary.\n"
                f"Do not generate a table of contents or any document-oriented formatting that is not required for downstream analysis.\n"
                f"Do not repeat findings that already appear in the research sections. Preserve the original section content and avoid redundant summaries.\n\n"
            },
        ]

        response = await call_model(
            prompt,
            task.get("model"),
            response_format="json",
        )
        return response

    async def revise_headers(self, task: dict, headers: dict):
        prompt = [
            {
                "role": "system",
                "content": """You are a research writer. 
Your sole purpose is to revise the headers data based on the given guidelines.""",
            },
            {
                "role": "user",
                "content": f"""Your task is to revise the given headers JSON based on the guidelines given.
You are to follow the guidelines but the values should be in simple strings, ignoring all markdown syntax.
You must return nothing but a JSON in the same format as given in headers data.
Guidelines: {task.get("guidelines")}\n
Headers Data: {headers}\n
""",
            },
        ]

        response = await call_model(
            prompt,
            task.get("model"),
            response_format="json",
        )
        return {"headers": response}

    async def run(self, research_state: dict):
        task = research_state.get("task") or {}

        if self.websocket and self.stream_output:
            await self.stream_output(
                "logs",
                "writing_report",
                f"Writing final research report based on research data...",
                self.websocket,
            )
        else:
            print_agent_output(
                f"Writing final research report based on research data...",
                agent="WRITER",
            )

        research_layout_content = await self.write_sections(research_state)
        if not isinstance(research_layout_content, dict):
            research_layout_content = {}

        fallback_layout = {
            "table_of_contents": "",
            "introduction": "",
            "conclusion": "",
            "sources": [],
        }
        research_layout_content = {**fallback_layout, **research_layout_content}

        if task.get("verbose"):
            if self.websocket and self.stream_output:
                research_layout_content_str = json.dumps(
                    research_layout_content, indent=2
                )
                await self.stream_output(
                    "logs",
                    "research_layout_content",
                    research_layout_content_str,
                    self.websocket,
                )
            else:
                print_agent_output(research_layout_content, agent="WRITER")

        headers = self.get_headers(research_state)
        if task.get("follow_guidelines"):
            if self.websocket and self.stream_output:
                await self.stream_output(
                    "logs",
                    "rewriting_layout",
                    "Rewriting layout based on guidelines...",
                    self.websocket,
                )
            else:
                print_agent_output(
                    "Rewriting layout based on guidelines...", agent="WRITER"
                )
            revised_headers = await self.revise_headers(task=task, headers=headers)
            if isinstance(revised_headers, dict):
                headers = revised_headers.get("headers") or headers
            if not isinstance(headers, dict):
                headers = self.get_headers(research_state)

        return {**research_layout_content, "headers": headers}
