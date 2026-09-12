"""Device (kiosk) registration + token authentication.

Each terminal is registered once and issued a device token (stored hashed). The
kiosk presents that token (X-Device-Token header / device cookie) on every
/faces/search call so the platform knows which device recorded which event —
part of the DPDP audit trail.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.envelope import ApiError
from app.core.security import hash_token, new_token
from app.models import Device


def register_device(db: Session, *, tenant_id: str, name: str,
                    zone_id: str | None, capture_method: str) -> dict:
    raw_token = new_token("dev_")
    device = Device(
        tenant_id=tenant_id,
        name=name,
        zone_id=zone_id,
        capture_method=capture_method,
        device_token=hash_token(raw_token),
        status="offline",
    )
    db.add(device)
    db.commit()
    kiosk_url = f"/kiosk?token={raw_token}"
    return {
        "device_id": str(device.id),
        "pairing_token": raw_token,  # shown ONCE; stored only as a hash
        "kiosk_url": kiosk_url,
    }


def disable_device(db: Session, *, device_id: str) -> None:
    device = db.get(Device, device_id)
    if not device:
        raise ApiError(404, "DEVICE_NOT_FOUND", "Device does not exist.")
    device.status = "disabled"
    db.commit()


def authenticate_device(db: Session, raw_token: str) -> dict:
    """Resolve a device from its token. Used under bypass at the gateway layer
    (the device's tenant is not yet known). Returns tenant/zone for scoping."""
    token_hash = hash_token(raw_token)
    device = db.execute(
        select(Device).where(Device.device_token == token_hash)
    ).scalar_one_or_none()
    if not device:
        raise ApiError(401, "DEVICE_UNKNOWN", "Unrecognised device token.")
    if device.status == "disabled":
        raise ApiError(403, "DEVICE_DISABLED", "This device has been disabled.")

    device.status = "online"
    device.last_seen = datetime.now(timezone.utc)
    db.commit()
    return {
        "device_id": str(device.id),
        "tenant_id": str(device.tenant_id),
        "zone_id": str(device.zone_id) if device.zone_id else None,
    }
