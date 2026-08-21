import asyncio

import pytest

from multi_agents.agents.reviser import ReviserAgent


class DummyTask:
    def get(self, key, default=None):
        if key == "model":
            return "dummy-model"
        return default


@pytest.mark.asyncio
async def test_reviser_retries_insufficient_draft_then_returns_final_revision(monkeypatch):
    responses = [
        {"draft": "Draft title only", "revision_notes": "Need more analysis."},
        {"draft": "Draft title with a short sentence.", "revision_notes": "Still too short."},
        {
            "draft": "This final draft contains substantive analysis and evidence for the topic. "
            + "It includes multiple paragraphs, structured discussion, and enough words to be considered a full draft. "
            + "The report explores the subject deeply and provides citations in the style required by the guidelines.",
            "revision_notes": "Final substantive revision.",
        },
    ]
    call_count = {"count": 0}

    async def fake_call_model(prompt, model=None, response_format=None):
        index = call_count["count"]
        call_count["count"] += 1
        return responses[index]

    monkeypatch.setattr("multi_agents.agents.reviser.call_model", fake_call_model)
    agent = ReviserAgent()

    revision = await agent.revise_draft({
        "review": "Please add analysis and evidence.",
        "task": DummyTask(),
        "draft": "Draft title only",
    })

    assert call_count["count"] == 3
    assert revision["draft"] == responses[2]["draft"]
    assert revision["revision_notes"] == responses[2]["revision_notes"]


@pytest.mark.asyncio
async def test_reviser_returns_to_reviewer_after_three_failures(monkeypatch):
    responses = [
        {"draft": "Draft title only", "revision_notes": "Need more analysis."},
        {"draft": "Draft title with a short sentence.", "revision_notes": "Still too short."},
        {"draft": "Another minimal title draft.", "revision_notes": "Still insufficient."},
    ]
    call_count = {"count": 0}

    async def fake_call_model(prompt, model=None, response_format=None):
        index = call_count["count"]
        call_count["count"] += 1
        return responses[index]

    monkeypatch.setattr("multi_agents.agents.reviser.call_model", fake_call_model)
    agent = ReviserAgent()

    revision = await agent.revise_draft({
        "review": "Please add analysis and evidence.",
        "task": DummyTask(),
        "draft": "Draft title only",
    })

    assert call_count["count"] == 3
    assert revision["draft"] == responses[2]["draft"]
    assert revision["revision_notes"] == responses[2]["revision_notes"]
