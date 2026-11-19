from __future__ import annotations

import html
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, owned_application
from app.models.applications import Application
from app.models.commerce import Payment, Refund, ServiceCatalogItem, WritingOrder
from app.models.users import ApplicantProfile, User
from app.services.payments.providers import SandboxProvider, fmt_amount, get_provider
from app.services.payments.service import handle_webhook, start_payment

router = APIRouter(prefix="/payments", tags=["payments"])


class CheckoutIn(BaseModel):
    purpose: str
    reference_id: uuid.UUID


def payment_out(p: Payment) -> dict:
    return {"id": str(p.id), "purpose": p.purpose, "reference_id": str(p.reference_id), "service_code": p.service_code,
            "amount": fmt_amount(p.amount_cents), "amount_cents": p.amount_cents, "currency": p.currency, "provider": p.provider,
            "status": p.status, "invoice_number": p.invoice_number, "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "refunded": fmt_amount(p.refunded_cents), "created_at": p.created_at.isoformat(), "failure_reason": p.failure_reason}


@router.get("/config")
def payment_config():
    s = get_settings()
    return {"provider": s.payment_provider, "is_sandbox": s.payment_provider == "sandbox" or s.payhere_sandbox,
            "label": "Test mode – no real payment is taken" if s.payment_provider == "sandbox" else "PayHere secure checkout"}


@router.post("/checkout")
def checkout(body: CheckoutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.purpose in ("assessment", "reassessment"):
        app = owned_application(db, user, body.reference_id, for_update=True)
        if body.purpose == "assessment" and app.status != "draft":
            raise HTTPException(409, "This application is already unlocked.")
        if body.purpose == "reassessment" and app.status == "draft":
            raise HTTPException(409, "Unlock the assessment first.")
        service, item = body.purpose, f"Visa application assessment – {app.title}"
    elif body.purpose == "writing_order":
        order = db.scalars(select(WritingOrder).where(WritingOrder.id == body.reference_id, WritingOrder.user_id == user.id)).first()
        if not order:
            raise HTTPException(404, "Order not found")
        if order.status != "payment_pending":
            raise HTTPException(409, "This order has already been paid.")
        service, item = order.service_code, f"Order {order.reference}"
    else:
        raise HTTPException(422, "Unsupported payment purpose")
    amount = None
    if body.purpose == "writing_order":
        amount = order.price_cents  # price locked at order creation
    p = start_payment(db, user, body.purpose, body.reference_id, service, amount)
    profile = db.scalars(select(ApplicantProfile).where(ApplicantProfile.user_id == user.id)).first()
    sess = get_provider(p.provider).create_checkout(p, {"name": user.full_name, "email": user.email, "item": item,
                                                         "phone": profile.phone if profile else None})
    db.commit()
    return {"payment": payment_out(p), "checkout": {"method": sess.method, "url": sess.url, "fields": sess.fields,
                                                    "provider_label": sess.provider_label, "is_sandbox": sess.is_sandbox}}


@router.get("")
def my_payments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [payment_out(p) for p in db.scalars(select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc())).all()]


@router.get("/{payment_id}")
def get_payment(payment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Payment, payment_id)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Payment not found")
    return payment_out(p)


@router.post("/webhook/payhere", response_class=PlainTextResponse)
async def payhere_webhook(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    if get_settings().payment_provider != "payhere":
        raise HTTPException(404, "Not found")
    outcome = handle_webhook(db, "payhere", get_provider("payhere").parse_webhook({k: str(v) for k, v in form.items()}))
    db.commit()
    return "OK" if outcome != "invalid_signature" else PlainTextResponse("invalid", status_code=400)


class SandboxCompleteIn(BaseModel):
    payment_id: uuid.UUID
    token: str
    outcome: str  # succeeded | failed | cancelled


@router.post("/sandbox/complete")
def sandbox_complete(body: SandboxCompleteIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Test-mode checkout. Goes through the SAME signed-webhook path as a real provider."""
    if get_settings().payment_provider != "sandbox" or get_settings().environment == "production":
        raise HTTPException(404, "Not found")
    p = db.get(Payment, body.payment_id)
    prov = SandboxProvider()
    if not p or p.user_id != user.id or p.provider != "sandbox" or not prov.verify_checkout_token(p, body.token):
        raise HTTPException(404, "Payment not found")
    if body.outcome not in ("succeeded", "failed", "cancelled"):
        raise HTTPException(422, "Invalid outcome")
    event = prov.signed_event(p, body.outcome, uuid.uuid4().hex)
    outcome = handle_webhook(db, "sandbox", prov.parse_webhook(event))
    db.commit()
    return {"outcome": outcome, "payment": payment_out(db.get(Payment, p.id))}


@router.get("/{payment_id}/invoice", response_class=HTMLResponse)
def invoice(payment_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Payment, payment_id)
    if not p or p.user_id != user.id or not p.invoice_number:
        raise HTTPException(404, "Invoice not found")
    svc = db.get(ServiceCatalogItem, p.service_code)
    refunds = db.scalars(select(Refund).where(Refund.payment_id == p.id, Refund.status == "succeeded")).all()
    e = html.escape
    rrows = "".join(f"<tr><td>Refund {r.processed_at:%d %b %Y}</td><td>-${fmt_amount(r.amount_cents)}</td></tr>" for r in refunds)
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><title>Invoice {e(p.invoice_number)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;color:#0f172a;padding:0 16px}}td{{padding:6px 0}}table{{width:100%}}</style></head>
<body><h1>Invoice {e(p.invoice_number)}</h1><p>VisaReady AI<br>Date: {p.paid_at:%d %b %Y}<br>Billed to: {e(user.full_name)} ({e(user.email)})</p>
<table><tr><td>{e(svc.name if svc else p.service_code)}</td><td>${fmt_amount(p.amount_cents)} {e(p.currency)}</td></tr>{rrows}</table>
<p>Payment reference: {e(p.provider_order_id)} · Provider: {e(p.provider)}{' (TEST MODE – no real payment)' if p.provider == 'sandbox' else ''}</p>
<p style="font-size:12px;color:#475569">Business registration and tax details to be added before launch.</p></body></html>""",
                        headers={"Cache-Control": "no-store"})
