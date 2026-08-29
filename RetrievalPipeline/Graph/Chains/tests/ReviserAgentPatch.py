"""
يحمي ReviserAgent.run من الانهيار لو revision رجعت شكل غريب (list/None).
"""
from multi_agents.agents.reviser import ReviserAgent
from multi_agents.agents.utils.views import print_agent_output


def _normalize_revision(revision):
    if isinstance(revision, dict):
        return revision
    if isinstance(revision, list):
        if revision and isinstance(revision[0], dict):
            return revision[0]
        return {"draft": None, "revision_notes": str(revision)}
    return {"draft": None, "revision_notes": str(revision)}


_original_run = ReviserAgent.run


async def _safe_run(self, draft_state: dict):
    print_agent_output("Rewriting draft based on feedback...", agent="REVISOR")
    revision = await self.revise_draft(draft_state)
    revision = _normalize_revision(revision)

    if draft_state.get("task", {}).get("verbose"):
        note = f"Revision notes: {revision.get('revision_notes')}"
        if self.websocket and self.stream_output:
            await self.stream_output("logs", "revision_notes", note, self.websocket)
        else:
            print_agent_output(note, agent="REVISOR")

    return {
        "draft": revision.get("draft"),
        "revision_notes": revision.get("revision_notes"),
    }


ReviserAgent.run = _safe_run
print("✅ Patched ReviserAgent.run: يتعامل مع list/dict/None بأمان")