"""Admin-assisted enrollment (API Reference §3.5, Screen A7).

Used when a person cannot self-register (patient, inmate, citizen, devotee,
visitor, guardian). The admin captures the face and records consent on their
behalf, with the admin's identity and the four confirmations logged.
"""
import secrets
from datetime import date

from sqlalchemy.orm import Session

from app.core.envelope import ApiError
from app.models import ConsentRecord, User
from app.services.face_service import enroll_face


def _consent_ref() -> str:
    return f"CNS-ADM-{secrets.randbelow(100000):05d}"


def admin_enroll(db: Session, *, tenant_id: str, admin_user_id: str, person_type: str,
                 first_name: str, last_name: str | None, reference_id: str | None,
                 purpose: str, image: str, consent_method: str,
                 expiry_date: str | None, extra: dict,
                 confirmations: dict) -> dict:
    # All four admin confirmations are mandatory (A7).
    required = ("person_present", "purpose_explained", "person_consented", "admin_responsible")
    if not all(confirmations.get(k) for k in required):
        raise ApiError(400, "CONFIRMATIONS_REQUIRED",
                       "All four admin confirmations are required.",
                       details={"missing": [k for k in required if not confirmations.get(k)]})

    user = User(
        tenant_id=tenant_id,
        user_type="admin_enrolled" if person_type != "visitor" else "visitor",
        role=person_type if person_type in ("guardian", "visitor") else "admin_enrolled",
        first_name=first_name,
        last_name=last_name,
        member_id=reference_id,
        status="active",
        enrolled_by=admin_user_id,
        expiry_date=date.fromisoformat(expiry_date) if expiry_date else None,
        extra={**extra, "person_type": person_type, "purpose": purpose},
    )
    db.add(user)
    db.flush()
    user_id = str(user.id)

    # Consent recorded on the person's behalf, fully traceable to the admin.
    ref = _consent_ref()
    db.add(ConsentRecord(
        tenant_id=tenant_id, user_id=user_id, purpose=purpose,
        method="admin_assisted",
        acknowledgements={"purpose_understood": True, "sensitivity_understood": True,
                          "rights_understood": True, "freely_given": True,
                          "consent_method": consent_method, "recorded_by": admin_user_id},
        active=True, consent_ref=ref,
    ))
    db.commit()

    # Capture the face (consent is now on file, so the gate passes).
    enroll_face(db, tenant_id=tenant_id, user_id=user_id, image_b64=image,
                enrolled_by=admin_user_id)

    return {"user_id": user_id, "consent_ref": ref}
