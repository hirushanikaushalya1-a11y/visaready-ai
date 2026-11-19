from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import account, admin, applications, assessments, auth, documents, knowledge, orders, payments, profile
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
app = FastAPI(
    title="VisaReady AI API",
    version="1.0.0",
    docs_url="/api/docs" if settings.environment in ("development", "test") else None,
    openapi_url="/api/openapi.json" if settings.environment in ("development", "test") else None,
)


@app.on_event("startup")
def _embedded_worker() -> None:
    import os

    if os.environ.get("RUN_EMBEDDED_WORKER") == "1":
        from app.services.jobs.worker import start_embedded

        start_embedded()

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_EXEMPT = ("/api/payments/webhook/",)  # server-to-server, authenticated by signature instead


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # CSRF: auth cookies are SameSite=Lax; additionally every state-changing browser request must carry
    # a custom header, which cross-site forms cannot set without a CORS preflight (which we never allow).
    if request.method in UNSAFE and not request.url.path.startswith(CSRF_EXEMPT):
        if request.headers.get("x-requested-with") != "visaready":
            return JSONResponse({"detail": "Missing CSRF header"}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.cookie_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logging.getLogger("visaready").exception("Unhandled error on %s", request.url.path)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


for r in (auth.router, profile.router, applications.router, documents.router, assessments.router, knowledge.router,
          payments.router, orders.router, account.router, admin.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    from app.services.ai.provider import provider_name
    from app.services.documents.text import ocr_available

    s = get_settings()
    return {"status": "ok", "environment": s.environment,
            "integrations": {
                "ai_provider": provider_name(),
                "ocr": "tesseract" if ocr_available() else "unavailable",
                "payments": s.payment_provider + (" (test mode)" if s.payment_provider == "sandbox" else ""),
                "email": s.email_backend if (s.email_backend == "outbox" or s.smtp_host) else "outbox",
                "storage": s.storage_backend,
            }}
