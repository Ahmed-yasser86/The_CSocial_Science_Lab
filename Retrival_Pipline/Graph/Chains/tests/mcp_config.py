import os

from dotenv import load_dotenv

# Load environment variables from .env if available.
load_dotenv()

SOCIALCRAWL_MCP_URL = os.environ.get(
    "SOCIALCRAWL_MCP_URL",
    "https://mcp.socialcrawl.dev/mcp",
)
GDELT_MCP_URL = os.environ.get(
    "GDELT_MCP_URL",
    "https://gdelt-cloud-mcp.fastmcp.app/mcp",
)


def load_environment() -> None:
    """Load environment variables from .env for MCP configuration."""
    load_dotenv()


def build_audience_mcp_configs() -> list[dict[str, object]]:
    """Build MCP server config list for Audience Intelligence runs."""
    load_environment()
    socialcrawl_key = os.environ.get("SOCIALCRAWL_MCP_API_KEY") or os.environ.get("MCP_API_KEY")
    gdelt_key = os.environ.get("GDELT_API_KEY") or os.environ.get("GDELT_MCP_API_KEY")

    if socialcrawl_key:
        print("[OK] Injected SocialCrawl MCP key from environment.")
    else:
        print("[WARN] No SocialCrawl MCP key found. Set SOCIALCRAWL_MCP_API_KEY or MCP_API_KEY.")

    if gdelt_key:
        print("[OK] Injected GDELT MCP key from environment.")
    else:
        print("[WARN] No GDELT MCP key found. Set GDELT_MCP_API_KEY or GDELT_API_KEY.")

    configs: list[dict[str, object]] = []

    if socialcrawl_key:
        configs.append({
            "name": "socialcrawl",
            "connection_url": SOCIALCRAWL_MCP_URL,
            "connection_type": "streamable_http",
            "connection_headers": {"x-api-key": socialcrawl_key},
            "headers": {"x-api-key": socialcrawl_key},
            "connection_token": socialcrawl_key,
        })

    if gdelt_key:
        configs.append({
            "name": "gdelt-cloud",
            "connection_url": GDELT_MCP_URL,
            "connection_type": "streamable_http",
            "connection_headers": {"Authorization": f"Bearer {gdelt_key}"},
            "headers": {"Authorization": f"Bearer {gdelt_key}"},
            "connection_token": gdelt_key,
        })

    return configs
