"""Suggested drafts included in the paid assessment report.

Each draft is a structured starting point built ONLY from facts the applicant entered. Anything we
cannot know is left as a [bracketed prompt] for the applicant to complete truthfully. Drafts never
invent history, money, relationships or reasons.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.applications import Assessment, AssessmentFinding
from app.services.evidence.engine import _load
from app.services.evidence.facts import build_documents, build_facts

FOOTER = ("\n\n— Draft prepared with VisaReady AI. Replace every [bracketed] prompt with accurate information, "
          "remove anything that does not apply, and make sure every statement is true and supported by your documents.")


def _v(x, prompt: str) -> str:
    return str(x) if x not in (None, "", []) else f"[{prompt}]"


def _month_year(iso: str | None) -> str:
    try:
        return date.fromisoformat(iso).strftime("%B %Y") if iso else "[month/year]"
    except ValueError:
        return "[month/year]"


def build_drafts(db: Session, assessment: Assessment) -> list[dict]:
    app, user, profile, raw_docs = _load(db, assessment.application_id)
    f = build_facts(user, profile, app, build_documents(raw_docs))
    fps = {x.fingerprint for x in db.scalars(select(AssessmentFinding).where(AssessmentFinding.assessment_id == assessment.id)).all()}
    ap, ac, em, fi, im = f["applicant"], f["academic"], f["employment"], f["financial"], f["immigration"]
    name, country, visa = ap["full_name"], app.country.name, app.visa_category.name
    today = date.today().strftime("%d %B %Y")
    drafts: list[dict] = []

    # 1. Cover letter — always
    funding = {"self": "my own savings", "sponsor": f"my {fi.get('sponsor_relationship') or 'sponsor'}, {fi.get('sponsor_name') or '[sponsor name]'}",
               "mixed": "my own savings together with support from my sponsor", "scholarship": "a scholarship", "employer": "my employer"}.get(
        fi.get("funding_source") or "", "[how your application is funded]")
    purpose = (f"to study {_v(ac.get('course_name'), 'course')} at {_v(ac.get('institution'), 'institution')}" if f["category"] == "student"
               else f"to take up employment as {_v(em.get('job_offer_title'), 'job title')} with {_v(em.get('job_offer_employer'), 'employer')}"
               if f["category"] == "work" else f"to join {_v(f['family'].get('principal_name'), 'family member')}")
    drafts.append({"key": "cover_letter", "title": "Cover letter", "service_code": "cover_letter", "text":
        f"{today}\n\nTo the Visa Officer,\n\nRe: {visa} application — {name} (Passport {_v(ap.get('passport_number'), 'passport number')})\n\n"
        f"I am applying for a {visa} {purpose}.\n\n"
        f"My application is funded by {funding}. The enclosed documents are arranged in the order of the attached index (sections A to I).\n\n"
        "In summary:\n• Identity: [list passport and civil documents]\n• Purpose: [offer / job / relationship documents]\n"
        "• Finances: [bank statements, sponsor evidence and source of funds]\n• Background: [education and employment evidence]\n"
        + ("• Previous refusal: I disclose my previous refusal and explain what has changed in [section reference].\n" if im.get("previous_refusals") else "")
        + "\nI confirm that the information in this application is true and complete.\n\nYours faithfully,\n\n" + name + FOOTER})

    # 2. SOP outline — students
    if f["category"] == "student":
        quals = ", ".join(q.get("title", "") for q in ac["qualifications"] if q.get("title")) or "[your qualifications]"
        drafts.append({"key": "sop_outline", "title": "Statement of purpose — structured outline", "service_code": "sop", "text":
            f"STATEMENT OF PURPOSE — {name}\n{_v(ac.get('course_name'), 'course')}, {_v(ac.get('institution'), 'institution')} ({country})\n\n"
            f"1. Introduction — who you are and the course you are applying for.\n   [2–3 sentences]\n\n"
            f"2. Academic background — {quals}.\n   [What you studied, results, and the subjects that led you to this course]\n\n"
            + (f"3. Professional experience — {', '.join(h.get('employer', '') for h in em['history'])}.\n   [Your role, responsibilities and what you learned]\n\n" if em["history"] else "3. Professional experience — [if any]\n\n")
            + ("4. Study gap — [what you did during the gap, with dates; refer to your evidence]\n\n" if "study_gap" in fps else "")
            + f"5. Why this course and this institution — [specific modules, faculty, facilities; why not an equivalent course at home]\n\n"
            f"6. Why {country} — [specific, genuine reasons]\n\n"
            f"7. Career plans — {_v(ac.get('career_goal'), 'your realistic plans after graduating and how this course leads to them')}\n\n"
            f"8. Funding — {funding}. [Brief, consistent with your financial documents]\n\n"
            "9. Ties and intention — [your plans and commitments after your studies, stated truthfully]\n" + FOOTER})

    # 3. Circumstance-specific letters
    if "study_gap" in fps:
        drafts.append({"key": "study_gap", "title": "Study gap explanation", "service_code": "study_gap_letter", "text":
            f"To the Visa Officer,\n\nRe: Explanation of study gap — {name}\n\nI completed my last qualification in {_month_year(ac.get('last_completion'))}. "
            f"During the period from then until now I [describe each activity with dates], as shown by [list documents, e.g. employment letter from …].\n\n"
            "This experience [explain truthfully how it relates to your intended course and plans].\n\nYours faithfully,\n" + name + FOOTER})
    if fi.get("funding_source") in ("sponsor", "mixed"):
        drafts.append({"key": "sponsorship", "title": "Sponsorship letter (for your sponsor to sign)", "service_code": "sponsorship_letter", "text":
            f"{today}\n\nTo the Visa Officer,\n\nI, {_v(fi.get('sponsor_name'), 'sponsor full name')}, {_v(fi.get('sponsor_relationship'), 'relationship')} of {name}, "
            f"confirm that I will financially support {name} during their stay in {country}, including [tuition fees / living costs / travel].\n\n"
            f"My income comes from [employment as … at … / business …], as shown in the enclosed [salary slips, employment letter, tax records, bank statements]. "
            "The funds in my account [account ending ….] are available for this purpose.\n\n"
            "Signed: ______________________   Date: __________\n[Sponsor contact details and ID number]" + FOOTER})
    if any(x.startswith("significant_deposits") for x in fps) or fi.get("declared_large_deposits"):
        drafts.append({"key": "financial_explanation", "title": "Explanation of large deposits / source of funds", "service_code": "financial_explanation_letter", "text":
            "To the Visa Officer,\n\nRe: Source of funds\n\nThe following deposits appear in the enclosed bank statements:\n"
            "• [date] — [amount] — [source, e.g. sale of …, maturity of fixed deposit …] — evidence: [document]\n\n"
            "These funds are genuinely available for my application and are not borrowed for the purpose of showing a balance. [Only state this if true.]\n\n"
            f"Yours faithfully,\n{name}" + FOOTER})
    if im.get("previous_refusals"):
        drafts.append({"key": "refusal_response", "title": "Response to previous refusal", "service_code": "explanation_letter", "text":
            "To the Visa Officer,\n\nRe: Previous refusal\n\nI was refused a [visa type] for [country] on [date]. The decision gave these reasons:\n"
            "1. [quote reason] — Since then, [what has changed], supported by [document].\n2. [quote reason] — [response and evidence]\n\n"
            f"Yours faithfully,\n{name}" + FOOTER})
    if em.get("career_change"):
        drafts.append({"key": "career_change", "title": "Career change explanation", "service_code": "employment_explanation_letter", "text":
            "To the Visa Officer,\n\nRe: Change of career direction\n\nMy background is in [field]. I am now [course/job] because [genuine reasons]. "
            "I have prepared for this change by [training, experience — with evidence].\n\n"
            f"Yours faithfully,\n{name}" + FOOTER})
    if f["category"] == "family" or f["family"].get("accompanying_spouse"):
        drafts.append({"key": "relationship", "title": "Relationship statement and timeline", "service_code": "relationship_portfolio", "text":
            "RELATIONSHIP STATEMENT\n\nHow we met: [date, place]\nRelationship began: [date]\nMarried / registered: [date, place]\n"
            "Living together since: [date, address]\nPeriods apart: [dates and reasons, and how you stayed in contact]\n\n"
            "Evidence enclosed (section F): [joint lease, shared bills, joint account, photos with dates, communication records]" + FOOTER})
    if f["applicant"].get("age") is not None and f["applicant"]["age"] < 18:
        drafts.append({"key": "consent", "title": "Parental consent letter", "service_code": "consent_letter", "text":
            f"I/We, [parent names], parent(s) of {name}, born {_v(ap.get('date_of_birth'), 'date of birth')}, consent to their travel to and stay in {country} "
            "for [purpose], and to [living and care arrangements].\n\nSigned: ______________________  Date: __________" + FOOTER})
    return drafts
