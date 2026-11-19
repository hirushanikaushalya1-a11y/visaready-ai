"""Evidence Intelligence Engine — orchestrates one assessment version.

Inputs are read fresh from the database; outputs are written as an immutable assessment version
(findings, checklist items, claims, score). What-If simulations use the same code path with fact
overrides and are stored with is_simulation=true (never counted, never shown as the official report).
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import utcnow
from app.models.applications import (
    Application,
    Assessment,
    AssessmentChecklistItem,
    AssessmentClaim,
    AssessmentFinding,
    Document,
    RefusalAnalysis,
)
from app.models.knowledge import Country
from app.models.users import ApplicantProfile, User
from app.services.ai.provider import ai_plain_language, provider_name
from app.services.evidence.checklist import build_checklist
from app.services.evidence.claims import build_claims, evaluate_claims
from app.services.evidence.consistency import run_consistency
from app.services.evidence.facts import attribute_owners, build_documents, build_facts
from app.services.evidence.findings import SEVERITY_ORDER, Finding
from app.services.evidence.profile_analysis import profile_completeness, profile_concerns, questions, strengths
from app.services.evidence.refusal import analyse_refusal
from app.services.evidence.scoring import compute_score
from app.services.knowledge.requirements import active_evidence_rules, active_requirements

ENGINE_VERSION = "1.0.0"


def _load(db: Session, application_id: uuid.UUID):
    app = db.get(Application, application_id)
    user = db.get(User, app.user_id)
    profile = db.scalars(select(ApplicantProfile).where(ApplicantProfile.user_id == user.id)).first() or ApplicantProfile(user_id=user.id)
    docs = db.scalars(select(Document).where(Document.application_id == app.id, Document.deleted_at.is_(None))
                      .options(selectinload(Document.pages), selectinload(Document.fields))).all()
    return app, user, profile, list(docs)


def analyse(db: Session, application_id: uuid.UUID, overrides: dict | None = None, today: date | None = None) -> dict:
    """Pure analysis (no writes). Returns every artefact of an assessment."""
    app, user, profile, raw_docs = _load(db, application_id)
    docs = build_documents(raw_docs)
    facts = build_facts(user, profile, app, docs, today=today, overrides=overrides)
    attribute_owners(docs, facts["applicant"]["full_name"], facts["financial"]["sponsor_name"],
                     [(m["id"], m["name"]) for m in facts["family"]["members"]])
    facts["documents"]["types_present"] = sorted({d.effective_type for d in docs if d.effective_type})

    requirements = active_requirements(db, app.visa_category_id)
    rules = active_evidence_rules(db, facts["category"])
    country = db.get(Country, app.country_code)

    items = build_checklist(facts, requirements, rules, docs)
    findings: list[Finding] = run_consistency(facts, docs) + profile_concerns(facts)

    # Missing-evidence findings from the checklist
    for it in items:
        if it.status != "missing" or it.applicability != "applies":
            continue
        if not it.document_types:
            continue
        is_req = it.origin == "requirement"
        findings.append(Finding(
            fingerprint=f"missing:{it.item_key}", kind="missing_evidence",
            category="general" if is_req else (it.claim_key or "general").split(".")[0],
            severity=("high" if it.level == "mandatory" else "medium") if is_req else ("medium" if it.level == "conditional" else "low"),
            certainty="confirmed_missing_requirement" if (is_req and it.level == "mandatory") else "potential_concern",
            title=f"Missing: {it.title}", explanation=it.reason,
            why_it_matters=("This is listed as an official requirement for this visa" + ("" if it.source_verified else
                            " (source recorded, awaiting verification by our team)") + ".") if is_req else
            "This evidence would substantiate something you declared in your profile.",
            triggers=[{"type": "checklist", "item_key": it.item_key}], requirement_id=it.requirement_id, source_url=it.source_url,
            suggested_action="Upload the document against this checklist item.", confidence="high" if is_req else "medium",
        ))

    claims = build_claims(facts, docs)
    evaluate_claims(claims, docs, findings)

    refusals = []
    for d in docs:
        if d.effective_type == "visa_refusal" and d.status == "processed":
            reasons, rf = analyse_refusal(d, claims)
            refusals.append({"document_id": d.id, "reasons": reasons})
            findings += rf

    findings += questions(facts, findings)
    findings += strengths(facts, items, claims, findings)

    # De-duplicate fingerprints (first wins), sort by severity.
    seen, unique = set(), []
    for f in findings:
        if f.fingerprint not in seen:
            seen.add(f.fingerprint)
            unique.append(f)
    unique.sort(key=lambda f: (f.kind == "strength", f.kind == "question", SEVERITY_ORDER[f.severity]))

    ratio, missing_fields = profile_completeness(facts)
    score, breakdown = compute_score(ratio, missing_fields, items, claims, unique)

    limitations = []
    if not requirements:
        limitations.append(f"Detailed official requirements for {country.name} ({app.visa_category.name}) have not been loaded yet. "
                           "This assessment covers your evidence and consistency only; check the official source for requirements.")
    elif not any(r.review_status == "verified" for r in requirements):
        limitations.append("Requirements for this visa were recorded from official sources but have not yet been verified by our team. "
                           "Always confirm against the official source link shown on each item.")
    if provider_name() == "none":
        limitations.append("Document data was extracted with rule-based methods (no AI provider configured). Some fields may not be detected.")
    elif provider_name() == "anthropic":
        limitations.append("Your documents were read in full by Claude (Anthropic) to prepare the case review. AI can make mistakes — check every point against your documents.")
    limitations.append("Documents are checked for readability and consistency only. Authenticity has not been independently verified with issuing authorities.")

    summary = {
        "counts": {
            "high": sum(1 for f in unique if f.severity == "high" and f.kind not in ("question", "strength")),
            "medium": sum(1 for f in unique if f.severity == "medium" and f.kind not in ("question", "strength")),
            "low": sum(1 for f in unique if f.severity == "low" and f.kind not in ("question", "strength")),
            "missing_items": sum(1 for i in items if i.status == "missing" and i.applicability == "applies"),
            "satisfied_items": sum(1 for i in items if i.status == "satisfied"),
            "total_items": len(items),
            "claims_supported": sum(1 for c in claims if c.status == "supported"),
            "claims_total": len(claims),
        },
        "limitations": limitations,
        "country_module_status": country.module_status,
        "facts_snapshot": {k: facts[k] for k in ("category", "destination")} | {"study_gap_months": facts["academic"]["study_gap_months"],
                                                                                 "funding_source": facts["financial"]["funding_source"]},
        "refusals": refusals,
        "disclaimer": "VisaReady AI is an independent preparation tool. It is not affiliated with any government, does not give legal advice and cannot guarantee any visa outcome.",
    }
    return {"facts": facts, "items": items, "findings": unique, "claims": claims, "score": score, "breakdown": breakdown,
            "summary": summary, "requirements": requirements, "docs": docs, "app": app}


def run_assessment(db: Session, application_id: uuid.UUID, triggered_by: uuid.UUID | None, *,
                   overrides: dict | None = None, simulation: bool = False, assessment_id: uuid.UUID | None = None) -> Assessment:
    result = analyse(db, application_id, overrides=overrides)
    app: Application = result["app"]
    if assessment_id:
        a = db.get(Assessment, assessment_id)
    else:
        version = 0 if simulation else (db.scalar(select(func.max(Assessment.version)).where(
            Assessment.application_id == app.id, Assessment.is_simulation.is_(False))) or 0) + 1
        a = Assessment(application_id=app.id, version=version, engine_version=ENGINE_VERSION, created_at=utcnow(),
                       triggered_by_id=triggered_by, is_simulation=simulation, scenario=overrides)
        db.add(a)
        db.flush()
    from app.services.ai.claude_review import enabled as claude_review_enabled

    # When the Claude case review is on it already explains the file in plain language; skip the extra call.
    plain = ai_plain_language([{"id": f.fingerprint, "text": f.explanation} for f in result["findings"][:25]
                               if f.kind not in ("strength",)]) if not simulation and not claude_review_enabled() else {}
    for f in result["findings"]:
        db.add(AssessmentFinding(
            assessment_id=a.id, fingerprint=f.fingerprint, kind=f.kind, category=f.category, severity=f.severity,
            certainty=f.certainty, title=f.title[:300], explanation=plain.get(f.fingerprint, f.explanation),
            why_it_matters=f.why_it_matters, triggers=f.triggers, requirement_id=uuid.UUID(f.requirement_id) if f.requirement_id else None,
            source_url=f.source_url, suggested_action=f.suggested_action, evidence_suggestions=f.evidence_suggestions, confidence=f.confidence,
        ))
    for it in result["items"]:
        db.add(AssessmentChecklistItem(
            assessment_id=a.id, item_key=it.item_key, title=it.title, reason=it.reason, origin=it.origin, level=it.level,
            classifications=it.classifications, status=it.status, document_types=it.document_types,
            matched_document_ids=it.matched_document_ids + [f"unconfirmed:{x}" for x in it.unconfirmed_document_ids],
            requirement_id=uuid.UUID(it.requirement_id) if it.requirement_id else None,
            evidence_rule_id=uuid.UUID(it.evidence_rule_id) if it.evidence_rule_id else None,
            source_url=it.source_url, source_verified=it.source_verified, last_verified_at=it.last_verified_at, sort_order=it.sort_order,
        ))
    for c in result["claims"]:
        db.add(AssessmentClaim(assessment_id=a.id, claim_key=c.claim_key, category=c.category, statement=c.statement, source=c.source,
                               status=c.status, evidence=c.evidence(), related_finding_fingerprints=c.related, explanation=c.explanation))
    if not simulation:
        db.execute(delete(RefusalAnalysis).where(RefusalAnalysis.application_id == app.id))
        for r in result["summary"]["refusals"]:
            db.add(RefusalAnalysis(application_id=app.id, document_id=uuid.UUID(r["document_id"]), reasons=r["reasons"], method="rules"))
    a.readiness_score = result["score"]
    a.score_breakdown = result["breakdown"]
    a.summary = result["summary"]
    a.knowledge_snapshot = {str(r.id): {"key": r.key, "version": r.version, "review_status": r.review_status} for r in result["requirements"]}
    a.ai_provider = provider_name()
    a.status = "completed"
    a.completed_at = utcnow()
    db.flush()
    return a
