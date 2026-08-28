"""Offline tests for compression rework + persistence layer.

No network/LLM calls: the structured compressor is mocked and the persistence
layer uses a temporary SQLite database.
"""
import os
import sys
import json
import tempfile
import types

import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, WORKSPACE_ROOT)

from Retrival_Pipline.Graph.Nodes.CompressionNode import research_compressor_node as rc
from Retrival_Pipline.Graph.persistence import IntelligenceStore


# ---------------------------------------------------------------------------
# Compression: structure + consumer-aware injection + reference doc
# ---------------------------------------------------------------------------
class FakeCompressed:
    covered_topics = "T1\nT2"
    confirmed_positions = "P1 [VERIFIED]"
    available_insights = "I1"
    profile_context = "C1"
    key_claims_with_sources = "- [VERIFIED] claim A -- http://a\n- [INFERRED FROM PATTERNS] claim B -- http://b"
    open_questions = "Q1\nQ2"
    intelligence_type = "subject"


def _fake_compressor_for(target_node):
    class _FakeChain:
        def invoke(self, _payload):
            f = FakeCompressed()
            f.target_node = target_node
            return f
    return _FakeChain()


@pytest.fixture(autouse=True)
def patch_compressor(monkeypatch):
    monkeypatch.setattr(rc, "_compressor_for", _fake_compressor_for)


def test_compress_returns_new_fields():
    state = {"reports": {"subject": {"content": "some report text"}}}
    out = rc.compress_intelligence_report(state, "subject", target_node="audience")
    comp = out["compressed_intelligence"]
    assert "key_claims_with_sources" in comp
    assert "open_questions" in comp
    assert comp["target_node"] == "audience"


def test_get_or_compress_caches():
    state = {"reports": {"subject": {"content": "x"}}}
    out1 = rc.get_or_compress(state, "subject", target_node="audience")
    key = "subject->audience"
    assert key in out1.get("compressed_reports", {})
    # Second call should hit the cache (no recompute) and return identical object.
    out2 = rc.get_or_compress(out1, "subject", target_node="audience")
    assert out2["compressed_intelligence"] is out1["compressed_reports"][key]


def test_format_injection_audience_trims_to_relevant_sections():
    comp = {
        "covered_topics": "T",
        "confirmed_positions": "P [VERIFIED]",
        "available_insights": "I",
        "profile_context": "C",
        "key_claims_with_sources": "- [VERIFIED] a -- http://a",
        "open_questions": "Q",
        "source_report": "subject",
        "compression_timestamp": "now",
    }
    text = rc.format_compressed_for_injection(comp, target_node="audience")
    assert "CONFIRMED POSITIONS" in text
    assert "PROFILE CONTEXT" in text
    assert "AVAILABLE INSIGHTS" not in text  # trimmed for audience
    assert "OPEN QUESTIONS" in text


def test_format_injection_ecosystem_trims_to_relevant_sections():
    comp = {
        "covered_topics": "T",
        "confirmed_positions": "P [VERIFIED]",
        "available_insights": "I",
        "profile_context": "C",
        "key_claims_with_sources": "- [VERIFIED] a -- http://a",
        "open_questions": "Q",
        "source_report": "subject",
        "compression_timestamp": "now",
    }
    text = rc.format_compressed_for_injection(comp, target_node="ecosystem")
    assert "AVAILABLE INSIGHTS" in text
    assert "PROFILE CONTEXT" in text
    assert "CONFIRMED POSITIONS" not in text  # trimmed for ecosystem
    assert "OPEN QUESTIONS" in text


def test_reference_doc_short_circuits_when_small():
    small = "short profile"
    assert rc.compress_reference_doc(small) == small


def test_reference_doc_compresses_large(monkeypatch):
    big = "x" * 9000
    monkeypatch.setattr(
        rc, "_ref_chain",
        types.SimpleNamespace(invoke=lambda payload: types.SimpleNamespace(content="SUMMARY")),
    )
    assert rc.compress_reference_doc(big) == "SUMMARY"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def test_persistence_roundtrip():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = os.path.join(tmp, "intel.db")
        store = IntelligenceStore(db_path=db)

        sid = "run_test123"
        store.create_session(sid, subject="Test Subject", report_plan=["subject", "audience"])
        sess = store.get_session(sid)
        assert sess["subject"] == "Test Subject"
        assert json.loads(sess["report_plan"]) == ["subject", "audience"]

        rid = store.add_report(
            sid, "subject", "/tmp/x.md", summary="hi", sources_count=2, costs=0.5,
            sources=[{"url": "http://a", "title": "A"}],
        )
        rep = store.get_report(sid, "subject")
        assert rep["path"] == "/tmp/x.md"
        assert rep["sources_count"] == 2
        assert rep["sources"][0]["url"] == "http://a"

        # Marking a completed report updates the session's completed_reports.
        sess = store.get_session(sid)
        assert "subject" in json.loads(sess["completed_reports"])

        store.save_step(sid, "identity_research", "/tmp/state.json")
        steps = store.list_steps(sid)
        assert steps[0]["step"] == "identity_research"
