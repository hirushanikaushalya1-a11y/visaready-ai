from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import utcnow
from app.models.applications import Application
from app.models.commerce import Payment, PaymentEvent, Refund, ServiceCatalogItem, WritingOrder
from app.models.users import User
from app.services.notifications.service import notify
from app.services.payments.providers import WebhookResult, fmt_amount, get_provider


def start_payment(db: Session, user: User, purpose: str, reference_id: uuid.UUID, service_code: str,
                  amount_cents: int | None = None, currency: str | None = None) -> Payment:
    """Creates (or reuses) a pending payment. Raises 409 if this target is already paid."""
    svc = db.get(ServiceCatalogItem, service_code)
    if not svc or not svc.is_active:
        raise HTTPException(404, "Service not available")
    amount = amount_cents if amount_cents is not None else svc.price_cents
    if amount == 0:
        raise HTTPException(400, "This service is free.")
    if amount is None:
        raise HTTPException(400, "This service requires a quotation before payment.")
    paid = db.scalars(select(Payment).where(Payment.purpose == purpose, Payment.reference_id == reference_id,
                                            Payment.status.in_(("succeeded", "partially_refunded")))).first()
    if paid and purpose != "reassessment":
        raise HTTPException(409, "This item has already been paid for.")
    provider = get_settings().payment_provider
    pending = db.scalars(select(Payment).where(Payment.purpose == purpose, Payment.reference_id == reference_id,
                                               Payment.status == "pending", Payment.user_id == user.id,
                                               Payment.provider == provider, Payment.amount_cents == amount,
                                               Payment.currency == (currency or svc.currency))).first()
    if pending:
        return pending
    p = Payment(user_id=user.id, purpose=purpose, reference_id=reference_id, service_code=service_code, amount_cents=amount,
                currency=currency or svc.currency, provider=provider, provider_order_id=f"VR{uuid.uuid4().hex[:18].upper()}", status="pending")
    db.add(p)
    db.flush()
    audit(db, "payment.created", actor=user, target_type="payment", target_id=p.id, purpose=purpose, amount_cents=amount)
    return p


def _next_invoice_number(db: Session) -> str:
    year = utcnow().year
    n = db.scalar(select(func.count()).select_from(Payment).where(Payment.invoice_number.like(f"VR-{year}-%"))) or 0
    return f"VR-{year}-{n + 1:06d}"


def fulfil(db: Session, p: Payment) -> None:
    """Grant what was bought. Idempotent — only called on the pending->succeeded transition."""
    s = get_settings()
    if p.purpose == "assessment_report":
        notify(db, p.user_id, "payment_confirmed", "Your full assessment report is unlocked",
               f"Payment of {fmt_amount(p.amount_cents)} {p.currency} received (invoice {p.invoice_number}). "
               "Your printable report, submission file and suggested drafts are now available.", link=f"/applications/{p.reference_id}")
    elif p.purpose == "assessment":
        app = db.get(Application, p.reference_id)
        if app and app.status == "draft":
            app.status = "active"
            app.unlocked_at = utcnow()
            app.reassessments_allowed = s.included_reassessments
        notify(db, p.user_id, "payment_confirmed", "Payment received – your assessment is unlocked",
               f"We received your payment of {fmt_amount(p.amount_cents)} {p.currency}. Invoice {p.invoice_number}. "
               "You can now upload documents and run your assessment.", link=f"/applications/{p.reference_id}")
    elif p.purpose == "reassessment":
        app = db.get(Application, p.reference_id)
        if app:
            app.reassessments_allowed += 1
        notify(db, p.user_id, "payment_confirmed", "Additional reassessment purchased",
               f"Payment of {fmt_amount(p.amount_cents)} {p.currency} received. Invoice {p.invoice_number}.", link=f"/applications/{p.reference_id}")
    elif p.purpose == "writing_order":
        from app.services.orders.writing import on_payment_success

        order = db.get(WritingOrder, p.reference_id)
        if order:
            on_payment_success(db, order, p)


