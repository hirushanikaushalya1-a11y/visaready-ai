"""Password hashing, tokens and envelope encryption helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.core.database import utcnow

_ph = PasswordHasher()  # Argon2id with library defaults (memory-hard)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_policy_errors(password: str) -> list[str]:
    errors = []
    if len(password) < 10:
        errors.append("Password must be at least 10 characters.")
    if password.lower() == password or password.upper() == password:
        errors.append("Use both upper- and lower-case letters.")
    if not any(c.isdigit() for c in password):
        errors.append("Include at least one number.")
    return errors


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ---------------------------------------------------------------- JWT
def create_access_token(user_id: uuid.UUID, role: str, session_id: uuid.UUID) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.access_token_minutes)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def create_signed_token(purpose: str, data: dict[str, Any], seconds: int) -> str:
    s = get_settings()
    now = utcnow()
    payload = {**data, "typ": purpose, "iat": int(now.timestamp()), "exp": int(now.timestamp()) + seconds}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_token(token: str, purpose: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != purpose:
        return None
    return payload


# ---------------------------------------------------------------- envelope encryption
def _master_key() -> bytes:
    key = base64.urlsafe_b64decode(get_settings().storage_master_key)
    if len(key) != 32:
        raise RuntimeError("STORAGE_MASTER_KEY must decode to 32 bytes")
    return key


def encrypt_blob(plaintext: bytes) -> tuple[bytes, bytes]:
    """Returns (ciphertext, wrapped_data_key). Each blob gets its own random AES-256 key."""
    data_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ct = nonce + AESGCM(data_key).encrypt(nonce, plaintext, None)
    wrap_nonce = os.urandom(12)
    wrapped = wrap_nonce + AESGCM(_master_key()).encrypt(wrap_nonce, data_key, b"visaready-dek")
    return ct, wrapped


def decrypt_blob(ciphertext: bytes, wrapped_key: bytes) -> bytes:
    data_key = AESGCM(_master_key()).decrypt(wrapped_key[:12], wrapped_key[12:], b"visaready-dek")
    return AESGCM(data_key).decrypt(ciphertext[:12], ciphertext[12:], None)


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
