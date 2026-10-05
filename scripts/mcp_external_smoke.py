"""Black-box MCP OAuth smoke test against a running PriceAgent deployment.

Required environment:
  PRICEAGENT_BASE_URL=https://priceagent.onrender.com
  PRICEAGENT_TEST_EMAIL=...
  PRICEAGENT_TEST_PASSWORD=...

This uses only HTTP APIs, so it exercises the same discovery/OAuth/MCP path an
external client uses. It does not import application modules.
"""
import base64
import hashlib
import os
import re
import secrets
import sys
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx


def pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def main():
    base = os.environ["PRICEAGENT_BASE_URL"].rstrip("/") + "/"
    email = os.environ["PRICEAGENT_TEST_EMAIL"]
    password = os.environ["PRICEAGENT_TEST_PASSWORD"]
    cb = "http://127.0.0.1:8765/callback"
    resource = urljoin(base, "mcp").rstrip("/")

    with httpx.Client(base_url=base, follow_redirects=False, timeout=20) as client:
        pr = client.get("/mcp", headers={"Accept": "application/json, text/event-stream"})
        assert pr.status_code == 401, pr.text
        assert "resource_metadata" in pr.headers.get("www-authenticate", "")

        meta = client.get("/.well-known/oauth-protected-resource/mcp").json()
        assert meta["resource"] == resource
        assert meta["authorization_servers"]

        as_meta = client.get("/.well-known/oauth-authorization-server").json()
        assert as_meta["code_challenge_methods_supported"] == ["S256"]

        reg = client.post("/oauth/register", json={"client_name": "PriceAgent external smoke", "redirect_uris": [cb]})
        assert reg.status_code == 201, reg.text
        client_id = reg.json()["client_id"]

        verifier, challenge = pkce()
        state = secrets.token_urlsafe(18)
        auth = client.get("/oauth/authorize", params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": cb,
            "scope": "prices:read",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": resource,
        })
        assert auth.status_code == 200, auth.text
        match = re.search(r"name=request_id value='([^']+)'", auth.text)
        assert match, "authorization page did not contain request_id"

        decision = client.post("/oauth/authorize", data={
            "request_id": match.group(1),
            "email": email,
            "password": password,
            "action": "login",
        })
        assert decision.status_code == 303, decision.text
        location = decision.headers["location"]
        qs = parse_qs(urlsplit(location).query)
        assert qs["state"] == [state]
        assert qs["iss"] == [base.rstrip("/")]
        code = qs["code"][0]

        token = client.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": cb,
            "code_verifier": verifier,
        })
        assert token.status_code == 200, token.text
        access = token.json()["access_token"]

        headers = {
            "Authorization": "Bearer " + access,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "priceagent-external-smoke", "version": "1"},
            },
        }
        mcp = client.post("/mcp", json=init, headers=headers)
        assert mcp.status_code == 200, mcp.text

        tools = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
        assert tools.status_code == 200, tools.text
        names = {tool["name"] for tool in tools.json()["result"]["tools"]}
        expected = {"compare_prices", "get_reviews_and_alternatives", "get_comparison_result"}
        assert expected <= names, names

        print("PASS: protected-resource discovery -> OAuth PKCE -> MCP initialize -> tools/list")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FAIL:", exc)
        sys.exit(1)
