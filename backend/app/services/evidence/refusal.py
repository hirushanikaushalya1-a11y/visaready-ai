"""Previous Refusal Analysis — extracts the reasons stated in a refusal decision and checks whether
the current application's evidence addresses each one. Deterministic (sentence cues + topic
keywords); quotes the exact sentence and page so applicants can verify every reason."""
from __future__ import annotations

import re

from app.services.evidence.claims import Claim
from app.services.evidence.facts import DocInfo
from app.services.evidence.findings import Finding

CUES = re.compile(r"not satisfied|not been satisfied|have not (?:demonstrated|shown|provided)|has not (?:demonstrated|shown|provided)|"
                  r"failed to|insufficient|unable to (?:verify|confirm|accept)|i am not|i have refused|therefore refuse|"
                  r"does not meet|do not meet|not genuine|not credible|doubts? about|concerns? (?:about|that)|inconsisten", re.I)
TOPICS = {
    "financial": (r"fund|financ|bank|maintenance|money|deposit|sponsor|income|salary", ["financial.own_funds", "financial.sponsorship"],
                  "Show that funds are genuinely available and explain their source."),
    "genuineness": (r"genuine|intention|intend|credib|bona fide|purpose|motivat|study plan|course choice", ["academic.study_plan"],
                    "Explain your study or travel purpose clearly and consistently, supported by evidence."),
    "ties": (r"ties|return|home country|circumstances in", [],
             "Provide evidence of your circumstances and commitments that relate to the concern raised."),
    "documents": (r"document|evidence|not provided|verify|verification|certified|translation", [],
                  "Make sure every requested document is included, complete and translated where needed."),
    "english": (r"english|language|ielts|toefl|pte", ["academic.english"], "Provide an accepted English language test or exemption evidence."),
    "academic": (r"qualification|academic|progression|gap|previous stud", ["academic.qualification.0"],
                 "Explain your academic progression and any gaps with evidence."),
    "employment": (r"employ|job|work experience|occupation|employer", ["employment.history.0", "employment.job_offer"],
                   "Provide clear employer evidence for your declared employment."),
    "immigration_history": (r"previous|overstay|breach|immigration history|travel history", [],
                            "Disclose your immigration history fully and accurately."),
    "deception": (r"decept|false|misrepresent|forged|fraud", [],
                  "A finding of deception or false documents can carry serious long-term consequences. Seek advice from a qualified immigration adviser or lawyer."),
}


def analyse_refusal(doc: DocInfo, claims: list[Claim]) -> tuple[list[dict], list[Finding]]:
    reasons: list[dict] = []
    for page, text in sorted(doc.pages.items()):
        flat = re.sub(r"\s+", " ", text)
        for sent in re.split(r"(?<=[.!?])\s+", flat):
            if len(sent) < 25 or not CUES.search(sent):
                continue
            topics = [t for t, (rx, _, _) in TOPICS.items() if re.search(rx, sent, re.I)] or ["general"]
            reasons.append({"quote": sent[:500], "page": page, "topics": topics})
    reasons = reasons[:15]
    by_key = {c.claim_key: c for c in claims}
    findings: list[Finding] = []
    for i, r in enumerate(reasons):
        addressed, related_status = [], []
        for t in r["topics"]:
            if t == "general":
                continue
            for ck in TOPICS[t][1]:
                c = by_key.get(ck)
                if c:
                    related_status.append({"claim": c.claim_key, "status": c.status})
                    if c.status == "supported":
                        addressed.append(c.claim_key)
        r["evidence_status"] = related_status
        deception = "deception" in r["topics"]
        resolved = bool(related_status) and all(x["status"] == "supported" for x in related_status)
        advice = " ".join(TOPICS[t][2] for t in r["topics"] if t in TOPICS)
        findings.append(Finding(
            fingerprint=f"refusal:{doc.id}:{i}", kind="professional_review" if deception else "refusal_reason",
            category="immigration", severity="high" if deception else ("low" if resolved else "medium"),
            certainty="requires_professional_judgement" if deception else "potential_concern",
            title=("Previous refusal reason: " + ", ".join(t.replace("_", " ") for t in r["topics"])),
            explanation=f"The decision said: “{r['quote']}”" + (
                " Your current evidence for the related claims is recognised as supported." if resolved else
                " Your current application does not yet clearly address this." if related_status else
                " We could not automatically link this reason to your current evidence; review it carefully."),
            why_it_matters="Decision-makers can see previous decisions. Showing how each stated concern has been addressed is important. Addressing these reasons does not guarantee a different outcome.",
            triggers=[doc.ref(r["page"], r["quote"][:200])], suggested_action=advice or "Review this reason and address it with evidence.",
            confidence="medium",
        ))
    return reasons, findings
