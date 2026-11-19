"""Proof Builder: turns what the applicant declared into explicit claims and maps each claim to
the evidence that supports it, is missing, or conflicts with it."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.evidence.facts import DocInfo
from app.services.evidence.findings import Finding

LABEL = {
    "passport": "Passport", "academic_certificate": "Certificate", "academic_transcript": "Transcript",
    "employment_letter": "Employer letter", "experience_certificate": "Experience certificate", "salary_slip": "Salary slips",
    "bank_statement": "Bank statements", "birth_certificate": "Birth certificate", "relationship_evidence": "Relationship evidence",
    "tax_record": "Tax records", "business_registration": "Business registration", "sponsorship_letter": "Sponsorship letter",
    "english_test_result": "Test report", "offer_letter": "Offer / acceptance letter", "sop": "Statement of purpose",
    "employment_contract": "Job offer / contract", "marriage_certificate": "Marriage certificate", "visa_refusal": "Refusal decision",
    "travel_document": "Visa / permit copy", "professional_registration": "Registration certificate",
}


@dataclass
class EvidenceSlot:
    document_type: str
    label: str
    required: bool
    owner: str | None = None
    must_mention: str | None = None
    document_ids: list[str] = field(default_factory=list)
    state: str = "missing"  # present | unconfirmed | missing


@dataclass
class Claim:
    claim_key: str
    category: str
    statement: str
    source: str
    slots: list[EvidenceSlot]
    status: str = "unsupported"
    explanation: str = ""
    related: list[str] = field(default_factory=list)

    def evidence(self) -> list[dict]:
        return [s.__dict__ for s in self.slots]


def _mentions(doc: DocInfo, phrase: str | None) -> bool:
    if not phrase:
        return True
    toks = [t for t in re.findall(r"[a-z]{3,}", phrase.lower()) if t not in {"the", "and", "ltd", "pvt", "limited", "private", "of"}]
    if not toks:
        return True
    text = doc.text.lower()
    return sum(1 for t in toks if t in text) / len(toks) >= 0.5


def _fill(slot: EvidenceSlot, docs: list[DocInfo]) -> None:
    for d in docs:
        if d.effective_type != slot.document_type:
            continue
        owner_ok = slot.owner is None or d.owner == slot.owner or d.owner == "unknown"
        if not owner_ok or not _mentions(d, slot.must_mention):
            continue
        slot.document_ids.append(d.id)
        if d.confirmed and (slot.owner is None or d.owner == slot.owner):
            slot.state = "present"
        elif slot.state != "present":
            slot.state = "unconfirmed"


def build_claims(facts: dict, docs: list[DocInfo]) -> list[Claim]:
    claims: list[Claim] = []
    ap, ac, em, fi, im, fa = (facts[k] for k in ("applicant", "academic", "employment", "financial", "immigration", "family"))

    claims.append(Claim("identity", "identity",
                        f"You are {ap['full_name']}" + (f", born {ap['date_of_birth']}" if ap["date_of_birth"] else "")
                        + (f", holding passport {ap['passport_number']}" if ap["passport_number"] else "") + ".",
                        "applicant", [EvidenceSlot("passport", "Passport bio page", True)]))

    for i, q in enumerate(ac["qualifications"]):
        title = q.get("title") or (q.get("level") or "qualification").replace("_", " ")
        inst = q.get("institution")
        claims.append(Claim(f"academic.qualification.{i}", "academic",
                            f"You completed {title}" + (f" at {inst}" if inst else "") + (f" ({q['completion_date']})" if q.get("completion_date") else "") + ".",
                            f"academic.qualifications[{i}]",
                            [EvidenceSlot("academic_certificate", "Certificate", True, must_mention=inst),
                             EvidenceSlot("academic_transcript", "Transcript", q.get("level") not in ("secondary",), must_mention=inst)]))

    if ac.get("english_test_type"):
        claims.append(Claim("academic.english", "academic",
                            f"You took {ac['english_test_type']}" + (f" with an overall score of {ac['english_test_score']}" if ac.get("english_test_score") else "") + ".",
                            "academic.english_test", [EvidenceSlot("english_test_result", "Test report", True)]))

    if facts["category"] == "student" and ac.get("course_name"):
        claims.append(Claim("academic.study_plan", "academic",
                            f"You plan to study {ac['course_name']}" + (f" at {ac['institution']}" if ac.get("institution") else "") + ".",
                            "application.details",
                            [EvidenceSlot("offer_letter", "Offer / acceptance letter", True, must_mention=ac.get("institution")),
                             EvidenceSlot("sop", "Statement of purpose", False)]))

    for i, h in enumerate(em["history"]):
        emp = h.get("employer") or "an employer"
        current = not h.get("end_date")
        slots = [EvidenceSlot("employment_letter", "Employer letter", True, must_mention=h.get("employer")),
                 EvidenceSlot("experience_certificate", "Experience certificate", False, must_mention=h.get("employer"))]
        if current:
            slots.append(EvidenceSlot("salary_slip", "Recent salary slips", False, owner="applicant"))
        claims.append(Claim(f"employment.history.{i}", "employment",
                            f"You worked as {h.get('job_title') or 'an employee'} at {emp} from {h.get('start_date') or '?'} to {h.get('end_date') or 'present'}.",
                            f"employment.history[{i}]", slots))
    if em.get("self_employed"):
        claims.append(Claim("employment.self_employment", "employment", "You are self-employed / run a business.", "employment.status",
                            [EvidenceSlot("business_registration", "Business registration", True), EvidenceSlot("tax_record", "Tax records", True)]))
    if facts["category"] == "work" and em.get("job_offer_employer"):
        claims.append(Claim("employment.job_offer", "employment",
                            f"You have a job offer from {em['job_offer_employer']}" + (f" as {em['job_offer_title']}" if em.get("job_offer_title") else "") + ".",
                            "application.details", [EvidenceSlot("employment_contract", "Job offer / contract", True, must_mention=em["job_offer_employer"])]))

    funding = fi.get("funding_source")
    if funding in ("self", "mixed"):
        claims.append(Claim("financial.own_funds", "financial",
                            "You will use your own funds" + (f" (declared savings: {fi['savings_amount']:,} {fi.get('savings_currency') or ''})" if isinstance(fi.get("savings_amount"), (int, float)) else "") + ".",
                            "financial", [EvidenceSlot("bank_statement", "Your bank statements", True, owner="applicant")]))
    if funding in ("sponsor", "mixed"):
        rel = fi.get("sponsor_relationship") or "a sponsor"
        slots = [EvidenceSlot("bank_statement", "Sponsor's bank statements", True, owner="sponsor"),
                 EvidenceSlot("birth_certificate" if rel in ("father", "mother", "parent") else "relationship_evidence",
                              "Proof of relationship to sponsor", True),
                 EvidenceSlot("sponsorship_letter", "Sponsorship letter / declaration", False)]
        et = fi.get("sponsor_employment_type")
        if et == "salaried":
            slots += [EvidenceSlot("employment_letter", "Sponsor's employment letter", True, owner="sponsor"),
                      EvidenceSlot("salary_slip", "Sponsor's salary slips", False, owner="sponsor"),
                      EvidenceSlot("tax_record", "Sponsor's tax records", False, owner="sponsor")]
        elif et in ("self_employed", "business_owner"):
            slots += [EvidenceSlot("business_registration", "Sponsor's business registration", True, owner="sponsor"),
                      EvidenceSlot("tax_record", "Sponsor's tax records", True, owner="sponsor")]
        claims.append(Claim("financial.sponsorship", "financial",
                            f"Your {rel} ({fi.get('sponsor_name') or 'name not given'}) will fund your application.", "financial.sponsor", slots))

    if im.get("previous_refusals"):
        claims.append(Claim("immigration.refusals", "immigration",
                            f"You have declared {im['previous_refusals']} previous visa refusal(s).", "immigration_history",
                            [EvidenceSlot("visa_refusal", "Refusal decision letter(s)", True)]))

    for m in fa.get("members", []):
        if m["relation"] in ("spouse", "partner"):
            claims.append(Claim(f"family.{m['id']}", "family", f"{m['name']} is your {m['relation']}.", "family_members",
                                [EvidenceSlot("marriage_certificate", "Marriage certificate", m["relation"] == "spouse", must_mention=m["name"].split()[-1] if m["name"] else None),
                                 EvidenceSlot("relationship_evidence", "Further relationship evidence", m["relation"] == "partner")]))
        elif m["relation"] == "child":
            claims.append(Claim(f"family.{m['id']}", "family", f"{m['name']} is your child.", "family_members",
                                [EvidenceSlot("birth_certificate", "Birth certificate", True, must_mention=m["name"].split()[0] if m["name"] else None)]))
    if facts["category"] == "family" and fa.get("principal_name"):
        claims.append(Claim("family.principal_status", "family",
                            f"{fa['principal_name']} holds (or is applying for) the qualifying status you are joining.", "application.details",
                            [EvidenceSlot("travel_document", "Principal's visa / permit or status evidence", True)]))
    return claims


def evaluate_claims(claims: list[Claim], docs: list[DocInfo], findings: list[Finding]) -> None:
    category_conflicts = {}
    for f in findings:
        if f.kind == "inconsistency" and f.severity in ("high", "medium"):
            category_conflicts.setdefault(f.category, []).append(f)
    for c in claims:
        for s in c.slots:
            _fill(s, docs)
        required = [s for s in c.slots if s.required]
        present = [s for s in required if s.state == "present"]
        unconfirmed = [s for s in required if s.state == "unconfirmed"]
        doc_ids = {i for s in c.slots for i in s.document_ids}
        conflicts = [f for f in category_conflicts.get(c.category, [])
                     if any(t.get("document_id") in doc_ids for t in f.triggers) or (c.claim_key == "identity" and f.category == "identity")
                     or (c.claim_key == "immigration.refusals")]
        if c.claim_key == "immigration.refusals" or any(f.certainty == "requires_professional_judgement" for f in conflicts):
            c.related = [f.fingerprint for f in conflicts]
        if conflicts:
            c.status = "conflicting"
            c.related = [f.fingerprint for f in conflicts]
            c.explanation = "Some of your documents disagree with this claim. See the related consistency findings."
        elif required and len(present) == len(required):
            c.status = "supported"
            c.explanation = "All core evidence for this claim has been uploaded and recognised."
        elif present:
            c.status = "partially_supported"
            missing = [s.label for s in required if s.state != "present"]
            c.explanation = f"Some evidence is in place. Still needed: {', '.join(missing)}."
        elif unconfirmed:
            c.status = "requires_clarification"
            c.explanation = "Documents were uploaded for this claim, but we could not confirm they are the right type or belong to the right person."
        else:
            c.status = "unsupported"
            c.explanation = f"No supporting evidence yet. Upload: {', '.join(s.label for s in required) or 'supporting documents'}."
        if c.claim_key == "immigration.refusals" and c.status in ("supported", "partially_supported"):
            c.status = "human_review_recommended"
            c.explanation += " Because a refusal is involved, a professional review of how it is addressed is recommended."
