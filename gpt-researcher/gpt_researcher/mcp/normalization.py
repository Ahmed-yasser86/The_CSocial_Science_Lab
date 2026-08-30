"""
Shared MCP tool-input normalization.

Several MCP servers use strict Pydantic input schemas. LLM tool-call
arguments are frequently malformed in ways that cause the *server* to reject
the call and return a validation error inside the tool response body (e.g.
``1 validation error for SearchWebInput / query / Field required``).

This module centralizes the fixes so every invocation path -- direct tool
calls, catalog-wrapped calls, and the ToolSelector validation path -- applies
the same normalization.
"""
from typing import Any, Dict


def preprocess_mcp_tool_input(tool_name: str, tool_input: Any) -> Any:
    """Normalize raw MCP tool arguments to match the server's schema.

    Handles common issues such as:
    - ``raw_args`` emitted by the model instead of the required ``query``
      (SEARCH_WEB).
    - Missing required ``category`` for SEARCH_STORIES, including mapping of
      common free-text aliases to the server's accepted enum values.

    Args:
        tool_name: Name of the MCP tool being invoked.
        tool_input: Raw input dictionary produced from the LLM tool call.

    Returns:
        A processed input dictionary that conforms to the tool's schema.
        Non-dict inputs are returned unchanged.
    """
    if not isinstance(tool_input, dict):
        return tool_input

    processed_input = tool_input.copy()

    # Handle SEARCH_WEB: Ensure `query` is present
    if tool_name == "SEARCH_WEB":
        if "query" not in processed_input and "raw_args" in processed_input:
            processed_input["query"] = processed_input.pop("raw_args")
        elif "query" not in processed_input:
            raise ValueError("Missing required field: 'query' for SEARCH_WEB tool")

    # Handle SEARCH_STORIES: Validate and transform `category`
    elif tool_name == "SEARCH_STORIES":
        if "category" not in processed_input:
            raise ValueError("Missing required field: 'category' for SEARCH_STORIES tool")

        # Map common category aliases to valid enum values
        category_mapping = {
            "political conflict": "POLITICAL",
            "political": "POLITICAL",
            "conflict": "POLITICAL",
            "crime": "CRIME",
            "economic": "ECONOMIC",
            "corporate": "CORPORATE",
            "technology": "TECHNOLOGY",
            "infrastructure": "INFRASTRUCTURE",
            "environment": "ENVIRONMENT",
            "health": "HEALTH",
            "demographic": "DEMOGRAPHIC",
            "information": "INFORMATION",
        }

        category = processed_input["category"].lower()
        if category in category_mapping:
            processed_input["category"] = category_mapping[category]
        elif category not in {
            "battles", "protests", "riots", "explosions/remote violence",
            "violence against civilians", "strategic developments",
            "political", "crime", "economic", "corporate",
            "technology", "infrastructure", "environment",
            "health", "demographic", "information"
        }:
            raise ValueError(
                f"Invalid category: '{category}'. Must be one of: {list(category_mapping.keys())}"
            )

    return processed_input
