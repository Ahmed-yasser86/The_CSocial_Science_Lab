# Nodes/IdentityResearchNode/IdentityResearchNode.py
from typing import Any, Dict
from Retrival_Pipline.Graph.Chains.IdentityResearch import research_identity
from StateGraph import GraphState


async def make_identity_research(state: GraphState) -> Dict[str, Any]:
    """
    Identity Research Node: Performs research and returns IdentityData.
    """
    print("---IDENTITY RESEARCH NODE---")
    
    chain_input = state.get("chain_input", {})
    query = chain_input.get("query", "")
    
    # Get existing identity data to preserve iteration count
    identity_data_existing = state.get("identity_data", {})
    iteration = identity_data_existing.get("research_iteration", 1)
    
    print(f"🔍 Researching: '{query}' (Iteration {iteration})")
    
    # Perform research
    result = await research_identity(query=query)
    
    # Return only IdentityData fields
    return {
        "identity_data": {
            "report": result["report"],
            "sources": result["source_urls"],
            "research_sources": result["research_sources"],
            "costs": result["costs"],
            "subtopics": result.get("subtopics", []),
            "needs_reprocessing": False,  # Reset for next cycle
            "feedback_notes": "",  # Reset feedback after research
            "research_iteration": iteration  # Preserve iteration count
        }
    }