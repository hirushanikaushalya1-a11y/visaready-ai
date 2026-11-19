"""Payments, duplicate protection, webhooks, PayHere signatures, writing orders & the 24-hour guarantee."""
import hashlib
import uuid
from datetime import timedelta

from app.core.database import utcnow
from app.models.commerce import Payment, WritingOrder
from app.services.payments.providers import SandboxProvider
from tests.conftest import create_app, login_staff, make_client, pay_for, register


def test_assessment_payment_unlocks_and_invoices(applicant):
    client, _ = applicant
    a = create_app(client)
    assert a["status"] == "draft"
    res = pay_for(client, "assessment", a["id"])
    assert res["outcome"] == "succeeded" and res["payment"]["invoice_number"].startswith("VR-")
    app = client.get(f"/api/applications/{a['id']}").json()
    assert app["status"] == "active" and app["reassessments"]["remaining"] == 4  # initial + 3 included
    inv = client.get(f"/api/payments/{res['payment']['id']}/invoice")
    assert inv.status_code == 200 and "TEST MODE" in inv.text and "33.00" in inv.text
    # duplicate payment is refused
    assert client.post("/api/payments/checkout", json={"purpose": "assessment", "reference_id": a["id"]}).status_code == 409


def test_failed_payment_keeps_locked(applicant):
    client, _ = applicant
    a = create_app(client)
    res = pay_for(client, "assessment", a["id"], outcome="failed")
    assert res["payment"]["status"] == "failed"
    assert client.get(f"/api/applications/{a['id']}").json()["status"] == "draft"
    res = pay_for(client, "assessment", a["id"])  # retry works
    assert res["outcome"] == "succeeded"


def test_pending_checkout_is_reused(applicant):
    client, _ = applicant
    a = create_app(client)
    p1 = client.post("/api/payments/checkout", json={"purpose": "assessment", "reference_id": a["id"]}).json()["payment"]["id"]
    p2 = client.post("/api/payments/checkout", json={"purpose": "assessment", "reference_id": a["id"]}).json()["payment"]["id"]
    assert p1 == p2


def test_webhook_replay_tamper_and_amount_mismatch(applicant, db):
    from app.services.payments.service import handle_webhook

    client, _ = applicant
    a = create_app(client)
    pid = client.post("/api/payments/checkout", json={"purpose": "assessment", "reference_id": a["id"]}).json()["payment"]["id"]
    p = db.get(Payment, uuid.UUID(pid))
    prov = SandboxProvider()
    ev = prov.signed_event(p, "succeeded", "evt-1")
    tampered = {**ev, "amount": "0.01"}
    assert handle_webhook(db, "sandbox", prov.parse_webhook(tampered)) == "invalid_signature"
    db.commit()
    assert handle_webhook(db, "sandbox", prov.parse_webhook(ev)) == "succeeded"
    db.commit()
    assert handle_webhook(db, "sandbox", prov.parse_webhook(ev)) == "duplicate"  # replayed event ignored
    db.commit()
    # amount mismatch on a different (validly signed) payment is rejected
    b = create_app(client)
    pid2 = client.post("/api/payments/checkout", json={"purpose": "assessment", "reference_id": b["id"]}).json()["payment"]["id"]
    p2 = db.get(Payment, uuid.UUID(pid2))
    p2.amount_cents = 3300
    ev2 = prov.signed_event(p2, "succeeded", "evt-2")
    ev2_body = {k: v for k, v in ev2.items() if k != "sig"}
    ev2_body["amount"] = "1.00"
    import json
    ev2_body["sig"] = prov._sig(json.dumps({k: ev2_body[k] for k in sorted(ev2_body)}))
    assert handle_webhook(db, "sandbox", prov.parse_webhook(ev2_body)) == "amount_mismatch"
    db.commit()
    assert client.get(f"/api/applications/{b['id']}").json()["status"] == "draft"


def test_payhere_signatures(monkeypatch):
    """Checks our PayHere hashing against an independent computation of the documented formula."""
    from app.core.config import get_settings
    from app.services.payments.providers import PayHereProvider

    s = get_settings()
    monkeypatch.setattr(s, "payhere_merchant_id", "1211149")
    monkeypatch.setattr(s, "payhere_merchant_secret", "TEST_SECRET")
    prov = PayHereProvider()
    md5 = lambda x: hashlib.md5(x.encode()).hexdigest().upper()  # noqa: E731
    assert prov.checkout_hash("VR123", "33.00", "USD") == md5("1211149" + "VR123" + "33.00" + "USD" + md5("TEST_SECRET"))
    form = {"merchant_id": "1211149", "order_id": "VR123", "payment_id": "320025071278", "payhere_amount": "33.00",
            "payhere_currency": "USD", "status_code": "2"}
    form["md5sig"] = md5("1211149VR12333.00USD2" + md5("TEST_SECRET"))
    r = prov.parse_webhook(form)
    assert r.signature_valid and r.status == "succeeded"
    assert not prov.parse_webhook({**form, "payhere_amount": "0.33"}).signature_valid
    assert not prov.parse_webhook({**form, "merchant_id": "999"}).signature_valid


