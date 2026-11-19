"""Durable Postgres-backed job queue (SELECT ... FOR UPDATE SKIP LOCKED).

Run the worker with:  python -m app.services.jobs.worker
In tests and in JOBS_INLINE=1 mode jobs execute synchronously at enqueue time.
"""
from __future__ import annotations

import logging
import os
import socket
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, utcnow
from app.models.platform import Job

log = logging.getLogger("visaready.jobs")
HANDLERS: dict[str, Callable[[Session, dict], None]] = {}


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn
    return deco


def inline_mode() -> bool:
    return os.environ.get("JOBS_INLINE") == "1"


def enqueue(db: Session, kind: str, payload: dict, run_at: datetime | None = None, *, dedupe: bool = False) -> Job | None:
    if dedupe:
        existing = db.scalars(select(Job).where(Job.kind == kind, Job.status == "queued", Job.payload == payload)).first()
        if existing:
            return existing
    job = Job(kind=kind, payload=payload, run_at=run_at or utcnow(), created_at=utcnow())
    db.add(job)
    db.flush()
    if inline_mode() and run_at is None:
        db.commit()
        run_job(job.id)
    return job


def run_job(job_id: uuid.UUID) -> None:
    from app.services.jobs import tasks  # noqa: F401  (registers handlers)

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job or job.status not in ("queued", "running"):
            return
        job.status, job.attempts, job.locked_at = "running", job.attempts + 1, job.locked_at or utcnow()
        db.commit()
        try:
            HANDLERS[job.kind](db, job.payload)
            job = db.get(Job, job_id)
            job.status, job.finished_at = "done", utcnow()
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            job = db.get(Job, job_id)
            job.last_error = str(exc)[:2000]
            if job.attempts >= job.max_attempts:
                job.status = "failed"
            else:
                job.status = "queued"
                job.run_at = utcnow() + timedelta(seconds=30 * 2 ** job.attempts)
            log.warning("job %s (%s) failed: %s", job.id, job.kind, exc)
        db.commit()
    finally:
        db.close()


def claim_next(worker_id: str) -> uuid.UUID | None:
    db = SessionLocal()
    try:
        row = db.execute(text(
            "UPDATE jobs SET status='running', locked_at=now(), locked_by=:w "
            "WHERE id = (SELECT id FROM jobs WHERE status='queued' AND run_at <= now() "
            "ORDER BY run_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING id"), {"w": worker_id}).first()
        db.commit()
        return row[0] if row else None
    finally:
        db.close()


def worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"
