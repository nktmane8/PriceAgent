"""MCP wrapper: exposes the price agent as a tool to Claude Desktop, Cursor, etc.

It calls your deployed API (/api/v1/compare) with an API key, so auth and rate
limits stay in one place.   Install: pip install -r requirements.txt
  Local (stdio):   PRICE_AGENT_URL=https://your-app.onrender.com PRICE_AGENT_API_KEY=... python mcp_server.py
  For remote clients use the OAuth-protected /mcp endpoint of the deployed app instead (no script needed).
"""
import json
import os
import sys
import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

BASE = os.environ.get("PRICE_AGENT_URL", "http://127.0.0.1:8000").rstrip("/")
KEY = os.environ.get("PRICE_AGENT_API_KEY", "")  # never hardcode

mcp = FastMCP("price-agent", host="0.0.0.0", port=int(os.environ.get("PORT", "8001")))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
def compare_prices(product: str, country: str, city: str = "") -> str:
    """Compare live prices for an exact product variant across online and local stores
    in a region. Returns JSON with per-store price, effective price, offers, stock and
    URL, plus a best deal. Takes 30-60 seconds; may return a job_id if still running. Verify prices on the store before buying."""
    body = json.dumps({"product": product, "country": country, "city": city or None}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/v1/compare", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-API-Key": KEY})
    try:
        with urllib.request.urlopen(req, timeout=170) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return f"Error {e.code}: {e.read().decode()[:300]}"
    except Exception as e:
        return f"Error: could not reach the price agent ({e})"


if __name__ == "__main__":
    mcp.run(transport="streamable-http" if "--http" in sys.argv else "stdio")
