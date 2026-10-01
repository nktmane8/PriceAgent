"""Background jobs: a thread pool runs the slow agent so web requests return fast.
Same-query requests share one job (in-flight dedupe); results are cached in SQLite."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import agent
import config
import db

log = logging.getLogger("price-agent")
_pool = ThreadPoolExecutor(max_workers=config.WORKERS, thread_name_prefix="agent")
_submit_lock = threading.Lock()
_stop = threading.Event()


class RateLimited(Exception):
    def __init__(self, minutes):
        self.minutes = minutes


def make_key(p):
    return "|".join([p["product"].lower(), p["country"].lower(), p["city"].lower(), ",".join(sorted(p["sites"]))])


def submit(params, principal, limit):
    """Return a job id. Order: cache hit -> join running job -> rate limit -> start new job."""
    key = make_key(params)
    with _submit_lock:  # make "check then create" atomic within this process
        cached = db.cache_get(key)
        if cached is not None:
            jid = db.job_create(key, params, principal, status="done")
            db.job_update(jid, status="done", result=cached, source="cache")
            return jid
        active = db.job_active(key)
        if active:
            return active
        wait = db.rate_check(principal, limit)
        if wait:
            raise RateLimited(wait)
        jid = db.job_create(key, params, principal)
    _pool.submit(_work, jid, key, params)
    return jid


def _work(jid, key, params):
    db.job_update(jid, status="running")
    try:
        data, usage = agent.run_agent(params["product"], params["country"], params["city"], params["sites"])
        db.cache_set(key, data)
        if params.get("kind", "prices") == "prices":
            db.record_history(db.history_key(params["product"], params["country"], params["city"]), data)
        db.job_update(jid, status="done", result=data, source="agent", **usage)
    except agent.AgentError as e:
        db.job_update(jid, status="error", error=str(e))
    except Exception:
        log.exception("job %s crashed", jid)
        db.job_update(jid, status="error", error="Unexpected server error. Please retry.")


def wait(jid, timeout):
    """Poll until the job finishes or `timeout` seconds pass."""
    end = time.time() + timeout
    while True:
        job = db.job_get(jid)
        if job["status"] in ("done", "error") or time.time() >= end:
            return job
        time.sleep(0.5)


def view(job):
    """The only fields clients may see."""
    out = {"job_id": job["id"], "status": job["status"]}
    if job["status"] == "done":
        out["result"], out["cached"] = job["result"], job["source"] == "cache"
    if job["status"] == "error":
        out["error"] = job["error"]
    return out


def start_purger(interval=600):
    """Daemon thread that deletes expired cache rows, tokens, codes and old jobs."""
    def loop():
        while not _stop.wait(interval):
            try:
                db.purge()
            except Exception:
                log.exception("purge failed")
    threading.Thread(target=loop, name="purger", daemon=True).start()
