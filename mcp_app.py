"""Remote MCP server (streamable HTTP) protected by our OAuth tokens.
Tools: compare_prices (waits up to JOB_WAIT s, else returns a job id) and get_comparison_result."""
import json
from urllib.parse import urlsplit

import anyio
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl

import config
import db
import jobs
import oauth
from util import validate


class DbTokenVerifier:
    async def verify_token(self, token: str):
        row = await anyio.to_thread.run_sync(oauth.verify_access_token, token)
        if not row or row["resource"] not in (None, "", config.PUBLIC_URL + "/mcp"):  # audience check
            return None
        return AccessToken(token=token, client_id=row["client_id"], scopes=row["scope"].split(),
                           expires_at=int(row["expires_at"]), resource=row["resource"], subject=str(row["user_id"]))


_u = urlsplit(config.PUBLIC_URL)
mcp = FastMCP(
    "price-agent", token_verifier=DbTokenVerifier(), stateless_http=True, json_response=True,
    auth=AuthSettings(issuer_url=AnyHttpUrl(config.PUBLIC_URL), resource_server_url=AnyHttpUrl(config.PUBLIC_URL + "/mcp"),
                      required_scopes=[config.SCOPE], validate_token_resource=False),  # DbTokenVerifier checks audience
    # Host + Origin validation (blocks DNS-rebinding; directories require Origin checks).
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=[_u.netloc],
        allowed_origins=[f"{_u.scheme}://{_u.netloc}", "https://claude.ai", "https://chatgpt.com", *config.EXTRA_ORIGINS]))


def _principal():
    t = get_access_token()  # set by the SDK's auth middleware
    return "user:" + (t.subject if t and t.subject else "unknown")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def compare_prices(product: str, country: str, city: str = "") -> str:
    """Compare live prices for an EXACT product variant across online and local stores in a region.
    Returns JSON with per-store price, effective price, offers, stock and URL plus a best deal.
    If it is still running after ~50 s it returns a job_id; call get_comparison_result with it.
    Prices change quickly; verify on the store before buying."""
    params = {"product": product.strip(), "country": country.strip(), "city": city.strip(), "sites": []}
    err = validate(params)
    if err:
        return json.dumps({"error": err})
    me = _principal()

    def run():
        try:
            jid = jobs.submit(params, me, config.USER_RATE_LIMIT)
        except jobs.RateLimited as e:
            return {"error": f"Hourly limit reached. Try again in about {e.minutes} minutes."}
        return jobs.view(jobs.wait(jid, config.JOB_WAIT))
    return json.dumps(await anyio.to_thread.run_sync(run))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def get_comparison_result(job_id: str) -> str:
    """Fetch the result of a comparison started by compare_prices (status: queued, running, done, error)."""
    job = await anyio.to_thread.run_sync(db.job_get, job_id)
    return json.dumps(jobs.view(job) if job else {"error": "Unknown job_id."})
