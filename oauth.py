"""Minimal OAuth 2.1 authorization server for AI clients.
Authorization code + PKCE (S256 only), public clients, dynamic client registration,
refresh-token rotation with reuse detection. Accounts: email + scrypt-hashed password."""
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sqlite3
import time
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import config
import db
from constants import (LOGIN_ACCOUNT_LIMIT, LOGIN_IP_LIMIT, LOGIN_WINDOW, PASSWORD_MIN, REGISTER_IP_LIMIT,
                       TOKEN_IP_LIMIT)
from util import client_ip

router = APIRouter()
LOOPBACK = {"127.0.0.1", "localhost", "[::1]"}
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def sha(s):
    """SHA-256 hex digest (tokens and codes are stored hashed)."""
    return hashlib.sha256(s.encode()).hexdigest()


def b64url(b):
    """URL-safe base64 without padding (PKCE)."""
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def hash_pw(pw):
    """Salted scrypt hash of a password."""
    salt = os.urandom(16)
    return salt.hex() + ":" + hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1).hex()


def check_pw(pw, stored):
    """Constant-time password check."""
    salt, h = stored.split(":")
    return hmac.compare_digest(hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex(), h)


DUMMY_HASH = hash_pw("not-a-real-password")  # used so unknown emails take the same time as wrong passwords


def valid_redirect(uri):
    """Is this redirect URI allowed at registration (https or loopback http)?"""
    u = urlsplit(uri)
    if u.fragment or not u.netloc:
        return False
    return u.scheme == "https" or (u.scheme == "http" and u.hostname in {"127.0.0.1", "localhost", "::1", "priceagent.onrender.com"})


def redirect_ok(registered, given):
    """Exact match; loopback http URIs may differ only by port (native/CLI clients)."""
    if given in registered:
        return True
    g = urlsplit(given)
    if g.scheme == "http" and g.hostname in {"127.0.0.1", "localhost", "::1"}:
        return any((r := urlsplit(x)).scheme == "http" and r.hostname == g.hostname and r.path == g.path
                   for x in registered)
    return False


def resources():
    """Allowed token audiences (REST root and /mcp)."""
    return {config.PUBLIC_URL, config.PUBLIC_URL + "/mcp"}


def oerr(code, desc, status=400):
    """OAuth error JSON response (no-store)."""
    return JSONResponse({"error": code, "error_description": desc}, status, headers=NO_STORE)


async def form(request):
    """Parse an x-www-form-urlencoded body."""
    return {k: v[0] for k, v in parse_qs((await request.body()).decode(), keep_blank_values=True).items()}


# ---- discovery ------------------------------------------------------------
@router.get("/.well-known/oauth-authorization-server")
def as_metadata():
    """Authorization-server metadata (RFC 8414)."""
    u = config.PUBLIC_URL
    return {"issuer": u, "authorization_endpoint": u + "/oauth/authorize", "token_endpoint": u + "/oauth/token",
            "registration_endpoint": u + "/oauth/register", "revocation_endpoint": u + "/oauth/revoke",
            "response_types_supported": ["code"], "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"], "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": [config.SCOPE], "authorization_response_iss_parameter_supported": True, "client_id_metadata_document_supported": False}


@router.get("/.well-known/oauth-protected-resource")
def resource_metadata():
    """Protected-resource metadata for the REST API (RFC 9728)."""
    return {"resource": config.PUBLIC_URL, "authorization_servers": [config.PUBLIC_URL],
            "scopes_supported": [config.SCOPE], "bearer_methods_supported": ["header"]}

@router.get("/mcp/.well-known/oauth-protected-resource")
def mcp_resource_metadata():
    """Protected-resource metadata for MCP clients discovering metadata under /mcp."""
    return {"resource": config.PUBLIC_URL + "/mcp", "authorization_servers": [config.PUBLIC_URL],
            "scopes_supported": [config.SCOPE], "bearer_methods_supported": ["header"]}


