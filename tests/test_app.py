import base64
import hashlib
import re
import secrets
import time
from urllib.parse import parse_qs, urlsplit

import config
import db

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
    monkeypatch.setattr(config, "RATE_LIMIT", 1)
    assert client.post("/api/jobs", json=BODY).status_code in (200, 202)
    r = client.post("/api/jobs", json={**BODY, "product": "Other Phone 5"})
    assert r.status_code == 429


def test_api_key_and_auth_required(client):
    assert client.post("/api/v1/compare", json=BODY).status_code == 401
    r = client.post("/api/v1/compare", json=BODY, headers={"X-API-Key": "testkey"})
    assert r.status_code == 200 and r.json()["status"] == "done"
    assert "resource_metadata" in client.post("/api/v1/compare", json=BODY).headers["www-authenticate"]


def pkce():
    v = secrets.token_urlsafe(48)
    return v, base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()


def sign_in(client, email="a@example.com", action="signup", resource=None, cb=CB):
    reg = client.post("/oauth/register", json={"redirect_uris": [cb], "client_name": "Test <b>App</b>"}).json()
    ver, ch = pkce()
    q = {"response_type": "code", "client_id": reg["client_id"], "redirect_uri": cb, "code_challenge": ch,
         "code_challenge_method": "S256", "state": "xyz"}
    if resource:
        q["resource"] = resource
    page = client.get("/oauth/authorize", params=q)
    assert page.status_code == 200 and "<b>App</b>" not in page.text      # client name is HTML-escaped
    rid = re.search(r"name=request_id value='([^']+)'", page.text).group(1)
    r = client.post("/oauth/authorize", data={"request_id": rid, "email": email, "password": "correct horse 1",
                                              "action": action}, follow_redirects=False)
    return reg["client_id"], ver, r


def exchange(client, cid, ver, r, cb=CB):
    qs = parse_qs(urlsplit(r.headers["location"]).query)
    assert qs["state"] == ["xyz"] and qs["iss"] == [config.PUBLIC_URL]
    return client.post("/oauth/token", data={"grant_type": "authorization_code", "code": qs["code"][0],
                                             "client_id": cid, "redirect_uri": cb, "code_verifier": ver})


def test_oauth_flow_refresh_rotation_and_reuse_detection(client):
    meta = client.get("/.well-known/oauth-authorization-server").json()
    assert meta["code_challenge_methods_supported"] == ["S256"]
    cid, ver, r = sign_in(client)
    assert r.status_code == 303
    t = exchange(client, cid, ver, r)
    assert t.status_code == 200
    tok = t.json()
    ok = client.post("/api/v1/compare", json=BODY, headers={"Authorization": "Bearer " + tok["access_token"]})
    assert ok.status_code == 200
    # refresh rotates; replaying the old refresh token revokes the whole family
    new = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": cid})
    assert new.status_code == 200
    replay = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": cid})
    assert replay.status_code == 400
    after = client.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": new.json()["refresh_token"], "client_id": cid})
    assert after.status_code == 400
    # revoke makes the access token useless
    client.post("/oauth/revoke", data={"token": tok["access_token"]})
    assert client.post("/api/v1/compare", json=BODY, headers={"Authorization": "Bearer " + tok["access_token"]}).status_code == 401


def test_oauth_rejects_bad_pkce_code_reuse_and_bad_redirect(client):
    cid, ver, r = sign_in(client)
    qs = parse_qs(urlsplit(r.headers["location"]).query)
    base = {"grant_type": "authorization_code", "code": qs["code"][0], "client_id": cid, "redirect_uri": CB}
    assert client.post("/oauth/token", data={**base, "code_verifier": secrets.token_urlsafe(48)}).status_code == 400
    assert client.post("/oauth/token", data={**base, "code_verifier": ver}).status_code == 400   # code already burned
    reg = client.post("/oauth/register", json={"redirect_uris": [CB]}).json()
    bad = client.get("/oauth/authorize", params={"response_type": "code", "client_id": reg["client_id"],
                     "redirect_uri": "https://evil.example/cb", "code_challenge": "a" * 43, "code_challenge_method": "S256"})
    assert bad.status_code == 400                                                                 # never redirects to unregistered URI
    assert client.post("/oauth/register", json={"redirect_uris": ["http://evil.example/cb"]}).status_code == 400
    no_pkce = client.get("/oauth/authorize", params={"response_type": "code", "client_id": reg["client_id"], "redirect_uri": CB},
                         follow_redirects=False)
    assert "invalid_request" in no_pkce.headers["location"]


def test_login_wrong_password_and_duplicate_signup(client):
    sign_in(client, email="dup@example.com")
    cid, ver, r = sign_in(client, email="dup@example.com", action="signup")
    assert r.status_code == 400
    cid, ver, r = sign_in(client, email="dup@example.com", action="login")
    assert r.status_code == 303                                                                   # same password -> ok


def test_mcp_requires_oauth_and_lists_tools(client):
    H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    r = client.post("/mcp", json=init, headers=H)
    assert r.status_code == 401 and "resource_metadata" in r.headers["www-authenticate"]
    assert client.get("/.well-known/oauth-protected-resource/mcp").json()["authorization_servers"]
    cid, ver, r = sign_in(client, resource=config.PUBLIC_URL + "/mcp")
    tok = exchange(client, cid, ver, r).json()["access_token"]
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
    assert s["cache_hit_rate"] == 0.5 and s["by_principal_type"]["ip"]["jobs"] == 2
    assert "avg_agent_seconds" in s and "top_errors" in s and s["price_history_rows"] == 2


def test_account_deletion_removes_everything(client):
    cid, ver, r = sign_in(client, email="del@example.com")
    H = {"Authorization": "Bearer " + exchange(client, cid, ver, r).json()["access_token"]}
    client.post("/api/v1/compare", json=BODY, headers=H)
    assert client.post("/api/v1/account/delete", json={"password": "wrong password 12"}, headers=H).status_code == 403
    assert client.post("/api/v1/account/delete", json={"password": "correct horse 1"}, headers=H).status_code == 200
    assert client.post("/api/v1/compare", json=BODY, headers=H).status_code == 401      # token gone
    with db.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM jobs WHERE principal LIKE 'user:%'").fetchone()[0] == 0
    assert sign_in(client, email="del@example.com", action="login")[2].status_code == 401
