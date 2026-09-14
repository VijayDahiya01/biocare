"""Person-centric identity + hub + join (see docs/PERSON_APP.md).

These are cross-tenant by design (your data at every business). Each runs under
bypass_rls() but ALWAYS hard-filters to the authenticated person_id / their email,
and audits the access — the data subject reading their own data, never anyone else.
"""
import secrets
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.zepiris import ZepIrisError, get_zepiris
from app.core.db import bypass_rls
from app.core.envelope import ApiError
from app.dpdp.audit import write_audit
from app.dpdp.erasure import erase_user
from app.models import (
    AttendanceLog,
    Badge,
    BusinessInvite,
    ConsentRecord,
    Event,
    EventRegistration,
    FaceCredential,
    FaceRecord,
    Person,
    PersonFace,
    Tenant,
    TenantSubject,
    User,
    UserBadge,
)
from app.services import face_vault

_REQUIRED_ACKS = ("purpose_understood", "sensitivity_understood", "rights_understood", "freely_given")


def _master_object_key(db: Session, person_id: str) -> str | None:
    pf = db.execute(
        select(PersonFace).where(PersonFace.person_id == person_id, PersonFace.is_active.is_(True))
    ).scalar_one_or_none()
    return pf.object_key if pf else None


def resolve_or_create_person(db: Session, *, email: str) -> str:
    """Find the person by email, or create one — and link any existing per-business
    memberships with that email onto this identity. Returns person_id."""
    with bypass_rls(db):
        p = db.execute(select(Person).where(Person.email == email)).scalar_one_or_none()
        if not p:
            u = db.execute(select(User).where(User.email == email).limit(1)).scalar_one_or_none()
            # No name has been given yet. The email prefix is a PLACEHOLDER so the row can
            # exist; `profile_completed_at` stays null until the person tells us who they are,
            # and nothing should show this to a guard or match it against a government record.
            p = Person(email=email,
                       first_name=(u.first_name if u else email.split("@")[0]),
                       last_name=(u.last_name if u else None),
                       profile_completed_at=(datetime.now(timezone.utc) if u and u.first_name
                                             else None))
            db.add(p)
            db.flush()
        db.execute(
            update(User).where(User.email == email, User.person_id.is_(None)).values(person_id=p.id)
        )
        pid = str(p.id)
        db.commit()
    return pid


def has_master_face(db: Session, person_id: str) -> bool:
    with bypass_rls(db):
        row = db.execute(
            select(PersonFace.id).where(PersonFace.person_id == person_id,
                                        PersonFace.is_active.is_(True)).limit(1)
        ).first()
    return row is not None


def has_entry_credential(db: Session, membership_id: str) -> bool:
    """New verified-identity system (§11.1): an active encrypted FaceCredential for this
    membership's tenant subject (keyed on membership id). This is what the real-engine
    'Set up face entry' flow creates, so the person app reflects the real credential."""
    subj_id = db.execute(select(TenantSubject.id).where(
        TenantSubject.external_reference == membership_id)).scalars().first()
    if not subj_id:
        return False
    return db.execute(select(FaceCredential.id).where(
        FaceCredential.tenant_subject_id == subj_id,
        FaceCredential.status == "active").limit(1)).first() is not None


def profile(db: Session, person_id: str) -> dict:
    with bypass_rls(db):
        p = db.get(Person, person_id)
        if not p:
            raise ApiError(404, "PERSON_NOT_FOUND", "No such person.")
        n_biz = db.execute(
            select(User.id).where(User.person_id == person_id, User.deleted_at.is_(None))
        ).all()
    return {
        "person_id": person_id,
        "name": f"{p.first_name} {p.last_name or ''}".strip(),
        "gender": p.gender,
        "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
        # False while `first_name` is still the placeholder taken from the email address.
        # The app uses this to ask for real details before anything depends on them.
        "profile_complete": p.profile_completed_at is not None,
        "email": p.email,
        "phone": p.phone,
        "face_verified": has_master_face(db, person_id) or any(
            has_entry_credential(db, str(r[0])) for r in n_biz),
        "business_count": len(n_biz),
    }


