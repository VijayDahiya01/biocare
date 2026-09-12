"""Zones, badges, and badge assignment (API Reference §5.2, §5.3)."""
from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, require_role
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.models import Badge, User, UserBadge, Zone
from app.schemas.access import AssignBadge, BadgeCreate, ZoneCreate
from app.schemas.modules import ZoneUpdate

router = APIRouter(tags=["access"])
_ADMIN = ("entity_admin", "manager", "super_admin")


# ----- zones -----
@router.get("/zones")
def list_zones(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
               db: Session = Depends(auth_db)):
    rows = db.execute(select(Zone)).scalars().all()
    items = [{"zone_id": str(z.id), "name": z.name, "type": z.type,
              "access_rule": z.access_rule, "door_webhook_url": z.door_webhook_url} for z in rows]
    return success(request, {"items": items, "total": len(items)})


@router.post("/zones")
def create_zone(request: Request, body: ZoneCreate,
                principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    zone = Zone(tenant_id=principal.tenant_id, name=body.name, type=body.type,
                access_rule=body.access_rule, door_webhook_url=body.door_webhook_url)
    db.add(zone)
    write_audit(db, action="ZONE_CREATED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id)
    db.commit()
    return success(request, {"zone_id": str(zone.id)}, status_code=201)


@router.patch("/zones/{zone_id}")
def update_zone(request: Request, zone_id: str, body: ZoneUpdate,
                principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    zone = db.get(Zone, zone_id)
    if not zone:
        raise ApiError(404, "ZONE_NOT_FOUND", "Zone not found in this tenant.")
    if body.name is not None:
        zone.name = body.name
    if body.access_rule is not None:
        zone.access_rule = body.access_rule
    if body.door_webhook_url is not None:
        zone.door_webhook_url = body.door_webhook_url
    write_audit(db, action="ZONE_UPDATED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=zone_id,
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"zone_id": zone_id})


# ----- badges -----
@router.get("/badges")
def list_badges(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    rows = db.execute(select(Badge)).scalars().all()
    items = [{"badge_id": str(b.id), "name": b.name, "zones": b.zones,
              "time_rule": b.time_rule, "time_windows": b.time_windows,
              "expiry": b.expiry.isoformat() if b.expiry else None,
              "print_badge": b.print_badge} for b in rows]
    return success(request, {"items": items, "total": len(items)})


@router.post("/badges")
def create_badge(request: Request, body: BadgeCreate,
                 principal: Principal = Depends(require_role(*_ADMIN)),
                 db: Session = Depends(auth_db)):
    badge = Badge(
        tenant_id=principal.tenant_id, name=body.name, zones=body.zones,
        time_rule=body.time_rule, time_windows=body.time_windows,
        expiry=date.fromisoformat(body.expiry) if body.expiry else None,
        print_badge=body.print_badge,
    )
    db.add(badge)
    write_audit(db, action="BADGE_CREATED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id)
    db.commit()
    return success(request, {"badge_id": str(badge.id)}, status_code=201)


@router.post("/badges/assign")
def assign_badge(request: Request, body: AssignBadge,
                 principal: Principal = Depends(require_role(*_ADMIN)),
                 db: Session = Depends(auth_db)):
    # RLS scopes these gets to the tenant; a foreign id resolves to None -> 404.
    if not db.get(User, body.user_id) or not db.get(Badge, body.badge_id):
        raise ApiError(404, "NOT_FOUND", "User or badge not found in this tenant.")
    existing = db.get(UserBadge, (body.user_id, body.badge_id))
    if not existing:
        db.add(UserBadge(tenant_id=principal.tenant_id, user_id=body.user_id, badge_id=body.badge_id))
    write_audit(db, action="BADGE_ASSIGNED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=body.user_id,
                request_id=request.state.request_id, metadata={"badge_id": body.badge_id})
    db.commit()
    return success(request, {"user_id": body.user_id, "badge_id": body.badge_id})
