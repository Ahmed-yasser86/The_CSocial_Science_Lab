"""
Integration tests for the complete Intelligence Graph
"""

import pytest
import asyncio
import os
import tempfile
from typing import Dict, Any

from StateGraph import GraphState
from RetrievalPipeline.Graph.intelligence_graph import (
    app,
    create_initial_state,
    IDENTITY_RESEARCH,
    PROFILE_SUMMARIZATION,
    SUBJECT_INTELLIGENCE,
    AUDIENCE_INTELLIGENCE,
    ECOSYSTEM_INTELLIGENCE
)


def _live_tests_enabled() -> bool:
    return os.getenv("RUN_LIVE_TESTS") == "1"


pytestmark = pytest.mark.skipif(
    not _live_tests_enabled(),
    reason="live integration test: set RUN_LIVE_TESTS=1 with valid LLM/MCP credentials and network",
)


@pytest.fixture
def test_data_dir():
    """Fixture providing path to test data directory."""
    return os.path.join(os.path.dirname(__file__), "test_data")


@pytest.fixture
def sample_initial_state(test_data_dir: str) -> GraphState:
    """Fixture providing a sample initial state for graph testing."""
    return create_initial_state(
        user_query="Sheikh Mostafa Al-Adawy",
        subject_profile_path=os.path.join(test_data_dir, "subject_profile.md"),
        briefing_1_path=os.path.join(test_data_dir, "briefing_1.md"),
        briefing_2_path=os.path.join(test_data_dir, "briefing_2.md")
    )


@pytest.mark.asyncio
async def test_graph_execution(sample_initial_state: GraphState):
    """Test the complete graph execution."""
    config = {"configurable": {"thread_id": "test_graph_execution"}}
    
    # Run the graph
    final_state = await app.ainvoke(sample_initial_state, config=config)
    
    # Verify the final state contains expected results
    assert "reports" in final_state
    reports = final_state["reports"]
    
    # Check that all expected reports were generated
    expected_reports = ["subject", "audience", "ecosystem", "profile_summary", "briefing_summary"]
    for report_type in expected_reports:
        assert report_type in reports, f"Missing {report_type} report"
        assert len(reports[report_type]["content"]) > 0, f"Empty {report_type} report content"
        assert len(reports[report_type]["path"]) > 0, f"Missing {report_type} report path"
    
    # Check that run folder was created and contains files
    run_folder = final_state.get("run_folder")
    assert run_folder is not None, "Run folder not created"
    assert os.path.exists(run_folder), "Run folder does not exist"
    
    # Check that files were created in run folder
    run_files = os.listdir(run_folder)
    assert len(run_files) > 0, "No files created in run folder"
    
    print("✅ Graph execution test passed")
    print(f"   Run folder: {run_folder}")
    print(f"   Generated reports: {list(reports.keys())}")
    print(f"   Files in run folder: {len(run_files)}")