def handle_webhook(db: Session, provider_name: str, result: WebhookResult) -> str:
    """Verify, de-duplicate, reconcile and apply a provider notification. Returns an outcome string."""
    payment = db.scalars(select(Payment).where(Payment.provider_order_id == result.provider_order_id).with_for_update()).first() \
        if result.provider_order_id else None
    # Only validly-signed events occupy the de-duplication key; otherwise a forged notification could
    # "claim" a genuine event id and cause the real one to be ignored.
    event_key = result.event_id if result.signature_valid else f"invalid:{uuid.uuid4().hex}"
    event = PaymentEvent(payment_id=payment.id if payment else None, provider=provider_name, provider_event_id=event_key,
                         event_type=result.status, signature_valid=result.signature_valid,
                         payload={k: v for k, v in result.raw.items() if k not in ("card_no", "card_holder_name")}, received_at=utcnow())
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
    except IntegrityError:
        return "duplicate"
    if not result.signature_valid:
        audit(db, "payment.webhook_invalid_signature", target_type="payment", target_id=payment.id if payment else None)
        return "invalid_signature"
    if not payment or payment.provider != provider_name:
        return "unknown_payment"
    if result.status == "succeeded":
        if result.amount is not None and (result.amount != fmt_amount(payment.amount_cents) or result.currency != payment.currency):
            payment.status = "failed"
            payment.failure_reason = f"Amount/currency mismatch: got {result.amount} {result.currency}"
            audit(db, "payment.amount_mismatch", target_type="payment", target_id=payment.id, got=result.amount)
            return "amount_mismatch"
        if payment.status == "succeeded":
            return "already_succeeded"
        payment.status = "succeeded"
        payment.provider_payment_id = result.provider_payment_id
        payment.paid_at = utcnow()
        payment.invoice_number = _next_invoice_number(db)
        audit(db, "payment.succeeded", target_type="payment", target_id=payment.id, amount_cents=payment.amount_cents)
        fulfil(db, payment)
        return "succeeded"
    if result.status in ("failed", "cancelled") and payment.status == "pending":
        payment.status = result.status
        payment.failure_reason = f"Provider reported {result.status}"
        notify(db, payment.user_id, "payment_failed", "Payment was not completed",
               "Your payment was not completed and you have not been charged by us. You can try again from your dashboard.", email=False)
        return result.status
    if result.status == "chargeback":
        audit(db, "payment.chargeback", target_type="payment", target_id=payment.id)
        return "chargeback"
    return "ignored"


def process_refund(db: Session, payment: Payment, amount_cents: int, reason: str, actor: User | None) -> Refund:
    if payment.status not in ("succeeded", "partially_refunded"):
        raise HTTPException(400, "Only successful payments can be refunded.")
    if amount_cents <= 0 or amount_cents > payment.amount_cents - payment.refunded_cents:
        raise HTTPException(400, "Refund amount exceeds the refundable balance.")
    refund = Refund(payment_id=payment.id, amount_cents=amount_cents, reason=reason, status="processing",
                    requested_by_id=actor.id if actor else None)
    db.add(refund)
    db.flush()
    ok, ref, err = get_provider(payment.provider).refund(payment, amount_cents, reason)
    if ok:
        refund.status, refund.provider_refund_id, refund.processed_at = "succeeded", ref, utcnow()
        payment.refunded_cents += amount_cents
        payment.status = "refunded" if payment.refunded_cents >= payment.amount_cents else "partially_refunded"
        notify(db, payment.user_id, "refund_processed", "Your refund has been processed",
               f"We have refunded {fmt_amount(amount_cents)} {payment.currency} to your original payment method. "
               "Depending on your bank or card issuer it can take 5–10 business days (sometimes longer) to appear.")
    else:
        refund.status, refund.failure_reason = "failed", err
    audit(db, "refund.processed", actor=actor, target_type="refund", target_id=refund.id, ok=ok, error=err)
    return refund
