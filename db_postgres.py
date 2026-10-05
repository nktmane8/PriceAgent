"""PostgreSQL storage backend for distributed Render deployments."""
import json, secrets, time
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row

class _Conn:
    def __init__(self, raw): self.raw = raw
    def execute(self, sql, params=None): return self.raw.execute(sql.replace("?", "%s"), params)
    def executemany(self, sql, params): return self.raw.executemany(sql.replace("?", "%s"), params)
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb):
        if exc_type: self.raw.rollback()
        else: self.raw.commit()
        self.raw.close()

import config
from constants import HISTORY_DAYS, HISTORY_RETENTION_DAYS, HOUR, JOB_RETENTION_DAYS, QUEUED, SEARCH_COST_USD, USAGE_RETENTION_DAYS

SCHEMA=[
"CREATE TABLE IF NOT EXISTS users(id BIGSERIAL PRIMARY KEY,email TEXT UNIQUE NOT NULL,pw_hash TEXT NOT NULL,created_at DOUBLE PRECISION NOT NULL)",
"CREATE TABLE IF NOT EXISTS oauth_clients(client_id TEXT PRIMARY KEY,name TEXT NOT NULL,redirect_uris TEXT NOT NULL,created_at DOUBLE PRECISION NOT NULL)",
"CREATE TABLE IF NOT EXISTS oauth_requests(id TEXT PRIMARY KEY,client_id TEXT NOT NULL REFERENCES oauth_clients(client_id),redirect_uri TEXT NOT NULL,state TEXT,challenge TEXT NOT NULL,scope TEXT NOT NULL,resource TEXT,expires_at DOUBLE PRECISION NOT NULL)",
"CREATE TABLE IF NOT EXISTS oauth_codes(hash TEXT PRIMARY KEY,client_id TEXT NOT NULL,user_id BIGINT NOT NULL REFERENCES users(id),redirect_uri TEXT NOT NULL,challenge TEXT NOT NULL,scope TEXT NOT NULL,resource TEXT,expires_at DOUBLE PRECISION NOT NULL)",
"CREATE TABLE IF NOT EXISTS oauth_tokens(hash TEXT PRIMARY KEY,kind TEXT NOT NULL,family TEXT NOT NULL,client_id TEXT NOT NULL,user_id BIGINT NOT NULL REFERENCES users(id),scope TEXT NOT NULL,resource TEXT,expires_at DOUBLE PRECISION NOT NULL,revoked INTEGER NOT NULL DEFAULT 0,used INTEGER NOT NULL DEFAULT 0)",
"CREATE INDEX IF NOT EXISTS ix_tokens_family ON oauth_tokens(family)",
"CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,value TEXT NOT NULL,expires_at DOUBLE PRECISION NOT NULL)",
"CREATE TABLE IF NOT EXISTS usage(id BIGSERIAL PRIMARY KEY,principal TEXT NOT NULL,ts DOUBLE PRECISION NOT NULL)",
"CREATE INDEX IF NOT EXISTS ix_usage ON usage(principal,ts)",
"CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,key TEXT NOT NULL,status TEXT NOT NULL,product TEXT,country TEXT,city TEXT,sites TEXT,principal TEXT,result TEXT,error TEXT,source TEXT,input_tokens INTEGER DEFAULT 0,output_tokens INTEGER DEFAULT 0,searches INTEGER DEFAULT 0,created_at DOUBLE PRECISION NOT NULL,updated_at DOUBLE PRECISION NOT NULL)",
"CREATE INDEX IF NOT EXISTS ix_jobs_key ON jobs(key,status)",
"CREATE TABLE IF NOT EXISTS price_history(id BIGSERIAL PRIMARY KEY,key TEXT NOT NULL,store TEXT NOT NULL,price DOUBLE PRECISION,effective_price DOUBLE PRECISION,currency TEXT,ts DOUBLE PRECISION NOT NULL)",
"CREATE INDEX IF NOT EXISTS ix_hist ON price_history(key,ts)"
]

@contextmanager
def conn():
    with psycopg.connect(config.DATABASE_URL,row_factory=dict_row) as raw:
        yield _Conn(raw)

@contextmanager
def tx():
    with psycopg.connect(config.DATABASE_URL,row_factory=dict_row) as raw:
        c=_Conn(raw)
        try: yield c; raw.commit()
        except BaseException: raw.rollback(); raise

def init():
    with psycopg.connect(config.DATABASE_URL) as c:
        for s in SCHEMA:c.execute(s)
        c.commit()

def recover_stale_jobs(max_age):
    """Mark jobs stuck in running state after a worker/process loss."""
    cutoff = time.time() - max_age
    with tx() as c:
        c.execute("UPDATE jobs SET status='error', error='Worker lost while processing the job. Please retry.', updated_at=%s WHERE status='running' AND updated_at<%s",
                  (time.time(), cutoff))


def cache_get(key):
    with conn() as c:r=c.execute("SELECT value FROM cache WHERE key=%s AND expires_at>%s",(key,time.time())).fetchone()
    return json.loads(r["value"]) if r else None

def cache_set(key,value):
    with conn() as c:
        c.execute("INSERT INTO cache(key,value,expires_at) VALUES(%s,%s,%s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,expires_at=EXCLUDED.expires_at",(key,json.dumps(value),time.time()+config.CACHE_TTL));c.commit()

