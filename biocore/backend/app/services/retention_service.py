"""Retention & auto-expiry (BIOCORE_COMPLETE_CHANGE_SPEC §13.3).

Per-tenant retention policies (by data category) drive credential expiry; a sweep marks
expired credentials. Retention *triggers* are vertical-specific (event end, checkout,
employment end, visit end) — those lifecycle events call the sweep/erasure; this module
provides the expiry computation and the periodic sweep.
"""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import bypass_rls
from app.models import DataRetentionPolicy, FaceCredential


def parse_period(s: str | None) -> timedelta | None:
    """Parse a compact retention string like '30d', '1y', '8h', '90m', '2w' → timedelta."""
    if not s:
        return None
    total = timedelta()
    for num, unit in re.findall(r"(\d+)\s*([mhdwy])", s.lower()):
        n = int(num)
        total += {
            "m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n),
            "w": timedelta(weeks=n), "y": timedelta(days=365 * n),
        }[unit]
    return total or None


def get_policy(db: Session, tenant_id, category: str) -> DataRetentionPolicy | None:
    return db.execute(
        select(DataRetentionPolicy).where(
            DataRetentionPolicy.tenant_id == tenant_id,
            DataRetentionPolicy.data_category == category,
        )
    ).scalars().first()


def credential_expiry(db: Session, tenant_id, category: str = "face_credential") -> datetime | None:
    """Expiry timestamp for a new credential, from the tenant's retention policy (or None)."""
    p = get_policy(db, tenant_id, category)
    d = parse_period(p.retention_period) if p else None
    return (datetime.now(timezone.utc) + d) if d else None


def sweep_expired(db: Session, tenant_id) -> int:
    """Mark active credentials whose expiry has passed as 'expired'. Returns the count."""
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(FaceCredential).where(
            FaceCredential.tenant_id == tenant_id,
            FaceCredential.status == "active",
            FaceCredential.expires_at.is_not(None),
            FaceCredential.expires_at < now,
        )
    ).scalars().all()
    for c in rows:
        c.status = "expired"
    return len(rows)


def sweep_all(db: Session) -> dict:
    """Cross-tenant sweep (for a scheduled worker). Runs under bypass; commits."""
    now = datetime.now(timezone.utc)
    with bypass_rls(db):
        rows = db.execute(
            select(FaceCredential).where(
                FaceCredential.status == "active",
                FaceCredential.expires_at.is_not(None),
                FaceCredential.expires_at < now,
            )
        ).scalars().all()
        for c in rows:
            c.status = "expired"
        db.commit()
    return {"expired": len(rows)}
