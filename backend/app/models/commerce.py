from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, IdMixin, TimestampMixin


class ServiceCatalogItem(TimestampMixin, Base):
    """Prices live here (admin-editable), never in frontend code."""

    __tablename__ = "service_catalog"
    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))  # assessment|writing|translation|review|reassessment
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    price_cents: Mapped[int | None] = mapped_column(Integer)  # None => quotation required
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    sla_hours: Mapped[int | None] = mapped_column(Integer)
    required_information: Mapped[list] = mapped_column(JSONB, default=list)
    inclusions: Mapped[list] = mapped_column(JSONB, default=list)
    exclusions: Mapped[list] = mapped_column(JSONB, default=list)
    disclaimer: Mapped[str | None] = mapped_column(Text)
    # Destinations where this service may not be sold (e.g. regulated immigration advice).
    restricted_countries: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)


class Payment(IdMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(30))
    reference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)  # application / order id
    service_code: Mapped[str] = mapped_column(ForeignKey("service_catalog.code"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    provider: Mapped[str] = mapped_column(String(30))
    provider_order_id: Mapped[str] = mapped_column(String(100), unique=True)  # our id sent to the provider
    provider_payment_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    invoice_number: Mapped[str | None] = mapped_column(String(40), unique=True)
    refunded_cents: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        CheckConstraint(
            "status in ('pending','succeeded','failed','cancelled','refunded','partially_refunded')", name="status"
        ),
        CheckConstraint("amount_cents >= 0", name="amount_nonneg"),
        # Duplicate-payment protection: at most one *successful* payment per purpose+target.
        Index(
            "uq_payment_success_per_target",
            "purpose",
            "reference_id",
            unique=True,
            postgresql_where="status in ('succeeded','partially_refunded')",
        ),
        UniqueConstraint("provider", "provider_payment_id"),
    )


class PaymentEvent(IdMixin, Base):
    __tablename__ = "payment_events"
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    provider_event_id: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(60))
    signature_valid: Mapped[bool] = mapped_column(Boolean)
    payload: Mapped[dict] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("provider", "provider_event_id"),)


class Refund(IdMixin, TimestampMixin, Base):
    __tablename__ = "refunds"
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="requested")  # requested|processing|succeeded|failed
    provider_refund_id: Mapped[str | None] = mapped_column(String(100))
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (CheckConstraint("amount_cents > 0", name="amount_pos"),)


class WritingOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "writing_orders"
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"))
    service_code: Mapped[str] = mapped_column(ForeignKey("service_catalog.code"))
    price_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(30), default="payment_pending", index=True)
    customer_notes: Mapped[str | None] = mapped_column(Text)
    missing_information_note: Mapped[str | None] = mapped_column(Text)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # --- SLA timeline -------------------------------------------------------
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    instructions_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    info_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    info_complete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # clock starts
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quality_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_warning_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refund_eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refund_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refunds.id"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"))


class OrderEvent(IdMixin, Base):
    __tablename__ = "order_events"
    order_type: Mapped[str] = mapped_column(String(20))  # writing | translation
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TranslationOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "translation_orders"
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    language_pair: Mapped[str] = mapped_column(String(10))  # si-en | ta-en
    page_count: Mapped[int | None] = mapped_column(Integer)
    quote_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    translation_type: Mapped[str] = mapped_column(String(20), default="sworn")  # sworn | ai_draft
    status: Mapped[str] = mapped_column(String(30), default="quote_requested")
    # quote_requested -> quoted -> payment_pending -> paid -> assigned -> in_progress -> quality_review -> delivered
    translator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("translators.id"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HumanReviewRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "human_review_requests"
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assessments.id", ondelete="SET NULL"))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("professional_reviewers.id"))
    status: Mapped[str] = mapped_column(String(30), default="payment_pending")
    comments: Mapped[list] = mapped_column(JSONB, default=list)
    requires_legal_advice: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"))


class Deliverable(IdMixin, Base):
    """Encrypted files produced by staff (writing / translation outputs)."""

    __tablename__ = "deliverables"
    order_type: Mapped[str] = mapped_column(String(20))
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(300))
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
