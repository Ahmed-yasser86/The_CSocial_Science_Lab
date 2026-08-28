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
from typing import Dict, Any, Optional, List
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

# Ordered list of the three intelligence reports and their dependencies.
# Each report depends on the previous one, so the canonical execution order is
# subject -> audience -> ecosystem.
REPORT_KEYS = ["subject", "audience", "ecosystem"]
REPORT_NODES = {
    "subject": SUBJECT_INTELLIGENCE,
    "audience": AUDIENCE_INTELLIGENCE,
    "ecosystem": ECOSYSTEM_INTELLIGENCE,
}


def normalize_report_plan(requested: Optional[List[str]]) -> List[str]:
    """
    Resolve a user-requested report subset into a valid execution plan.

    Always returns the requested reports in canonical dependency order, and
    automatically includes any prerequisite reports that are missing. For example:
      - None / []            -> ["subject", "audience", "ecosystem"]
      - ["audience"]         -> ["subject", "audience"]
      - ["ecosystem"]        -> ["subject", "audience", "ecosystem"]
    """
    if not requested:
        return list(REPORT_KEYS)
    plan = [k for k in REPORT_KEYS if k in requested]
    # Add missing prerequisites in canonical order.
    for prereq in REPORT_KEYS:
        if prereq in plan:
            continue
        depends = any(
            REPORT_KEYS.index(later) > REPORT_KEYS.index(prereq) and later in plan
            for later in plan
        )
        if depends:
            plan.append(prereq)
    plan.sort(key=lambda k: REPORT_KEYS.index(k))
    return plan


def report_router(state: GraphState):
    """
    Conditional-edge router.

    Returns the next report node to execute: the first report in the plan whose
    output is not already present in state (respecting skip_existing_reports), or
    END if every requested report is satisfied. This lets a single compiled graph
    serve both "all three in one run" and "one report at a time, resumed later".
    """
    plan = state.get("report_plan") or list(REPORT_KEYS)
    reports = state.get("reports", {}) or {}
    skip = state.get("skip_existing_reports", True)
    force = set(state.get("force_reports", []) or [])
    for key in REPORT_KEYS:
        if key not in plan:
            continue
        existing = reports.get(key, {}) or {}
        if existing.get("content") and skip and key not in force:
            continue
        return REPORT_NODES[key]
    return END


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

    # Skip if this report already exists and we are allowed to reuse prior results.
    _reports = state.get("reports", {}) or {}
    _skip = state.get("skip_existing_reports", True)
    _force = set(state.get("force_reports", []) or [])
    if _skip and "subject" not in _force and _reports.get("subject", {}).get("content"):
        print("---SUBJECT INTELLIGENCE (skipped: already present in state)---")
        return state

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

    # Skip if this report already exists and we are allowed to reuse prior results.
    _reports = state.get("reports", {}) or {}
    _skip = state.get("skip_existing_reports", True)
    _force = set(state.get("force_reports", []) or [])
    if _skip and "audience" not in _force and _reports.get("audience", {}).get("content"):
        print("---AUDIENCE INTELLIGENCE (skipped: already present in state)---")
        return state

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

    # Skip if this report already exists and we are allowed to reuse prior results.
    _reports = state.get("reports", {}) or {}
    _skip = state.get("skip_existing_reports", True)
    _force = set(state.get("force_reports", []) or [])
    if _skip and "ecosystem" not in _force and _reports.get("ecosystem", {}).get("content"):
        print("---ECOSYSTEM INTELLIGENCE (skipped: already present in state)---")
        return state

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


