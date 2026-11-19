# VisaReady AI — Architecture

> Status: living document. Updated at the end of every phase. See `IMPLEMENTATION_CHECKLIST.md` for what is actually built and tested.

## 1. Starting point

The project began from an empty workspace (no prior code), so no existing components were replaced.
Runtime available in the build environment: Node 22, Python 3.13, PostgreSQL 16, Tesseract 5 OCR, poppler (`pdftotext`).

## 2. System overview

```
 Browser ──HTTPS──► Next.js (frontend, :3000)
                      │  /api/* is rewritten (same-origin) ─────────────┐
                      ▼                                                 ▼
                 React UI (App Router, TS, Tailwind)        FastAPI (backend, :8000)
                                                               │
          ┌───────────────┬──────────────┬──────────────┬──────┴───────┬───────────────┐
          ▼               ▼              ▼              ▼              ▼               ▼
     PostgreSQL     Encrypted object   OCR / text   Evidence        AI provider     Payment
     (all state,    storage (local     extraction   Intelligence    adapter         provider
      job queue,    AES-GCM; S3        (pdftotext,  engine          (Anthropic /    adapter
      audit log)    adapter planned)   tesseract)   (deterministic) OpenAI / none)  (sandbox/PayHere)
                                                               │
                                                     Worker process (same codebase)
                                                     polls `jobs` table: OCR, assessments,
                                                     SLA timers, reminders, retention purge
```

### Why this stack
| Concern | Choice | Reason |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind | SSR for the marketing pages, typed UI, design-system tokens |
| Backend | Python FastAPI, SQLAlchemy 2, Alembic | Python is the strongest ecosystem for OCR / document AI; FastAPI gives typed, documented APIs (`/api/docs`) |
| DB | PostgreSQL | Relational integrity, JSONB for extracted data, `SKIP LOCKED` job queue (no extra broker needed at MVP scale) |
| Background work | Postgres-backed job queue + worker | Durable, transactional, no Redis/Celery dependency; can be swapped for a broker later |
| Storage | `StorageBackend` interface; `LocalEncryptedStorage` (AES-256-GCM, per-file data key wrapped by a master key) | Documents are never publicly addressable; S3/GCS adapter slots into the same interface |
| AI | `AIProvider` interface with Anthropic and OpenAI adapters + `NullProvider` | Provider-agnostic; core assessment does **not** depend on an LLM (see §4) |
| Payments | `PaymentProvider` interface: `SandboxProvider`, `PayHereProvider` | Stripe is not assumed available for a Sri Lankan business (see `PAYMENTS.md`) |
| Email | `EmailBackend`: SMTP adapter, or `OutboxOnly` (recorded in DB, logged) | Works without credentials and never pretends an email was sent |

## 3. Backend module layout (`backend/app`)

```
core/        config, database, security (hashing, JWT, crypto), rate limiting, audit
models/      SQLAlchemy models (one file per domain)
schemas/     Pydantic request/response models
api/         routers: auth, users, profile, applications, documents, assessments,
             knowledge, payments, writing_orders, notifications, privacy, admin
services/
  storage/          encrypted storage backends
  documents/        text extraction, OCR, classification, field extraction, MRZ
  knowledge/        requirement resolution (country × category × version)
  evidence/         Evidence Intelligence Engine
                    ├─ facts.py        profile → normalised fact tree
                    ├─ conditions.py   safe JSON condition evaluator (no eval())
                    ├─ checklist.py    personalised checklist builder
                    ├─ claims.py       claims + Proof Builder evidence mapping
                    ├─ consistency.py  cross-document relationship intelligence
                    ├─ questions.py    decision-maker question simulator
                    ├─ scoring.py      explainable readiness score
                    ├─ engine.py       orchestrates a full assessment version
                    └─ diff.py         Application Strength Simulator (version diff)
  ai/               provider adapters + prompt-injection-safe wrappers
  payments/         provider adapters, checkout, webhook verification, refunds
  orders/           writing-order state machine, 24-hour SLA clock
  notifications/    templated notifications + email backends
  jobs/             queue + worker
```

## 4. Evidence Intelligence — design principles

1. **Rules are data, not code.** Official requirements live in `immigration_requirements` (+ `requirement_versions`, `official_sources`). Evidence rules ("if sponsor is a parent, the parent's income evidence is relevant") live in `evidence_rules` with JSON conditions. Nothing immigration-specific is hard-coded in the frontend.
2. **Two kinds of checklist item, never confused.**
   * *Official requirement* — comes from an `immigration_requirement` with an official source URL. Only these can be `mandatory`. If the requirement's `review_status` is not `verified`, the UI shows "Source recorded – awaiting verification".
   * *Evidence recommendation* — comes from an `evidence_rule`. Always `conditional` or `supplementary`, never `mandatory`.
3. **Deterministic core, AI as an assistant.** Checklist, claims, consistency and scoring are deterministic and reproducible, so every finding can be explained. When an AI provider is configured it is used for (a) structured field extraction from documents and (b) plain-language explanations — never for inventing requirements. Without an AI key the platform still works, using heuristic extraction that is labelled as such.
4. **Scores move only when evidence addresses an issue.** A checklist item counts as satisfied only when an uploaded document is linked to it *and* its detected type matches the expected type *and* it has no unresolved conflicting finding. Uploading unrelated files changes nothing.
5. **Every finding carries provenance:** document id, page, extracted snippet or applicant statement, the rule/requirement that triggered it, severity, confidence and next action.
6. **Uploaded content is untrusted.** Document text is never concatenated into system instructions. It is passed to LLMs only as delimited data with an instruction to treat it as data, outputs are JSON-schema validated, and fields that do not match the schema are discarded.

## 5. Security boundaries (summary — detail in `SECURITY.md`)

* Auth: Argon2id password hashes; short-lived access JWT + rotating refresh token (hashed in DB) in `HttpOnly; Secure; SameSite=Lax` cookies; CSRF protection by requiring the `X-Requested-With` header on state-changing requests; TOTP MFA (required for staff roles in production).
* Authorisation: every applicant-owned query is scoped via `owned_application(user, id)` helpers; staff access is permission-based (RBAC) and narrowed by assignment (translators only see their assigned files).
* Files: type sniffing (magic bytes), size limits, per-file AES-GCM encryption, download only via authenticated, short-lived signed tokens; all downloads audit-logged.
* Audit log on authentication, document access, admin actions, payment and refund events.

## 6. Data flow — one assessment

1. Applicant pays $33 → `payments` row (`pending`) → provider callback verified → application `unlocked`.
2. Applicant fills profile + application details; uploads documents (optionally against checklist items).
3. Worker extracts text per page (pdftotext → Tesseract fallback), classifies the document, extracts fields (MRZ, dates, names, amounts) with page references.
4. `engine.run_assessment()` builds facts → resolves requirements and evidence rules → checklist → claims & proof map → consistency findings → questions → score. Stored as an immutable `assessment` version.
5. Reassessment produces a new version; `diff.py` explains what changed and why.

## 7. Deployment (target)

* Containers: `frontend`, `api`, `worker`, managed PostgreSQL, S3-compatible private bucket with SSE + bucket policy denying public access.
* TLS terminated at the load balancer; HSTS; backups via managed PG point-in-time recovery.
* Secrets only via environment / secret manager; `.env.example` documents every variable.
