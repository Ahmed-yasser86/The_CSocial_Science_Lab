from .utils.views import print_agent_output
from .utils.llms import call_model
from .shared_prompt_instructions import NON_EMPIRICAL_REPORTING_INSTRUCTIONS

TEMPLATE = """You are an expert intelligence reviewer. "
Your goal is to review drafts for downstream intelligence ingestion, evidence density, and guideline compliance. "
"""


class ReviewerAgent:
    def __init__(self, websocket=None, stream_output=None, headers=None):
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers or {}

    async def review_draft(self, draft_state: dict):
        """
        Review a draft article
        :param draft_state:
        :return:
        """
        task = draft_state.get("task") or {}
        prompt_type_value = task.get("prompt_type") or draft_state.get("prompt_type")
        prompt_type = getattr(prompt_type_value, "value", prompt_type_value)
        if isinstance(prompt_type, str):
            prompt_type = prompt_type.lower()
        guidelines = "- ".join(guideline for guideline in task.get("guidelines") or [])
        revision_notes = draft_state.get("revision_notes")

        revise_prompt = f"""The reviser has already revised the draft based on your previous review notes with the following feedback:
{revision_notes}\n
Please provide additional feedback ONLY if critical since the reviser has already made changes based on your previous feedback.
If you think the article is sufficient or that non critical revisions are required, please aim to return None.
"""

        audience_instruction = ""
        if prompt_type == "audience":
            audience_instruction = (
                "This is an audience intelligence and social network analysis report. "
                "Do not approve or request academic research design, methodology, longitudinal analysis, "
                "mixed-methods, triangulation, network mapping procedure, or other process-oriented research sections. "
                "Do not approve narrative, introductory, conclusion, or background sections that do not add discrete intelligence content. "
                "Focus on whether the draft is concise, structured, and optimized for RAG ingestion with evidence-supported audience findings. "
                f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS} "
                "If the draft includes unrelated methodological or academic planning headings, mark them as inappropriate and request revision.\n"
            )
        elif prompt_type == "ecosystem":
            audience_instruction = (
                "This is an ecosystem intelligence report. "
                "Keep the draft centered on observable ecosystem behavior: communities, institutions, audiences, opposition, influence paths, network structure, resilience, and relationships. "
                "Do not approve or request biography, subject-only ideology sections, or generic academic methodology sections. "
                "Do not approve statistical, survey, dashboard, or quantitative framing unless evidence clearly supports it. "
                "If the draft drifts into subject biography or abstract theory, mark it as inappropriate and request revision. "
                f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS} "
                "Prioritize observable ecosystem dynamics and evidence-supported relational analysis.\n"
            )
        elif prompt_type == "subject":
            audience_instruction = (
                "This is a subject intelligence report. "
                "Keep the draft tightly centered on the subject itself: worldview, identity, ideas, methodology, communication style, positioning, and other subject-specific dimensions. "
                "Do not approve or request audience composition, followers, community, ecosystem, diffusion, or social-network behavior sections as core content. "
                "Do not approve statistical, survey, dashboard, or quantitative analysis sections unless the evidence clearly supports such framing. "
                "If the draft drifts into audience or community analysis, mark it as inappropriate and request revision. "
                f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS} "
                "Prioritize evidence about the subject over background or audience-context material.\n"
            )

        review_prompt = f"""You have been tasked with reviewing the draft which was written by a non-expert based on specific guidelines.
Please accept the draft if it is good enough to publish, or send it for revision, along with your notes to guide the revision.
If not all of the guideline criteria are met, you should send appropriate revision notes.
If the draft meets all the guidelines, please return None.
{audience_instruction}{revise_prompt if revision_notes else ""}

Guidelines: {guidelines}\nDraft: {draft_state.get("draft")}\n
"""
        prompt = [
            {"role": "system", "content": TEMPLATE},
            {"role": "user", "content": review_prompt},
        ]

        response = await call_model(prompt, model=task.get("model"))

        if task.get("verbose"):
            if self.websocket and self.stream_output:
                await self.stream_output(
                    "logs",
                    "review_feedback",
                    f"Review feedback is: {response}...",
                    self.websocket,
                )
            else:
                print_agent_output(
                    f"Review feedback is: {response}...", agent="REVIEWER"
                )

        from .utils.none_sentinels import is_none_accept_response

        if is_none_accept_response(response):
            return None
        return response

    async def run(self, draft_state: dict):
        task = draft_state.get("task") or {}
        guidelines = task.get("guidelines")
        to_follow_guidelines = task.get("follow_guidelines")
        review = None
        if to_follow_guidelines:
            print_agent_output(f"Reviewing draft...", agent="REVIEWER")

            if task.get("verbose"):
                print_agent_output(
                    f"Following guidelines {guidelines}...", agent="REVIEWER"
                )

            review = await self.review_draft(draft_state)
        else:
            print_agent_output(f"Ignoring guidelines...", agent="REVIEWER")
        out = {"review": review}
        if review is not None:
            out["draft_revision_count"] = draft_state.get("draft_revision_count", 0) + 1
        return out
