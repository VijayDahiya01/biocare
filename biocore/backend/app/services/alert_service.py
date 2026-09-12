"""Alerts — raise, list, dismiss. Critical alerts (blacklist, breach) are routed
immediately; routine ones are lower priority (notification routing arrives with
the full notification service)."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.envelope import ApiError
from app.models import Alert


def raise_alert(db: Session, *, tenant_id: str, type: str, message: str,
                priority: str = "high", target_id: str | None = None,
                device_id: str | None = None) -> Alert:
    alert = Alert(
        tenant_id=tenant_id, type=type, message=message,
        priority=priority, target_id=target_id, device_id=device_id,
    )
    db.add(alert)
    db.flush()
    return alert


def list_alerts(db: Session, *, priority: str | None, type: str | None,
                status: str = "active") -> list[dict]:
    stmt = select(Alert).where(Alert.status == status)
    if priority:
        stmt = stmt.where(Alert.priority == priority)
    if type:
        stmt = stmt.where(Alert.type == type)
    rows = db.execute(stmt.order_by(Alert.created_at.desc()).limit(200)).scalars().all()
    return [
        {"alert_id": str(a.id), "type": a.type, "priority": a.priority,
         "message": a.message, "status": a.status, "target_id": a.target_id,
         "created_at": a.created_at.isoformat()}
        for a in rows
    ]


def dismiss_alert(db: Session, *, alert_id: str, actor_id: str) -> None:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise ApiError(404, "ALERT_NOT_FOUND", "Alert does not exist.")
    alert.status = "dismissed"
    alert.dismissed_by = actor_id
    alert.dismissed_at = datetime.now(timezone.utc)
    db.commit()
