from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.models.platform import AuditLog


def audit(
    db: Session,
    action: str,
    *,
    actor=None,
    target_type: str | None = None,
    target_id: Any = None,
    request: Request | None = None,
    **details: Any,
) -> None:
    """Append an audit record. Caller commits. Never put document contents or secrets in details."""
    db.add(
        AuditLog(
            actor_id=getattr(actor, "id", None),
            actor_role=getattr(actor, "role", None),
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            ip_address=client_ip(request) if request else None,
            user_agent=(request.headers.get("user-agent", "")[:400] if request else None),
            details={k: (str(v) if not isinstance(v, (int, float, bool, type(None), list, dict)) else v) for k, v in details.items()},
            created_at=utcnow(),
        )
    )


def client_ip(request: Request) -> str:
    # Only trust X-Forwarded-For from our own proxy in production deployments (configure at the LB).
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"