def list_businesses(db: Session, person_id: str) -> list[dict]:
    """The person's memberships across all businesses, with sector + verification."""
    with bypass_rls(db):
        rows = db.execute(
            select(User, Tenant).join(Tenant, Tenant.id == User.tenant_id)
            .where(User.person_id == person_id, User.deleted_at.is_(None))
        ).all()
        items = []
        for u, t in rows:
            verified = has_entry_credential(db, str(u.id)) or db.execute(
                select(FaceRecord.id).where(FaceRecord.user_id == u.id,
                                            FaceRecord.is_active.is_(True)).limit(1)
            ).first() is not None
            items.append({
                "membership_id": str(u.id), "tenant_id": str(t.id),
                "business": t.name, "sector": t.vertical,
                "role": u.role, "status": u.status, "face_verified_here": verified,
            })
    return items


def join_by_code(db: Session, *, person_id: str, org_code: str, request_id: str | None) -> dict:
    with bypass_rls(db):
        t = db.execute(
            select(Tenant).where(Tenant.org_code == org_code, Tenant.status == "active")
        ).scalar_one_or_none()
        if not t:
            raise ApiError(400, "INVALID_ORG_CODE", "Unknown or inactive organisation code.")
        if db.execute(select(User.id).where(User.person_id == person_id, User.tenant_id == t.id)).first():
            raise ApiError(409, "ALREADY_MEMBER", "You already belong to this business.")
        p = db.get(Person, person_id)
        u = User(tenant_id=t.id, person_id=person_id, user_type="self_user", role="self_user",
                 first_name=p.first_name, last_name=p.last_name, email=p.email,
                 status="pending_face", enrolled_by="self")
        db.add(u)
        db.flush()
        mid = str(u.id)
        write_audit(db, action="PERSON_JOIN", actor_id=person_id, tenant_id=str(t.id),
                    target_id=mid, request_id=request_id, metadata={"org_code": org_code})
        db.commit()
    return {"membership_id": mid, "business": t.name, "sector": t.vertical, "status": "pending_face"}


def list_invites(db: Session, *, email: str | None) -> list[dict]:
    if not email:
        return []
    with bypass_rls(db):
        rows = db.execute(
            select(BusinessInvite, Tenant).join(Tenant, Tenant.id == BusinessInvite.tenant_id)
            .where(BusinessInvite.email == email, BusinessInvite.status == "pending")
        ).all()
        return [{"invite_id": str(i.id), "business": t.name, "sector": t.vertical, "role": i.role}
                for i, t in rows]


def enroll_master(db: Session, *, person_id: str, image_b64: str, acks: dict,
                  request_id: str | None) -> dict:
    """One-time master capture: quality-gate via ZepIris (person space), store the
    encrypted master image, record the template. No business gets it until allowed."""
    if not all(acks.get(k) for k in _REQUIRED_ACKS):
        raise ApiError(400, "CONSENT_INCOMPLETE", "All four acknowledgements are required.")
    person_space = f"person_{person_id}"
    master_id = f"person:{person_id}"
    try:
        get_zepiris().insert(tenant=person_space, face_id=master_id, image_b64=image_b64)
    except ZepIrisError as e:
        if e.status_code == 422:
            raise ApiError(422, "IMAGE_QUALITY_FAILED", "Image quality / liveness check failed.")
        if e.status_code == 400:
            raise ApiError(400, "BAD_IMAGE", "The image could not be read.")
        raise ApiError(502, "FACE_ENGINE_ERROR", "Face engine unavailable.")

    object_key = face_vault.save(image_b64)  # encrypted master image (Option A)
    with bypass_rls(db):
        db.execute(update(PersonFace).where(PersonFace.person_id == person_id).values(is_active=False))
        db.add(PersonFace(person_id=person_id, milvus_vector_id=master_id, object_key=object_key, is_active=True))
        write_audit(db, action="PERSON_FACE_ENROLL", actor_id=person_id,
                    request_id=request_id, metadata={"acks": True})
        db.commit()
    return {"face_verified": True}


