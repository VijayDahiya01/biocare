"""consent_records — DPDP consent. Mandatory before any face capture."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)  # e.g. attendance
    method: Mapped[str] = mapped_column(String, nullable=False)  # self | admin_assisted
    acknowledgements: Mapped[dict] = mapped_column(JSONB, nullable=False)  # the four required booleans
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    consent_ref: Mapped[str] = mapped_column(String, nullable=False)  # human-readable ref
    given_at: Mapped[datetime] = created_at_col()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
