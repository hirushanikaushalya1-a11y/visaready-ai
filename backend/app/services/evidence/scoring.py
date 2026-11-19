"""Explainable readiness score (0-100).

The score measures PREPARATION QUALITY — completeness and consistency of the application file.
It is NOT a probability of approval and is never presented as one.

Components (weights renormalised if a component does not apply):
  profile        20  share of key profile questions answered
  requirements   40  share of applicable official-requirement items with a recognised document
  evidence       20  share of claims supported (partial = half credit)
  consistency    20  starts full; deductions per unresolved inconsistency/concern
Uploading documents only raises the score when a recognised document satisfies a specific item
or claim — unrelated uploads change nothing.
"""
from __future__ import annotations

from app.services.evidence.checklist import ChecklistItem
from app.services.evidence.claims import Claim
from app.services.evidence.findings import Finding

WEIGHTS = {"profile": 20, "requirements": 40, "evidence": 20, "consistency": 20}
DEDUCTIONS = {"high": 6, "medium": 3, "low": 1, "info": 0}
CONSISTENCY_KINDS = {"inconsistency", "concern", "professional_review", "refusal_reason"}


def compute_score(profile_ratio: float, profile_missing: list[str], items: list[ChecklistItem], claims: list[Claim],
                  findings: list[Finding]) -> tuple[int, dict]:
    components: dict[str, dict] = {}

    components["profile"] = {"ratio": round(profile_ratio, 3), "explanation":
                             "All key profile questions answered." if not profile_missing else
                             f"Unanswered: {', '.join(profile_missing)}."}

    req = [i for i in items if i.origin == "requirement" and i.applicability == "applies"]
    if req:
        sat = [i for i in req if i.status == "satisfied"]
        components["requirements"] = {"ratio": round(len(sat) / len(req), 3), "satisfied": len(sat), "total": len(req),
                                      "explanation": f"{len(sat)} of {len(req)} applicable official requirement items have a recognised document."}
    else:
        components["requirements"] = {"ratio": None, "explanation":
                                      "No official requirements are recorded yet for this country and visa type, so this component is excluded from the score."}

    if claims:
        pts = sum(1.0 if c.status == "supported" else 0.5 if c.status in ("partially_supported", "human_review_recommended") else 0.0 for c in claims)
        components["evidence"] = {"ratio": round(pts / len(claims), 3), "supported": sum(c.status == "supported" for c in claims),
                                  "total": len(claims), "explanation": f"{sum(c.status == 'supported' for c in claims)} of {len(claims)} claims fully supported by evidence."}
    else:
        components["evidence"] = {"ratio": None, "explanation": "No claims to evaluate yet — complete your profile."}

    deductions = []
    for f in findings:
        if f.kind in CONSISTENCY_KINDS and DEDUCTIONS[f.severity]:
            deductions.append({"fingerprint": f.fingerprint, "title": f.title, "points": DEDUCTIONS[f.severity]})
    total_ded = sum(d["points"] for d in deductions)
    components["consistency"] = {"ratio": round(max(0.0, (WEIGHTS["consistency"] - total_ded) / WEIGHTS["consistency"]), 3),
                                 "deductions": deductions,
                                 "explanation": "No unresolved inconsistencies or concerns." if not deductions else
                                 f"{len(deductions)} unresolved issue(s) reduce this component."}

    active = {k: w for k, w in WEIGHTS.items() if components[k]["ratio"] is not None}
    scale = 100 / sum(active.values())
    score = 0.0
    for k, w in WEIGHTS.items():
        if k in active:
            pts = components[k]["ratio"] * w * scale
            components[k]["points"] = round(pts, 1)
            components[k]["max_points"] = round(w * scale, 1)
            score += pts
        else:
            components[k]["points"] = None
            components[k]["max_points"] = 0
    return int(round(score)), {"components": components, "weights": WEIGHTS,
                               "note": "Readiness reflects how complete and consistent your application preparation is. It is not a probability of visa approval."}
