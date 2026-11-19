from __future__ import annotations

import hashlib
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core import ratelimit
from app.core.audit import audit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, owned_application, require_unlocked
from app.core.security import create_signed_token, decode_token
from app.models.applications import Document
from app.models.enums import DOCUMENT_TYPES
from app.models.users import User
from app.services.documents.text import ALLOWED_TYPES, pdf_is_encrypted_or_active, sniff_content_type
from app.services.jobs.queue import enqueue
from app.services.privacy import purge_document_blob
from app.services.storage.backend import load_decrypted, store_encrypted

router = APIRouter(tags=["documents"])


def _safe_name(name: str) -> str:
    name = re.sub(r"[^\w.\- ()]", "_", (name or "document").split("/")[-1].split("\\")[-1])[:120]
    return name or "document"


def doc_out(d: Document, detail: bool = False) -> dict:
    out = {
        "id": str(d.id), "filename": d.original_filename, "content_type": d.content_type, "size_bytes": d.size_bytes,
        "declared_type": d.declared_type, "detected_type": d.detected_type,
        "detected_type_label": DOCUMENT_TYPES.get(d.detected_type or "", None),
        "classification_confidence": d.classification_confidence, "status": d.status, "page_count": d.page_count,
        "checklist_item_key": d.checklist_item_key, "family_member_id": str(d.family_member_id) if d.family_member_id else None,
        "quality": d.quality or {}, "processing_error": d.processing_error, "created_at": d.created_at.isoformat(),
        "replaces_id": str(d.replaces_id) if d.replaces_id else None, "is_current": d.is_current,
        "authenticity_note": "Readability and consistency checked only. Authenticity has not been verified with the issuing authority.",
    }
    if detail:
        out["fields"] = [{"name": f.field_name, "value": f.value, "normalized": f.normalized_value, "page": f.page_number,
                          "snippet": f.snippet, "confidence": f.confidence, "method": f.method} for f in d.fields]
        out["pages"] = [{"page": p.page_number, "method": p.method, "ocr_confidence": p.ocr_confidence, "chars": len(p.text)} for p in d.pages]
    return out


@router.get("/document-types")
def document_types():
    return [{"code": k, "label": v} for k, v in DOCUMENT_TYPES.items()]


