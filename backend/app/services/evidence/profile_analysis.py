"""Profile-level concerns, the decision-maker question simulator, and strengths."""
from __future__ import annotations

from app.services.evidence.checklist import ChecklistItem
from app.services.evidence.claims import Claim
from app.services.evidence.findings import Finding, profile_ref

PROFILE_FIELDS = [
    ("applicant.full_name", "Full name"), ("applicant.date_of_birth", "Date of birth"),
    ("applicant.nationality", "Nationality"), ("applicant.residence", "Country of residence"),
    ("applicant.passport_number", "Passport number"), ("applicant.passport_expiry", "Passport expiry"),
    ("applicant.marital_status", "Marital status"), ("financial.funding_source", "How you will fund your application"),
    ("immigration.previous_refusals", "Previous refusals question"), ("employment.status", "Current employment status"),
]
STUDENT_FIELDS = [("academic.qualification_count", "Previous qualifications"), ("academic.course_name", "Intended course"),
                  ("academic.institution", "Intended institution")]
WORK_FIELDS = [("employment.job_offer_employer", "Job offer employer"), ("employment.history_count", "Employment history")]
FAMILY_FIELDS = [("family.relation_to_principal", "Relationship to main applicant"), ("family.principal_name", "Main applicant's name")]


def _get(facts: dict, path: str):
    cur = facts
    for p in path.split("."):
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur


def profile_completeness(facts: dict) -> tuple[float, list[str]]:
    fields = PROFILE_FIELDS + {"student": STUDENT_FIELDS, "work": WORK_FIELDS, "family": FAMILY_FIELDS}[facts["category"]]
    missing = [label for path, label in fields if _get(facts, path) in (None, "", 0) and not (path == "immigration.previous_refusals" and _get(facts, path) == 0)]
    return (len(fields) - len(missing)) / len(fields), missing


