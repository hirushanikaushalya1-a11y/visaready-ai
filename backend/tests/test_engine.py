"""End-to-end Evidence Intelligence tests: realistic Sri Lankan UK student applicant sponsored by a salaried father."""
import pytest

from app.services.evidence.conditions import evaluate, validate, ConditionError
from tests.conftest import make_client, mrz, paid_app, pdf_bytes, register, upload

PROFILE = {
    "given_names": "Nimal Kumar", "family_name": "Perera", "date_of_birth": "1999-03-05", "nationality": "LK",
    "residence_country": "LK", "marital_status": "single", "passport_number": "N1234567", "passport_expiry": "2032-01-01",
    "academic": {"qualifications": [{"level": "bachelor", "title": "BSc Computer Science", "institution": "University of Colombo",
                                     "country": "LK", "completion_date": "2021-12"}],
                 "english_test": {"type": "IELTS Academic", "overall_score": 7.0, "test_date": "2025-11"}},
    "employment": {"status": "employed", "history": [{"employer": "Dialog Axiata", "job_title": "Software Engineer", "start_date": "2022-03"}],
                   "career_change": False},
    "financial": {"funding_source": "sponsor", "sponsor": {"name": "Sunil Perera", "relationship": "father", "employment_type": "salaried"},
                  "declared_large_deposits": False},
    "immigration_history": {"has_previous_refusals": False, "overstays": False},
}
DETAILS = {"course_name": "MSc Data Science", "course_level": "master", "institution": "University of Leeds",
           "course_start": "2026-09", "course_related_to_previous": "yes", "career_goal": "Data scientist in Sri Lanka's telecom sector"}

PASSPORT = ["PASSPORT", "Democratic Socialist Republic of Sri Lanka", "Nationality: Sri Lankan"] + mrz("PERERA", "NIMAL KUMAR", "N1234567", "LKA", "990305", "M", "320101")
OFFER = ["University of Leeds", "Confirmation of Acceptance for Studies (CAS)", "Unconditional offer of a place",
         "Student Name: Nimal Kumar Perera", "Course: MSc Data Science", "Tuition fee: GBP 31,000", "Course start: September 2026"]
SPONSOR_BANK = ["Bank of Ceylon - Account Statement", "Account Holder: Sunil Perera", "Account No: 0071234567",
                "01/03/2026  Opening      0.00          0.00   4,000,000.00", "05/03/2026  Salary       0.00    250,000.00   4,250,000.00",
                "12/03/2026  Utility   20,000.00          0.00   4,230,000.00", "18/03/2026  Deposit      0.00  3,000,000.00   7,230,000.00",
                "25/03/2026  Salary       0.00    250,000.00   7,480,000.00", "Closing Balance: 7,480,000.00"]
BIRTH_CERT = ["Birth Certificate", "Registration of Birth", "Full Name: Nimal Kumar Perera", "Date of Birth: 05/03/1999",
              "Name of Father: Sunil Perera", "Name of Mother: Kamala Perera", "Place of birth: Colombo"]
IELTS = ["IELTS Test Report Form", "Candidate Name: Nimal Kumar Perera", "Overall Band Score: 7.0",
         "Listening 7.5 Reading 7.0 Writing 6.5 Speaking 7.0", "Test Date: 15/11/2025"]
RANDOM = ["Gym membership receipt", "Thank you for your custom", "Amount paid 2,500.00"]


def _setup(client):
    assert client.put("/api/profile", json=PROFILE).status_code == 200
    a = paid_app(client, details=DETAILS)
    for lines, name, t in ((PASSPORT, "passport.pdf", "passport"), (OFFER, "cas.pdf", "offer_letter"),
                           (SPONSOR_BANK, "father_bank.pdf", "bank_statement"), (BIRTH_CERT, "birth.pdf", "birth_certificate")):
        r = upload(client, a["id"], pdf_bytes(lines), name, t)
        assert r.status_code == 201, r.text
    return a


def _assess(client, app_id):
    r = client.post(f"/api/applications/{app_id}/assessments")
    assert r.status_code == 202, r.text
    a = client.get(f"/api/assessments/{r.json()['id']}").json()
    assert a["status"] == "completed", a
    return a


