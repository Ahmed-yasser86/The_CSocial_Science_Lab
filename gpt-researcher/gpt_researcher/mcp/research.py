"""
MCP Research Execution Skill

Handles research execution using selected MCP tools as a skill component.
"""
import asyncio
import json
import logging
from typing import List, Dict, Any

from langchain_core.tools import Tool

from .normalization import preprocess_mcp_tool_input

logger = logging.getLogger(__name__)


class MCPResearchSkill:
    """
    Handles research execution using selected MCP tools.
    
    Responsible for:
    - Executing research with LLM and bound tools
    - Processing tool results into standard format
    - Managing tool execution and error handling
    """

    def __init__(self, cfg, researcher=None):
        """
        Initialize the MCP research skill.
        
        Args:
            cfg: Configuration object with LLM settings
            researcher: Researcher instance for cost tracking
        """
        self.cfg = cfg
        self.researcher = researcher

    async def conduct_research_with_tools(self, query: str, selected_tools: List) -> List[Dict[str, str]]:
        """
        Use LLM with bound tools to conduct intelligent research.
        
        Args:
            query: Research query
            selected_tools: List of selected MCP tools
            
        Returns:
            List[Dict[str, str]]: Research results in standard format
        """
        if not selected_tools:
            logger.warning("No tools available for research")
            return []
            
        logger.info(f"Conducting research using {len(selected_tools)} selected tools")
        
        try:
            from ..llm_provider.generic.base import GenericLLMProvider
            
            # Create LLM provider using the config
            provider_kwargs = {
                'model': self.cfg.strategic_llm_model,
                **self.cfg.llm_kwargs
            }
            
            llm_provider = GenericLLMProvider.from_provider(
                self.cfg.strategic_llm_provider, 
                **provider_kwargs
            )
            
            # Expand wrapper-style MCP servers (for example GDELT Cloud or Media Intelligence)
            # into concrete callable tools before binding them to the LLM.
            selected_tools = await self._build_catalog_tools(selected_tools)

            # Bind tools to LLM
            llm_with_tools = llm_provider.llm.bind_tools(selected_tools)
            
            # Import here to avoid circular imports
            from ..prompts import PromptFamily
            
            # Create research prompt
            research_prompt = PromptFamily.generate_mcp_research_prompt(query, selected_tools)

            # Create messages
            messages = [{"role": "user", "content": research_prompt}]
            
            # Invoke LLM with tools
            logger.info("LLM researching with bound tools...")
            response = await llm_with_tools.ainvoke(messages)
            
            # Process tool calls and results
            research_results = []
            
            # Check if the LLM made tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"LLM made {len(response.tool_calls)} tool calls")
                
                # Process each tool call
                for i, tool_call in enumerate(response.tool_calls, 1):
                    tool_name = tool_call.get("name") or tool_call.get("tool_name") or "unknown"
                    raw_args = tool_call.get("args", {})
                    # Handle args that might be a JSON string or already a dict
                    if isinstance(raw_args, str):
                        try:
                            tool_args = json.loads(raw_args)
                        except (json.JSONDecodeError, TypeError):
                            # If it's not valid JSON, wrap it as a tool_arguments value
                            tool_args = {"tool_arguments": raw_args}
                    elif isinstance(raw_args, dict):
                        tool_args = raw_args
                    else:
                        tool_args = {"tool_arguments": raw_args}
                    available_tool_names = {getattr(t, "name", None) for t in selected_tools if getattr(t, "name", None)}
                    
                    if tool_name not in available_tool_names:
                        logger.warning(
                            "Rejecting invalid MCP tool call '%s'. Valid names: %s",
                            tool_name,
                            sorted(available_tool_names),
                        )
                        continue
                    
                    logger.info(f"Executing tool {i}/{len(response.tool_calls)}: {tool_name}")
                    
                    # Log the tool arguments for transparency
                    if tool_args:
                        args_str = ", ".join([f"{k}={v}" for k, v in tool_args.items()])
                        logger.debug(f"Tool arguments: {args_str}")
                    
                    try:
                        # Find the tool by name
                        tool = next((t for t in selected_tools if getattr(t, "name", None) == tool_name), None)
                        if not tool:
                            logger.warning(
                                "Tool %s not found in selected tools. Available tool names: %s",
                                tool_name,
                                sorted(available_tool_names),
                            )
                            continue

                        resolved_tool = self._resolve_socialcrawl_tool(tool_name, tool_args, selected_tools)
                        if resolved_tool is None:
                            logger.warning("Skipping invalid SocialCrawl request for %s with args %s", tool_name, tool_args)
                            continue
                        tool, tool_name, tool_args = resolved_tool
                        
                        logger.info("After SocialCrawl resolution: tool_name=%s, tool_args=%s", tool_name, tool_args)

                        # Fix schema-level issues (e.g. `raw_args` -> `query` for
                        # SEARCH_WEB, `category` aliases for SEARCH_STORIES) BEFORE any
                        # numeric coercion, otherwise the MCP server returns a
                        # validation error inside the tool response body.
                        normalized_tool_args = preprocess_mcp_tool_input(tool_name, tool_args)
                        if normalized_tool_args != tool_args:
                            logger.info("Preprocessed MCP arguments for %s before execution: %s", tool_name, normalized_tool_args)
                        tool_args = normalized_tool_args

                        normalized_tool_args = self._normalize_tool_arguments(tool_name, tool_args)
                        if normalized_tool_args != tool_args:
                            logger.info("Normalized MCP arguments for %s before execution: %s", tool_name, normalized_tool_args)
                        tool_args = normalized_tool_args
                        
                        # Execute the tool
                        if hasattr(tool, 'ainvoke'):
                            result = await tool.ainvoke(tool_args)
                        elif hasattr(tool, 'invoke'):
                            result = tool.invoke(tool_args)
                        else:
                            result = await tool(tool_args) if asyncio.iscoroutinefunction(tool) else tool(tool_args)
                        
                        # Log the actual tool response for debugging
                        if result:
                            result_preview = str(result)[:500] + "..." if len(str(result)) > 500 else str(result)
                            logger.debug(f"Tool {tool_name} response preview: {result_preview}")
                            
                            # Process the result
                            formatted_results = self._process_tool_result(tool_name, result)
                            research_results.extend(formatted_results)
                            logger.info(f"Tool {tool_name} returned {len(formatted_results)} formatted results")
                            
                            # Log details of each formatted result
                            for j, formatted_result in enumerate(formatted_results):
                                title = formatted_result.get("title", "No title")
                                content_preview = formatted_result.get("body", "")[:200] + "..." if len(formatted_result.get("body", "")) > 200 else formatted_result.get("body", "")
                                logger.debug(f"Result {j+1}: '{title}' - Content: {content_preview}")
                        else:
                            logger.warning(f"Tool {tool_name} returned empty result")
                            
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}")
                        continue
                        
            # Also include the LLM's own analysis/response as a result
            if hasattr(response, 'content') and response.content:
                llm_analysis = {
                    "title": f"LLM Analysis: {query}",
                    "href": "mcp://llm_analysis",
                    "body": response.content
                }
                research_results.append(llm_analysis)
                
                # Log LLM analysis content
                analysis_preview = response.content[:300] + "..." if len(response.content) > 300 else response.content
                logger.debug(f"LLM Analysis: {analysis_preview}")
                logger.info("Added LLM analysis to results")
            
            logger.info(f"Research completed with {len(research_results)} total results")
            return research_results
            
        except Exception as e:
            logger.error(f"Error in LLM research with tools: {e}")
            return []

    async def _build_catalog_tools(self, selected_tools: List) -> List:
        """Expand wrapper-style MCP tools into concrete callable tools.

        Some MCP servers expose a progressive-discovery pattern where the actual
        capabilities are discovered via wrapper tools such as
        ``tool_list`` / ``tool_get`` / ``tool_call``. The LLM can work much more
        reliably if we expose the discovered catalog items as direct tools.
        """
        if not selected_tools:
            return []

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

        has_wrapper_tools = any(
            _tool_name_matches(tool_obj, "tool_list", "tool_catalog", "tool_get", "tool_call", "list_tools", "list_tool", "get_tool", "call_tool")
            for tool_obj in selected_tools
        )
        if not has_wrapper_tools:
            return selected_tools

        # Find all list and call tool pairs
        list_tools = [
            tool_obj for tool_obj in selected_tools
            if _tool_name_matches(tool_obj, "tool_list", "tool_catalog", "tool_get", "list_tools", "list_tool", "get_tool")
        ]
        call_tools = [
            tool_obj for tool_obj in selected_tools
            if _tool_name_matches(tool_obj, "tool_call", "call_tool", "invoke_tool")
        ]

        if not list_tools:
            return selected_tools

        # Build a map of list tool name to its corresponding call tool
        list_to_call_map = {}  # Maps list tool name -> call tool object
        for list_tool in list_tools:
            call_tool = next(
                (t for t in call_tools if _get_matching_tool(list_tool, "tool_call", [t])),
                None
            )
            if not call_tool:
                # Try to find call tool in all selected tools
                call_tool = _get_matching_tool(list_tool, "tool_call", selected_tools)
            if call_tool:
                list_name = getattr(list_tool, "name", "") or str(list_tool)
                list_to_call_map[list_name] = (list_tool, call_tool)

        if not list_to_call_map:
            return selected_tools

        dynamic_tools: List[Any] = []

        # Process each list tool and its corresponding call tool
        for list_name, (list_tool, call_tool) in list_to_call_map.items():
            try:
                if hasattr(list_tool, "ainvoke"):
                    list_result = await list_tool.ainvoke({})
                elif hasattr(list_tool, "invoke"):
                    list_result = list_tool.invoke({})
                else:
                    list_result = await list_tool({}) if asyncio.iscoroutinefunction(list_tool) else list_tool({})
            except Exception as exc:
                logger.warning("Could not discover MCP catalog tools from %s: %s", getattr(list_tool, "name", "unknown"), exc)
                continue

            catalog_entries = self._extract_catalog_entries(list_result)
            if not catalog_entries:
                logger.warning("No catalog entries found from MCP wrapper tool %s", getattr(list_tool, "name", "unknown"))
                continue

            for entry in catalog_entries:
                tool_name = entry.get("name") or entry.get("tool_name")
                if not tool_name:
                    continue

                description = (
                    entry.get("description")
                    or entry.get("summary")
                    or entry.get("detail")
                    or ""
                )
                if description:
                    description = f"{tool_name}: {description}"
                else:
                    description = f"Execute the MCP catalog tool '{tool_name}' via the server wrapper."

                # Capture call_tool in closure
                wrapper_tool = call_tool

                async def invoke_catalog_tool(tool_arguments: Any = None, *, actual_tool_name: str = tool_name, wrapper_tool: Any = wrapper_tool):
                    # Parse tool_arguments if it's a JSON string (some LLM providers send args as string)
                    if isinstance(tool_arguments, str):
                        try:
                            tool_arguments = json.loads(tool_arguments)
                        except (json.JSONDecodeError, TypeError):
                            tool_arguments = {"raw_args": tool_arguments}

                    # Normalize schema issues (e.g. `raw_args` -> `query`) before
                    # forwarding to the catalog wrapper so the underlying tool
                    # receives the field it actually expects.
                    tool_arguments = preprocess_mcp_tool_input(actual_tool_name, tool_arguments or {})

                    payload = {
                        "tool_name": actual_tool_name,
                        "tool_arguments": tool_arguments or {},
                    }
                    if hasattr(wrapper_tool, "ainvoke"):
                        return await wrapper_tool.ainvoke(payload)
                    if hasattr(wrapper_tool, "invoke"):
                        return wrapper_tool.invoke(payload)
                    return await wrapper_tool(payload) if asyncio.iscoroutinefunction(wrapper_tool) else wrapper_tool(payload)

                dynamic_tools.append(
                    Tool.from_function(
                        func=invoke_catalog_tool,
                        name=str(tool_name),
                        description=str(description),
                        coroutine=invoke_catalog_tool,
                    )
                )

        if dynamic_tools:
            logger.info("Exposed %d concrete tools discovered from MCP catalog wrappers", len(dynamic_tools))
            return dynamic_tools

        return selected_tools

    def _resolve_socialcrawl_tool(self, tool_name: str, tool_args: Any, selected_tools: List) -> Any:
        """Resolve platform-specific SocialCrawl tools before execution."""
        if tool_name != "socialcrawl_request":
            return (next((t for t in selected_tools if getattr(t, "name", None) == tool_name), None), tool_name, tool_args)

        params = tool_args.get("params", tool_args) if isinstance(tool_args, dict) else {}
        if not isinstance(params, dict):
            logger.warning(
                "SocialCrawl params is not a dict: tool_name=%s, tool_args=%s, params=%s",
                tool_name, tool_args, params
            )
            return (next((t for t in selected_tools if getattr(t, "name", None) == tool_name), None), tool_name, tool_args)

        platform = str(params.get("platform") or params.get("source") or "").lower()
        logger.info("SocialCrawl tool resolution: tool_name=%s, platform='%s', params keys=%s", 
                    tool_name, platform, list(params.keys()))
        
        if platform in {"web", "website", "browser"}:
            web_tool = next((t for t in selected_tools if getattr(t, "name", None) == "socialcrawl_web"), None)
            if web_tool is not None:
                logger.info("Resolving socialcrawl_request (platform=%s) to socialcrawl_web", platform)
                return (web_tool, "socialcrawl_web", tool_args)

        ids = params.get("ids")
        if ids is not None and isinstance(ids, (list, tuple, set)) and len(ids) == 0:
            logger.warning("Skipping SocialCrawl request with empty ids payload for tool %s", tool_name)
            return None

        if ids is not None and isinstance(ids, str) and ids.strip() == "":
            logger.warning("Skipping SocialCrawl request with empty ids payload for tool %s", tool_name)
            return None

        request_tool = next((t for t in selected_tools if getattr(t, "name", None) == tool_name), None)
        return (request_tool, tool_name, tool_args)

    def _normalize_tool_arguments(self, tool_name: str, tool_args: Any) -> Any:
        """Normalize tool arguments to match strict remote MCP schemas.

        Some servers (for example SocialCrawl) require params such as ``limit`` to
        be strings instead of integers even when the model emits numeric values.
        """
        if not isinstance(tool_args, dict):
            return tool_args

        normalized = {}
        for key, value in tool_args.items():
            if isinstance(value, dict):
                normalized[key] = self._normalize_tool_arguments(tool_name, value)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                if str(key).lower() in {"limit", "page_size", "offset", "max_results", "count", "timeout"}:
                    normalized[key] = str(value)
                else:
                    normalized[key] = value
            else:
                normalized[key] = value

        if "params" in normalized and isinstance(normalized["params"], dict):
            params = normalized["params"]
            for key, value in list(params.items()):
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if str(key).lower() in {"limit", "page_size", "offset", "max_results", "count", "timeout"}:
                        params[key] = str(value)

        return normalized

    def _extract_catalog_entries(self, result: Any) -> List[Dict[str, Any]]:
        """Parse tool-list responses returned by MCP wrapper tools."""
        if isinstance(result, list):
            entries = []
            for item in result:
                if isinstance(item, dict):
                    # Handle MCP wrapper response format: list of dicts with "text" field containing JSON
                    if "text" in item and isinstance(item.get("text"), str):
                        try:
                            parsed = json.loads(item["text"])
                            nested_entries = self._extract_catalog_entries(parsed)
                            if nested_entries:
                                entries.extend(nested_entries)
                                continue
                        except json.JSONDecodeError:
                            pass
                    entries.append(item)
                elif isinstance(item, str):
                    entries.append({"name": item, "description": item})
            return entries

        if isinstance(result, dict):
            # Handle common wrapper response shapes.
            for key in ("tools", "data", "items", "catalog"):
                value = result.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]

            if isinstance(result.get("structured_content"), dict):
                return self._extract_catalog_entries(result["structured_content"])

            if isinstance(result.get("content"), list):
                for part in result["content"]:
                    if isinstance(part, dict):
                        text = part.get("text")
                        if isinstance(text, str):
                            try:
                                parsed = json.loads(text)
                            except json.JSONDecodeError:
                                continue
                            entries = self._extract_catalog_entries(parsed)
                            if entries:
                                return entries
                return []

            if isinstance(result.get("content"), str):
                try:
                    parsed = json.loads(result["content"])
                except json.JSONDecodeError:
                    return []
                return self._extract_catalog_entries(parsed)

        return []

    def _process_tool_result(self, tool_name: str, result: Any) -> List[Dict[str, str]]:
        """
        Process tool result into search result format.
        
        Args:
            tool_name: Name of the tool that produced the result
            result: The tool result
            
        Returns:
            List[Dict[str, str]]: Formatted search results
        """
        search_results = []
        
        try:
            # 1) First: handle MCP result wrapper with structured_content/content
            if isinstance(result, dict) and ("structured_content" in result or "content" in result):
                search_results = []
                # Prefer structured_content when present
                structured = result.get("structured_content")
                if isinstance(structured, dict):
                    items = structured.get("results")
                    if isinstance(items, list):
                        for i, item in enumerate(items):
                            if isinstance(item, dict):
                                search_results.append({
                                    "title": item.get("title", f"Result from {tool_name} #{i+1}"),
                                    "href": item.get("href", item.get("url", f"mcp://{tool_name}/{i}")),
                                    "body": item.get("body", item.get("content", str(item)))
                                })
                    # If no items array but structured is dict, treat as single
                    elif isinstance(structured, dict):
                        search_results.append({
                            "title": structured.get("title", f"Result from {tool_name}"),
                            "href": structured.get("href", structured.get("url", f"mcp://{tool_name}")),
                            "body": structured.get("body", structured.get("content", str(structured)))
                        })
                # Fallback to content if provided (MCP spec: list of {type: text, text: ...})
                if not search_results:
                    content_field = result.get("content")
                    if isinstance(content_field, list):
                        texts = []
                        for part in content_field:
                            if isinstance(part, dict):
                                if part.get("type") == "text" and isinstance(part.get("text"), str):
                                    texts.append(part["text"])
                                elif "text" in part:
                                    texts.append(str(part.get("text")))
                                else:
                                    # unknown piece; stringify
                                    texts.append(str(part))
                            else:
                                texts.append(str(part))
                        body_text = "\n\n".join([t for t in texts if t])
                    elif isinstance(content_field, str):
                        body_text = content_field
                    else:
                        body_text = str(result)
                    search_results.append({
                        "title": f"Result from {tool_name}",
                        "href": f"mcp://{tool_name}",
                        "body": body_text,
                    })
                return search_results

            # 2) If the result is already a list, process each item normally
            if isinstance(result, list):
                # If the result is already a list, process each item
                for i, item in enumerate(result):
                    if isinstance(item, dict):
                        # Use the item as is if it has required fields
                        if "title" in item and ("content" in item or "body" in item):
                            search_result = {
                                "title": item.get("title", ""),
                                "href": item.get("href", item.get("url", f"mcp://{tool_name}/{i}")),
                                "body": item.get("body", item.get("content", str(item))),
                            }
                            search_results.append(search_result)
                        else:
                            # Create a search result with a generic title
                            search_result = {
                                "title": f"Result from {tool_name}",
                                "href": f"mcp://{tool_name}/{i}",
                                "body": str(item),
                            }
                            search_results.append(search_result)
            # 3) If the result is a dict (non-MCP wrapper), use it as a single search result
            elif isinstance(result, dict):
                # If the result is a dictionary, use it as a single search result
                search_result = {
                    "title": result.get("title", f"Result from {tool_name}"),
                    "href": result.get("href", result.get("url", f"mcp://{tool_name}")),
                    "body": result.get("body", result.get("content", str(result))),
                }
                search_results.append(search_result)
            else:
                # For any other type, convert to string and use as a single search result
                search_result = {
                    "title": f"Result from {tool_name}",
                    "href": f"mcp://{tool_name}",
                    "body": str(result),
                }
                search_results.append(search_result)
                
        except Exception as e:
            logger.error(f"Error processing tool result from {tool_name}: {e}")
            # Fallback: create a basic result
            search_result = {
                "title": f"Result from {tool_name}",
                "href": f"mcp://{tool_name}",
                "body": str(result),
            }
            search_results.append(search_result)
        
        return search_results 