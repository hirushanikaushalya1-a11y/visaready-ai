"""Document processing job: decrypt -> extract text per page -> classify -> extract fields."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.models.applications import Document, DocumentPage, ExtractedField
from app.services.ai.provider import AIUnavailable, ai_extract_fields, provider_name
from app.services.documents import extract as X
from app.services.documents.text import PageText, detect_scripts, extract_pages
from app.services.storage.backend import load_decrypted

log = logging.getLogger("visaready.documents")


def process_document(db: Session, document_id: uuid.UUID) -> Document:
    doc = db.get(Document, document_id)
    if not doc or doc.deleted_at:
        raise ValueError("document not found")
    doc.status = "processing"
    db.commit()
    try:
        data = load_decrypted(doc.storage_key, doc.wrapped_key)
        pages = extract_pages(data, doc.content_type)
        db.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
        db.execute(delete(ExtractedField).where(ExtractedField.document_id == doc.id))
        for p in pages:
            db.add(DocumentPage(document_id=doc.id, page_number=p.page_number, text=p.text, method=p.method, ocr_confidence=p.ocr_confidence))
        full_text = "\n".join(p.text for p in pages)

        quality: dict = {"pages": len(pages), "issues": []}
        empty = [p.page_number for p in pages if len(p.text.strip()) < 25]
        if pages and pages[0].method == "unavailable":
            quality["issues"].append("OCR is not available on this server, so text could not be read from this image.")
        elif empty:
            quality["issues"].append(f"Little or no readable text on page(s) {', '.join(map(str, empty))}. The scan may be blank, too dark or low resolution.")
        low = [p.page_number for p in pages if p.ocr_confidence is not None and p.ocr_confidence < 60]
        if low:
            quality["issues"].append(f"Text recognition confidence is low on page(s) {', '.join(map(str, low))}. Consider uploading a clearer scan.")
        quality["issues"] += X.missing_page_hints(pages)
        scripts = detect_scripts(full_text)
        quality["non_latin_scripts"] = sorted(scripts)
        quality["readable"] = bool(full_text.strip()) and not (len(empty) == len(pages))
        doc.language_hint = "si" if "sinhala" in scripts else "ta" if "tamil" in scripts else ("en" if full_text.strip() else None)

        cls = X.classify(full_text, doc.declared_type)
        doc.detected_type = cls.doc_type
        doc.classification_confidence = cls.confidence
        doc.classification_method = "rules"
        if doc.declared_type and cls.doc_type and cls.doc_type != doc.declared_type:
            quality["issues"].append(
                f"You labelled this as '{doc.declared_type.replace('_', ' ')}', but its content looks more like '{cls.doc_type.replace('_', ' ')}'."
            )

        fields = X.extract_all(pages)
        if (doc.detected_type or doc.declared_type) == "bank_statement":
            txns = X.extract_transactions(pages)
            quality["transactions_parsed"] = len(txns)
            for t in X.significant_deposits(txns):
                fields.append(X.Field("significant_deposit", f"{t.delta:.2f}", f"{t.delta:.2f}", t.page, t.line, 0.6))
            if txns:
                fields.append(X.Field("last_balance", f"{txns[-1].balance:.2f}", f"{txns[-1].balance:.2f}", txns[-1].page, txns[-1].line, 0.55))

        for f in fields:
            db.add(ExtractedField(document_id=doc.id, field_name=f.name, value=f.value[:2000], normalized_value=f.normalized,
                                  page_number=f.page, snippet=f.snippet, confidence=f.confidence, method=f.method))

        if provider_name() != "none":
            try:
                for f in ai_extract_fields([(p.page_number, p.text) for p in pages if p.text.strip()], doc.detected_type):
                    norm = f["value"]
                    if f["name"] in X.DATE_FIELDS | {"expiry_date"}:
                        d = X.parse_date(f["value"])
                        norm = d.isoformat() if d else None
                    elif f["name"] in ("full_name", "account_holder"):
                        norm = X.normalize_name(f["value"])
                    db.add(ExtractedField(document_id=doc.id, field_name=f["name"], value=f["value"], normalized_value=norm,
                                          page_number=f["page"], snippet=f["quote"], confidence=0.75, method="ai"))
                quality["ai_extraction"] = provider_name()
            except AIUnavailable:
                pass
            except Exception as exc:  # noqa: BLE001
                log.warning("AI extraction failed for %s: %s", doc.id, exc)
                quality["ai_extraction_error"] = "AI extraction failed; deterministic extraction was used."

        doc.quality = quality
        doc.page_count = len(pages)
        doc.status = "processed"
        doc.processing_error = None
        doc.processed_at = utcnow()
        db.commit()
        return doc
    except Exception as exc:
        db.rollback()
        doc = db.get(Document, document_id)
        doc.status = "failed"
        doc.processing_error = "We could not process this file. Try re-uploading a clear PDF or image."
        log.exception("processing failed for %s: %s", document_id, exc)
        db.commit()
        raise


def page_texts(doc: Document) -> list[PageText]:
    return [PageText(p.page_number, p.text, p.method, p.ocr_confidence) for p in doc.pages]