def test_full_assessment_and_strength_simulator(applicant):
    client, _ = applicant
    app = _setup(client)
    v1 = _assess(client, app["id"])
    items = {i["item_key"]: i for i in v1["checklist"]}
    fps = {f["fingerprint"]: f for f in v1["findings"]}

    # Official requirements: passport & CAS satisfied, English missing, TB applies to LK residents.
    assert items["req:valid-passport"]["status"] == "satisfied"
    assert items["req:cas"]["status"] == "satisfied"
    assert items["req:financial-capacity"]["status"] == "satisfied"
    assert items["req:english-language"]["status"] == "missing"
    assert "mandatory" in items["req:english-language"]["classifications"]
    assert "requires_verification" in items["req:english-language"]["classifications"]  # seed data is unverified
    assert items["req:tb-test"]["status"] == "missing"
    assert "req:parental-consent" not in items  # applicant is an adult
    # Evidence rules from the sponsorship declaration
    assert items["ev:sponsor-bank-statements"]["status"] == "satisfied"  # owner attribution: statement belongs to Sunil Perera
    assert items["ev:sponsor-salaried-income"]["status"] == "missing"
    assert "mandatory" not in items["ev:sponsor-salaried-income"]["classifications"]  # evidence rules are never mandatory

    # Missing-evidence certainty distinguishes official requirements from evidence recommendations
    assert fps["missing:req:english-language"]["certainty"] == "confirmed_missing_requirement"
    assert fps["missing:ev:sponsor-salaried-income"]["certainty"] == "potential_concern"
    # Significant deposit flagged with page reference, worded neutrally
    dep = fps[next(k for k in fps if k.startswith("significant_deposits:"))]
    assert dep["triggers"][0]["page"] == 1 and "legitimate" in dep["explanation"]
    # Questions simulator
    assert "q:sponsor_source" in fps and "q:deposits" in fps
    # Claims / Proof Builder
    claims = {c["claim_key"]: c for c in v1["claims"]}
    assert claims["identity"]["status"] == "supported"
    assert claims["financial.sponsorship"]["status"] == "partially_supported"
    assert claims["academic.english"]["status"] == "unsupported"
    # Score is explained and bounded
    assert 0 <= v1["readiness_score"] <= 100
    assert "not a probability" in v1["score_breakdown"]["note"]
    assert any("not yet been verified" in l for l in v1["summary"]["limitations"])

    # 1) Unrelated upload must NOT change the score.
    upload(client, app["id"], pdf_bytes(RANDOM), "receipt.pdf", "other")
    v2 = _assess(client, app["id"])
    assert v2["readiness_score"] == v1["readiness_score"]

    # 2) Evidence that addresses an issue DOES change it, and the diff explains why.
    upload(client, app["id"], pdf_bytes(IELTS), "ielts.pdf", "english_test_result")
    v3 = _assess(client, app["id"])
    assert v3["readiness_score"] > v2["readiness_score"]
    diff = client.get(f"/api/assessments/{v2['id']}/compare/{v3['id']}").json()
    resolved = {x["fingerprint"] for x in diff["issues_resolved"]}
    assert "missing:req:english-language" in resolved
    assert any(c["item_key"] == "req:english-language" and c["to"] == "satisfied" for c in diff["checklist_changes"])
    assert any(e["component"] in ("requirements", "evidence") and e["delta"] > 0 for e in diff["score_explanations"])

    # Version history
    hist = client.get(f"/api/applications/{app['id']}/assessments").json()
    assert [h["version"] for h in hist] == [3, 2, 1]


def test_cross_document_conflicts_are_cited(applicant):
    client, _ = applicant
    app = _setup(client)
    wrong_dob = [l.replace("05/03/1999", "05/03/1998") for l in BIRTH_CERT]
    upload(client, app["id"], pdf_bytes(wrong_dob), "birth2.pdf", "birth_certificate")
    wrong_score = [l.replace("Overall Band Score: 7.0", "Overall Band Score: 6.5") for l in IELTS]
    upload(client, app["id"], pdf_bytes(wrong_score), "ielts.pdf", "english_test_result")
    v = _assess(client, app["id"])
    fps = {f["fingerprint"]: f for f in v["findings"]}
    dob = next(f for k, f in fps.items() if k.startswith("dob_conflict:"))
    assert dob["severity"] == "high" and dob["triggers"][0]["filename"] == "birth2.pdf" and dob["triggers"][0]["page"] == 1
    assert "1998-03-05" in dob["explanation"]
    assert any(k.startswith("english_score_conflict:") for k in fps)
    claims = {c["claim_key"]: c for c in v["claims"]}
    assert claims["identity"]["status"] == "conflicting"


def test_undeclared_refusal_flagged_and_analysed(applicant):
    client, _ = applicant
    app = _setup(client)
    refusal = ["UK Visas and Immigration", "Decision on your application - refusal",
               "I am not satisfied that you have demonstrated that the funds are genuinely available to you.",
               "I am not satisfied that you are a genuine student.",
               "Your application is refused under the Immigration Rules. You have no right of appeal but may seek administrative review."]
    upload(client, app["id"], pdf_bytes(refusal), "refusal.pdf", "visa_refusal")
    v = _assess(client, app["id"])
    fps = {f["fingerprint"]: f for f in v["findings"]}
    assert fps["undeclared_refusal"]["severity"] == "high"
    assert fps["undeclared_refusal"]["certainty"] == "requires_professional_judgement"
    reasons = [f for f in v["findings"] if f["kind"] == "refusal_reason"]
    assert len(reasons) >= 2 and any("financial" in f["title"] for f in reasons)
    ra = client.get(f"/api/applications/{app['id']}/refusal-analyses").json()
    assert ra and ra[0]["reasons"][0]["page"] == 1


