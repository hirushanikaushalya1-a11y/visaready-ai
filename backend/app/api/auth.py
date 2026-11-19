from __future__ import annotations

import base64
import io
import uuid
from datetime import timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.audit import audit, client_ip
from app.core.config import get_settings
from app.core.database import get_db, utcnow
from app.core.deps import ACCESS_COOKIE, REFRESH_COOKIE, get_current_user, user_permissions
from app.core.security import (
    create_access_token,
    decrypt_blob,
    encrypt_blob,
    hash_password,
    password_policy_errors,
    random_token,
    sha256_hex,
    verify_password,
)
from app.models.enums import STAFF_ROLES
from app.models.users import ApplicantProfile, ConsentRecord, PasswordResetToken, User, UserSession
from app.services.notifications.service import notify

router = APIRouter(prefix="/auth", tags=["auth"])
POLICY_VERSION = "2026-11-draft"
MAX_FAILED = 8
LOCK_MINUTES = 15
_DUMMY_HASH = hash_password(random_token())  # equalises timing for unknown accounts


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    accept_terms: bool
    marketing_consent: bool = False


class LoginIn(BaseModel):
    email: str = Field(max_length=320)  # not EmailStr: login must not reject existing accounts on syntax rules
    password: str = Field(max_length=200)
    mfa_code: str | None = Field(default=None, max_length=10)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(max_length=200)
    password: str = Field(min_length=10, max_length=200)


class MfaCodeIn(BaseModel):
    code: str = Field(max_length=10)


def user_out(db: Session, user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_staff": user.role in STAFF_ROLES,
        "mfa_enabled": user.mfa_enabled,
        "permissions": sorted(user_permissions(db, user)),
        "ai_training_consent": user.ai_training_consent,
        "marketing_consent": user.marketing_consent,
    }


def _set_cookies(response: Response, access: str, refresh: str) -> None:
    s = get_settings()
    common = dict(httponly=True, secure=s.cookie_secure, samesite="lax")
    response.set_cookie(ACCESS_COOKIE, access, max_age=s.access_token_minutes * 60, path="/", **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=s.refresh_token_days * 86400, path="/api/auth", **common)


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


