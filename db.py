"""SQLite storage: schema plus small helpers for cache, rate limits and jobs.
One file, WAL mode, a short-lived connection per call (safe across threads)."""
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_clients(client_id TEXT PRIMARY KEY, name TEXT NOT NULL, redirect_uris TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_requests(id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES oauth_clients(client_id), redirect_uri TEXT NOT NULL, state TEXT, challenge TEXT NOT NULL, scope TEXT NOT NULL, resource TEXT, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_codes(hash TEXT PRIMARY KEY, client_id TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), redirect_uri TEXT NOT NULL, challenge TEXT NOT NULL, scope TEXT NOT NULL, resource TEXT, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_tokens(hash TEXT PRIMARY KEY, kind TEXT NOT NULL, family TEXT NOT NULL, client_id TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), scope TEXT NOT NULL, resource TEXT, expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_tokens_family ON oauth_tokens(family);
CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY, principal TEXT NOT NULL, ts REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_usage ON usage(principal, ts);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, key TEXT NOT NULL, status TEXT NOT NULL, product TEXT, country TEXT, city TEXT, sites TEXT, principal TEXT, result TEXT, error TEXT, source TEXT, input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0, searches INTEGER DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_jobs_key ON jobs(key, status);
"""


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH, timeout=30, isolation_level=None)  # autocommit
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
    finally:
        c.close()


@contextmanager
def tx():
    """Write transaction: takes the write lock up front, commits or rolls back."""
    with conn() as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.execute("COMMIT")
        except BaseException:
            c.execute("ROLLBACK")
            raise


def init():
    d = os.path.dirname(config.DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    with conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
        # Jobs that were in flight when the process stopped can never finish.
        c.execute("UPDATE jobs SET status='error', error='Server restarted. Please retry.', updated_at=? "
                  "WHERE status IN ('queued','running')", (time.time(),))


# ---- cache -------------------------------------------------------------
def cache_get(key):
    with conn() as c:
        r = c.execute("SELECT value FROM cache WHERE key=? AND expires_at>?", (key, time.time())).fetchone()
    return json.loads(r["value"]) if r else None


def cache_set(key, value):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO cache(key,value,expires_at) VALUES(?,?,?)",
                  (key, json.dumps(value), time.time() + config.CACHE_TTL))


# ---- rate limits (sliding window, persisted) -----------------------------
def rate_check(principal, limit, window=3600):
    """Record one use. Returns None if allowed, else minutes until allowed again."""
    now = time.time()
    with tx() as c:
        r = c.execute("SELECT MIN(ts) m, COUNT(*) n FROM usage WHERE principal=? AND ts>?",
                      (principal, now - window)).fetchone()
        if r["n"] >= limit:
            return max(1, int((r["m"] + window - now) // 60) + 1)
        c.execute("INSERT INTO usage(principal, ts) VALUES(?,?)", (principal, now))
    return None


# ---- jobs ----------------------------------------------------------------
_JOB_FIELDS = {"status", "result", "error", "source", "input_tokens", "output_tokens", "searches"}


def job_create(key, params, principal, status="queued"):
    jid, now = secrets.token_urlsafe(16), time.time()
    with conn() as c:
        c.execute("INSERT INTO jobs(id,key,status,product,country,city,sites,principal,created_at,updated_at) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (jid, key, status, params["product"], params["country"], params["city"],
                   json.dumps(params["sites"]), principal, now, now))
    return jid


def job_update(jid, **fields):
    assert set(fields) <= _JOB_FIELDS
    if "result" in fields:
        fields["result"] = json.dumps(fields["result"])
    cols = ",".join(f"{k}=?" for k in fields) + ",updated_at=?"
    with conn() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), time.time(), jid))


def job_get(jid):
    with conn() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["result"] = json.loads(d["result"]) if d["result"] else None
    return d


def job_active(key):
    with conn() as c:
        r = c.execute("SELECT id FROM jobs WHERE key=? AND status IN ('queued','running') "
                      "ORDER BY created_at DESC LIMIT 1", (key,)).fetchone()
    return r["id"] if r else None


# ---- housekeeping --------------------------------------------------------
def purge():
    now = time.time()
    with tx() as c:
        c.execute("DELETE FROM cache WHERE expires_at<?", (now,))
        c.execute("DELETE FROM usage WHERE ts<?", (now - 86400,))
        c.execute("DELETE FROM oauth_requests WHERE expires_at<?", (now,))
        c.execute("DELETE FROM oauth_codes WHERE expires_at<?", (now,))
        c.execute("DELETE FROM oauth_tokens WHERE expires_at<?", (now - 86400,))
        c.execute("DELETE FROM jobs WHERE created_at<?", (now - 7 * 86400,))


def stats():
    with conn() as c:
        one = lambda q: c.execute(q).fetchone()[0]
        jobs = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status")}
        s = one("SELECT COALESCE(SUM(searches),0) FROM jobs")
        return {"jobs": jobs, "users": one("SELECT COUNT(*) FROM users"),
                "oauth_clients": one("SELECT COUNT(*) FROM oauth_clients"),
                "cache_entries": one("SELECT COUNT(*) FROM cache"),
                "input_tokens": one("SELECT COALESCE(SUM(input_tokens),0) FROM jobs"),
                "output_tokens": one("SELECT COALESCE(SUM(output_tokens),0) FROM jobs"),
                "web_searches": s, "search_cost_usd_estimate": round(s * 0.01, 2)}