# ---- dynamic client registration (RFC 7591) ---------------------------------
@router.post("/oauth/register")
async def register(request: Request):
    """Dynamic client registration (RFC 7591)."""
    if db.rate_check("reg:" + client_ip(request), REGISTER_IP_LIMIT):
        return oerr("temporarily_unavailable", "Too many registrations.", 429)
    try:
        body = await request.json()
        uris = body.get("redirect_uris")
        assert isinstance(uris, list) and 1 <= len(uris) <= 5 and all(isinstance(x, str) and valid_redirect(x) for x in uris)
    except Exception:
        return oerr("invalid_redirect_uri", "Provide 1-5 https (or loopback http) redirect_uris.")
    name = str(body.get("client_name") or "Unnamed app")[:80]
    cid = secrets.token_urlsafe(16)
    with db.conn() as c:
        c.execute("INSERT INTO oauth_clients VALUES(?,?,?,?)", (cid, name, json.dumps(uris), time.time()))
    return JSONResponse({"client_id": cid, "client_name": name, "redirect_uris": uris,
                         "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
                         "response_types": ["code"], "client_id_issued_at": int(time.time())}, 201, headers=NO_STORE)


# ---- authorization page --------------------------------------------------------
SEC_HEADERS = {"X-Frame-Options": "DENY", "Cache-Control": "no-store",
               "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"}
CSS = ("body{font:16px system-ui;max-width:420px;margin:8vh auto;padding:0 16px;background:#f6f7f4;color:#1c2321}"
       "input{width:100%;padding:10px;margin:6px 0;font-size:1rem;box-sizing:border-box}"
       "button{padding:10px 14px;margin:6px 6px 0 0;font-size:1rem;cursor:pointer}.e{color:#b00020}")


def page(body, status=200):
    """Render an HTML page with security headers."""
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                        f"<title>Price Comparison Agent</title><style>{CSS}</style>{body}", status, headers=SEC_HEADERS)


def login_page(rid, client_name, msg="", status=200):
    """Sign-in / create-account / deny page (all values HTML-escaped)."""
    e = html.escape  # escape everything that came from outside
    return page(f"<h1>Price Comparison Agent</h1><p><b>{e(client_name)}</b> wants to compare prices on your behalf "
                f"(permission: <code>{e(config.SCOPE)}</code>).</p><p class=e>{e(msg)}</p>"
                f"<form method=post action='/oauth/authorize'><input type=hidden name=request_id value='{e(rid)}'>"
                "<input name=email type=email placeholder=Email autocomplete=username required>"
                "<input name=password type=password placeholder='Password (10+ characters)' autocomplete=current-password required>"
                "<button name=action value=login>Sign in and allow</button>"
                "<button name=action value=signup>Create account and allow</button>"
                "<button name=action value=deny formnovalidate>Deny</button></form>", status)


def back(uri, **params):
    """Redirect to the client's redirect URI with extra query parameters."""
    u = urlsplit(uri)
    q = parse_qsl(u.query) + [(k, v) for k, v in params.items() if v]
    return RedirectResponse(urlunsplit(u._replace(query=urlencode(q))), 303)


@router.get("/oauth/authorize")
def authorize(request: Request):
    """Start authorization: validate client, redirect URI and PKCE, then show the sign-in page."""
    q = dict(request.query_params)
    with db.conn() as c:
        cl = c.execute("SELECT * FROM oauth_clients WHERE client_id=?", (q.get("client_id", ""),)).fetchone()
    # Bad client or redirect URI: never redirect, show an error instead.
    if not cl or not redirect_ok(json.loads(cl["redirect_uris"]), q.get("redirect_uri", "")):
        return page("<p class=e>Unknown app or invalid redirect address.</p>", 400)
    ru, state, iss = q["redirect_uri"], q.get("state"), config.PUBLIC_URL
    if q.get("response_type") != "code":
        return back(ru, error="unsupported_response_type", state=state, iss=iss)
    if q.get("code_challenge_method") != "S256" or not re.fullmatch(r"[A-Za-z0-9_-]{43,128}", q.get("code_challenge", "")):
        return back(ru, error="invalid_request", error_description="PKCE S256 required", state=state, iss=iss)
    res = q.get("resource")
    if res not in resources():
        return back(ru, error="invalid_target", error_description="resource is required and must identify the target API.", state=state, iss=iss)
    rid = secrets.token_urlsafe(24)
    with db.conn() as c:
        c.execute("INSERT INTO oauth_requests VALUES(?,?,?,?,?,?,?,?)",
                  (rid, cl["client_id"], ru, (state or "")[:500], q["code_challenge"], config.SCOPE, res,
                   time.time() + config.AUTHREQ_TTL))
    return login_page(rid, cl["name"])


