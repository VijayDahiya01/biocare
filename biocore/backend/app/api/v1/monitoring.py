"""Monitoring API (BIOCORE_COMPLETE_CHANGE_SPEC §23).

Read-only admin views: the §23 metric set (DB-derived rates/counts + in-process operational
counters/latencies) and the evaluated §23 alerts. No biometric data is exposed — rates,
counts and latencies only.
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, require_role
from app.core.envelope import success
from app.core.roles import READ_STATUS
from app.services import monitoring_service

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/metrics")
def get_metrics(request: Request, window_hours: int = Query(24, ge=1, le=720),
                principal: Principal = Depends(require_role(*READ_STATUS)),
                db: Session = Depends(auth_db)):
    return success(request, monitoring_service.collect_metrics(db, window_hours=window_hours))


@router.get("/alerts")
def get_alerts(request: Request, window_hours: int = Query(24, ge=1, le=720),
               principal: Principal = Depends(require_role(*READ_STATUS)),
               db: Session = Depends(auth_db)):
    m = monitoring_service.collect_metrics(db, window_hours=window_hours)
    alerts = monitoring_service.evaluate_alerts(db, m)
    return success(request, {"alerts": alerts, "count": len(alerts)})
