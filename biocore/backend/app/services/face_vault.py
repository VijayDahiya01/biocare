"""Encrypted store for the person's ONE master face image (person app, Option A).

The master image is retained — encrypted at rest (Fernet) — solely to re-provision
the person's face into businesses/events they explicitly allow, with no re-scan.
It is India-region, person-controlled, and deleted on person erasure / withdrawal.
In production, back this with MinIO (SSE) + a KMS key; locally it's an encrypted
file under FILES_DIR. See docs/PERSON_APP.md §4.
"""
import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.security import new_token


def _fernet() -> Fernet:
    key = settings.master_key
    if not key:
        # dev fallback: a stable key derived from SESSION_SECRET (set MASTER_KEY in prod)
        digest = hashlib.sha256(settings.session_secret.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def _dir() -> Path:
    p = Path(settings.files_dir) / "person_faces"
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(image_b64: str) -> str:
    """Encrypt + store the master image; return its opaque object key."""
    token = new_token()
    (_dir() / token).write_bytes(_fernet().encrypt(image_b64.encode()))
    return token


def load(object_key: str) -> str | None:
    fp = _dir() / object_key
    if not fp.exists():
        return None
    return _fernet().decrypt(fp.read_bytes()).decode()


def delete(object_key: str) -> None:
    fp = _dir() / object_key
    if fp.exists():
        fp.unlink()
