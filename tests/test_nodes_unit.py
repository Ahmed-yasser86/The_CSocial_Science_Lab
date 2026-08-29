"""
Unit tests for the Graph retrieval pipeline nodes.

These tests run **offline** (no API keys, no network, no vector DB) by mocking
the heavy dependencies: the chat model used for compression, the GPT-Researcher
multi-agent research call, the Tavily web search backend, and the vector-store
retriever.

Covered:
  * Pure helpers: query builders, normalizers, formatters, result normalizers
  * Compression node: empty-report branch (no LLM) + mocked-LLM branch
  * Research node: raw-result normalization + mock of conduct_multi_agent_research
  * Retrieval / web-search nodes with mocked backends
  * Orchestration nodes (subject / audience / ecosystem / summarization) with
    their heavy dependencies mocked
"""

import asyncio
import os
import tempfile
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from RetrievalPipeline.Graph.StateGraph import GraphState
from RetrievalPipeline.Graph.Nodes import web_search as web_search_module
from RetrievalPipeline.Graph.Nodes.CompressionNode import (
    compress_intelligence_report,
    compress_subject_intelligence,
    format_compressed_for_injection,
    research_compressor_node,
)
from RetrievalPipeline.Graph.Nodes.GPT_ResearcherNode import ResearchNode as research_node_module
from RetrievalPipeline.Graph.Nodes.SubjectIntelligenceNode import SubjectIntelligenceNode as subject_module
from RetrievalPipeline.Graph.Nodes.AudienceIntelligenceNode import AudienceIntelligenceNode as audience_module
from RetrievalPipeline.Graph.Nodes.EcosystemIntelligenceNode import EcosystemIntelligenceNode as ecosystem_module
from RetrievalPipeline.Graph.Nodes.ProfileSummarizationNode import ProfileSummarizationNode as profile_module
from RetrievalPipeline.Graph.Nodes import retrive as retrive_module
from RetrievalPipeline.Graph.Nodes.IdentityResearchNode import IdentityResearchNode as identity_module
from RetrievalPipeline.Graph.Chains.tests import mcp_config as mcp_config_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_state() -> GraphState:
    return {
        "user_initial_query": "Test Subject",
        "mcp_strategy": "fast",
        "reports": {},
        "input_paths": {},
    }


@pytest.fixture
def fake_compressed() -> Dict[str, str]:
    return {
        "covered_topics": "- topic A\n- topic B",
        "confirmed_positions": "- position X",
        "available_insights": "Some insight text.",
        "profile_context": "Context about the subject.",
        "intelligence_type": "subject",
        "source_report": "subject",
        "compression_timestamp": "2026-01-01T00:00:00",
    }


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def test_normalize_query_for_tavily_truncates():
    long_q = "A" * 500 + " tail"
    out = web_search_module.normalize_query_for_tavily(long_q)
    assert len(out) <= 400
    assert out.startswith("A")


def test_normalize_query_for_tavily_handles_non_str():
    assert web_search_module.normalize_query_for_tavily(None) == ""
    assert web_search_module.normalize_query_for_tavily(123) == "123"
    assert web_search_module.normalize_query_for_tavily("  spaced  ").strip() == "spaced"


def test_build_subject_query_contains_inputs():
    q = subject_module.build_subject_query("Sheikh X", "PROFILE TEXT")
    assert "Sheikh X" in q
    assert "PROFILE TEXT" in q
    assert "Identity & Worldview Layer" in q
    assert "RESEARCH FRAMEWORKS" in q


def test_build_audience_query_contains_inputs():
    q = audience_module.build_audience_query("Sheikh X", "PROFILE", "SUMMARY")
    assert "Sheikh X" in q
    assert "PROFILE" in q
    assert "SUMMARY" in q
    assert "Audience Profile Layer" in q
    assert "Diffusion & Recruitment Layer" in q


def test_build_ecosystem_query_contains_inputs():
    q = ecosystem_module.build_ecosystem_query("Sheikh X", "SUBJ", "AUD")
    assert "Sheikh X" in q
    assert "SUBJ" in q
    assert "AUD" in q
    assert "Macro Environmental Context Layer" in q
    assert "Systemic Risk & Vulnerability Layer" in q


