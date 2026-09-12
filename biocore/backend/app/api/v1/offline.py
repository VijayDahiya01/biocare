"""Offline / poor-network mode API (BIOCORE_COMPLETE_CHANGE_SPEC §16).

Terminal-authenticated (device token). A terminal downloads an encrypted device-bound roster
(Option B), keeps admitting authorized subjects while offline, then syncs its decisions and
confirms it wiped the local roster when the network returns. Admins get read-only roster
accountability. The encrypted payload is never persisted server-side (§16, §14.1).
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DeviceContext, Principal, auth_db, device_db, require_role
from app.core.config import settings
from app.core.envelope import ApiError, success
from app.core.roles import READ_STATUS
from app.dpdp.audit import write_audit
from app.models import OfflineRoster
from app.schemas.entry import OfflineSyncRequest, RosterWipe
from app.services import offline_roster

router = APIRouter(prefix="/offline", tags=["offline"])


@router.post("/roster")
def build_roster(request: Request, ctx: DeviceContext = Depends(device_db)):
    """Issue an encrypted, device-bound offline roster (§16 Option B). Gated on offline_mode."""
    if settings.offline_mode != "roster":
        raise ApiError(409, "OFFLINE_ROSTER_DISABLED",
                       f"Encrypted offline roster is not enabled (offline_mode={settings.offline_mode!r}).")
    result = offline_roster.build_roster(ctx.db, device_ctx=ctx)
    write_audit(ctx.db, action="OFFLINE_ROSTER_ISSUED", tenant_id=ctx.tenant_id,
                target_id=result["roster_id"], request_id=request.state.request_id,
                metadata={"device": ctx.device_id, "subjects": result["subject_count"]})
    ctx.db.commit()
    return success(request, result, status_code=201)


@router.post("/sync")
def sync(request: Request, body: OfflineSyncRequest, ctx: DeviceContext = Depends(device_db)):
    """Sync decisions made offline (idempotent by nonce)."""
    res = offline_roster.sync_decisions(ctx.db, device_ctx=ctx,
                                        decisions=[d.model_dump() for d in body.decisions])
    write_audit(ctx.db, action="OFFLINE_DECISIONS_SYNCED", tenant_id=ctx.tenant_id,
                request_id=request.state.request_id,
                metadata={"device": ctx.device_id, **res})
    ctx.db.commit()
    return success(request, res, status_code=201)


@router.post("/roster/wipe")
def wipe(request: Request, body: RosterWipe, ctx: DeviceContext = Depends(device_db)):
    """The terminal confirms it auto-wiped the local roster."""
    ok = offline_roster.wipe(ctx.db, device_ctx=ctx, roster_id=body.roster_id)
    if not ok:
        raise ApiError(404, "ROSTER_NOT_FOUND", "No such roster for this device.")
    write_audit(ctx.db, action="OFFLINE_ROSTER_WIPED", tenant_id=ctx.tenant_id,
                target_id=body.roster_id, request_id=request.state.request_id)
    ctx.db.commit()
    return success(request, {"roster_id": body.roster_id, "status": "wiped"})


@router.get("/rosters")
def list_rosters(request: Request, principal: Principal = Depends(require_role(*READ_STATUS)),
                 db: Session = Depends(auth_db)):
    """Read-only accountability: which terminals hold/held an offline roster (§16)."""
    rows = db.execute(select(OfflineRoster).order_by(OfflineRoster.issued_at.desc()).limit(100)).scalars().all()
    items = [{
        "id": str(r.id), "device_id": str(r.device_id),
        "zone_id": str(r.zone_id) if r.zone_id else None,
        "subject_count": r.subject_count, "status": r.status,
        "issued_at": r.issued_at.isoformat() if r.issued_at else None,
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        "wiped_at": r.wiped_at.isoformat() if r.wiped_at else None,
    } for r in rows]
    return success(request, {"items": items, "offline_mode": settings.offline_mode})
