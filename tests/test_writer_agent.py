import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gpt-researcher"))

from multi_agents.agents.writer import WriterAgent


@pytest.mark.asyncio
async def test_run_returns_fallback_when_layout_is_none(monkeypatch):
    agent = WriterAgent()

    async def fake_write_sections(research_state):
        return None

    async def fake_revise_headers(task, headers):
        return None

    monkeypatch.setattr(agent, "write_sections", fake_write_sections)
    monkeypatch.setattr(agent, "revise_headers", fake_revise_headers)

    research_state = {
        "title": "Example Subject",
        "research_data": {},
        "task": {"verbose": False, "follow_guidelines": False},
        "fact_check_notes": None,
    }

    result = await agent.run(research_state)

    assert result["headers"]["title"] == "Example Subject"
    assert result["table_of_contents"] == ""
    assert result["introduction"] == ""
    assert result["conclusion"] == ""
    assert result["sources"] == []