@pytest.mark.asyncio
async def test_graph_state_flow(sample_initial_state: GraphState):
    """Test that the graph maintains proper state flow between nodes."""
    config = {"configurable": {"thread_id": "test_state_flow"}}
    
    # Test intermediate states by checking the checkpoint
    intermediate_state = None
    
    # Run through identity research
    async for event in app.astream(sample_initial_state, config=config):
        if IDENTITY_RESEARCH in event:
            intermediate_state = event[IDENTITY_RESEARCH]
            break
    
    assert intermediate_state is not None, "Identity research node not executed"
    assert "identity_data" in intermediate_state, "Identity data not created"
    
    # Continue to profile summarization
    async for event in app.astream(intermediate_state, config=config):
        if PROFILE_SUMMARIZATION in event:
            intermediate_state = event[PROFILE_SUMMARIZATION]
            break
    
    assert intermediate_state is not None, "Profile summarization node not executed"
    assert "reports" in intermediate_state, "Reports not created"
    assert "profile_summary" in intermediate_state["reports"], "Profile summary not created"
    
    # Continue to subject intelligence
    async for event in app.astream(intermediate_state, config=config):
        if SUBJECT_INTELLIGENCE in event:
            intermediate_state = event[SUBJECT_INTELLIGENCE]
            break
    
    assert intermediate_state is not None, "Subject intelligence node not executed"
    assert "subject" in intermediate_state["reports"], "Subject report not created"
    
    # Continue to audience intelligence
    async for event in app.astream(intermediate_state, config=config):
        if AUDIENCE_INTELLIGENCE in event:
            intermediate_state = event[AUDIENCE_INTELLIGENCE]
            break
    
    assert intermediate_state is not None, "Audience intelligence node not executed"
    assert "audience" in intermediate_state["reports"], "Audience report not created"
    
    # Continue to ecosystem intelligence
    async for event in app.astream(intermediate_state, config=config):
        if ECOSYSTEM_INTELLIGENCE in event:
            intermediate_state = event[ECOSYSTEM_INTELLIGENCE]
            break
    
    assert intermediate_state is not None, "Ecosystem intelligence node not executed"
    assert "ecosystem" in intermediate_state["reports"], "Ecosystem report not created"
    
    print("✅ Graph state flow test passed")
    print(f"   Final reports: {list(intermediate_state['reports'].keys())}")


@pytest.mark.asyncio
async def test_graph_error_handling(sample_initial_state: GraphState):
    """Test graph error handling and recovery."""
    config = {"configurable": {"thread_id": "test_error_handling"}}
    
    # Test with missing input files (should handle gracefully)
    bad_state = sample_initial_state.copy()
    bad_state["input_paths"]["subject_profile_path"] = "/nonexistent/path.md"
    
    try:
        final_state = await app.ainvoke(bad_state, config=config)
        # Should still complete with error information
        assert "reports" in final_state
        print("✅ Graph error handling test passed - handled missing file gracefully")
    except Exception as e:
        # Some errors might still propagate, but they should be informative
        print(f"✅ Graph error handling test passed - error was: {str(e)}")
        assert "file" in str(e).lower() or "path" in str(e).lower(), "Error not related to missing file"


@pytest.mark.asyncio
async def test_graph_report_quality(sample_initial_state: GraphState):
    """Test the quality and structure of generated reports."""
    config = {"configurable": {"thread_id": "test_report_quality"}}
    
    final_state = await app.ainvoke(sample_initial_state, config=config)
    reports = final_state.get("reports", {})
    
    # Test report structure and content quality
    for report_type, report_data in reports.items():
        # Check required fields
        required_fields = ["content", "path", "sources", "costs", "metadata"]
        for field in required_fields:
            assert field in report_data, f"Missing {field} in {report_type} report"
        
        # Check content quality
        content = report_data.get("content", "")
        assert len(content) > 100, f"{report_type} report content too short ({len(content)} chars)"
        
        # Check for meaningful content (not just error messages)
        assert "error" not in content.lower(), f"{report_type} report contains error message"
        assert "not found" not in content.lower(), f"{report_type} report indicates missing data"
        
        # Check sources
        sources = report_data.get("sources", [])
        if report_type not in ["profile_summary", "briefing_summary"]:  # Summaries might not have sources
            assert len(sources) > 0, f"{report_type} report has no sources"
        
        # Check costs
        costs = report_data.get("costs", 0)
        assert costs >= 0, f"{report_type} report has negative costs"
        
        # Check metadata
        metadata = report_data.get("metadata", {})
        assert len(metadata) > 0, f"{report_type} report has no metadata"
        assert "prompt_type" in metadata, f"{report_type} report missing prompt_type in metadata"
    
    print("✅ Graph report quality test passed")
    print(f"   Report types tested: {list(reports.keys())}")
    for report_type, report_data in reports.items():
        print(f"   - {report_type}: {len(report_data.get('content', ''))} chars, {len(report_data.get('sources', []))} sources")