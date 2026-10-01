"""Background jobs: a thread pool runs the slow agent so web requests return fast.
Same-query requests share one job (in-flight dedupe); results are cached in SQLite."""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import agent
import config
from constants import DONE, ERROR, FINISHED, KIND_INSIGHTS, KIND_PRICES, PURGE_INTERVAL, RUNNING
import db

log = logging.getLogger("price-agent")
_pool = ThreadPoolExecutor(max_workers=config.WORKERS, thread_name_prefix="agent")
_submit_lock = threading.Lock()
_stop = threading.Event()


class RateLimited(Exception):
    """Raised when the caller is over their hourly limit; carries minutes to wait."""
    def __init__(self, minutes):
        self.minutes = minutes


def make_key(p):
    """Cache/dedupe key: kind + product + country + city + sites."""
    return "|".join([p.get("kind", KIND_PRICES), p["product"].lower(), p["country"].lower(), p["city"].lower(), ",".join(sorted(p["sites"]))])


def submit(params, principal, limit):
    """Return a job id. Order: cache hit -> join running job -> rate limit -> start new job."""
    key = make_key(params)
    with _submit_lock:  # make "check then create" atomic within this process
        cached = db.cache_get(key)
        if cached is not None:
            jid = db.job_create(key, params, principal, status=DONE)
            db.job_update(jid, status=DONE, result=cached, source="cache")
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
    """Worker thread body: run the agent, cache, record history, save the job outcome."""
    db.job_update(jid, status=RUNNING)
    try:
        run = agent.run_insights if params.get("kind") == KIND_INSIGHTS else agent.run_agent
        data, usage = run(params["product"], params["country"], params["city"], params["sites"])
        db.cache_set(key, data)
        if params.get("kind", KIND_PRICES) == KIND_PRICES:
            db.record_history(db.history_key(params["product"], params["country"], params["city"]), data)
        db.job_update(jid, status=DONE, result=data, source="agent", **usage)
    except agent.AgentError as e:
        db.job_update(jid, status=ERROR, error=str(e))
    except Exception:
        log.exception("job %s crashed", jid)
        db.job_update(jid, status=ERROR, error="Unexpected server error. Please retry.")


def wait(jid, timeout):
    """Poll until the job finishes or `timeout` seconds pass."""
    end = time.time() + timeout
    while True:
        job = db.job_get(jid)
        if job["status"] in FINISHED or time.time() >= end:
            return job
        time.sleep(0.5)


def view(job):
    """The only fields clients may see."""
    out = {"job_id": job["id"], "status": job["status"]}
    if job["status"] == DONE:
        out["result"], out["cached"] = job["result"], job["source"] == "cache"
    if job["status"] == ERROR:
        out["error"] = job["error"]
    return out


def start_purger(interval=PURGE_INTERVAL):
    """Daemon thread that deletes expired cache rows, tokens, codes and old jobs."""
    def loop():
        while not _stop.wait(interval):
            try:
                db.purge()
            except Exception:
                log.exception("purge failed")
    threading.Thread(target=loop, name="purger", daemon=True).start()