def test_resolve_report_path():
    # None input
    assert ecosystem_module._resolve_report_path(None) is None
    # Existing absolute path
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tf:
        path = tf.name
    try:
        assert ecosystem_module._resolve_report_path(path) == path
    finally:
        os.remove(path)
    # Non-existing path
    assert ecosystem_module._resolve_report_path("does/not/exist.md") is None


# ---------------------------------------------------------------------------
# Compression node
# ---------------------------------------------------------------------------

def test_format_compressed_for_injection_full(fake_compressed):
    out = format_compressed_for_injection(fake_compressed)
    assert "SUBJECT INTELLIGENCE BRIEFING" in out
    assert "PREVIOUSLY COVERED TOPICS" in out
    assert "ESTABLISHED CONTEXT" in out
    assert "AVAILABLE INSIGHTS" in out
    assert "PROFILE CONTEXT" in out


def test_format_compressed_for_injection_missing_keys():
    out = format_compressed_for_injection({})
    assert "UNKNOWN INTELLIGENCE BRIEFING" in out
    assert "No topics covered." in out


def test_compress_empty_report_no_llm(base_state):
    """An empty report must return a default compressed dict without calling the LLM."""
    state = {**base_state, "reports": {}}
    result = compress_intelligence_report(state, "subject")
    compressed = result["compressed_intelligence"]
    assert compressed["intelligence_type"] == "subject"
    assert "No subject report provided." in compressed["available_insights"]
    assert compressed["covered_topics"] == ""
    # Ensure the missing report path did not raise


def test_compress_with_content_mocked_llm(base_state, monkeypatch):
    """With content present, the LLM compressor is invoked once."""
    fake_llm = SimpleNamespace(
        invoke=lambda payload: SimpleNamespace(
            covered_topics="topic1\ntopic2",
            confirmed_positions="pos1",
            available_insights="insight",
            profile_context="ctx",
        )
    )
    monkeypatch.setattr(research_compressor_node, "intelligence_compressor", fake_llm)

    state = {**base_state, "reports": {"subject": {"content": "A real report body."}}}
    result = compress_intelligence_report(state, "subject")
    compressed = result["compressed_intelligence"]
    assert compressed["covered_topics"] == "topic1\ntopic2"
    assert compressed["available_insights"] == "insight"
    assert compressed["intelligence_type"] == "subject"


def test_compress_subject_intelligence_wrapper(base_state, monkeypatch):
    """compress_subject_intelligence builds a subject report from the raw text."""
    fake_llm = SimpleNamespace(
        invoke=lambda payload: SimpleNamespace(
            covered_topics="t",
            confirmed_positions="p",
            available_insights="i",
            profile_context="c",
        )
    )
    monkeypatch.setattr(research_compressor_node, "intelligence_compressor", fake_llm)
    state = {**base_state, "subject_intelligence_report": "RAW REPORT", "user_initial_query": "X"}
    result = compress_subject_intelligence(state)
    assert result["compressed_intelligence"]["available_insights"] == "i"


# ---------------------------------------------------------------------------
# Research node result normalization (pure helpers)
# ---------------------------------------------------------------------------

def test_normalize_raw_result_dict():
    d = {"report": "r", "sources": ["s"]}
    assert research_node_module._normalize_raw_result(d) == d


def test_normalize_raw_result_str():
    assert research_node_module._normalize_raw_result("hello") == {"report": "hello"}


def test_normalize_raw_result_list_of_dicts():
    out = research_node_module._normalize_raw_result([{"a": 1}, "x"])
    assert out == {"a": 1}


def test_normalize_raw_result_list_of_scalars():
    out = research_node_module._normalize_raw_result([1, 2])
    assert out == {"report": "1 2"}


def test_normalize_raw_result_none():
    assert research_node_module._normalize_raw_result(None) == {}


def test_as_title():
    assert research_node_module._as_title("sec") == "sec"
    assert research_node_module._as_title({"title": "T"}) == "T"
    assert research_node_module._as_title(42) == "42"


def test_extract_section_map():
    assert research_node_module._extract_section_map({"k": "v"}) == {"k": "v"}
    assert research_node_module._extract_section_map("x") == {"unrecognized_section": "x"}
    assert research_node_module._extract_section_map({}) == {}


