"""Retention and deletion workflows."""
from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import utcnow
from app.models.applications import Application, Document
from app.models.commerce import Deliverable, WritingOrder
from app.models.platform import SystemSetting
from app.models.users import ApplicantProfile, User, UserSession
from app.services.storage.backend import storage


def retention_days(db: Session) -> int:
    row = db.get(SystemSetting, "retention_days_after_completion")
    return int(row.value.get("days")) if row else get_settings().retention_days_after_completion


def purge_document_blob(db: Session, doc: Document) -> None:
    try:
        storage().delete(doc.storage_key)
    except FileNotFoundError:
        pass
    doc.pages.clear()
    doc.fields.clear()
    doc.status = "deleted"
    doc.deleted_at = utcnow()
    doc.wrapped_key = b""  # destroys the data key: ciphertext is unrecoverable even from backups


def purge_application_documents(db: Session, app: Application) -> int:
    docs = db.scalars(select(Document).where(Document.application_id == app.id, Document.deleted_at.is_(None))).all()
    for d in docs:
        purge_document_blob(db, d)
    return len(docs)


def complete_application(db: Session, app: Application) -> None:
    app.status = "completed"
    app.completed_at = utcnow()
    app.retention_delete_after = app.completed_at + timedelta(days=retention_days(db))


def purge_expired_applications(db: Session) -> int:
    now = utcnow()
    apps = db.scalars(select(Application).where(Application.retention_delete_after.is_not(None),
                                                Application.retention_delete_after < now, Application.deleted_at.is_(None))).all()
    n = 0
    for a in apps:
        n += purge_application_documents(db, a)
        a.status = "archived"
        audit(db, "retention.purged_documents", target_type="application", target_id=a.id, documents=n)
    return n


def delete_application(db: Session, app: Application, actor: User | None) -> dict:
    n = purge_application_documents(db, app)
    app.deleted_at = utcnow()
    app.details = {}
    app.title = "Deleted application"
    audit(db, "privacy.application_deleted", actor=actor, target_type="application", target_id=app.id, documents=n)
    return {"documents_purged": n}


def delete_account(db: Session, user: User, actor: User | None) -> dict:
    """Erases personal data. Payment records are retained (anonymised link) because financial records
    are generally subject to statutory retention; this is disclosed in the Privacy Policy."""
    apps = db.scalars(select(Application).where(Application.user_id == user.id, Application.deleted_at.is_(None))).all()
    docs = 0
    for a in apps:
        docs += delete_application(db, a, actor)["documents_purged"]
    orders = db.scalars(select(WritingOrder).where(WritingOrder.user_id == user.id)).all()
    for o in orders:
        for d in db.scalars(select(Deliverable).where(Deliverable.order_type == "writing", Deliverable.order_id == o.id)).all():
            try:
                storage().delete(d.storage_key)
            except FileNotFoundError:
                pass
            d.wrapped_key = b""
        o.customer_notes = None
        o.missing_information_note = None
    profile = db.scalars(select(ApplicantProfile).where(ApplicantProfile.user_id == user.id)).first()
    if profile:
        db.delete(profile)
    for s in db.scalars(select(UserSession).where(UserSession.user_id == user.id)).all():
        s.revoked_at = utcnow()
    anon = uuid.uuid4().hex[:12]
    user.email = f"deleted-{anon}@deleted.invalid"
    user.full_name = "Deleted user"
    user.password_hash = "!"
    user.is_active = False
    user.mfa_enabled = False
    user.mfa_secret_enc = user.mfa_secret_key = None
    user.deleted_at = utcnow()
    audit(db, "privacy.account_deleted", actor=actor, target_type="user", target_id=user.id, applications=len(apps), documents=docs)
    return {"applications": len(apps), "documents_purged": docs}
