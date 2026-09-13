"""Face enrollment — wraps the ZepIris adapter and enforces the consent gate.

Data minimisation: the platform keeps only the vector reference. The raw image
is never persisted by the platform (ZepIris discards it after embedding), so
face_records.minio_object_key stays null.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.zepiris import ZepIrisError, get_zepiris
from app.core.envelope import ApiError
from app.models import FaceRecord, User
from app.services.consent_service import has_active_consent


def enroll_face(db: Session, *, tenant_id: str, user_id: str, image_b64: str,
                enrolled_by: str) -> dict:
    # 1. consent gate — no face capture without consent on file (non-negotiable).
    if not has_active_consent(db, user_id=user_id):
        raise ApiError(403, "CONSENT_REQUIRED", "No active consent on file for this user.")

    user = db.get(User, user_id)
    if not user:
        raise ApiError(404, "USER_NOT_FOUND", "User does not exist in this tenant.")

    face_id = str(user_id)  # stable ZepIris id per user

    # 2. enroll into ZepIris (insert; if the id already exists, re-enroll via upsert).
    try:
        z = get_zepiris()
        result = z.insert(tenant=tenant_id, face_id=face_id, image_b64=image_b64)
    except ZepIrisError as e:
        if e.code == "LEGACY_ENGINE_RETIRED":
            # get_zepiris() itself raises this when the engine isn't deployed at all —
            # pass it straight through instead of the per-call mapping below.
            raise ApiError(e.status_code, e.code, e.message)
        if e.status_code == 409:
            result = z.upsert(tenant=tenant_id, face_id=face_id, image_b64=image_b64)
        elif e.status_code == 422:
            raise ApiError(422, "IMAGE_QUALITY_FAILED",
                           "Image quality or liveness check failed.")
        elif e.status_code == 400:
            raise ApiError(400, "BAD_IMAGE", "The submitted image could not be read.")
        else:
            raise ApiError(502, "FACE_ENGINE_ERROR", "Face engine unavailable.")

    # 3. record the reference (idempotent per user) + activate the account.
    record = db.execute(
        select(FaceRecord).where(FaceRecord.user_id == user_id, FaceRecord.is_active.is_(True))
    ).scalar_one_or_none()
    if record is None:
        record = FaceRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            milvus_vector_id=face_id,
            minio_object_key=None,  # raw image not retained
            is_active=True,
            enrolled_by=enrolled_by,
        )
        db.add(record)

    if user.status in ("pending_face", "pending_email"):
        user.status = "active"
    db.commit()

    return {
        "face_id": face_id,
        "vector_stored": result.stored,
        "quality": {
            "blur": "pass" if result.quality.blur_ok else "fail",
            "liveness": "pass" if not result.quality.spoof else "fail",
            "face_detected": result.quality.passed,
        },
    }
