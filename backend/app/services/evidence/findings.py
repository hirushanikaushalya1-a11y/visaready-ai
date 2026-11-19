from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Finding:
    fingerprint: str
    kind: str  # strength|missing_evidence|inconsistency|concern|question|professional_review|document_quality|refusal_reason
    category: str  # identity|academic|employment|financial|immigration|family|general
    severity: str  # high|medium|low|info
    certainty: str  # confirmed_missing_requirement|potential_concern|requires_professional_judgement|observation
    title: str
    explanation: str
    why_it_matters: str | None = None
    triggers: list[dict] = field(default_factory=list)
    suggested_action: str | None = None
    evidence_suggestions: list[str] = field(default_factory=list)
    confidence: str = "medium"
    requirement_id: str | None = None
    source_url: str | None = None

    def dict(self) -> dict:
        return asdict(self)


def profile_ref(path: str, value=None) -> dict:
    return {"type": "profile", "path": path, "value": None if value is None else str(value)[:200]}


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
