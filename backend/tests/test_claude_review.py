"""Claude case review: request shape, storage, reuse, and failure isolation (Claude is simulated)."""
import json
import types

import pytest

from tests.conftest import paid_app, pdf_bytes, upload
from tests.test_engine import PASSPORT, PROFILE, DETAILS

REVIEW = {
    "file_strength": "fair", "headline": "Good start — two important items missing", "summary": "Your passport is in order.",
    "documents": [{"filename": "passport.pdf", "what_it_is": "Passport bio page", "readable": True,
                   "key_facts": ["Name: Nimal Kumar Perera"], "concerns": []}],
    "strengths": ["Valid passport"], "problems": [{"title": "No offer letter", "severity": "high", "explanation": "x",
                                                   "how_to_fix": "Upload it", "documents": []}],
    "missing_documents": [{"document": "Offer letter", "why_needed": "Required"}],
    "if_submitted_now": ["The officer would query the missing offer letter."], "questions_to_prepare": ["Why this course?"], "next_steps": ["Upload the offer letter"],
    "professional_advice_recommended": False,
}


class FakeStream:
    calls = []

    def __init__(self, kwargs, reply):
        self.kwargs, self.reply = kwargs, reply

    def __enter__(self):
        FakeStream.calls.append(self.kwargs)
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        if isinstance(self.reply, Exception):
            raise self.reply
        return types.SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5",
                                     content=[types.SimpleNamespace(type="text", text=json.dumps(self.reply))],
                                     usage=types.SimpleNamespace(input_tokens=1000, output_tokens=200))


@pytest.fixture
def fake_claude(monkeypatch):
    import anthropic

    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "ai_provider", "anthropic")
    monkeypatch.setattr(s, "anthropic_api_key", "test-key")
    state = {"reply": REVIEW}

    class FakeClient:
        def __init__(self, **kw):
            self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(stream=lambda **k: FakeStream(k, state["reply"])))
            self.messages = types.SimpleNamespace(create=lambda **k: (_ for _ in ()).throw(RuntimeError("not used")))

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    FakeStream.calls.clear()
    return state


def _assess(client, app_id):
    r = client.post(f"/api/applications/{app_id}/assessments")
    assert r.status_code == 202, r.text
    return client.get(f"/api/assessments/{r.json()['id']}").json()


def test_review_sent_as_native_documents_and_stored(applicant, fake_claude):
    client, _ = applicant
    client.put("/api/profile", json=PROFILE)
    a = paid_app(client, details=DETAILS)
    upload(client, a["id"], pdf_bytes(PASSPORT), "passport.pdf", "passport")
    v = _assess(client, a["id"])
    review = v["summary"]["ai_review"]
    assert review["file_strength"] == "fair" and review["documents"][0]["filename"] == "passport.pdf"
    call = FakeStream.calls[-1]
    assert call["model"] == "claude-opus-5-5" and call["thinking"] == {"type": "adaptive"}
    assert call["output_config"]["format"]["type"] == "json_schema" and call["fallbacks"] == "default"
    content = call["messages"][0]["content"]
    assert content[0]["type"] == "document" and content[0]["source"]["media_type"] == "application/pdf"
    assert content[0]["title"] == "passport.pdf"
    assert "untrusted data" in call["system"] and "probability" in call["system"]
    assert "<context>" in content[-1]["text"]


def test_review_reused_when_nothing_changed(applicant, fake_claude):
    client, _ = applicant
    a = paid_app(client)
    upload(client, a["id"], pdf_bytes(PASSPORT), "passport.pdf", "passport")
    _assess(client, a["id"])
    _assess(client, a["id"])
    assert len(FakeStream.calls) == 1  # second assessment reused the review: no extra cost
    upload(client, a["id"], pdf_bytes(["Bank statement", "Closing Balance: 1,000.00"]), "bank.pdf")
    v = _assess(client, a["id"])
    assert len(FakeStream.calls) == 2 and v["summary"]["ai_review"]["headline"]


def test_review_failure_never_breaks_assessment(applicant, fake_claude):
    import anthropic
    import httpx

    client, _ = applicant
    a = paid_app(client)
    upload(client, a["id"], pdf_bytes(PASSPORT), "passport.pdf", "passport")
    fake_claude["reply"] = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    v = _assess(client, a["id"])
    assert v["status"] == "completed" and v["readiness_score"] is not None
    assert "ai_review" not in v["summary"] and "try again" in v["summary"]["ai_review_error"]


def test_no_review_without_key(applicant):
    client, _ = applicant
    a = paid_app(client)
    v = _assess(client, a["id"])
    assert "ai_review" not in v["summary"] and "ai_review_error" not in v["summary"]
