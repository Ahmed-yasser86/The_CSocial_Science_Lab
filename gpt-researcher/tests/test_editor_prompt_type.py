import asyncio

from multi_agents.agents.editor import EditorAgent
from multi_agents.agents.prompt_type import PromptType


class DummyModelResponse:
    def __init__(self):
        self.called = False


async def fake_call_model(*, prompt, model, response_format):
    DummyModelResponse.called = True
    return {"title": "Audience plan", "date": "01/01/2026", "sections": ["Segment A", "Segment B"]}


def test_plan_research_uses_prompt_type_from_task(monkeypatch):
    async def run_test():
        monkeypatch.setattr("multi_agents.agents.editor.call_model", fake_call_model)

        agent = EditorAgent()
        research_state = {
            "initial_research": "Initial audience summary",
            "task": {
                "include_human_feedback": False,
                "max_sections": 3,
                "model": "test-model",
                "prompt_type": "audience",
            },
        }

        result = await agent.plan_research(research_state)

        assert result["title"] == "Audience plan"
        assert result["sections"] == ["Segment A", "Segment B"]
        assert DummyModelResponse.called is True

    asyncio.run(run_test())
