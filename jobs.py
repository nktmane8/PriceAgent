"""Distributed background jobs using Redis/Valkey + RQ, with an in-process fallback for local tests."""
import hashlib, logging, threading, time
from concurrent.futures import ThreadPoolExecutor
import agent, config, db
from constants import DONE, ERROR, FINISHED, KIND_INSIGHTS, KIND_PRICES, PURGE_INTERVAL, RUNNING

try:
    from redis import Redis
    from rq import Queue
except ImportError:
    Redis = Queue = None

log = logging.getLogger("price-agent")
_pool = ThreadPoolExecutor(max_workers=config.WORKERS, thread_name_prefix="agent")
_submit_lock = threading.Lock()
_stop = threading.Event()

class RateLimited(Exception):
    def __init__(self, minutes):
        self.minutes = minutes

def _redis():
    if not config.REDIS_URL or Redis is None:
        return None
    return Redis.from_url(config.REDIS_URL, decode_responses=False)

def _queue():
    r = _redis()
    return Queue(config.QUEUE_NAME, connection=r, default_timeout=config.JOB_TIMEOUT) if r else None

def make_key(p):
    return "|".join([p.get("kind", KIND_PRICES),p["product"].lower(),p["country"].lower(),p["city"].lower(),",".join(sorted(p["sites"]))])

def submit(params, principal, limit):
    key = make_key(params)
    r = _redis()
    lock = r.lock("priceagent:submit:"+hashlib.sha256(key.encode()).hexdigest(), timeout=15) if r else _submit_lock
    with lock:
        cached=db.cache_get(key)
        if cached is not None:
            jid=db.job_create(key,params,principal,status=DONE)
            db.job_update(jid,status=DONE,result=cached,source="cache")
            return jid
        active=db.job_active(key)
        if active:
            return active
        wait=db.rate_check(principal,limit)
        if wait:
            raise RateLimited(wait)
        jid=db.job_create(key,params,principal)
        q=_queue()
        if q:
            try:
                q.enqueue(_work,jid,key,params,job_id=jid,result_ttl=config.JOB_RESULT_TTL,failure_ttl=config.JOB_FAILURE_TTL)
            except Exception:
                log.exception("queue enqueue failed for job %s", jid)
                db.job_update(jid,status=ERROR,error="QUEUE_UNAVAILABLE")
                raise
        else:
            _pool.submit(_work,jid,key,params)
        return jid

def _work(jid,key,params):
    db.job_update(jid,status=RUNNING)
    try:
        run=agent.run_insights if params.get("kind")==KIND_INSIGHTS else agent.run_agent
        data,usage=run(params["product"],params["country"],params["city"],params["sites"])
        db.cache_set(key,data)
        if params.get("kind",KIND_PRICES)==KIND_PRICES:
            db.record_history(db.history_key(params["product"],params["country"],params["city"]),data)
        db.job_update(jid,status=DONE,result=data,source="agent",**usage)
    except agent.AgentError as e:
        db.job_update(jid,status=ERROR,error=str(e))
    except Exception:
        log.exception("job %s crashed",jid)
        db.job_update(jid,status=ERROR,error="Unexpected server error. Please retry.")

def wait(jid,timeout):
    end=time.time()+timeout
    while True:
        job=db.job_get(jid)
        if job is None or job["status"] in FINISHED or time.time()>=end:
            return job
        time.sleep(0.5)

def view(job):
    out={"job_id":job["id"],"status":job["status"]}
    if job["status"]==DONE:
        out["result"],out["cached"]=job["result"],job["source"]=="cache"
    if job["status"]==ERROR:
        out["error"]=job["error"]
    return out

def start_purger(interval=PURGE_INTERVAL):
    def loop():
        while not _stop.wait(interval):
            try:
                db.purge()
            except Exception:
                log.exception("purge failed")
    threading.Thread(target=loop,name="purger",daemon=True).start()
