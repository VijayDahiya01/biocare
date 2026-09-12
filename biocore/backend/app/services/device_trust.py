"""Device certificate trust (BIOCORE_COMPLETE_CHANGE_SPEC §10.5, §12.2).

Every production terminal is paired, certified and revocable. Certificates are issued as a
one-time secret whose HASH (thumbprint) is stored — mirroring the hashed device-token design
(§12.1). This is the software baseline; production may layer mTLS/attestation (§12.4).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.envelope import ApiError
from app.core.security import hash_token, new_token
from app.models import Device, DeviceCertificate

# The hardening flags a compliant terminal must attest to (§12.3). OS/disk/port controls are
# provisioned on the device; the terminal reports its posture and the platform records/enforces.
POSTURE_BASELINE = ("kiosk_mode", "disk_encryption", "screen_lock", "os_auto_update",
                    "ports_restricted", "downloads_disabled", "local_export_disabled")


def issue_certificate(db: Session, *, tenant_id, device_id, expires_at=None) -> tuple[str, DeviceCertificate]:
    raw = new_token("cert_")
    cert = DeviceCertificate(
        tenant_id=tenant_id, device_id=device_id,
        certificate_thumbprint=hash_token(raw), expires_at=expires_at,
    )
    db.add(cert)
    db.flush()
    return raw, cert  # raw shown ONCE; only the thumbprint is stored


def attest(db: Session, *, device_id, raw_certificate: str) -> bool:
    thumb = hash_token(raw_certificate)
    cert = db.execute(
        select(DeviceCertificate).where(
            DeviceCertificate.device_id == device_id,
            DeviceCertificate.certificate_thumbprint == thumb,
            DeviceCertificate.revoked_at.is_(None),
        )
    ).scalars().first()
    if cert is None:
        return False
    if cert.expires_at and cert.expires_at < datetime.now(timezone.utc):
        return False
    return True


def rotate(db: Session, *, tenant_id, device_id) -> tuple[str, DeviceCertificate]:
    revoke(db, device_id=device_id)
    return issue_certificate(db, tenant_id=tenant_id, device_id=device_id)


def revoke(db: Session, *, device_id) -> int:
    n = 0
    for c in db.execute(
        select(DeviceCertificate).where(
            DeviceCertificate.device_id == device_id,
            DeviceCertificate.revoked_at.is_(None),
        )
    ).scalars().all():
        c.revoked_at = datetime.now(timezone.utc)
        n += 1
    return n


# --- §12.3 terminal hardening posture ---------------------------------------
def record_posture(db: Session, *, device_id, posture: dict, software_version: str | None = None) -> Device:
    """A terminal attests its hardening posture (kiosk mode, disk encryption, screen lock, …)."""
    d = db.get(Device, device_id)
    if d is None:
        raise ApiError(404, "DEVICE_NOT_FOUND", "Device does not exist.")
    d.hardening = {k: bool(posture.get(k, False)) for k in POSTURE_BASELINE}
    if software_version:
        d.software_version = software_version
    d.posture_attested_at = datetime.now(timezone.utc)
    return d


def posture_ok(device: Device | None) -> bool:
    """True only if the device attested every baseline hardening control."""
    if device is None:
        return False
    h = device.hardening or {}
    return all(h.get(k) for k in POSTURE_BASELINE)
