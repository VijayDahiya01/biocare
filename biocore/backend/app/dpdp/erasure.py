"""The erasure cascade — DPDP right to erasure (System doc §8.1).

One request performs a verified, atomic deletion across every store:
  * Milvus vector + MinIO image  -> the legacy engine DELETE (it owns both). Only subjects
    enrolled through the OLD face path have anything there; the verified-identity path stores
    no image and no vector, so on a deployment without those services erasure still completes
    and self-verifies. If a subject DOES have legacy data and the engine is unreachable, this
    refuses rather than certify an erasure it cannot confirm.
  * Postgres biometric refs       -> face_records hard-deleted; user PII redacted
  * Redis sessions                -> flushed
Each deletion is independently VERIFIED before the erasure is marked complete,
then an erasure certificate reference is issued.

What is NOT deleted (and why):
  * attendance_logs are retained (labour law, up to 3 years) but de-linked from
    any biometric data — the user row remains only as an opaque, redacted anchor.
  * the audit log of the erasure itself is retained (proving erasure happened is
    itself a compliance requirement).
"""
import secrets
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.envelope import ApiError
from app.core.sessions import flush_user_sessions
from app.models import ConsentRecord, FaceRecord, User, UserBadge


def _erasure_ref() -> str:
    year = datetime.now(timezone.utc).year
    return f"ERA-{year}-{secrets.randbelow(100000):05d}"


def erase_user(db: Session, *, tenant_id: str, user_id: str) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise ApiError(404, "USER_NOT_FOUND", "User does not exist in this tenant.")

    face_ids = [
        fr.milvus_vector_id
        for fr in db.execute(
            select(FaceRecord).where(FaceRecord.user_id == user_id)
        ).scalars().all()
    ]

    stores_cleared: list[str] = []
    legacy_verified: bool | None = None

    # 1. Milvus + MinIO, via the legacy engine that owns both.
    #
    # Only subjects enrolled through the OLD face path have rows here. The verified-identity
    # path stores no image and no vector, so for anything enrolled through it there is nothing
    # in either store and the engine is never contacted — which is why erasure works on a
    # deployment that runs neither. Imported lazily for exactly that reason.
    if face_ids:
        from app.adapters.zepiris import ZepIrisError, get_zepiris
        z = get_zepiris()
        for fid in face_ids:
            try:
                z.delete(fid)
            except ZepIrisError:
                pass  # verification below is the source of truth
        try:
            legacy_verified = all(z.get(fid) is None for fid in face_ids)
        except ZepIrisError as e:
            # This subject HAS legacy biometric data and we cannot confirm it is gone. Saying
            # "erased" here would put a false claim on a compliance certificate.
            raise ApiError(503, "ERASURE_UNVERIFIABLE",
                           "This person has face data in the legacy store and that service "
                           "cannot be reached, so erasure cannot be confirmed. Retry once it "
                           "is available.", details={"store": "milvus/minio"}) from e
        stores_cleared += ["milvus", "minio"]

    # 2. Postgres: drop biometric refs + badges, redact PII, revoke consent.
    db.execute(delete(FaceRecord).where(FaceRecord.user_id == user_id))
    db.execute(delete(UserBadge).where(UserBadge.user_id == user_id))
    db.execute(
        update(ConsentRecord).where(ConsentRecord.user_id == user_id)
        .values(active=False, revoked_at=datetime.now(timezone.utc))
    )
    user.email = None
    user.first_name = "ERASED"
    user.last_name = None
    user.member_id = None
    user.department = None
    user.password_hash = None
    user.totp_secret = None
    user.extra = {}
    user.status = "erased"
    user.deleted_at = datetime.now(timezone.utc)
    stores_cleared.append("postgres")
    db.commit()

    # 3. Redis sessions.
    flush_user_sessions(user_id)
    stores_cleared.append("redis")

    # --- VERIFY each store independently ---
    verified = {
        "postgres": db.execute(
            select(FaceRecord.id).where(FaceRecord.user_id == user_id).limit(1)
        ).first() is None,
        "redis": flush_user_sessions(user_id) == 0,
    }
    # Report the legacy stores only when this subject actually had data in them. Claiming
    # "verified" for a store that was never used reads as a stronger assurance than it is.
    if legacy_verified is not None:
        verified["milvus"] = legacy_verified
        verified["minio"] = legacy_verified   # the engine deletes both together

    if not all(verified.values()):
        raise ApiError(500, "ERASURE_INCOMPLETE",
                       "Erasure could not be verified across all stores.",
                       details=verified)

    ref = _erasure_ref()
    cleared = sorted(set(stores_cleared))

    # generate + store the erasure certificate (capability-token URL; the erased
    # user has no session, so the link itself is the access grant).
    from app.services import documents, pdf_service
    pdf = pdf_service.erasure_certificate(
        erasure_ref=ref, stores=cleared, when=datetime.now(timezone.utc)
    )
    certificate_url = documents.save("certificates", pdf)

    return {
        "erasure_ref": ref,
        "stores_cleared": cleared,
        "verified": verified,
        "certificate_url": certificate_url,
    }
