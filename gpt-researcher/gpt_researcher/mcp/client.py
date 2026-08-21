"""
MCP Client Management Module

Handles MCP client creation, configuration conversion, and connection management.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional

try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    HAS_MCP_ADAPTERS = True
except ImportError:
    HAS_MCP_ADAPTERS = False

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    Manages MCP client lifecycle and configuration.
    
    Responsible for:
    - Converting GPT Researcher MCP configs to langchain format
    - Creating and managing MultiServerMCPClient instances
    - Handling client cleanup and resource management
    """

    def __init__(self, mcp_configs: List[Dict[str, Any]]):
        """
        Initialize the MCP client manager.
        
        Args:
            mcp_configs: List of MCP server configurations from GPT Researcher
        """
        self.mcp_configs = mcp_configs or []
        self._client = None
        self._client_lock = None
        self._client_lock_loop = None

    def _get_client_lock(self) -> asyncio.Lock:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._client_lock is None or self._client_lock_loop != loop:
            self._client_lock = asyncio.Lock()
            self._client_lock_loop = loop
        return self._client_lock

    def convert_configs_to_langchain_format(self) -> Dict[str, Dict[str, Any]]:
        """
        Convert GPT Researcher MCP configs to langchain-mcp-adapters format.
        
        Returns:
            Dict[str, Dict[str, Any]]: Server configurations for MultiServerMCPClient
        """
        server_configs = {}
        
        for i, config in enumerate(self.mcp_configs):
            # Generate server name
            server_name = config.get("name", f"mcp_server_{i+1}")
            
            # Build the server config
            server_config = {}
            
            # Auto-detect transport type from URL if provided
            connection_url = config.get("connection_url") or config.get("url")
            if connection_url:
                if connection_url.startswith(("wss://", "ws://")):
                    server_config["transport"] = "websocket"
                    server_config["url"] = connection_url
                elif connection_url.startswith(("https://", "http://")):
                    server_config["transport"] = "streamable_http"
                    server_config["url"] = connection_url
                else:
                    # Fallback to specified connection_type, transport, or stdio
                    connection_type = config.get("connection_type") or config.get("transport") or "stdio"
                    server_config["transport"] = connection_type
                    if connection_type in ["websocket", "streamable_http", "http"]:
                        server_config["url"] = connection_url
            else:
                # No URL provided, use stdio (default) or specified connection_type
                connection_type = config.get("connection_type") or config.get("transport") or "stdio"
                server_config["transport"] = connection_type
            
            if server_config.get("transport") in ["streamable_http", "http", "websocket"]:
                connection_headers = config.get("connection_headers") or config.get("headers")
                if connection_headers and isinstance(connection_headers, dict):
                    server_config["headers"] = connection_headers
            
            # Handle stdio transport configuration
            if server_config.get("transport") == "stdio":
                if config.get("command"):
                    server_config["command"] = config["command"]
                    
                    # Handle server_args
                    server_args = config.get("args", [])
                    if isinstance(server_args, str):
                        server_args = server_args.split()
                    server_config["args"] = server_args
                    
                    # Handle environment variables
                    server_env = config.get("env", {})
                    if server_env:
                        server_config["env"] = server_env
                        
            # Add authentication if provided
            if config.get("connection_token"):
                token = config["connection_token"]
                # streamable_http/http/websocket transports may not accept a
                # top-level `token` kwarg. Move token into headers as a
                # Bearer Authorization header for HTTP-like transports and
                # only set `token` for stdio-style transports.
                if server_config.get("transport") in ["streamable_http", "http", "websocket"]:
                    headers = server_config.get("headers") or {}
                    # Do not overwrite an existing Authorization header
                    if "Authorization" not in headers and "authorization" not in headers:
                        headers["Authorization"] = f"Bearer {token}"
                    server_config["headers"] = headers
                else:
                    server_config["token"] = token
                
            server_configs[server_name] = server_config
            
        return server_configs

    async def get_or_create_client(self) -> Optional[object]:
        """
        Get or create a MultiServerMCPClient with proper lifecycle management.
        
        Returns:
            MultiServerMCPClient: The client instance or None if creation fails
        """
        async with self._get_client_lock():
            if self._client is not None:
                return self._client
                
            if not HAS_MCP_ADAPTERS:
                logger.error("langchain-mcp-adapters not installed")
                return None
                
            if not self.mcp_configs:
                logger.error("No MCP server configurations found")
                return None
                
            try:
                # Convert configs to langchain format
                server_configs = self.convert_configs_to_langchain_format()
                # Create a redacted copy for safe logging (hide tokens/Authorization)
                redacted_configs = {}
                for name, cfg in server_configs.items():
                    rcfg = {}
                    for k, v in cfg.items():
                        if k == "headers" and isinstance(v, dict):
                            new_headers = {}
                            for hk, hv in v.items():
                                if hk.lower() == "authorization" or "token" in hk.lower():
                                    new_headers[hk] = "<REDACTED>"
                                else:
                                    new_headers[hk] = hv
                            rcfg["headers"] = new_headers
                        elif k == "token":
                            rcfg["token"] = "<REDACTED>"
                        else:
                            rcfg[k] = v
                    redacted_configs[name] = rcfg

                logger.info(f"Creating MCP client for {len(server_configs)} server(s)")
                logger.debug(f"MCP server_configs (redacted): {redacted_configs}")
                
                # Initialize the MultiServerMCPClient
                self._client = MultiServerMCPClient(server_configs)
                
                return self._client
                
            except Exception as e:
                logger.error(f"Error creating MCP client: {e}")
                return None

    async def close_client(self):
        """
        Properly close the MCP client and clean up resources.
        """
        async with self._get_client_lock():
            if self._client is not None:
                try:
                    # Since MultiServerMCPClient doesn't support context manager
                    # or explicit close methods in langchain-mcp-adapters 0.1.0,
                    # we just clear the reference and let garbage collection handle it
                    logger.debug("Releasing MCP client reference")
                except Exception as e:
                    logger.error(f"Error during MCP client cleanup: {e}")
                finally:
                    # Always clear the reference
                    self._client = None

    async def get_all_tools(self) -> List:
        """
        Get all available tools from MCP servers.
        
        Returns:
            List: All available MCP tools
        """
        client = await self.get_or_create_client()
        if not client:
            return []
            
        try:
            # Get tools from all servers
            all_tools = await client.get_tools()
            
            if all_tools:
                logger.info(f"Loaded {len(all_tools)} total tools from MCP servers")
                return all_tools
            else:
                logger.warning("No tools available from MCP servers")
                return []
                
        except Exception as e:
            logger.error(f"Error getting MCP tools: {e}")
            return [] 
