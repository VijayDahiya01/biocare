"""Generated-document storage (PDFs) with capability-token URLs.

A document is written to {files_dir}/{category}/{token}.pdf and served by an
unguessable token — so an erased user (who has no session) can still fetch their
certificate via the link. In production, swap this for MinIO + presigned URLs;
the public-facing URL shape (/documents/{category}/{token}) stays the same.
"""
from pathlib import Path

from app.core.config import settings
from app.core.security import new_token

_ALLOWED = {"certificates", "receipts", "musters"}


def _dir(category: str) -> Path:
    if category not in _ALLOWED:
        raise ValueError(f"unknown document category: {category}")
    p = Path(settings.files_dir) / category
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(category: str, data: bytes) -> str:
    """Write a PDF and return its public URL path."""
    token = new_token()
    (_dir(category) / f"{token}.pdf").write_bytes(data)
    return f"/api/v1/documents/{category}/{token}"


def path(category: str, token: str) -> Path | None:
    if category not in _ALLOWED or "/" in token or "\\" in token or "." in token:
        return None
    fp = _dir(category) / f"{token}.pdf"
    return fp if fp.exists() else None
