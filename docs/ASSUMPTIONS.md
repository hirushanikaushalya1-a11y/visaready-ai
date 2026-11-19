# Assumptions & decisions made without asking

1. **Stack**: Next.js + FastAPI + PostgreSQL as suggested. Background jobs use a Postgres `SKIP LOCKED` queue instead of Celery/Redis to reduce moving parts at MVP scale.
2. **Deterministic core engine.** Checklist, claims, consistency checks and scoring are rule-based and reproducible, so every finding is explainable and no "fake AI result" can appear. An LLM (Anthropic or OpenAI, switchable) is optional and limited to grounded field extraction and plain-language rewriting.
3. **Knowledge seed is unverified by design.** Government sites were unreachable from the build environment, so the 47 seeded requirements (UK/CA/AU) carry official URLs but `pending_review` status, contain **no monetary thresholds**, and are shown to users as "awaiting verification". The other 12 destinations are registered with official portals but no requirements — the app says so instead of guessing.
4. **TB-test applicability** for LK/IN/BD/NP residents is encoded as a condition but flagged for verification against the official UK list.
5. **Business model (owner decision, catalogue v2)**: the file-strength assessment is free (40 documents, 15 MB each, up to 10 assessment runs per application). The printable report, submission file and suggested drafts are a €35 per-application unlock; writing and application services are priced individually (see PAYMENTS.md).
6. **Retention**: documents purged 30 days after the applicant marks the application submitted (admin-configurable); payment records retained for accounting.
7. **Readiness score weights**: profile 20 / official requirements 40 / evidence for claims 20 / consistency 20; components that cannot apply are excluded and the rest renormalised (disclosed).
8. **Date convention** in documents: day-first (South Asian/UK) when ambiguous.
9. **Form filling and online submission** are refused for GB/CA/AU/NZ (licensed-adviser regimes), and are described as "carefully checked, with unlimited free amendments" rather than guaranteed error-free.
10. **Human review & translations** are not sold yet (no reviewers/translators onboarded); the UI says "coming soon" rather than taking money.
11. **Writing-order delivery** is via encrypted in-app download; customers send source material by email to `DOCUMENT_SERVICE_EMAIL` as specified.
12. Legal pages are **draft structures** clearly marked for professional legal review.
