"""Administration API. Every endpoint is permission-gated (RBAC) and state changes are audit-logged."""
from __future__ import annotations

import hashlib
import uuid
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.database import get_db, utcnow
from app.core.deps import require_permission
from app.models.applications import Application, Assessment, Document
from app.models.commerce import Deliverable, Payment, Refund, WritingOrder
from app.models.enums import ROLES
from app.models.knowledge import (
    Country,
    EvidenceRule,
    ImmigrationRequirement,
    OfficialSource,
    PolicyAlert,
    RequirementVersion,
    VisaCategory,
)
from app.models.platform import AuditLog, DataDeletionRequest, Job, SupportTicket, SystemSetting
from app.models.users import User
from app.services.documents.text import sniff_content_type
from app.services.evidence.conditions import ConditionError, validate
from app.services.knowledge.requirements import requirement_snapshot, update_requirement, verify_requirement
from app.services.notifications.service import notify
from app.services.orders import writing as W
from app.services.payments.providers import fmt_amount
from app.services.payments.service import process_refund
from app.services.privacy import delete_account, delete_application
from app.services.storage.backend import load_decrypted, store_encrypted

router = APIRouter(prefix="/admin", tags=["admin"])


# ------------------------------------------------------------------ overview / analytics
@router.get("/overview")
def overview(user: User = Depends(require_permission("admin.access")), db: Session = Depends(get_db)):
    now = utcnow()
    c = lambda q: db.scalar(q) or 0  # noqa: E731
    return {
        "users": c(select(func.count()).select_from(User).where(User.role == "applicant", User.deleted_at.is_(None))),
        "applications": {s: c(select(func.count()).select_from(Application).where(Application.status == s, Application.deleted_at.is_(None)))
                         for s in ("draft", "active", "completed", "archived")},
        "assessments_7d": c(select(func.count()).select_from(Assessment).where(Assessment.created_at > now - timedelta(days=7), Assessment.is_simulation.is_(False))),
        "documents": {s: c(select(func.count()).select_from(Document).where(Document.status == s)) for s in ("uploaded", "processing", "processed", "failed")},
        "writing_orders_open": c(select(func.count()).select_from(WritingOrder).where(WritingOrder.status.in_(("awaiting_documents", "information_incomplete") + W.CLOCK_RUNNING))),
        "writing_orders_due_6h": c(select(func.count()).select_from(WritingOrder).where(WritingOrder.status.in_(W.CLOCK_RUNNING), WritingOrder.deadline_at < now + timedelta(hours=6))),
        "refund_eligible": c(select(func.count()).select_from(WritingOrder).where(WritingOrder.status == "refund_eligible")),
        "revenue_30d_cents": c(select(func.sum(Payment.amount_cents - Payment.refunded_cents)).where(Payment.status.in_(("succeeded", "partially_refunded")), Payment.paid_at > now - timedelta(days=30), Payment.provider != "sandbox")),
        "sandbox_payments_30d": c(select(func.count()).select_from(Payment).where(Payment.provider == "sandbox", Payment.status == "succeeded", Payment.paid_at > now - timedelta(days=30))),
        "deletion_requests_open": c(select(func.count()).select_from(DataDeletionRequest).where(DataDeletionRequest.status == "requested")),
        "requirements_pending_review": c(select(func.count()).select_from(ImmigrationRequirement).where(ImmigrationRequirement.review_status == "pending_review")),
        "jobs": {s: c(select(func.count()).select_from(Job).where(Job.status == s)) for s in ("queued", "running", "failed")},
        "support_open": c(select(func.count()).select_from(SupportTicket).where(SupportTicket.status.in_(("open", "pending")))),
    }


