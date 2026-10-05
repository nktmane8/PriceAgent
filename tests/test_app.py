import base64
import hashlib
import re
import secrets
import time
from urllib.parse import parse_qs, urlsplit

import config
import db
import main

BODY = {"product": "Phone X 128GB", "country": "India", "city": "Pune"}
CB = "https://claude.ai/api/mcp/auth_callback"


def poll(client, jid, path="/api/jobs/"):
    for _ in range(50):
        j = client.get(path + jid).json()
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_validation(client):
    assert client.post("/api/jobs", json={**BODY, "product": "x"}).status_code == 422
    assert client.post("/api/jobs", json={**BODY, "country": "<script>"}).status_code == 422
    assert client.post("/api/jobs", json={**BODY, "sites": ["not a domain"]}).status_code == 422


def test_product_identity_normalizes_wording_and_preserves_variant(client):
    a = client.get("/api/product/resolve", params={"product": "Apple iPhone 16 128 GB Black"}).json()
    b = client.get("/api/product/resolve", params={"product": "apple iPhone 16 (128GB) - Black"}).json()
    c = client.get("/api/product/resolve", params={"product": "Apple iPhone 16 256GB Black"}).json()
    assert a["canonical_key"] == b["canonical_key"]
    assert a["storage"] == "128gb"
    assert c["canonical_key"] != a["canonical_key"]


def test_job_lifecycle_cache_and_cleaning(client, calls):
    r = client.post("/api/jobs", json=BODY)
    assert r.status_code in (200, 202)
    j = poll(client, r.json()["job_id"])
    assert j["status"] == "done" and j["cached"] is False
    assert j["result"]["results"][1]["url"] == ""            # non-http URL stripped
    again = client.post("/api/jobs", json=BODY).json()       # served from the SQLite cache
    assert again["status"] == "done" and again["cached"] is True
    assert len(calls) == 1                                    # agent ran once
    assert client.get("/api/admin/stats", headers={"X-Admin-Key": "adm"}).json()["web_searches"] == 2


def test_rate_limit_is_persisted(client, monkeypatch):
    monkeypatch.setattr(config, "USER_RATE_LIMIT", 1)
    assert client.post("/api/jobs", json=BODY).status_code in (200, 202)
    r = client.post("/api/jobs", json={**BODY, "product": "Other Phone 5"})
    assert r.status_code == 429


def test_web_price_comparison_requires_oauth(client):
    override = main.api.dependency_overrides.pop(main.web_user)
    try:
        assert client.post("/api/jobs", json=BODY).status_code == 401
        assert client.get("/api/jobs/not-owned").status_code == 401
    finally:
        main.api.dependency_overrides[main.web_user] = override


def test_jwt_auth_required(client):
    assert client.post("/api/v1/compare", json=BODY).status_code == 401
    assert client.post("/api/v1/compare", json=BODY, headers={"X-API-Key": "testkey"}).status_code == 401
    assert "resource_metadata" in client.post("/api/v1/compare", json=BODY).headers["www-authenticate"]


def pkce():
    v = secrets.token_urlsafe(48)
    return v, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


def jwt_token(email="a@example.com", resource=None):
    with db.tx() as c:
        row = c.execute("INSERT INTO users(email,pw_hash,google_sub,auth_provider,created_at) VALUES(?,?,?,?,?) RETURNING id",
                        (email, None, "google-" + email, "google", time.time())).fetchone()
    return oauth.issue("test-client", row["id"], config.SCOPE, resource or config.PUBLIC_URL, secrets.token_hex(8)).body


def test_google_only_authorization_page(client):
    reg = client.post("/oauth/register", json={"redirect_uris": [CB], "client_name": "Test App"}).json()
    ver, ch = pkce()
    q = {"response_type": "code", "client_id": reg["client_id"], "redirect_uri": CB,
         "code_challenge": ch, "code_challenge_method": "S256", "state": "xyz", "resource": config.PUBLIC_URL}
    page = client.get("/oauth/authorize", params=q)
    assert page.status_code == 200
    assert "Continue with Google" in page.text
    assert "password" not in page.text.lower()


