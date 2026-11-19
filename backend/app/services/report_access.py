"""Paid assessment report access (EUR 35 per application)."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commerce import Payment


def report_unlocked(db: Session, application_id: uuid.UUID) -> bool:
    return db.scalar(select(Payment.id).where(Payment.purpose == "assessment_report", Payment.reference_id == application_id,
                                              Payment.status.in_(("succeeded", "partially_refunded")))) is not None


def require_report(db: Session, application_id: uuid.UUID) -> None:
    if not report_unlocked(db, application_id):
        raise HTTPException(402, "This is part of the full assessment report. Unlock it for this application to continue.")
