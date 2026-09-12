"""DPDP data-subject rights (API Reference §6.1) + audit viewer."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import ApiError, success
from app.core.otp import verify_otp
from app.dpdp.audit import write_audit
from app.dpdp.erasure import erase_user
from app.dpdp.export import export_user
from app.models import AuditLog, ConsentRecord, User
from app.schemas.dpdp import ErasureRequest

router = APIRouter(tags=["dpdp"])


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("/me/data/export")
def export_my_data(request: Request, principal: Principal = Depends(get_principal),
                   db: Session = Depends(_scoped_db)):
    data = export_user(db, user_id=principal.user_id)
    write_audit(db, action="DATA_EXPORT", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=principal.user_id,
                request_id=request.state.request_id)
    db.commit()
    return success(request, data)


@router.post("/me/data/erasure")
def erase_my_data(request: Request, body: ErasureRequest,
                  principal: Principal = Depends(get_principal),
                  db: Session = Depends(auth_db)):
    """Verified erasure cascade. Requires OTP re-authentication."""
    user = db.get(User, principal.user_id)
    if not user or not user.email or not verify_otp(user.email, body.otp):
        raise ApiError(401, "REAUTH_REQUIRED", "Valid OTP re-authentication required.")

    # Log the request BEFORE deletion begins (System doc §8.1).
    write_audit(db, action="ERASURE_REQUESTED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=principal.user_id,
                request_id=request.state.request_id)
    db.commit()

    result = erase_user(db, tenant_id=principal.tenant_id, user_id=principal.user_id)

    write_audit(db, action="ERASURE_COMPLETE", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=principal.user_id,
                request_id=request.state.request_id,
                metadata={"erasure_ref": result["erasure_ref"],
                          "stores_cleared": result["stores_cleared"]})
    db.commit()
    return success(request, result)


@router.post("/me/consent/revoke")
def revoke_consent(request: Request, principal: Principal = Depends(get_principal),
                   db: Session = Depends(auth_db)):
    db.execute(
        update(ConsentRecord)
        .where(ConsentRecord.user_id == principal.user_id, ConsentRecord.active.is_(True))
        .values(active=False, revoked_at=datetime.utcnow())
    )
    write_audit(db, action="CONSENT_REVOKED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=principal.user_id,
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"revoked": True})


# ----- audit viewer (auditor / DPO read-only) -----
@router.get("/audit")
def view_audit(request: Request,
               principal: Principal = Depends(require_role("auditor_dpo", "entity_admin", "super_admin")),
               db: Session = Depends(_scoped_db),
               action: str | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = db.execute(
        stmt.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    items = [
        {"action": a.action, "actor_id": a.actor_id, "target_id": a.target_id,
         "request_id": a.request_id, "metadata": a.metadata_,
         "created_at": a.created_at.isoformat()}
        for a in rows
    ]
    return success(request, {"items": items, "page": page, "page_size": page_size})
