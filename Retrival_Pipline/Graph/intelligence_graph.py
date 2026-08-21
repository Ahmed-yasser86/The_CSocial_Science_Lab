"""
Production-Grade Intelligence Graph

This graph implements a sequential intelligence pipeline:
1. Identity Research (based on user input)
2. Subject Intelligence
3. Audience Intelligence
4. Ecosystem Intelligence

Each step builds on the previous one and stores results in a dedicated run folder.
"""

import os
import asyncio
import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

# Import all nodes
from StateGraph import GraphState
from Nodes import (
    make_identity_research,
    run_subject_intelligence,
    run_audience_intelligence,
    run_ecosystem_intelligence,
    summarize_profile,
    summarize_briefings,
    compress_intelligence_report,
    format_compressed_for_injection,
)

# Load environment variables
load_dotenv()

# Constants
IDENTITY_RESEARCH = "identity_research"
SUBJECT_INTELLIGENCE = "subject_intelligence"
AUDIENCE_INTELLIGENCE = "audience_intelligence"
ECOSYSTEM_INTELLIGENCE = "ecosystem_intelligence"
PROFILE_SUMMARIZATION = "profile_summarization"
BRIEFING_SUMMARIZATION = "briefing_summarization"
MAX_ITERATIONS = 3


def create_run_folder() -> str:
    """
    Creates a unique folder for each graph run to store all output files.
    
    Returns:
        Path to the created run folder
    """
    run_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"run_{timestamp}_{run_id[:8]}"
    
    run_folder = os.path.join(
        os.path.dirname(__file__), 
        "runs", 
        run_name
    )
    
    os.makedirs(run_folder, exist_ok=True)
    return run_folder


def save_state_to_file(state: GraphState, run_folder: str, step_name: str) -> None:
    """
    Saves the current state to a JSON file in the run folder.
    
    Args:
        state: Current graph state
        run_folder: Path to the run folder
        step_name: Name of the current step
    """
    state_file = os.path.join(run_folder, f"{step_name}_state.json")
    
    # Prepare state for serialization
    serializable_state = {}
    for key, value in state.items():
        if key == "reports":
            # Handle reports separately to avoid serialization issues
            serializable_reports = {}
            for report_key, report_data in value.items():
                if isinstance(report_data, dict):
                    serializable_reports[report_key] = {
                        k: v for k, v in report_data.items() 
                        if not callable(v) and not k.startswith('_')
                    }
                else:
                    serializable_reports[report_key] = str(report_data)
            serializable_state[key] = serializable_reports
        elif not callable(value) and not key.startswith('_'):
            serializable_state[key] = value
    
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_state, f, indent=2, ensure_ascii=False)


def save_report_to_file(state: GraphState, run_folder: str, report_type: str) -> None:
    """
    Saves a specific report from state to a markdown file.
    
    Args:
        state: Current graph state
        run_folder: Path to the run folder
        report_type: Type of report to save (subject, audience, ecosystem)
    """
    reports = state.get("reports", {})
    if reports.get(report_type):
        report_data = reports[report_type]
        report_path = os.path.join(run_folder, report_data.get("path", f"{report_type}_intelligence.md"))
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        # Get content with default
        content = report_data.get("content", "")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(content)


async def profile_summarization_node(state: GraphState) -> GraphState:
    """
    Profile summarization node: Summarizes subject profile and briefings.
    
    This node takes the identity research results and creates summaries that will be
    used by subsequent intelligence nodes.
    """
    print("---PROFILE SUMMARIZATION---")
    
    # Get run folder from state with default
    run_folder = state.get("run_folder", "")
    if not run_folder:
        run_folder = create_run_folder()
        state = {**state, "run_folder": run_folder}
    
    # Extract identity data for context with defaults
    identity_data = state.get("identity_data", {})
    user_query = state.get("user_initial_query", "Unknown Subject")
    
    print(f"🔍 Summarizing profile for: {user_query}")
    if identity_data.get("report"):
        print(f"📄 Identity report length: {len(identity_data.get('report', ''))} chars")
    
    # Summarize profile
    state = await summarize_profile(state)
    
    # Summarize briefings
    state = await summarize_briefings(state)
    
    # Add context about what was summarized for next nodes
    reports = state.get("reports", {})
    if reports.get("profile_summary"):
        profile_content = reports["profile_summary"].get("content", "")
        print(f"✅ Profile summary created: {len(profile_content)} chars")
    if reports.get("briefing_summary"):
        briefing_content = reports["briefing_summary"].get("content", "")
        print(f"✅ Briefing summary created: {len(briefing_content)} chars")
    
    # Save state after summarization
    save_state_to_file(state, run_folder, PROFILE_SUMMARIZATION)
    
    return state


