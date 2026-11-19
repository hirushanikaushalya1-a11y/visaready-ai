# Payment provider evaluation (Sri Lanka-operated business)

Research done November 2026 via web search. **Every item marked "confirm" must be confirmed directly with the provider before go-live.**

| Provider | Sri Lankan merchant | Intl cards | USD | Refund API | Webhooks | Notes |
|---|---|---|---|---|---|---|
| **PayHere** (recommended primary) | Yes (local gateway) | Visa/Mastercard/Amex | `payhere_currency` documents LKR/USD — **confirm USD is enabled for the account** | Yes (Merchant Refund API, OAuth client-credentials, **server IP must be whitelisted**) | Yes — server-to-server `notify_url` with `md5sig` | USD refund behaviour on international cards is **not documented — confirm** |
| Paddle (merchant of record) | Sri Lanka appears on Paddle's country list, but that page is buyer-oriented — **seller eligibility unconfirmed** | Yes | Yes | Yes | Yes | MoR handles tax; would need a new adapter |
| Stripe | Sources conflict; not on Stripe's standard country list — **do not assume available** | – | – | – | – | Not implemented |
| Lemon Squeezy | Seller payout eligibility for LK unconfirmed | – | – | – | – | Not implemented |

## What is implemented
- `PaymentProvider` interface (`backend/app/services/payments/providers.py`).
- **PayHereProvider**: checkout form fields + hash (`MD5(merchant_id+order_id+amount+currency+MD5(secret).upper()).upper()`), `notify_url` verification (`md5sig` + merchant id check), status mapping (2/0/-1/-2/-3), Refund API call. Unit-tested against an independent computation of the documented formula. **Awaiting credentials**: `PAYHERE_MERCHANT_ID`, `PAYHERE_MERCHANT_SECRET`, `PAYHERE_APP_ID`, `PAYHERE_APP_SECRET`; `API_PUBLIC_URL` must be publicly reachable (PayHere cannot call localhost).
- **SandboxProvider**: clearly labelled test mode, HMAC-signed events through the *same* webhook pipeline. Refused when `ENVIRONMENT=production`.
- Duplicate protection (DB partial unique index), pending-checkout reuse, replay protection, amount/currency reconciliation, invoices (`VR-YYYY-NNNNNN`), refunds with partial-refund accounting, failed-payment handling.

## Refund timing disclosure
Customers are told refunds go to the original payment method and may take 5–10 business days (sometimes longer) depending on their bank. Update once PayHere confirms its timelines.

## Pricing model (catalogue v3) — all prices in EUR
| Product | Price |
|---|---|
| File-strength assessment | Free |
| Full assessment report + suggested drafts (per application) | €35 |
| Statement of Purpose — complete | €20 |
| Relationship portfolio | €20 |
| Letters (cover, consent, explanation, sponsorship, study gap, financial, employment, affidavit draft, other) | €10 per letter |
| Visa application form filling (unlimited amendments) | €10 — blocked for GB, CA, AU, NZ |
| Online document submission | €20 — blocked for GB, CA, AU, NZ |

Prices live in `backend/app/seed/knowledge_data.py` (`SERVICES`). Bump `CATALOG_VERSION` when the owner changes prices so the
seed applies them over existing rows; admin-edited prices are otherwise preserved.

**Currency warning:** every price is in EUR (owner decision). PayHere documents LKR and USD only. Before switching
`PAYMENT_PROVIDER=payhere`, confirm with PayHere that EUR can be charged to your merchant account; otherwise a provider that
supports EUR is needed (or prices must be converted).

**Licensing:** preparing or lodging visa applications for a fee is regulated immigration advice in the UK (OISC), Canada (CICC),
Australia (OMARA) and New Zealand (IAA). The form-filling and submission services are therefore refused for those destinations
(`restricted_countries`). Check the rules for every other destination before selling these services there.
