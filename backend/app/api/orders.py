"""Customer-facing writing orders."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import get_db, utcnow
from app.core.deps import get_current_user, owned_application
from app.models.commerce import Deliverable, OrderEvent, ServiceCatalogItem, WritingOrder
from app.models.users import User
from app.services.orders.writing import CLOCK_RUNNING, create_order, is_refund_eligible
from app.services.payments.providers import fmt_amount
from app.services.storage.backend import load_decrypted

router = APIRouter(prefix="/writing-orders", tags=["writing-orders"])


class OrderIn(BaseModel):
    service_code: str = Field(max_length=60)
    application_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


def order_out(db: Session, o: WritingOrder, events: bool = False) -> dict:
    svc = db.get(ServiceCatalogItem, o.service_code)
    now = utcnow()
    out = {
        "id": str(o.id), "reference": o.reference, "service_code": o.service_code, "service_name": svc.name if svc else o.service_code,
        "price": fmt_amount(o.price_cents), "currency": o.currency, "status": o.status, "customer_notes": o.customer_notes,
        "missing_information_note": o.missing_information_note, "submission_email": get_settings().document_service_email,
        "required_information": svc.required_information if svc else [], "disclaimer": svc.disclaimer if svc else None,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "info_complete_at": o.info_complete_at.isoformat() if o.info_complete_at else None,
        "deadline_at": o.deadline_at.isoformat() if o.deadline_at else None,
        "seconds_remaining": int((o.deadline_at - now).total_seconds()) if o.deadline_at and o.status in CLOCK_RUNNING else None,
        "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
        "refund_eligible": is_refund_eligible(o) or o.status in ("refund_eligible", "refund_processing", "refunded"),
        "created_at": o.created_at.isoformat(), "application_id": str(o.application_id) if o.application_id else None,
    }
    out["deliverables"] = [{"id": str(d.id), "filename": d.filename, "created_at": d.created_at.isoformat()}
                           for d in db.scalars(select(Deliverable).where(Deliverable.order_type == "writing", Deliverable.order_id == o.id)).all()
                           if d.wrapped_key]
    if events:
        out["events"] = [{"from": e.from_status, "to": e.to_status, "note": e.note, "at": e.created_at.isoformat()}
                         for e in db.scalars(select(OrderEvent).where(OrderEvent.order_type == "writing", OrderEvent.order_id == o.id)
                                             .order_by(OrderEvent.created_at)).all()]
    return out


@router.post("", status_code=201)
def create(body: OrderIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.application_id:
        owned_application(db, user, body.application_id)
    o = create_order(db, user, body.service_code, body.application_id, body.notes)
    audit(db, "writing_order.created", actor=user, target_type="writing_order", target_id=o.id, request=request)
    db.commit()
    return order_out(db, o)


@router.get("")
def list_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [order_out(db, o) for o in db.scalars(select(WritingOrder).where(WritingOrder.user_id == user.id).order_by(WritingOrder.created_at.desc())).all()]


@router.get("/{order_id}")
def get_order(order_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(WritingOrder, order_id)
    if not o or o.user_id != user.id:
        raise HTTPException(404, "Order not found")
    return order_out(db, o, events=True)


@router.get("/{order_id}/deliverables/{deliverable_id}")
def download_deliverable(order_id: uuid.UUID, deliverable_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = db.get(WritingOrder, order_id)
    d = db.get(Deliverable, deliverable_id)
    if not o or o.user_id != user.id or not d or d.order_id != o.id or not d.wrapped_key:
        raise HTTPException(404, "Not found")
    audit(db, "deliverable.downloaded", actor=user, target_type="deliverable", target_id=d.id, request=request)
    db.commit()
    return Response(load_decrypted(d.storage_key, d.wrapped_key), media_type=d.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{d.filename}"', "Cache-Control": "no-store"})
