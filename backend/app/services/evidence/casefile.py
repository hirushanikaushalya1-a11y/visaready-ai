"""Submission File Builder.

Assembles the applicant's evidence into a structured, numbered case file in the order a
decision-maker reads it (identity → purpose → finances → background → relationships →
health & character → immigration history), shows which document fills each item, and lists
what must be resolved before lodging. It organises evidence; it never invents any.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.applications import (
    Application,
    Assessment,
    AssessmentChecklistItem,
    AssessmentClaim,
    AssessmentFinding,
    Document,
)
from app.models.enums import DOCUMENT_TYPES

SECTIONS = [
    ("A", "Identity and travel document", {"passport", "photo", "birth_certificate"}),
    ("B", "Purpose of travel", {"offer_letter", "employment_contract", "sop", "skills_assessment"}),
    ("C", "Financial capacity and source of funds", {"bank_statement", "salary_slip", "tax_record", "business_registration",
                                                      "sponsorship_letter", "affidavit"}),
    ("D", "Education and English language", {"academic_certificate", "academic_transcript", "english_test_result"}),
    ("E", "Employment and professional background", {"employment_letter", "experience_certificate", "cv", "professional_registration"}),
    ("F", "Relationship and family", {"marriage_certificate", "relationship_evidence"}),
    ("G", "Health and character", {"medical_report", "police_certificate"}),
    ("H", "Immigration history", {"travel_document", "visa_refusal"}),
    ("I", "Other supporting documents", {"other"}),
]
STATUS_LABEL = {"satisfied": "Included", "uploaded_unconfirmed": "Uploaded — not confirmed", "missing": "Missing",
                "needs_clarification": "Needs clarification"}


# Evidence whose purpose is financial (e.g. proving the sponsor relationship or income) is filed
# with the finances even when the document itself is a birth certificate or employer letter.
FINANCIAL_PURPOSE_KEYS = ("ev:sponsor-", "ev:nz-financial", "ev:own-funds", "ev:large-deposit", "ev:education-loan")


def _section_for(types: list[str], item_key: str = "") -> str:
    if item_key.startswith(FINANCIAL_PURPOSE_KEYS):
        return "C"
    for t in types:  # the first (primary) accepted document type decides the section
        for code, _, members in SECTIONS:
            if t in members:
                return code
    return "I"


def build_case_file(db: Session, assessment: Assessment) -> dict:
    app = db.get(Application, assessment.application_id)
    items = db.scalars(select(AssessmentChecklistItem).where(AssessmentChecklistItem.assessment_id == assessment.id)
                       .order_by(AssessmentChecklistItem.sort_order)).all()
    findings = db.scalars(select(AssessmentFinding).where(AssessmentFinding.assessment_id == assessment.id)).all()
    claims = db.scalars(select(AssessmentClaim).where(AssessmentClaim.assessment_id == assessment.id)).all()
    docs = {str(d.id): d for d in db.scalars(select(Document).where(Document.application_id == app.id,
                                                                    Document.deleted_at.is_(None), Document.is_current.is_(True))).all()}

    def doc_ref(doc_id: str) -> dict | None:
        d = docs.get(doc_id)
        if not d:
            return None
        return {"id": doc_id, "filename": d.original_filename, "pages": d.page_count,
                "type": DOCUMENT_TYPES.get(d.detected_type or d.declared_type or "", "Document"),
                "needs_translation": bool((d.quality or {}).get("non_latin_scripts"))}

    sections = {code: {"code": code, "title": title, "entries": []} for code, title, _ in SECTIONS}
    used_docs: set[str] = set()
    for it in items:
        if not it.document_types:
            continue  # translation-type items are reported as a lodging note instead
        confirmed = [x for x in it.matched_document_ids if not x.startswith("unconfirmed:")]
        unconfirmed = [x.split(":", 1)[1] for x in it.matched_document_ids if x.startswith("unconfirmed:")]
        used_docs.update(confirmed + unconfirmed)
        sec = sections[_section_for(it.document_types, it.item_key)]
        sec["entries"].append({
            "title": it.title, "status": it.status, "status_label": STATUS_LABEL.get(it.status, it.status),
            "basis": "Official requirement" if it.origin == "requirement" else "Supports your declared circumstances",
            "level": it.level, "source_url": it.source_url, "source_verified": it.source_verified,
            "documents": [r for r in (doc_ref(x) for x in confirmed) if r],
            "unconfirmed_documents": [r for r in (doc_ref(x) for x in unconfirmed) if r],
            "accepted_types": [DOCUMENT_TYPES.get(t, t) for t in it.document_types],
        })
    # Documents the applicant uploaded that no checklist item claimed are still filed, under their own type.
    for doc_id, d in docs.items():
        if doc_id in used_docs:
            continue
        t = d.detected_type or d.declared_type or "other"
        sections[_section_for([t])]["entries"].append({
            "title": DOCUMENT_TYPES.get(t, "Supporting document"), "status": "satisfied", "status_label": "Included (additional)",
            "basis": "Additional evidence you provided", "level": "supplementary", "source_url": None, "source_verified": False,
            "documents": [doc_ref(doc_id)], "unconfirmed_documents": [], "accepted_types": [],
        })

    ordered, n_total, n_done = [], 0, 0
    for code, _, _ in SECTIONS:
        sec = sections[code]
        if not sec["entries"]:
            continue
        sec["entries"].sort(key=lambda e: (e["status"] != "satisfied", e["level"] != "mandatory"))
        for i, e in enumerate(sec["entries"], 1):
            e["ref"] = f"{code}{i}"
            n_total += 1
            n_done += e["status"] == "satisfied"
        ordered.append(sec)

    blockers = [{"title": f.title, "severity": f.severity, "action": f.suggested_action}
                for f in findings if f.kind in ("inconsistency", "professional_review", "refusal_reason") and f.severity in ("high", "medium")]
    blockers += [{"title": f.title, "severity": f.severity, "action": f.suggested_action}
                 for f in findings if f.kind == "missing_evidence" and f.certainty == "confirmed_missing_requirement"]
    explanations = [{"question": f.title, "evidence": f.evidence_suggestions} for f in findings if f.kind == "question"]
    translations = sorted({d.original_filename for d in docs.values() if (d.quality or {}).get("non_latin_scripts")})
    unsupported_claims = [c.statement for c in claims if c.status in ("unsupported", "conflicting")]

    ready = not blockers and n_done == n_total and n_total > 0
    return {
        "application": {"id": str(app.id), "title": app.title, "country": app.country.name, "visa": app.visa_category.name,
                        "official_url": app.visa_category.official_url},
        "assessment": {"id": str(assessment.id), "version": assessment.version, "score": assessment.readiness_score,
                       "created_at": assessment.created_at.isoformat()},
        "progress": {"included": n_done, "total": n_total},
        "status": "ready_for_final_review" if ready else "not_ready",
        "status_label": "Ready for your final review" if ready else "Not ready to lodge yet",
        "sections": ordered,
        "before_lodging": blockers,
        "explanations_to_prepare": explanations,
        "translations_needed": translations,
        "unsupported_claims": unsupported_claims,
        "notes": [
            "Lodge documents in this order and use the reference numbers (A1, B2 …) in your cover letter and file names.",
            "Upload complete, legible copies of every page. Certified translations must accompany documents not in English.",
            "This file organises your evidence. It does not guarantee a decision, and requirements must be confirmed on the official source.",
        ],
    }


def get_assessment(db: Session, assessment_id: uuid.UUID) -> Assessment | None:
    return db.get(Assessment, assessment_id)
