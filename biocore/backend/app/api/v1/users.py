"""Users list (API Reference §5.1). Tenant-scoped; admin-facing."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.dpdp.erasure import erase_user
from app.models import User
from app.schemas.modules import UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
_ADMIN = ("entity_admin", "manager", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("")
def list_users(
    request: Request,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(_scoped_db),
    status: str | None = None,
    department: str | None = None,
    sort: str = Query("created", pattern="^(created|name)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    stmt = select(User).where(User.deleted_at.is_(None))
    if status:
        stmt = stmt.where(User.status == status)
    if department:
        stmt = stmt.where(User.department == department)

    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    order = User.created_at.desc() if sort == "created" else User.first_name.asc()
    rows = db.execute(
        stmt.order_by(order).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    items = [
        {
            "user_id": str(u.id),
            "name": f"{u.first_name} {u.last_name or ''}".strip(),
            "email": u.email,
            "user_type": u.user_type,
            "role": u.role,
            "department": u.department,
            "status": u.status,
            "member_id": u.member_id,
            "created_at": u.created_at.isoformat(),
        }
        for u in rows
    ]
    return success(request, {"items": items, "total": total, "page": page, "page_size": page_size})


def _user_dict(u: User) -> dict:
    return {"user_id": str(u.id), "name": f"{u.first_name} {u.last_name or ''}".strip(),
            "email": u.email, "user_type": u.user_type, "role": u.role,
            "department": u.department, "status": u.status, "member_id": u.member_id}


@router.get("/{user_id}")
def get_user(request: Request, user_id: str,
             principal: Principal = Depends(require_role(*_ADMIN)),
             db: Session = Depends(_scoped_db)):
    u = db.get(User, user_id)
    if not u:
        raise ApiError(404, "USER_NOT_FOUND", "User not found in this tenant.")
    return success(request, _user_dict(u))


@router.patch("/{user_id}")
def update_user(request: Request, user_id: str, body: UserUpdate,
                principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    u = db.get(User, user_id)
    if not u:
        raise ApiError(404, "USER_NOT_FOUND", "User not found in this tenant.")
    for field in ("role", "department", "status", "member_id"):
        val = getattr(body, field)
        if val is not None:
            setattr(u, field, val)
    write_audit(db, action="USER_UPDATED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=user_id,
                request_id=request.state.request_id)
    db.commit()
    return success(request, _user_dict(u))


@router.delete("/{user_id}")
def delete_user(request: Request, user_id: str,
                principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    """DELETE triggers the full DPDP erasure cascade (System doc §8.1)."""
    write_audit(db, action="ERASURE_REQUESTED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=user_id,
                request_id=request.state.request_id, metadata={"by": "admin"})
    db.commit()
    result = erase_user(db, tenant_id=principal.tenant_id, user_id=user_id)
    write_audit(db, action="ERASURE_COMPLETE", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=user_id,
                request_id=request.state.request_id,
                metadata={"erasure_ref": result["erasure_ref"], "stores_cleared": result["stores_cleared"]})
    db.commit()
    return success(request, result)
