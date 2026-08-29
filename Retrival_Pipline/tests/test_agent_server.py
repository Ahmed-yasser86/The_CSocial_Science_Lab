"""Tests for the agent server stage / resume / report endpoints.

These exercise the pipeline's native stage + resume support and the HTTP API
without requiring live LLM credentials.
"""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from intelligence_graph import normalize_report_plan, prepare_resume_state
from persistence import get_store
from agent_server import app, _resolve_run_state


# --------------------------------------------------------------------------- #
# Pure pipeline logic
# --------------------------------------------------------------------------- #
def test_normalize_report_plan_prerequisites():
    assert normalize_report_plan(None) == ["subject", "audience", "ecosystem"]
    assert normalize_report_plan([]) == ["subject", "audience", "ecosystem"]
    assert normalize_report_plan(["subject"]) == ["subject"]
    # audience implies subject
    assert normalize_report_plan(["audience"]) == ["subject", "audience"]
    # ecosystem implies both predecessors
    assert normalize_report_plan(["ecosystem"]) == ["subject", "audience", "ecosystem"]
    # explicit order is preserved and de-duplicated
    assert normalize_report_plan(["ecosystem", "subject"]) == ["subject", "audience", "ecosystem"]
    # unknown keys are ignored
    assert normalize_report_plan(["subject", "bogus"]) == ["subject"]


def test_prepare_resume_state_keeps_reports_and_plan():
    loaded = {
        "session_id": "run_test",
        "run_folder": "/tmp/x",
        "reports": {"subject": {"content": "prior subject report", "path": "/tmp/x/subject.md"}},
    }
    state = prepare_resume_state(loaded, report_plan=["audience"])
    # existing reports are preserved
    assert "subject" in state["reports"]
    assert state["reports"]["subject"]["content"] == "prior subject report"
    # requesting audience pulls in its subject prerequisite
    assert state.get("report_plan") == ["subject", "audience"]
    assert state.get("skip_existing_reports") is True


# --------------------------------------------------------------------------- #
# HTTP API contracts
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_list_runs_endpoint(client):
    res = client.get("/api/agent/runs")
    assert res.status_code == 200
    body = res.json()
    assert "runs" in body
    assert isinstance(body["runs"], list)


def test_missing_run_returns_404(client):
    assert client.get("/api/agent/runs/does_not_exist").status_code == 404
    assert client.get("/api/agent/runs/does_not_exist/reports/subject").status_code == 404


def test_run_endpoint_returns_ok_contract(client):
    res = client.post("/api/agent/run", json={"user_query": "test", "stages": ["subject"]})
    assert res.status_code == 200
    body = res.json()
    assert "ok" in body
    # either it ran (ok True with run_id) or the env lacks the graph/keys (ok False with error)
    if body["ok"]:
        assert "run_id" in body
        assert body["report_plan"] == ["subject"]
    else:
        assert "error" in body


# --------------------------------------------------------------------------- #
# Resume reconstruction from the store
# --------------------------------------------------------------------------- #
def test_resolve_run_state_resume_loads_reports():
    store = get_store()
    with tempfile.TemporaryDirectory() as tmp:
        report_path = os.path.join(tmp, "subject_intelligence.md")
        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write("# Subject report\nprior content")

        run_id = "run_resume_test_" + os.urandom(4).hex()
        store.create_session(run_id, subject="Test Subject", run_folder=tmp)
        store.add_report(run_id, "subject", report_path, summary="s", completed=True)

        state, returned_id = _resolve_run_state(
            {"resume_run_id": run_id, "stages": ["audience"]}
        )
        assert returned_id == run_id
        # the previously generated report is loaded into state for the graph to reuse
        assert "subject" in state["reports"]
        assert state["reports"]["subject"]["content"].startswith("# Subject report")
        # audience triggers subject prerequisite
        assert state.get("report_plan") == ["subject", "audience"]
        assert state.get("run_folder") == tmp


def test_resolve_run_state_fresh_builds_plan():
    state, run_id = _resolve_run_state({"user_query": "x", "stages": ["ecosystem"]})
    assert state.get("report_plan") == ["subject", "audience", "ecosystem"]
    assert run_id
