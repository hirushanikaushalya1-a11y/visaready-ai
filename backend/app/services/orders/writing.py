"""24-hour document writing service: state machine and SLA clock.

The 24-hour clock starts ONLY when staff confirm that all required information and documents have
been received (info_complete_at). deadline_at = info_complete_at + WRITING_SLA_HOURS. Delivery after
the deadline makes the order refund-eligible automatically.
"""
from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import utcnow
from app.models.commerce import OrderEvent, Payment, ServiceCatalogItem, WritingOrder
from app.models.users import User
from app.services.notifications.service import notify

TRANSITIONS = {
    "payment_pending": {"payment_successful", "cancelled"},
    "payment_successful": {"awaiting_documents"},
    "awaiting_documents": {"information_incomplete", "submission_complete", "cancelled"},
    "information_incomplete": {"submission_complete", "information_incomplete", "cancelled"},
    "submission_complete": {"processing", "refund_eligible"},
    "processing": {"quality_review", "refund_eligible"},
    "quality_review": {"processing", "delivered", "refund_eligible"},
    "delivered": {"refund_eligible"},
    "refund_eligible": {"refund_processing", "processing", "quality_review"},
    "refund_processing": {"refunded", "refund_eligible"},
    "refunded": set(),
    "cancelled": set(),
}
CLOCK_RUNNING = ("submission_complete", "processing", "quality_review")


def new_reference() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "VRW-" + "".join(secrets.choice(alphabet) for _ in range(7))


def transition(db: Session, order: WritingOrder, to: str, actor: User | None, note: str | None = None) -> None:
    if to not in TRANSITIONS.get(order.status, set()):
        raise HTTPException(409, f"Cannot move an order from '{order.status}' to '{to}'.")
    db.add(OrderEvent(order_type="writing", order_id=order.id, from_status=order.status, to_status=to,
                      actor_id=actor.id if actor else None, note=note, created_at=utcnow()))
    order.status = to


def create_order(db: Session, user: User, service_code: str, application_id=None, notes: str | None = None) -> WritingOrder:
    svc = db.get(ServiceCatalogItem, service_code)
    if not svc or svc.kind != "writing" or not svc.is_active or svc.price_cents is None:
        raise HTTPException(404, "Writing service not available")
    order = WritingOrder(reference=new_reference(), user_id=user.id, application_id=application_id, service_code=svc.code,
                         price_cents=svc.price_cents, currency=svc.currency, customer_notes=notes, status="payment_pending")
    db.add(order)
    db.flush()
    db.add(OrderEvent(order_type="writing", order_id=order.id, from_status=None, to_status="payment_pending",
                      actor_id=user.id, created_at=utcnow()))
    return order


def on_payment_success(db: Session, order: WritingOrder, payment: Payment) -> None:
    if order.status != "payment_pending":
        return
    s = get_settings()
    svc = db.get(ServiceCatalogItem, order.service_code)
    now = utcnow()
    order.paid_at = now
    order.payment_id = payment.id
    transition(db, order, "payment_successful", None, f"Payment {payment.provider_order_id}")
    transition(db, order, "awaiting_documents", None, "Submission instructions sent")
    order.instructions_sent_at = now
    needed = "\n".join(f"  • {x}" for x in (svc.required_information or []))
    notify(db, order.user_id, "writing_order_paid", f"Order {order.reference}: payment confirmed – next steps",
           f"Thank you. Your order reference is {order.reference} ({svc.name}).\n\n"
           f"Please email the following to {s.document_service_email} with '{order.reference}' in the subject line:\n{needed}\n\n"
           f"Your {s.writing_sla_hours}-hour delivery clock starts as soon as we confirm we have everything we need. "
           "We will tell you immediately if anything is missing.", link=f"/orders/{order.id}")


def mark_incomplete(db: Session, order: WritingOrder, actor: User, note: str) -> None:
    transition(db, order, "information_incomplete", actor, note)
    order.missing_information_note = note
    order.info_requested_at = utcnow()
    notify(db, order.user_id, "writing_order_incomplete", f"Order {order.reference}: we need a little more information",
           f"To start your document we still need:\n{note}\n\nPlease reply to {get_settings().document_service_email} "
           f"quoting {order.reference}. The 24-hour clock has not started yet.", link=f"/orders/{order.id}")


def mark_complete(db: Session, order: WritingOrder, actor: User) -> None:
    s = get_settings()
    transition(db, order, "submission_complete", actor, "All information received")
    now = utcnow()
    order.info_complete_at = now
    order.deadline_at = now + timedelta(hours=s.writing_sla_hours)
    order.missing_information_note = None
    notify(db, order.user_id, "writing_order_started", f"Order {order.reference}: your 24-hour clock has started",
           f"We have everything we need. Your document will be delivered by {order.deadline_at.strftime('%d %b %Y %H:%M UTC')}. "
           "If we miss this deadline you are entitled to a full refund of this order's fee.", link=f"/orders/{order.id}")


