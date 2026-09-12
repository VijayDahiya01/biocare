"""DPDP grievance redressal (Screen M7; Doc 1 §8 #10).

Members file grievances; the DPO/admin reviews and resolves them.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.models import Grievance, User
from app.schemas.dpdp import GrievanceCreate, GrievanceResolve

router = APIRouter(tags=["grievance"])
_DPO = ("entity_admin", "auditor_dpo", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.post("/grievance")
def file_grievance(request: Request, body: GrievanceCreate,
                   principal: Principal = Depends(get_principal),
                   db: Session = Depends(auth_db)):
    """Any signed-in member raises a grievance."""
    g = Grievance(tenant_id=principal.tenant_id, user_id=principal.user_id,
                  subject=body.subject, message=body.message, status="open")
    db.add(g)
    write_audit(db, action="GRIEVANCE_FILED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(g.id) if g.id else None,
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"grievance_id": str(g.id), "status": "open"}, status_code=201)


@router.get("/grievances")
def list_grievances(request: Request,
                    principal: Principal = Depends(get_principal),
                    db: Session = Depends(_scoped_db), status: str | None = None):
    """DPO/admin see all; members see only their own."""
    stmt = select(Grievance, User).join(User, User.id == Grievance.user_id)
    if principal.role not in _DPO:
        stmt = stmt.where(Grievance.user_id == principal.user_id)
    if status:
        stmt = stmt.where(Grievance.status == status)
    rows = db.execute(stmt.order_by(Grievance.created_at.desc()).limit(500)).all()
    items = [{
        "grievance_id": str(g.id), "user_id": str(g.user_id),
        "user_name": f"{u.first_name} {u.last_name or ''}".strip(),
        "subject": g.subject, "message": g.message, "status": g.status,
        "resolution": g.resolution, "created_at": g.created_at.isoformat(),
    } for g, u in rows]
    return success(request, {"items": items})


@router.post("/grievances/{grievance_id}/resolve")
def resolve_grievance(request: Request, grievance_id: str, body: GrievanceResolve,
                      principal: Principal = Depends(require_role(*_DPO)),
                      db: Session = Depends(auth_db)):
    g = db.get(Grievance, grievance_id)
    if not g:
        raise ApiError(404, "GRIEVANCE_NOT_FOUND", "Grievance not found.")
    g.status = "resolved"
    g.resolution = body.resolution
    g.resolved_by = principal.user_id
    g.resolved_at = datetime.now(timezone.utc)
    write_audit(db, action="GRIEVANCE_RESOLVED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=grievance_id,
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"grievance_id": grievance_id, "status": "resolved"})
