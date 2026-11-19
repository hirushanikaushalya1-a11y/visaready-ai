from __future__ import annotations

import html
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.database import get_db, utcnow
from app.core.deps import get_current_user, owned_application, require_unlocked
from app.models.applications import (
    Application,
    Assessment,
    AssessmentChecklistItem,
    AssessmentClaim,
    AssessmentFinding,
    Document,
    RefusalAnalysis,
)
from app.models.users import User
from app.services.evidence.diff import compare
from app.services.evidence.engine import ENGINE_VERSION, run_assessment
from app.services.jobs.queue import enqueue

router = APIRouter(tags=["assessments"])


class WhatIfIn(BaseModel):
    academic: dict = Field(default_factory=dict)
    employment: dict = Field(default_factory=dict)
    financial: dict = Field(default_factory=dict)
    immigration: dict = Field(default_factory=dict)
    details: dict = Field(default_factory=dict)
    family: dict = Field(default_factory=dict)


WHATIF_ALLOWED = {
    "academic": {"english_test"},
    "employment": {"status", "career_change", "regulated_occupation"},
    "financial": {"funding_source", "sponsor", "declared_large_deposits", "has_education_loan", "savings_amount"},
    "immigration": {"has_previous_refusals", "overstays"},
    "details": {"course_name", "course_level", "institution", "course_start", "course_related_to_previous", "employer", "job_title", "job_offer_sector"},
    "family": {"accompanying_spouse", "accompanying_children"},
}


def assessment_out(db: Session, a: Assessment, full: bool = True) -> dict:
    out = {"id": str(a.id), "application_id": str(a.application_id), "version": a.version, "status": a.status,
           "readiness_score": a.readiness_score, "score_breakdown": a.score_breakdown, "summary": a.summary,
           "engine_version": a.engine_version, "ai_provider": a.ai_provider, "is_simulation": a.is_simulation,
           "scenario": a.scenario, "error": a.error, "created_at": a.created_at.isoformat(),
           "completed_at": a.completed_at.isoformat() if a.completed_at else None}
    if not full:
        return out
    out["findings"] = [{
        "id": str(f.id), "fingerprint": f.fingerprint, "kind": f.kind, "category": f.category, "severity": f.severity,
        "certainty": f.certainty, "title": f.title, "explanation": f.explanation, "why_it_matters": f.why_it_matters,
        "triggers": f.triggers, "source_url": f.source_url, "suggested_action": f.suggested_action,
        "evidence_suggestions": f.evidence_suggestions, "confidence": f.confidence,
    } for f in db.scalars(select(AssessmentFinding).where(AssessmentFinding.assessment_id == a.id)).all()]
    out["checklist"] = [{
        "item_key": i.item_key, "title": i.title, "reason": i.reason, "origin": i.origin, "level": i.level,
        "classifications": i.classifications, "status": i.status, "document_types": i.document_types,
        "matched_document_ids": [x for x in i.matched_document_ids if not x.startswith("unconfirmed:")],
        "unconfirmed_document_ids": [x.split(":", 1)[1] for x in i.matched_document_ids if x.startswith("unconfirmed:")],
        "source_url": i.source_url, "source_verified": i.source_verified,
        "last_verified_at": i.last_verified_at.isoformat() if i.last_verified_at else None,
    } for i in db.scalars(select(AssessmentChecklistItem).where(AssessmentChecklistItem.assessment_id == a.id)
                          .order_by(AssessmentChecklistItem.sort_order)).all()]
    out["claims"] = [{"claim_key": c.claim_key, "category": c.category, "statement": c.statement, "source": c.source,
                      "status": c.status, "evidence": c.evidence, "related": c.related_finding_fingerprints, "explanation": c.explanation}
                     for c in db.scalars(select(AssessmentClaim).where(AssessmentClaim.assessment_id == a.id)).all()]
    return out


def _owned_assessment(db: Session, user: User, assessment_id: uuid.UUID) -> Assessment:
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    owned_application(db, user, a.application_id)
    return a