def consent_for_business(db: Session, *, person_id: str, membership_id: str,
                         request_id: str | None) -> dict:
    """One-tap: record per-business consent + re-provision the master face into that
    business's space (no re-scan). Activates the membership."""
    with bypass_rls(db):
        u = db.get(User, membership_id)
        if not u or str(u.person_id) != person_id:
            raise ApiError(404, "MEMBERSHIP_NOT_FOUND", "Not your membership.")
        object_key = _master_object_key(db, person_id)
        if not object_key:
            raise ApiError(400, "NO_MASTER_FACE", "Capture your face once before allowing businesses.")
        image = face_vault.load(object_key)
        if not image:
            raise ApiError(500, "MASTER_FACE_MISSING", "Master template unavailable.")

        tenant_id = str(u.tenant_id)
        try:
            get_zepiris().insert(tenant=tenant_id, face_id=str(u.id), image_b64=image)  # re-provision
        except ZepIrisError as e:
            if e.code == "LEGACY_ENGINE_RETIRED":
                raise ApiError(e.status_code, e.code, e.message)
            raise ApiError(502, "FACE_ENGINE_ERROR", "Face engine unavailable.")

        ref = f"CNS-{datetime.now(timezone.utc).year}-{secrets.randbelow(100000):05d}"
        db.add(ConsentRecord(
            tenant_id=tenant_id, user_id=u.id, purpose="attendance", method="self",
            acknowledgements={k: True for k in _REQUIRED_ACKS}, active=True, consent_ref=ref,
        ))
        if not db.execute(select(FaceRecord.id).where(FaceRecord.user_id == u.id, FaceRecord.is_active.is_(True))).first():
            db.add(FaceRecord(tenant_id=tenant_id, user_id=u.id, milvus_vector_id=str(u.id),
                              is_active=True, enrolled_by="person_reuse"))
        if u.status in ("pending_face", "pending_email"):
            u.status = "active"
        write_audit(db, action="PERSON_CONSENT_BUSINESS", actor_id=person_id, tenant_id=tenant_id,
                    target_id=membership_id, request_id=request_id, metadata={"consent_ref": ref})
        db.commit()
    return {"membership_id": membership_id, "status": "active", "consent_ref": ref}


def revoke_business(db: Session, *, person_id: str, membership_id: str, request_id: str | None) -> dict:
    """Withdraw consent for one business: revoke + remove that business's face copy."""
    with bypass_rls(db):
        u = db.get(User, membership_id)
        if not u or str(u.person_id) != person_id:
            raise ApiError(404, "MEMBERSHIP_NOT_FOUND", "Not your membership.")
        db.execute(update(ConsentRecord).where(ConsentRecord.user_id == u.id, ConsentRecord.active.is_(True))
                   .values(active=False, revoked_at=datetime.now(timezone.utc)))
        try:
            get_zepiris().delete(str(u.id))
        except ZepIrisError:
            pass
        db.execute(update(FaceRecord).where(FaceRecord.user_id == u.id).values(is_active=False))
        u.status = "suspended"
        write_audit(db, action="PERSON_REVOKE_BUSINESS", actor_id=person_id, tenant_id=str(u.tenant_id),
                    target_id=membership_id, request_id=request_id)
        db.commit()
    return {"membership_id": membership_id, "status": "suspended"}


def erase_person(db: Session, *, person_id: str, request_id: str | None) -> dict:
    """Global erasure: erase every membership + the master template + redact the person."""
    with bypass_rls(db):
        rows = db.execute(select(User.id, User.tenant_id).where(User.person_id == person_id)).all()
    erased = 0
    for uid, tid in rows:
        try:
            erase_user(db, tenant_id=str(tid), user_id=str(uid))
            erased += 1
        except ApiError:
            pass
    with bypass_rls(db):
        pf = db.execute(select(PersonFace).where(PersonFace.person_id == person_id,
                                                 PersonFace.is_active.is_(True))).scalar_one_or_none()
        if pf:
            try:
                get_zepiris().delete(pf.milvus_vector_id)
            except ZepIrisError:
                pass
            if pf.object_key:
                face_vault.delete(pf.object_key)
            pf.is_active = False
        p = db.get(Person, person_id)
        if p:
            p.email = None
            p.phone = None
            p.first_name = "ERASED"
            p.last_name = None
        write_audit(db, action="PERSON_ERASURE", actor_id=person_id, request_id=request_id,
                    metadata={"memberships_erased": erased})
        db.commit()
    return {"erased": True, "memberships_erased": erased}


def _ensure_face_provisioned(db: Session, u: User, person_id: str) -> bool:
    """Make sure this business has the person's face (reuse master, no re-scan).
    Caller must already be inside a bypass_rls() scope."""
    if db.execute(select(FaceRecord.id).where(FaceRecord.user_id == u.id,
                                              FaceRecord.is_active.is_(True))).first():
        return True
    object_key = _master_object_key(db, person_id)
    if not object_key:
        return False
    image = face_vault.load(object_key)
    if not image:
        return False
    try:
        get_zepiris().insert(tenant=str(u.tenant_id), face_id=str(u.id), image_b64=image)
    except ZepIrisError as e:
        if e.code == "LEGACY_ENGINE_RETIRED":
            raise ApiError(e.status_code, e.code, e.message)
        raise ApiError(502, "FACE_ENGINE_ERROR", "Face engine unavailable.")
    db.add(FaceRecord(tenant_id=u.tenant_id, user_id=u.id, milvus_vector_id=str(u.id),
                      is_active=True, enrolled_by="person_reuse"))
    return True