def create_initial_state(
    user_query: str,
    subject_profile_path: str,
    briefing_1_path: str,
    briefing_2_path: str,
    report_plan: Optional[List[str]] = None,
    skip_existing_reports: bool = True,
    force_reports: Optional[List[str]] = None,
) -> GraphState:
    """
    Creates the initial state for the graph with user input.

    Args:
        user_query: The user's research query
        subject_profile_path: Path to subject profile document
        briefing_1_path: Path to first briefing document
        briefing_2_path: Path to second briefing document
        report_plan: Subset of ["subject", "audience", "ecosystem"] to generate.
            None (default) generates all three. Prerequisites are added
            automatically (e.g. requesting "audience" also schedules "subject").
        skip_existing_reports: When True (default), reports already present in a
            resumed state are not recomputed.
        force_reports: Report keys to (re)generate even if already present.

    Returns:
        Initialized GraphState
    """
    # Create run folder
    run_folder = create_run_folder()

    return {
        "user_initial_query": user_query,
        "mcp_strategy": "fast",
        "run_folder": run_folder,
        "report_plan": normalize_report_plan(report_plan),
        "skip_existing_reports": skip_existing_reports,
        "force_reports": force_reports or [],
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
workflow.add_edge(IDENTITY_RESEARCH, PROFILE_SUMMARIZATION)

# Conditional routing: after each step, run the next requested report in canonical
# dependency order (subject -> audience -> ecosystem), skipping any report that is
# already present (when skip_existing_reports is True). This supports both
# "generate all three in one run" and "one report at a time, resumed later" modes.
_PATH_MAP = {
    SUBJECT_INTELLIGENCE: SUBJECT_INTELLIGENCE,
    AUDIENCE_INTELLIGENCE: AUDIENCE_INTELLIGENCE,
    ECOSYSTEM_INTELLIGENCE: ECOSYSTEM_INTELLIGENCE,
    END: END,
}
workflow.add_conditional_edges(PROFILE_SUMMARIZATION, report_router, _PATH_MAP)
workflow.add_conditional_edges(SUBJECT_INTELLIGENCE, report_router, _PATH_MAP)
workflow.add_conditional_edges(AUDIENCE_INTELLIGENCE, report_router, _PATH_MAP)
workflow.add_conditional_edges(ECOSYSTEM_INTELLIGENCE, report_router, _PATH_MAP)

# Compile with memory (enables in-session pause/resume via thread_id)
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

# Save graph visualization
try:
    app.get_graph().draw_mermaid_png(output_file_path="intelligence_graph.png")
except Exception as e:
    print(f"Could not save graph visualization: {e}")


def load_state_from_file(path: str) -> GraphState:
    """Load a previously saved graph state JSON (created by save_state_to_file)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def prepare_resume_state(
    loaded_state: GraphState,
    report_plan: Optional[List[str]] = None,
    force_reports: Optional[List[str]] = None,
) -> GraphState:
    """
    Prepare a loaded state for a follow-up run.

    Keeps all previously generated reports (so they are reused, not recomputed)
    and sets the report_plan to the newly requested report(s). Prerequisites are
    added automatically and already-present reports are skipped.
    """
    loaded_state = dict(loaded_state)
    loaded_state["report_plan"] = normalize_report_plan(report_plan)
    loaded_state["skip_existing_reports"] = True
    loaded_state["force_reports"] = force_reports or []
    return loaded_state


async def run_intelligence_pipeline(initial_state: GraphState, config: dict = None, interrupt_after=None) -> GraphState:
    """
    Run the intelligence graph.

    Mode 1 (all three at once):  run_intelligence_pipeline(create_initial_state(...))
    Mode 2 (one at a time):      run_intelligence_pipeline(state, interrupt_after="subject_intelligence")
                                 ... later resume_intelligence_pipeline(config, report_plan=["audience"])

    Args:
        initial_state: Graph state (e.g. from create_initial_state).
        config: LangGraph run config; a stable thread_id enables pause/resume.
        interrupt_after: Node name(s) (e.g. "subject_intelligence") after which to
            pause. Resume later with the same config via resume_intelligence_pipeline.

    Returns:
        Final GraphState with the requested reports populated.
    """
    if config is None:
        config = {"configurable": {"thread_id": f"run_{uuid.uuid4().hex[:8]}"}}
    if isinstance(interrupt_after, str):
        interrupt_after = [interrupt_after]
    kwargs = {}
    if interrupt_after:
        kwargs["interrupt_after"] = interrupt_after
    return await app.ainvoke(initial_state, config=config, **kwargs)


async def resume_intelligence_pipeline(
    config: dict,
    report_plan: Optional[List[str]] = None,
    force_reports: Optional[List[str]] = None,
    interrupt_after=None,
) -> GraphState:
    """
    Resume a paused (or previous) run using its thread_id.

    Optionally extend the report_plan (e.g. request the next report) before
    continuing. Uses the in-memory checkpointer, so this works within the same
    process/session. Cross-process resumption should use load_state_from_file +
    prepare_resume_state instead.
    """
    if report_plan is not None:
        plan = normalize_report_plan(report_plan)
        app.update_state(config, {"report_plan": plan, "force_reports": force_reports or []})
    if isinstance(interrupt_after, str):
        interrupt_after = [interrupt_after]
    kwargs = {}
    if interrupt_after:
        kwargs["interrupt_after"] = interrupt_after
    return await app.ainvoke(None, config=config, **kwargs)


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