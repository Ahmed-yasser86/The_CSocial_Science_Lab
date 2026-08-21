"""
Unit tests for individual nodes in the Intelligence Graph
"""

import pytest
import asyncio
import os
import tempfile
from typing import Dict, Any
from datetime import datetime

# Import nodes to test
from StateGraph import GraphState
from Nodes import (
    run_subject_intelligence,
    run_audience_intelligence,
    run_ecosystem_intelligence,
    summarize_profile,
    summarize_briefings,
    compress_intelligence_report,
    format_compressed_for_injection,
)


@pytest.fixture
def sample_state() -> GraphState:
    """Fixture providing a sample state for testing."""
    return {
        "user_initial_query": "Sheikh Mostafa Al-Adawy",
        "mcp_strategy": "fast",
        "run_folder": tempfile.mkdtemp(),
        "input_paths": {
            "subject_profile_path": os.path.join(os.path.dirname(__file__), "test_data", "subject_profile.md"),
            "briefing_1_path": os.path.join(os.path.dirname(__file__), "test_data", "briefing_1.md"),
            "briefing_2_path": os.path.join(os.path.dirname(__file__), "test_data", "briefing_2.md"),
        },
        "reports": {}
    }


@pytest.fixture
def sample_report_state(sample_state: GraphState) -> GraphState:
    """Fixture providing a state with sample reports for testing downstream nodes."""
    # Add sample reports to the state
    sample_state["reports"] = {
        "profile_summary": {
            "content": "Sample profile summary content...",
            "path": "profile_summary.md"
        },
        "briefing_summary": {
            "content": "Sample briefing summary content...",
            "path": "briefing_summary.md"
        }
    }
    return sample_state


@pytest.mark.asyncio
async def test_profile_summarization(sample_state: GraphState):
    """Test the profile summarization node."""
    # Test profile summarization
    state = await summarize_profile(sample_state)
    
    assert "reports" in state
    assert "profile_summary" in state["reports"]
    assert len(state["reports"]["profile_summary"]["content"]) > 0
    
    # Test briefing summarization
    state = await summarize_briefings(state)
    
    assert "briefing_summary" in state["reports"]
    assert len(state["reports"]["briefing_summary"]["content"]) > 0
    
    print("✅ Profile summarization tests passed")


@pytest.mark.asyncio
async def test_subject_intelligence_node(sample_report_state: GraphState):
    """Test the subject intelligence node."""
    state = await run_subject_intelligence(sample_report_state, max_sections=2)
    
    assert "reports" in state
    assert "subject" in state["reports"]
    assert len(state["reports"]["subject"]["content"]) > 0
    assert len(state["reports"]["subject"]["sources"]) >= 0
    assert state["reports"]["subject"]["costs"] >= 0
    
    print("✅ Subject intelligence tests passed")


@pytest.mark.asyncio
async def test_audience_intelligence_node(sample_report_state: GraphState):
    """Test the audience intelligence node."""
    # First add subject report to state
    sample_report_state["reports"]["subject"] = {
        "content": "Sample subject intelligence content...",
        "path": "subject_intelligence.md",
        "sources": ["source1", "source2"],
        "costs": 0.5
    }
    
    state = await run_audience_intelligence(sample_report_state, max_sections=2)
    
    assert "reports" in state
    assert "audience" in state["reports"]
    assert len(state["reports"]["audience"]["content"]) > 0
    assert len(state["reports"]["audience"]["sources"]) >= 0
    assert state["reports"]["audience"]["costs"] >= 0
    
    print("✅ Audience intelligence tests passed")


@pytest.mark.asyncio
async def test_ecosystem_intelligence_node(sample_report_state: GraphState):
    """Test the ecosystem intelligence node."""
    # Add subject and audience reports to state
    sample_report_state["reports"]["subject"] = {
        "content": "Sample subject intelligence content...",
        "path": "subject_intelligence.md",
        "sources": ["source1", "source2"],
        "costs": 0.5
    }
    sample_report_state["reports"]["audience"] = {
        "content": "Sample audience intelligence content...",
        "path": "audience_intelligence.md",
        "sources": ["source3", "source4"],
        "costs": 0.7
    }
    
    state = await run_ecosystem_intelligence(sample_report_state, max_sections=2)
    
    assert "reports" in state
    assert "ecosystem" in state["reports"]
    assert len(state["reports"]["ecosystem"]["content"]) > 0
    assert len(state["reports"]["ecosystem"]["sources"]) >= 0
    assert state["reports"]["ecosystem"]["costs"] >= 0
    
    print("✅ Ecosystem intelligence tests passed")


def test_compression_functions(sample_report_state: GraphState):
    """Test the compression functions."""
    # Add a sample report to compress
    sample_report_state["reports"]["subject"] = {
        "content": "This is a sample subject intelligence report about Sheikh Mostafa Al-Adawy. "
                   "The report covers his background, positions, and influence. "
                   "Key findings include his conservative views and significant following.",
        "path": "subject_intelligence.md",
        "sources": ["source1", "source2"],
        "costs": 0.5
    }
    
    # Test compression
    state = compress_intelligence_report(sample_report_state, "subject")
    
    assert "compressed_intelligence" in state
    compressed = state["compressed_intelligence"]
    
    assert compressed["intelligence_type"] == "subject"
    assert len(compressed["covered_topics"]) > 0
    assert len(compressed["confirmed_positions"]) > 0
    assert len(compressed["available_insights"]) > 0
    assert len(compressed["profile_context"]) > 0
    
    # Test formatting
    formatted = format_compressed_for_injection(compressed)
    assert "SUBJECT INTELLIGENCE BRIEFING" in formatted
    assert "PREVIOUSLY COVERED TOPICS" in formatted
    assert "ESTABLISHED CONTEXT" in formatted
    
    print("✅ Compression tests passed")


@pytest.mark.asyncio
async def test_node_sequence_integration(sample_report_state: GraphState):
    """Test the complete node sequence integration."""
    # Start with profile summarization
    state = await summarize_profile(sample_report_state)
    state = await summarize_briefings(state)
    
    # Run subject intelligence
    state = await run_subject_intelligence(state, max_sections=2)
    
    # Compress subject intelligence
    state = compress_intelligence_report(state, "subject")
    
    # Run audience intelligence
    state = await run_audience_intelligence(state, max_sections=2)
    
    # Compress audience intelligence
    state = compress_intelligence_report(state, "audience")
    
    # Run ecosystem intelligence
    state = await run_ecosystem_intelligence(state, max_sections=2)
    
    # Verify all reports were created
    reports = state.get("reports", {})
    assert "subject" in reports
    assert "audience" in reports
    assert "ecosystem" in reports
    
    # Verify compression worked
    assert "compressed_intelligence" in state
    
    print("✅ Node sequence integration tests passed")
    print(f"   Generated reports: {list(reports.keys())}")
    print(f"   Final state keys: {list(state.keys())}")