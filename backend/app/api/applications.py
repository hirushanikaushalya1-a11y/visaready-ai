from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, owned_application
from app.models.applications import Application, Assessment, ChecklistItemState, Document, FamilyMember
from app.models.commerce import Payment
from app.models.knowledge import Country, VisaCategory
from app.models.users import User
from app.schemas.profile import DETAILS_SCHEMA
from app.services.privacy import complete_application
from app.services.report_access import report_unlocked

router = APIRouter(prefix="/applications", tags=["applications"])


class ApplicationIn(BaseModel):
    country_code: str = Field(min_length=2, max_length=2)
    visa_category_id: uuid.UUID
    title: str | None = Field(default=None, max_length=200)
    details: dict = Field(default_factory=dict)


class ApplicationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    details: dict | None = None


class FamilyMemberIn(BaseModel):
    relation: str = Field(pattern=r"^(spouse|partner|child|parent|other)$")
    full_name: str = Field(min_length=2, max_length=200)
    date_of_birth: date | None = None
    included_in_application: bool = True


class ChecklistStateIn(BaseModel):
    collected: bool | None = None
    note: str | None = Field(default=None, max_length=1000)


def _validate_details(category_type: str, details: dict) -> dict:
    try:
        return DETAILS_SCHEMA[category_type](**details).model_dump(mode="json", exclude_none=True)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False))


def app_out(db: Session, a: Application, full: bool = False) -> dict:
    latest = db.scalars(select(Assessment).where(Assessment.application_id == a.id, Assessment.is_simulation.is_(False))
                        .order_by(Assessment.version.desc()).limit(1)).first()
    s = get_settings()
    out = {
        "id": str(a.id), "title": a.title, "status": a.status, "country_code": a.country_code, "country_name": a.country.name,
        "country_module_status": a.country.module_status,
        "visa_category": {"id": str(a.visa_category.id), "name": a.visa_category.name, "category_type": a.visa_category.category_type,
                          "official_url": a.visa_category.official_url},
        "details": a.details, "created_at": a.created_at.isoformat(), "unlocked_at": a.unlocked_at.isoformat() if a.unlocked_at else None,
        "reassessments": {"included": a.reassessments_allowed, "assessments_run": a.assessments_run,
                          "remaining": max(0, a.reassessments_allowed + 1 - a.assessments_run) if a.status != "draft" else 0},
        "latest_assessment": {"id": str(latest.id), "version": latest.version, "status": latest.status, "score": latest.readiness_score,
                              "created_at": latest.created_at.isoformat()} if latest else None,
        "document_count": db.scalar(select(func.count()).select_from(Document).where(Document.application_id == a.id, Document.deleted_at.is_(None), Document.is_current.is_(True))),
        "limits": {"max_documents": s.max_documents_per_application, "max_file_size_mb": s.max_file_size_mb},
        "retention_delete_after": a.retention_delete_after.isoformat() if a.retention_delete_after else None,
        "report_unlocked": report_unlocked(db, a.id),
    }
    if full:
        out["family_members"] = [{"id": str(m.id), "relation": m.relation, "full_name": m.full_name,
                                  "date_of_birth": m.date_of_birth.isoformat() if m.date_of_birth else None,
                                  "included_in_application": m.included_in_application} for m in a.family_members]
        out["checklist_state"] = {s.item_key: {"collected": s.collected, "note": s.note} for s in
                                  db.scalars(select(ChecklistItemState).where(ChecklistItemState.application_id == a.id)).all()}
        out["payment"] = next(({"id": str(p.id), "status": p.status} for p in db.scalars(
            select(Payment).where(Payment.purpose == "assessment_report", Payment.reference_id == a.id).order_by(Payment.created_at.desc())).all()), None)
    return out


@router.get("")
def list_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    apps = db.scalars(select(Application).where(Application.user_id == user.id, Application.deleted_at.is_(None))
                      .order_by(Application.created_at.desc())).all()
    return [app_out(db, a) for a in apps]


@router.post("", status_code=201)
def create_application(body: ApplicationIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    country = db.get(Country, body.country_code.upper())
    cat = db.get(VisaCategory, body.visa_category_id)
    if not country or not country.is_destination or not cat or cat.country_code != country.code or not cat.is_active:
        raise HTTPException(422, "Choose a supported destination and visa category.")
    open_count = db.scalar(select(func.count()).select_from(Application).where(
        Application.user_id == user.id, Application.deleted_at.is_(None), Application.status == "active"))
    if open_count >= 10:
        raise HTTPException(429, "You can have up to 10 open applications. Mark one as submitted or delete one first.")
    from app.core.database import utcnow

    # The file-strength assessment is free: applications are active immediately.
    a = Application(user_id=user.id, country_code=country.code, visa_category_id=cat.id,
                    title=body.title or f"{cat.name} – {country.name}", details=_validate_details(cat.category_type, body.details),
                    status="active", unlocked_at=utcnow(), reassessments_allowed=get_settings().included_reassessments)
    db.add(a)
    db.flush()
    audit(db, "application.created", actor=user, target_type="application", target_id=a.id, request=request)
    db.commit()
    db.refresh(a)
    return app_out(db, a, full=True)


@router.get("/{application_id}")
def get_application(application_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return app_out(db, owned_application(db, user, application_id), full=True)


@router.patch("/{application_id}")
def update_application(application_id: uuid.UUID, body: ApplicationUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = owned_application(db, user, application_id)
    if body.title:
        a.title = body.title
    if body.details is not None:
        a.details = _validate_details(a.visa_category.category_type, {**(a.details or {}), **body.details})
    db.commit()
    return app_out(db, a, full=True)


@router.post("/{application_id}/complete")
def mark_complete(application_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = owned_application(db, user, application_id)
    if a.status != "active":
        raise HTTPException(409, "Only active applications can be marked complete.")
    complete_application(db, a)
    audit(db, "application.completed", actor=user, target_type="application", target_id=a.id, request=request)
    db.commit()
    return app_out(db, a, full=True)


@router.post("/{application_id}/family-members", status_code=201)
def add_family_member(application_id: uuid.UUID, body: FamilyMemberIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = owned_application(db, user, application_id)
    if len(a.family_members) >= 12:
        raise HTTPException(422, "Too many family members on one application.")
    a.family_members.append(FamilyMember(**body.model_dump()))
    db.commit()
    return app_out(db, a, full=True)


@router.delete("/{application_id}/family-members/{member_id}")
def remove_family_member(application_id: uuid.UUID, member_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = owned_application(db, user, application_id)
    m = next((m for m in a.family_members if m.id == member_id), None)
    if not m:
        raise HTTPException(404, "Family member not found")
    a.family_members.remove(m)
    db.commit()
    return app_out(db, a, full=True)


@router.put("/{application_id}/checklist/{item_key}")
def set_checklist_state(application_id: uuid.UUID, item_key: str, body: ChecklistStateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = owned_application(db, user, application_id)
    if len(item_key) > 200:
        raise HTTPException(422, "Invalid item")
    st = db.scalars(select(ChecklistItemState).where(ChecklistItemState.application_id == a.id, ChecklistItemState.item_key == item_key)).first()
    if not st:
        st = ChecklistItemState(application_id=a.id, item_key=item_key)
        db.add(st)
    if body.collected is not None:
        st.collected = body.collected
    if body.note is not None:
        st.note = body.note
    db.commit()
    return {"item_key": item_key, "collected": st.collected, "note": st.note}
