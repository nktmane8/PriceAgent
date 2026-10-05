"""SQLite storage backend used for local development and tests."""
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager

import config
from product_identity import normalize
from constants import (HISTORY_DAYS, HISTORY_RETENTION_DAYS, HOUR, JOB_RETENTION_DAYS, QUEUED, SEARCH_COST_USD,
                       USAGE_RETENTION_DAYS)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT, google_sub TEXT UNIQUE, auth_provider TEXT NOT NULL DEFAULT 'password', created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_clients(client_id TEXT PRIMARY KEY, name TEXT NOT NULL, redirect_uris TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_requests(id TEXT PRIMARY KEY, client_id TEXT NOT NULL REFERENCES oauth_clients(client_id), redirect_uri TEXT NOT NULL, state TEXT, challenge TEXT NOT NULL, scope TEXT NOT NULL, resource TEXT, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_codes(hash TEXT PRIMARY KEY, client_id TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), redirect_uri TEXT NOT NULL, challenge TEXT NOT NULL, scope TEXT NOT NULL, resource TEXT, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_tokens(hash TEXT PRIMARY KEY, kind TEXT NOT NULL, family TEXT NOT NULL, client_id TEXT NOT NULL, user_id INTEGER NOT NULL REFERENCES users(id), scope TEXT NOT NULL, resource TEXT, expires_at REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_tokens_family ON oauth_tokens(family);
CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT NOT NULL, expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY, principal TEXT NOT NULL, ts REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_usage ON usage(principal, ts);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, key TEXT NOT NULL, status TEXT NOT NULL, product TEXT, country TEXT, city TEXT, sites TEXT, principal TEXT, result TEXT, error TEXT, error_code TEXT, source TEXT, input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0, searches INTEGER DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_jobs_key ON jobs(key, status);
CREATE TABLE IF NOT EXISTS price_history(id INTEGER PRIMARY KEY, key TEXT NOT NULL, store TEXT NOT NULL, price REAL, effective_price REAL, currency TEXT, ts REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_hist ON price_history(key, ts);
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_key TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL, brand TEXT, variant TEXT, storage TEXT, color TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_products_brand ON products(brand);
"""


@contextmanager
def conn():
    """Open a SQLite connection (autocommit, row dicts, foreign keys on)."""
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
    """Create tables and fail jobs left over from a previous process."""
    d = os.path.dirname(config.DB_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    with conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
        for sql in (
            "ALTER TABLE users ADD COLUMN google_sub TEXT",
            "ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'password'",
            "ALTER TABLE users ADD COLUMN pw_hash TEXT",
        ):
            try:
                c.execute(sql)
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_google_sub ON users(google_sub)")
        try:
            c.execute("ALTER TABLE jobs ADD COLUMN error_code TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
        # Jobs that were in flight when the process stopped can never finish.
        c.execute("UPDATE jobs SET status='error', error='Server restarted. Please retry.', updated_at=? "
                  "WHERE status IN ('queued','running')", (time.time(),))


# ---- cache -------------------------------------------------------------
def recover_stale_jobs(max_age):
    """Mark jobs stuck in running state after a worker/process loss."""
    cutoff = time.time() - max_age
    with tx() as c:
        c.execute("UPDATE jobs SET status='error', error='Worker lost while processing the job. Please retry.', updated_at=? WHERE status='running' AND updated_at<?",
                  (time.time(), cutoff))


def cache_get(key):
    """Read a fresh cached result or None."""
    with conn() as c:
        r = c.execute("SELECT value FROM cache WHERE key=? AND expires_at>?", (key, time.time())).fetchone()
    return json.loads(r["value"]) if r else None


def cache_set(key, value):
    """Save a result with the cache TTL."""
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO cache(key,value,expires_at) VALUES(?,?,?)",
                  (key, json.dumps(value), time.time() + config.CACHE_TTL))


# ---- rate limits (sliding window, persisted) -----------------------------
def rate_check(principal, limit, window=HOUR):
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
_JOB_FIELDS = {"status", "result", "error", "error_code", "source", "input_tokens", "output_tokens", "searches"}


def job_create(key, params, principal, status=QUEUED):
    """Insert a new job row and return its secret id."""
    jid, now = secrets.token_urlsafe(16), time.time()
    with conn() as c:
        c.execute("INSERT INTO jobs(id,key,status,product,country,city,sites,principal,created_at,updated_at) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (jid, key, status, params["product"], params["country"], params["city"],
                   json.dumps(params["sites"]), principal, now, now))
    return jid


def job_update(jid, **fields):
    """Update allowed job fields (status, result, error, cost)."""
    assert set(fields) <= _JOB_FIELDS
    if "result" in fields:
        fields["result"] = json.dumps(fields["result"])
    cols = ",".join(f"{k}=?" for k in fields) + ",updated_at=?"
    with conn() as c:
        c.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*fields.values(), time.time(), jid))


def job_get(jid):
    """Load a job with its result parsed, or None."""
    with conn() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["result"] = json.loads(d["result"]) if d["result"] else None
    return d


def job_active(key):
    """Id of a queued/running job with this key, if any."""
    with conn() as c:
        r = c.execute("SELECT id FROM jobs WHERE key=? AND status IN ('queued','running') "
                      "ORDER BY created_at DESC LIMIT 1", (key,)).fetchone()
    return r["id"] if r else None


def product_upsert(identity):
    """Persist a canonical product identity and return its stable id."""
    now = time.time()
    with tx() as c:
        c.execute(
            "INSERT INTO products(canonical_key,display_name,brand,variant,storage,color,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(canonical_key) DO UPDATE SET display_name=excluded.display_name,updated_at=excluded.updated_at",
            (identity["canonical_key"], identity["display_name"], identity["brand"], identity["variant"],
             identity["storage"], identity["color"], now, now),
        )
        row = c.execute("SELECT id FROM products WHERE canonical_key=?", (identity["canonical_key"],)).fetchone()
    return int(row["id"])

def product_get(canonical_key):
    with conn() as c:
        r = c.execute("SELECT * FROM products WHERE canonical_key=?", (canonical_key,)).fetchone()
    return dict(r) if r else None


# ---- price history -----------------------------------------------------
def history_key(product, country, city):
    """Key used to group price history by canonical product + region."""
    identity = normalize(product)
    return "|".join([identity["canonical_key"], country.lower(), city.lower()])


def record_history(hkey, data):
    """Save every offer of a fresh (not cached) price run. Product and prices only, no user data."""
    now = time.time()
    rows = [(hkey, r["site"], r["price"], r["effective_price"], data.get("currency", ""), now)
            for r in data.get("results", []) if r.get("effective_price") is not None]
    if rows:
        with tx() as c:
            c.executemany("INSERT INTO price_history(key,store,price,effective_price,currency,ts) VALUES(?,?,?,?,?,?)", rows)


def history_summary(hkey, days=HISTORY_DAYS):
    """Daily lows and the lowest price seen in the last N days."""
    since = time.time() - days * 86400
    with conn() as c:
        daily = [dict(r) for r in c.execute(
            "SELECT date(ts,'unixepoch') AS day, MIN(effective_price) AS low FROM price_history "
            "WHERE key=? AND ts>? AND effective_price IS NOT NULL GROUP BY day ORDER BY day", (hkey, since))]
        best = c.execute("SELECT store, effective_price, currency, date(ts,'unixepoch') AS date FROM price_history "
                         "WHERE key=? AND ts>? AND effective_price IS NOT NULL ORDER BY effective_price ASC LIMIT 1",
                         (hkey, since)).fetchone()
    return {"days": daily, "lowest": ({"store": best["store"], "price": best["effective_price"],
                                       "currency": best["currency"], "date": best["date"]} if best else None)}


# ---- housekeeping --------------------------------------------------------
def purge():
    """Delete expired cache, codes, tokens, old jobs and history."""
    now = time.time()
    with tx() as c:
        c.execute("DELETE FROM cache WHERE expires_at<?", (now,))
        c.execute("DELETE FROM usage WHERE ts<?", (now - USAGE_RETENTION_DAYS * 86400,))
        c.execute("DELETE FROM oauth_requests WHERE expires_at<?", (now,))
        c.execute("DELETE FROM oauth_codes WHERE expires_at<?", (now,))
        c.execute("DELETE FROM oauth_tokens WHERE expires_at<?", (now - 86400,))
        c.execute("DELETE FROM jobs WHERE created_at<?", (now - JOB_RETENTION_DAYS * 86400,))
        c.execute("DELETE FROM price_history WHERE ts<?", (now - HISTORY_RETENTION_DAYS * 86400,))


def stats():
    """Admin metrics: volume, latency, cache hit rate, failures, cost drivers."""
    with conn() as c:
        one = lambda q: c.execute(q).fetchone()[0]
        jobs = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) n FROM jobs GROUP BY status")}
        s = one("SELECT COALESCE(SUM(searches),0) FROM jobs")
        done = one("SELECT COUNT(*) FROM jobs WHERE status='done'")
        cached = one("SELECT COUNT(*) FROM jobs WHERE status='done' AND source='cache'")
        errors = [dict(r) for r in c.execute("SELECT error, COUNT(*) n FROM jobs WHERE status='error' "
                                             "GROUP BY error ORDER BY n DESC LIMIT 5")]
        by_type = {r["t"]: dict(jobs=r["jobs"], searches=r["s"]) for r in c.execute(
            "SELECT substr(principal,1,instr(principal,':')-1) t, COUNT(*) jobs, COALESCE(SUM(searches),0) s "
            "FROM jobs GROUP BY t")}
        return {"jobs": jobs, "users": one("SELECT COUNT(*) FROM users"),
                "oauth_clients": one("SELECT COUNT(*) FROM oauth_clients"),
                "cache_entries": one("SELECT COUNT(*) FROM cache"),
                "price_history_rows": one("SELECT COUNT(*) FROM price_history"),
                "input_tokens": one("SELECT COALESCE(SUM(input_tokens),0) FROM jobs"),
                "output_tokens": one("SELECT COALESCE(SUM(output_tokens),0) FROM jobs"),
                "web_searches": s, "search_cost_usd_estimate": round(s * SEARCH_COST_USD, 2),
                "cache_hit_rate": round(cached / done, 3) if done else None,
                "avg_agent_seconds": round(one("SELECT COALESCE(AVG(updated_at-created_at),0) FROM jobs "
                                               "WHERE status='done' AND source='agent'"), 1),
                "top_errors": errors, "by_principal_type": by_type}