@router.post("/oauth/authorize")
async def authorize_post(request: Request):
    """Handle sign-in or sign-up, then redirect back with a one-time code."""
    f = await form(request)
    with db.conn() as c:
        rq = c.execute("SELECT r.*, c.name FROM oauth_requests r JOIN oauth_clients c USING(client_id) "
                       "WHERE r.id=? AND r.expires_at>?", (f.get("request_id", ""), time.time())).fetchone()
    if not rq:
        return page("<p class=e>This sign-in link expired. Go back to the app and try again.</p>", 400)
    ru, state, iss = rq["redirect_uri"], rq["state"], config.PUBLIC_URL

    def finish(**kw):  # a request id is single use
        with db.conn() as c:
            c.execute("DELETE FROM oauth_requests WHERE id=?", (rq["id"],))
        return back(ru, state=state, iss=iss, **kw)

    if f.get("action") == "deny":
        return finish(error="access_denied")
    email, pw = (f.get("email") or "").strip().lower()[:200], f.get("password") or ""
    # Brute-force protection: per IP and per account.
    if db.rate_check("login-ip:" + client_ip(request), LOGIN_IP_LIMIT, LOGIN_WINDOW) or db.rate_check("login-em:" + email, LOGIN_ACCOUNT_LIMIT, LOGIN_WINDOW):
        return login_page(rq["id"], rq["name"], "Too many attempts. Wait 15 minutes.", 429)
    uid = None
    if f.get("action") == "signup":
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(pw) < PASSWORD_MIN:
            return login_page(rq["id"], rq["name"], "Enter a valid email and a password of 10+ characters.", 400)
        try:
            with db.conn() as c:
                row = c.execute("INSERT INTO users(email,pw_hash,created_at) VALUES(?,?,?) RETURNING id",
                                (email, hash_pw(pw), time.time())).fetchone()
            uid = row["id"]
        except sqlite3.IntegrityError:
            return login_page(rq["id"], rq["name"], "That email already has an account. Use Sign in.", 400)
    else:
        with db.conn() as c:
            u = c.execute("SELECT id, pw_hash FROM users WHERE email=?", (email,)).fetchone()
        if check_pw(pw, u["pw_hash"] if u else DUMMY_HASH) and u:
            uid = u["id"]
        else:
            return login_page(rq["id"], rq["name"], "Wrong email or password.", 401)
    code = secrets.token_urlsafe(32)
    with db.conn() as c:
        c.execute("INSERT INTO oauth_codes VALUES(?,?,?,?,?,?,?,?)",
                  (sha(code), rq["client_id"], uid, ru, rq["challenge"], rq["scope"], rq["resource"],
                   time.time() + config.CODE_TTL))
    return finish(code=code)


# ---- token endpoint ---------------------------------------------------------------
def issue(client_id, user_id, scope, resource, family):
    """Create and store an access + refresh token pair in a token family."""
    access, refresh, now = secrets.token_urlsafe(32), secrets.token_urlsafe(32), time.time()
    with db.conn() as c:
        c.execute("INSERT INTO oauth_tokens(hash,kind,family,client_id,user_id,scope,resource,expires_at) VALUES(?,?,?,?,?,?,?,?)",
                  (sha(access), "access", family, client_id, user_id, scope, resource, now + config.ACCESS_TTL))
        c.execute("INSERT INTO oauth_tokens(hash,kind,family,client_id,user_id,scope,resource,expires_at) VALUES(?,?,?,?,?,?,?,?)",
                  (sha(refresh), "refresh", family, client_id, user_id, scope, resource, now + config.REFRESH_TTL))
    return JSONResponse({"access_token": access, "token_type": "Bearer", "expires_in": config.ACCESS_TTL,
                         "refresh_token": refresh, "scope": scope}, headers=NO_STORE)


