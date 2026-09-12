"""Events: bulk import, badge printing, footfall (API Reference §14.5)."""
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.models import Event, User
from app.services import reports_service, webhook_service

router = APIRouter(prefix="/events", tags=["events"])
_ADMIN = ("entity_admin", "manager", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.get("")
def list_events(request: Request, principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(_scoped_db)):
    rows = db.execute(select(Event).order_by(Event.created_at.desc())).scalars().all()
    items = [{"event_id": str(e.id), "name": e.name, "created_at": e.created_at.isoformat()} for e in rows]
    return success(request, {"items": items})


@router.post("")
def create_event(request: Request, body: dict,
                 principal: Principal = Depends(require_role(*_ADMIN)),
                 db: Session = Depends(auth_db)):
    ev = Event(tenant_id=principal.tenant_id, name=(body.get("name") or "Event").strip())
    db.add(ev)
    db.commit()
    return success(request, {"event_id": str(ev.id), "name": ev.name}, status_code=201)


@router.post("/import")
async def import_delegates(request: Request, event_id: str = Form(...),
                           file: UploadFile = File(...),
                           principal: Principal = Depends(require_role(*_ADMIN)),
                           db: Session = Depends(auth_db)):
    """Bulk-import a delegate list (CSV) and create pending accounts. Each delegate
    completes face capture (desk or personal link) before they can check in."""
    raw = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    created = 0
    for row in reader:
        email = (row.get("email") or "").strip() or None
        first = (row.get("first_name") or row.get("name") or "Delegate").strip()
        user = User(
            tenant_id=principal.tenant_id, user_type="self_user", role="self_user",
            first_name=first, last_name=(row.get("last_name") or "").strip() or None,
            email=email, member_id=(row.get("member_id") or "").strip() or None,
            status="pending_face", enrolled_by="import", extra={"event_id": event_id},
        )
        db.add(user)
        created += 1
    write_audit(db, action="EVENT_IMPORT", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=event_id,
                request_id=request.state.request_id, metadata={"created": created})
    db.commit()
    return success(request, {"event_id": event_id, "created": created}, status_code=201)


@router.post("/badge-print")
def badge_print(request: Request, body: dict,
                principal: Principal = Depends(require_role(*_ADMIN)),
                db: Session = Depends(auth_db)):
    sent = webhook_service.dispatch(db, tenant_id=principal.tenant_id, event="badge.print",
                                    payload={"user_id": body.get("user_id")})
    db.commit()
    return success(request, {"dispatched": sent})


@router.get("/{event_id}/footfall")
def event_footfall(request: Request, event_id: str,
                   principal: Principal = Depends(require_role(*_ADMIN)),
                   db: Session = Depends(_scoped_db)):
    today = date.today()
    return success(request, {"event_id": event_id,
                             "by_zone": reports_service.footfall(db, from_date=today, to_date=today)})
