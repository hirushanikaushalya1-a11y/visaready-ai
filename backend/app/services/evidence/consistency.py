"""Cross-Document Relationship Intelligence.

Compares the applicant's declarations with information extracted from every document, and the
documents with each other. Every finding cites the document, page and snippet it came from.
Wording rule: we describe differences and ask for clarification; we never allege fraud.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date

from app.services.evidence.facts import DocInfo, _ym, name_match
from app.services.evidence.findings import Finding, profile_ref

ID_TYPES = {"passport", "birth_certificate", "academic_certificate", "academic_transcript", "english_test_result",
            "employment_letter", "experience_certificate", "offer_letter", "employment_contract", "salary_slip"}


def _first(doc: DocInfo, name: str) -> dict | None:
    vals = sorted(doc.field_values(name), key=lambda f: -f["confidence"])
    return vals[0] if vals else None


def _token_overlap(a: str, b: str) -> float:
    ta = {t for t in re.findall(r"[a-z]{3,}", a.lower()) if t not in {"the", "and", "ltd", "pvt", "limited", "private", "company", "university", "college", "institute"}}
    tb = set(re.findall(r"[a-z]{3,}", b.lower()))
    return len(ta & tb) / len(ta) if ta else 0.0


def check_identity(facts: dict, docs: list[DocInfo]) -> list[Finding]:
    out: list[Finding] = []
    ap = facts["applicant"]
    declared_name, declared_dob, declared_pp = ap["full_name"], ap["date_of_birth"], ap["passport_number"]
    passports = [d for d in docs if d.effective_type == "passport"]

    # --- names on applicant-owned or identity documents
    for d in docs:
        if d.effective_type not in ID_TYPES or d.owner == "sponsor" or d.owner.startswith("family:"):
            continue
        f = _first(d, "full_name")
        if not f:
            continue
        m = name_match(f["normalized"], declared_name)
        if m == "variant" and d.effective_type in ("passport", "academic_certificate", "birth_certificate"):
            out.append(Finding(
                fingerprint=f"name_variant:{d.id}", kind="inconsistency", category="identity", severity="low",
                certainty="potential_concern", confidence="medium",
                title=f"Name is written differently on {d.filename}",
                explanation=f"Your profile name is '{declared_name}', while the document shows '{f['value']}'. This looks like the same name in a different order, spelling or with initials.",
                why_it_matters="Decision-makers compare names across documents. Small variations are common (especially with initials), but they should be consistent or explained.",
                triggers=[d.ref(f["page"], f["snippet"]), profile_ref("applicant.full_name", declared_name)],
                suggested_action="Use the name exactly as it appears in your passport on all forms. If documents legitimately use different formats, a short explanation or a one-and-the-same-person declaration can help.",
                evidence_suggestions=["One-and-the-same-person affidavit (if names differ materially)"],
            ))
        elif m == "different":
            out.append(Finding(
                fingerprint=f"name_conflict:{d.id}", kind="inconsistency", category="identity", severity="high",
                certainty="potential_concern", confidence="medium" if f["method"] != "mrz" else "high",
                title=f"Name on {d.filename} does not match your profile",
                explanation=f"The document shows '{f['value']}' but your profile name is '{declared_name}'.",
                why_it_matters="If a document appears to belong to someone else, it may not count as your evidence, and unexplained differences can raise questions.",
                triggers=[d.ref(f["page"], f["snippet"]), profile_ref("applicant.full_name", declared_name)],
                suggested_action="Check whether this document belongs to you (or to a sponsor/family member — if so, record them in your profile). If it is yours, correct the profile or explain the difference.",
            ))

    # --- date of birth
    if declared_dob:
        for d in docs:
            if d.owner in ("sponsor",) or d.owner.startswith("family:"):
                continue
            for f in d.field_values("date_of_birth"):
                if f["normalized"] != declared_dob:
                    out.append(Finding(
                        fingerprint=f"dob_conflict:{d.id}", kind="inconsistency", category="identity", severity="high",
                        certainty="potential_concern", confidence="high" if f["method"] == "mrz" else "medium",
                        title=f"Date of birth differs on {d.filename}",
                        explanation=f"Your profile says {declared_dob}; {d.filename} (page {f['page']}) shows {f['normalized']}.",
                        why_it_matters="Date of birth must be identical across identity and supporting documents.",
                        triggers=[d.ref(f["page"], f["snippet"]), profile_ref("applicant.date_of_birth", declared_dob)],
                        suggested_action="Check which date is correct. If the document is wrong, ask the issuer for a corrected copy; if the profile is wrong, update it. Date formats (day/month order) can also cause this — verify carefully.",
                    ))
                    break

    # --- passport number & MRZ integrity & expiry
    for d in passports:
        f = _first(d, "passport_number")
        if f and declared_pp and f["normalized"].upper() != declared_pp.upper().replace(" ", ""):
            out.append(Finding(
                fingerprint=f"passport_number_conflict:{d.id}", kind="inconsistency", category="identity", severity="high",
                certainty="potential_concern", confidence="high",
                title="Passport number differs from your profile",
                explanation=f"Profile: {declared_pp}; passport document: {f['normalized']}.",
                why_it_matters="The passport number must match exactly on forms, offer/CAS records and bookings.",
                triggers=[d.ref(f["page"], f["snippet"]), profile_ref("applicant.passport_number", declared_pp)],
                suggested_action="Correct whichever is wrong. If you have renewed your passport, upload the current one and make sure your institution/employer has the new number.",
            ))
        chk = _first(d, "mrz_check_digits_valid")
        if chk and chk["normalized"] in ("0", "1"):
            out.append(Finding(
                fingerprint=f"mrz_unreadable:{d.id}", kind="document_quality", category="identity", severity="low",
                certainty="observation", confidence="medium",
                title="Passport machine-readable zone could not be read reliably",
                explanation="The two lines at the bottom of the passport page were read, but their check digits did not validate. This is usually caused by scan quality.",
                why_it_matters="We use these lines to confirm your name, date of birth and passport number.",
                triggers=[d.ref(chk["page"])], suggested_action="Upload a clear, flat, glare-free scan of the passport bio page.",
            ))
        exp = _first(d, "expiry_date")
        if exp:
            try:
                exp_d = date.fromisoformat(exp["normalized"])
            except ValueError:
                exp_d = None
            if exp_d:
                months_left = (exp_d.year - date.today().year) * 12 + exp_d.month - date.today().month
                if months_left < 0:
                    out.append(Finding(
                        fingerprint=f"passport_expired:{d.id}", kind="concern", category="identity", severity="high",
                        certainty="potential_concern", confidence="high", title="Your passport appears to have expired",
                        explanation=f"The passport shows an expiry date of {exp_d.isoformat()}.",
                        why_it_matters="A valid passport is required for virtually every visa application.",
                        triggers=[d.ref(exp["page"], exp["snippet"])], suggested_action="Renew your passport before applying and upload the new one.",
                    ))
                elif months_left < 12:
                    out.append(Finding(
                        fingerprint=f"passport_expiring:{d.id}", kind="concern", category="identity", severity="medium",
                        certainty="potential_concern", confidence="high", title="Your passport expires within 12 months",
                        explanation=f"The passport expires on {exp_d.isoformat()}. Some destinations limit the visa length to passport validity or require validity beyond your stay.",
                        why_it_matters="Short passport validity can shorten the permission you receive or cause complications.",
                        triggers=[d.ref(exp["page"], exp["snippet"])],
                        suggested_action="Check the passport-validity rule in the official guidance for your destination and consider renewing first.",
                    ))
    if len(passports) > 1:
        nums = {(_first(p, "passport_number") or {}).get("normalized") for p in passports} - {None}
        if len(nums) > 1:
            out.append(Finding(
                fingerprint="multiple_passports", kind="inconsistency", category="identity", severity="medium",
                certainty="potential_concern", title="Multiple different passports uploaded",
                explanation=f"We found passport numbers {', '.join(sorted(nums))}.",
                why_it_matters="Applications normally use your current passport; old passports can support travel history.",
                triggers=[p.ref() for p in passports],
                suggested_action="Mark old passports as travel-history evidence and make sure the current passport is the one used in your application.",
            ))
    return out


def check_employment(facts: dict, docs: list[DocInfo]) -> list[Finding]:
    out: list[Finding] = []
    history = facts["employment"]["history"]
    emp_docs = [d for d in docs if d.effective_type in ("employment_letter", "experience_certificate") and d.owner != "sponsor"]
    for i, h in enumerate(history):
        employer = (h.get("employer") or "").strip()
        if not employer:
            continue
        matched = [d for d in emp_docs if _token_overlap(employer, d.text) >= 0.5]
        for d in matched:
            f = _first(d, "employment_start")
            declared = _ym(h.get("start_date"))
            if f and declared:
                doc_d = date.fromisoformat(f["normalized"])
                diff = abs((doc_d.year - declared.year) * 12 + doc_d.month - declared.month)
                if diff >= 2:
                    out.append(Finding(
                        fingerprint=f"employment_start_conflict:{i}:{d.id}", kind="inconsistency", category="employment",
                        severity="medium" if diff < 12 else "high", certainty="potential_concern",
                        title=f"Start date at {employer} differs between your profile and {d.filename}",
                        explanation=f"Profile: {declared.strftime('%b %Y')}; document (page {f['page']}): {doc_d.strftime('%d %b %Y')}.",
                        why_it_matters="Employment dates should agree across your CV, forms and employer letters.",
                        triggers=[d.ref(f["page"], f["snippet"]), profile_ref(f"employment.history[{i}].start_date", h.get("start_date"))],
                        suggested_action="Confirm the correct date with your employer records and update whichever is wrong.",
                    ))
            if h.get("job_title"):
                jt = _first(d, "job_title")
                if jt and _token_overlap(h["job_title"], jt["value"]) < 0.34:
                    out.append(Finding(
                        fingerprint=f"job_title_conflict:{i}:{d.id}", kind="inconsistency", category="employment", severity="low",
                        certainty="potential_concern",
                        title=f"Job title at {employer} is described differently",
                        explanation=f"Profile: '{h['job_title']}'; {d.filename}: '{jt['value']}'.",
                        why_it_matters="Different titles for the same job can be legitimate (internal vs. market titles) but may need a brief explanation, especially for work visas tied to an occupation.",
                        triggers=[d.ref(jt["page"], jt["snippet"]), profile_ref(f"employment.history[{i}].job_title", h["job_title"])],
                        suggested_action="Use the title shown on your employer's letter, or ask the employer to state both titles and your duties.",
                    ))
    # CV vs declared employers
    for d in [d for d in docs if d.effective_type == "cv"]:
        for i, h in enumerate(history):
            employer = (h.get("employer") or "").strip()
            if employer and _token_overlap(employer, d.text) < 0.5:
                out.append(Finding(
                    fingerprint=f"cv_missing_employer:{i}:{d.id}", kind="inconsistency", category="employment", severity="low",
                    certainty="potential_concern", title=f"Your CV does not mention {employer}",
                    explanation=f"{employer} is listed in your employment history but we could not find it in {d.filename}.",
                    why_it_matters="Your CV, forms and statements should describe the same history.",
                    triggers=[d.ref(), profile_ref(f"employment.history[{i}].employer", employer)],
                    suggested_action="Update your CV so it includes every role you declare (or remove roles from your profile that are not accurate).",
                ))
    return out


def check_financial(facts: dict, docs: list[DocInfo]) -> list[Finding]:
    out: list[Finding] = []
    fin = facts["financial"]
    statements = [d for d in docs if d.effective_type == "bank_statement"]
    funding = fin.get("funding_source")
    sponsor_name = fin.get("sponsor_name")

    if funding in ("sponsor", "mixed") and sponsor_name:
        for d in statements:
            f = _first(d, "full_name")
            if f and d.owner == "unknown":
                out.append(Finding(
                    fingerprint=f"statement_holder_unmatched:{d.id}", kind="inconsistency", category="financial", severity="medium",
                    certainty="potential_concern", title=f"Account holder on {d.filename} is neither you nor your declared sponsor",
                    explanation=f"The statement appears to belong to '{f['value']}'. Your declared sponsor is '{sponsor_name}'.",
                    why_it_matters="Funds normally need to be held by you or an acceptable sponsor whose relationship to you is evidenced.",
                    triggers=[d.ref(f["page"], f["snippet"]), profile_ref("financial.sponsor.name", sponsor_name)],
                    suggested_action="Check that the sponsor's name in your profile matches their bank records exactly, or explain whose account this is.",
                ))
    # declared savings vs extracted balances (own statements)
    declared = fin.get("savings_amount")
    if isinstance(declared, (int, float)) and declared > 0:
        own = [d for d in statements if d.owner == "applicant"]
        for d in own:
            bal = _first(d, "closing_balance") or _first(d, "last_balance")
            if not bal:
                continue
            amount = float(bal["normalized"])
            if amount and abs(amount - declared) / max(declared, 1) > 0.2:
                out.append(Finding(
                    fingerprint=f"savings_mismatch:{d.id}", kind="inconsistency", category="financial", severity="medium",
                    certainty="potential_concern",
                    title="Declared savings differ from your bank statement balance",
                    explanation=f"You declared savings of {declared:,.2f} {fin.get('savings_currency') or ''}; {d.filename} shows a balance of {amount:,.2f} (page {bal['page']}).",
                    why_it_matters="Financial declarations on forms should match the evidence provided.",
                    triggers=[d.ref(bal["page"], bal["snippet"]), profile_ref("financial.savings_amount", declared)],
                    suggested_action="Update your declaration to match your evidence (note the currency and date), or upload statements for all accounts you counted.",
                ))
    # significant deposits
    for d in statements:
        deps = d.field_values("significant_deposit")
        if deps and not fin.get("large_deposit_explanation"):
            out.append(Finding(
                fingerprint=f"significant_deposits:{d.id}", kind="concern", category="financial", severity="medium",
                certainty="potential_concern", confidence="low",
                title=f"Large deposit(s) found in {d.filename}",
                explanation=f"We identified {len(deps)} credit(s) that are large compared with this account's usual activity (for example {float(deps[0]['normalized']):,.2f} on page {deps[0]['page']}). Large deposits are often entirely legitimate.",
                why_it_matters="Decision-makers may ask where recently deposited funds came from and whether they are genuinely available to you.",
                triggers=[d.ref(x["page"], x["snippet"]) for x in deps[:5]],
                suggested_action="Add a short explanation of each large deposit in your profile and keep evidence of its source.",
                evidence_suggestions=["Sale deed or agreement", "Gift letter with donor's bank statement", "Fixed-deposit maturity advice", "Loan sanction / disbursement letter", "Salary or bonus confirmation"],
            ))
    return out


def check_academic(facts: dict, docs: list[DocInfo]) -> list[Finding]:
    out: list[Finding] = []
    quals = facts["academic"]["qualifications"]
    certs = [d for d in docs if d.effective_type in ("academic_certificate", "academic_transcript")]
    for i, q in enumerate(quals):
        inst = q.get("institution") or ""
        declared = _ym(q.get("completion_date"))
        for d in certs:
            if not inst or _token_overlap(inst, d.text) < 0.5:
                continue
            f = _first(d, "award_date")
            if f and declared:
                doc_d = date.fromisoformat(f["normalized"])
                if abs(doc_d.year - declared.year) >= 1 and abs((doc_d - declared).days) > 200:
                    out.append(Finding(
                        fingerprint=f"award_date_conflict:{i}:{d.id}", kind="inconsistency", category="academic", severity="medium",
                        certainty="potential_concern", title=f"Completion date for your {q.get('title') or 'qualification'} differs",
                        explanation=f"Profile: {declared.strftime('%b %Y')}; {d.filename}: {doc_d.strftime('%d %b %Y')} (page {f['page']}).",
                        why_it_matters="Academic timelines are used to understand study gaps and progression.",
                        triggers=[d.ref(f["page"], f["snippet"]), profile_ref(f"academic.qualifications[{i}].completion_date", q.get("completion_date"))],
                        suggested_action="Note that results-release, examination and convocation dates often differ; use the date the authority asks for and keep it consistent.",
                    ))
    # English test: declared score vs document
    t = facts["academic"]
    for d in [d for d in docs if d.effective_type == "english_test_result"]:
        f = _first(d, "overall_score")
        if f and t.get("english_test_score") not in (None, ""):
            try:
                if abs(float(f["normalized"]) - float(t["english_test_score"])) > 0.01:
                    out.append(Finding(
                        fingerprint=f"english_score_conflict:{d.id}", kind="inconsistency", category="academic", severity="medium",
                        certainty="potential_concern", title="English test score differs from what you declared",
                        explanation=f"You declared {t['english_test_score']}; the test report shows {f['normalized']} (page {f['page']}).",
                        why_it_matters="Scores on forms must match the official test report exactly.",
                        triggers=[d.ref(f["page"], f["snippet"]), profile_ref("academic.english_test.overall_score", t["english_test_score"])],
                        suggested_action="Correct your declared score to match the test report.",
                    ))
            except ValueError:
                pass
    return out


def check_disclosures(facts: dict, docs: list[DocInfo]) -> list[Finding]:
    out: list[Finding] = []
    refusal_docs = [d for d in docs if d.effective_type == "visa_refusal"]
    if refusal_docs and facts["immigration"]["previous_refusals"] in (0, None):
        out.append(Finding(
            fingerprint="undeclared_refusal", kind="inconsistency", category="immigration", severity="high",
            certainty="requires_professional_judgement", confidence="medium",
            title="A refusal letter was uploaded but no previous refusal is declared",
            explanation=f"{refusal_docs[0].filename} looks like a visa refusal decision, but your immigration history does not record any refusal.",
            why_it_matters="Most immigration authorities require previous refusals to be disclosed. Failing to disclose a refusal can have serious consequences, potentially more serious than the refusal itself.",
            triggers=[d.ref() for d in refusal_docs] + [profile_ref("immigration.previous_refusals", facts["immigration"]["previous_refusals"])],
            suggested_action="Update your immigration history to declare this refusal accurately. Consider professional advice if you are unsure what must be disclosed.",
        ))
    return out


def check_quality(docs: list[DocInfo]) -> list[Finding]:
    out: list[Finding] = []
    for d in docs:
        if d.status == "failed":
            out.append(Finding(fingerprint=f"processing_failed:{d.id}", kind="document_quality", category="general", severity="medium",
                               certainty="observation", title=f"{d.filename} could not be processed",
                               explanation="We could not read this file.", triggers=[d.ref()],
                               suggested_action="Re-upload a clear PDF, JPG or PNG."))
            continue
        for issue in (d.quality or {}).get("issues", []):
            out.append(Finding(fingerprint=f"quality:{d.id}:{hashlib.sha1(issue.encode()).hexdigest()[:10]}", kind="document_quality", category="general",
                               severity="low", certainty="observation", title=f"Document quality: {d.filename}",
                               explanation=issue, triggers=[d.ref()],
                               why_it_matters="Unclear or incomplete documents may not be accepted as evidence.",
                               suggested_action="Upload a complete, clear scan of every page."))
        if d.non_english:
            scripts = ", ".join(d.quality.get("non_latin_scripts", []))
            out.append(Finding(fingerprint=f"translation_needed:{d.id}", kind="missing_evidence", category="general", severity="medium",
                               certainty="potential_concern", title=f"{d.filename} appears to contain {scripts} text",
                               explanation="Documents not in the language(s) accepted by the destination usually need a certified translation.",
                               why_it_matters="Untranslated documents may be disregarded.",
                               triggers=[d.ref()], suggested_action="Order a sworn/certified translation and upload it alongside the original.",
                               evidence_suggestions=["Certified or sworn translation"]))
        if not d.confirmed and d.status == "processed":
            out.append(Finding(fingerprint=f"unconfirmed_type:{d.id}", kind="document_quality", category="general", severity="info",
                               certainty="observation", confidence="low", title=f"We could not confirm what {d.filename} is",
                               explanation=f"You labelled it as '{(d.declared_type or 'unspecified').replace('_', ' ')}', but its content did not clearly match a known document type. It will not count towards checklist items until confirmed.",
                               triggers=[d.ref()], suggested_action="Check that the right file was uploaded and that it is complete and legible. A human reviewer can confirm it if needed."))
    return out


def run_consistency(facts: dict, docs: list[DocInfo]) -> list[Finding]:
    return (check_identity(facts, docs) + check_employment(facts, docs) + check_financial(facts, docs)
            + check_academic(facts, docs) + check_disclosures(facts, docs) + check_quality(docs))
