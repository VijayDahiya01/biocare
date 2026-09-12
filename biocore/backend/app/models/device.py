"""devices — registered kiosk terminals (a non-human identity)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)  # e.g. KIOSK-GATE-01
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    capture_method: Mapped[str] = mapped_column(String, server_default=text("'webcam'"))  # webcam | rtsp
    device_token: Mapped[str] = mapped_column(String, nullable=False)  # hashed pairing/device token
    status: Mapped[str] = mapped_column(String, server_default=text("'offline'"))  # online|offline|disabled
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Terminal hardening posture attested by the device (§12.3): kiosk_mode, disk_encryption,
    # screen_lock, os_auto_update, ports_restricted, downloads_disabled, local_export_disabled.
    software_version: Mapped[str | None] = mapped_column(String, nullable=True)
    hardening: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    posture_attested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