def test_oauth_flow_refresh_rotation_and_reuse_detection(client):
    token = jwt_token("refresh@example.com")
    # issue() returns a JSONResponse; decode its body for the test.
    tok = json.loads(token.body)
    ok = client.post("/api/v1/compare", json=BODY, headers={"Authorization": "Bearer " + tok["access_token"]})
    assert ok.status_code == 200
    new = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": "test-client"})
    assert new.status_code == 200
    replay = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": "test-client"})
    assert replay.status_code == 400
    after = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": new.json()["refresh_token"], "client_id": "test-client"})
    assert after.status_code == 400
    client.post("/oauth/revoke", data={"token": tok["access_token"]})
    assert client.post("/api/v1/compare", json=BODY, headers={"Authorization": "Bearer " + tok["access_token"]}).status_code == 401


def test_mcp_requires_oauth_and_lists_tools(client):
    H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    r = client.post("/mcp", json=init, headers=H)
    assert r.status_code == 401 and "resource_metadata" in r.headers["www-authenticate"]
    assert client.get("/.well-known/oauth-protected-resource/mcp").json()["authorization_servers"]
    tok = json.loads(jwt_token("mcp@example.com", config.PUBLIC_URL + "/mcp").body)["access_token"]
    H["Authorization"] = "Bearer " + tok
    assert client.post("/mcp", json=init, headers=H).status_code == 200
    tools = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=H).json()
    assert {t["name"] for t in tools["result"]["tools"]} == {"compare_prices", "get_reviews_and_alternatives", "get_comparison_result"}
    call = client.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "compare_prices", "arguments": {"product": "Phone X 128GB", "country": "India"}}}, headers=H).json()
    assert '"status": "done"' in call["result"]["content"][0]["text"]
    # tokens bound to the MCP resource must not work on the REST API
    assert client.post("/api/v1/compare", json=BODY, headers={"Authorization": "Bearer " + tok}).status_code == 401


def test_purge_and_restart_recovery(client):
    jid = db.job_create("k", {"product": "p", "country": "c", "city": "", "sites": []}, "ip:1")
    db.init()                                   # simulates a restart
    assert db.job_get(jid)["status"] == "error"
    db.cache_set("old", {"a": 1})
    with db.conn() as c:
        c.execute("UPDATE cache SET expires_at=1")
    db.purge()
    assert db.cache_get("old") is None


def test_insights_job_drops_unsourced_reviews_and_has_own_cache(client, calls):
    assert client.post("/api/jobs", json={**BODY, "kind": "bogus"}).status_code == 422
    r = client.post("/api/jobs", json={**BODY, "kind": "insights"}).json()
    j = poll(client, r["job_id"])
    res = j["result"]
    assert [x["source"] for x in res["reviews"]] == ["Example Paper"]          # review without a URL removed
    assert res["alternatives"][0]["url"] == "" and res["alternatives"][0]["name"] == "Phone Y"
    assert calls == []                                                          # price agent not used
    assert client.post("/api/jobs", json={**BODY, "kind": "insights"}).json()["cached"] is True
    prices = poll(client, client.post("/api/jobs", json=BODY).json()["job_id"])  # separate cache key
    assert "verdict" not in prices["result"] and len(calls) == 1


def test_price_history_is_recorded_once_per_fresh_run(client):
    poll(client, client.post("/api/jobs", json=BODY).json()["job_id"])
    q = {"product": BODY["product"], "country": BODY["country"], "city": BODY["city"]}
    h = client.get("/api/history", params=q).json()
    assert h["lowest"]["store"] == "a.in" and h["lowest"]["price"] == 90 and len(h["days"]) == 1
    client.post("/api/jobs", json=BODY)                                  # cache hit: no new data point
    with db.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM price_history").fetchone()[0] == 2
    assert client.get("/api/history", params={**q, "product": "x"}).status_code == 422


def test_admin_metrics_fields(client):
    poll(client, client.post("/api/jobs", json=BODY).json()["job_id"])
    client.post("/api/jobs", json=BODY)
    s = client.get("/api/admin/stats", headers={"X-Admin-Key": "adm"}).json()
    assert s["cache_hit_rate"] == 0.5 and s["by_principal_type"]["user"]["jobs"] == 2
    assert "avg_agent_seconds" in s and "top_errors" in s and s["price_history_rows"] == 2


