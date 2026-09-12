"""DB-backed access-control evaluation, layered on the pure access_logic.

Called at a kiosk after a face match when the device's zone is gated. Records an
access_event, fires the access.granted / access.denied webhook, and raises a
security alert on denial.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccessEvent, Badge, UserBadge, Zone
from app.services import webhook_service
from app.services.access_logic import BadgeView, ZoneView, evaluate_access, is_gated
from app.services.alert_service import raise_alert


def _zone_view(zone: Zone) -> ZoneView:
    rule = zone.access_rule or {}
    return ZoneView(
        zone_id=str(zone.id),
        type=zone.type,
        allowed_badges=[str(b) for b in rule.get("allowed_badges", [])],
        time_windows=rule.get("time_windows", []),
    )


def _badge_views(db: Session, user_id: str) -> list[BadgeView]:
    rows = db.execute(
        select(Badge).join(UserBadge, UserBadge.badge_id == Badge.id)
        .where(UserBadge.user_id == user_id)
    ).scalars().all()
    return [
        BadgeView(
            badge_id=str(b.id),
            zones={str(z) for z in (b.zones or [])},
            time_rule=b.time_rule,
            time_windows=b.time_windows or [],
            expiry=b.expiry,
        )
        for b in rows
    ]


def evaluate_for_user(db: Session, *, tenant_id: str, user_id: str, zone_id: str,
                      device_id: str | None, now: datetime | None = None) -> dict:
    """Decide access for a recognised user at a zone. Records + notifies.
    Returns {gated, granted, reason}."""
    now = now or datetime.now(timezone.utc)
    zone = db.get(Zone, zone_id)
    if not zone:
        return {"gated": False, "granted": True, "reason": "no_zone"}

    zv = _zone_view(zone)
    if not is_gated(zv):
        return {"gated": False, "granted": True, "reason": "open_zone"}

    granted, reason = evaluate_access(zv, _badge_views(db, user_id), now)

    db.add(AccessEvent(
        tenant_id=tenant_id, user_id=user_id, zone_id=zone_id,
        device_id=device_id, granted=granted, reason=reason,
    ))

    payload = {
        "user_id": user_id, "zone_id": zone_id, "device_id": device_id,
        "timestamp": now.isoformat(), "reason": reason,
    }
    event = "access.granted" if granted else "access.denied"
    webhook_service.dispatch(db, tenant_id=tenant_id, event=event, payload=payload)

    if not granted:
        raise_alert(
            db, tenant_id=tenant_id, type="access_denied",
            message=f"Access denied at {zone.name}: {reason}",
            priority="high", target_id=user_id, device_id=device_id,
        )

    return {"gated": True, "granted": granted, "reason": reason}
