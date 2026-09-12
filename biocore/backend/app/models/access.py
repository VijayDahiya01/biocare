"""Zones, badges, access events, blacklist, webhooks, alerts, visitor invites."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # entry_exit | restricted | amenity
    access_rule: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # allowed_badges[], time_windows[]
    door_webhook_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = created_at_col()


class Badge(Base):
    __tablename__ = "badges"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    zones: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))  # zone ids
    time_rule: Mapped[str] = mapped_column(String, server_default=text("'always'"))  # always | window
    time_windows: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))  # [{from,to,days?}]
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    print_badge: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class UserBadge(Base):
    __tablename__ = "user_badges"
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    badge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    assigned_at: Mapped[datetime] = created_at_col()


class AccessEvent(Base):
    __tablename__ = "access_events"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # null = unknown face
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)  # badge_ok|no_badge|outside_hours|unknown
    created_at: Mapped[datetime] = created_at_col()


class BlacklistEntry(Base):
    __tablename__ = "blacklist"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    milvus_vector_id: Mapped[str] = mapped_column(String, nullable=False)  # id in the blacklist collection
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()


class WebhookConfig(Base):
    __tablename__ = "webhook_configs"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    event: Mapped[str] = mapped_column(String, nullable=False)  # access.granted, etc.
    url: Mapped[str] = mapped_column(String, nullable=False)
    secret: Mapped[str] = mapped_column(String, nullable=False)  # HMAC secret
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = created_at_col()


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # blacklist_hit|unrecognised|access_denied|device_offline
    priority: Mapped[str] = mapped_column(String, server_default=text("'high'"))  # critical|high|medium
    message: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, server_default=text("'active'"))  # active|dismissed
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    dismissed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VisitorInvite(Base):
    __tablename__ = "visitor_invites"
    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    token: Mapped[str] = mapped_column(String, nullable=False)  # hashed invite token
    visitor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    host_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # created visitor user
    created_at: Mapped[datetime] = created_at_col()