@pytest.mark.asyncio
async def test_make_research_normalizes_output(base_state, monkeypatch):
    async def fake_research(**kwargs):
        return {
            "report": "FULL REPORT",
            "title": "TITLE",
            "sources": ["http://a", "http://b"],
            "costs": 1.5,
            "sections": ["S1", {"title": "S2"}],
            "research_data": [{"sec_a": "content a"}, {"sec_b": "content b"}],
        }

    monkeypatch.setattr(research_node_module, "conduct_multi_agent_research", fake_research)

    state = {
        **base_state,
        "chain_input": {"query": "q", "max_sections": 3},
        "profile_candidates": [],
    }
    result = await research_node_module.make_research(state)
    assert len(result["profile_candidates"]) == 1
    cand = result["profile_candidates"][0]
    assert cand["full_report"] == "FULL REPORT"
    assert cand["sources"] == ["http://a", "http://b"]
    assert cand["costs"] == 1.5
    assert cand["sub_topics"] == ["S1", "S2"]
    assert cand["section_content"] == {"sec_a": "content a", "sec_b": "content b"}
    assert result["research_iteration"] == 1


# ---------------------------------------------------------------------------
# Retrieval node (mocked retriever)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_mocked(base_state, monkeypatch):
    async def fake_retrieve(embeddings, index, question):
        return [{"page_content": "doc1"}]

    monkeypatch.setattr(retrive_module, "retive_query", fake_retrieve)
    result = await retrive_module.retrieve({"question": "what?"})
    assert result["question"] == "what?"
    assert result["documents"] == [{"page_content": "doc1"}]


# ---------------------------------------------------------------------------
# Web search node (mocked Tavily)
# ---------------------------------------------------------------------------

def test_websearch_mocked(base_state, monkeypatch):
    class FakeTavily:
        def __init__(self, query=None, query_domains=None):
            self.query = query

        def search(self, max_results=5):
            return {
                "results": [
                    {"url": "http://example.com", "content": "body text", "title": "Example"}
                ]
            }

    monkeypatch.setattr(web_search_module, "TavilySearch", FakeTavily)
    out = web_search_module.websearch({"question": "query", "documents": []})
    assert isinstance(out["documents"], list)
    assert len(out["documents"]) == 1
    assert "http://example.com" in out["documents"][0].page_content


def test_websearch_empty_question(base_state):
    out = web_search_module.websearch({"question": "", "documents": ["existing"]})
    assert out["documents"] == ["existing"]


@pytest.mark.asyncio
async def test_websearch_async_mocked(base_state, monkeypatch):
    async def fake_get_search_results(**kwargs):
        return [{"url": "http://x.com", "content": "c", "title": "t"}]

    monkeypatch.setattr(web_search_module, "get_search_results_async", fake_get_search_results)
    out = await web_search_module.websearch_async({"question": "q", "documents": []})
    assert len(out["documents"]) == 1
    assert "http://x.com" in out["documents"][0].page_content


# ---------------------------------------------------------------------------
# Identity research node (mocked research_identity)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_make_identity_research_mocked(base_state, monkeypatch):
    async def fake_research_identity(query=""):
        return {
            "report": "ID REPORT",
            "source_urls": ["http://s1"],
            "research_sources": [{"url": "http://s1"}],
            "costs": 0.3,
            "subtopics": ["a", "b"],
        }

    monkeypatch.setattr(identity_module, "research_identity", fake_research_identity)
    state = {**base_state, "chain_input": {"query": "who?"}, "identity_data": {"research_iteration": 2}}
    result = await identity_module.make_identity_research(state)
    idata = result["identity_data"]
    assert idata["report"] == "ID REPORT"
    assert idata["sources"] == ["http://s1"]
    assert idata["research_iteration"] == 2
    assert idata["needs_reprocessing"] is False


# ---------------------------------------------------------------------------
# Orchestration nodes (heavy deps mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_subject_intelligence_mocked(base_state, monkeypatch):
    async def fake_make_research(state):
        return {
            "profile_candidates": [{
                "title": "t", "summary": "", "full_report": "SUBJECT REPORT",
                "introduction": "", "conclusion": "", "initial_research": "",
                "sub_topics": [], "section_content": {}, "table_of_contents": "",
                "sources": ["http://s"], "costs": 0.1,
            }],
            "research_iteration": 1,
        }

    monkeypatch.setattr(subject_module, "make_research", fake_make_research)
    monkeypatch.setattr(mcp_config_module, "build_audience_mcp_configs", lambda: [])
    monkeypatch.setattr(mcp_config_module, "load_environment", lambda: None)

    state = {**base_state, "reports": {"profile_summary": {"content": "profile text"}}}
    result = await subject_module.run_subject_intelligence(state, max_sections=2)
    assert result["reports"]["subject"]["content"] == "SUBJECT REPORT"
    assert result["reports"]["subject"]["sources"] == ["http://s"]


