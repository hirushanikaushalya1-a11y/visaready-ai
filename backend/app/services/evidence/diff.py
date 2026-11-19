"""Application Strength Simulator: explains exactly what changed between two assessment versions."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.applications import Assessment, AssessmentChecklistItem, AssessmentClaim, AssessmentFinding

ISSUE_KINDS = {"missing_evidence", "inconsistency", "concern", "professional_review", "document_quality", "refusal_reason"}


def _load(db: Session, a: Assessment):
    f = db.scalars(select(AssessmentFinding).where(AssessmentFinding.assessment_id == a.id)).all()
    i = db.scalars(select(AssessmentChecklistItem).where(AssessmentChecklistItem.assessment_id == a.id)).all()
    c = db.scalars(select(AssessmentClaim).where(AssessmentClaim.assessment_id == a.id)).all()
    return {x.fingerprint: x for x in f if x.kind in ISSUE_KINDS}, {x.item_key: x for x in i}, {x.claim_key: x for x in c}


def compare(db: Session, before: Assessment, after: Assessment) -> dict:
    fb, ib, cb = _load(db, before)
    fa, ia, ca = _load(db, after)
    resolved = [{"fingerprint": k, "title": v.title, "severity": v.severity} for k, v in fb.items() if k not in fa]
    new = [{"fingerprint": k, "title": v.title, "severity": v.severity} for k, v in fa.items() if k not in fb]
    remaining = [{"fingerprint": k, "title": v.title, "severity": v.severity} for k, v in fa.items() if k in fb]
    item_changes = []
    for k, v in ia.items():
        old = ib.get(k)
        if old and old.status != v.status:
            item_changes.append({"item_key": k, "title": v.title, "from": old.status, "to": v.status})
        elif not old:
            item_changes.append({"item_key": k, "title": v.title, "from": None, "to": v.status})
    for k, v in ib.items():
        if k not in ia:
            item_changes.append({"item_key": k, "title": v.title, "from": v.status, "to": "no_longer_applies"})
    claim_changes = [{"claim_key": k, "statement": v.statement, "from": cb[k].status, "to": v.status}
                     for k, v in ca.items() if k in cb and cb[k].status != v.status]

    comp_b = (before.score_breakdown or {}).get("components", {})
    comp_a = (after.score_breakdown or {}).get("components", {})
    explanations = []
    for name in ("profile", "requirements", "evidence", "consistency"):
        pb, pa = (comp_b.get(name) or {}).get("points"), (comp_a.get(name) or {}).get("points")
        if pb is None and pa is None:
            continue
        delta = round((pa or 0) - (pb or 0), 1)
        if delta:
            explanations.append({"component": name, "delta": delta, "now": comp_a.get(name, {}).get("explanation")})
    return {
        "before": {"id": str(before.id), "version": before.version, "score": before.readiness_score, "at": before.created_at.isoformat()},
        "after": {"id": str(after.id), "version": after.version, "score": after.readiness_score, "at": after.created_at.isoformat()},
        "score_delta": (after.readiness_score or 0) - (before.readiness_score or 0),
        "score_explanations": explanations,
        "issues_resolved": resolved, "new_issues": new, "remaining_issues": remaining,
        "checklist_changes": item_changes, "claim_changes": claim_changes,
        "note": "Scores change only when evidence or information actually resolves an issue; uploading unrelated documents does not change the score.",
    }
