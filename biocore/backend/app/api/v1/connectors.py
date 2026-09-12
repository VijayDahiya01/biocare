"""Business connector API (BIOCORE_COMPLETE_CHANGE_SPEC §19.2).

List the supported connector catalog, pull an external roster into tenant subjects, and push
entry events out. Provider-agnostic: `kind` selects the connector; dev uses in-memory fakes.
No biometric payload is exposed.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.connectors import CONNECTOR_CATALOG, ConnectorError
from app.api.deps import Principal, auth_db, require_role
from app.core.config import settings
from app.core.envelope import ApiError, success
from app.core.roles import ENROLL, READ_STATUS, SECURITY
from app.dpdp.audit import write_audit
from app.models import Integration
from app.services import integration_sync

router = APIRouter(prefix="/connectors", tags=["connectors"])


class ConnectorSync(BaseModel):
    config: dict = {}
    since_hours: int = 24


def _upsert_integration(db: Session, tenant_id, kind: str, config: dict) -> None:
    row = db.execute(select(Integration).where(Integration.kind == kind)).scalars().first()
    if row is None:
        db.add(Integration(tenant_id=tenant_id, kind=kind, config=config or {}, status="active"))
    else:
        row.status = "active"
        if config:
            row.config = config


@router.get("/catalog")
def catalog(request: Request, principal: Principal = Depends(require_role(*READ_STATUS)),
            db: Session = Depends(auth_db)):
    items = [{"kind": k, **v} for k, v in CONNECTOR_CATALOG.items()]
    return success(request, {"items": items, "fake_connectors": settings.fake_connectors})


@router.post("/{kind}/sync-roster")
def sync_roster(request: Request, kind: str, body: ConnectorSync,
                principal: Principal = Depends(require_role(*ENROLL)),
                db: Session = Depends(auth_db)):
    try:
        res = integration_sync.sync_roster(db, tenant_id=principal.tenant_id, kind=kind, config=body.config)
    except ConnectorError as e:
        raise ApiError(400, "CONNECTOR_ERROR", str(e))
    _upsert_integration(db, principal.tenant_id, kind, body.config)
    write_audit(db, action="CONNECTOR_ROSTER_SYNC", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id, metadata=res)
    db.commit()
    return success(request, res, status_code=201)


@router.post("/{kind}/push-events")
def push_events(request: Request, kind: str, body: ConnectorSync,
                principal: Principal = Depends(require_role(*SECURITY)),
                db: Session = Depends(auth_db)):
    try:
        res = integration_sync.push_entry_events(db, tenant_id=principal.tenant_id, kind=kind,
                                                 config=body.config, since_hours=body.since_hours)
    except ConnectorError as e:
        raise ApiError(400, "CONNECTOR_ERROR", str(e))
    write_audit(db, action="CONNECTOR_EVENTS_PUSH", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, request_id=request.state.request_id, metadata=res)
    db.commit()
    return success(request, res, status_code=201)