@router.post("/oauth/token")
async def token(request: Request):
    """Token endpoint: authorization_code (PKCE) and refresh_token grants."""
    f = await form(request)
    if db.rate_check("tok:" + client_ip(request), TOKEN_IP_LIMIT):
        return oerr("temporarily_unavailable", "Too many requests.", 429)
    gt = f.get("grant_type")
    if gt == "authorization_code":
        with db.tx() as c:  # codes are single use: delete on first sight
            row = c.execute("SELECT * FROM oauth_codes WHERE hash=?", (sha(f.get("code", "")),)).fetchone()
            if row:
                c.execute("DELETE FROM oauth_codes WHERE hash=?", (row["hash"],))
        v = f.get("code_verifier", "")
        if (not row or row["expires_at"] < time.time() or row["client_id"] != f.get("client_id")
                or row["redirect_uri"] != f.get("redirect_uri") or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", v)
                or not hmac.compare_digest(b64url(hashlib.sha256(v.encode()).digest()), row["challenge"])):
            return oerr("invalid_grant", "Invalid or expired code, redirect URI or PKCE verifier.")
        return issue(row["client_id"], row["user_id"], row["scope"], row["resource"], secrets.token_hex(8))
    if gt == "refresh_token":
        reused = False
        with db.tx() as c:
            row = c.execute("SELECT * FROM oauth_tokens WHERE hash=? AND kind='refresh'", (sha(f.get("refresh_token", "")),)).fetchone()
            if row and (row["used"] or row["revoked"]):
                reused = True  # stolen-token signal: kill the whole family
                c.execute("UPDATE oauth_tokens SET revoked=1 WHERE family=?", (row["family"],))
            elif row:
                c.execute("UPDATE oauth_tokens SET used=1 WHERE hash=?", (row["hash"],))
        if not row or reused or row["expires_at"] < time.time() or row["client_id"] != f.get("client_id"):
            return oerr("invalid_grant", "Invalid refresh token.")
        return issue(row["client_id"], row["user_id"], row["scope"], row["resource"], row["family"])
    return oerr("unsupported_grant_type", "Use authorization_code or refresh_token.")


@router.post("/oauth/revoke")
async def revoke(request: Request):
    """Revoke a token (a refresh token revokes its whole family)."""
    t = (await form(request)).get("token", "")
    with db.tx() as c:
        row = c.execute("SELECT family, kind FROM oauth_tokens WHERE hash=?", (sha(t),)).fetchone()
        if row:  # revoking a refresh token revokes its whole family
            c.execute("UPDATE oauth_tokens SET revoked=1 WHERE " + ("family=?" if row["kind"] == "refresh" else "hash=?"),
                      (row["family"] if row["kind"] == "refresh" else sha(t),))
    return JSONResponse({}, headers=NO_STORE)  # always 200 per RFC 7009


def verify_access_token(t):
    """Return the token row if valid, else None."""
    with db.conn() as c:
        r = c.execute("SELECT * FROM oauth_tokens WHERE hash=? AND kind='access' AND revoked=0 AND expires_at>?",
                      (sha(t), time.time())).fetchone()
    return dict(r) if r else None


def delete_user(uid, password):
    """Delete an account and everything tied to it. Returns 'ok', 'bad_password' or 'limited'."""
    if db.rate_check(f"delacct:{uid}", 5, 900):
        return "limited"
    with db.conn() as c:
        u = c.execute("SELECT pw_hash FROM users WHERE id=?", (uid,)).fetchone()
    if not u or not check_pw(password, u["pw_hash"]):
        return "bad_password"
    mine = (f"user:{uid}", f"user:{uid}:insights")
    with db.tx() as c:  # one transaction: all or nothing
        c.execute("DELETE FROM oauth_tokens WHERE user_id=?", (uid,))
        c.execute("DELETE FROM oauth_codes WHERE user_id=?", (uid,))
        c.execute("DELETE FROM jobs WHERE principal IN (?,?)", mine)
        c.execute("DELETE FROM usage WHERE principal IN (?,?)", mine)
        c.execute("DELETE FROM users WHERE id=?", (uid,))
    return "ok"
