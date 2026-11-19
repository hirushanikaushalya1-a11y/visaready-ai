from __future__ import annotations

import uuid
from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db, utcnow
from app.core.security import decode_token
from app.models.applications import Application
from app.models.enums import STAFF_ROLES
from app.models.users import RolePermission, User, UserSession

ACCESS_COOKIE = "vr_access"
REFRESH_COOKIE = "vr_refresh"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    payload = decode_token(token, "access") if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = db.get(UserSession, uuid.UUID(payload["sid"]))
    if not session or session.revoked_at or session.expires_at < utcnow():
        raise HTTPException(status_code=401, detail="Session expired")
    user = db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active or user.deleted_at:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user.role in STAFF_ROLES and get_settings().require_staff_mfa and not session.mfa_passed:
        raise HTTPException(status_code=403, detail="Multi-factor authentication required")
    request.state.user = user
    request.state.session = session
    return user


def _permissions_for(db: Session, role: str) -> frozenset[str]:
    rows = db.scalars(select(RolePermission.permission_code).where(RolePermission.role_name == role)).all()
    return frozenset(rows)


def user_permissions(db: Session, user: User) -> frozenset[str]:
    return _permissions_for(db, user.role)


def require_permission(*codes: str) -> Callable[..., User]:
    """Dependency: user must hold ALL listed permissions."""

    def dep(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        perms = user_permissions(db, user)
        if not set(codes) <= perms:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        return user

    return dep


def owned_application(db: Session, user: User, application_id: uuid.UUID, *, for_update: bool = False) -> Application:
    """The single choke-point for applicant-owned data. Returns 404 (not 403) for other users'
    applications so their existence is not disclosed."""
    stmt = select(Application).where(
        Application.id == application_id, Application.user_id == user.id, Application.deleted_at.is_(None)
    )
    if for_update:
        stmt = stmt.with_for_update()
    app = db.scalars(stmt).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def require_unlocked(app: Application) -> None:
    if app.status not in ("active", "completed"):
        raise HTTPException(
            status_code=402,
            detail="This feature is part of the $33 assessment package. Complete payment to unlock it.",
        )
