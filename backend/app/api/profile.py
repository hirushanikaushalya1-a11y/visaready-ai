from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.users import ApplicantProfile, User
from app.schemas.profile import ProfileIn
from app.services.evidence.profile_analysis import PROFILE_FIELDS

router = APIRouter(prefix="/profile", tags=["profile"])
SECTIONS = ("academic", "employment", "financial", "immigration_history")


def _get_profile(db: Session, user: User) -> ApplicantProfile:
    p = db.scalars(select(ApplicantProfile).where(ApplicantProfile.user_id == user.id)).first()
    if not p:
        p = ApplicantProfile(user_id=user.id)
        db.add(p)
        db.flush()
    return p


def profile_out(p: ApplicantProfile) -> dict:
    core = ["given_names", "family_name", "date_of_birth", "nationality", "residence_country", "marital_status",
            "passport_number", "passport_expiry", "phone"]
    out = {k: (getattr(p, k).isoformat() if hasattr(getattr(p, k), "isoformat") else getattr(p, k)) for k in core}
    for s in SECTIONS:
        out[s] = getattr(p, s) or {}
    filled = sum(1 for k in core[:8] if getattr(p, k)) + sum(1 for s in SECTIONS if getattr(p, s))
    out["completion"] = round(100 * filled / (8 + len(SECTIONS)))
    return out


@router.get("")
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _get_profile(db, user)
    db.commit()
    return profile_out(p)


@router.put("")
def update_profile(body: ProfileIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = _get_profile(db, user)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k in SECTIONS:
            setattr(p, k, getattr(body, k).model_dump(mode="json") if v is not None else {})
        else:
            setattr(p, k, v)
    audit(db, "profile.updated", actor=user, target_type="profile", target_id=p.id, request=request, sections=list(data.keys()))
    db.commit()
    return profile_out(p)