async def subject_intelligence_node(state: GraphState) -> GraphState:
    """
    Subject intelligence node: Extracts structured intelligence about the subject.
    
    This node builds on the profile summaries created in the previous step to
    develop a comprehensive understanding of the subject's identity, worldview,
    and ideology.
    """
    print("---SUBJECT INTELLIGENCE---")
    
    # Get run folder from state with default
    run_folder = state.get("run_folder", "")
    if not run_folder:
        run_folder = create_run_folder()
        state = {**state, "run_folder": run_folder}
    
    # Get context from previous steps with defaults
    user_query = state.get("user_initial_query", "Unknown Subject")
    reports = state.get("reports", {})
    
    print(f"🔍 Analyzing subject: {user_query}")
    if reports.get("profile_summary"):
        profile_content = reports["profile_summary"].get("content", "")
        print(f"📄 Using profile summary: {len(profile_content)} chars")
    if reports.get("briefing_summary"):
        briefing_content = reports["briefing_summary"].get("content", "")
        print(f"📋 Using briefing summary: {len(briefing_content)} chars")
    
    # Run subject intelligence
    state = await run_subject_intelligence(state, max_sections=4)
    
    # Save subject report to file
    save_report_to_file(state, run_folder, "subject")
    
    # Add context for next nodes
    reports = state.get("reports", {})
    if reports.get("subject"):
        subject_report = reports["subject"]
        print(f"✅ Subject intelligence generated: {len(subject_report.get('content', ''))} chars")
        print(f"   Sources: {len(subject_report.get('sources', []))}")
        print(f"   Costs: {subject_report.get('costs', 0)}")
    
    # Save state after subject intelligence
    save_state_to_file(state, run_folder, SUBJECT_INTELLIGENCE)
    
    return state


async def audience_intelligence_node(state: GraphState) -> GraphState:
    """
    Audience intelligence node: Analyzes the audience ecosystem.
    
    This node builds on the subject intelligence and profile summaries to
    understand the audience segments, their motivations, and how they interact
    with the subject.
    """
    print("---AUDIENCE INTELLIGENCE---")
    
    # Get run folder from state with default
    run_folder = state.get("run_folder", "")
    if not run_folder:
        run_folder = create_run_folder()
        state = {**state, "run_folder": run_folder}
    
    # Get context from previous steps with defaults
    user_query = state.get("user_initial_query", "Unknown Subject")
    reports = state.get("reports", {})
    
    print(f"👥 Analyzing audience for: {user_query}")
    if reports.get("subject"):
        subject_content = reports["subject"].get("content", "")
        print(f"🔍 Using subject intelligence: {len(subject_content)} chars")
    if reports.get("profile_summary"):
        profile_content = reports["profile_summary"].get("content", "")
        print(f"📄 Using profile summary: {len(profile_content)} chars")
    if reports.get("briefing_summary"):
        briefing_content = reports["briefing_summary"].get("content", "")
        print(f"📋 Using briefing summary: {len(briefing_content)} chars")
    
    # Run audience intelligence
    state = await run_audience_intelligence(state, max_sections=4)
    
    # Save audience report to file
    save_report_to_file(state, run_folder, "audience")
    
    # Add context for next nodes
    reports = state.get("reports", {})
    if reports.get("audience"):
        audience_report = reports["audience"]
        print(f"✅ Audience intelligence generated: {len(audience_report.get('content', ''))} chars")
        print(f"   Sources: {len(audience_report.get('sources', []))}")
        print(f"   Costs: {audience_report.get('costs', 0)}")
    
    # Save state after audience intelligence
    save_state_to_file(state, run_folder, AUDIENCE_INTELLIGENCE)
    
    return state


async def ecosystem_intelligence_node(state: GraphState) -> GraphState:
    """
    Ecosystem intelligence node: Examines macro-environmental context.
    
    This node builds on both subject and audience intelligence to analyze
    the broader ecosystem in which the subject operates, including institutional
    dynamics, systemic risks, and environmental factors.
    """
    print("---ECOSYSTEM INTELLIGENCE---")
    
    # Get run folder from state with default
    run_folder = state.get("run_folder", "")
    if not run_folder:
        run_folder = create_run_folder()
        state = {**state, "run_folder": run_folder}
    
    # Get context from previous steps with defaults
    user_query = state.get("user_initial_query", "Unknown Subject")
    reports = state.get("reports", {})
    
    print(f"🌍 Analyzing ecosystem for: {user_query}")
    if reports.get("subject"):
        subject_content = reports["subject"].get("content", "")
        print(f"🔍 Using subject intelligence: {len(subject_content)} chars")
    if reports.get("audience"):
        audience_content = reports["audience"].get("content", "")
        print(f"👥 Using audience intelligence: {len(audience_content)} chars")
    
    # Run ecosystem intelligence
    state = await run_ecosystem_intelligence(state, max_sections=4)
    
    # Save ecosystem report to file
    save_report_to_file(state, run_folder, "ecosystem")
    
    # Add context for potential future nodes
    reports = state.get("reports", {})
    if reports.get("ecosystem"):
        ecosystem_report = reports["ecosystem"]
        print(f"✅ Ecosystem intelligence generated: {len(ecosystem_report.get('content', ''))} chars")
        print(f"   Sources: {len(ecosystem_report.get('sources', []))}")
        print(f"   Costs: {ecosystem_report.get('costs', 0)}")
    
    # Save final state
    save_state_to_file(state, run_folder, ECOSYSTEM_INTELLIGENCE)
    
    print("🎯 Intelligence pipeline completed successfully!")
    
    return state


