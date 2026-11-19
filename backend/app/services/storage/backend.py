"""Object storage. Blobs are always encrypted client-side (AES-256-GCM, per-file data key wrapped
by STORAGE_MASTER_KEY) before they reach any backend, so a leaked bucket exposes only ciphertext."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings
from app.core.security import decrypt_blob, encrypt_blob


class StorageBackend(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalEncryptedStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.chmod(tmp, 0o600)
        tmp.replace(p)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            # Overwrite before unlink (best effort; on SSD/cloud storage rely on key destruction).
            size = p.stat().st_size
            with open(p, "r+b") as fh:
                fh.write(os.urandom(min(size, 1 << 20)))
            p.unlink()


class S3Storage:  # pragma: no cover - requires credentials
    """S3-compatible adapter. AWAITING INTEGRATION: requires boto3 and S3_BUCKET / AWS credentials.
    Bucket must block all public access and use SSE-KMS in addition to our client-side encryption."""

    def __init__(self) -> None:
        raise RuntimeError("S3 storage is not configured in this deployment. Set STORAGE_BACKEND=local_encrypted or configure S3.")


_backend: StorageBackend | None = None


def storage() -> StorageBackend:
    global _backend
    if _backend is None:
        s = get_settings()
        _backend = S3Storage() if s.storage_backend == "s3" else LocalEncryptedStorage(s.storage_local_path)
    return _backend


def store_encrypted(prefix: str, data: bytes) -> tuple[str, bytes]:
    key = f"{prefix}/{uuid.uuid4().hex}"
    ciphertext, wrapped = encrypt_blob(data)
    storage().put(key, ciphertext)
    return key, wrapped


def load_decrypted(key: str, wrapped: bytes) -> bytes:
    return decrypt_blob(storage().get(key), wrapped)
