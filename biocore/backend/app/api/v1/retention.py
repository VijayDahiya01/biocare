"""Retention policy + auto-expiry API (BIOCORE_COMPLETE_CHANGE_SPEC §13.3)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, require_role
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.core.roles import PRIVACY, READ_STATUS
from app.models import DataRetentionPolicy
from app.schemas.identity import RetentionPolicyBody
from app.services import retention_service

router = APIRouter(prefix="/retention", tags=["retention"])
_ADMIN = PRIVACY


@router.get("/policies")
def list_policies(request: Request, principal: Principal = Depends(require_role(*READ_STATUS)),
                  db: Session = Depends(auth_db)):
    rows = db.execute(select(DataRetentionPolicy)).scalars().all()
    return success(request, {"items": [{
        "id": str(p.id), "data_category": p.data_category, "retention_period": p.retention_period,
        "expiry_trigger": p.expiry_trigger, "legal_hold_allowed": p.legal_hold_allowed,
        "deletion_method": p.deletion_method,
    } for p in rows]})


@router.post("/policies")
def set_policy(request: Request, body: RetentionPolicyBody,
               principal: Principal = Depends(require_role(*_ADMIN)),
               db: Session = Depends(auth_db)):
    p = db.execute(select(DataRetentionPolicy).where(
        DataRetentionPolicy.tenant_id == principal.tenant_id,
        DataRetentionPolicy.data_category == body.data_category,
    )).scalars().first()
    if p:
        p.retention_period = body.retention_period
        p.expiry_trigger = body.expiry_trigger
        p.deletion_method = body.deletion_method
        p.legal_hold_allowed = body.legal_hold_allowed
    else:
        p = DataRetentionPolicy(
            tenant_id=principal.tenant_id, data_category=body.data_category,
            retention_period=body.retention_period, expiry_trigger=body.expiry_trigger,
            deletion_method=body.deletion_method, legal_hold_allowed=body.legal_hold_allowed,
        )
        db.add(p)
    write_audit(db, action="RETENTION_POLICY_SET", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id,
                metadata={"category": body.data_category, "period": body.retention_period})
    db.commit()
    return success(request, {"data_category": body.data_category, "retention_period": body.retention_period},
                   status_code=201)


@router.post("/sweep")
def sweep(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
          db: Session = Depends(auth_db)):
    n = retention_service.sweep_expired(db, principal.tenant_id)
    write_audit(db, action="RETENTION_SWEEP", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id,
                metadata={"expired": n})
    db.commit()
    return success(request, {"expired": n})
