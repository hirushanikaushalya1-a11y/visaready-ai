"""Country-specific immigration knowledge database. Nothing here is hard-coded in the UI."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, IdMixin, TimestampMixin


class Country(TimestampMixin, Base):
    __tablename__ = "countries"
    code: Mapped[str] = mapped_column(String(2), primary_key=True)  # ISO 3166-1 alpha-2
    name: Mapped[str] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(60))
    is_destination: Mapped[bool] = mapped_column(Boolean, default=False)
    is_source_market: Mapped[bool] = mapped_column(Boolean, default=False)
    # live: requirements populated & verified · pilot: requirements recorded, pending verification
    # · planned: country module registered, no requirements yet
    module_status: Mapped[str] = mapped_column(String(20), default="planned")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    __table_args__ = (CheckConstraint("module_status in ('live','pilot','planned')", name="module_status"),)


class VisaCategory(IdMixin, TimestampMixin, Base):
    __tablename__ = "visa_categories"
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"), index=True)
    category_type: Mapped[str] = mapped_column(String(20))  # student | work | family
    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    official_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    country: Mapped[Country] = relationship()
    __table_args__ = (
        UniqueConstraint("country_code", "code"),
        CheckConstraint("category_type in ('student','work','family')", name="category_type"),
    )


class OfficialSource(IdMixin, TimestampMixin, Base):
    __tablename__ = "official_sources"
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(800), unique=True)
    publisher: Mapped[str] = mapped_column(String(200))  # must be a government / official authority
    is_official: Mapped[bool] = mapped_column(Boolean, default=True)
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_content_hash: Mapped[str | None] = mapped_column(String(64))
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImmigrationRequirement(IdMixin, TimestampMixin, Base):
    __tablename__ = "immigration_requirements"
    visa_category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("visa_categories.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    requirement_level: Mapped[str] = mapped_column(String(20))  # mandatory|conditional|supplementary
    applies_when: Mapped[dict | None] = mapped_column(JSONB)  # condition DSL, see services/evidence/conditions.py
    applies_to_member: Mapped[str] = mapped_column(String(20), default="principal")  # principal|dependant|all
    eligibility_conditions: Mapped[str | None] = mapped_column(Text)
    document_types: Mapped[list] = mapped_column(JSONB, default=list)
    financial_requirement: Mapped[dict | None] = mapped_column(JSONB)  # {amount, currency, period, notes}
    exceptions: Mapped[str | None] = mapped_column(Text)
    translation_required_if_not_english: Mapped[bool] = mapped_column(Boolean, default=False)
    official_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("official_sources.id"))
    source_url: Mapped[str] = mapped_column(String(800))
    source_excerpt: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[date | None] = mapped_column(Date)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    review_status: Mapped[str] = mapped_column(String(20), default="pending_review", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)

    visa_category: Mapped[VisaCategory] = relationship()
    official_source: Mapped[OfficialSource | None] = relationship()
    __table_args__ = (
        UniqueConstraint("visa_category_id", "key"),
        CheckConstraint("requirement_level in ('mandatory','conditional','supplementary')", name="level"),
        CheckConstraint(
            "review_status in ('draft','pending_review','verified','superseded','retired')", name="review_status"
        ),
        # A requirement can only be marked verified when it has a verification date.
        CheckConstraint("review_status <> 'verified' OR last_verified_at IS NOT NULL", name="verified_has_date"),
    )


class RequirementVersion(IdMixin, Base):
    __tablename__ = "requirement_versions"
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("immigration_requirements.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    change_note: Mapped[str | None] = mapped_column(Text)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("requirement_id", "version"),)


class EvidenceRule(IdMixin, TimestampMixin, Base):
    """Evidence logic that is *not* an official requirement: it explains which documents could
    substantiate a claim the applicant made. Never produces 'mandatory' items."""

    __tablename__ = "evidence_rules"
    key: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    category_types: Mapped[list] = mapped_column(JSONB, default=list)  # [] = all
    applies_when: Mapped[dict] = mapped_column(JSONB)
    level: Mapped[str] = mapped_column(String(20), default="conditional")
    document_types: Mapped[list] = mapped_column(JSONB, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    claim_key: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("level in ('conditional','supplementary')", name="level"),)


class PolicyAlert(IdMixin, TimestampMixin, Base):
    __tablename__ = "policy_alerts"
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"), index=True)
    visa_category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visa_categories.id"))
    requirement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("immigration_requirements.id"))
    official_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("official_sources.id"))
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(800))
    effective_date: Mapped[date | None] = mapped_column(Date)
    # detected (source changed, unverified) -> verified (human checked) -> published (applicants notified)
    status: Mapped[str] = mapped_column(String(20), default="detected")
    verified_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    affected_application_count: Mapped[int] = mapped_column(Integer, default=0)
