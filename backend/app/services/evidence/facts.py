"""Builds the normalised fact tree the engine reasons over, and the document index with owner
attribution (whose document is this? applicant / sponsor / family member)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.models.applications import Application, Document
from app.models.users import ApplicantProfile, User
from app.services.documents.extract import normalize_name

CONFIRM_THRESHOLD = 0.35  # minimum classifier confidence for a document type to count as confirmed


def _ym(s: str | None) -> date | None:
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", str(s))
    if not m:
        return None
    try:
        return date(int(m[1]), int(m[2]), int(m[3] or 1))
    except ValueError:
        return None


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def age_on(dob: date | None, on: date) -> int | None:
    if not dob:
        return None
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


@dataclass
class DocInfo:
    id: str
    filename: str
    effective_type: str | None
    confirmed: bool
    declared_type: str | None
    detected_type: str | None
    confidence: float
    status: str
    checklist_item_key: str | None
    text: str
    pages: dict[int, str]
    fields: list[dict]
    quality: dict
    owner: str = "unknown"  # applicant | sponsor | family:<id> | unknown
    owner_name: str | None = None
    non_english: bool = False

    def field_values(self, name: str) -> list[dict]:
        return [f for f in self.fields if f["name"] == name and f.get("normalized")]

    def ref(self, page: int | None = None, snippet: str | None = None) -> dict:
        return {"type": "document", "document_id": self.id, "filename": self.filename, "page": page, "snippet": snippet}


def name_match(a: str | None, b: str | None) -> str:
    """'exact' | 'variant' (same person, different spelling/order/initials) | 'different' | 'unknown'."""
    if not a or not b:
        return "unknown"
    ta, tb = normalize_name(a).split(), normalize_name(b).split()
    if not ta or not tb:
        return "unknown"
    if ta == tb:
        return "exact"
    sa, sb = set(ta), set(tb)
    if sa == sb:
        return "variant"
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    matched = 0
    for tok in small:
        if tok in big or (len(tok) == 1 and any(x.startswith(tok) for x in big)) or any(len(x) == 1 and tok.startswith(x) for x in big):
            matched += 1
    full_tokens = [t for t in small if len(t) > 1]
    full_matched = sum(1 for t in full_tokens if t in big)
    if matched == len(small) and full_matched >= 1:
        return "variant"
    return "different"


def build_documents(docs: list[Document]) -> list[DocInfo]:
    out = []
    for d in docs:
        if d.deleted_at or not d.is_current:
            continue
        conf = d.classification_confidence or 0.0
        confirmed = bool(d.detected_type) and conf >= CONFIRM_THRESHOLD
        effective = d.detected_type if confirmed else (d.declared_type or d.detected_type)
        pages = {p.page_number: p.text for p in d.pages}
        out.append(DocInfo(
            id=str(d.id), filename=d.original_filename, effective_type=effective, confirmed=confirmed,
            declared_type=d.declared_type, detected_type=d.detected_type, confidence=conf, status=d.status,
            checklist_item_key=d.checklist_item_key, text="\n".join(pages.values()), pages=pages,
            fields=[{"name": f.field_name, "value": f.value, "normalized": f.normalized_value, "page": f.page_number,
                     "snippet": f.snippet, "confidence": f.confidence, "method": f.method} for f in d.fields],
            quality=d.quality or {}, non_english=bool((d.quality or {}).get("non_latin_scripts")),
        ))
    return out


def attribute_owners(docs: list[DocInfo], applicant_name: str | None, sponsor_name: str | None, members: list[tuple[str, str]]) -> None:
    for d in docs:
        names = [f["normalized"] for f in d.fields if f["name"] in ("full_name", "account_holder") and f.get("normalized")]
        for n in names:
            if applicant_name and name_match(n, applicant_name) in ("exact", "variant"):
                d.owner, d.owner_name = "applicant", n
                break
            if sponsor_name and name_match(n, sponsor_name) in ("exact", "variant"):
                d.owner, d.owner_name = "sponsor", n
                break
            for mid, mname in members:
                if name_match(n, mname) in ("exact", "variant"):
                    d.owner, d.owner_name = f"family:{mid}", n
                    break
            if d.owner != "unknown":
                break
        if d.owner == "unknown" and names:
            d.owner_name = names[0]


def build_facts(user: User, profile: ApplicantProfile, app: Application, docs: list[DocInfo], today: date | None = None,
                overrides: dict | None = None) -> dict:
    today = today or date.today()
    acad = dict(profile.academic or {})
    emp = dict(profile.employment or {})
    fin = dict(profile.financial or {})
    imm = dict(profile.immigration_history or {})
    det = dict(app.details or {})
    if overrides:  # What-If planner: shallow overrides per section
        acad.update(overrides.get("academic", {}))
        emp.update(overrides.get("employment", {}))
        fin.update(overrides.get("financial", {}))
        imm.update(overrides.get("immigration", {}))
        det.update(overrides.get("details", {}))

    quals = [q for q in acad.get("qualifications", []) if isinstance(q, dict)]
    last_completion = max((d for d in (_ym(q.get("completion_date")) for q in quals) if d), default=None)
    course_start = _ym(det.get("course_start")) or today
    study_gap = months_between(last_completion, course_start) if last_completion else None

    history = [h for h in emp.get("history", []) if isinstance(h, dict)]
    exp_months = 0
    for h in history:
        s, e = _ym(h.get("start_date")), _ym(h.get("end_date")) or today
        if s and e >= s:
            exp_months += months_between(s, e)
    sponsor = fin.get("sponsor") or {}
    ent = dict(fin)
    members = [m for m in app.family_members if m.included_in_application]
    spouse = any(m.relation in ("spouse", "partner") for m in members)
    children = sum(1 for m in members if m.relation == "child")
    if overrides and "family" in overrides:
        spouse = overrides["family"].get("accompanying_spouse", spouse)
        children = overrides["family"].get("accompanying_children", children)

    full_name = " ".join(x for x in [profile.given_names, profile.family_name] if x) or user.full_name
    return {
        "category": app.visa_category.category_type,
        "destination": app.country_code,
        "applicant": {
            "full_name": full_name,
            "nationality": profile.nationality,
            "residence": profile.residence_country,
            "age": age_on(profile.date_of_birth, today),
            "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            "marital_status": profile.marital_status,
            "passport_number": profile.passport_number,
            "passport_expiry": profile.passport_expiry.isoformat() if profile.passport_expiry else None,
        },
        "academic": {
            "qualifications": quals,
            "qualification_count": len(quals),
            "last_completion": last_completion.isoformat() if last_completion else None,
            "study_gap_months": study_gap,
            "english_test_type": (acad.get("english_test") or {}).get("type") or None,
            "english_test_score": (acad.get("english_test") or {}).get("overall_score"),
            "english_test_date": (acad.get("english_test") or {}).get("test_date"),
            "course_name": det.get("course_name"),
            "course_level": det.get("course_level"),
            "institution": det.get("institution"),
            "course_related_to_previous": det.get("course_related_to_previous"),
            "career_goal": det.get("career_goal"),
        },
        "employment": {
            "status": emp.get("status"),
            "history": history,
            "history_count": len(history),
            "experience_months": exp_months,
            "self_employed": emp.get("status") == "self_employed" if emp.get("status") else None,
            "career_change": emp.get("career_change"),
            "regulated_occupation": emp.get("regulated_occupation"),
            "has_job_offer": bool(det.get("employer")) if app.visa_category.category_type == "work" else None,
            "job_offer_employer": det.get("employer"),
            "job_offer_title": det.get("job_title"),
            "job_offer_sector": det.get("job_offer_sector"),
        },
        "financial": {
            "funding_source": ent.get("funding_source"),
            "savings_amount": ent.get("savings_amount"),
            "savings_currency": ent.get("savings_currency"),
            "sponsor_name": sponsor.get("name"),
            "sponsor_relationship": sponsor.get("relationship"),
            "sponsor_employment_type": sponsor.get("employment_type"),
            "sponsor_annual_income": sponsor.get("annual_income"),
            "declared_large_deposits": ent.get("declared_large_deposits"),
            "large_deposit_explanation": ent.get("large_deposit_explanation"),
            "has_education_loan": ent.get("has_education_loan"),
        },
        "immigration": {
            # None = question not answered yet; 0 = answered "no"; n = number declared
            "previous_refusals": (max(1, len(imm.get("previous_refusals") or [])) if imm.get("has_previous_refusals")
                                  else 0 if imm.get("has_previous_refusals") is False else None),
            "refusals": imm.get("previous_refusals", []) or [],
            "previous_visa_count": len(imm.get("previous_visas", []) or []),
            "overstays": imm.get("overstays"),
            "overstay_details": imm.get("overstay_details"),
        },
        "family": {
            "accompanying_spouse": spouse,
            "accompanying_children": children,
            "members": [{"id": str(m.id), "relation": m.relation, "name": m.full_name} for m in members],
            "relation_to_principal": det.get("relation_to_principal"),
            "principal_name": det.get("principal_name"),
        },
        "documents": {
            "types_present": sorted({d.effective_type for d in docs if d.effective_type}),
            "has_non_english": any(d.non_english for d in docs),
            "count": len(docs),
        },
    }
