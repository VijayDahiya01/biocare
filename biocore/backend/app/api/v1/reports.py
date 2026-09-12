"""Reports & analytics (API Reference §11)."""
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.models import Tenant
from app.schemas.modules import ReportSchedule
from app.services import reports_service

router = APIRouter(prefix="/reports", tags=["reports"])
_VIEW = ("entity_admin", "manager", "hr_payroll", "auditor_dpo", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


def _late_threshold(db: Session, tenant_id: str) -> str:
    tenant = db.get(Tenant, tenant_id)
    return (tenant.settings or {}).get("alerts", {}).get("late_threshold") or "09:30"


@router.get("/attendance")
def attendance_report(request: Request, principal: Principal = Depends(require_role(*_VIEW)),
                      db: Session = Depends(_scoped_db),
                      from_: date = Query(alias="from"), to: date = Query(alias="to"),
                      group_by: str = "day"):
    return success(request, {"items": reports_service.attendance(db, from_date=from_, to_date=to, group_by=group_by)})


@router.get("/late")
def late_report(request: Request, principal: Principal = Depends(require_role(*_VIEW)),
                db: Session = Depends(_scoped_db),
                from_: date = Query(alias="from"), to: date = Query(alias="to")):
    th = _late_threshold(db, principal.tenant_id)
    return success(request, {"threshold": th, "items": reports_service.late(db, from_date=from_, to_date=to, threshold=th)})


@router.get("/absent")
def absent_report(request: Request, principal: Principal = Depends(require_role(*_VIEW)),
                  db: Session = Depends(_scoped_db), on: date = Query(...)):
    return success(request, {"items": reports_service.absent(db, on_date=on)})


@router.get("/zone-access")
def zone_access_report(request: Request, principal: Principal = Depends(require_role(*_VIEW)),
                       db: Session = Depends(_scoped_db),
                       from_: date = Query(alias="from"), to: date = Query(alias="to")):
    return success(request, {"items": reports_service.zone_access(db, from_date=from_, to_date=to)})


@router.get("/footfall")
def footfall_report(request: Request, principal: Principal = Depends(require_role(*_VIEW)),
                    db: Session = Depends(_scoped_db),
                    from_: date = Query(alias="from"), to: date = Query(alias="to")):
    return success(request, {"items": reports_service.footfall(db, from_date=from_, to_date=to)})


@router.get("/movement")
def movement_report(request: Request, principal: Principal = Depends(require_role(*_VIEW)),
                    db: Session = Depends(_scoped_db), user_id: str = Query(...),
                    from_: date = Query(alias="from"), to: date = Query(alias="to")):
    return success(request, {"items": reports_service.movement(db, user_id=user_id, from_date=from_, to_date=to)})


@router.get("/export")
def export_report(request: Request, principal: Principal = Depends(require_role(*_VIEW)),
                  db: Session = Depends(_scoped_db),
                  report: str = "attendance", format: str = "csv",
                  from_: date = Query(alias="from"), to: date = Query(alias="to"),
                  group_by: str = "day"):
    if format != "csv":
        raise ApiError(400, "UNSUPPORTED_FORMAT", "Only csv export is implemented in this phase.")
    fns = {
        "attendance": lambda: reports_service.attendance(db, from_date=from_, to_date=to, group_by=group_by),
        "late": lambda: reports_service.late(db, from_date=from_, to_date=to, threshold=_late_threshold(db, principal.tenant_id)),
        "zone-access": lambda: reports_service.zone_access(db, from_date=from_, to_date=to),
        "footfall": lambda: reports_service.footfall(db, from_date=from_, to_date=to),
    }
    if report not in fns:
        raise ApiError(400, "UNKNOWN_REPORT", f"No exporter for report '{report}'.")
    rows = fns[report]()
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={report}.csv"})


@router.post("/schedule")
def schedule_report(request: Request, body: ReportSchedule,
                    principal: Principal = Depends(require_role(*_VIEW)),
                    db: Session = Depends(auth_db)):
    # Persisted into tenant settings; a worker (RabbitMQ/cron) sends them in a later phase.
    tenant = db.get(Tenant, principal.tenant_id)
    settings = dict(tenant.settings or {})
    scheduled = settings.get("scheduled_reports", [])
    scheduled.append(body.model_dump())
    settings["scheduled_reports"] = scheduled
    tenant.settings = settings
    write_audit(db, action="REPORT_SCHEDULED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id)
    db.commit()
    return success(request, {"scheduled": body.model_dump()}, status_code=201)
