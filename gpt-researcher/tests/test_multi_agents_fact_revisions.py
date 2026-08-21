import importlib.util
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[1] / "multi_agents" / "agents" / "fact_review.py"
spec = importlib.util.spec_from_file_location("fact_review", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_accept_none_notes():
    assert mod.route_fact_check({"fact_check_notes": None}) == "accept"


def test_revise_until_limit():
    assert mod.route_fact_check(
        {"fact_check_notes": "fix X", "fact_check_revision_count": 2},
        max_fact_check_revisions=2,
    ) == "revise"


def test_auto_accept_past_limit():
    state = {
        "fact_check_notes": "still bad",
        "fact_check_revision_count": 3,
    }
    result = mod.route_fact_check(state, max_fact_check_revisions=2)

    assert result == "accept"
    assert state["fact_check_result"]["status"] == "unverified_contested"
    assert state["fact_check_result"]["use_as_basis"] is True
    assert state["fact_check_result"]["auto_decision"] == "exceeded_max_revisions"
    assert state["fact_check_result"]["fact_check_revision_count"] == 3


def test_clamps_task_max_to_default_limit():
    state = {
        "fact_check_notes": "still bad",
        "fact_check_revision_count": 8,
    }
    result = mod.route_fact_check(state, max_fact_check_revisions=7)

    assert result == "accept"
    assert state["fact_check_result"]["status"] == "unverified_contested"
    assert state["fact_check_result"]["fact_check_revision_count"] == 8
