# Implementation checklist

Legend: ✅ built **and** tested end-to-end (frontend + API + DB) · 🟡 built, needs credentials / external setup · ⬜ not started · 🧱 schema/foundation only

_Last updated: end of build session 1 (Phases 1–3 delivered; foundations for 4–6)._

## Phase 1 — Core MVP
| Item | Status | Evidence |
|---|---|---|
| Landing page (14 sections, prices & coverage from DB) | ✅ | e2e `01-landing` |
| Registration / login / logout / refresh rotation | ✅ | `test_auth.py`, e2e |
| Password recovery (single-use, expiring, revokes sessions) | ✅ (email 🟡) | `test_password_reset_flow_revokes_sessions` |
| TOTP MFA (mandatory for staff in production) | ✅ | `test_mfa_totp`, `test_staff_mfa_enforced_when_required` |
| Applicant dashboard (8 widgets) | ✅ | e2e `16-dashboard` |
| Profile (personal, academic, employment, financial, immigration) with validation | ✅ | `test_profile_validation`, e2e |
| Application creation wizard, country & category selection | ✅ | e2e `04-new-application` |
| $33 payment architecture | ✅ sandbox · 🟡 PayHere live | `test_commerce.py` |
| Secure, encrypted document uploads | ✅ | `test_stored_blob_is_encrypted`, isolation tests |
| OCR / text extraction / classification / field extraction / MRZ | ✅ (rule-based) · 🟡 AI-assisted | `test_access_and_documents.py` |
| Initial profile assessment, checklist, readiness report | ✅ | `test_engine.py`, e2e |
| Admin dashboard foundation | ✅ | e2e `22-admin-overview` |

## Phase 2 — Evidence Intelligence
| Item | Status |
|---|---|
| Missing Evidence Detective (data-driven evidence rules) | ✅ |
| Proof Builder (claims ↔ evidence, 6 statuses) | ✅ |
| Cross-document intelligence (names, DOB, passport, employment dates/titles, CV, savings vs balance, statement holder, English score, award dates) with page citations | ✅ |
| Truth & Consistency report (incl. undeclared refusal detection) | ✅ |
| Decision-maker question simulator | ✅ |
| Application Strength Simulator (version diff, explained score deltas) | ✅ (test proves unrelated uploads don't move the score) |
| What-If planner (non-persisted simulations) | ✅ |

## Phase 3 — Document writing business
| Item | Status |
|---|---|
| Paid services catalogue (prices in DB) | ✅ |
| Order creation, unique reference, payment, instructions (env-configured service email) | ✅ (email delivery 🟡) |
| Info-incomplete / complete workflow; clock starts only on complete submission | ✅ |
| 24h deadline, live countdown, admin warnings, auto refund-eligibility, late-delivery handling | ✅ (`sla_sweep` runs every 60 s in the worker) |
| Quality review, secure encrypted delivery | ✅ |
| Refund processing & tracking | ✅ sandbox · 🟡 PayHere Refund API |

## Phase 4 — Translation marketplace
🧱 Tables `translators`, `translation_orders`, role & least-privilege permissions, service catalogue entries (quotation), automatic "needs certified translation" detection (Sinhala/Tamil script) — ✅. Ordering UI, quotation, translator dashboard — ⬜.

## Phase 5 — Country intelligence
| Item | Status |
|---|---|
| Knowledge DB: countries (all ISO), 15 destination modules, categories, requirements, sources, versions | ✅ |
| Seeded requirements: UK, Canada, Australia × student/work/family (47) | ✅ — **all `pending_review`** |
| Admin requirement editing → new version + forced re-verification; verify flow | ✅ |
| Knowledge Centre (official-source answers only, relevance floor, "we don't know") | ✅ |
| Previous refusal analysis | ✅ (rule-based) |
| Policy monitoring: source hash check → alert → human verify → notify affected | ✅ (outbound fetch 🟡 network) |
| Requirements for remaining 12 destinations | ⬜ (needs research + verification) |

## Phase 6 — Advanced
Family connection map ✅ · Policy alerts ✅ · Human review 🧱 (table + reviewer credential model; service inactive) · Analytics (basic overview) ✅ · Additional languages ⬜.

## Test totals
- Backend: **51 pytest tests**, all passing (`cd backend && pytest`).
- Frontend: `tsc` clean, `eslint` clean, production build clean.
- E2E: full Playwright journey (applicant + document team + super admin, desktop + 5 mobile pages): passes with 0 console errors and no horizontal overflow.
