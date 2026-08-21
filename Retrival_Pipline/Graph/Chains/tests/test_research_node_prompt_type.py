import importlib.util
import os
import pathlib
import sys

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

# Ensure direct imports of local test helpers like mcp_config resolve when loaded dynamically.
TESTS_ROOT = pathlib.Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

GPT_RESEARCHER_DIR = pathlib.Path(__file__).resolve().parents[4] / "gpt-researcher"
if str(GPT_RESEARCHER_DIR) not in sys.path:
    sys.path.insert(0, str(GPT_RESEARCHER_DIR))

from Nodes.GPT_ResearcherNode.ResearchNode import make_research
import multi_agents.agents.researcher as researcher_module
from multi_agents.agents.researcher import ResearchAgent
from multi_agents.agents.editor import EditorAgent
from multi_agents.agents.prompt_type import PromptType
import subject_intelligence


def import_audience_profile_layer():
    module_path = TESTS_DIR / "Audience_Profile_Layer.py"
    spec = importlib.util.spec_from_file_location("Audience_Profile_Layer", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_make_research_forwards_prompt_type_from_state(monkeypatch):
    captured = {}

    async def fake_conduct_multi_agent_research(
        query,
        max_sections,
        follow_guidelines,
        verbose,
        prompt_type,
        mcp_configs,
        mcp_strategy,
        guidelines=None,
        **kwargs,
    ):
        captured.update(
            {
                "query": query,
                "max_sections": max_sections,
                "follow_guidelines": follow_guidelines,
                "verbose": verbose,
                "prompt_type": prompt_type,
                "mcp_configs": mcp_configs,
                "mcp_strategy": mcp_strategy,
            }
        )
        return {"research_data": [], "title": "test", "report": "ok"}

    monkeypatch.setattr(
        "Nodes.GPT_ResearcherNode.ResearchNode.conduct_multi_agent_research",
        fake_conduct_multi_agent_research,
    )

    state = {
        "user_initial_query": "query",
        "chain_input": {
            "query": "search",
            "max_sections": 3,
            "follow_guidelines": True,
            "verbose": False,
        },
        "prompt_type": "audience",
        "research_iteration": 0,
    }

    result = await make_research(state)

    assert result["profile_candidates"][0]["title"] == "test"
    assert captured["prompt_type"] == "audience"


@pytest.mark.asyncio
async def test_make_research_forwards_prompt_type_from_chain_input(monkeypatch):
    captured = {}

    async def fake_conduct_multi_agent_research(
        query,
        max_sections,
        follow_guidelines,
        verbose,
        prompt_type,
        mcp_configs,
        mcp_strategy,
        guidelines=None,
        **kwargs,
    ):
        captured["prompt_type"] = prompt_type
        return {"research_data": [], "title": "test", "report": "ok"}

    monkeypatch.setattr(
        "Nodes.GPT_ResearcherNode.ResearchNode.conduct_multi_agent_research",
        fake_conduct_multi_agent_research,
    )

    state = {
        "user_initial_query": "query",
        "chain_input": {
            "query": "search",
            "max_sections": 3,
            "follow_guidelines": True,
            "verbose": False,
            "prompt_type": "subject",
        },
        "research_iteration": 0,
    }

    await make_research(state)
    assert captured["prompt_type"] == "subject"


@pytest.mark.asyncio
async def test_make_research_forwards_guidelines_from_chain_input(monkeypatch):
    captured = {}

    async def fake_conduct_multi_agent_research(
        query,
        max_sections,
        follow_guidelines,
        verbose,
        prompt_type,
        mcp_configs,
        mcp_strategy,
        guidelines=None,
    ):
        captured["guidelines"] = guidelines
        return {"research_data": [], "title": "test", "report": "ok"}

    monkeypatch.setattr(
        "Nodes.GPT_ResearcherNode.ResearchNode.conduct_multi_agent_research",
        fake_conduct_multi_agent_research,
    )

    subject_guidelines = ["Focus only on the subject's worldview and methodology."]
    state = {
        "user_initial_query": "query",
        "chain_input": {
            "query": "search",
            "max_sections": 3,
            "follow_guidelines": True,
            "verbose": False,
            "guidelines": subject_guidelines,
            "prompt_type": "subject",
        },
        "research_iteration": 0,
    }

    await make_research(state)

    assert captured["guidelines"] == subject_guidelines


def test_subject_planning_prompt_scopes_to_subject_only():
    agent = EditorAgent()
    prompt = agent._create_planning_prompt("", False, None, 4, PromptType.SUBJECT)
    system_message = prompt[0]["content"]

    assert "subject only" in system_message.lower()
    assert "audience" in system_message.lower() or "community" in system_message.lower()
    assert "followers" in system_message.lower() or "community" in system_message.lower()
    assert "statistical" in system_message.lower()
    assert "quantitative" in system_message.lower()


def test_ecosystem_planning_prompt_scopes_to_ecosystem_only():
    agent = EditorAgent()
    prompt = agent._create_planning_prompt("", False, None, 4, PromptType.ECOSYSTEM)
    system_message = prompt[0]["content"]

    assert "ecosystem" in system_message.lower()
    assert "audience" in system_message.lower() or "community" in system_message.lower()
    assert "statistical" in system_message.lower()
    assert "quantitative" in system_message.lower()


def test_subject_intelligence_state_includes_mcp_configs(monkeypatch):
    captured = {}

    async def fake_make_research(state):
        captured["state"] = state
        return {"report": "ok"}

    monkeypatch.setattr(subject_intelligence, "make_research", fake_make_research)

    fake_configs = [{"name": "socialcrawl", "connection_url": "https://example.test/mcp"}]
    monkeypatch.setattr(subject_intelligence, "build_audience_mcp_configs", lambda: fake_configs)

    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
        handle.write("sample profile")
        profile_path = handle.name

    async def run_test():
        await subject_intelligence.run_subject_intelligence(
            subject_name="Test Subject",
            profile_path=profile_path,
            short_query="test",
            max_sections=2,
        )

    import asyncio
    asyncio.run(run_test())

    assert captured["state"]["chain_input"]["mcp_configs"] == fake_configs
    assert captured["state"]["mcp_configs"] == fake_configs


def test_build_audience_mcp_configs_includes_socialcrawl_and_gdelt(monkeypatch):
    monkeypatch.setenv("SOCIALCRAWL_MCP_API_KEY", "socialcrawl-key")
    monkeypatch.setenv("GDELT_MCP_API_KEY", "gdelt-key")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("GDELT_API_KEY", raising=False)

    module = import_audience_profile_layer()
    configs = module.build_audience_mcp_configs()

    assert len(configs) == 2
    assert {cfg["name"] for cfg in configs} == {"socialcrawl", "gdelt-cloud"}
    assert configs[0]["connection_headers"]["x-api-key"] == "socialcrawl-key"
    assert configs[1]["connection_headers"]["Authorization"] == "Bearer gdelt-key"


@pytest.mark.asyncio
async def test_make_research_passes_gdelt_mcp_config_from_builder(monkeypatch):
    captured = {}

    async def fake_conduct_multi_agent_research(
        query,
        max_sections,
        follow_guidelines,
        verbose,
        prompt_type,
        mcp_configs,
        mcp_strategy,
        guidelines=None,
        **kwargs,
    ):
        captured.update(
            {
                "prompt_type": prompt_type,
                "mcp_configs": mcp_configs,
            }
        )
        return {"research_data": [], "title": "test", "report": "ok"}

    monkeypatch.setattr(
        "Nodes.GPT_ResearcherNode.ResearchNode.conduct_multi_agent_research",
        fake_conduct_multi_agent_research,
    )
    monkeypatch.setenv("SOCIALCRAWL_MCP_API_KEY", "socialcrawl-key")
    monkeypatch.setenv("GDELT_MCP_API_KEY", "gdelt-key")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("GDELT_API_KEY", raising=False)

    module = import_audience_profile_layer()
    state = {
        "user_initial_query": "query",
        "chain_input": {
            "query": "search",
            "max_sections": 3,
            "follow_guidelines": True,
            "verbose": False,
            "prompt_type": "audience",
            "mcp_configs": module.build_audience_mcp_configs(),
        },
        "prompt_type": "audience",
        "research_iteration": 0,
    }

    await make_research(state)

    assert captured["prompt_type"] == "audience"
    assert len(captured["mcp_configs"]) == 2
    assert {cfg["name"] for cfg in captured["mcp_configs"]} == {"socialcrawl", "gdelt-cloud"}
    gdelt_config = next(cfg for cfg in captured["mcp_configs"] if cfg["name"] == "gdelt-cloud")
    assert gdelt_config["connection_headers"]["Authorization"] == "Bearer gdelt-key"


@pytest.mark.asyncio
async def test_make_research_preserves_prompt_type_and_mcp_configs_across_retries(monkeypatch):
    captured_calls = []

    async def fake_conduct_multi_agent_research(
        query,
        max_sections,
        follow_guidelines,
        verbose,
        prompt_type,
        mcp_configs,
        mcp_strategy,
        guidelines=None,
        **kwargs,
    ):
        captured_calls.append(
            {
                "prompt_type": prompt_type,
                "mcp_configs": mcp_configs,
                "mcp_strategy": mcp_strategy,
            }
        )
        return {"research_data": [], "title": "test", "report": "ok"}

    monkeypatch.setattr(
        "Nodes.GPT_ResearcherNode.ResearchNode.conduct_multi_agent_research",
        fake_conduct_multi_agent_research,
    )
    monkeypatch.setenv("SOCIALCRAWL_MCP_API_KEY", "socialcrawl-key")
    monkeypatch.setenv("GDELT_MCP_API_KEY", "gdelt-key")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("GDELT_API_KEY", raising=False)

    module = import_audience_profile_layer()
    state = {
        "user_initial_query": "query",
        "chain_input": {
            "query": "search",
            "max_sections": 3,
            "follow_guidelines": True,
            "verbose": False,
            "prompt_type": "audience",
            "mcp_configs": module.build_audience_mcp_configs(),
            "mcp_strategy": "fast",
        },
        "prompt_type": "audience",
        "mcp_configs": module.build_audience_mcp_configs(),
        "mcp_strategy": "fast",
        "research_iteration": 0,
    }

    await make_research(state)
    await make_research(state)

    assert len(captured_calls) == 2
    assert all(call["prompt_type"] == "audience" for call in captured_calls)
    assert all(call["mcp_strategy"] == "fast" for call in captured_calls)
    assert len(captured_calls[0]["mcp_configs"]) == 2
    assert {cfg["name"] for cfg in captured_calls[0]["mcp_configs"]} == {"socialcrawl", "gdelt-cloud"}
    assert captured_calls[0]["mcp_configs"] == captured_calls[1]["mcp_configs"]


@pytest.mark.asyncio
async def test_make_research_passes_multiple_mcp_servers(monkeypatch):
    captured = {}

    async def fake_conduct_multi_agent_research(
        query,
        max_sections,
        follow_guidelines,
        verbose,
        prompt_type,
        mcp_configs,
        mcp_strategy,
    ):
        captured.update(
            {
                "prompt_type": prompt_type,
                "mcp_configs": mcp_configs,
            }
        )
        return {"research_data": [], "title": "test", "report": "ok"}

    monkeypatch.setattr(
        "Nodes.GPT_ResearcherNode.ResearchNode.conduct_multi_agent_research",
        fake_conduct_multi_agent_research,
    )
    monkeypatch.setenv("SOCIALCRAWL_MCP_API_KEY", "socialcrawl-key")
    monkeypatch.setenv("GDELT_MCP_API_KEY", "gdelt-key")
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("GDELT_API_KEY", raising=False)

    module = import_audience_profile_layer()
    state = {
        "user_initial_query": "query",
        "chain_input": {
            "query": "search",
            "max_sections": 3,
            "follow_guidelines": True,
            "verbose": False,
            "prompt_type": "audience",
            "mcp_configs": module.build_audience_mcp_configs(),
        },
        "prompt_type": "audience",
        "research_iteration": 0,
    }

    await make_research(state)

    assert captured["prompt_type"] == "audience"
    assert len(captured["mcp_configs"]) == 2
    assert {cfg["name"] for cfg in captured["mcp_configs"]} == {"socialcrawl", "gdelt-cloud"}


@pytest.mark.asyncio
async def test_research_agent_preserves_three_mcp_configs_for_subtopic_research(monkeypatch):
    captured = []

    class FakeGPTResearcher:
        def __init__(self, *args, mcp_configs=None, **kwargs):
            self.mcp_configs = mcp_configs
            self.query = kwargs.get('query') or (args[0] if args else None)
            captured.append(mcp_configs)

        async def conduct_research(self):
            return None

        async def write_report(self):
            return {"query": self.query, "mcp_configs": self.mcp_configs}

    monkeypatch.setattr(
        researcher_module,
        "GPTResearcher",
        FakeGPTResearcher,
    )

    three_mcp_configs = [
        {
            "name": "socialcrawl",
            "connection_url": "https://mcp.socialcrawl.dev/mcp",
            "connection_type": "streamable_http",
            "connection_headers": {"x-api-key": "socialcrawl-key"},
        },
        {
            "name": "gdelt-cloud",
            "connection_url": "https://gdelt-cloud-mcp.fastmcp.app/mcp",
            "connection_type": "streamable_http",
            "connection_headers": {"Authorization": "Bearer gdelt-key"},
        },
        {
            "name": "third-mcp",
            "connection_url": "https://third-mcp.example.com/mcp",
            "connection_type": "streamable_http",
            "connection_headers": {"Authorization": "Bearer third-key"},
        },
    ]

    agent = ResearchAgent(mcp_configs=three_mcp_configs)

    await agent.run_subtopic_research(parent_query="query", subtopic="subtopic", verbose=False, source="web")
    await agent.run_subtopic_research(parent_query="query", subtopic="another topic", verbose=False, source="web")

    assert len(captured) == 2
    assert all(cfg is not None and len(cfg) == 3 for cfg in captured)
    assert {server["name"] for cfg in captured for server in cfg} == {"socialcrawl", "gdelt-cloud", "third-mcp"}


@pytest.mark.asyncio
async def test_make_research_accepts_three_mcp_servers_in_one_request(monkeypatch):
    captured = {}

    async def fake_conduct_multi_agent_research(
        query,
        max_sections,
        follow_guidelines,
        verbose,
        prompt_type,
        mcp_configs,
        mcp_strategy,
    ):
        captured.update(
            {
                "prompt_type": prompt_type,
                "mcp_configs": mcp_configs,
            }
        )
        return {"research_data": [], "title": "test", "report": "ok"}

    monkeypatch.setattr(
        "Nodes.GPT_ResearcherNode.ResearchNode.conduct_multi_agent_research",
        fake_conduct_multi_agent_research,
    )

    state = {
        "user_initial_query": "query",
        "chain_input": {
            "query": "search",
            "max_sections": 3,
            "follow_guidelines": True,
            "verbose": False,
            "prompt_type": "audience",
            "mcp_configs": [
                {
                    "name": "socialcrawl",
                    "connection_url": "https://mcp.socialcrawl.dev/mcp",
                    "connection_type": "streamable_http",
                    "connection_headers": {"x-api-key": "socialcrawl-key"},
                },
                {
                    "name": "gdelt-cloud",
                    "connection_url": "https://gdelt-cloud-mcp.fastmcp.app/mcp",
                    "connection_type": "streamable_http",
                    "connection_headers": {"Authorization": "Bearer gdelt-key"},
                },
                {
                    "name": "third-mcp",
                    "connection_url": "https://third-mcp.example.com/mcp",
                    "connection_type": "streamable_http",
                    "connection_headers": {"Authorization": "Bearer third-key"},
                },
            ],
        },
        "prompt_type": "audience",
        "research_iteration": 0,
    }

    await make_research(state)

    assert captured["prompt_type"] == "audience"
    assert len(captured["mcp_configs"]) == 3
    assert {cfg["name"] for cfg in captured["mcp_configs"]} == {
        "socialcrawl",
        "gdelt-cloud",
        "third-mcp",
    }


def test_gdelt_mcp_url_and_bearer_auth_match_documentation(monkeypatch):
    monkeypatch.setenv(
        "GDELT_API_KEY",
        "gdelt_sk_test_env_key_0000000000000000000000000000",
    )
    monkeypatch.delenv("SOCIALCRAWL_MCP_API_KEY", raising=False)
    monkeypatch.delenv("MCP_API_KEY", raising=False)

    module = import_audience_profile_layer()
    configs = module.build_audience_mcp_configs()

    gdelt_config = next(cfg for cfg in configs if cfg["name"] == "gdelt-cloud")

    assert gdelt_config["connection_url"] == "https://gdelt-cloud-mcp.fastmcp.app/mcp"
    assert gdelt_config["connection_headers"]["Authorization"] == (
        "Bearer gdelt_sk_test_env_key_0000000000000000000000000000"
    )
    assert gdelt_config["headers"]["Authorization"] == (
        "Bearer gdelt_sk_test_env_key_0000000000000000000000000000"
    )
