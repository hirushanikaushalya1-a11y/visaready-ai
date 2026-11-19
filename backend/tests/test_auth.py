from tests.conftest import PASSWORD, make_client, register


def test_register_login_me_logout(client):
    u = register(client, "Nimal Perera")
    assert u["role"] == "applicant" and not u["is_staff"]
    assert client.get("/api/auth/me").json()["email"] == u["email"]
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    c2 = make_client()
    assert c2.post("/api/auth/login", json={"email": u["email"], "password": "wrong-Password1"}).status_code == 401
    assert c2.post("/api/auth/login", json={"email": u["email"], "password": PASSWORD}).status_code == 200
    assert c2.get("/api/auth/me").status_code == 200


def test_unknown_email_same_error(client):
    r = client.post("/api/auth/login", json={"email": "nobody-xyz@example.com", "password": "Whatever-123"})
    assert r.status_code == 401 and r.json()["detail"] == "Incorrect email or password."


def test_password_policy_and_terms(client):
    r = client.post("/api/auth/register", json={"email": "weak@example.com", "password": "alllowercase1", "full_name": "W", "accept_terms": True})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={"email": "noterms@example.com", "password": PASSWORD, "full_name": "No Terms", "accept_terms": False})
    assert r.status_code == 422


def test_duplicate_email(client):
    u = register(client)
    r = make_client().post("/api/auth/register", json={"email": u["email"], "password": PASSWORD, "full_name": "X Y", "accept_terms": True})
    assert r.status_code == 409


def test_csrf_header_required(client):
    from fastapi.testclient import TestClient

    from app.main import app

    bare = TestClient(app)
    r = bare.post("/api/auth/login", json={"email": "a@b.com", "password": "x"})
    assert r.status_code == 403 and "CSRF" in r.json()["detail"]


def test_refresh_rotates_token(client):
    register(client)
    old = client.cookies.get("vr_refresh")
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    assert client.cookies.get("vr_refresh") != old


def test_password_reset_flow_revokes_sessions(client):
    u = register(client)
    other = make_client()
    other.post("/api/auth/login", json={"email": u["email"], "password": PASSWORD})
    r = make_client().post("/api/auth/forgot-password", json={"email": u["email"]})
    token = r.json()["_test_token"]
    assert make_client().post("/api/auth/forgot-password", json={"email": "doesnotexist@example.com"}).json() == {"ok": True}
    new_pw = "Brand-New-Pass7"
    assert make_client().post("/api/auth/reset-password", json={"token": token, "password": new_pw}).status_code == 200
    assert make_client().post("/api/auth/reset-password", json={"token": token, "password": new_pw}).status_code == 400  # single use
    assert other.get("/api/auth/me").status_code == 401  # old session revoked
    assert make_client().post("/api/auth/login", json={"email": u["email"], "password": new_pw}).status_code == 200


def test_lockout_after_repeated_failures(client):
    u = register(client)
    c = make_client()
    for _ in range(8):
        c.post("/api/auth/login", json={"email": u["email"], "password": "Wrong-pass-1"})
    from app.core import ratelimit

    ratelimit.reset_all()
    r = c.post("/api/auth/login", json={"email": u["email"], "password": PASSWORD})
    assert r.status_code == 429


def test_mfa_totp(client):
    import pyotp

    u = register(client)
    secret = client.post("/api/auth/mfa/setup").json()["secret"]
    assert client.post("/api/auth/mfa/enable", json={"code": "000000"}).status_code == 400
    assert client.post("/api/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    c = make_client()
    r = c.post("/api/auth/login", json={"email": u["email"], "password": PASSWORD})
    assert r.status_code == 401 and r.json()["detail"] == "mfa_required"
    r = c.post("/api/auth/login", json={"email": u["email"], "password": PASSWORD, "mfa_code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
