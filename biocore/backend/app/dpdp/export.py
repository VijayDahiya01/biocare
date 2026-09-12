"""DPDP right to access — export everything the platform holds on a user, in a
machine-readable form."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AttendanceLog,
    Badge,
    ConsentRecord,
    FaceRecord,
    User,
    UserBadge,
)


def export_user(db: Session, *, user_id: str) -> dict:
    user = db.get(User, user_id)
    if not user:
        return {}

    consents = db.execute(
        select(ConsentRecord).where(ConsentRecord.user_id == user_id)
    ).scalars().all()
    faces = db.execute(
        select(FaceRecord).where(FaceRecord.user_id == user_id)
    ).scalars().all()
    attendance = db.execute(
        select(AttendanceLog).where(AttendanceLog.user_id == user_id)
        .order_by(AttendanceLog.created_at.desc()).limit(5000)
    ).scalars().all()
    badges = db.execute(
        select(Badge).join(UserBadge, UserBadge.badge_id == Badge.id)
        .where(UserBadge.user_id == user_id)
    ).scalars().all()

    return {
        "profile": {
            "user_id": str(user.id), "name": f"{user.first_name} {user.last_name or ''}".strip(),
            "email": user.email, "member_id": user.member_id, "department": user.department,
            "user_type": user.user_type, "status": user.status,
            "created_at": user.created_at.isoformat(),
        },
        "consents": [
            {"consent_ref": c.consent_ref, "purpose": c.purpose, "method": c.method,
             "active": c.active, "given_at": c.given_at.isoformat(),
             "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None}
            for c in consents
        ],
        # biometric note: only references are stored, never the raw image or vector.
        "biometric": [
            {"face_id": f.milvus_vector_id, "active": f.is_active,
             "enrolled_at": f.enrolled_at.isoformat(), "raw_image_retained": f.minio_object_key is not None}
            for f in faces
        ],
        "badges": [{"badge_id": str(b.id), "name": b.name} for b in badges],
        "attendance": [
            {"event": a.event_type, "timestamp": a.created_at.isoformat(),
             "device_id": str(a.device_id) if a.device_id else None}
            for a in attendance
        ],
    }
