"""Device trust API (BIOCORE_COMPLETE_CHANGE_SPEC §10.5, §12.2).

Pair a terminal (issues a device token + certificate), attest it, rotate/revoke its
certificate, and expose its policy + heartbeat. Pair/rotate/revoke are admin-authenticated;
attest/policy/heartbeat are terminal-authenticated (device token). Certificates are shown
ONCE and stored only as a hash (thumbprint), like device tokens (§12.1).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.api.deps import DeviceContext, Principal, auth_db, device_db, require_role
from app.core.config import settings
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.core.roles import READ_STATUS, SECURITY
from app.models import Device, DeviceCertificate
from app.schemas.entry import DeviceAttest, DeviceIdBody, DevicePair, DevicePosture
from app.services import device_trust
from app.services.device_service import register_device
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/devices", tags=["device-trust"])
_ADMIN = SECURITY


@router.post("/pair")
def pair(request: Request, body: DevicePair,
         principal: Principal = Depends(require_role(*_ADMIN)),
         db: Session = Depends(auth_db)):
    """Register a terminal and issue its first certificate (both shown once)."""
    res = register_device(db, tenant_id=principal.tenant_id, name=body.name,
                          zone_id=body.zone_id, capture_method=body.capture_method)
    raw_cert, _ = device_trust.issue_certificate(db, tenant_id=principal.tenant_id,
                                                  device_id=res["device_id"])
    write_audit(db, action="DEVICE_PAIRED", actor_id=principal.user_id, tenant_id=principal.tenant_id,
                target_id=res["device_id"], request_id=request.state.request_id)
    db.commit()
    return success(request, {**res, "certificate": raw_cert}, status_code=201)


@router.post("/attest")
def attest(request: Request, body: DeviceAttest, ctx: DeviceContext = Depends(device_db)):
    trusted = device_trust.attest(ctx.db, device_id=ctx.device_id, raw_certificate=body.certificate)
    ctx.db.commit()
    return success(request, {"device_id": ctx.device_id, "trusted": trusted})


@router.post("/rotate-certificate")
def rotate_certificate(request: Request, body: DeviceIdBody,
                       principal: Principal = Depends(require_role(*_ADMIN)),
                       db: Session = Depends(auth_db)):
    raw_cert, _ = device_trust.rotate(db, tenant_id=principal.tenant_id, device_id=body.device_id)
    write_audit(db, action="DEVICE_CERT_ROTATED", actor_id=principal.user_id, tenant_id=principal.tenant_id,
                target_id=body.device_id, request_id=request.state.request_id)
    db.commit()
    return success(request, {"device_id": body.device_id, "certificate": raw_cert}, status_code=201)


@router.post("/revoke")
def revoke(request: Request, body: DeviceIdBody,
           principal: Principal = Depends(require_role(*_ADMIN)),
           db: Session = Depends(auth_db)):
    n = device_trust.revoke(db, device_id=body.device_id)
    d = db.get(Device, body.device_id)
    if d:
        d.status = "disabled"
    write_audit(db, action="DEVICE_REVOKED", actor_id=principal.user_id, tenant_id=principal.tenant_id,
                target_id=body.device_id, request_id=request.state.request_id, metadata={"certs_revoked": n})
    db.commit()
    return success(request, {"device_id": body.device_id, "certificates_revoked": n, "status": "disabled"})


@router.get("/{device_id}/policy")
def device_policy(request: Request, device_id: str, ctx: DeviceContext = Depends(device_db)):
    # a terminal may read only its OWN policy (identified by its device token, not the path)
    d = ctx.db.get(Device, ctx.device_id)
    return success(request, {"device_id": ctx.device_id, "tenant_id": ctx.tenant_id,
                             "zone_id": ctx.zone_id,
                             "capture_method": d.capture_method if d else None,
                             "status": d.status if d else None,
                             "policy_profile": settings.default_policy_profile,
                             "offline_mode": settings.offline_mode,  # §16: off | manual | roster
                             "require_signed_context": settings.require_signed_context})


@router.post("/{device_id}/heartbeat")
def heartbeat(request: Request, device_id: str, ctx: DeviceContext = Depends(device_db)):
    d = ctx.db.get(Device, ctx.device_id)
    if d:
        d.last_seen = datetime.now(timezone.utc)
        d.status = "online"
        ctx.db.commit()
    return success(request, {"device_id": ctx.device_id, "ok": True})


@router.post("/{device_id}/posture")
def posture(request: Request, device_id: str, body: DevicePosture,
            ctx: DeviceContext = Depends(device_db)):
    """A terminal attests its OWN hardening posture (§12.3), identified by its device token."""
    d = device_trust.record_posture(
        ctx.db, device_id=ctx.device_id,
        posture=body.model_dump(exclude={"software_version"}),
        software_version=body.software_version)
    ctx.db.commit()
    return success(request, {"device_id": ctx.device_id, "hardening": d.hardening,
                             "software_version": d.software_version,
                             "compliant": device_trust.posture_ok(d)}, status_code=201)


@router.get("/certificates")
def list_certificates(request: Request, principal: Principal = Depends(require_role(*READ_STATUS)),
                      db: Session = Depends(auth_db)):
    rows = db.execute(
        select(DeviceCertificate, Device).join(Device, Device.id == DeviceCertificate.device_id)
        .order_by(DeviceCertificate.issued_at.desc()).limit(100)
    ).all()
    items = [{
        "id": str(c.id), "device_id": str(c.device_id), "device_name": d.name,
        "thumbprint": (c.certificate_thumbprint or "")[:12] + "…",
        "issued_at": c.issued_at.isoformat() if c.issued_at else None,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "revoked": c.revoked_at is not None,
        "software_version": d.software_version,
        "hardened": device_trust.posture_ok(d),
        "posture_attested_at": d.posture_attested_at.isoformat() if d.posture_attested_at else None,
    } for c, d in rows]
    return success(request, {"items": items})