@router.post("/applications/{application_id}/assessments", status_code=202)
def request_assessment(application_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = owned_application(db, user, application_id, for_update=True)
    require_unlocked(app)
    if app.assessments_run >= 1 + app.reassessments_allowed:
        raise HTTPException(429, "You have reached the limit of assessment runs for this application. Please contact support if you need more.")
    running = db.scalars(select(Assessment).where(Assessment.application_id == app.id, Assessment.is_simulation.is_(False),
                                                  Assessment.status.in_(("queued", "running")))).first()
    if running:
        return assessment_out(db, running, full=False)
    pending_docs = db.scalars(select(Document).where(Document.application_id == app.id, Document.deleted_at.is_(None),
                                                     Document.status.in_(("uploaded", "processing")))).first()
    if pending_docs:
        raise HTTPException(409, "Some documents are still being processed. Please wait a moment and try again.")
    from sqlalchemy import func

    version = (db.scalar(select(func.max(Assessment.version)).where(Assessment.application_id == app.id, Assessment.is_simulation.is_(False))) or 0) + 1
    a = Assessment(application_id=app.id, version=version, engine_version=ENGINE_VERSION, status="queued",
                   triggered_by_id=user.id, created_at=utcnow())
    db.add(a)
    app.assessments_run += 1
    db.flush()
    audit(db, "assessment.requested", actor=user, target_type="assessment", target_id=a.id, request=request, version=version)
    enqueue(db, "run_assessment", {"assessment_id": str(a.id)})
    db.commit()
    db.refresh(a)
    return assessment_out(db, a, full=False)


@router.get("/applications/{application_id}/assessments")
def list_assessments(application_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = owned_application(db, user, application_id)
    rows = db.scalars(select(Assessment).where(Assessment.application_id == app.id, Assessment.is_simulation.is_(False))
                      .order_by(Assessment.version.desc())).all()
    return [assessment_out(db, a, full=False) for a in rows]


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return assessment_out(db, _owned_assessment(db, user, assessment_id))


@router.get("/assessments/{assessment_id}/compare/{other_id}")
def compare_assessments(assessment_id: uuid.UUID, other_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a, b = _owned_assessment(db, user, assessment_id), _owned_assessment(db, user, other_id)
    if a.application_id != b.application_id:
        raise HTTPException(422, "Assessments belong to different applications.")
    before, after = (a, b) if a.version <= b.version else (b, a)
    return compare(db, before, after)


@router.post("/applications/{application_id}/what-if")
def what_if(application_id: uuid.UUID, body: WhatIfIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """What-If Application Planner: re-runs the engine with hypothetical changes. Nothing is saved
    to the official history and it does not use a reassessment."""
    app = owned_application(db, user, application_id)
    require_unlocked(app)
    overrides = {}
    for section, allowed in WHATIF_ALLOWED.items():
        vals = {k: v for k, v in getattr(body, section).items() if k in allowed}
        if vals:
            overrides[section] = vals
    if not overrides:
        raise HTTPException(422, "Choose at least one change to simulate.")
    baseline = db.scalars(select(Assessment).where(Assessment.application_id == app.id, Assessment.is_simulation.is_(False),
                                                   Assessment.status == "completed").order_by(Assessment.version.desc())).first()
    sim = run_assessment(db, app.id, user.id, overrides=overrides, simulation=True)
    db.flush()
    result = {"scenario": overrides, "simulation": assessment_out(db, sim)}
    if baseline:
        result["comparison"] = compare(db, baseline, sim)
    db.rollback()  # simulations are never persisted
    return result


@router.get("/applications/{application_id}/refusal-analyses")
def refusal_analyses(application_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = owned_application(db, user, application_id)
    return [{"id": str(r.id), "document_id": str(r.document_id), "reasons": r.reasons, "method": r.method,
             "note": "Addressing previous refusal reasons does not guarantee approval."}
            for r in db.scalars(select(RefusalAnalysis).where(RefusalAnalysis.application_id == app.id)).all()]


@router.get("/assessments/{assessment_id}/report", response_class=HTMLResponse)
def printable_report(assessment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Self-contained printable report (browser 'Save as PDF'). Part of the paid full report."""
    from app.services.report_access import require_report

    a = _owned_assessment(db, user, assessment_id)
    require_report(db, a.application_id)
    app = db.get(Application, a.application_id)
    d = assessment_out(db, a)
    e = html.escape
    rows = "".join(f"<tr><td>{e(i['title'])}</td><td>{e(i['level'])}</td><td>{e(i['status'].replace('_', ' '))}</td>"
                   f"<td>{e(', '.join(c.replace('_', ' ') for c in i['classifications']))}</td></tr>" for i in d["checklist"])
    finds = "".join(f"<li><b>[{e(f['severity'])}] {e(f['title'])}</b><br>{e(f['explanation'])}<br><i>Next step:</i> {e(f['suggested_action'] or '')}</li>"
                    for f in d["findings"] if f["kind"] not in ("strength", "question"))
    lims = "".join(f"<li>{e(x)}</li>" for x in d["summary"].get("limitations", []))
    body = f"""<!doctype html><html><head><meta charset="utf-8"><title>Readiness report v{a.version}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:860px;margin:32px auto;color:#0f172a;padding:0 16px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #cbd5e1;padding:6px;font-size:13px;text-align:left}}h1{{color:#0b1f4d}}.note{{background:#f1f5f9;padding:12px;border-radius:8px;font-size:13px}}</style></head>
<body><h1>VisaReady AI – Application readiness report</h1><p>{e(app.title)} · Version {a.version} · {a.created_at:%d %b %Y}</p>
<p class="note"><b>Readiness score: {a.readiness_score}/100.</b> {e(d['score_breakdown'].get('note', ''))}</p>
<h2>Checklist</h2><table><tr><th>Item</th><th>Level</th><th>Status</th><th>Classification</th></tr>{rows}</table>
<h2>Findings</h2><ol>{finds}</ol><h2>Limitations</h2><ul>{lims}</ul>
<p class="note">{e(d['summary'].get('disclaimer', ''))}</p></body></html>"""
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


@router.get("/assessments/{assessment_id}/case-file")
def case_file(assessment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Submission File Builder: the applicant's evidence organised into a numbered, lodge-ready file."""
    from app.services.evidence.casefile import build_case_file

    return build_case_file(db, _owned_assessment(db, user, assessment_id))


@router.get("/assessments/{assessment_id}/case-file/print", response_class=HTMLResponse)
def case_file_print(assessment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.evidence.casefile import build_case_file
    from app.services.report_access import require_report

    a = _owned_assessment(db, user, assessment_id)
    require_report(db, a.application_id)
    f = build_case_file(db, a)
    e = html.escape
    secs = ""
    for sec in f["sections"]:
        rows = ""
        for en in sec["entries"]:
            docs = "<br>".join(f"{e(d['filename'])}" + (f" ({d['pages']} p.)" if d["pages"] else "") for d in en["documents"]) or "<i>—</i>"
            rows += (f"<tr><td><b>{e(en['ref'])}</b></td><td>{e(en['title'])}<div class='m'>{e(en['basis'])}</div></td>"
                     f"<td>{docs}</td><td class='s {e(en['status'])}'>{e(en['status_label'])}</td></tr>")
        secs += f"<h2>{e(sec['code'])}. {e(sec['title'])}</h2><table><tr><th>Ref</th><th>Item</th><th>Document(s)</th><th>Status</th></tr>{rows}</table>"
    block = "".join(f"<li><b>{e(b['title'])}</b> — {e(b['action'] or '')}</li>" for b in f["before_lodging"]) or "<li>None</li>"
    expl = "".join(f"<li>{e(x['question'])}</li>" for x in f["explanations_to_prepare"]) or "<li>None</li>"
    a = f["application"]
    body = f"""<!doctype html><html><head><meta charset="utf-8"><title>Submission file – {e(a['title'])}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:32px auto;color:#0f172a;padding:0 16px;font-size:13px}}
h1{{color:#0b1f4d;margin-bottom:4px}}h2{{margin-top:28px;border-bottom:2px solid #0b1f4d;padding-bottom:4px;font-size:15px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #cbd5e1;padding:6px;text-align:left;vertical-align:top}}
th{{background:#f1f5f9}}.m{{color:#64748b;font-size:11px}}.s.satisfied{{color:#157f4b}}.s.missing{{color:#b42318;font-weight:600}}
.s.uploaded_unconfirmed{{color:#a15c07}}.box{{background:#f1f5f9;padding:12px;border-radius:8px}}</style></head><body>
<h1>Submission file</h1><p>{e(a['title'])} · {e(a['visa'])} · {e(a['country'])}<br>Assessment v{f['assessment']['version']} ·
{f['progress']['included']} of {f['progress']['total']} items in place · <b>{e(f['status_label'])}</b></p>
<div class="box"><b>Resolve before lodging</b><ul>{block}</ul><b>Explanations to prepare</b><ul>{expl}</ul></div>
{secs}<p class="m">{'<br>'.join(e(n) for n in f['notes'])}</p></body></html>"""
    return HTMLResponse(body, headers={"Cache-Control": "no-store"})


@router.get("/assessments/{assessment_id}/drafts")
def drafts(assessment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Suggested drafts. Titles are always visible; full text is part of the paid report."""
    from app.services.evidence.drafts import build_drafts
    from app.services.report_access import report_unlocked

    a = _owned_assessment(db, user, assessment_id)
    items = build_drafts(db, a)
    unlocked = report_unlocked(db, a.application_id)
    if not unlocked:
        items = [{k: v for k, v in d.items() if k != "text"} for d in items]
    return {"unlocked": unlocked, "drafts": items}
