"""users — every human identity (admins, staff, members, admin-enrolled, guardians, visitors)."""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class User(Base):
    __tablename__ = "users"
    # email is unique PER tenant (nullable for admin-enrolled people).
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=False
    )
    # links this membership to a global person identity (person-centric app).
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    user_type: Mapped[str] = mapped_column(String, nullable=False)  # self_user, admin_enrolled, guardian, visitor, ...
    role: Mapped[str | None] = mapped_column(String, nullable=True)  # roles.key
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    member_id: Mapped[str | None] = mapped_column(String, nullable=True)  # client's own id, EMP-4821
    department: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, server_default=text("'pending_email'")
    )  # pending_email|pending_face|active|suspended
    enrolled_by: Mapped[str | None] = mapped_column(String, nullable=True)  # self | <admin user_id>
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    # Admin/staff credentials (members use email+OTP, so these stay null for them).
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = created_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # soft delete for non-biometric data