def _start_session(db: Session, user: User, request: Request, response: Response, mfa_passed: bool) -> None:
    s = get_settings()
    refresh = random_token()
    now = utcnow()
    sess = UserSession(
        user_id=user.id,
        refresh_token_hash=sha256_hex(refresh),
        created_at=now,
        expires_at=now + timedelta(days=s.refresh_token_days),
        mfa_passed=mfa_passed,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:400],
    )
    db.add(sess)
    db.flush()
    _set_cookies(response, create_access_token(user.id, user.role, sess.id), refresh)


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ratelimit.enforce(request, "register", 5, 60)
    if not body.accept_terms:
        raise HTTPException(422, "You must accept the Terms of Service and Privacy Policy.")
    errors = password_policy_errors(body.password)
    if errors:
        raise HTTPException(422, " ".join(errors))
    email = body.email.lower().strip()
    if db.scalar(select(User.id).where(User.email == email)):
        # Same response shape as success would leak; we return a generic conflict message.
        raise HTTPException(409, "An account with this email already exists. Try signing in or resetting your password.")
    now = utcnow()
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        role="applicant",
        terms_accepted_at=now,
        marketing_consent=body.marketing_consent,
        ai_training_consent=False,  # never opted in by default
    )
    db.add(user)
    db.flush()
    db.add(ApplicantProfile(user_id=user.id))
    for ctype, granted in (("terms", True), ("privacy", True), ("marketing", body.marketing_consent), ("ai_training", False)):
        db.add(ConsentRecord(user_id=user.id, consent_type=ctype, granted=granted, policy_version=POLICY_VERSION, created_at=now))
    audit(db, "auth.register", actor=user, target_type="user", target_id=user.id, request=request)
    notify(db, user, "welcome", "Welcome to VisaReady AI",
           "Your account has been created. Start by completing your profile and creating your first application.",
           link="/dashboard")
    _start_session(db, user, request, response, mfa_passed=False)
    db.commit()
    return user_out(db, user)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    ratelimit.enforce(request, "login", s.login_rate_limit_per_minute, 60)
    email = body.email.lower().strip()
    user = db.scalars(select(User).where(User.email == email)).first()
    generic = HTTPException(401, "Incorrect email or password.")
    if not user or user.deleted_at or not user.is_active:
        verify_password(body.password, _DUMMY_HASH)
        raise generic
    now = utcnow()
    if user.locked_until and user.locked_until > now:
        raise HTTPException(429, "Too many failed attempts. Try again later or reset your password.")
    if not verify_password(body.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.failed_login_count = 0
        audit(db, "auth.login_failed", actor=user, target_type="user", target_id=user.id, request=request)
        db.commit()
        raise generic
    mfa_passed = False
    if user.mfa_enabled:
        if not body.mfa_code:
            raise HTTPException(401, detail="mfa_required")
        if not _check_totp(user, body.mfa_code):
            audit(db, "auth.mfa_failed", actor=user, target_type="user", target_id=user.id, request=request)
            db.commit()
            raise HTTPException(401, "Invalid authentication code.")
        mfa_passed = True
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    _start_session(db, user, request, response, mfa_passed)
    audit(db, "auth.login", actor=user, target_type="user", target_id=user.id, request=request)
    db.commit()
    return user_out(db, user)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(401, "Not authenticated")
    sess = db.scalars(select(UserSession).where(UserSession.refresh_token_hash == sha256_hex(token))).first()
    now = utcnow()
    if not sess or sess.revoked_at or sess.expires_at < now:
        _clear_cookies(response)
        raise HTTPException(401, "Session expired")
    user = db.get(User, sess.user_id)
    if not user or not user.is_active or user.deleted_at:
        raise HTTPException(401, "Not authenticated")
    # Rotate the refresh token on every use.
    new_refresh = random_token()
    sess.refresh_token_hash = sha256_hex(new_refresh)
    sess.last_used_at = now
    _set_cookies(response, create_access_token(user.id, user.role, sess.id), new_refresh)
    db.commit()
    return user_out(db, user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        db.execute(
            update(UserSession).where(UserSession.refresh_token_hash == sha256_hex(token)).values(revoked_at=utcnow())
        )
        db.commit()
    _clear_cookies(response)
    return {"ok": True}


@router.post("/logout-all")
def logout_all(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
    audit(db, "auth.logout_all", actor=user, request=request)
    db.commit()
    _clear_cookies(response)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_out(db, user)


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.enforce(request, "forgot", 5, 300)
    user = db.scalars(select(User).where(User.email == body.email.lower().strip())).first()
    if user and user.is_active and not user.deleted_at:
        token = random_token()
        now = utcnow()
        db.add(PasswordResetToken(
            user_id=user.id, token_hash=sha256_hex(token), created_at=now,
            expires_at=now + timedelta(minutes=get_settings().password_reset_minutes),
        ))
        notify(db, user, "password_reset", "Reset your VisaReady AI password",
               "We received a request to reset your password. This link expires in "
               f"{get_settings().password_reset_minutes} minutes. If you did not request it, ignore this email.",
               link=f"/reset-password?token={token}")
        audit(db, "auth.password_reset_requested", actor=user, request=request)
        db.commit()
        if get_settings().environment == "test":
            return {"ok": True, "_test_token": token}
    # Identical response whether or not the account exists (no account enumeration).
    return {"ok": True}


@router.post("/reset-password")
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.enforce(request, "reset", 10, 300)
    rec = db.scalars(select(PasswordResetToken).where(PasswordResetToken.token_hash == sha256_hex(body.token))).first()
    now = utcnow()
    if not rec or rec.used_at or rec.expires_at < now:
        raise HTTPException(400, "This reset link is invalid or has expired. Please request a new one.")
    errors = password_policy_errors(body.password)
    if errors:
        raise HTTPException(422, " ".join(errors))
    user = db.get(User, rec.user_id)
    user.password_hash = hash_password(body.password)
    user.failed_login_count = 0
    user.locked_until = None
    rec.used_at = now
    # Revoke every existing session after a password change.
    db.execute(update(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).values(revoked_at=now))
    audit(db, "auth.password_reset", actor=user, request=request)
    notify(db, user, "security", "Your password was changed",
           "Your VisaReady AI password was just changed and all sessions were signed out. If this wasn't you, contact support immediately.")
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- MFA (TOTP)
def _check_totp(user: User, code: str) -> bool:
    if not user.mfa_secret_enc or not user.mfa_secret_key:
        return False
    secret = decrypt_blob(user.mfa_secret_enc, user.mfa_secret_key).decode()
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


@router.post("/mfa/setup")
def mfa_setup(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.mfa_enabled:
        raise HTTPException(400, "MFA is already enabled.")
    secret = pyotp.random_base32()
    user.mfa_secret_enc, user.mfa_secret_key = encrypt_blob(secret.encode())
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="VisaReady AI")
    return {"secret": secret, "otpauth_uri": uri}


@router.post("/mfa/enable")
def mfa_enable(body: MfaCodeIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _check_totp(user, body.code):
        raise HTTPException(400, "That code is not valid. Check your authenticator app's clock and try again.")
    user.mfa_enabled = True
    request.state.session.mfa_passed = True
    audit(db, "auth.mfa_enabled", actor=user, request=request)
    db.commit()
    return {"ok": True}


@router.post("/mfa/disable")
def mfa_disable(body: MfaCodeIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role in STAFF_ROLES and get_settings().require_staff_mfa:
        raise HTTPException(400, "MFA is required for staff accounts.")
    if not _check_totp(user, body.code):
        raise HTTPException(400, "Invalid code.")
    user.mfa_enabled = False
    user.mfa_secret_enc = user.mfa_secret_key = None
    audit(db, "auth.mfa_disabled", actor=user, request=request)
    db.commit()
    return {"ok": True}
