"""Render background worker entrypoint for the shared RQ queue."""
import os
import db, jobs
from redis import Redis
from rq import Queue, Worker

if __name__ == "__main__":
    db.init()
    db.recover_stale_jobs(max(300, jobs.config.JOB_TIMEOUT * 2))
    jobs.start_purger()
    connection = Redis.from_url(os.environ["REDIS_URL"])
    queue = Queue(os.environ.get("QUEUE_NAME", "price-agent"), connection=connection)
    Worker([queue], connection=connection).work()
