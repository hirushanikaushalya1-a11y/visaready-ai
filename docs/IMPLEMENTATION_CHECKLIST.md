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

## Business model v2 (owner request)
| Item | Status |
|---|---|
| Free file-strength assessment (applications active on creation, 10 runs) | ✅ |
| €35 full report unlock: printable report, printable submission file, suggested drafts | ✅ |
| Suggested drafts generator (cover letter, SOP outline, study gap, sponsorship, source of funds, refusal response, career change, relationship statement, consent) — built only from applicant facts with [prompts] | ✅ |
| New catalogue, all in EUR: report €35, SOP €20, relationship portfolio €20, letters €10 each (quantity), form filling €10, online submission €20 | ✅ |
| Licensing guard: form filling / submission refused for GB, CA, AU, NZ | ✅ |
| Euro pricing throughout (multi-currency capable) | ✅ |
| EUR acceptance with PayHere | ⬜ confirm with PayHere before going live |

## Phase 4 — Translation marketplace
🧱 Tables `translators`, `translation_orders`, role & least-privilege permissions, service catalogue entries (quotation), automatic "needs certified translation" detection (Sinhala/Tamil script) — ✅. Ordering UI, quotation, translator dashboard — ⬜.

## Phase 5 — Country intelligence
| Item | Status |
|---|---|
| Knowledge DB: countries (all ISO), 15 destination modules, categories, requirements, sources, versions | ✅ |
| Seeded requirements: **all 15 destinations** (UK, Canada, Australia, New Zealand, Ireland, France, Italy, Malta, Germany, Netherlands, Sweden, Finland, Lithuania, Hungary, Georgia) × student/work/family — 45 visa types, 265 requirements | ✅ — **all `pending_review`**; every item cites a national authority page or the European Commission's EU Immigration Portal |
| New Zealand module: Fee Paying Student Visa, Accredited Employer Work Visa, partner/dependant visas + NZ evidence rules (INZ 1014 Financial Undertaking, relationship history) | ✅ (researched Nov 2026; admin verification pending) |
| **Submission File Builder**: numbered A–I case file in decision-maker reading order, document per item, lodging blockers, explanations to prepare, printable PDF | ✅ |
| Admin requirement editing → new version + forced re-verification; verify flow | ✅ |
| Knowledge Centre (official-source answers only, relevance floor, "we don't know") | ✅ |
| Previous refusal analysis | ✅ (rule-based) |
| Policy monitoring: source hash check → alert → human verify → notify affected | ✅ (outbound fetch 🟡 network) |
| Admin verification of all 265 requirements against their official sources | ⬜ (human task — see Admin → Knowledge base) |

## Phase 6 — Advanced
Family connection map ✅ · Policy alerts ✅ · Human review 🧱 (table + reviewer credential model; service inactive) · Analytics (basic overview) ✅ · Additional languages ⬜.

## Test totals
- Backend: **69 pytest tests**, all passing (`cd backend && pytest`).
- Frontend: `tsc` clean, `eslint` clean, production build clean.
- E2E: full Playwright journey (applicant + document team + super admin, desktop + 5 mobile pages): passes with 0 console errors and no horizontal overflow.
