"""Requirement resolution and versioning."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.models.knowledge import EvidenceRule, ImmigrationRequirement, RequirementVersion

SNAPSHOT_FIELDS = (
    "key", "title", "description", "requirement_level", "applies_when", "applies_to_member",
    "eligibility_conditions", "document_types", "financial_requirement", "exceptions",
    "translation_required_if_not_english", "source_url", "source_excerpt", "review_status",
)


def requirement_snapshot(req: ImmigrationRequirement) -> dict:
    snap = {f: getattr(req, f) for f in SNAPSHOT_FIELDS}
    snap["effective_date"] = req.effective_date.isoformat() if req.effective_date else None
    snap["last_verified_at"] = req.last_verified_at.isoformat() if req.last_verified_at else None
    return snap


def active_requirements(db: Session, visa_category_id: uuid.UUID) -> list[ImmigrationRequirement]:
    return list(
        db.scalars(
            select(ImmigrationRequirement)
            .where(
                ImmigrationRequirement.visa_category_id == visa_category_id,
                ImmigrationRequirement.review_status.in_(("pending_review", "verified")),
            )
            .order_by(ImmigrationRequirement.sort_order)
        )
    )


def active_evidence_rules(db: Session, category_type: str) -> list[EvidenceRule]:
    rules = db.scalars(select(EvidenceRule).where(EvidenceRule.is_active.is_(True))).all()
    return [r for r in rules if not r.category_types or category_type in r.category_types]


def update_requirement(db: Session, req: ImmigrationRequirement, changes: dict, actor_id: uuid.UUID, note: str) -> None:
    """Every content change creates a new version and resets verification — a changed requirement
    must be re-verified against its source before it is shown as verified again."""
    content_changed = False
    for k, v in changes.items():
        if k in SNAPSHOT_FIELDS and k != "review_status" and getattr(req, k) != v:
            setattr(req, k, v)
            content_changed = True
        elif k == "effective_date":
            req.effective_date = v
            content_changed = True
    if not content_changed:
        return
    req.version += 1
    req.review_status = "pending_review"
    req.last_verified_at = None
    req.verified_by_id = None
    db.flush()
    db.add(RequirementVersion(requirement_id=req.id, version=req.version, snapshot=requirement_snapshot(req),
                              change_note=note, changed_by_id=actor_id, created_at=utcnow()))


def verify_requirement(db: Session, req: ImmigrationRequirement, actor_id: uuid.UUID, excerpt: str | None) -> None:
    req.review_status = "verified"
    req.last_verified_at = utcnow()
    req.verified_by_id = actor_id
    if excerpt:
        req.source_excerpt = excerpt
    # Verification is an event on the current version (not a new content version): record it on that row.
    row = db.scalars(select(RequirementVersion).where(RequirementVersion.requirement_id == req.id,
                                                      RequirementVersion.version == req.version)).first()
    note = f"Verified against official source on {req.last_verified_at:%Y-%m-%d}"
    if row:
        row.snapshot = requirement_snapshot(req)
        row.change_note = f"{row.change_note or ''} · {note}".strip(" ·")
    else:
        db.add(RequirementVersion(requirement_id=req.id, version=req.version, snapshot=requirement_snapshot(req),
                                  change_note=note, changed_by_id=actor_id, created_at=utcnow()))
