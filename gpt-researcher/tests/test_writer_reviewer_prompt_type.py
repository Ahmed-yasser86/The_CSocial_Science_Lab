import pytest

from multi_agents.agents.reviewer import ReviewerAgent
from multi_agents.agents.writer import WriterAgent


class DummyTask:
    def __init__(self, prompt_type=None):
        self._prompt_type = prompt_type

    def get(self, key, default=None):
        if key == "model":
            return "dummy-model"
        if key == "prompt_type":
            return self._prompt_type
        if key == "guidelines":
            return ["Follow the report guidelines."]
        if key == "follow_guidelines":
            return True
        return default


@pytest.mark.asyncio
async def test_writer_uses_audience_system_prompt(monkeypatch):
    captured_prompt = {}

    async def fake_call_model(prompt, model=None, response_format=None):
        captured_prompt["prompt"] = prompt
        return {
            "table_of_contents": "",
            "introduction": "",
            "conclusion": "",
            "sources": [],
        }

    monkeypatch.setattr("multi_agents.agents.writer.call_model", fake_call_model)
    agent = WriterAgent()

    await agent.write_sections({
        "title": "Audience Report",
        "research_data": "Evidence details.",
        "task": {"prompt_type": "audience", "model": "dummy-model", "follow_guidelines": True, "guidelines": ["Use audience intelligence style."]},
    })

    system_messages = [m for m in captured_prompt["prompt"] if m["role"] == "system"]
    assert any("Audience Intelligence Analyst" in m["content"] for m in system_messages)
    assert any("downstream embedding report for a RAG pipeline" in m["content"] or "downstream embedding artifact" in m["content"] for m in system_messages)
    assert any("Do not create sections about research design" in m["content"] for m in system_messages)


@pytest.mark.asyncio
async def test_reviewer_adds_audience_review_instructions(monkeypatch):
    captured_prompt = {}

    async def fake_call_model(prompt, model=None):
        captured_prompt["prompt"] = prompt
        return "None"

    monkeypatch.setattr("multi_agents.agents.reviewer.call_model", fake_call_model)
    agent = ReviewerAgent()

    await agent.review_draft({
        "task": {"prompt_type": "audience", "model": "dummy-model", "guidelines": ["Match audience intelligence style."], "follow_guidelines": True},
        "draft": "A draft about audience behavior.",
        "revision_notes": "",
    })

    user_message = next(m for m in captured_prompt["prompt"] if m["role"] == "user")
    assert "audience intelligence and social network analysis report" in user_message["content"].lower()
    assert "do not approve or request academic research design" in user_message["content"].lower()


@pytest.mark.asyncio
async def test_editor_uses_audience_planning_system_prompt(monkeypatch):
    captured_prompt = {}

    async def fake_call_model(prompt, model=None, response_format=None):
        captured_prompt["prompt"] = prompt
        return {"title": "test", "date": "01/01/2025", "sections": ["Audience segments", "Community dynamics"]}

    monkeypatch.setattr("multi_agents.agents.editor.call_model", fake_call_model)
    from multi_agents.agents.editor import EditorAgent

    agent = EditorAgent()
    result = await agent.plan_research({
        "task": {"prompt_type": "audience", "model": "dummy-model", "max_sections": 3},
        "initial_research": "Initial evidence about audience groups.",
    })

    system_messages = [m for m in captured_prompt["prompt"] if m["role"] == "system"]
    assert any("Audience Intelligence Architect" in m["content"] for m in system_messages)
    assert any("Do not include sections on research design" in m["content"] for m in system_messages)
    assert result["sections"] == ["Audience segments", "Community dynamics"]
