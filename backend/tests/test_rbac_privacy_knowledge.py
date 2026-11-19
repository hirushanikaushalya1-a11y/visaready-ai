import uuid
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.models.applications import Document
from tests.conftest import PASSWORD, create_app, login_staff, make_client, paid_app, pdf_bytes, register, upload


@pytest.mark.parametrize("path", ["/api/admin/overview", "/api/admin/users", "/api/admin/payments", "/api/admin/audit-logs",
                                  "/api/admin/writing-orders", "/api/admin/deletion-requests"])
def test_applicant_cannot_access_admin(applicant, path):
    client, _ = applicant
    assert client.get(path).status_code == 403


def test_role_boundaries():
    support = login_staff("support")
    assert support.get("/api/admin/users").status_code == 200
    target = support.get("/api/admin/users").json()[0]["id"]
    assert support.patch(f"/api/admin/users/{target}", json={"is_active": False}).status_code == 403
    assert support.get("/api/admin/audit-logs").status_code == 403

    translator = login_staff("translator")
    for p in ("/api/admin/writing-orders", "/api/admin/users", "/api/admin/applications", "/api/admin/payments"):
        assert translator.get(p).status_code == 403, p

    team = login_staff("document_team")
    assert team.get("/api/admin/writing-orders").status_code == 200
    assert team.get("/api/admin/applications").status_code == 403
    assert team.get("/api/admin/payments").status_code == 403

    reviewer = login_staff("reviewer")
    assert reviewer.get("/api/admin/knowledge/categories").status_code == 200
    assert reviewer.post("/api/admin/knowledge/requirements/00000000-0000-0000-0000-000000000000/verify",
                         json={"confirm_checked_official_source": True}).status_code == 403


def test_only_super_admin_grants_super_admin():
    c = make_client()
    u = register(c)
    admin = login_staff("admin")
    assert admin.patch(f"/api/admin/users/{u['id']}", json={"role": "super_admin"}).status_code == 403
    assert admin.patch(f"/api/admin/users/{u['id']}", json={"role": "support"}).status_code == 200
    sa = login_staff("super_admin")
    assert sa.patch(f"/api/admin/users/{u['id']}", json={"role": "applicant"}).status_code == 200
    me = sa.get("/api/auth/me").json()
    assert sa.patch(f"/api/admin/users/{me['id']}", json={"role": "applicant"}).status_code == 400


def test_staff_mfa_enforced_when_required(monkeypatch):
    monkeypatch.setattr(get_settings(), "require_staff_mfa", True)
    c = make_client()
    c.post("/api/auth/login", json={"email": "admin@demo.visaready.local", "password": "DemoPass123!"})
    assert c.get("/api/admin/overview").status_code == 403


def test_account_deletion_workflow(db):
    c = make_client()
    u = register(c)
    a = paid_app(c)
    d = upload(c, a["id"], pdf_bytes(["Passport", "Nationality"]), "p.pdf", "passport").json()
    row = db.get(Document, uuid.UUID(d["id"]))
    blob = Path(get_settings().storage_local_path) / row.storage_key
    assert blob.exists()
    r = c.post("/api/privacy/deletion-requests", json={"scope": "account", "reason": "done"})
    assert r.status_code == 201
    admin = login_staff("admin")
    req = next(x for x in admin.get("/api/admin/deletion-requests").json() if x["user_email"] == u["email"])
    res = admin.post(f"/api/admin/deletion-requests/{req['id']}/process").json()
    assert res["status"] == "completed" and res["result"]["documents_purged"] == 1
    assert not blob.exists()
    assert c.get("/api/auth/me").status_code == 401
    assert make_client().post("/api/auth/login", json={"email": u["email"], "password": PASSWORD}).status_code == 401
    logs = admin.get("/api/admin/audit-logs?action=privacy").json()
    assert any(l["action"] == "privacy.account_deleted" for l in logs)


def test_privacy_consent_defaults_off(applicant):
    client, _ = applicant
    p = client.get("/api/privacy").json()
    assert p["ai_training_consent"] is False and p["retention_days_after_completion"] == 30
    assert client.put("/api/privacy", json={"ai_training_consent": True}).json()["ai_training_consent"] is True


def test_retention_on_completion(applicant):
    client, _ = applicant
    a = paid_app(client)
    r = client.post(f"/api/applications/{a['id']}/complete").json()
    assert r["status"] == "completed" and r["retention_delete_after"]


def test_requirement_versioning_and_verification():
    admin = login_staff("admin")
    cats = admin.get("/api/admin/knowledge/categories?country=GB").json()
    cat = next(c for c in cats if c["category_type"] == "student")
    reqs = admin.get(f"/api/admin/knowledge/requirements?category_id={cat['id']}").json()
    req = next(r for r in reqs if r["key"] == "english-language")
    assert admin.post(f"/api/admin/knowledge/requirements/{req['id']}/verify", json={"confirm_checked_official_source": False}).status_code == 422
    v = admin.post(f"/api/admin/knowledge/requirements/{req['id']}/verify",
                   json={"confirm_checked_official_source": True, "source_excerpt": "You must prove your knowledge of English"}).json()
    assert v["review_status"] == "verified"
    p = admin.patch(f"/api/admin/knowledge/requirements/{req['id']}", json={"description": "Updated wording", "change_note": "Policy update"}).json()
    assert p["review_status"] == "pending_review" and p["version"] == req["version"] + 1  # edits require re-verification
    versions = admin.get(f"/api/admin/knowledge/requirements/{req['id']}/versions").json()
    assert len(versions) == 2 and "Verified" in versions[0]["change_note"] and versions[-1]["change_note"] == "Policy update"
    bad = admin.patch(f"/api/admin/knowledge/requirements/{req['id']}", json={"applies_when": {"fact": "x", "op": "exec"}, "change_note": "bad"})
    assert bad.status_code == 422
    assert admin.patch("/api/admin/knowledge/countries/GB", json={"module_status": "live"}).status_code == 409  # unverified items remain


def test_knowledge_centre_honesty(client):
    r = client.get("/api/knowledge/search", params={"q": "english requirement student", "country": "GB"}).json()
    assert r["answer_available"] and all(x["source_url"].startswith("https://www.gov.uk") for x in r["results"])
    r = client.get("/api/knowledge/search", params={"q": "quantum zebra licensing"}).json()
    assert not r["answer_available"] and "official" in r["message"]


def test_policy_alert_notifies_affected(applicant):
    client, _ = applicant
    paid_app(client)
    admin = login_staff("admin")
    a = admin.post("/api/admin/policy-alerts", json={"country_code": "GB", "title": "Test change", "summary": "Something changed",
                                                     "source_url": "https://www.gov.uk/student-visa"}).json()
    assert client.get("/api/policy-alerts").json() == [] or all(x["id"] != a["id"] for x in client.get("/api/policy-alerts").json())
    res = admin.post(f"/api/admin/policy-alerts/{a['id']}/publish").json()
    assert res["notified_applications"] >= 1
    assert any(n["kind"] == "policy_alert" for n in client.get("/api/notifications").json()["items"])


def test_profile_validation(applicant):
    client, _ = applicant
    assert client.put("/api/profile", json={"financial": {"funding_source": "lottery"}}).status_code == 422
    assert client.put("/api/profile", json={"academic": {"qualifications": [{"level": "bachelor", "title": "BSc", "completion_date": "2021-13"}]}}).status_code == 422
    assert client.put("/api/profile", json={"unknown_field": 1}).status_code == 422
    r = client.put("/api/profile", json={"nationality": "lk", "given_names": "Asha"})
    assert r.status_code == 200 and r.json()["nationality"] == "LK"
