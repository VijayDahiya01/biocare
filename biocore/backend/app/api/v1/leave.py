"""Leave management (API Reference §8)."""
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.models import LeaveRequest
from app.schemas.modules import LeaveDecision, LeaveRequestBody
from app.services.leave_logic import balance, days_inclusive

router = APIRouter(prefix="/leave", tags=["leave"])
_APPROVERS = ("entity_admin", "manager", "hr_payroll", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("")
def list_leave(request: Request, principal: Principal = Depends(get_principal),
               db: Session = Depends(_scoped_db), status: str | None = None,
               user_id: str | None = None):
    stmt = select(LeaveRequest)
    # members see only their own; approvers can see all / filter.
    if principal.role not in _APPROVERS:
        stmt = stmt.where(LeaveRequest.user_id == principal.user_id)
    elif user_id:
        stmt = stmt.where(LeaveRequest.user_id == user_id)
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    rows = db.execute(stmt.order_by(LeaveRequest.created_at.desc())).scalars().all()
    items = [{"leave_id": str(r.id), "user_id": str(r.user_id), "type": r.type,
              "from": r.from_date.isoformat(), "to": r.to_date.isoformat(),
              "reason": r.reason, "status": r.status} for r in rows]
    return success(request, {"items": items})


@router.post("")
def submit_leave(request: Request, body: LeaveRequestBody,
                 principal: Principal = Depends(get_principal),
                 db: Session = Depends(auth_db)):
    lr = LeaveRequest(
        tenant_id=principal.tenant_id, user_id=principal.user_id, type=body.type,
        from_date=date.fromisoformat(body.from_date), to_date=date.fromisoformat(body.to_date),
        reason=body.reason, status="pending",
    )
    db.add(lr)
    db.commit()
    return success(request, {"leave_id": str(lr.id), "status": "pending"}, status_code=201)


@router.post("/{leave_id}/approve")
def approve(request: Request, leave_id: str, body: LeaveDecision,
            principal: Principal = Depends(require_role(*_APPROVERS)),
            db: Session = Depends(auth_db)):
    lr = db.get(LeaveRequest, leave_id)
    if not lr:
        raise ApiError(404, "LEAVE_NOT_FOUND", "Leave request not found.")
    lr.status = "approved"
    lr.note = body.note
    lr.decided_by = principal.user_id
    write_audit(db, action="LEAVE_APPROVED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=leave_id,
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"leave_id": leave_id, "status": "approved"})


@router.post("/{leave_id}/reject")
def reject(request: Request, leave_id: str, body: LeaveDecision,
           principal: Principal = Depends(require_role(*_APPROVERS)),
           db: Session = Depends(auth_db)):
    lr = db.get(LeaveRequest, leave_id)
    if not lr:
        raise ApiError(404, "LEAVE_NOT_FOUND", "Leave request not found.")
    lr.status = "rejected"
    lr.note = body.reason
    lr.decided_by = principal.user_id
    write_audit(db, action="LEAVE_REJECTED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=leave_id,
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"leave_id": leave_id, "status": "rejected"})


@router.get("/balance/{user_id}")
def leave_balance(request: Request, user_id: str,
                  principal: Principal = Depends(get_principal),
                  db: Session = Depends(_scoped_db)):
    year = date.today().year
    rows = db.execute(
        select(LeaveRequest).where(LeaveRequest.user_id == user_id,
                                   LeaveRequest.status == "approved")
    ).scalars().all()
    used: dict[str, int] = defaultdict(int)
    for r in rows:
        if r.from_date.year == year:
            used[r.type] += days_inclusive(r.from_date.toordinal(), r.to_date.toordinal())
    return success(request, balance(dict(used)))
