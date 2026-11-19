from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, IdMixin, TimestampMixin
from app.models.knowledge import Country, VisaCategory


class Application(IdMixin, TimestampMixin, Base):
    __tablename__ = "applications"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"))
    visa_category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visa_categories.id"))
    title: Mapped[str] = mapped_column(String(200))
    # draft -> active (paid) -> completed -> archived
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)  # category-specific answers
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reassessments_allowed: Mapped[int] = mapped_column(Integer, default=0)
    assessments_run: Mapped[int] = mapped_column(Integer, default=0)
    retention_delete_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    country: Mapped[Country] = relationship()
    visa_category: Mapped[VisaCategory] = relationship()
    family_members: Mapped[list[FamilyMember]] = relationship(back_populates="application", cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint("status in ('draft','active','completed','archived')", name="status"),
    )


class FamilyMember(IdMixin, TimestampMixin, Base):
    __tablename__ = "family_members"
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(30))  # spouse | partner | child | parent | other
    full_name: Mapped[str] = mapped_column(String(200))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    included_in_application: Mapped[bool] = mapped_column(Boolean, default=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    application: Mapped[Application] = relationship(back_populates="family_members")


class ChecklistItemState(IdMixin, TimestampMixin, Base):
    """Applicant-controlled state that persists across assessment versions."""

    __tablename__ = "checklist_item_states"
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    item_key: Mapped[str] = mapped_column(String(200))
    collected: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("application_id", "item_key"),)


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    family_member_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("family_members.id", ondelete="SET NULL"))
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(300))
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary)
    declared_type: Mapped[str | None] = mapped_column(String(60))
    detected_type: Mapped[str | None] = mapped_column(String(60))
    classification_confidence: Mapped[float | None] = mapped_column(Float)
    classification_method: Mapped[str | None] = mapped_column(String(30))
    checklist_item_key: Mapped[str | None] = mapped_column(String(200))
    # uploaded -> processing -> processed | failed ; deleted (soft, blob purged)
    status: Mapped[str] = mapped_column(String(20), default="uploaded", index=True)
    processing_error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    language_hint: Mapped[str | None] = mapped_column(String(10))
    quality: Mapped[dict] = mapped_column(JSONB, default=dict)  # readability, low-ocr pages, missing-page hints
    replaces_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pages: Mapped[list[DocumentPage]] = relationship(cascade="all, delete-orphan", order_by="DocumentPage.page_number")
    fields: Mapped[list[ExtractedField]] = relationship(cascade="all, delete-orphan")


class DocumentPage(IdMixin, Base):
    __tablename__ = "document_pages"
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    method: Mapped[str] = mapped_column(String(20))  # pdf_text | ocr | plain
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("document_id", "page_number"),)


class ExtractedField(IdMixin, Base):
    __tablename__ = "extracted_fields"
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    snippet: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    method: Mapped[str] = mapped_column(String(20))  # mrz | pattern | ai | user


class Assessment(IdMixin, Base):
    __tablename__ = "assessments"
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|completed|failed
    readiness_score: Mapped[int | None] = mapped_column(Integer)
    score_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    knowledge_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)  # requirement id -> version used
    engine_version: Mapped[str] = mapped_column(String(20))
    ai_provider: Mapped[str] = mapped_column(String(30), default="none")
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    scenario: Mapped[dict | None] = mapped_column(JSONB)  # set for What-If simulations (never billed/saved as official)
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("uq_assessment_version", "application_id", "version", unique=True, postgresql_where="is_simulation = false"),
    )


class AssessmentFinding(IdMixin, Base):
    __tablename__ = "assessment_findings"
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(200))  # stable across versions, used for diffing
    kind: Mapped[str] = mapped_column(String(30))
    # strength | missing_evidence | inconsistency | concern | question | professional_review | document_quality
    category: Mapped[str] = mapped_column(String(30))  # identity|academic|employment|financial|immigration|family|general
    severity: Mapped[str] = mapped_column(String(10))  # high|medium|low|info
    certainty: Mapped[str] = mapped_column(String(40))
    # confirmed_missing_requirement | potential_concern | requires_professional_judgement | observation
    title: Mapped[str] = mapped_column(String(300))
    explanation: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str | None] = mapped_column(Text)
    triggers: Mapped[list] = mapped_column(JSONB, default=list)  # [{type: document|profile, ref, page, snippet}]
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("immigration_requirements.id", ondelete="SET NULL"))
    source_url: Mapped[str | None] = mapped_column(String(800))
    suggested_action: Mapped[str | None] = mapped_column(Text)
    evidence_suggestions: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[str] = mapped_column(String(10), default="medium")


class AssessmentChecklistItem(IdMixin, Base):
    __tablename__ = "assessment_checklist_items"
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    item_key: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(20))  # requirement | evidence_rule
    level: Mapped[str] = mapped_column(String(20))
    classifications: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30))  # satisfied|uploaded_unconfirmed|missing|needs_clarification
    document_types: Mapped[list] = mapped_column(JSONB, default=list)
    matched_document_ids: Mapped[list] = mapped_column(JSONB, default=list)
    family_member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("immigration_requirements.id", ondelete="SET NULL"))
    evidence_rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("evidence_rules.id", ondelete="SET NULL"))
    source_url: Mapped[str | None] = mapped_column(String(800))
    source_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sort_order: Mapped[int] = mapped_column(Integer, default=100)


class AssessmentClaim(IdMixin, Base):
    """Proof Builder: a claim the applicant makes, and the evidence that does / does not support it."""

    __tablename__ = "assessment_claims"
    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    claim_key: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30))
    statement: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(200))  # profile path the claim came from
    status: Mapped[str] = mapped_column(String(30))
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    # [{document_type, label, required: bool, document_ids: [], state: present|missing|conflicting}]
    related_finding_fingerprints: Mapped[list] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text)


class RefusalAnalysis(IdMixin, TimestampMixin, Base):
    __tablename__ = "refusal_analyses"
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    reasons: Mapped[list] = mapped_column(JSONB, default=list)  # [{reason, quote, page, category, addressed_by: []}]
    method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="completed")
