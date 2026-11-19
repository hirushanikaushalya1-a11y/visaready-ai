"""Background worker: processes queued jobs and runs periodic maintenance.

    python -m app.services.jobs.worker
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import timedelta

from sqlalchemy import text

from app.core.database import SessionLocal, utcnow
from app.services.jobs import tasks  # noqa: F401  (register handlers)
from app.services.jobs.queue import claim_next, enqueue, run_job, worker_id

log = logging.getLogger("visaready.worker")
PERIODIC = {"writing_sla_sweep": 60, "retention_purge": 3600}
_running = True


def _stop(*_):
    global _running
    _running = False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    run_loop()


def start_embedded() -> None:
    """Run the worker loop in a daemon thread inside the API process (single-service hosting)."""
    import threading

    threading.Thread(target=run_loop, name="visaready-worker", daemon=True).start()


def run_loop() -> None:
    wid = worker_id()
    last_run = {k: 0.0 for k in PERIODIC}
    log.info("worker %s started", wid)
    while _running:
        now = time.time()
        db = SessionLocal()
        try:
            # Recover jobs from crashed workers.
            db.execute(text("UPDATE jobs SET status='queued' WHERE status='running' AND locked_at < :t"),
                       {"t": utcnow() - timedelta(minutes=15)})
            for kind, every in PERIODIC.items():
                if now - last_run[kind] >= every:
                    enqueue(db, kind, {}, dedupe=True)
                    last_run[kind] = now
            db.commit()
        finally:
            db.close()
        try:
            job_id = claim_next(wid)
            if job_id:
                run_job(job_id)
            else:
                time.sleep(1.0)
        except Exception:  # noqa: BLE001 - keep the loop alive (e.g. DB briefly unavailable)
            log.exception("worker loop error")
            time.sleep(5.0)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
