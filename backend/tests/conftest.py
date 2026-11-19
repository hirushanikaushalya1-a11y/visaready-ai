from __future__ import annotations

import os
import tempfile
import uuid

os.environ.update({
    "ENVIRONMENT": "test",
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://visaready:visaready_dev@localhost:5432/visaready_test"),
    "JOBS_INLINE": "1",
    "STORAGE_LOCAL_PATH": tempfile.mkdtemp(prefix="vr-test-storage-"),
    "PAYMENT_PROVIDER": "sandbox",
    "AI_PROVIDER": "none",
    "EMAIL_BACKEND": "outbox",
})

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from fpdf import FPDF  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core import ratelimit  # noqa: E402
from app.core.database import SessionLocal, get_engine  # noqa: E402

HEADERS = {"X-Requested-With": "visaready"}
PASSWORD = "Correct-Horse-9"


@pytest.fixture(scope="session", autouse=True)
def database():
    eng = get_engine()
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
    command.upgrade(cfg, "head")
    from app.seed.seed import run

    run(demo_staff=True)
    yield


@pytest.fixture(autouse=True)
def _reset_limits():
    ratelimit.reset_all()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def make_client() -> TestClient:
    from app.main import app

    return TestClient(app, headers=HEADERS)


@pytest.fixture
def client():
    return make_client()


def register(client: TestClient, name: str = "Test Applicant", email: str | None = None) -> dict:
    email = email or f"user-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": PASSWORD, "full_name": name, "accept_terms": True})
    assert r.status_code == 201, r.text
    return {**r.json(), "password": PASSWORD}


def login_staff(role: str) -> TestClient:
    c = make_client()
    r = c.post("/api/auth/login", json={"email": f"{role.replace('_', '-')}@demo.visaready.local", "password": "DemoPass123!"})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def applicant(client):
    user = register(client)
    return client, user


def uk_student_category(client) -> str:
    cats = client.get("/api/countries/GB/visa-categories").json()
    return next(c["id"] for c in cats if c["category_type"] == "student")


def create_app(client, country="GB", category_type="student", details=None) -> dict:
    cats = client.get(f"/api/countries/{country}/visa-categories").json()
    cat = next(c["id"] for c in cats if c["category_type"] == category_type)
    r = client.post("/api/applications", json={"country_code": country, "visa_category_id": cat, "details": details or {}})
    assert r.status_code == 201, r.text
    return r.json()


def pay_for(client, purpose: str, reference_id: str, outcome: str = "succeeded") -> dict:
    r = client.post("/api/payments/checkout", json={"purpose": purpose, "reference_id": reference_id})
    assert r.status_code == 200, r.text
    url = r.json()["checkout"]["url"]
    pid, token = url.split("/checkout/sandbox/")[1].split("?t=")
    r = client.post("/api/payments/sandbox/complete", json={"payment_id": pid, "token": token, "outcome": outcome})
    assert r.status_code == 200, r.text
    return r.json()


def paid_app(client, **kw) -> dict:
    """Applications are free and active on creation (name kept for readability of older tests)."""
    a = create_app(client, **kw)
    return client.get(f"/api/applications/{a['id']}").json()


# ------------------------------------------------------------------ document factories
def pdf_bytes(lines: list[str] | list[list[str]]) -> bytes:
    """lines: list of strings (one page) or list of pages."""
    pages = lines if lines and isinstance(lines[0], list) else [lines]
    pdf = FPDF()
    pdf.set_auto_page_break(False)
    for page in pages:
        pdf.add_page()
        pdf.set_font("Courier", size=10)
        for ln in page:
            pdf.cell(0, 6, ln, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def mrz(surname: str, given: str, number: str, nat: str, dob: str, sex: str, expiry: str) -> list[str]:
    from app.services.documents.extract import _mrz_check

    l1 = f"P<{nat}{surname.upper()}<<{given.upper().replace(' ', '<')}".ljust(44, "<")[:44]
    num = number.ljust(9, "<")
    body = f"{num}{_mrz_check(num)}{nat}{dob}{_mrz_check(dob)}{sex}{expiry}{_mrz_check(expiry)}" + "<" * 14 + "0"
    l2 = (body + "0")[:44]
    return [l1, l2]


def upload(client, app_id: str, data: bytes, filename: str, declared_type: str | None = None, **extra):
    files = {"file": (filename, data, "application/pdf")}
    form = {k: v for k, v in {"declared_type": declared_type, **extra}.items() if v is not None}
    return client.post(f"/api/applications/{app_id}/documents", files=files, data=form)