# ------------------------------------------------------------------ users
class UserPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.get("/users")
def users(q: str | None = None, user: User = Depends(require_permission("users.read")), db: Session = Depends(get_db)):
    stmt = select(User).where(User.deleted_at.is_(None))
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))
    return [{"id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active,
             "mfa_enabled": u.mfa_enabled, "created_at": u.created_at.isoformat(), "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}
            for u in db.scalars(stmt.order_by(User.created_at.desc()).limit(200)).all()]


@router.patch("/users/{user_id}")
def patch_user(user_id: uuid.UUID, body: UserPatch, request: Request, actor: User = Depends(require_permission("users.manage")), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.deleted_at:
        raise HTTPException(404, "User not found")
    if u.id == actor.id:
        raise HTTPException(400, "You cannot change your own role or status.")
    if body.role:
        if body.role not in ROLES:
            raise HTTPException(422, "Unknown role")
        if (body.role == "super_admin" or u.role == "super_admin") and actor.role != "super_admin":
            raise HTTPException(403, "Only a Super Admin can grant or remove Super Admin.")
        audit(db, "admin.role_changed", actor=actor, target_type="user", target_id=u.id, request=request, old=u.role, new=body.role)
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
        audit(db, "admin.user_status", actor=actor, target_type="user", target_id=u.id, request=request, active=body.is_active)
    db.commit()
    return {"id": str(u.id), "role": u.role, "is_active": u.is_active}


# ------------------------------------------------------------------ applications (metadata only)
@router.get("/applications")
def applications(user: User = Depends(require_permission("applications.read_all")), db: Session = Depends(get_db)):
    rows = db.execute(select(Application, User.email).join(User, User.id == Application.user_id).where(Application.deleted_at.is_(None))
                      .order_by(Application.created_at.desc()).limit(200)).all()
    return [{"id": str(a.id), "title": a.title, "status": a.status, "country_code": a.country_code, "user_email": email,
             "created_at": a.created_at.isoformat(), "assessments_run": a.assessments_run} for a, email in rows]


@router.get("/documents/{document_id}/download")
def staff_download(document_id: uuid.UUID, request: Request, actor: User = Depends(require_permission("documents.read_all")), db: Session = Depends(get_db)):
    d = db.get(Document, document_id)
    if not d or d.deleted_at:
        raise HTTPException(404, "Not found")
    audit(db, "staff.document_accessed", actor=actor, target_type="document", target_id=d.id, request=request)
    db.commit()
    return Response(load_decrypted(d.storage_key, d.wrapped_key), media_type=d.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{d.original_filename}"', "Cache-Control": "no-store"})


# ------------------------------------------------------------------ knowledge management
class RequirementIn(BaseModel):
    visa_category_id: uuid.UUID
    key: str = Field(pattern=r"^[a-z0-9\-]{2,120}$")
    title: str = Field(max_length=300)
    description: str
    requirement_level: str = Field(pattern="^(mandatory|conditional|supplementary)$")
    source_url: str = Field(pattern=r"^https://")
    document_types: list[str] = Field(default_factory=list)
    applies_when: dict | None = None
    eligibility_conditions: str | None = None
    financial_requirement: dict | None = None
    exceptions: str | None = None
    effective_date: date | None = None
    translation_required_if_not_english: bool = False


class RequirementPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    requirement_level: str | None = Field(default=None, pattern="^(mandatory|conditional|supplementary)$")
    source_url: str | None = Field(default=None, pattern=r"^https://")
    document_types: list[str] | None = None
    applies_when: dict | None = None
    eligibility_conditions: str | None = None
    financial_requirement: dict | None = None
    exceptions: str | None = None
    effective_date: date | None = None
    change_note: str = Field(min_length=3, max_length=1000)


class VerifyIn(BaseModel):
    source_excerpt: str | None = Field(default=None, max_length=4000)
    confirm_checked_official_source: bool


@router.get("/knowledge/categories")
def admin_categories(country: str | None = None, user: User = Depends(require_permission("knowledge.read")), db: Session = Depends(get_db)):
    q = select(VisaCategory)
    if country:
        q = q.where(VisaCategory.country_code == country.upper())
    out = []
    for c in db.scalars(q.order_by(VisaCategory.country_code, VisaCategory.category_type)).all():
        reqs = db.scalars(select(ImmigrationRequirement).where(ImmigrationRequirement.visa_category_id == c.id)).all()
        out.append({"id": str(c.id), "country_code": c.country_code, "name": c.name, "category_type": c.category_type, "official_url": c.official_url,
                    "requirements": len(reqs), "verified": sum(r.review_status == "verified" for r in reqs), "is_active": c.is_active})
    return out


@router.get("/knowledge/requirements")
def admin_requirements(category_id: uuid.UUID, user: User = Depends(require_permission("knowledge.read")), db: Session = Depends(get_db)):
    from app.api.knowledge import req_out

    return [req_out(r) for r in db.scalars(select(ImmigrationRequirement).where(ImmigrationRequirement.visa_category_id == category_id)
                                           .order_by(ImmigrationRequirement.sort_order)).all()]


@router.post("/knowledge/requirements", status_code=201)
def create_requirement(body: RequirementIn, request: Request, actor: User = Depends(require_permission("knowledge.manage")), db: Session = Depends(get_db)):
    try:
        validate(body.applies_when)
    except ConditionError as e:
        raise HTTPException(422, f"Invalid condition: {e}")
    if not db.get(VisaCategory, body.visa_category_id):
        raise HTTPException(404, "Category not found")
    r = ImmigrationRequirement(**body.model_dump(), review_status="pending_review", version=1)
    db.add(r)
    db.flush()
    db.add(RequirementVersion(requirement_id=r.id, version=1, snapshot=requirement_snapshot(r), change_note="Created", changed_by_id=actor.id, created_at=utcnow()))
    audit(db, "knowledge.requirement_created", actor=actor, target_type="requirement", target_id=r.id, request=request)
    db.commit()
    return {"id": str(r.id)}


@router.patch("/knowledge/requirements/{req_id}")
def patch_requirement(req_id: uuid.UUID, body: RequirementPatch, request: Request, actor: User = Depends(require_permission("knowledge.manage")), db: Session = Depends(get_db)):
    r = db.get(ImmigrationRequirement, req_id)
    if not r:
        raise HTTPException(404, "Not found")
    changes = body.model_dump(exclude_unset=True)
    note = changes.pop("change_note")
    if "applies_when" in changes:
        try:
            validate(changes["applies_when"])
        except ConditionError as e:
            raise HTTPException(422, f"Invalid condition: {e}")
    update_requirement(db, r, changes, actor.id, note)
    audit(db, "knowledge.requirement_updated", actor=actor, target_type="requirement", target_id=r.id, request=request, version=r.version)
    db.commit()
    return {"id": str(r.id), "version": r.version, "review_status": r.review_status}


@router.post("/knowledge/requirements/{req_id}/verify")
def verify(req_id: uuid.UUID, body: VerifyIn, request: Request, actor: User = Depends(require_permission("knowledge.verify")), db: Session = Depends(get_db)):
    if not body.confirm_checked_official_source:
        raise HTTPException(422, "You must confirm you checked the official source.")
    r = db.get(ImmigrationRequirement, req_id)
    if not r:
        raise HTTPException(404, "Not found")
    verify_requirement(db, r, actor.id, body.source_excerpt)
    audit(db, "knowledge.requirement_verified", actor=actor, target_type="requirement", target_id=r.id, request=request, version=r.version)
    db.commit()
    return {"id": str(r.id), "review_status": r.review_status, "last_verified_at": r.last_verified_at.isoformat()}


@router.post("/knowledge/requirements/{req_id}/retire")
def retire(req_id: uuid.UUID, request: Request, actor: User = Depends(require_permission("knowledge.manage")), db: Session = Depends(get_db)):
    r = db.get(ImmigrationRequirement, req_id)
    if not r:
        raise HTTPException(404, "Not found")
    r.review_status = "retired"
    audit(db, "knowledge.requirement_retired", actor=actor, target_type="requirement", target_id=r.id, request=request)
    db.commit()
    return {"ok": True}


@router.get("/knowledge/requirements/{req_id}/versions")
def versions(req_id: uuid.UUID, user: User = Depends(require_permission("knowledge.read")), db: Session = Depends(get_db)):
    return [{"version": v.version, "snapshot": v.snapshot, "change_note": v.change_note, "changed_by": str(v.changed_by_id) if v.changed_by_id else None,
             "created_at": v.created_at.isoformat()}
            for v in db.scalars(select(RequirementVersion).where(RequirementVersion.requirement_id == req_id).order_by(RequirementVersion.created_at)).all()]


class CountryPatch(BaseModel):
    module_status: str | None = Field(default=None, pattern="^(live|pilot|planned)$")
    is_destination: bool | None = None


@router.patch("/knowledge/countries/{code}")
def patch_country(code: str, body: CountryPatch, request: Request, actor: User = Depends(require_permission("knowledge.manage")), db: Session = Depends(get_db)):
    c = db.get(Country, code.upper())
    if not c:
        raise HTTPException(404, "Not found")
    if body.module_status == "live":
        unverified = db.scalar(select(func.count()).select_from(ImmigrationRequirement).join(VisaCategory).where(
            VisaCategory.country_code == c.code, ImmigrationRequirement.review_status == "pending_review"))
        if unverified:
            raise HTTPException(409, f"{unverified} requirement(s) for {c.name} are still pending verification.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    audit(db, "knowledge.country_updated", actor=actor, target_type="country", target_id=c.code, request=request, **body.model_dump(exclude_none=True))
    db.commit()
    return {"code": c.code, "module_status": c.module_status, "is_destination": c.is_destination}


class CategoryIn(BaseModel):
    country_code: str = Field(min_length=2, max_length=2)
    category_type: str = Field(pattern="^(student|work|family)$")
    code: str = Field(pattern=r"^[a-z0-9\-]{2,80}$")
    name: str = Field(max_length=200)
    description: str | None = None
    official_url: str = Field(pattern=r"^https://")


@router.post("/knowledge/categories", status_code=201)
def create_category(body: CategoryIn, request: Request, actor: User = Depends(require_permission("knowledge.manage")), db: Session = Depends(get_db)):
    if not db.get(Country, body.country_code.upper()):
        raise HTTPException(404, "Country not found")
    c = VisaCategory(**{**body.model_dump(), "country_code": body.country_code.upper()})
    db.add(c)
    audit(db, "knowledge.category_created", actor=actor, target_type="visa_category", request=request, code=body.code)
    db.commit()
    return {"id": str(c.id)}


@router.get("/knowledge/evidence-rules")
def evidence_rules(user: User = Depends(require_permission("knowledge.read")), db: Session = Depends(get_db)):
    return [{"id": str(r.id), "key": r.key, "title": r.title, "level": r.level, "applies_when": r.applies_when, "document_types": r.document_types,
             "category_types": r.category_types, "explanation": r.explanation, "is_active": r.is_active}
            for r in db.scalars(select(EvidenceRule).order_by(EvidenceRule.key)).all()]


@router.get("/knowledge/sources")
def sources(user: User = Depends(require_permission("knowledge.read")), db: Session = Depends(get_db)):
    return [{"id": str(s.id), "country_code": s.country_code, "title": s.title, "url": s.url, "publisher": s.publisher,
             "monitoring_enabled": s.monitoring_enabled, "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
             "last_changed_at": s.last_changed_at.isoformat() if s.last_changed_at else None}
            for s in db.scalars(select(OfficialSource).order_by(OfficialSource.country_code)).all()]


@router.post("/knowledge/sources/{source_id}/check")
def check_source(source_id: uuid.UUID, request: Request, actor: User = Depends(require_permission("knowledge.manage")), db: Session = Depends(get_db)):
    """Policy monitoring: fetch the official page and compare a content hash. A change creates a
    'detected' policy alert that a human must verify before anything changes for applicants."""
    s = db.get(OfficialSource, source_id)
    if not s:
        raise HTTPException(404, "Not found")
    try:
        r = httpx.get(s.url, timeout=20, follow_redirects=True, headers={"User-Agent": "VisaReadyAI-PolicyMonitor/1.0"})
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"Could not fetch the source: {exc}"[:300]}
    import re as _re

    text = _re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>|\s+", " ", r.text, flags=_re.S)
    digest = hashlib.sha256(text.encode()).hexdigest()
    changed = s.last_content_hash is not None and digest != s.last_content_hash
    s.last_checked_at = utcnow()
    if changed:
        s.last_changed_at = utcnow()
        db.add(PolicyAlert(country_code=s.country_code, official_source_id=s.id, title=f"Possible change: {s.title}",
                           summary="The official page content changed since the last check. Review the page and affected requirements.",
                           source_url=s.url, status="detected"))
    s.last_content_hash = digest
    audit(db, "knowledge.source_checked", actor=actor, target_type="official_source", target_id=s.id, request=request, changed=changed)
    db.commit()
    return {"ok": True, "changed": changed, "first_check": not changed and s.last_changed_at is None}


class AlertIn(BaseModel):
    country_code: str
    title: str = Field(max_length=300)
    summary: str
    source_url: str = Field(pattern=r"^https://")
    visa_category_id: uuid.UUID | None = None
    requirement_id: uuid.UUID | None = None
    effective_date: date | None = None


@router.get("/policy-alerts")
def alerts(user: User = Depends(require_permission("knowledge.read")), db: Session = Depends(get_db)):
    return [{"id": str(a.id), "country_code": a.country_code, "title": a.title, "summary": a.summary, "status": a.status, "source_url": a.source_url,
             "effective_date": a.effective_date.isoformat() if a.effective_date else None, "affected": a.affected_application_count,
             "created_at": a.created_at.isoformat()} for a in db.scalars(select(PolicyAlert).order_by(PolicyAlert.created_at.desc())).all()]


@router.post("/policy-alerts", status_code=201)
def create_alert(body: AlertIn, actor: User = Depends(require_permission("knowledge.manage")), db: Session = Depends(get_db)):
    a = PolicyAlert(**body.model_dump(), status="detected")
    db.add(a)
    db.commit()
    return {"id": str(a.id)}


@router.post("/policy-alerts/{alert_id}/publish")
def publish_alert(alert_id: uuid.UUID, request: Request, actor: User = Depends(require_permission("knowledge.verify")), db: Session = Depends(get_db)):
    """Only verified changes reach applicants: publishing records the verifier, then notifies every
    active applicant whose application matches the country (and category, if set)."""
    a = db.get(PolicyAlert, alert_id)
    if not a or a.status == "published":
        raise HTTPException(404, "Alert not found or already published")
    a.status, a.verified_by_id, a.published_at = "published", actor.id, utcnow()
    q = select(Application).where(Application.country_code == a.country_code, Application.status == "active", Application.deleted_at.is_(None))
    if a.visa_category_id:
        q = q.where(Application.visa_category_id == a.visa_category_id)
    apps = db.scalars(q).all()
    for app in apps:
        notify(db, app.user_id, "policy_alert", f"Immigration update: {a.title}",
               f"{a.summary}\n\nOfficial source: {a.source_url}\n\nWe recommend reviewing your checklist and requesting a reassessment.",
               link=f"/applications/{app.id}")
    a.affected_application_count = len(apps)
    audit(db, "knowledge.alert_published", actor=actor, target_type="policy_alert", target_id=a.id, request=request, affected=len(apps))
    db.commit()
    return {"published": True, "notified_applications": len(apps)}


# ------------------------------------------------------------------ writing orders
def _admin_order(db: Session, o: WritingOrder) -> dict:
    from app.api.orders import order_out

    u = db.get(User, o.user_id)
    return {**order_out(db, o, events=True), "customer": {"name": u.full_name, "email": u.email},
            "assigned_to_id": str(o.assigned_to_id) if o.assigned_to_id else None}


@router.get("/writing-orders")
def writing_orders(status: str | None = None, user: User = Depends(require_permission("writing_orders.read")), db: Session = Depends(get_db)):
    q = select(WritingOrder)
    if status:
        q = q.where(WritingOrder.status == status)
    rows = db.scalars(q.order_by(WritingOrder.deadline_at.asc().nulls_last(), WritingOrder.created_at.desc()).limit(300)).all()
    return [_admin_order(db, o) for o in rows]


@router.get("/writing-orders/{order_id}")
def writing_order(order_id: uuid.UUID, user: User = Depends(require_permission("writing_orders.read")), db: Session = Depends(get_db)):
    o = db.get(WritingOrder, order_id)
    if not o:
        raise HTTPException(404, "Not found")
    return _admin_order(db, o)


class OrderAction(BaseModel):
    action: str = Field(pattern="^(incomplete|complete|start|review|rework)$")
    note: str | None = Field(default=None, max_length=2000)


@router.post("/writing-orders/{order_id}/action")
def order_action(order_id: uuid.UUID, body: OrderAction, request: Request, actor: User = Depends(require_permission("writing_orders.manage")), db: Session = Depends(get_db)):
    o = db.scalars(select(WritingOrder).where(WritingOrder.id == order_id).with_for_update()).first()
    if not o:
        raise HTTPException(404, "Not found")
    if body.action == "incomplete":
        if not body.note:
            raise HTTPException(422, "Describe what information is missing.")
        W.mark_incomplete(db, o, actor, body.note)
    elif body.action == "complete":
        W.mark_complete(db, o, actor)
    elif body.action == "start":
        W.start_processing(db, o, actor)
    elif body.action == "review":
        W.send_to_review(db, o, actor)
    elif body.action == "rework":
        W.transition(db, o, "processing", actor, body.note or "Returned from quality review")
    audit(db, f"writing_order.{body.action}", actor=actor, target_type="writing_order", target_id=o.id, request=request)
    db.commit()
    return _admin_order(db, o)


@router.post("/writing-orders/{order_id}/deliver")
def deliver(order_id: uuid.UUID, request: Request, file: UploadFile = File(...), actor: User = Depends(require_permission("writing_orders.manage")), db: Session = Depends(get_db)):
    o = db.scalars(select(WritingOrder).where(WritingOrder.id == order_id).with_for_update()).first()
    if not o:
        raise HTTPException(404, "Not found")
    if o.status not in ("quality_review", "refund_eligible"):
        raise HTTPException(409, "Documents must pass quality review before delivery.")
    data = file.file.read(20 * 1024 * 1024 + 1)
    ctype = sniff_content_type(data)
    if data[:4] == b"PK\x03\x04":
        ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if not ctype or len(data) > 20 * 1024 * 1024:
        raise HTTPException(415, "Upload a PDF or DOCX up to 20 MB.")
    key, wrapped = store_encrypted(f"deliverables/{o.id}", data)
    db.add(Deliverable(order_type="writing", order_id=o.id, filename=(file.filename or "document")[:200], content_type=ctype, size_bytes=len(data),
                       storage_key=key, wrapped_key=wrapped, uploaded_by_id=actor.id, created_at=utcnow()))
    W.deliver(db, o, actor)
    audit(db, "writing_order.delivered", actor=actor, target_type="writing_order", target_id=o.id, request=request)
    db.commit()
    return _admin_order(db, o)


@router.post("/writing-orders/{order_id}/refund")
def refund_order(order_id: uuid.UUID, request: Request, actor: User = Depends(require_permission("refunds.manage")), db: Session = Depends(get_db)):
    o = db.scalars(select(WritingOrder).where(WritingOrder.id == order_id).with_for_update()).first()
    if not o:
        raise HTTPException(404, "Not found")
    W.process_order_refund(db, o, actor)
    db.commit()
    return _admin_order(db, o)


@router.post("/writing-orders/sla-sweep")
def run_sla_sweep(actor: User = Depends(require_permission("writing_orders.manage")), db: Session = Depends(get_db)):
    stats = W.sla_sweep(db)
    db.commit()
    return stats


# ------------------------------------------------------------------ payments & refunds
@router.get("/payments")
def payments(user: User = Depends(require_permission("payments.read")), db: Session = Depends(get_db)):
    from app.api.payments import payment_out

    rows = db.execute(select(Payment, User.email).join(User, User.id == Payment.user_id).order_by(Payment.created_at.desc()).limit(300)).all()
    return [{**payment_out(p), "user_email": email} for p, email in rows]


class RefundIn(BaseModel):
    amount_cents: int | None = Field(default=None, gt=0)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/payments/{payment_id}/refund")
def refund_payment(payment_id: uuid.UUID, body: RefundIn, actor: User = Depends(require_permission("refunds.manage")), db: Session = Depends(get_db)):
    p = db.scalars(select(Payment).where(Payment.id == payment_id).with_for_update()).first()
    if not p:
        raise HTTPException(404, "Not found")
    r = process_refund(db, p, body.amount_cents or (p.amount_cents - p.refunded_cents), body.reason, actor)
    db.commit()
    return {"refund_id": str(r.id), "status": r.status, "failure_reason": r.failure_reason, "amount": fmt_amount(r.amount_cents)}


@router.get("/refunds")
def refunds(user: User = Depends(require_permission("payments.read")), db: Session = Depends(get_db)):
    return [{"id": str(r.id), "payment_id": str(r.payment_id), "amount": fmt_amount(r.amount_cents), "status": r.status, "reason": r.reason,
             "failure_reason": r.failure_reason, "created_at": r.created_at.isoformat()}
            for r in db.scalars(select(Refund).order_by(Refund.created_at.desc()).limit(200)).all()]


# ------------------------------------------------------------------ privacy, retention, audit, support, jobs
@router.get("/deletion-requests")
def deletion_requests(user: User = Depends(require_permission("privacy.manage")), db: Session = Depends(get_db)):
    rows = db.execute(select(DataDeletionRequest, User.email).join(User, User.id == DataDeletionRequest.user_id).order_by(DataDeletionRequest.created_at.desc())).all()
    return [{"id": str(r.id), "user_email": email, "scope": r.scope, "application_id": str(r.application_id) if r.application_id else None,
             "status": r.status, "reason": r.reason, "created_at": r.created_at.isoformat(), "result": r.result} for r, email in rows]


@router.post("/deletion-requests/{request_id}/process")
def process_deletion(request_id: uuid.UUID, request: Request, actor: User = Depends(require_permission("privacy.manage")), db: Session = Depends(get_db)):
    r = db.get(DataDeletionRequest, request_id)
    if not r or r.status != "requested":
        raise HTTPException(404, "Request not found or already processed")
    target = db.get(User, r.user_id)
    if r.scope == "application":
        app = db.get(Application, r.application_id)
        result = delete_application(db, app, actor) if app and not app.deleted_at else {"documents_purged": 0}
        notify(db, target, "privacy", "Your application data was deleted", "The application and its documents have been permanently deleted as you requested.")
    else:
        notify(db, target, "privacy", "Your account deletion is complete", "Your account and documents have been deleted as you requested.")
        result = delete_account(db, target, actor)
    r.status, r.completed_at, r.processed_by_id, r.result = "completed", utcnow(), actor.id, result
    db.commit()
    return {"status": r.status, "result": result}


class RetentionIn(BaseModel):
    days: int = Field(ge=1, le=3650)


@router.get("/settings/retention")
def get_retention(user: User = Depends(require_permission("privacy.manage")), db: Session = Depends(get_db)):
    from app.services.privacy import retention_days

    return {"days": retention_days(db)}


@router.put("/settings/retention")
def set_retention(body: RetentionIn, request: Request, actor: User = Depends(require_permission("privacy.manage")), db: Session = Depends(get_db)):
    row = db.get(SystemSetting, "retention_days_after_completion") or SystemSetting(key="retention_days_after_completion", value={})
    row.value, row.updated_by_id = {"days": body.days}, actor.id
    db.merge(row)
    audit(db, "settings.retention_changed", actor=actor, request=request, days=body.days)
    db.commit()
    return {"days": body.days, "note": "Applies to applications completed from now on. Update the Privacy Policy to match."}


@router.get("/audit-logs")
def audit_logs(action: str | None = None, user: User = Depends(require_permission("audit.read")), db: Session = Depends(get_db)):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action.ilike(f"{action}%"))
    return [{"id": str(a.id), "action": a.action, "actor_id": str(a.actor_id) if a.actor_id else None, "actor_role": a.actor_role,
             "target_type": a.target_type, "target_id": a.target_id, "ip": a.ip_address, "details": a.details, "created_at": a.created_at.isoformat()}
            for a in db.scalars(q.order_by(AuditLog.created_at.desc()).limit(300)).all()]


@router.get("/support-tickets")
def tickets(user: User = Depends(require_permission("support.manage")), db: Session = Depends(get_db)):
    rows = db.execute(select(SupportTicket, User.email).join(User, User.id == SupportTicket.user_id).order_by(SupportTicket.created_at.desc())).all()
    return [{"id": str(t.id), "subject": t.subject, "body": t.body, "status": t.status, "user_email": email, "created_at": t.created_at.isoformat()} for t, email in rows]


class TicketPatch(BaseModel):
    status: str = Field(pattern="^(open|pending|resolved|closed)$")


@router.patch("/support-tickets/{ticket_id}")
def patch_ticket(ticket_id: uuid.UUID, body: TicketPatch, actor: User = Depends(require_permission("support.manage")), db: Session = Depends(get_db)):
    t = db.get(SupportTicket, ticket_id)
    if not t:
        raise HTTPException(404, "Not found")
    t.status, t.assigned_to_id = body.status, actor.id
    db.commit()
    return {"id": str(t.id), "status": t.status}


@router.get("/jobs")
def jobs(user: User = Depends(require_permission("analytics.read")), db: Session = Depends(get_db)):
    return [{"id": str(j.id), "kind": j.kind, "status": j.status, "attempts": j.attempts, "last_error": j.last_error,
             "created_at": j.created_at.isoformat(), "finished_at": j.finished_at.isoformat() if j.finished_at else None}
            for j in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)).all()]
