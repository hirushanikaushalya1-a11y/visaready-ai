"""In-app notifications + transactional email.

EMAIL_BACKEND=outbox (default): nothing is sent; each notification is recorded with
email_status='outbox_only' so the UI/admin can see the email was NOT delivered.
EMAIL_BACKEND=smtp: sent via SMTP (any transactional provider offering SMTP — e.g. SES, Postmark, Mailgun).
"""
from __future__ import annotations

import logging
import smtplib
import ssl
import uuid
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import utcnow
from app.models.platform import Notification
from app.models.users import User

log = logging.getLogger("visaready.notifications")


def _send_smtp(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
        if s.smtp_use_tls:
            smtp.starttls(context=ssl.create_default_context())
        if s.smtp_username:
            smtp.login(s.smtp_username, s.smtp_password or "")
        smtp.send_message(msg)


def send_email(to: str, subject: str, body: str) -> tuple[str, str | None]:
    s = get_settings()
    if s.email_backend == "smtp" and s.smtp_host:
        try:
            _send_smtp(to, subject, body)
            return "sent", None
        except Exception as exc:  # noqa: BLE001 - record and continue
            log.warning("SMTP send failed: %s", exc)
            return "failed", str(exc)[:500]
    log.info("[email outbox] to=%s subject=%s", to, subject)
    return "outbox_only", None


def notify(
    db: Session,
    user: User | uuid.UUID,
    kind: str,
    title: str,
    body: str,
    *,
    link: str | None = None,
    email: bool = True,
) -> Notification:
    if not isinstance(user, User):
        user = db.get(User, user)
    status, err = ("not_requested", None)
    if email and user and user.email:
        footer = f"\n\n— {get_settings().app_name}\nThis is an automated message. VisaReady AI is independent and not affiliated with any government."
        url = f"\n\nView: {get_settings().public_base_url}{link}" if link else ""
        status, err = send_email(user.email, title, body + url + footer)
    n = Notification(
        user_id=user.id, kind=kind, title=title, body=body, link=link,
        email_status=status, email_error=err, created_at=utcnow(),
    )
    db.add(n)
    return n
