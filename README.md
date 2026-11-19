# VisaReady AI

AI-assisted visa application assessment, evidence intelligence and preparation platform.

> VisaReady AI is an independent preparation tool. It is not affiliated with any government, does not provide legal advice and never guarantees visa outcomes. The readiness score measures preparation quality, **not** approval probability.

- `backend/` — FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Tesseract OCR, job worker
- `frontend/` — Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4
- `docs/` — [Architecture](docs/ARCHITECTURE.md) · [Database](docs/DATABASE.md) · [API](docs/API.md) · [Security](docs/SECURITY.md) · [Payments research](docs/PAYMENTS.md) · [Implementation checklist](docs/IMPLEMENTATION_CHECKLIST.md) · [Assumptions](docs/ASSUMPTIONS.md)

## Put it online (no technical skills needed)

Follow **[docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md)** — one link, a few clicks.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/hirushanikaushalya1-a11y/visaready-ai)

## Run locally

Prerequisites: Python 3.12+, Node 22, PostgreSQL 16, `tesseract-ocr`, `poppler-utils`.

```bash
cp .env.example backend/.env    # then edit
```

```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
```

```bash
cd backend && alembic upgrade head && python -m app.seed.seed --demo-staff
```

```bash
cd backend && uvicorn app.main:app --port 8000
```

```bash
cd backend && python -m app.services.jobs.worker
```

```bash
cd frontend && npm install && npm run build && npm start
```

Open http://localhost:3000. Demo staff accounts (development only): `super-admin@demo.visaready.local`, `admin@…`, `document-team@…`, `translator@…`, `reviewer@…`, `support@…` — password `DemoPass123!`.

Or with Docker: `docker compose up --build`.

## Tests

```bash
cd backend && pytest
```

Uses database `visaready_test` (override with `TEST_DATABASE_URL`).
