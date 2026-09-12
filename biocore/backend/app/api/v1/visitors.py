"""Visitor temporary enrollment (API Reference §5.5)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, require_role
from app.core.db import get_db
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.schemas.access import VisitorEnrollRequest, VisitorInviteRequest
from app.services import visitor_service

router = APIRouter(prefix="/visitors", tags=["visitors"])
_RECEPTION = ("entity_admin", "manager", "security_reception", "super_admin")


@router.post("/invite")
def invite(request: Request, body: VisitorInviteRequest,
           principal: Principal = Depends(require_role(*_RECEPTION)),
           db: Session = Depends(auth_db)):
    result = visitor_service.invite(
        db, tenant_id=principal.tenant_id, host_user_id=body.host_user_id,
        visitor_name=body.visitor_name, valid_hours=body.valid_hours,
    )
    write_audit(db, action="VISITOR_INVITED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=result["invite_id"],
                request_id=request.state.request_id)
    db.commit()
    return success(request, result, status_code=201)


@router.post("/enroll")
def enroll(request: Request, body: VisitorEnrollRequest, db: Session = Depends(get_db)):
    """Public — the visitor presents the invite token (no session)."""
    result = visitor_service.enroll(
        db, token=body.token, name=body.name, phone=body.phone, image=body.image,
    )
    return success(request, result, status_code=201)