@router.get("/applications/{application_id}/documents")
def list_documents(application_id: uuid.UUID, include_replaced: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = owned_application(db, user, application_id)
    q = select(Document).where(Document.application_id == a.id, Document.deleted_at.is_(None))
    if not include_replaced:
        q = q.where(Document.is_current.is_(True))
    return [doc_out(d) for d in db.scalars(q.order_by(Document.created_at.desc())).all()]


@router.post("/applications/{application_id}/documents", status_code=201)
async def upload_document(
    application_id: uuid.UUID, request: Request,
    file: UploadFile = File(...),
    declared_type: str | None = Form(default=None),
    checklist_item_key: str | None = Form(default=None),
    family_member_id: uuid.UUID | None = Form(default=None),
    replaces_id: uuid.UUID | None = Form(default=None),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    s = get_settings()
    ratelimit.enforce(request, "upload", s.upload_rate_limit_per_minute, 60, key_suffix=str(user.id))
    a = owned_application(db, user, application_id, for_update=True)
    require_unlocked(a)
    if declared_type and declared_type not in DOCUMENT_TYPES:
        raise HTTPException(422, "Unknown document type")
    if family_member_id and not any(m.id == family_member_id for m in a.family_members):
        raise HTTPException(422, "Unknown family member")
    count = db.scalar(select(func.count()).select_from(Document).where(Document.application_id == a.id, Document.deleted_at.is_(None), Document.is_current.is_(True)))
    if count >= s.max_documents_per_application and not replaces_id:
        raise HTTPException(422, f"Your package allows up to {s.max_documents_per_application} documents per application.")
    max_bytes = s.max_file_size_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"Files must be {s.max_file_size_mb} MB or smaller.")
    if not data:
        raise HTTPException(422, "The file is empty.")
    ctype = sniff_content_type(data)
    if ctype not in ALLOWED_TYPES:
        raise HTTPException(415, "Only PDF, JPG and PNG files are accepted.")
    if ctype == "application/pdf":
        problem = pdf_is_encrypted_or_active(data)
        if problem:
            raise HTTPException(422, problem)
    # Malware scanning: hook point. AWAITING INTEGRATION (e.g. ClamAV daemon / cloud scanning API).
    # Idempotent: if the same file is already in this application (e.g. a retried upload whose first
    # attempt actually succeeded), return the existing document instead of storing a duplicate.
    digest = hashlib.sha256(data).hexdigest()
    if not replaces_id:
        same = db.scalars(select(Document).where(Document.application_id == a.id, Document.sha256 == digest,
                                                 Document.deleted_at.is_(None), Document.is_current.is_(True))).first()
        if same:
            return doc_out(same)
    old = None
    if replaces_id:
        old = db.scalars(select(Document).where(Document.id == replaces_id, Document.application_id == a.id, Document.deleted_at.is_(None))).first()
        if not old:
            raise HTTPException(404, "Document to replace not found")
    key, wrapped = store_encrypted(f"applications/{a.id}", data)
    doc = Document(application_id=a.id, uploaded_by_id=user.id, original_filename=_safe_name(file.filename), content_type=ctype,
                   size_bytes=len(data), sha256=digest, storage_key=key, wrapped_key=wrapped,
                   declared_type=declared_type or (old.declared_type if old else None),
                   checklist_item_key=checklist_item_key or (old.checklist_item_key if old else None),
                   family_member_id=family_member_id, replaces_id=old.id if old else None, status="uploaded")
    db.add(doc)
    if old:
        old.is_current = False
    db.flush()
    audit(db, "document.uploaded", actor=user, target_type="document", target_id=doc.id, request=request, size=len(data), replaced=str(old.id) if old else None)
    enqueue(db, "process_document", {"document_id": str(doc.id)})
    db.commit()
    db.refresh(doc)
    return doc_out(doc)


@router.get("/documents/{document_id}")
def get_document(document_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.scalars(select(Document).where(Document.id == document_id, Document.deleted_at.is_(None))
                   .options(selectinload(Document.fields), selectinload(Document.pages))).first()
    if not d:
        raise HTTPException(404, "Document not found")
    owned_application(db, user, d.application_id)  # ownership check (404 if not owner)
    return doc_out(d, detail=True)


@router.patch("/documents/{document_id}")
def update_document(document_id: uuid.UUID, body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(Document, document_id)
    if not d or d.deleted_at:
        raise HTTPException(404, "Document not found")
    owned_application(db, user, d.application_id)
    if "declared_type" in body:
        if body["declared_type"] not in DOCUMENT_TYPES:
            raise HTTPException(422, "Unknown document type")
        d.declared_type = body["declared_type"]
    if "checklist_item_key" in body:
        d.checklist_item_key = (body["checklist_item_key"] or None) and str(body["checklist_item_key"])[:200]
    db.commit()
    if "declared_type" in body:
        enqueue(db, "process_document", {"document_id": str(d.id)})
        db.commit()
    return doc_out(d)


@router.post("/documents/{document_id}/download-token")
def download_token(document_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(Document, document_id)
    if not d or d.deleted_at:
        raise HTTPException(404, "Document not found")
    owned_application(db, user, d.application_id)
    token = create_signed_token("download", {"doc": str(d.id), "uid": str(user.id)}, get_settings().download_token_seconds)
    return {"url": f"/api/documents/download/{token}", "expires_in": get_settings().download_token_seconds}


@router.get("/documents/download/{token}")
def download(token: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Short-lived signed link that ALSO requires the same authenticated user (a leaked link is useless)."""
    payload = decode_token(token, "download")
    if not payload or payload.get("uid") != str(user.id):
        raise HTTPException(403, "This download link is invalid or has expired.")
    d = db.get(Document, uuid.UUID(payload["doc"]))
    if not d or d.deleted_at:
        raise HTTPException(404, "Document not found")
    owned_application(db, user, d.application_id)
    data = load_decrypted(d.storage_key, d.wrapped_key)
    audit(db, "document.downloaded", actor=user, target_type="document", target_id=d.id, request=request)
    db.commit()
    return Response(data, media_type=d.content_type, headers={
        "Content-Disposition": f'attachment; filename="{d.original_filename}"', "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff"})


@router.delete("/documents/{document_id}")
def delete_document(document_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.get(Document, document_id)
    if not d or d.deleted_at:
        raise HTTPException(404, "Document not found")
    owned_application(db, user, d.application_id)
    purge_document_blob(db, d)
    audit(db, "document.deleted", actor=user, target_type="document", target_id=d.id, request=request)
    db.commit()
    return {"ok": True}