def profile_concerns(facts: dict) -> list[Finding]:
    out: list[Finding] = []
    ac, em, fi, im = facts["academic"], facts["employment"], facts["financial"], facts["immigration"]
    cat = facts["category"]

    gap = ac.get("study_gap_months")
    if cat == "student" and gap is not None and gap >= 12:
        sev = "medium" if gap >= 24 else "low"
        out.append(Finding(
            fingerprint="study_gap", kind="concern", category="academic", severity=sev, certainty="potential_concern",
            title=f"Study gap of about {gap // 12} year(s) {gap % 12} month(s)",
            explanation=f"Your last qualification was completed in {ac['last_completion'][:7]} and your course starts later, leaving a gap of {gap} months.",
            why_it_matters="Decision-makers may want to understand what you did during the gap and why you are returning to study now.",
            triggers=[profile_ref("academic.qualifications", ac["last_completion"]), profile_ref("application.details.course_start")],
            suggested_action="Prepare a truthful explanation of the gap supported by evidence (employment letters, training certificates, other records).",
            evidence_suggestions=["Employment letters for the gap period", "Training or short-course certificates", "Study gap explanation letter"],
        ))
    if cat == "student" and ac.get("course_related_to_previous") == "no":
        out.append(Finding(
            fingerprint="course_unrelated", kind="concern", category="academic", severity="medium", certainty="potential_concern",
            title="Your intended course is not related to your previous studies or work",
            explanation="You indicated that the course does not build on your previous education or experience.",
            why_it_matters="Changes of direction are acceptable, but you may need to explain how the course fits your plans and why it is a logical step.",
            triggers=[profile_ref("application.details.course_related_to_previous", "no")],
            suggested_action="Explain the reason for the change and how the course supports a realistic career plan in your statement of purpose.",
        ))
    if fi.get("funding_source") in ("sponsor", "mixed") and not fi.get("sponsor_name"):
        out.append(Finding(
            fingerprint="sponsor_details_missing", kind="missing_evidence", category="financial", severity="medium",
            certainty="potential_concern", title="Sponsor details are incomplete",
            explanation="You said a sponsor will fund your application but have not entered their name and relationship.",
            why_it_matters="We need these details to check the sponsor's documents against your claim.",
            triggers=[profile_ref("financial.sponsor")], suggested_action="Add your sponsor's full name (as on their bank records), relationship and employment type."))
    if fi.get("funding_source") is None:
        out.append(Finding(
            fingerprint="funding_unknown", kind="missing_evidence", category="financial", severity="medium", certainty="potential_concern",
            title="Funding source not declared", explanation="You have not told us how your studies, stay or move will be funded.",
            why_it_matters="Financial capacity is assessed in most visa categories.", triggers=[profile_ref("financial.funding_source")],
            suggested_action="Complete the financial section of your profile."))
    if fi.get("declared_large_deposits") and not fi.get("large_deposit_explanation"):
        out.append(Finding(
            fingerprint="large_deposit_unexplained", kind="concern", category="financial", severity="medium", certainty="potential_concern",
            title="Large deposits declared without an explanation",
            explanation="You indicated there are large recent deposits in the accounts you are relying on.",
            why_it_matters="The origin of recently deposited funds is frequently questioned.",
            triggers=[profile_ref("financial.declared_large_deposits", True)],
            suggested_action="Describe the origin of each large deposit and upload documents that prove it."))
    if im.get("overstays"):
        out.append(Finding(
            fingerprint="overstay", kind="professional_review", category="immigration", severity="high",
            certainty="requires_professional_judgement", title="Previous overstay declared",
            explanation="You declared a previous overstay or breach of visa conditions.",
            why_it_matters="Previous immigration breaches can affect eligibility in some routes and must be disclosed accurately. The effect depends on the specific rules and circumstances.",
            triggers=[profile_ref("immigration.overstays", True)],
            suggested_action="We recommend advice from a qualified immigration adviser or lawyer before applying."))
    if im.get("previous_refusals"):
        out.append(Finding(
            fingerprint="previous_refusal", kind="concern", category="immigration", severity="medium", certainty="potential_concern",
            title="Previous visa refusal(s) declared",
            explanation=f"You declared {im['previous_refusals']} previous refusal(s).",
            why_it_matters="A refusal is not a bar in itself, but the reasons given should be addressed by your current evidence, and the refusal must be disclosed truthfully.",
            triggers=[profile_ref("immigration.previous_refusals", im["previous_refusals"])],
            suggested_action="Upload each refusal decision so we can compare its reasons with your current application."))
    if im.get("previous_refusals") is None:
        out.append(Finding(
            fingerprint="refusal_question_unanswered", kind="missing_evidence", category="immigration", severity="low",
            certainty="observation", title="Immigration history not completed",
            explanation="You have not yet answered whether you have ever been refused a visa.",
            why_it_matters="Almost every application form asks this question.", triggers=[profile_ref("immigration.previous_refusals")],
            suggested_action="Complete the immigration history section."))
    if em.get("career_change") and cat in ("student", "work"):
        out.append(Finding(
            fingerprint="career_change", kind="concern", category="employment", severity="low", certainty="potential_concern",
            title="Change of career direction",
            explanation="You indicated your plans involve a change of career.",
            why_it_matters="A clear explanation of why the change makes sense helps the decision-maker follow your plans.",
            triggers=[profile_ref("employment.career_change", True)],
            suggested_action="Explain the change and include evidence of relevant skills or preparation."))
    return out


