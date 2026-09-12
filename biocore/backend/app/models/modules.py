"""Phase 3 module tables: wages, memberships, guardians, timetables, donations,
geofences, leave, events, integrations. Each is tenant-scoped (FORCE RLS)."""
import uuid
from datetime import date, datetime, time

from sqlalchemy import Date, Integer, Numeric, String, Time, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class WageConfig(Base):
    __tablename__ = "wage_config"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    rate_per_hour: Mapped[float] = mapped_column(Numeric, nullable=False)
    overtime_multiplier: Mapped[float] = mapped_column(Numeric, server_default=text("1.5"))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    plan_type: Mapped[str] = mapped_column(String, nullable=False)  # monthly|quarterly|annual
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paid: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    payment_ref: Mapped[str | None] = mapped_column(String, nullable=True)


class GuardianLink(Base):
    __tablename__ = "guardian_links"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    guardian_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    student_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    relationship: Mapped[str] = mapped_column(String, server_default=text("'parent'"))


class Timetable(Base):
    __tablename__ = "timetables"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    teacher_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon..6=Sun
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class Donation(Base):
    __tablename__ = "donations"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    donor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    purpose: Mapped[str | None] = mapped_column(String, nullable=True)
    payment_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    receipt_url: Mapped[str | None] = mapped_column(String, nullable=True)  # 80G PDF
    created_at: Mapped[datetime] = created_at_col()


class Geofence(Base):
    __tablename__ = "geofences"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    center_lat: Mapped[float] = mapped_column(Numeric, nullable=False)
    center_lng: Mapped[float] = mapped_column(Numeric, nullable=False)
    radius_km: Mapped[float] = mapped_column(Numeric, nullable=False)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # casual|sick|earned|unpaid
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, server_default=text("'pending'"))  # pending|approved|rejected
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = created_at_col()


class Event(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # sap|zoho|darwinbox|keka
    config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String, server_default=text("'configured'"))
    created_at: Mapped[datetime] = created_at_col()
