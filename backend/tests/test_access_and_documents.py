from tests.conftest import create_app, make_client, mrz, paid_app, pdf_bytes, register, upload


def test_upload_requires_payment(applicant):
    client, _ = applicant
    a = create_app(client)
    r = upload(client, a["id"], pdf_bytes(["hello"]), "x.pdf")
    assert r.status_code == 402


def test_rejects_disallowed_file_types(applicant):
    client, _ = applicant
    a = paid_app(client)
    r = client.post(f"/api/applications/{a['id']}/documents", files={"file": ("evil.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")})
    assert r.status_code == 415
    r = client.post(f"/api/applications/{a['id']}/documents", files={"file": ("e.pdf", b"", "application/pdf")})
    assert r.status_code == 422


def test_rejects_oversize(applicant, monkeypatch):
    from app.core.config import get_settings

    client, _ = applicant
    a = paid_app(client)
    monkeypatch.setattr(get_settings(), "max_file_size_mb", 0)
    r = upload(client, a["id"], pdf_bytes(["x"]), "big.pdf")
    assert r.status_code == 413


def test_cross_user_isolation(applicant):
    client, _ = applicant
    a = paid_app(client)
    doc = upload(client, a["id"], pdf_bytes(["Passport", "Nationality"]), "p.pdf", "passport").json()
    token_url = client.post(f"/api/documents/{doc['id']}/download-token").json()["url"]

    other = make_client()
    register(other)
    assert other.get(f"/api/applications/{a['id']}").status_code == 404
    assert other.get(f"/api/applications/{a['id']}/documents").status_code == 404
    assert other.get(f"/api/documents/{doc['id']}").status_code == 404
    assert other.post(f"/api/documents/{doc['id']}/download-token").status_code == 404
    assert other.get(token_url).status_code == 403  # leaked signed link is useless to another user
    assert other.delete(f"/api/documents/{doc['id']}").status_code == 404
    assert other.post(f"/api/applications/{a['id']}/assessments").status_code == 404
    # owner can download and gets the original bytes back (decrypted)
    r = client.get(token_url)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_stored_blob_is_encrypted(applicant, db):
    from pathlib import Path

    from app.core.config import get_settings
    from app.models.applications import Document

    client, _ = applicant
    a = paid_app(client)
    data = pdf_bytes(["UNIQUE-PLAINTEXT-MARKER-12345"])
    doc = upload(client, a["id"], data, "m.pdf").json()
    row = db.get(Document, __import__("uuid").UUID(doc["id"]))
    raw = (Path(get_settings().storage_local_path) / row.storage_key).read_bytes()
    assert b"%PDF" not in raw and raw != data


def test_passport_mrz_extraction_spec_vector(applicant):
    """ICAO 9303 specimen MRZ (Anna Maria Eriksson) validates our check-digit implementation."""
    client, _ = applicant
    a = paid_app(client)
    lines = ["PASSPORT", "Utopia", "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<", "L898902C36UTO7408122F1204159ZE184226B<<<<<10"]
    doc = upload(client, a["id"], pdf_bytes(lines), "passport.pdf", "passport").json()
    detail = client.get(f"/api/documents/{doc['id']}").json()
    assert detail["status"] == "processed" and detail["detected_type"] == "passport"
    f = {x["name"]: x for x in detail["fields"] if x["method"] == "mrz"}
    assert f["passport_number"]["normalized"] == "L898902C3"
    assert f["date_of_birth"]["normalized"] == "1974-08-12"
    assert f["expiry_date"]["normalized"] == "2012-04-15"
    assert f["full_name"]["normalized"] == "ANNA MARIA ERIKSSON"
    assert f["mrz_check_digits_valid"]["normalized"] == "3"
    assert f["full_name"]["page"] == 1


def test_bank_statement_deposits_and_missing_pages(applicant):
    client, _ = applicant
    a = paid_app(client)
    page1 = ["People's Bank - Account Statement", "Account Holder: Sunil Perera", "Account No: 1234567890", "Page 1 of 3",
             "01/01/2026  Opening      0.00      1,000.00     50,000.00", "05/01/2026  Salary       0.00     10,000.00     60,000.00",
             "10/01/2026  ATM      5,000.00          0.00     55,000.00", "15/01/2026  Deposit      0.00  2,000,000.00  2,055,000.00",
             "20/01/2026  Salary       0.00     10,000.00  2,065,000.00", "Closing Balance: 2,065,000.00"]
    page3 = ["Page 3 of 3", "End of statement"]
    doc = upload(client, a["id"], pdf_bytes([page1, page3]), "bank.pdf", "bank_statement").json()
    d = client.get(f"/api/documents/{doc['id']}").json()
    assert d["detected_type"] == "bank_statement"
    deps = [x for x in d["fields"] if x["name"] == "significant_deposit"]
    assert len(deps) == 1 and deps[0]["normalized"] == "2000000.00" and deps[0]["page"] == 1
    assert any("pages 2" in i for i in d["quality"]["issues"])


def test_image_ocr(applicant):
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont

    client, _ = applicant
    a = paid_app(client)
    img = Image.new("L", (1400, 500), 255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 44)
    except OSError:
        font = ImageFont.load_default(size=44)
    draw.text((40, 60), "IELTS Test Report Form", fill=0, font=font)
    draw.text((40, 160), "Overall Band Score: 7.0", fill=0, font=font)
    draw.text((40, 260), "Listening Reading Writing Speaking", fill=0, font=font)
    buf = BytesIO()
    img.save(buf, "PNG")
    r = client.post(f"/api/applications/{a['id']}/documents", files={"file": ("ielts.png", buf.getvalue(), "image/png")},
                    data={"declared_type": "english_test_result"})
    d = client.get(f"/api/documents/{r.json()['id']}").json()
    assert d["detected_type"] == "english_test_result"
    assert d["pages"][0]["method"] == "ocr"


def test_replace_document_keeps_history(applicant):
    client, _ = applicant
    a = paid_app(client)
    d1 = upload(client, a["id"], pdf_bytes(["Passport", "Nationality"] + mrz("Perera", "Nimal", "N1234567", "LKA", "950305", "M", "300101")), "p1.pdf", "passport").json()
    d2 = upload(client, a["id"], pdf_bytes(["Passport", "Nationality"] + mrz("Perera", "Nimal", "N7654321", "LKA", "950305", "M", "350101")), "p2.pdf", replaces_id=d1["id"]).json()
    assert d2["replaces_id"] == d1["id"] and d2["declared_type"] == "passport"
    current = client.get(f"/api/applications/{a['id']}/documents").json()
    assert [x["id"] for x in current] == [d2["id"]]
    assert len(client.get(f"/api/applications/{a['id']}/documents?include_replaced=true").json()) == 2
