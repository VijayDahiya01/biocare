"""tenant settings jsonb

Revision ID: 0004_settings
Revises: 0003_phase2
Create Date: 2026-06-15
"""
from alembic import op

revision = "0004_settings"
down_revision = "0003_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tenants ADD COLUMN settings jsonb NOT NULL DEFAULT '{}'::jsonb;")


def downgrade() -> None:
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS settings;")
