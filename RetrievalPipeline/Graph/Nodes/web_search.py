"""
Web Search Node for Retrieval Pipeline

This module provides web search functionality using GPT-Researcher's retriever pattern.
It supports multiple search providers:
- TavilySearch: Primary web search with full Tavily API capabilities
- SocialCrawl: MCP-based search for social media and web content
- GDELT: MCP-based search for news and events

The philosophy follows the original GPT-Researcher architecture where:
1. get_search_results() handles retriever instantiation and search execution
2. Multiple retrievers can be configured and used
3. Each retriever follows a consistent interface: retriever(query, **kwargs).search(max_results=N)
"""

from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from langchain_core.documents import Document
import asyncio
import os
import logging

from RetrievalPipeline.Graph.StateGraph import GraphState
from gpt_researcher.retrievers import TavilySearch
from gpt_researcher.retrievers.mcp.retriever import MCPRetriever

load_dotenv()

logger = logging.getLogger(__name__)

# Default max results for each retriever
DEFAULT_TAVILY_MAX_RESULTS = 5
DEFAULT_SOCIALCRAWL_MAX_RESULTS = 5
DEFAULT_GDELT_MAX_RESULTS = 5


def normalize_query_for_tavily(query: str, max_chars: int = 400) -> str:
    """Trim overly long queries so Tavily accepts them."""
    if not isinstance(query, str):
        query = str(query or "")
    return query.strip()[:max_chars]