def create_initial_state(user_query: str, subject_profile_path: str, briefing_1_path: str, briefing_2_path: str) -> GraphState:
    """
    Creates the initial state for the graph with user input.
    
    Args:
        user_query: The user's research query
        subject_profile_path: Path to subject profile document
        briefing_1_path: Path to first briefing document
        briefing_2_path: Path to second briefing document
        
    Returns:
        Initialized GraphState
    """
    # Create run folder
    run_folder = create_run_folder()
    
    return {
        "user_initial_query": user_query,
        "mcp_strategy": "fast",
        "run_folder": run_folder,
        "input_paths": {
            "subject_profile_path": subject_profile_path,
            "briefing_1_path": briefing_1_path,
            "briefing_2_path": briefing_2_path,
        },
        "identity_data": {
            "research_iteration": 1,
            "needs_reprocessing": False,
            "feedback_notes": ""
        }
    }


# Build workflow
workflow = StateGraph(GraphState)

# Add nodes
workflow.add_node(IDENTITY_RESEARCH, make_identity_research)
workflow.add_node(PROFILE_SUMMARIZATION, profile_summarization_node)
workflow.add_node(SUBJECT_INTELLIGENCE, subject_intelligence_node)
workflow.add_node(AUDIENCE_INTELLIGENCE, audience_intelligence_node)
workflow.add_node(ECOSYSTEM_INTELLIGENCE, ecosystem_intelligence_node)

# Set entry point
workflow.set_entry_point(IDENTITY_RESEARCH)

# Add sequential edges
workflow.add_edge(IDENTITY_RESEARCH, PROFILE_SUMMARIZATION)
workflow.add_edge(PROFILE_SUMMARIZATION, SUBJECT_INTELLIGENCE)
workflow.add_edge(SUBJECT_INTELLIGENCE, AUDIENCE_INTELLIGENCE)
workflow.add_edge(AUDIENCE_INTELLIGENCE, ECOSYSTEM_INTELLIGENCE)
workflow.add_edge(ECOSYSTEM_INTELLIGENCE, END)

# Compile with memory
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

# Save graph visualization
try:
    app.get_graph().draw_mermaid_png(output_file_path="intelligence_graph.png")
except Exception as e:
    print(f"Could not save graph visualization: {e}")


# Test run
if __name__ == "__main__":
    async def run_test():
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        # Example paths - these would come from user input in production
        subject_profile_path = os.path.join(
            project_root, "mostafa_el_adawy_the_egyptian_salafai_report.md"
        )
        briefing_1_path = os.path.join(
            project_root,
            "outputs",
            "run_f72fdfbdb74642b59e8a8eb3eb9e8188",
            "b113dfd89d214e61ac82e1958b61dc84.md",
        )
        briefing_2_path = os.path.join(
            project_root,
            "outputs",
            "run_f72fdfbdb74642b59e8a8eb3eb9e8188",
            "b113dfd89d214e61ac82e1958b61dc84.md",
        )
        
        # Create initial state
        initial_state = create_initial_state(
            user_query="Sheikh Mostafa Al-Adawy",
            subject_profile_path=subject_profile_path,
            briefing_1_path=briefing_1_path,
            briefing_2_path=briefing_2_path
        )
        
        print("🚀 Starting Intelligence Graph...")
        print(f"📁 Run folder: {initial_state['run_folder']}")
        print(f"🔍 Subject: {initial_state['user_initial_query']}")
        
        config = {"configurable": {"thread_id": "intelligence_graph_test"}}
        
        try:
            final_state = await app.ainvoke(initial_state, config=config)
            print("\n🏁 Graph Execution Completed Successfully!")
            
            # Print summary of results
            reports = final_state.get("reports", {})
            print(f"\n📋 Generated Reports:")
            for report_type, report_data in reports.items():
                if isinstance(report_data, dict) and "content" in report_data:
                    print(f"  📄 {report_type.capitalize()} Report: {report_data.get('path')}")
                    print(f"     Length: {len(report_data.get('content', ''))} chars")
                    print(f"     Sources: {len(report_data.get('sources', []))}")
                    print(f"     Costs: {report_data.get('costs', 0.0)}")
            
            print(f"\n📁 All files saved to: {final_state['run_folder']}")
            
        except Exception as e:
            print(f"Error occurred: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_test())