def questions(facts: dict, findings: list[Finding]) -> list[Finding]:
    """'What questions could your application raise?' — preparation prompts, not predictions."""
    q: list[Finding] = []
    ac, em, fi, im, fa = (facts[k] for k in ("academic", "employment", "financial", "immigration", "family"))
    fps = {f.fingerprint for f in findings}

    def add(fp, category, title, explanation, evidence):
        q.append(Finding(fingerprint=f"q:{fp}", kind="question", category=category, severity="info", certainty="observation",
                         title=title, explanation=explanation, evidence_suggestions=evidence,
                         suggested_action="Prepare a truthful answer and make sure your documents support it. Do not create explanations that are not true.",
                         why_it_matters="This is a question a decision-maker could reasonably want answered. It is a preparation exercise, not a prediction of any decision."))

    if facts["category"] == "student":
        if ac.get("course_name"):
            add("why_course", "academic", f"Why did you choose {ac['course_name']}" + (f" at {ac['institution']}" if ac.get("institution") else "") + "?",
                "Explain what attracted you to this specific course and institution, and what alternatives you considered.",
                ["Statement of purpose", "Course comparison notes", "Offer letter"])
        if ac.get("course_related_to_previous") in ("no", "partly") or "course_unrelated" in fps:
            add("course_progression", "academic", "How does this course relate to your previous education and experience?",
                "Explain how the course builds on, or deliberately changes, your academic and career path.",
                ["Transcripts", "CV", "Employer letters"])
        if "study_gap" in fps:
            add("study_gap", "academic", "What did you do during your study gap?",
                "Describe your activities during the gap period with dates.", ["Employment letters", "Training certificates", "Study gap explanation"])
        if ac.get("career_goal") is None:
            add("career_plans", "academic", "What will you do after completing the course?",
                "Explain realistic plans after your studies.", ["Statement of purpose", "Evidence of job market research or employer interest"])
    if fi.get("funding_source") in ("sponsor", "mixed"):
        rel = fi.get("sponsor_relationship") or "sponsor"
        add("sponsor_source", "financial", f"What is the source of your {rel}'s funds?",
            "Explain how your sponsor earned or accumulated the money and that it is available for your use.",
            ["Sponsor's income evidence", "Sponsor's bank statements", "Tax records"])
        if rel not in ("father", "mother", "parent", "spouse", "self"):
            add("sponsor_why", "financial", f"Why is your {rel} sponsoring you?",
                "Sponsorship by someone other than a parent or spouse is often examined more closely; explain the relationship and the reason.",
                ["Relationship evidence", "Sponsorship letter"])
    if "large_deposit_unexplained" in fps or any(f.fingerprint.startswith("significant_deposits") for f in findings):
        add("deposits", "financial", "Where did the large deposits in your bank account come from?",
            "Identify each large deposit and the document proving its source.", ["Sale deed", "Gift deed", "Loan letter", "FD maturity advice"])
    if em.get("career_change"):
        add("career_change", "employment", "Why are you changing careers?", "Explain the reason and your preparation for the change.",
            ["CV", "Training certificates"])
    if em.get("history_count"):
        add("employment_evidence", "employment", "What evidence supports your employment history?",
            "Each declared role should be backed by an employer letter with dates and duties.", ["Employer letters", "Salary slips", "Tax records"])
    if im.get("previous_refusals"):
        add("refusal_change", "immigration", "What has changed since your previous refusal?",
            "Explain how your circumstances or evidence now address the reasons for refusal.", ["Refusal letter", "New evidence addressing each reason"])
    if fa.get("members"):
        add("family_relationship", "family", "What supports the relationship with each family member included?",
            "Each relationship should be evidenced by civil records and, for partners, evidence of a genuine relationship.",
            ["Marriage certificate", "Birth certificates", "Joint finances, photos, communication"])
    return q


def strengths(facts: dict, items: list[ChecklistItem], claims: list[Claim], findings: list[Finding]) -> list[Finding]:
    s: list[Finding] = []
    identity_issues = [f for f in findings if f.category == "identity" and f.kind == "inconsistency"]
    ident = next((c for c in claims if c.claim_key == "identity"), None)
    if ident and ident.status == "supported" and not identity_issues:
        s.append(Finding("strength:identity", "strength", "identity", "info", "observation", "Identity details are consistent",
                         "Your passport was recognised and its details agree with your profile."))
    acad = [c for c in claims if c.claim_key.startswith("academic.qualification")]
    if acad and all(c.status == "supported" for c in acad):
        s.append(Finding("strength:academic", "strength", "academic", "info", "observation", "Academic history is fully evidenced",
                         "Every qualification you listed has a matching certificate and transcript."))
    fin = [c for c in claims if c.category == "financial"]
    if fin and all(c.status == "supported" for c in fin):
        s.append(Finding("strength:financial", "strength", "financial", "info", "observation", "Funding evidence is in place",
                         "The financial claims you made are backed by recognised documents from the right account holders."))
    emp = [c for c in claims if c.category == "employment"]
    if emp and all(c.status == "supported" for c in emp):
        s.append(Finding("strength:employment", "strength", "employment", "info", "observation", "Employment history is evidenced",
                         "Each declared role is supported by employer documents."))
    req_items = [i for i in items if i.origin == "requirement" and i.applicability == "applies"]
    if req_items and all(i.status == "satisfied" for i in req_items):
        s.append(Finding("strength:requirements", "strength", "general", "info", "observation", "All recorded requirements have matching documents",
                         "Every official requirement in our knowledge base for this visa has a recognised document uploaded."))
    return s
