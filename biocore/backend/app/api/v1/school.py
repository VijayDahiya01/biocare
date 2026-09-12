"""School module: timetable, per-period attendance, guardian pickup
(API Reference §14.2, §14.3)."""
import json
from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    DeviceContext,
    Principal,
    auth_db,
    device_db,
    get_db_for,
    get_principal,
    require_role,
)
from app.core.db import get_db, set_tenant_guc
from app.core.envelope import ApiError, success
from app.core.redis_client import client as redis_client
from app.core.redis_client import guardian_invite_key
from app.core.security import new_token
from app.dpdp.audit import write_audit
from app.models import AttendanceLog, ConsentRecord, GuardianLink, Timetable, User
from app.schemas.modules import GuardianEnroll, GuardianInvite, PickupVerify, TimetableCreate
from app.services.face_service import enroll_face
from app.services.notifier import send_email

GUARDIAN_INVITE_TTL = 7 * 24 * 3600  # 7 days

router = APIRouter(tags=["school"])
_ADMIN = ("entity_admin", "manager", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


# ----- timetable -----
@router.get("/timetable")
def get_timetable(request: Request, principal: Principal = Depends(get_principal),
                  db: Session = Depends(_scoped_db), class_id: str | None = None,
                  day: int | None = None):
    stmt = select(Timetable)
    if class_id:
        stmt = stmt.where(Timetable.class_id == class_id)
    if day is not None:
        stmt = stmt.where(Timetable.day_of_week == day)
    rows = db.execute(stmt).scalars().all()
    items = [{"session_id": str(t.id), "class_id": t.class_id, "subject": t.subject,
              "teacher_user_id": str(t.teacher_user_id) if t.teacher_user_id else None,
              "day_of_week": t.day_of_week, "start_time": t.start_time.isoformat(),
              "end_time": t.end_time.isoformat()} for t in rows]
    return success(request, {"items": items})


@router.post("/timetable")
def create_timetable(request: Request, body: TimetableCreate,
                     principal: Principal = Depends(require_role(*_ADMIN)),
                     db: Session = Depends(auth_db)):
    t = Timetable(tenant_id=principal.tenant_id, class_id=body.class_id, subject=body.subject,
                  teacher_user_id=body.teacher_user_id, day_of_week=body.day_of_week,
                  start_time=time.fromisoformat(body.start_time), end_time=time.fromisoformat(body.end_time))
    db.add(t)
    db.commit()
    return success(request, {"session_id": str(t.id)}, status_code=201)


@router.get("/attendance/session")
def session_attendance(request: Request, session_id: str,
                       principal: Principal = Depends(get_principal),
                       db: Session = Depends(_scoped_db)):
    """Per-period attendance: check-ins today within the timetable slot's window."""
    tt = db.get(Timetable, session_id)
    if not tt:
        raise ApiError(404, "SESSION_NOT_FOUND", "Timetable session not found.")
    today = datetime.now(timezone.utc).date()
    lo = datetime.combine(today, tt.start_time, timezone.utc)
    hi = datetime.combine(today, tt.end_time, timezone.utc)
    rows = db.execute(
        select(AttendanceLog, User).join(User, User.id == AttendanceLog.user_id)
        .where(AttendanceLog.event_type == "check_in", AttendanceLog.created_at.between(lo, hi))
    ).all()
    present = [{"user_id": str(a.user_id), "name": f"{u.first_name} {u.last_name or ''}".strip(),
                "at": a.created_at.isoformat()} for a, u in rows]
    return success(request, {"session_id": session_id, "class_id": tt.class_id, "present": present})


# ----- guardians -----
@router.post("/guardians/invite")
def invite_guardian(request: Request, body: GuardianInvite,
                    principal: Principal = Depends(require_role(*_ADMIN)),
                    db: Session = Depends(auth_db)):
    student = db.get(User, body.student_user_id)
    if not student:
        raise ApiError(404, "STUDENT_NOT_FOUND", "Student not found in this tenant.")
    guardian = User(tenant_id=principal.tenant_id, user_type="guardian", role="guardian",
                    first_name=body.guardian_name, email=body.guardian_email, status="pending_face",
                    enrolled_by="self")
    db.add(guardian)
    db.flush()
    db.add(GuardianLink(tenant_id=principal.tenant_id, guardian_user_id=guardian.id,
                        student_user_id=student.id, relationship=body.relationship))
    write_audit(db, action="GUARDIAN_INVITED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(guardian.id),
                request_id=request.state.request_id)
    db.commit()

    # Tokenised enrollment link (Redis-backed, 7-day TTL) — the guardian captures
    # their face from home via /guardian/<token>; no org code or password needed.
    token = new_token("grd_")
    redis_client.set(
        guardian_invite_key(token),
        json.dumps({"guardian_user_id": str(guardian.id), "tenant_id": principal.tenant_id}),
        ex=GUARDIAN_INVITE_TTL,
    )
    enroll_url = f"/guardian/{token}"
    send_email(to=body.guardian_email, subject="Enrol for school pickup",
               body=f"Open {enroll_url} to capture your face for verified pickup.")
    return success(request, {"guardian_user_id": str(guardian.id),
                             "token": token, "enroll_url": enroll_url}, status_code=201)


@router.post("/guardians/enroll")
def guardian_enroll(request: Request, body: GuardianEnroll, db: Session = Depends(get_db)):
    """Public — guardian captures their face against the invite token (no session)."""
    raw = redis_client.get(guardian_invite_key(body.token))
    if not raw:
        raise ApiError(404, "INVITE_INVALID", "Unknown or expired guardian invite.")
    info = json.loads(raw)
    tenant_id = info["tenant_id"]
    guardian_user_id = info["guardian_user_id"]

    set_tenant_guc(db, tenant_id)
    db.add(ConsentRecord(
        tenant_id=tenant_id, user_id=guardian_user_id, purpose="guardian_pickup",
        method="self",
        acknowledgements={"purpose_understood": True, "sensitivity_understood": True,
                          "rights_understood": True, "freely_given": True},
        active=True, consent_ref=f"CNS-GRD-{guardian_user_id[:8]}",
    ))
    db.commit()
    enroll_face(db, tenant_id=tenant_id, user_id=guardian_user_id, image_b64=body.image,
                enrolled_by="guardian_self")
    redis_client.delete(guardian_invite_key(body.token))
    return success(request, {"guardian_user_id": guardian_user_id, "status": "active"}, status_code=201)


@router.get("/guardians/{student_id}")
def list_guardians(request: Request, student_id: str,
                   principal: Principal = Depends(require_role(*_ADMIN)),
                   db: Session = Depends(_scoped_db)):
    rows = db.execute(
        select(GuardianLink, User).join(User, User.id == GuardianLink.guardian_user_id)
        .where(GuardianLink.student_user_id == student_id)
    ).all()
    items = [{"guardian_user_id": str(g.guardian_user_id),
              "name": f"{u.first_name} {u.last_name or ''}".strip(),
              "relationship": g.relationship} for g, u in rows]
    return success(request, {"items": items})


@router.post("/pickup/verify")
def pickup_verify(request: Request, body: PickupVerify,
                  device: DeviceContext = Depends(device_db)):
    """Kiosk verifies a guardian's face and confirms the student link."""
    from app.services.kiosk_service import _search_match
    guardian = _search_match(device.db, device, body.image)
    link = device.db.execute(
        select(GuardianLink).where(
            GuardianLink.guardian_user_id == guardian.id,
            GuardianLink.student_user_id == body.student_id,
        )
    ).scalar_one_or_none()
    authorised = link is not None
    write_audit(device.db, action="PICKUP_VERIFY", actor_id=device.device_id,
                tenant_id=device.tenant_id, target_id=body.student_id,
                request_id=request.state.request_id,
                metadata={"guardian_user_id": str(guardian.id), "authorised": authorised})
    device.db.commit()
    return success(request, {
        "authorised": authorised,
        "guardian_name": f"{guardian.first_name} {guardian.last_name or ''}".strip() if authorised else None,
    })
