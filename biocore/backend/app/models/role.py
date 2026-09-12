"""roles — 12 presets (tenant_id NULL = global preset) plus custom roles."""
import uuid

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = uuid_pk()
    # NULL tenant_id => global preset shared by all tenants.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True, nullable=True
    )
    key: Mapped[str] = mapped_column(String, nullable=False)  # entity_admin, manager, custom_*
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_preset: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    permissions: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    scope: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
