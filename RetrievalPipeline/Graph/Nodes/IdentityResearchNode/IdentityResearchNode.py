# Nodes/IdentityResearchNode/IdentityResearchNode.py
from typing import Any, Dict
from RetrievalPipeline.Graph.Chains.IdentityResearch import research_identity
from StateGraph import GraphState


async def make_identity_research(state: GraphState) -> Dict[str, Any]:
    """
    Identity Research Node: Performs research and returns IdentityData.
    """
    print("---IDENTITY RESEARCH NODE---")

    # Skip if identity research already exists and we are allowed to reuse it
    # (used when resuming a prior run so we don't re-run expensive research).
    _existing = state.get("identity_data", {}) or {}
    _skip = state.get("skip_existing_reports", True)
    _force = set(state.get("force_reports", []) or [])
    if _skip and "identity" not in _force and _existing.get("report"):
        print("---IDENTITY RESEARCH NODE (skipped: already present in state)---")
        return {"identity_data": _existing}

    chain_input = state.get("chain_input", {})
    query = chain_input.get("query", "")
    
    # Get existing identity data to preserve iteration count
    identity_data_existing = state.get("identity_data", {})
    iteration = identity_data_existing.get("research_iteration", 1)
    
    print(f"🔍 Researching: '{query}' (Iteration {iteration})")
    
    # Perform research
    result = await research_identity(query=query)

    # `result["subtopics"]` is a pydantic `Subtopics` model; flatten it to a
    # plain list[str] so the graph state stays JSON-serializable downstream.
    _raw = result.get("subtopics")
    if isinstance(_raw, list):
        subtopics = [getattr(s, "task", str(s)) for s in _raw]
    elif hasattr(_raw, "subtopics"):
        subtopics = [getattr(s, "task", str(s)) for s in _raw.subtopics]
    else:
        subtopics = []

    # Return only IdentityData fields
    return {
        "identity_data": {
            "report": result["report"],
            "sources": result["source_urls"],
            "research_sources": result["research_sources"],
            "costs": result["costs"],
            "subtopics": subtopics,
            "needs_reprocessing": False,  # Reset for next cycle
            "feedback_notes": "",  # Reset feedback after research
            "research_iteration": iteration  # Preserve iteration count
        }
    }