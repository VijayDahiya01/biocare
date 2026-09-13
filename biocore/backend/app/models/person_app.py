"""Person-centric app: global identity + face template, business invites,
per-event registrations. See docs/PERSON_APP.md.

`persons` and `person_faces` are GLOBAL (no tenant_id, no RLS) — access is gated
to the authenticated person in the app layer. `business_invites` and
`event_registrations` are tenant-scoped (FORCE RLS like the rest).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class Person(Base):
    """One human, spanning businesses. Global — not tenant-scoped."""
    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    gender: Mapped[str | None] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Set when the person confirms their own details. Until then `first_name` may be a
    # placeholder derived from their email address, which is not a name and must not be
    # shown to a guard or compared against a government record.
    profile_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                                  nullable=True)
    created_at: Mapped[datetime] = created_at_col()


class PersonFace(Base):
    """The person's one-time master face template. Global.

    object_key points at the encrypted master image (India-region, person-controlled,
    deletable) retained solely to provision the face into businesses/events the
    person explicitly allows — see docs/PERSON_APP.md §4."""
    __tablename__ = "person_faces"

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    milvus_vector_id: Mapped[str] = mapped_column(String, nullable=False)  # master template id
    object_key: Mapped[str | None] = mapped_column(String, nullable=True)  # encrypted master image
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    enrolled_at: Mapped[datetime] = created_at_col()


class BusinessInvite(Base):
    """A business inviting a person to join (appears in the person's app)."""
    __tablename__ = "business_invites"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, server_default=text("'self_user'"))
    status: Mapped[str] = mapped_column(String, server_default=text("'pending'"))  # pending|accepted|revoked
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = created_at_col()


class EventRegistration(Base):
    """A person registering for a business's event, with per-event consent."""
    __tablename__ = "event_registrations"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String, server_default=text("'registered'"))  # registered|cancelled
    consent_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