def test_reassessment_limit(applicant, db):
    from uuid import UUID

    from app.models.applications import Application

    client, _ = applicant
    app = _setup(client)
    row = db.get(Application, UUID(app["id"]))
    row.reassessments_allowed = 0
    db.commit()
    _assess(client, app["id"])
    assert client.post(f"/api/applications/{app['id']}/assessments").status_code == 402


def test_what_if_planner_not_persisted(applicant):
    client, _ = applicant
    app = _setup(client)
    v1 = _assess(client, app["id"])
    r = client.post(f"/api/applications/{app['id']}/what-if", json={"financial": {"funding_source": "self"}, "family": {"accompanying_spouse": True}})
    assert r.status_code == 200, r.text
    sim = r.json()
    keys = {i["item_key"] for i in sim["simulation"]["checklist"]}
    assert "ev:sponsor-bank-statements" not in keys
    assert "ev:accompanying-spouse" in keys
    assert sim["comparison"]["before"]["version"] == v1["version"]
    # nothing saved
    assert len(client.get(f"/api/applications/{app['id']}/assessments").json()) == 1
    assert client.get(f"/api/applications/{app['id']}").json()["reassessments"]["assessments_run"] == 1


def test_planned_country_discloses_limitation(applicant):
    client, _ = applicant
    client.put("/api/profile", json=PROFILE)
    a = paid_app(client, country="DE", details=DETAILS)
    v = _assess(client, a["id"])
    assert v["score_breakdown"]["components"]["requirements"]["ratio"] is None
    assert any("have not been loaded yet" in l for l in v["summary"]["limitations"])
    assert not any(i["origin"] == "requirement" for i in v["checklist"])
    assert all("mandatory" not in i["classifications"] for i in v["checklist"])


def test_condition_evaluator():
    facts = {"a": {"x": 5, "y": None, "s": "LK"}}
    assert evaluate({"fact": "a.x", "op": "gt", "value": 3}, facts) is True
    assert evaluate({"fact": "a.y", "op": "gt", "value": 3}, facts) is None
    assert evaluate({"all": [{"fact": "a.x", "op": "gt", "value": 3}, {"fact": "a.y", "op": "eq", "value": 1}]}, facts) is None
    assert evaluate({"any": [{"fact": "a.s", "op": "in", "value": ["LK", "IN"]}, {"fact": "a.y", "op": "eq", "value": 1}]}, facts) is True
    assert evaluate({"not": {"fact": "a.s", "op": "eq", "value": "IN"}}, facts) is True
    assert evaluate({"fact": "missing.path", "op": "exists"}, facts) is False
    with pytest.raises(ConditionError):
        validate({"fact": "a.x", "op": "__import__"})


def test_case_file_builder(applicant):
    client, _ = applicant
    app = _setup(client)
    v = _assess(client, app["id"])
    f = client.get(f"/api/assessments/{v['id']}/case-file").json()
    codes = [s["code"] for s in f["sections"]]
    assert codes[0] == "A" and codes == sorted(codes)  # identity first, decision-maker reading order
    a1 = f["sections"][0]["entries"][0]
    assert a1["ref"] == "A1" and a1["documents"][0]["filename"] == "passport.pdf"
    assert f["status"] == "not_ready" and any("English" in b["title"] for b in f["before_lodging"])
    assert f["progress"]["included"] < f["progress"]["total"]
    where = {e["title"]: sec["code"] for sec in f["sections"] for e in sec["entries"]}
    assert where["Evidence of your relationship to your financial sponsor"] == "C"
    assert where["Employment confirmation for each declared job"] == "E"
    html = client.get(f"/api/assessments/{v['id']}/case-file/print")
    assert html.status_code == 200 and "Submission file" in html.text and "A1" in html.text
    other = make_client(); register(other)
    assert other.get(f"/api/assessments/{v['id']}/case-file").status_code == 404


def test_new_zealand_student_requirements(applicant):
    client, _ = applicant
    client.put("/api/profile", json=PROFILE)
    a = paid_app(client, country="NZ", details=DETAILS)
    for lines, name, t in ((PASSPORT, "passport.pdf", "passport"), (SPONSOR_BANK, "father_bank.pdf", "bank_statement")):
        upload(client, a["id"], pdf_bytes(lines), name, t)
    v = _assess(client, a["id"])
    items = {i["item_key"]: i for i in v["checklist"]}
    assert "req:offer-of-place" in items and items["req:offer-of-place"]["status"] == "missing"
    assert "req:living-costs" in items and items["req:living-costs"]["status"] == "satisfied"
    assert "req:chest-xray-medical" in items  # LK resident
    assert "ev:nz-financial-undertaking" in items  # NZ-specific sponsor evidence
    assert all(i["source_url"].startswith("https://www.immigration.govt.nz") for i in v["checklist"] if i["origin"] == "requirement")
    assert not any("have not been loaded yet" in l for l in v["summary"]["limitations"])
