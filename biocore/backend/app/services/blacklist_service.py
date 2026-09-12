"""Blacklist — faces searched in parallel at every kiosk scan.

ZepIris uses ONE collection (zepiris_faces) per the verified design, so blacklist
faces are inserted into that same tenant space under a distinguishable
`blacklist:<uuid>` id. A scan whose top match is a blacklist id is a hit and
raises an immediate alert (no attendance is recorded).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.zepiris import get_zepiris
from app.models import BlacklistEntry

BLACKLIST_PREFIX = "blacklist:"


def add(db: Session, *, tenant_id: str, image_b64: str, reason: str | None,
        added_by: str) -> dict:
    face_id = f"{BLACKLIST_PREFIX}{uuid.uuid4()}"
    get_zepiris().insert(tenant=tenant_id, face_id=face_id, image_b64=image_b64)
    entry = BlacklistEntry(
        tenant_id=tenant_id, milvus_vector_id=face_id, reason=reason,
        added_by=added_by,
    )
    db.add(entry)
    db.commit()
    return {"blacklist_id": str(entry.id), "vector_id": face_id}


def list_entries(db: Session) -> list[dict]:
    rows = db.execute(select(BlacklistEntry)).scalars().all()
    return [
        {"blacklist_id": str(e.id), "reason": e.reason,
         "created_at": e.created_at.isoformat()}
        for e in rows
    ]


def is_blacklisted(db: Session, matched_id: str | None) -> BlacklistEntry | None:
    """Confirm a matched ZepIris id is a blacklist entry in this tenant."""
    if not matched_id or not matched_id.startswith(BLACKLIST_PREFIX):
        return None
    return db.execute(
        select(BlacklistEntry).where(BlacklistEntry.milvus_vector_id == matched_id)
    ).scalar_one_or_none()