@pytest.mark.asyncio
async def test_run_audience_intelligence_mocked(base_state, monkeypatch):
    async def fake_make_research(state):
        return {
            "profile_candidates": [{
                "title": "t", "summary": "", "full_report": "AUDIENCE REPORT",
                "introduction": "", "conclusion": "", "initial_research": "",
                "sub_topics": [], "section_content": {}, "table_of_contents": "",
                "sources": ["http://a"], "costs": 0.2,
            }],
            "research_iteration": 1,
        }

    monkeypatch.setattr(audience_module, "make_research", fake_make_research)
    monkeypatch.setattr(mcp_config_module, "build_audience_mcp_configs", lambda: [])
    monkeypatch.setattr(mcp_config_module, "load_environment", lambda: None)

    state = {
        **base_state,
        "reports": {
            "profile_summary": {"content": "profile"},
            "briefing_summary": {"content": "briefing"},
        },
    }
    result = await audience_module.run_audience_intelligence(state, max_sections=2)
    assert result["reports"]["audience"]["content"] == "AUDIENCE REPORT"


@pytest.mark.asyncio
async def test_run_ecosystem_intelligence_mocked(base_state, monkeypatch):
    async def fake_make_research(state):
        return {
            "profile_candidates": [{
                "title": "t", "summary": "", "full_report": "ECOSYSTEM REPORT",
                "introduction": "", "conclusion": "", "initial_research": "",
                "sub_topics": [], "section_content": {}, "table_of_contents": "",
                "sources": ["http://e"], "costs": 0.3,
            }],
            "research_iteration": 1,
        }

    monkeypatch.setattr(ecosystem_module, "make_research", fake_make_research)
    monkeypatch.setattr(mcp_config_module, "build_audience_mcp_configs", lambda: [])
    monkeypatch.setattr(mcp_config_module, "load_environment", lambda: None)
    # Local compression helper returns a fixed summary string (no LLM)
    monkeypatch.setattr(ecosystem_module, "compress_intelligence_report", lambda *a, **k: "COMPRESSED")

    state = {
        **base_state,
        "reports": {
            "subject": {"content": "subject report"},
            "audience": {"content": "audience report"},
        },
    }
    result = await ecosystem_module.run_ecosystem_intelligence(state, max_sections=2)
    assert result["reports"]["ecosystem"]["content"] == "ECOSYSTEM REPORT"


@pytest.mark.asyncio
async def test_summarize_profile_short_file(base_state, monkeypatch):
    # Short profile content is returned verbatim without invoking the compressor.
    content = "Short profile content under the 8000 char threshold."
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tf:
        tf.write(content)
        path = tf.name
    try:
        state = {**base_state, "input_paths": {"subject_profile_path": path}}
        result = await profile_module.summarize_profile(state)
        assert result["reports"]["profile_summary"]["content"] == content
        assert result["reports"]["profile_summary"]["metadata"]["compressed"] is False
    finally:
        os.remove(path)


@pytest.mark.asyncio
async def test_summarize_briefings_mocked(base_state, monkeypatch):
    fake_llm = SimpleNamespace(
        invoke=lambda payload: SimpleNamespace(
            covered_topics="t",
            confirmed_positions="p",
            available_insights="i",
            profile_context="c",
        )
    )
    monkeypatch.setattr(research_compressor_node, "intelligence_compressor", fake_llm)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as b1, \
         tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as b2:
        b1.write("briefing one")
        b2.write("briefing two")
        p1, p2 = b1.name, b2.name
    try:
        state = {**base_state, "input_paths": {"briefing_1_path": p1, "briefing_2_path": p2}}
        result = await profile_module.summarize_briefings(state)
        summary = result["reports"]["briefing_summary"]["content"]
        # summarize_briefings always compresses the combined briefing.
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert result["reports"]["briefing_summary"]["sources"] == [p1, p2]
    finally:
        os.remove(p1)
        os.remove(p2)
