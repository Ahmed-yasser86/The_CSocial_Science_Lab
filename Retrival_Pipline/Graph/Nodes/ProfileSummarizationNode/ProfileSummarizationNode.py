"""
Profile Summarization Node

This node handles profile and briefing summarization tasks, storing results in the graph state.
"""

import asyncio
import os
import sys
from typing import Dict, Any

# Add the workspace root and Retrival_Pipline to the Python path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
RETRIVAL_PIPELINE_PATH = os.path.join(WORKSPACE_ROOT, "Retrival_Pipline")

if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)
if RETRIVAL_PIPELINE_PATH not in sys.path:
    sys.path.insert(0, RETRIVAL_PIPELINE_PATH)

from Retrival_Pipline.Graph.Nodes.CompressionNode import (
    compress_intelligence_report,
    compress_subject_intelligence,
    compress_reference_doc,
    format_compressed_for_injection,
)
from Retrival_Pipline.Graph.StateGraph import GraphState


async def summarize_profile(
    state: GraphState,
    profile_path_key: str = "subject_profile_path",
    output_key: str = "profile_summary"
) -> GraphState:
    """
    Summarize a profile document and store the result in the graph state.
    
    Args:
        state: The current graph state
        profile_path_key: Key in input_paths where the profile path is stored
        output_key: Key in reports where the summary will be stored
        
    Returns:
        Updated GraphState with profile summary
    """
    # Get profile path from state
    input_paths = state.get("input_paths", {})
    profile_path = input_paths.get(profile_path_key)
    
    if not profile_path:
        raise ValueError(f"Profile path not found in state.input_paths['{profile_path_key}']")
    
    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    # Read profile content
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_content = f.read()

    # Short circuit if content is already short enough
    if len(profile_content) <= 8000:
        summary_content = profile_content
    else:
        # Compress using the reference-doc compressor (profiles are not subject-intel reports)
        summary_content = compress_reference_doc(profile_content)
    
    # Store the result in state
    reports = state.get("reports", {})
    reports[output_key] = {
        "content": summary_content,
        "path": profile_path,
        "sources": [profile_path],
        "costs": 0.0,  # No LLM cost for simple summarization
        "metadata": {
            "original_length": len(profile_content),
            "summary_length": len(summary_content),
            "compressed": len(profile_content) > 8000
        }
    }
    
    # Update state
    updated_state = {
        **state,
        "reports": reports
    }
    
    print(f"✅ Profile summary generated: {len(profile_content)} chars → {len(summary_content)} chars")
    return updated_state


async def summarize_briefings(
    state: GraphState,
    briefing_1_key: str = "briefing_1_path",
    briefing_2_key: str = "briefing_2_path",
    output_key: str = "briefing_summary"
) -> GraphState:
    """
    Combine and summarize two briefing documents, storing the result in the graph state.
    
    Args:
        state: The current graph state
        briefing_1_key: Key in input_paths for first briefing path
        briefing_2_key: Key in input_paths for second briefing path
        output_key: Key in reports where the summary will be stored
        
    Returns:
        Updated GraphState with briefing summary
    """
    # Get briefing paths from state
    input_paths = state.get("input_paths", {})
    briefing_1_path = input_paths.get(briefing_1_key)
    briefing_2_path = input_paths.get(briefing_2_key, briefing_1_path)  # Fallback to briefing_1 if not provided
    
    if not briefing_1_path:
        raise ValueError(f"Briefing 1 path not found in state.input_paths['{briefing_1_key}']")
    
    if not os.path.exists(briefing_1_path):
        raise FileNotFoundError(f"Briefing 1 not found: {briefing_1_path}")

    if not os.path.exists(briefing_2_path):
        raise FileNotFoundError(f"Briefing 2 not found: {briefing_2_path}")

    # Read briefing contents
    with open(briefing_1_path, "r", encoding="utf-8") as f:
        briefing_1 = f.read()
    
    with open(briefing_2_path, "r", encoding="utf-8") as f:
        briefing_2 = f.read()
    
    # Combine briefings
    combined_report = (
        "SOURCE 1:\n" + briefing_1.strip() + "\n\n"
        "SOURCE 2:\n" + briefing_2.strip()
    )

    # Short circuit if already short enough, else compress with the reference-doc compressor.
    if len(combined_report) <= 8000:
        summary_content = combined_report
    else:
        summary_content = compress_reference_doc(combined_report)
    
    # Store the result in state
    reports = state.get("reports", {})
    reports[output_key] = {
        "content": summary_content,
        "path": briefing_1_path,  # Store primary briefing path
        "sources": [briefing_1_path, briefing_2_path],
        "costs": 0.0,  # No LLM cost for simple summarization
        "metadata": {
            "original_length": len(combined_report),
            "summary_length": len(summary_content),
            "sources_count": 2
        }
    }
    
    # Update state
    updated_state = {
        **state,
        "reports": reports
    }
    
    print(f"✅ Briefing summary generated: {len(combined_report)} chars → {len(summary_content)} chars")
    return updated_state