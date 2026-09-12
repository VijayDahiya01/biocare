"""Kiosk check-in (API Reference §3.4) — the most-called path.

A kiosk sends a frame; this identifies the person via ZepIris and records an
attendance event using toggle logic. One call does match + record.

Blacklist parallel-search and zone access decisions arrive in Phase 2; the
response already carries blacklist_hit (always false for now) so the kiosk UI
contract is stable.
"""
from sqlalchemy.orm import Session

from app.adapters.ppe import get_ppe
from app.adapters.zepiris import ZepIrisError, get_zepiris
from app.api.deps import DeviceContext
from app.core.config import settings
from app.core.envelope import ApiError
from app.models import AccessEvent, User, Zone
from app.services import access_service, blacklist_service, webhook_service
from app.services.alert_service import raise_alert
from app.services.attendance_service import record_break, record_event
from app.services.ppe_logic import evaluate_ppe


def _search_match(db: Session, device: DeviceContext, image_b64: str) -> User:
    """Shared: ZepIris search + quality gates -> the matched active User.
    Raises ApiError (spoof/quality) or returns the User. Used by scan + break."""
    z = get_zepiris()
    try:
        result = z.search(
            tenant=device.tenant_id, image_b64=image_b64,
            top_k=5, threshold=settings.match_threshold,
        )
    except ZepIrisError as e:
        if e.status_code == 400:
            raise ApiError(400, "BAD_IMAGE", "The frame could not be read.")
        raise ApiError(502, "FACE_ENGINE_ERROR", "Face engine unavailable.")
    if result.quality.spoof:
        raise ApiError(403, "SPOOF_DETECTED", "Liveness check failed.")
    if not result.quality.passed:
        raise ApiError(422, "IMAGE_QUALITY_FAILED", "Image quality check failed.")
    best = result.best
    if not best or best.score < settings.match_threshold:
        raise ApiError(404, "NO_MATCH", "Face not recognised.")
    user = db.get(User, best.id)
    if not user or user.status != "active":
        raise ApiError(404, "NO_MATCH", "Face not recognised.")
    return user


def process_break(db: Session, *, device: DeviceContext, image_b64: str,
                  break_type: str, request_id: str | None) -> dict:
    user = _search_match(db, device, image_b64)
    recorded = record_break(
        db, tenant_id=device.tenant_id, user_id=str(user.id), break_type=break_type,
        device_id=device.device_id, match_score=None, request_id=request_id,
    )
    return {"match": True, "user_id": str(user.id),
            "name": f"{user.first_name} {user.last_name or ''}".strip(), **recorded}


def process_scan(db: Session, *, device: DeviceContext, image_b64: str,
                 action: str, request_id: str | None) -> dict:
    z = get_zepiris()
    try:
        result = z.search(
            tenant=device.tenant_id, image_b64=image_b64,
            top_k=5, threshold=settings.match_threshold,
        )
    except ZepIrisError as e:
        if e.status_code == 400:
            raise ApiError(400, "BAD_IMAGE", "The frame could not be read.")
        raise ApiError(502, "FACE_ENGINE_ERROR", "Face engine unavailable.")

    # Quality gates (run before accepting any match).
    if result.quality.spoof:
        raise ApiError(403, "SPOOF_DETECTED", "Liveness check failed — present a real face.")
    if not result.quality.passed:
        raise ApiError(422, "IMAGE_QUALITY_FAILED", "Image quality check failed — please retry.")

    best = result.best
    if not best or best.score < settings.match_threshold:
        # Recognised nobody — raise an unrecognised-face alert for review.
        raise_alert(db, tenant_id=device.tenant_id, type="unrecognised",
                    message="Unrecognised face at kiosk", priority="medium",
                    device_id=device.device_id)
        return {"match": False, "score": round(best.score, 4) if best else 0.0}

    # Blacklist is searched in the same collection; a blacklist id as top match
    # is a hit — raise a critical alert and admit nobody (no attendance recorded).
    hit = blacklist_service.is_blacklisted(db, best.id)
    if hit:
        raise_alert(db, tenant_id=device.tenant_id, type="blacklist_hit",
                    message=f"Blacklisted face detected ({hit.reason or 'no reason'})",
                    priority="critical", target_id=str(hit.id), device_id=device.device_id)
        webhook_service.dispatch(
            db, tenant_id=device.tenant_id, event="blacklist.hit",
            payload={"blacklist_id": str(hit.id), "device_id": device.device_id, "score": best.score},
        )
        return {"match": False, "blacklist_hit": True, "score": round(best.score, 4)}

    # best.id is the ZepIris face id, which equals the user id. RLS scopes the
    # lookup to this device's tenant, so a foreign id can never resolve here.
    user = db.get(User, best.id)
    if not user or user.status != "active":
        return {"match": False, "score": round(best.score, 4)}

    recorded = record_event(
        db, tenant_id=device.tenant_id, user_id=str(user.id), action=action,
        device_id=device.device_id, zone_id=device.zone_id,
        match_score=best.score, request_id=request_id,
    )

    # Access-control decision for gated zones (door open / deny + alert).
    access = None
    ppe = None
    if device.zone_id:
        access = access_service.evaluate_for_user(
            db, tenant_id=device.tenant_id, user_id=str(user.id),
            zone_id=device.zone_id, device_id=device.device_id,
        )
        # PPE / safety-gear overlay (Phase 4) for zones that require it.
        zone = db.get(Zone, device.zone_id)
        rule = (zone.access_rule or {}) if zone else {}
        if rule.get("require_ppe"):
            det = get_ppe().detect(image_b64)
            if not det.configured:
                ppe = {"checked": False}
            else:
                ok, missing = evaluate_ppe(det.detections, rule.get("ppe_items") or None)
                ppe = {"checked": True, "ok": ok, "missing": missing}
                if not ok:
                    db.add(AccessEvent(
                        tenant_id=device.tenant_id, user_id=str(user.id), zone_id=device.zone_id,
                        device_id=device.device_id, granted=False, reason="ppe_missing",
                    ))
                    raise_alert(db, tenant_id=device.tenant_id, type="ppe_violation",
                                message=f"PPE missing at {zone.name}: {', '.join(missing)}",
                                priority="high", target_id=str(user.id), device_id=device.device_id)
                    if access:
                        access["granted"] = False
                        access["reason"] = "ppe_missing"

    # Notify ERP / HR sync of the attendance event.
    webhook_service.dispatch(
        db, tenant_id=device.tenant_id, event="attendance.recorded",
        payload={"user_id": str(user.id), "event": recorded["event"],
                 "device_id": device.device_id, "timestamp": recorded["timestamp"]},
    )

    return {
        "match": True,
        "user_id": str(user.id),
        "name": f"{user.first_name} {user.last_name or ''}".strip(),
        "score": round(best.score, 4),
        "event": recorded["event"],
        "timestamp": recorded["timestamp"],
        "duration_minutes": recorded["duration_minutes"],
        "blacklist_hit": False,
        "access": access,
        "ppe": ppe,
    }
