"""GPS field check-in + geofences + emergency headcount
(API Reference §14.6, §14.7)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.zepiris import ZepIrisError, get_zepiris
from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.config import settings
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.models import CurrentPresence, Geofence, User
from app.schemas.modules import GeofenceCreate, GpsCheckin
from app.services import geo
from app.services.attendance_service import record_event

router = APIRouter(tags=["gps", "emergency"])
_ADMIN = ("entity_admin", "manager", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.post("/attendance/gps")
def gps_checkin(request: Request, body: GpsCheckin,
                principal: Principal = Depends(get_principal),
                db: Session = Depends(auth_db)):
    """Field-worker self check-in: face must match the logged-in user, and the
    location must fall inside a configured geofence (if any)."""
    try:
        result = get_zepiris().search(tenant=principal.tenant_id, image_b64=body.image,
                                      top_k=5, threshold=settings.match_threshold)
    except ZepIrisError:
        raise ApiError(502, "FACE_ENGINE_ERROR", "Face engine unavailable.")
    if result.quality.spoof:
        raise ApiError(403, "SPOOF_DETECTED", "Liveness check failed.")
    best = result.best
    # anti-buddy-punch: the captured face must be the logged-in worker.
    if not best or best.id != principal.user_id or best.score < settings.match_threshold:
        raise ApiError(403, "FACE_MISMATCH", "Face does not match the signed-in user.")

    fences = [
        {"name": f.name, "center_lat": float(f.center_lat),
         "center_lng": float(f.center_lng), "radius_km": float(f.radius_km)}
        for f in db.execute(select(Geofence)).scalars().all()
    ]
    within, fence_name = geo.within_any(body.latitude, body.longitude, fences)
    if not within:
        write_audit(db, action="GPS_OUT_OF_FENCE", actor_id=principal.user_id,
                    tenant_id=principal.tenant_id, request_id=request.state.request_id)
        db.commit()
        return success(request, {"match": True, "within_geofence": False, "event": None})

    recorded = record_event(db, tenant_id=principal.tenant_id, user_id=principal.user_id,
                            action="auto", device_id=None, zone_id=None,
                            match_score=best.score, request_id=request.state.request_id)
    # stamp the coordinates on the row just written is omitted for brevity; the
    # event carries the geofence context via the audit entry.
    write_audit(db, action="GPS_CHECKIN", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id,
                metadata={"fence": fence_name, "event": recorded["event"]})
    db.commit()
    return success(request, {"match": True, "within_geofence": True, "event": recorded["event"]})


@router.get("/geofences")
def list_geofences(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                   db: Session = Depends(_scoped_db)):
    rows = db.execute(select(Geofence)).scalars().all()
    items = [{"id": str(g.id), "name": g.name, "center_lat": float(g.center_lat),
              "center_lng": float(g.center_lng), "radius_km": float(g.radius_km)} for g in rows]
    return success(request, {"items": items})


@router.post("/geofences")
def create_geofence(request: Request, body: GeofenceCreate,
                    principal: Principal = Depends(require_role(*_ADMIN)),
                    db: Session = Depends(auth_db)):
    g = Geofence(tenant_id=principal.tenant_id, name=body.name, center_lat=body.center_lat,
                 center_lng=body.center_lng, radius_km=body.radius_km)
    db.add(g)
    db.commit()
    return success(request, {"id": str(g.id)}, status_code=201)


@router.post("/emergency/trigger")
def emergency_trigger(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                      db: Session = Depends(auth_db)):
    """Snapshot who is inside right now for a muster roll."""
    rows = db.execute(
        select(CurrentPresence, User).join(User, User.id == CurrentPresence.user_id)
    ).all()
    people = [{"user_id": str(p.user_id),
               "name": f"{u.first_name} {u.last_name or ''}".strip(),
               "since": p.entered_at.isoformat()} for p, u in rows]
    now = datetime.now(timezone.utc)
    ref = now.strftime("MUSTER-%Y%m%d-%H%M%S")
    from app.services import documents, pdf_service
    pdf = pdf_service.muster_report(ref=ref, people=people, when=now)
    muster_url = documents.save("musters", pdf)
    write_audit(db, action="EMERGENCY_TRIGGERED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id,
                metadata={"inside_count": len(people), "ref": ref})
    db.commit()
    return success(request, {"inside_count": len(people), "people": people,
                             "muster_report_url": muster_url})


@router.get("/emergency/status")
def emergency_status(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                     db: Session = Depends(_scoped_db)):
    rows = db.execute(
        select(CurrentPresence, User).join(User, User.id == CurrentPresence.user_id)
    ).all()
    people = [{"user_id": str(p.user_id),
               "name": f"{u.first_name} {u.last_name or ''}".strip()} for p, u in rows]
    return success(request, {"inside_count": len(people), "people": people})
