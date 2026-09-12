"""audit_logs — immutable record of every significant action.

Append-only: never UPDATE or DELETE through the API. A DB trigger (see migration)
rejects updates/deletes as a hard safety net for the DPDP audit requirement.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)  # user/admin/device that acted
    action: Mapped[str] = mapped_column(String, nullable=False)  # FACE_SEARCH, ERASURE_COMPLETE, ...
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = created_at_col()
