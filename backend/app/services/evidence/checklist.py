"""Personalised checklist builder.

Two origins, never confused:
* requirement   — an official requirement from the knowledge base. Only these may be 'mandatory'.
* evidence_rule — evidence that would substantiate something the applicant declared. Never mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.models.knowledge import EvidenceRule, ImmigrationRequirement
from app.services.evidence.conditions import evaluate
from app.services.evidence.facts import DocInfo

# Which document owner an evidence rule's documents must belong to (by claim key).
OWNER_BY_CLAIM = {
    "financial.sponsorship": "sponsor",
    "financial.sponsor_income": "sponsor",
    "financial.own_funds": "applicant",
}
# Relationship evidence (e.g. birth certificate linking you to a parent sponsor) belongs to the applicant.
OWNER_EXEMPT_TYPES = {"birth_certificate", "relationship_evidence", "sponsorship_letter", "affidavit"}


@dataclass
class ChecklistItem:
    item_key: str
    title: str
    reason: str
    origin: str
    level: str
    classifications: list[str]
    status: str
    document_types: list[str]
    matched_document_ids: list[str] = field(default_factory=list)
    unconfirmed_document_ids: list[str] = field(default_factory=list)
    requirement_id: str | None = None
    evidence_rule_id: str | None = None
    claim_key: str | None = None
    source_url: str | None = None
    source_verified: bool = False
    last_verified_at: datetime | None = None
    applicability: str = "applies"  # applies | may_apply
    sort_order: int = 100
    owner: str | None = None


def _match_docs(item_key: str, types: list[str], docs: list[DocInfo], owner: str | None) -> tuple[list[DocInfo], list[DocInfo]]:
    confirmed, unconfirmed = [], []
    for d in docs:
        if d.status not in ("processed", "uploaded", "processing"):
            continue
        type_ok = d.confirmed and d.effective_type in types
        linked = d.checklist_item_key == item_key
        owner_ok = owner is None or d.effective_type in OWNER_EXEMPT_TYPES or d.owner == owner
        if type_ok and owner_ok:
            confirmed.append(d)
        elif (linked or (d.effective_type in types)) and d.status == "processed":
            unconfirmed.append(d)
        elif linked or (d.declared_type in types and d.status != "processed"):
            unconfirmed.append(d)
    return confirmed, unconfirmed


def build_checklist(facts: dict, requirements: list[ImmigrationRequirement], rules: list[EvidenceRule], docs: list[DocInfo]) -> list[ChecklistItem]:
    items: list[ChecklistItem] = []
    covered_types: set[str] = set()

    for req in requirements:
        applies = evaluate(req.applies_when, facts)
        if applies is False:
            continue
        key = f"req:{req.key}"
        classes: list[str] = []
        if req.requirement_level == "mandatory" and applies is True:
            classes.append("mandatory")
        elif req.requirement_level in ("mandatory", "conditional"):
            classes.append("conditionally_required")
        else:
            classes.append("additional_supporting")
        if req.review_status != "verified":
            classes.append("requires_verification")
        if applies is None:
            classes.append("requires_clarification")

        if req.translation_required_if_not_english and not req.document_types:
            # Translation requirement: about the other documents.
            needing = [d for d in docs if d.non_english]
            status = "missing" if needing else "satisfied"
            if needing:
                classes += ["requires_certified_translation", "missing"]
            items.append(ChecklistItem(
                item_key=key, title=req.title, origin="requirement", level=req.requirement_level, classifications=classes,
                status=status, document_types=[], unconfirmed_document_ids=[d.id for d in needing],
                reason=(f"{req.description} We detected non-English text in: {', '.join(d.filename for d in needing)}." if needing else req.description),
                requirement_id=str(req.id), source_url=req.source_url, source_verified=req.review_status == "verified",
                last_verified_at=req.last_verified_at, applicability="applies" if applies else "may_apply", sort_order=req.sort_order,
            ))
            continue

        confirmed, unconfirmed = _match_docs(key, req.document_types, docs, None)
        if confirmed:
            status = "satisfied"
        elif unconfirmed:
            status = "uploaded_unconfirmed"
            classes.append("requires_clarification")
        else:
            status = "missing"
            classes.append("missing")
        if any(d.non_english for d in confirmed + unconfirmed):
            classes.append("requires_certified_translation")
        reason = req.description
        if applies is None:
            reason += " This may apply to you — complete your profile so we can tell."
        if req.eligibility_conditions:
            reason += f" ({req.eligibility_conditions})"
        items.append(ChecklistItem(
            item_key=key, title=req.title, origin="requirement", level=req.requirement_level, classifications=classes,
            status=status, document_types=list(req.document_types), matched_document_ids=[d.id for d in confirmed],
            unconfirmed_document_ids=[d.id for d in unconfirmed], reason=reason, requirement_id=str(req.id),
            source_url=req.source_url, source_verified=req.review_status == "verified", last_verified_at=req.last_verified_at,
            applicability="applies" if applies else "may_apply", sort_order=req.sort_order,
        ))
        if applies:
            covered_types.update(req.document_types)

    for rule in rules:
        applies = evaluate(rule.applies_when, facts)
        if applies is not True:
            continue  # evidence rules only fire on things the applicant actually declared
        owner = OWNER_BY_CLAIM.get(rule.claim_key or "")
        if owner is None and rule.document_types and set(rule.document_types) <= covered_types:
            continue  # already covered by an official requirement item
        key = f"ev:{rule.key}"
        classes = ["conditionally_required" if rule.level == "conditional" else "additional_supporting"]
        confirmed, unconfirmed = _match_docs(key, rule.document_types, docs, owner)
        if confirmed:
            status = "satisfied"
        elif unconfirmed:
            status = "uploaded_unconfirmed"
            classes.append("requires_clarification")
        else:
            status = "missing"
            classes.append("missing")
        if any(d.non_english for d in confirmed + unconfirmed):
            classes.append("requires_certified_translation")
        if rule.key == "previous-refusal-letter":
            classes.append("human_review_recommended")
        items.append(ChecklistItem(
            item_key=key, title=rule.title, origin="evidence_rule", level=rule.level, classifications=classes, status=status,
            document_types=list(rule.document_types), matched_document_ids=[d.id for d in confirmed],
            unconfirmed_document_ids=[d.id for d in unconfirmed], reason=rule.explanation, evidence_rule_id=str(rule.id),
            claim_key=rule.claim_key, sort_order=500, owner=owner,
        ))
    return items
