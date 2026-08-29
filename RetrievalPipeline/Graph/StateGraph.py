from typing import Any, Optional, TypedDict

from pydantic import BaseModel, Field

class ProfileCandidate(TypedDict):
    """A single candidate profile generated for a research query."""
    title: str
    summary: str
    full_report: str
    introduction: str
    conclusion: str
    initial_research: str
    sub_topics: list[str]
    section_content: dict[str, str]
    table_of_contents: str
    sources: list[str]
    costs: float



class CompressedIntelligence(TypedDict, total=False):
    """Structured compression of a Subject Intelligence Report."""

    covered_topics: str
    confirmed_positions: str
    available_insights: str
    profile_context: str
    key_claims_with_sources: str
    open_questions: str
    intelligence_type: str
    target_node: Optional[str]
    source_report: str
    compression_timestamp: str



class ChainInput(TypedDict, total=False):
    """Input config for the research chain."""
    query: str
    max_sections: int
    follow_guidelines: bool
    guidelines: list[str]
    verbose: bool
    prompt_type: str
    mcp_configs: list[dict[str, object]]
    mcp_strategy: str


class IdentityData(TypedDict, total=False):
    """Verified identity anchors data structure."""
    report: str
    """Verified identity anchors report from the identity research node."""
    sources: list[str]
    """Source URLs used for identity verification."""
    research_sources: list[dict]
    """Richer source data for identity facts."""
    costs: float
    """Cost of the identity research pass."""
    subtopics: list[str]
    """Subtopics explored during identity verification."""
    
    needs_reprocessing: bool 
    """Boolean flag to check if the user requested to re-run the research."""
    feedback_notes: str
    """The specific feedback or extra details provided by the user for the next search pass."""
    research_iteration: int
    """Current research iteration count."""

class ReportData(TypedDict, total=False):
    """Structured data for storing generated reports."""
    content: str
    path: str
    sources: list[str]
    costs: float
    metadata: dict[str, Any]


class IntelligenceReports(TypedDict, total=False):
    """Collection of intelligence reports stored in the graph state."""
    subject: ReportData
    audience: ReportData
    ecosystem: ReportData
    profile_summary: ReportData
    briefing_summary: ReportData


class GraphState(TypedDict, total=False):
    """State shared across the graph."""
    user_initial_query: str
    chain_input: ChainInput
    prompt_type: str
    subject_intelligence_report: str
    profile_candidates: list[ProfileCandidate]
    selected_profile: Optional[ProfileCandidate]
    needs_more_research: bool
    feedback_notes: Optional[str]
    research_iteration: int
    compressed_intelligence: CompressedIntelligence
    identity_data: IdentityData
    mcp_configs: list[dict[str, object]]
    mcp_strategy: str
    reports: IntelligenceReports
    input_paths: dict[str, str]
    run_folder: str

    # --- Report execution control ---
    report_plan: list[str]
    """Ordered list of report keys to generate this run (subset of the three
    intelligence reports). Defaults to all three in canonical dependency order
    (subject -> audience -> ecosystem)."""
    skip_existing_reports: bool
    """When True (default), a report node is skipped if its output already exists
    in state['reports'] (used for resuming an earlier run without recomputing)."""
    force_reports: list[str]
    """Report keys to (re)generate even if already present in state."""

    compressed_reports: dict[str, Any]
    """Cache of compressions keyed by 'report_type->target_node' to avoid recompute."""

    session_id: str
    """Persistence session id (maps to the intelligence DB)."""