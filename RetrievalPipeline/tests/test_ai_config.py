"""Tests for the dynamic AI service catalog and safe .env writing."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from agent_server import app, apply_env_values


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_ai_config_endpoint(client):
    res = client.get("/api/agent/ai-config")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["services"], list) and len(body["services"]) >= 9
    # GPT Research Large/Medium/Small tiers are present
    tiers = {s["name"]: s.get("tier") for s in body["services"]}
    assert tiers.get("Strategic LLM") == "Large"
    assert tiers.get("Smart LLM") == "Medium"
    assert tiers.get("Fast LLM") == "Small"
    # providers are exposed (source of truth for the UI)
    assert "openai" in body["providers"] and "google_genai" in body["providers"]
    # current values reflect the process environment
    assert "STRATEGIC_LLM" in body["values"]


def test_apply_env_values_preserves_unknown_and_updates_process():
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
        f.write("# header comment\nFAST_LLM=old_initial\nUNKNOWN_KEY=preserve_me\n")
        path = f.name
    try:
        written = apply_env_values(
            {"FAST_LLM": "openai:gpt-4o", "COHERE_API_KEY": "secret-abc"},
            path=path,
        )
        assert "FAST_LLM" in written and "COHERE_API_KEY" in written
        content = open(path, encoding="utf-8").read()
        # new values present, unknown key + comment preserved, old known line gone
        assert "FAST_LLM=openai:gpt-4o" in content
        assert "FAST_LLM=old_initial" not in content
        assert "COHERE_API_KEY=secret-abc" in content
        assert "UNKNOWN_KEY=preserve_me" in content
        assert "# header comment" in content
        # process environment updated so the next pipeline run picks it up
        assert os.environ["FAST_LLM"] == "openai:gpt-4o"
    finally:
        os.remove(path)