async def get_search_results_async(
    query: str,
    retriever_class: Any,
    query_domains: List[str] = None,
    researcher=None,
    max_results: int = 5,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Get web search results using GPT-Researcher's retriever pattern.
    
    This function follows the same philosophy as gpt_researcher.actions.query_processing.get_search_results:
    - Instantiates the retriever with query and query_domains
    - Calls the search method with max_results
    - Handles MCP retrievers specially by passing the researcher instance
    
    Args:
        query: The search query
        retriever_class: The retriever class (e.g., TavilySearch, MCPRetriever)
        query_domains: Optional list of domains to restrict search to
        researcher: Researcher instance (needed for MCP retrievers)
        max_results: Maximum number of results to return
        **kwargs: Additional arguments passed to the retriever
        
    Returns:
        List of search results with 'href', 'body', 'title' keys
    """
    # Check if this is an MCP retriever and pass the researcher instance
    if "mcpretriever" in retriever_class.__name__.lower():
        search_retriever = retriever_class(
            query,
            query_domains=query_domains,
            researcher=researcher,
            **kwargs
        )
    else:
        search_retriever = retriever_class(query, query_domains=query_domains, **kwargs)
    
    # Retriever searches are blocking HTTP calls; keep the event loop free
    return await asyncio.to_thread(search_retriever.search, max_results=max_results)


def websearch(state: GraphState):
    """
    Web search node that uses GPT-Researcher's retriever pattern.
    
    Supports multiple search providers in priority order:
    1. TavilySearch - Primary web search (default)
    2. MCPRetriever - For SocialCrawl and GDELT MCP servers
    
    This follows the original GPT-Researcher philosophy where:
    - retrievers are configured via config/headers
    - get_search_results handles the search execution
    - Results are formatted consistently
    """
    question = state.get("question", "")
    documents = state.get("documents", [])
    
    if not question:
        return {"documents": documents, "question": question}
    
    normalized_question = normalize_query_for_tavily(question)
    
    # Log the search configuration
    logger.info(f"Web search for query: {normalized_question[:100]}...")
    
    try:
        # Use TavilySearch as the primary retriever (same as GPT-Researcher default)
        # This follows the pattern: retriever(query, query_domains).search(max_results=N)
        tavily_retriever = TavilySearch(
            query=normalized_question,
            query_domains=None  # Could be extended to use state.get("query_domains")
        )
        
        # Execute search using asyncio.to_thread to avoid blocking
        # This is the same pattern used in gpt_researcher.actions.query_processing.get_search_results
        tavily_response = asyncio.run(
            asyncio.to_thread(tavily_retriever.search, max_results=DEFAULT_TAVILY_MAX_RESULTS)
        )
        
        # Process Tavily response
        if isinstance(tavily_response, dict) and "results" in tavily_response:
            results = tavily_response["results"]
        else:
            results = tavily_response or []
        
        if not isinstance(results, list):
            results = [results] if results else []
        
        # Format results consistently with GPT-Researcher output
        # Each result should have: href, body, title (optional)
        formatted_results = []
        for res in results:
            if isinstance(res, dict):
                href = res.get("url") or res.get("href", "")
                body = res.get("content") or res.get("body") or res.get("snippet", "")
                title = res.get("title", "")
                if href:  # Only include results with valid URLs
                    formatted_results.append({
                        "href": href,
                        "body": body,
                        "title": title
                    })
        
        # Join results into a single document (same pattern as GPT-Researcher)
        if formatted_results:
            joined_results = "\n\n".join(
                f"Source: {r['href']}\nContent: {r['body']}" 
                for r in formatted_results
            )
        else:
            joined_results = "No search results found."
        
        web_results = Document(page_content=joined_results)
        
        # Append to existing documents
        if isinstance(documents, list):
            documents.append(web_results)
            updated_documents = documents
        else:
            updated_documents = [web_results]
        
        logger.info(f"Web search returned {len(formatted_results)} results")
        
        return {"documents": updated_documents, "question": question}
        
    except Exception as e:
        logger.error(f"Web search error: {e}")
        # Return empty results on error (graceful degradation like GPT-Researcher)
        error_doc = Document(page_content=f"Web search failed: {str(e)}")
        if isinstance(documents, list):
            documents.append(error_doc)
            updated_documents = documents
        else:
            updated_documents = [error_doc]
        return {"documents": updated_documents, "question": question}


async def websearch_async(state: GraphState) -> Dict[str, Any]:
    """
    Async version of web search node for use in async pipelines.
    
    Supports:
    - TavilySearch with full API capabilities (search, answer, extract)
    - MCPRetriever for SocialCrawl and GDELT MCP integration
    """
    question = state.get("question", "")
    documents = state.get("documents", [])
    
    if not question:
        return {"documents": documents, "question": question}
    
    normalized_question = normalize_query_for_tavily(question)
    
    try:
        # Primary search using TavilySearch (GPT-Researcher default)
        tavily_results = await get_search_results_async(
            query=normalized_question,
            retriever_class=TavilySearch,
            max_results=DEFAULT_TAVILY_MAX_RESULTS
        )
        
        # Process results
        if isinstance(tavily_results, dict) and "results" in tavily_results:
            results = tavily_results["results"]
        else:
            results = tavily_results or []
        
        if not isinstance(results, list):
            results = [results] if results else []
        
        # Format for output
        formatted_results = []
        for res in results:
            if isinstance(res, dict):
                href = res.get("url") or res.get("href", "")
                body = res.get("content") or res.get("body") or res.get("snippet", "")
                title = res.get("title", "")
                if href:
                    formatted_results.append({
                        "href": href,
                        "body": body,
                        "title": title
                    })
        
        # Try SocialCrawl MCP if configured and Tavily returns few results
        socialcrawl_results = []
        mcp_configs = state.get("mcp_configs")
        if mcp_configs and len(formatted_results) < 3:
            try:
                # Use MCPRetriever for SocialCrawl
                socialcrawl_results = await get_search_results_async(
                    query=normalized_question,
                    retriever_class=MCPRetriever,
                    researcher=state.get("researcher"),
                    max_results=DEFAULT_SOCIALCRAWL_MAX_RESULTS
                )
                if socialcrawl_results:
                    logger.info(f"SocialCrawl returned {len(socialcrawl_results)} additional results")
            except Exception as e:
                logger.warning(f"SocialCrawl search failed: {e}")
        
        # Combine results (Tavily primary, SocialCrawl supplementary)
        all_results = formatted_results + socialcrawl_results
        
        if all_results:
            joined_results = "\n\n".join(
                f"Source: {r['href']}\nContent: {r.get('body', '')}"
                for r in all_results
            )
        else:
            joined_results = "No search results found."
        
        web_results = Document(page_content=joined_results)
        
        if isinstance(documents, list):
            documents.append(web_results)
            updated_documents = documents
        else:
            updated_documents = [web_results]
        
        logger.info(f"Combined web search returned {len(all_results)} results (Tavily: {len(formatted_results)}, SocialCrawl: {len(socialcrawl_results)})")
        
        return {"documents": updated_documents, "question": question}
        
    except Exception as e:
        logger.error(f"Async web search error: {e}")
        error_doc = Document(page_content=f"Web search failed: {str(e)}")
        if isinstance(documents, list):
            documents.append(error_doc)
            updated_documents = documents
        else:
            updated_documents = [error_doc]
        return {"documents": updated_documents, "question": question}
