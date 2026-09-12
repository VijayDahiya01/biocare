"""HR, payroll & wages (API Reference §9)."""
import csv
import io
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import ApiError, success
from app.models import CurrentPresence, LeaveRequest, User, WageConfig
from app.schemas.modules import WageConfigRequest
from app.services import payroll_service

router = APIRouter(tags=["hr"])
_HR = ("entity_admin", "hr_payroll", "manager", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("/wage-config/{user_id}")
def get_wage(request: Request, user_id: str, principal: Principal = Depends(require_role(*_HR)),
             db: Session = Depends(_scoped_db)):
    rows = db.execute(
        select(WageConfig).where(WageConfig.user_id == user_id)
        .order_by(WageConfig.effective_from.desc())
    ).scalars().all()
    items = [{"rate_per_hour": float(w.rate_per_hour),
              "overtime_multiplier": float(w.overtime_multiplier),
              "effective_from": w.effective_from.isoformat()} for w in rows]
    return success(request, {"user_id": user_id, "history": items})


@router.post("/wage-config")
def set_wage(request: Request, body: WageConfigRequest,
             principal: Principal = Depends(require_role(*_HR)),
             db: Session = Depends(auth_db)):
    wage = WageConfig(
        tenant_id=principal.tenant_id, user_id=body.user_id,
        rate_per_hour=body.rate_per_hour, overtime_multiplier=body.overtime_multiplier,
        effective_from=date.fromisoformat(body.effective_from),
    )
    db.add(wage)
    db.commit()
    return success(request, {"wage_config_id": str(wage.id)}, status_code=201)


@router.get("/payroll/calculate")
def calculate(request: Request, principal: Principal = Depends(require_role(*_HR)),
              db: Session = Depends(_scoped_db),
              from_: date = Query(alias="from"), to: date = Query(alias="to"),
              user_id: str | None = None):
    items = payroll_service.calculate(db, from_date=from_, to_date=to, user_id=user_id)
    return success(request, {"items": items, "total_payable": round(sum(i["total"] for i in items), 2)})


@router.get("/payroll/export")
def export_payroll(request: Request, principal: Principal = Depends(require_role(*_HR)),
                   db: Session = Depends(_scoped_db),
                   from_: date = Query(alias="from"), to: date = Query(alias="to"),
                   format: str = "csv"):
    items = payroll_service.calculate(db, from_date=from_, to_date=to)
    if format != "csv":
        raise ApiError(400, "UNSUPPORTED_FORMAT", "Only csv export is implemented in this phase.")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "name", "regular_hours", "overtime_hours", "base_pay", "overtime_pay", "total"])
    for it in items:
        w.writerow([it["user_id"], it["name"], it["regular_hours"], it["overtime_hours"],
                    it["base_pay"], it["overtime_pay"], it["total"]])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=payroll.csv"})


@router.get("/hr/summary")
def hr_summary(request: Request, principal: Principal = Depends(require_role(*_HR)),
               db: Session = Depends(_scoped_db)):
    today = datetime.now(timezone.utc).date()
    headcount = db.execute(
        select(func.count()).select_from(User).where(User.status == "active", User.deleted_at.is_(None))
    ).scalar_one()
    present = db.execute(select(func.count()).select_from(CurrentPresence)).scalar_one()
    on_leave = db.execute(
        select(func.count()).select_from(LeaveRequest).where(
            LeaveRequest.status == "approved",
            LeaveRequest.from_date <= today, LeaveRequest.to_date >= today,
        )
    ).scalar_one()
    return success(request, {"headcount": headcount, "present_today": present,
                             "on_leave": on_leave})