def test_account_deletion_removes_everything(client):
    token = json.loads(jwt_token("del@example.com").body)["access_token"]
    H = {"Authorization": "Bearer " + token}
    client.post("/api/v1/compare", json=BODY, headers=H)
    assert client.post("/api/v1/account/delete", json={"password": "wrong password 12"}, headers=H).status_code == 200
    assert client.post("/api/v1/compare", json=BODY, headers=H).status_code == 401
    with db.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM jobs WHERE principal LIKE 'user:%'").fetchone()[0] == 0


def test_env_loader_precedence_and_production_checks(tmp_path, monkeypatch):
    f = tmp_path / ".env.x"
    f.write_text("# comment\nA_VAR=from_file\nB_VAR='quoted value'\nEXISTING=from_file\n")
    monkeypatch.setenv("EXISTING", "from_shell")
    monkeypatch.delenv("A_VAR", raising=False)
    monkeypatch.delenv("B_VAR", raising=False)
    config._load_file(f)
    import os
    assert os.environ["A_VAR"] == "from_file" and os.environ["B_VAR"] == "quoted value"
    assert os.environ["EXISTING"] == "from_shell"                      # real env vars always win
    monkeypatch.setattr(config, "PRODUCTION_LIKE", True)
    monkeypatch.setattr(config, "PUBLIC_URL", "http://x")
    monkeypatch.setattr(config, "AI_PROVIDER", "openai")
    monkeypatch.setattr(config, "DB_PATH", "data/x.db")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(config, "GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(config, "JWT_SECRET", "short")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    found = " | ".join(config.problems())
    for word in ("OPENAI_API_KEY", "https", "absolute path", "NOMINATIM_CONTACT", "32"):
        assert word in found
    import pytest
    with pytest.raises(RuntimeError):
        config.assert_ready()


def test_rest_job_is_owned_by_creator(client):
    tok1 = json.loads(jwt_token("owner-one@example.com").body)["access_token"]
    tok2 = json.loads(jwt_token("owner-two@example.com").body)["access_token"]
    first = client.post("/api/v1/compare", json=BODY, headers={"Authorization": "Bearer " + tok1})
    assert first.status_code == 200
    jid = first.json()["job_id"]
    assert client.get("/api/v1/jobs/" + jid, headers={"Authorization": "Bearer " + tok1}).status_code == 200
    assert client.get("/api/v1/jobs/" + jid, headers={"Authorization": "Bearer " + tok2}).status_code == 403


def test_oauth_requires_explicit_resource(client):
    reg = client.post("/oauth/register", json={"redirect_uris": [CB]}).json()
    ver, ch = pkce()
    r = client.get("/oauth/authorize", params={
        "response_type": "code", "client_id": reg["client_id"], "redirect_uri": CB,
        "code_challenge": ch, "code_challenge_method": "S256"
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "invalid_target" in r.headers["location"]


def test_mcp_token_cannot_be_used_for_rest(client):
    tok = json.loads(jwt_token("mcp-resource@example.com", config.PUBLIC_URL + "/mcp").body)["access_token"]
    assert client.post("/api/v1/compare", json=BODY, headers={"Authorization": "Bearer " + tok}).status_code == 401


def test_loopback_redirect_rules_reject_public_http(client):
    assert client.post("/oauth/register", json={"redirect_uris": ["http://priceagent.onrender.com/callback"]}).status_code == 400


def test_all_business_api_routes_require_priceagent_jwt(client):
    checks = [
        ("post", "/api/jobs", {"json": BODY}),
        ("get", "/api/jobs/not-found", {}),
        ("post", "/api/v1/compare", {"json": BODY}),
        ("get", "/api/v1/jobs/not-found", {}),
        ("post", "/api/v1/account/delete", {"json": {}}),
        ("get", "/api/locate?lat=18.62&lon=73.73", {}),
        ("get", "/api/product/resolve?product=Phone%20X%20128GB", {}),
        ("get", "/api/history?product=Phone%20X%20128GB&country=India&city=Pune", {}),
    ]
    for method, path, kwargs in checks:
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 401, (method, path, response.status_code)