def membership_detail(db: Session, *, person_id: str, membership_id: str) -> dict:
    with bypass_rls(db):
        u = db.get(User, membership_id)
        if not u or str(u.person_id) != person_id:
            raise ApiError(404, "MEMBERSHIP_NOT_FOUND", "Not your membership.")
        t = db.get(Tenant, u.tenant_id)
        badges = [b.name for b in db.execute(
            select(Badge).join(UserBadge, UserBadge.badge_id == Badge.id)
            .where(UserBadge.user_id == u.id)).scalars().all()]
        verified = has_entry_credential(db, membership_id) or db.execute(select(FaceRecord.id).where(
            FaceRecord.user_id == u.id, FaceRecord.is_active.is_(True)).limit(1)).first() is not None
        hist = db.execute(select(AttendanceLog).where(AttendanceLog.user_id == u.id)
                          .order_by(AttendanceLog.created_at.desc()).limit(50)).scalars().all()
        return {
            "membership_id": membership_id, "business": t.name, "sector": t.vertical,
            "role": u.role, "status": u.status, "face_verified_here": verified, "badges": badges,
            "history": [{"event": h.event_type, "at": h.created_at.isoformat()} for h in hist],
        }


def list_business_events(db: Session, *, person_id: str, membership_id: str) -> list[dict]:
    with bypass_rls(db):
        u = db.get(User, membership_id)
        if not u or str(u.person_id) != person_id:
            raise ApiError(404, "MEMBERSHIP_NOT_FOUND", "Not your membership.")
        evs = db.execute(select(Event).where(Event.tenant_id == u.tenant_id)
                         .order_by(Event.created_at.desc())).scalars().all()
        out = []
        for ev in evs:
            reg = db.execute(select(EventRegistration).where(
                EventRegistration.event_id == ev.id, EventRegistration.user_id == u.id)).scalar_one_or_none()
            registered = bool(reg and reg.status == "registered")
            consented = registered and db.execute(select(ConsentRecord.id).where(
                ConsentRecord.user_id == u.id, ConsentRecord.purpose == f"event:{ev.id}",
                ConsentRecord.active.is_(True)).limit(1)).first() is not None
            out.append({"event_id": str(ev.id), "name": ev.name,
                        "registered": registered, "consented": bool(consented)})
        return out


def register_event(db: Session, *, person_id: str, event_id: str, request_id: str | None) -> dict:
    with bypass_rls(db):
        ev = db.get(Event, event_id)
        if not ev:
            raise ApiError(404, "EVENT_NOT_FOUND", "Event not found.")
        u = db.execute(select(User).where(User.person_id == person_id,
                                          User.tenant_id == ev.tenant_id,
                                          User.deleted_at.is_(None))).scalar_one_or_none()
        if not u:
            raise ApiError(403, "NOT_A_MEMBER", "Join this business before registering for its events.")
        if not _ensure_face_provisioned(db, u, person_id):
            raise ApiError(400, "NO_MASTER_FACE", "Capture your face once before registering.")
        if u.status in ("pending_face", "pending_email"):
            u.status = "active"
        ref = f"CNS-EVT-{secrets.randbelow(100000):05d}"
        db.add(ConsentRecord(tenant_id=u.tenant_id, user_id=u.id, purpose=f"event:{event_id}",
                             method="self", acknowledgements={k: True for k in _REQUIRED_ACKS},
                             active=True, consent_ref=ref))
        reg = db.execute(select(EventRegistration).where(
            EventRegistration.event_id == ev.id, EventRegistration.user_id == u.id)).scalar_one_or_none()
        if reg:
            reg.status = "registered"
            reg.consent_ref = ref
        else:
            db.add(EventRegistration(tenant_id=u.tenant_id, event_id=ev.id, user_id=u.id,
                                     person_id=person_id, status="registered", consent_ref=ref))
        write_audit(db, action="PERSON_EVENT_REGISTER", actor_id=person_id, tenant_id=str(u.tenant_id),
                    target_id=str(ev.id), request_id=request_id, metadata={"consent_ref": ref})
        db.commit()
    return {"event_id": str(ev.id), "registered": True, "consent_ref": ref}


