"""Admin side of the person-app: a business invites a person to join."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.models import BusinessInvite
from app.schemas.person import InviteCreate

router = APIRouter(prefix="/businesses", tags=["person-app-admin"])
_ADMIN = ("entity_admin", "manager", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.post("/invites")
def create_invite(request: Request, body: InviteCreate,
                  principal: Principal = Depends(require_role(*_ADMIN)),
                  db: Session = Depends(auth_db)):
    """Invite a person (by email) to join this business; appears in their app."""
    inv = BusinessInvite(tenant_id=principal.tenant_id, email=body.email, role=body.role,
                         created_by=principal.user_id, status="pending")
    db.add(inv)
    write_audit(db, action="BUSINESS_INVITE_CREATED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id,
                metadata={"email": body.email, "role": body.role})
    db.commit()
    return success(request, {"invite_id": str(inv.id), "email": body.email, "status": "pending"}, status_code=201)


@router.get("/invites")
def list_invites(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                 db: Session = Depends(_scoped_db)):
    rows = db.execute(select(BusinessInvite).order_by(BusinessInvite.created_at.desc())).scalars().all()
    items = [{"invite_id": str(i.id), "email": i.email, "role": i.role, "status": i.status} for i in rows]
    return success(request, {"items": items})
