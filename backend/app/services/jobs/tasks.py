"""Job handlers."""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.models.applications import Application, Assessment
from app.services.documents.processor import process_document
from app.services.evidence.engine import run_assessment
from app.services.jobs.queue import handler
from app.services.notifications.service import notify


@handler("process_document")
def _process_document(db: Session, payload: dict) -> None:
    process_document(db, uuid.UUID(payload["document_id"]))


@handler("run_assessment")
def _run_assessment(db: Session, payload: dict) -> None:
    a = db.get(Assessment, uuid.UUID(payload["assessment_id"]))
    a.status = "running"
    db.commit()
    try:
        a = run_assessment(db, a.application_id, a.triggered_by_id, assessment_id=a.id)
        db.commit()
        # Claude reads every document and writes the case review (optional; reused if nothing changed).
        from app.services.ai.claude_review import attach_review

        attach_review(db, a)
        db.commit()
        app = db.get(Application, a.application_id)
        notify(db, app.user_id, "assessment_complete", f"Assessment v{a.version} is ready",
               f"Your readiness report for '{app.title}' is ready. Readiness score: {a.readiness_score}/100 "
               "(preparation quality — not a probability of approval).",
               link=f"/applications/{app.id}")
        db.commit()
    except Exception as exc:
        db.rollback()
        a = db.get(Assessment, uuid.UUID(payload["assessment_id"]))
        a.status, a.error = "failed", "The assessment could not be completed. Our team has been notified."
        db.commit()
        raise exc


@handler("writing_sla_sweep")
def _writing_sla_sweep(db: Session, payload: dict) -> None:
    from app.services.orders.writing import sla_sweep

    sla_sweep(db)
    db.commit()


@handler("retention_purge")
def _retention_purge(db: Session, payload: dict) -> None:
    from app.services.privacy import purge_expired_applications

    purge_expired_applications(db)
    db.commit()
