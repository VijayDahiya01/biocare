"""Audit writer. Every significant action lands here, immutably.

The audit_logs table rejects UPDATE/DELETE at the DB level (trigger), so writes
here are permanent. Always pass the request_id so an action can be traced from
the API envelope through to its audit entry.
"""
from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    actor_id: str | None = None,
    tenant_id: str | None = None,
    target_id: str | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Append an audit row. Caller controls the transaction/commit."""
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            target_id=target_id,
            request_id=request_id,
            ip_address=ip_address,
            metadata_=metadata or {},
        )
    )
