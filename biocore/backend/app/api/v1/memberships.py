"""Gym/club memberships (API Reference §14.1)."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import success
from app.models import Membership, User
from app.schemas.modules import MembershipCreate

router = APIRouter(prefix="/memberships", tags=["membership"])
_ADMIN = ("entity_admin", "manager", "super_admin")

_PLAN_DAYS = {"monthly": 30, "quarterly": 90, "annual": 365}


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("/expiring")
def expiring(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
             db: Session = Depends(_scoped_db), days: int = Query(7, ge=1, le=90)):
    cutoff = date.today() + timedelta(days=days)
    rows = db.execute(
        select(Membership, User).join(User, User.id == Membership.user_id)
        .where(Membership.end_date <= cutoff, Membership.end_date >= date.today())
        .order_by(Membership.end_date)
    ).all()
    items = [{"user_id": str(m.user_id), "name": f"{u.first_name} {u.last_name or ''}".strip(),
              "plan_type": m.plan_type, "end_date": m.end_date.isoformat()} for m, u in rows]
    return success(request, {"items": items})


@router.get("/{user_id}")
def get_membership(request: Request, user_id: str,
                   principal: Principal = Depends(require_role(*_ADMIN)),
                   db: Session = Depends(_scoped_db)):
    m = db.execute(
        select(Membership).where(Membership.user_id == user_id)
        .order_by(Membership.end_date.desc()).limit(1)
    ).scalar_one_or_none()
    if not m:
        return success(request, {"user_id": user_id, "membership": None})
    return success(request, {"user_id": user_id, "membership": {
        "plan_type": m.plan_type, "start_date": m.start_date.isoformat(),
        "end_date": m.end_date.isoformat(), "active": m.end_date >= date.today()}})


@router.post("")
def create_membership(request: Request, body: MembershipCreate,
                      principal: Principal = Depends(require_role(*_ADMIN)),
                      db: Session = Depends(auth_db)):
    start = date.fromisoformat(body.start_date)
    end = start + timedelta(days=_PLAN_DAYS[body.plan_type])
    m = Membership(tenant_id=principal.tenant_id, user_id=body.user_id, plan_type=body.plan_type,
                   start_date=start, end_date=end, amount_paid=body.amount_paid, payment_ref=body.payment_ref)
    db.add(m)
    db.commit()
    return success(request, {"membership_id": str(m.id), "end_date": end.isoformat()}, status_code=201)
