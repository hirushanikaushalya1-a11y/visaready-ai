"""Notifications, privacy controls, data export, deletion requests, support tickets."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.database import get_db, utcnow
from app.core.deps import get_current_user, owned_application
from app.models.applications import Application, Document
from app.models.platform import DataDeletionRequest, Notification, SupportTicket
from app.models.users import ConsentRecord, User
from app.services.privacy import retention_days

router = APIRouter(tags=["account"])


@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(100)).all()
    return {"unread": sum(1 for n in rows if not n.read_at),
            "items": [{"id": str(n.id), "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": bool(n.read_at),
                       "email_status": n.email_status, "created_at": n.created_at.isoformat()} for n in rows]}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=utcnow()))
    db.commit()
    return {"ok": True}


class PrivacyIn(BaseModel):
    ai_training_consent: bool | None = None
    marketing_consent: bool | None = None


@router.get("/privacy")
def privacy(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reqs = db.scalars(select(DataDeletionRequest).where(DataDeletionRequest.user_id == user.id).order_by(DataDeletionRequest.created_at.desc())).all()
    return {
        "ai_training_consent": user.ai_training_consent, "marketing_consent": user.marketing_consent,
        "retention_days_after_completion": retention_days(db),
        "processors": [
            {"name": "Hosting & database provider", "purpose": "Stores your account and encrypted documents"},
            {"name": "Payment provider (e.g. PayHere)", "purpose": "Processes payments; we never see or store card numbers"},
            {"name": "AI provider (only if enabled)", "purpose": "Extracts data from documents under a no-training contract; your documents are not used to train models without your explicit consent"},
            {"name": "Email provider", "purpose": "Sends transactional emails"},
        ],
        "deletion_requests": [{"id": str(r.id), "scope": r.scope, "status": r.status, "created_at": r.created_at.isoformat(),
                               "completed_at": r.completed_at.isoformat() if r.completed_at else None} for r in reqs],
    }


@router.put("/privacy")
def update_privacy(body: PrivacyIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = utcnow()
    for field, ctype in (("ai_training_consent", "ai_training"), ("marketing_consent", "marketing")):
        val = getattr(body, field)
        if val is not None and val != getattr(user, field):
            setattr(user, field, val)
            db.add(ConsentRecord(user_id=user.id, consent_type=ctype, granted=val, policy_version="2026-11-draft", created_at=now))
    audit(db, "privacy.consent_updated", actor=user, request=request, **body.model_dump(exclude_none=True))
    db.commit()
    return {"ai_training_consent": user.ai_training_consent, "marketing_consent": user.marketing_consent}


class DeletionIn(BaseModel):
    scope: str = Field(pattern="^(account|application)$")
    application_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=1000)


@router.post("/privacy/deletion-requests", status_code=201)
def request_deletion(body: DeletionIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.scope == "application":
        if not body.application_id:
            raise HTTPException(422, "application_id required")
        owned_application(db, user, body.application_id)
    r = DataDeletionRequest(user_id=user.id, scope=body.scope, application_id=body.application_id, reason=body.reason)
    db.add(r)
    audit(db, "privacy.deletion_requested", actor=user, target_type="deletion_request", request=request, scope=body.scope)
    db.commit()
    return {"id": str(r.id), "status": r.status,
            "message": "Your request has been recorded. We will process it promptly and confirm by email. Payment records may be retained where the law requires."}


@router.get("/privacy/export")
def export_data(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Machine-readable copy of personal data (documents themselves are downloadable individually)."""
    from app.api.applications import app_out
    from app.api.profile import _get_profile, profile_out

    apps = db.scalars(select(Application).where(Application.user_id == user.id, Application.deleted_at.is_(None))).all()
    docs = db.scalars(select(Document).join(Application).where(Application.user_id == user.id, Document.deleted_at.is_(None))).all()
    audit(db, "privacy.export", actor=user, request=request)
    db.commit()
    return {"account": {"email": user.email, "full_name": user.full_name, "created_at": user.created_at.isoformat()},
            "profile": profile_out(_get_profile(db, user)), "applications": [app_out(db, a, full=True) for a in apps],
            "documents": [{"id": str(d.id), "filename": d.original_filename, "uploaded": d.created_at.isoformat(),
                           "fields": [{"name": f.field_name, "value": f.value, "page": f.page_number} for f in d.fields]} for d in docs]}


class TicketIn(BaseModel):
    subject: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=5, max_length=5000)


@router.post("/support/tickets", status_code=201)
def create_ticket(body: TicketIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = SupportTicket(user_id=user.id, subject=body.subject, body=body.body)
    db.add(t)
    db.commit()
    return {"id": str(t.id), "status": t.status}


@router.get("/support/tickets")
def my_tickets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [{"id": str(t.id), "subject": t.subject, "status": t.status, "created_at": t.created_at.isoformat()}
            for t in db.scalars(select(SupportTicket).where(SupportTicket.user_id == user.id).order_by(SupportTicket.created_at.desc())).all()]
