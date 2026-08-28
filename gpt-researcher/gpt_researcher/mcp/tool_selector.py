"""
MCP Tool Selection Module

Handles intelligent tool selection using LLM analysis.
"""
import os
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class MCPToolSelector:
    """
    Handles intelligent selection of MCP tools using LLM analysis.
    
    Responsible for:
    - Analyzing available tools with LLM
    - Selecting the most relevant tools for a query
    - Providing fallback selection mechanisms
    """

    def __init__(self, cfg, researcher=None):
        """
        Initialize the tool selector.
        
        Args:
            cfg: Configuration object with LLM settings
            researcher: Researcher instance for cost tracking
        """
        self.cfg = cfg
        self.researcher = researcher

    async def select_relevant_tools(self, query: str, all_tools: List, max_tools: int = 3) -> List:
        """
        Use LLM to select the most relevant tools for the research query.
        
        Args:
            query: Research query
            all_tools: List of all available tools
            max_tools: Maximum number of tools to select (default: 3)
            
        Returns:
            List: Selected tools most relevant for the query
        """
        if not all_tools:
            return []

        # Catalog/wrapper tools (e.g. gdelt_cloud_tool_list, web_research_tool_list,
        # *_tool_call, *_tool_get) are the GATEWAYS to servers such as GDELT and
        # general web research. They MUST stay visible to the LLM so it can select
        # them; otherwise entire servers become unreachable (GDELT is never used and
        # SocialCrawl is over-used for ordinary web lookups). _build_catalog_tools()
        # later expands the selected "*_tool_list" tools into concrete callable tools.
        #
        # We only hide the generic MCP protocol primitives, which are not research
        # tools and only add noise to the selection prompt.
        GENERIC_MCP_PRIMITIVES = {
            "list_resources", "read_resource",
            "list_prompts", "get_prompt",
        }
        filtered_for_llm = [
            tool for tool in all_tools
            if (str(getattr(tool, "name", "") or "").lower()) not in GENERIC_MCP_PRIMITIVES
        ]

        # Use the filtered list for LLM selection; fall back to all tools only if
        # filtering removed everything.
        tools_for_selection = filtered_for_llm or all_tools

        # Fast-path: if available tools count is <= max_tools, return all directly without LLM call
        if len(tools_for_selection) <= max_tools:
            logger.info(f"Fast-path: {len(tools_for_selection)} tools available (<= max_tools {max_tools}), bypassing LLM selection")
            return list(tools_for_selection)
            
        logger.info(f"Using fast LLM to select {max_tools} most relevant tools from {len(all_tools)} available")
        
        # Create concise tool descriptions for LLM analysis
        # IMPORTANT: Iterate over tools_for_selection (the filtered list shown to LLM)
        # so that indices match what the LLM sees and selects from.
        tools_info = []
        for i, tool in enumerate(tools_for_selection):
            desc = tool.description or "No description available"
            if len(desc) > 250:
                desc = desc[:250] + "..."
            tool_info = {
                "index": i,
                "name": tool.name,
                "description": desc
            }
            tools_info.append(tool_info)
        
        # Import here to avoid circular imports
        from ..prompts import PromptFamily

        # Use the original query directly for tool selection to avoid an extra summarization step.
        query_summary = query.strip() or "No query provided"

        # Create prompt for intelligent tool selection
        prompt = PromptFamily.generate_mcp_tool_selection_prompt(query_summary, tools_info, max_tools)

        try:
            # Call LLM for tool selection with strict timeout
            response = await self._call_llm_for_tool_selection(prompt)
            
            if not response:
                logger.warning("No LLM response for tool selection, using fallback")
                return self._fallback_tool_selection(all_tools, max_tools)
            
            # Log a preview of the LLM response for debugging
            response_preview = response[:500] + "..." if len(response) > 500 else response
            logger.debug(f"LLM tool selection response: {response_preview}")
            
            # Parse LLM response
            try:
                selection_result = json.loads(response)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    try:
                        selection_result = json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        logger.warning("Could not parse extracted JSON, using fallback")
                        return self._fallback_tool_selection(all_tools, max_tools)
                else:
                    logger.warning("No JSON found in LLM response, using fallback")
                    return self._fallback_tool_selection(all_tools, max_tools)
            
            selected_tools = []
            
            # Process selected tools
            for tool_selection in selection_result.get("selected_tools", []):
                tool_index = tool_selection.get("index")
                tool_name = tool_selection.get("name", "")
                reason = tool_selection.get("reason", "")
                relevance_score = tool_selection.get("relevance_score", 0)
                
                # Debug: Log the index and tool name the LLM selected
                logger.debug(f"LLM selected index: {tool_index}, tool name: {tool_name}")
                logger.debug(f"Filtered tools list size: {len(tools_for_selection)}")
                
                # Resolve index against tools_for_selection (the list the LLM saw)
                if tool_index is not None and 0 <= tool_index < len(tools_for_selection):
                    selected_tool = tools_for_selection[tool_index]
                    selected_tools.append(selected_tool)
                    logger.info(f"Selected tool '{tool_name}' (score: {relevance_score}): {reason}")
                    
                    # Debug: Log the resolved tool name and description
                    logger.debug(f"Resolved tool: {getattr(selected_tool, 'name', 'unknown')}, description: {getattr(selected_tool, 'description', 'no description')}")
                else:
                    logger.warning(f"Invalid tool index {tool_index} for filtered list size {len(tools_for_selection)}")
            
            if len(selected_tools) == 0:
                logger.warning("No tools selected by LLM, using fallback selection")
                return self._fallback_tool_selection(all_tools, max_tools)
            
            # Log the overall selection reasoning
            selection_reasoning = selection_result.get("selection_reasoning", "No reasoning provided")
            logger.info(f"LLM selection strategy: {selection_reasoning}")
            
            # Auto-include corresponding call tools when list tools are selected
            selected_tools = self._ensure_call_tools(selected_tools, all_tools)
            
            logger.info(f"LLM selected {len(selected_tools)} tools for research")
            return selected_tools
            
        except Exception as e:
            logger.error(f"Error in LLM tool selection: {e}")
            logger.warning("Falling back to pattern-based selection")
            return self._fallback_tool_selection(all_tools, max_tools)

    async def _call_llm_for_tool_selection(self, prompt: str) -> str:
        """
        Call the LLM using the existing create_chat_completion function for tool selection.
        Uses fast_llm_model when available and enforces a configurable timeout via
        the TOOL_SELECTION_TIMEOUT environment variable (default 120.0s).
        """
        if not self.cfg:
            logger.warning("No config available for LLM call")
            return ""
            
        try:
            from ..utils.llm import create_chat_completion
            
            # Create messages for the LLM
            messages = [{"role": "user", "content": prompt}]
            
            # Use the original strategic LLM model as specified in configuration
            selection_model = self.cfg.strategic_llm_model
            selection_provider = self.cfg.strategic_llm_provider

            timeout_val = float(os.environ.get("TOOL_SELECTION_TIMEOUT", "120.0"))
            logger.debug(f"MCP tool selection timeout set to {timeout_val}s")
            result = await asyncio.wait_for(
                create_chat_completion(
                    model=selection_model,
                    messages=messages,
                    temperature=0.0,
                    llm_provider=selection_provider,
                    llm_kwargs=self.cfg.llm_kwargs,
                    cost_callback=self.researcher.add_costs if self.researcher and hasattr(self.researcher, 'add_costs') else None,
                ),
                timeout=timeout_val,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"LLM tool selection timed out after {timeout_val}s. Using instant fallback tool selection.")
            return ""
        except Exception as e:
            logger.error(f"Error calling LLM for tool selection: {e}")
            return ""

    def _fallback_tool_selection(self, all_tools: List, max_tools: int) -> List:
        """
        Fallback tool selection using pattern matching if LLM selection fails.
        """
        research_patterns = [
            'search', 'get', 'read', 'fetch', 'find', 'list', 'query', 
            'lookup', 'retrieve', 'browse', 'view', 'show', 'describe'
        ]
        
        scored_tools = []
        
        for tool in all_tools:
            tool_name = tool.name.lower()
            tool_description = (tool.description or "").lower()
            
            score = 0
            for pattern in research_patterns:
                if pattern in tool_name:
                    score += 3
                if pattern in tool_description:
                    score += 1
            
            if score > 0:
                scored_tools.append((tool, score))
        
        scored_tools.sort(key=lambda x: x[1], reverse=True)
        selected_tools = [tool for tool, score in scored_tools[:max_tools]]
        
        if not selected_tools and all_tools:
            selected_tools = all_tools[:max_tools]
        
        # Auto-include corresponding call tools when list tools are selected
        selected_tools = self._ensure_call_tools(selected_tools, all_tools)
            
        return selected_tools

    def _ensure_call_tools(self, selected_tools: List, all_tools: List) -> List:
        """
        When wrapper-style list tools are selected, ensure the corresponding call tools
        are also included for proper catalog expansion in _build_catalog_tools.
        Also preprocesses tool inputs to ensure they match the expected schema.
        """
        if not selected_tools or not all_tools:
            return selected_tools

        def _tool_name_matches(tool_obj: Any, *fragments: str) -> bool:
            name = str(getattr(tool_obj, "name", "") or "").lower()
            return any(fragment in name for fragment in fragments)

        def _get_matching_tool(tool_obj: Any, suffix: str, available_tools: List) -> Any:
            """Find a tool with the same prefix but different suffix."""
            original_name = str(getattr(tool_obj, "name", "") or "").lower()
            # Extract prefix (e.g., "web_research" from "web_research_tool_list")
            for suffix_frag in ("tool_list", "tool_catalog", "tool_get", "list_tools", "list_tool", "get_tool"):
                if suffix_frag in original_name:
                    prefix = original_name.replace(suffix_frag, "")
                    break
            else:
                return None
            # Find corresponding tool with the suffix
            for t in available_tools:
                t_name = str(getattr(t, "name", "") or "").lower()
                if t_name.startswith(prefix) and suffix in t_name and t_name != original_name:
                    return t
            return None

        # Check if any list tools are selected without their corresponding call tools
        list_tools = [
            tool_obj for tool_obj in selected_tools
            if _tool_name_matches(tool_obj, "tool_list", "tool_catalog", "tool_get", "list_tools", "list_tool", "get_tool")
        ]
        
        if not list_tools:
            return selected_tools

        # Find missing call tools
        call_tools_to_add = []
        for list_tool in list_tools:
            call_tool = _get_matching_tool(list_tool, "tool_call", all_tools)
            if call_tool and call_tool not in selected_tools:
                logger.info(f"Auto-adding corresponding call tool for list tool: {getattr(list_tool, 'name', 'unknown')} -> {getattr(call_tool, 'name', 'unknown')}")
                call_tools_to_add.append(call_tool)

        if call_tools_to_add:
            selected_tools = list(selected_tools) + call_tools_to_add
            logger.info(f"Added {len(call_tools_to_add)} call tools for wrapper expansion")

        return selected_tools

    async def invoke_tool_with_validation(self, tool: Any, tool_input: Dict[str, Any]) -> Any:
        """
        Invoke a tool with input validation and preprocessing.
        
        Args:
            tool: The tool to invoke.
            tool_input: Raw input dictionary for the tool.
            
        Returns:
            Result of the tool invocation.
        """
        try:
            # Preprocess the input to ensure it matches the tool's schema
            processed_input = preprocess_tool_input(
                tool_name=getattr(tool, "name", "unknown"),
                tool_input=tool_input
            )
            
            # Log the processed input for debugging
            logger.debug(f"Invoking tool '{getattr(tool, 'name', 'unknown')}' with input: {processed_input}")
            
            # Invoke the tool
            if hasattr(tool, "ainvoke"):
                return await tool.ainvoke(processed_input)
            elif hasattr(tool, "invoke"):
                return tool.invoke(processed_input)
            else:
                raise AttributeError(f"Tool {getattr(tool, 'name', 'unknown')} has no invoke or ainvoke method")
                
        except Exception as e:
            logger.error(f"Error invoking tool {getattr(tool, 'name', 'unknown')}: {e}")
            raise

    def preprocess_tool_input(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess tool inputs to ensure they match the expected schema.
        Handles common issues like:
        - Missing required fields (e.g., `query`, `category`).
        - Malformed inputs (e.g., `raw_args` instead of `query`).
        - Invalid enum values (e.g., `Political Conflict` instead of `POLITICAL`).
        
        Args:
            tool_name: Name of the tool being invoked.
            tool_input: Raw input dictionary provided to the tool.
            
        Returns:
            Processed input dictionary that matches the tool's schema.
        """
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
                raise ValueError(f"Invalid category: '{category}'. Must be one of: {list(category_mapping.keys())}")
        
        return processed_input