def rate_check(principal,limit,window=HOUR):
    """Atomically enforce a sliding-window limit across concurrent API instances."""
    now=time.time()
    with tx() as c:
        c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (principal,))
        r=c.execute("SELECT MIN(ts) AS m,COUNT(*) AS n FROM usage WHERE principal=%s AND ts>%s",(principal,now-window)).fetchone()
        if r["n"]>=limit:return max(1,int((r["m"]+window-now)//60)+1)
        c.execute("INSERT INTO usage(principal,ts) VALUES(%s,%s)",(principal,now))
    return None

_JOB_FIELDS={"status","result","error","source","input_tokens","output_tokens","searches"}

def job_create(key,p,principal,status=QUEUED):
    jid,now=secrets.token_urlsafe(16),time.time()
    with conn() as c:
        c.execute("INSERT INTO jobs(id,key,status,product,country,city,sites,principal,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(jid,key,status,p["product"],p["country"],p["city"],json.dumps(p["sites"]),principal,now,now));c.commit()
    return jid

def job_update(jid,**fields):
    assert set(fields)<=_JOB_FIELDS
    if "result" in fields:fields["result"]=json.dumps(fields["result"])
    cols=",".join(f"{k}=%s" for k in fields)+",updated_at=%s"
    with conn() as c:c.execute(f"UPDATE jobs SET {cols} WHERE id=%s",(*fields.values(),time.time(),jid));c.commit()

def job_get(jid):
    with conn() as c:r=c.execute("SELECT * FROM jobs WHERE id=%s",(jid,)).fetchone()
    if not r:return None
    d=dict(r);d["result"]=json.loads(d["result"]) if d["result"] else None;return d

def job_active(key):
    with conn() as c:r=c.execute("SELECT id FROM jobs WHERE key=%s AND status IN ('queued','running') ORDER BY created_at DESC LIMIT 1",(key,)).fetchone()
    return r["id"] if r else None

def history_key(product,country,city):return "|".join([product.lower(),country.lower(),city.lower()])

def record_history(hkey,data):
    now=time.time();rows=[(hkey,r["site"],r["price"],r["effective_price"],data.get("currency",""),now) for r in data.get("results",[]) if r.get("effective_price") is not None]
    if rows:
        with tx() as c:c.executemany("INSERT INTO price_history(key,store,price,effective_price,currency,ts) VALUES(%s,%s,%s,%s,%s,%s)",rows)

def history_summary(hkey,days=HISTORY_DAYS):
    since=time.time()-days*86400
    with conn() as c:
        daily=[dict(r) for r in c.execute("SELECT to_timestamp(ts)::date AS day,MIN(effective_price) AS low FROM price_history WHERE key=%s AND ts>%s AND effective_price IS NOT NULL GROUP BY day ORDER BY day",(hkey,since))]
        best=c.execute("SELECT store,effective_price,currency,to_timestamp(ts)::date AS date FROM price_history WHERE key=%s AND ts>%s AND effective_price IS NOT NULL ORDER BY effective_price LIMIT 1",(hkey,since)).fetchone()
    return {"days":daily,"lowest":({"store":best["store"],"price":best["effective_price"],"currency":best["currency"],"date":str(best["date"])} if best else None)}

def purge():
    now=time.time()
    with tx() as c:
        for q,v in [("DELETE FROM cache WHERE expires_at<%s",(now,)),("DELETE FROM usage WHERE ts<%s",(now-USAGE_RETENTION_DAYS*86400,)),("DELETE FROM oauth_requests WHERE expires_at<%s",(now,)),("DELETE FROM oauth_codes WHERE expires_at<%s",(now,)),("DELETE FROM oauth_tokens WHERE expires_at<%s",(now-86400,)),("DELETE FROM jobs WHERE created_at<%s",(now-JOB_RETENTION_DAYS*86400,)),("DELETE FROM price_history WHERE ts<%s",(now-HISTORY_RETENTION_DAYS*86400,))]:c.execute(q,v)

def stats():
    with conn() as c:
        jobs={r["status"]:r["n"] for r in c.execute("SELECT status,COUNT(*) AS n FROM jobs GROUP BY status")}
        s=c.execute("SELECT COALESCE(SUM(searches),0) AS v FROM jobs").fetchone()["v"];done=c.execute("SELECT COUNT(*) AS v FROM jobs WHERE status='done'").fetchone()["v"];cached=c.execute("SELECT COUNT(*) AS v FROM jobs WHERE status='done' AND source='cache'").fetchone()["v"]
        errors=[dict(r) for r in c.execute("SELECT error,COUNT(*) AS n FROM jobs WHERE status='error' GROUP BY error ORDER BY n DESC LIMIT 5")]
        by_type={r["t"]:{"jobs":r["jobs"],"searches":r["s"]} for r in c.execute("SELECT split_part(principal,':',1) AS t,COUNT(*) AS jobs,COALESCE(SUM(searches),0) AS s FROM jobs GROUP BY t")}
        q=lambda x:c.execute(x).fetchone()["v"]
        return {"jobs":jobs,"users":q("SELECT COUNT(*) AS v FROM users"),"oauth_clients":q("SELECT COUNT(*) AS v FROM oauth_clients"),"cache_entries":q("SELECT COUNT(*) AS v FROM cache"),"price_history_rows":q("SELECT COUNT(*) AS v FROM price_history"),"input_tokens":q("SELECT COALESCE(SUM(input_tokens),0) AS v FROM jobs"),"output_tokens":q("SELECT COALESCE(SUM(output_tokens),0) AS v FROM jobs"),"web_searches":s,"search_cost_usd_estimate":round(s*SEARCH_COST_USD,2),"cache_hit_rate":round(cached/done,3) if done else None,"avg_agent_seconds":round(q("SELECT COALESCE(AVG(updated_at-created_at),0) AS v FROM jobs WHERE status='done' AND source='agent'"),1),"top_errors":errors,"by_principal_type":by_type}
