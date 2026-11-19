# Security & privacy design

| Area | Implementation | Where |
|---|---|---|
| Passwords | Argon2id (memory-hard); policy ≥10 chars, mixed case, digit; constant-time dummy verify for unknown accounts | `core/security.py`, `api/auth.py` |
| Sessions | 15-min access JWT + 14-day refresh token (random, **stored hashed**, rotated on every use, revocable); `HttpOnly; SameSite=Lax; Secure` (prod) cookies; all sessions revoked on password reset | `api/auth.py` |
| CSRF | SameSite cookies **plus** mandatory `X-Requested-With: visaready` header on every state-changing request (cross-site forms cannot set it; no CORS is enabled) | `main.py` |
| Brute force | Per-IP rate limits (login, register, reset, upload); account lock 15 min after 8 failures; Redis backend available for multi-instance | `core/ratelimit.py` |
| MFA | TOTP (RFC 6238); secret encrypted at rest; **mandatory for all staff roles when `ENVIRONMENT=production`** | `api/auth.py`, `core/deps.py` |
| Authorisation | RBAC: roles → permissions in DB (`role_permissions`); every admin route declares its permission; applicant data reachable only through `owned_application()` which returns **404** for others' data (no existence leak) | `core/deps.py` |
| Least privilege | Translators: no access to applications, users, payments or writing orders (tested). Document team: orders only, cannot refund. Support: read users, cannot change them. Only Super Admin can grant Super Admin. | `models/enums.py`, tests |
| Files at rest | Each file encrypted with its own random AES-256-GCM key; the key is wrapped by `STORAGE_MASTER_KEY` (envelope encryption). Deletion destroys the wrapped key (crypto-shredding) and overwrites the blob | `services/storage`, `services/privacy.py` |
| Upload validation | Type from magic bytes (PDF/JPEG/PNG only; client MIME ignored), size limit, encrypted/JS-bearing PDFs rejected, page cap, filename sanitised, OCR in temp dir with timeouts | `api/documents.py`, `services/documents/text.py` |
| Downloads | Short-lived (120 s) signed link **bound to the requesting user** – a leaked link is useless to anyone else; `Cache-Control: no-store`; every download audit-logged | `api/documents.py` |
| Untrusted content / prompt injection | Document text never enters system prompts; sent as delimited data with "treat as data" instruction; AI output schema-validated, field allow-list, and every AI value must quote text that actually exists in the document or it is discarded | `services/ai/provider.py` |
| Payments | No card data ever touches our servers; webhook signatures verified (HMAC sandbox / PayHere md5sig); amount + currency reconciled; idempotent event table; forged events cannot block genuine ones | `services/payments` |
| Audit | Auth events, uploads/downloads, staff document access, role changes, knowledge edits/verification, payments, refunds, deletions | `audit_logs` |
| Headers | nosniff, X-Frame-Options DENY, Referrer-Policy, Permissions-Policy, HSTS (prod), no-store on API | `main.py`, `next.config.ts` |
| Production guard | App refuses to start in production with default secrets, insecure cookies or the sandbox payment provider | `core/config.py` |
| Privacy | AI-training consent **off by default** with consent ledger; data export (JSON); deletion requests workflow; configurable retention (default 30 days after completion) with automatic purge job | `api/account.py`, `services/privacy.py` |

## Known gaps (to close before launch)
- **Malware scanning**: hook point exists in upload handler; integrate ClamAV/cloud AV.
- **Encryption of extracted text in DB**: relies on managed-Postgres disk encryption; consider column-level encryption for `document_pages.text`.
- **Key management**: move `STORAGE_MASTER_KEY` to a KMS/HSM; implement key rotation (re-wrap data keys).
- **WAF / bot protection** at the edge; centralised log shipping & alerting.
- **Penetration test** and legal review of Terms/Privacy drafts (Sri Lanka PDPA 2022, GDPR/UK GDPR, India DPDP 2023).