def start_processing(db: Session, order: WritingOrder, actor: User) -> None:
    transition(db, order, "processing", actor)
    order.processing_started_at = order.processing_started_at or utcnow()
    order.assigned_to_id = order.assigned_to_id or actor.id
    notify(db, order.user_id, "writing_order_processing", f"Order {order.reference} is being prepared",
           "Our document team has started preparing your document.", link=f"/orders/{order.id}", email=False)


def send_to_review(db: Session, order: WritingOrder, actor: User) -> None:
    transition(db, order, "quality_review", actor)
    order.quality_review_at = utcnow()


def deliver(db: Session, order: WritingOrder, actor: User) -> None:
    now = utcnow()
    if order.status == "refund_eligible":
        # Already flagged as late: deliver the document but keep the refund entitlement.
        if order.delivered_at:
            raise HTTPException(409, "This order has already been delivered.")
        db.add(OrderEvent(order_type="writing", order_id=order.id, from_status=order.status, to_status=order.status,
                          actor_id=actor.id, note="Document delivered after the deadline (refund entitlement retained)", created_at=now))
        order.delivered_at = now
        late = True
    else:
        transition(db, order, "delivered", actor)
        order.delivered_at = now
        late = order.deadline_at is not None and now > order.deadline_at
        if late:
            transition(db, order, "refund_eligible", None, "Delivered after the 24-hour deadline")
            order.refund_eligible_at = now
    notify(db, order.user_id, "writing_order_delivered", f"Order {order.reference}: your document is ready",
           "Your document has been delivered. Download it securely from your order page. Please review it carefully and check every fact before use."
           + (" It was delivered after the guaranteed deadline, so you are entitled to a full refund of this order's fee — our team will process it." if late else ""),
           link=f"/orders/{order.id}")


def is_refund_eligible(order: WritingOrder, now=None) -> bool:
    now = now or utcnow()
    if order.deadline_at is None or order.info_complete_at is None:
        return False
    if order.delivered_at:
        return order.delivered_at > order.deadline_at
    return now > order.deadline_at


def sla_sweep(db: Session) -> dict:
    """Run periodically (worker). Flags missed deadlines and alerts staff before deadlines."""
    s = get_settings()
    now = utcnow()
    stats = {"warned": 0, "missed": 0}
    open_orders = db.scalars(select(WritingOrder).where(WritingOrder.status.in_(CLOCK_RUNNING)).with_for_update(skip_locked=True)).all()
    staff = db.scalars(select(User).where(User.role.in_(("document_team", "admin", "super_admin")), User.is_active.is_(True))).all()
    for o in open_orders:
        if o.deadline_at and now > o.deadline_at:
            transition(db, o, "refund_eligible", None, "24-hour deadline passed without delivery")
            o.refund_eligible_at = now
            stats["missed"] += 1
            notify(db, o.user_id, "writing_order_refund_eligible", f"Order {o.reference}: we missed our 24-hour deadline",
                   "We are sorry — your document was not delivered within 24 hours of your complete submission. "
                   "You are entitled to a full refund of this order's fee, which our team will process to your original payment method. "
                   "We will still deliver your document if you wish.", link=f"/orders/{o.id}")
            for u in staff:
                notify(db, u, "admin_sla_missed", f"SLA MISSED: {o.reference}", f"Order {o.reference} passed its deadline and is refund-eligible.",
                       link=f"/admin/orders/{o.id}", email=False)
        elif o.deadline_at and not o.deadline_warning_sent_at and o.deadline_at - now <= timedelta(hours=s.writing_sla_warning_hours):
            o.deadline_warning_sent_at = now
            stats["warned"] += 1
            hrs = max(0, int((o.deadline_at - now).total_seconds() // 3600))
            for u in staff:
                notify(db, u, "admin_sla_warning", f"Deadline approaching: {o.reference}", f"Less than {hrs + 1} hour(s) remain for order {o.reference} (status: {o.status}).",
                       link=f"/admin/orders/{o.id}", email=False)
    return stats


def process_order_refund(db: Session, order: WritingOrder, actor: User) -> None:
    from app.services.payments.service import process_refund

    if order.status != "refund_eligible":
        raise HTTPException(409, "Order is not refund-eligible.")
    payment = db.get(Payment, order.payment_id)
    transition(db, order, "refund_processing", actor)
    refund = process_refund(db, payment, order.price_cents, f"24-hour guarantee: order {order.reference}", actor)
    order.refund_id = refund.id
    if refund.status == "succeeded":
        transition(db, order, "refunded", actor)
    else:
        transition(db, order, "refund_eligible", actor, f"Refund failed: {refund.failure_reason}")
