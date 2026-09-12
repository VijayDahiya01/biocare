"""Business integration sync (BIOCORE_COMPLETE_CHANGE_SPEC §19.2).

Pull an authorized roster from an external source of truth into tenant subjects (additively —
imported subjects are `pending_verification`; each still goes through identity proofing +
consent before any face credential), and push minimal entry events out to an external sink.
All work is tenant-scoped by the RLS session; no biometric payload ever leaves.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.connectors import EntryEventRecord, get_event_sink, get_roster_source
from app.models import EntryAttempt, TenantSubject


def sync_roster(db: Session, *, tenant_id, kind: str, config: dict) -> dict:
    """Upsert the external roster into tenant subjects by external_reference."""
    source = get_roster_source(kind)
    records = source.fetch_roster(config=config or {})
    created = updated = 0
    for rec in records:
        subj = db.execute(select(TenantSubject).where(
            TenantSubject.external_reference == rec.external_reference)).scalars().first()
        if subj is None:
            db.add(TenantSubject(
                tenant_id=tenant_id, external_reference=rec.external_reference,
                display_name=rec.display_name, subject_type=rec.subject_type))
            created += 1
        else:
            if rec.display_name:
                subj.display_name = rec.display_name
            updated += 1
    db.flush()
    return {"kind": kind, "fetched": len(records), "created": created, "updated": updated}


def push_entry_events(db: Session, *, tenant_id, kind: str, config: dict, since_hours: int = 24) -> dict:
    """Push recent entry events out to an external sink (minimal metadata only)."""
    sink = get_event_sink(kind)
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    rows = db.execute(
        select(EntryAttempt, TenantSubject)
        .join(TenantSubject, TenantSubject.id == EntryAttempt.tenant_subject_id, isouter=True)
        .where(EntryAttempt.created_at >= since)
    ).all()
    events = [EntryEventRecord(
        external_reference=(subj.external_reference if subj else None),
        decision=att.authorization_result or "unknown", reason=att.reason_code or "",
        at=att.created_at.isoformat() if att.created_at else "",
        gate_id=str(att.gate_id) if att.gate_id else None,
    ) for att, subj in rows]
    pushed = sink.push_events(config=config or {}, events=events)
    return {"kind": kind, "events": len(events), "pushed": pushed}
