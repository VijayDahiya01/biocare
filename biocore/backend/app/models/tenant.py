"""tenants — one row per client organisation. The root of all isolation."""
import uuid
from datetime import datetime

from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    org_code: Mapped[str] = mapped_column(String, unique=True, nullable=False)  # e.g. ACME-2026
    vertical: Mapped[str] = mapped_column(String, nullable=False)  # school | hotel | factory | ...
    plan: Mapped[str] = mapped_column(String, server_default=text("'starter'"))  # starter|business|enterprise
    status: Mapped[str] = mapped_column(String, server_default=text("'active'"))  # active|suspended
    branding: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    dpdp_config: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # match_threshold, modules_enabled, alert routing, etc.
    settings: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = created_at_col()
