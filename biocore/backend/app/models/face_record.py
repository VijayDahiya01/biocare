"""face_records — link a user to their Milvus vector + (transient) MinIO image.

The Postgres row holds only REFERENCES, never the biometric itself. The raw image
is not retained by the platform (data minimisation): only the vector persists.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class FaceRecord(Base):
    __tablename__ = "face_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    milvus_vector_id: Mapped[str] = mapped_column(String, nullable=False)  # == ZepIris face id
    minio_object_key: Mapped[str | None] = mapped_column(String, nullable=True)  # null once raw deleted
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    enrolled_at: Mapped[datetime] = created_at_col()
    enrolled_by: Mapped[str | None] = mapped_column(String, nullable=True)  # self | admin user_id