def _paid_order(client, service="sop"):
    o = client.post("/api/writing-orders", json={"service_code": service}).json()
    assert o["status"] == "payment_pending"
    pay_for(client, "writing_order", o["id"])
    return client.get(f"/api/writing-orders/{o['id']}").json()


def test_writing_order_full_lifecycle_on_time(applicant):
    client, _ = applicant
    o = _paid_order(client)
    assert o["price"] == "20.00"
    assert o["status"] == "awaiting_documents" and o["deadline_at"] is None  # clock not started
    assert o["submission_email"] == "documents@yourdomain.com"
    notes = client.get("/api/notifications").json()["items"]
    assert any(o["reference"] in n["title"] and "documents@yourdomain.com" in n["body"] for n in notes)
    team = login_staff("document_team")
    r = team.post(f"/api/admin/writing-orders/{o['id']}/action", json={"action": "incomplete", "note": "Please send your transcript."})
    assert r.json()["status"] == "information_incomplete"
    r = team.post(f"/api/admin/writing-orders/{o['id']}/action", json={"action": "complete"})
    data = r.json()
    assert data["status"] == "submission_complete" and data["deadline_at"] and 86000 < data["seconds_remaining"] <= 86400
    assert team.post(f"/api/admin/writing-orders/{o['id']}/deliver", files={"file": ("sop.pdf", b"%PDF-1.4 x", "application/pdf")}).status_code == 409
    team.post(f"/api/admin/writing-orders/{o['id']}/action", json={"action": "start"})
    team.post(f"/api/admin/writing-orders/{o['id']}/action", json={"action": "review"})
    r = team.post(f"/api/admin/writing-orders/{o['id']}/deliver", files={"file": ("sop.pdf", b"%PDF-1.4 deliverable", "application/pdf")})
    assert r.json()["status"] == "delivered" and not r.json()["refund_eligible"]
    mine = client.get(f"/api/writing-orders/{o['id']}").json()
    d = mine["deliverables"][0]
    assert client.get(f"/api/writing-orders/{o['id']}/deliverables/{d['id']}").content == b"%PDF-1.4 deliverable"
    other = make_client()
    register(other)
    assert other.get(f"/api/writing-orders/{o['id']}").status_code == 404
    assert other.get(f"/api/writing-orders/{o['id']}/deliverables/{d['id']}").status_code == 404


def test_missed_deadline_refund(applicant, db):
    client, _ = applicant
    o = _paid_order(client, "explanation_letter")
    team = login_staff("document_team")
    team.post(f"/api/admin/writing-orders/{o['id']}/action", json={"action": "complete"})
    team.post(f"/api/admin/writing-orders/{o['id']}/action", json={"action": "start"})
    row = db.get(WritingOrder, uuid.UUID(o["id"]))
    row.deadline_at = utcnow() + timedelta(hours=2)
    db.commit()
    stats = team.post("/api/admin/writing-orders/sla-sweep").json()
    assert stats["warned"] >= 1
    db.refresh(row)
    row.deadline_at = utcnow() - timedelta(minutes=1)
    db.commit()
    team.post("/api/admin/writing-orders/sla-sweep")
    assert client.get(f"/api/writing-orders/{o['id']}").json()["status"] == "refund_eligible"
    assert team.post(f"/api/admin/writing-orders/{o['id']}/refund").status_code == 403  # document team cannot refund
    admin = login_staff("admin")
    r = admin.post(f"/api/admin/writing-orders/{o['id']}/refund")
    assert r.json()["status"] == "refunded"
    pay = [p for p in client.get("/api/payments").json() if p["purpose"] == "writing_order"][0]
    assert pay["status"] == "refunded" and pay["refunded"] == "5.00"
    assert admin.post(f"/api/admin/payments/{pay['id']}/refund", json={"reason": "again"}).status_code == 400  # nothing left


def test_late_delivery_becomes_refund_eligible(applicant, db):
    client, _ = applicant
    o = _paid_order(client, "study_gap_letter")
    team = login_staff("document_team")
    for action in ("complete", "start", "review"):
        team.post(f"/api/admin/writing-orders/{o['id']}/action", json={"action": action})
    row = db.get(WritingOrder, uuid.UUID(o["id"]))
    row.deadline_at = utcnow() - timedelta(minutes=5)
    db.commit()
    r = team.post(f"/api/admin/writing-orders/{o['id']}/deliver", files={"file": ("l.pdf", b"%PDF-1.4 y", "application/pdf")})
    assert r.json()["status"] == "refund_eligible" and r.json()["delivered_at"]


def test_illegal_transition(applicant):
    client, _ = applicant
    o = client.post("/api/writing-orders", json={"service_code": "cover_letter"}).json()
    team = login_staff("document_team")
    assert team.post(f"/api/admin/writing-orders/{o['id']}/action", json={"action": "complete"}).status_code == 409


def test_services_catalog_prices_from_db(client):
    s = {x["code"]: x for x in client.get("/api/services").json()}
    assert s["assessment"]["price_cents"] == 3300 and s["sop"]["price_cents"] == 2000 and s["affidavit_draft"]["price_cents"] == 500
    assert "not certified" in s["affidavit_draft"]["disclaimer"]
    assert s["translation_sworn_si_en"]["price_cents"] is None  # quotation
    assert "human_review" not in s  # inactive until pricing/credentials confirmed