def revoke_event(db: Session, *, person_id: str, event_id: str, request_id: str | None) -> dict:
    with bypass_rls(db):
        ev = db.get(Event, event_id)
        if not ev:
            raise ApiError(404, "EVENT_NOT_FOUND", "Event not found.")
        u = db.execute(select(User).where(User.person_id == person_id,
                                          User.tenant_id == ev.tenant_id)).scalar_one_or_none()
        if not u:
            raise ApiError(404, "MEMBERSHIP_NOT_FOUND", "Not your membership.")
        reg = db.execute(select(EventRegistration).where(
            EventRegistration.event_id == ev.id, EventRegistration.user_id == u.id)).scalar_one_or_none()
        if reg:
            reg.status = "cancelled"
        db.execute(update(ConsentRecord).where(
            ConsentRecord.user_id == u.id, ConsentRecord.purpose == f"event:{event_id}",
            ConsentRecord.active.is_(True)).values(active=False, revoked_at=datetime.now(timezone.utc)))
        write_audit(db, action="PERSON_EVENT_REVOKE", actor_id=person_id, tenant_id=str(u.tenant_id),
                    target_id=str(ev.id), request_id=request_id)
        db.commit()
    return {"event_id": str(ev.id), "registered": False}


def accept_invite(db: Session, *, person_id: str, email: str | None, invite_id: str,
                  request_id: str | None) -> dict:
    with bypass_rls(db):
        inv = db.get(BusinessInvite, invite_id)
        if not inv or inv.status != "pending":
            raise ApiError(404, "INVITE_NOT_FOUND", "Invite not found or already handled.")
        if email and inv.email and inv.email != email:
            raise ApiError(403, "INVITE_MISMATCH", "This invite is for a different email.")
        if db.execute(select(User.id).where(User.person_id == person_id, User.tenant_id == inv.tenant_id)).first():
            inv.status = "accepted"
            db.commit()
            raise ApiError(409, "ALREADY_MEMBER", "You already belong to this business.")
        p = db.get(Person, person_id)
        u = User(tenant_id=inv.tenant_id, person_id=person_id, user_type="self_user",
                 role=inv.role, first_name=p.first_name, last_name=p.last_name, email=p.email,
                 status="pending_face", enrolled_by="invite")
        db.add(u)
        db.flush()
        inv.status = "accepted"
        inv.person_id = person_id
        mid = str(u.id)
        t = db.get(Tenant, inv.tenant_id)
        write_audit(db, action="PERSON_INVITE_ACCEPT", actor_id=person_id, tenant_id=str(inv.tenant_id),
                    target_id=mid, request_id=request_id)
        db.commit()
    return {"membership_id": mid, "business": t.name, "sector": t.vertical, "status": "pending_face"}


def update_profile(db: Session, *, person_id: str, first_name: str, last_name: str | None,
                   gender: str | None, date_of_birth: str | None, phone: str | None) -> dict:
    """The person tells us who they actually is — name, and optionally gender, DOB, phone.

    Until this runs, `first_name` is a placeholder taken from their email address. A guard
    reading a name off a gate screen, and any comparison against a government record, both
    depend on this being real.
    """
    with bypass_rls(db):
        p = db.get(Person, person_id)
        if not p:
            raise ApiError(404, "PERSON_NOT_FOUND", "No such person.")
        name = (first_name or "").strip()
        if len(name) < 2:
            raise ApiError(400, "NAME_REQUIRED", "Please give your full name.")
        dob = None
        if date_of_birth:
            try:
                dob = date.fromisoformat(date_of_birth)
            except ValueError:
                raise ApiError(400, "DOB_INVALID", "Date of birth should look like 1990-04-23.")
            today = date.today()
            years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if not 0 < years < 120:
                raise ApiError(400, "DOB_INVALID", "That date of birth does not look right.")
        p.first_name = name
        p.last_name = (last_name or "").strip() or None
        p.gender = (gender or "").strip() or None
        p.date_of_birth = dob
        if phone and phone.strip():
            p.phone = phone.strip()
        p.profile_completed_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            if "persons_phone_key" in str(e.orig):
                raise ApiError(409, "PHONE_ALREADY_REGISTERED",
                               "That phone number is already registered to another account.")
            if "persons_email_key" in str(e.orig):
                raise ApiError(409, "EMAIL_ALREADY_REGISTERED",
                               "That email is already registered to another account.")
            raise ApiError(409, "CONFLICT", "That could not be saved — please try again.")
    return profile(db, person_id)
