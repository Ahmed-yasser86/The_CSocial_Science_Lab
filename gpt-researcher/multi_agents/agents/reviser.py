from .utils.views import print_agent_output
from .utils.llms import call_model
from .shared_prompt_instructions import NON_EMPIRICAL_REPORTING_INSTRUCTIONS
import json

sample_revision_notes = """
{
  "draft": { 
    draft title: The revised draft that you are submitting for review 
  },
  "revision_notes": Your message to the reviewer about the changes you made to the draft based on their feedback
}
"""


def _normalize_revision(revision):
    if isinstance(revision, dict):
        return revision
    if isinstance(revision, list):
        if revision and isinstance(revision[0], dict):
            return revision[0]
        return {"draft": None, "revision_notes": str(revision)}
    return {"draft": None, "revision_notes": str(revision)}


def _is_insufficient_draft(draft):
    if not isinstance(draft, str):
        return True
    text = draft.strip()
    if not text:
        return True
    words = text.split()
    if len(words) < 120:
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 1:
        return True
    if len(lines) <= 2 and lines[0].startswith("#"):
        return True
    if len(lines) <= 3 and words[0].lower().startswith("draft") and words[1].lower().startswith("title"):
        return True
    return False


class ReviserAgent:
    def __init__(self, websocket=None, stream_output=None, headers=None):
        self.websocket = websocket
        self.stream_output = stream_output
        self.headers = headers or {}

    async def revise_draft(self, draft_state: dict):
        """
        Review a draft article
        :param draft_state:
        :return:
        """
        review = draft_state.get("review")
        task = draft_state.get("task") or {}
        draft_report = draft_state.get("draft")

        max_attempts = 3
        revision = None

        prompt_type_value = task.get("prompt_type") or draft_state.get("prompt_type")
        prompt_type = getattr(prompt_type_value, "value", prompt_type_value)
        if isinstance(prompt_type, str):
            prompt_type = prompt_type.lower()
        for attempt in range(1, max_attempts + 1):
            extra_instruction = ""
            if attempt > 1:
                extra_instruction = (
                    "\n\nThe previous draft was insufficient: it contained only a title, outline, or too little analysis. "
                    "Regenerate a full substantive draft with evidence-based analysis, citations, audience analysis sections, "
                    "and structured headers/tables. Do not return only a title or empty content."
                )

            audience_instruction = ""
            if prompt_type == "audience":
                audience_instruction = (
                    "\n\nThis is an audience intelligence and social network analysis report. "
                    "Do not generate sections about academic research design, methodology, longitudinal study design, "
                    "time-series analysis, mixed-methods, triangulation, network mapping procedures, or other process-oriented research content. "
                    "Focus the revision on compact audience ecosystem analysis, community dynamics, influence pathways, and evidence-supported behavior patterns. "
                    f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS} "
                    "Prioritize concise, structured, RAG-friendly intelligence output over narrative or academic style."
                )
            elif prompt_type == "ecosystem":
                audience_instruction = (
                    "\n\nThis is an ecosystem intelligence report. "
                    "Keep the revision focused on observable ecosystem relations, audience communities, institutions, opposition, influence pathways, resilience, and network structure. "
                    "Do not turn the draft into biography, subject-only worldview analysis, or generic theory. "
                    "Do not frame the revision as a statistical report, survey, dashboard, or quantitative analysis unless the evidence clearly supports such framing. "
                    f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS} "
                    "Prioritize dense relational and structural analysis over narrative or subject-centric prose."
                )
            elif prompt_type == "subject":
                audience_instruction = (
                    "\n\nThis is a subject intelligence report. "
                    "Keep the revision tightly centered on the subject itself: worldview, identity, ideas, methodology, communication style, positioning, and subject-specific evidence. "
                    "Do not turn the draft into audience composition, ecosystem, followers, community, or social-network behavior analysis. "
                    "Do not frame the revision as a statistical report, survey, dashboard, or quantitative analysis unless the evidence clearly supports such framing. "
                    f"{NON_EMPIRICAL_REPORTING_INSTRUCTIONS} "
                    "Prioritize deep subject-focused analysis over audience-context material."
                )

            prompt = [
                {
                    "role": "system",
                    "content": "You are an expert writer. Your goal is to revise drafts based on reviewer notes.",
                },
                {
                    "role": "user",
                    "content": f"""Draft:\n{draft_report}\nReviewer's notes:\n{review}\n{extra_instruction}{audience_instruction}\n\n
You have been tasked by your reviewer with revising the following draft, which was written by a non-expert.
If you decide to follow the reviewer's notes, please write a new draft and make sure to address all of the points they raised.
Please keep all other aspects of the draft the same.
You MUST return nothing but a JSON in the following format:
{sample_revision_notes}
""",
                },
            ]

            response = await call_model(
                prompt,
                model=task.get("model"),
                response_format="json",
            )
            revision = _normalize_revision(response)
            candidate = revision.get("draft")

            if not _is_insufficient_draft(candidate):
                break

            if attempt < max_attempts:
                if self.websocket and self.stream_output:
                    await self.stream_output(
                        "logs",
                        "revision_notes",
                        "Draft was insufficient; retrying regeneration with stronger instructions.",
                        self.websocket,
                    )
                else:
                    print_agent_output(
                        "Draft was insufficient; retrying regeneration with stronger instructions.",
                        agent="REVISOR",
                    )
                draft_report = candidate or draft_report
                continue

            if self.websocket and self.stream_output:
                await self.stream_output(
                    "logs",
                    "revision_notes",
                    "Draft remained insufficient after multiple attempts; returning to reviewer.",
                    self.websocket,
                )
            else:
                print_agent_output(
                    "Draft remained insufficient after multiple attempts; returning to reviewer.",
                    agent="REVISOR",
                )

        return revision

    async def run(self, draft_state: dict):
        print_agent_output(f"Rewriting draft based on feedback...", agent="REVISOR")
        revision = await self.revise_draft(draft_state)
        revision = _normalize_revision(revision)

        if draft_state.get("task", {}).get("verbose"):
            note = f"Revision notes: {revision.get('revision_notes')}"
            if self.websocket and self.stream_output:
                await self.stream_output(
                    "logs",
                    "revision_notes",
                    note,
                    self.websocket,
                )
            else:
                print_agent_output(note, agent="REVISOR")

        return {
            "draft": revision.get("draft"),
            "revision_notes": revision.get("revision_notes"),
        }
