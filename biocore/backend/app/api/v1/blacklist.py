"""Blacklist management (API Reference §5.6)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.schemas.access import BlacklistAdd
from app.services import blacklist_service

router = APIRouter(prefix="/blacklist", tags=["blacklist"])
_ADMIN = ("entity_admin", "manager", "security_reception", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("")
def list_blacklist(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                   db: Session = Depends(_scoped_db)):
    return success(request, {"items": blacklist_service.list_entries(db)})


@router.post("")
def add_blacklist(request: Request, body: BlacklistAdd,
                  principal: Principal = Depends(require_role(*_ADMIN)),
                  db: Session = Depends(auth_db)):
    result = blacklist_service.add(
        db, tenant_id=principal.tenant_id, image_b64=body.image,
        reason=body.reason, added_by=principal.user_id,
    )
    write_audit(db, action="BLACKLIST_ADD", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=result["blacklist_id"],
                request_id=request.state.request_id)
    db.commit()
    return success(request, result, status_code=201)
