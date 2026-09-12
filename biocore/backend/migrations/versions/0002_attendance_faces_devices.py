"""attendance, faces, devices (Phase 1)

Revision ID: 0002_phase1
Revises: 0001_core
Create Date: 2026-06-15

Adds the core operational tables for the attendance MVP, each with the same
FORCE ROW LEVEL SECURITY tenant-isolation policy as the core tables.
"""
from alembic import op

revision = "0002_phase1"
down_revision = "0001_core"
branch_labels = None
depends_on = None


def _rls(table: str) -> str:
    return f"""
    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
    CREATE POLICY {table}_isolation ON {table}
      USING (current_setting('app.bypass_rls', true) = 'on'
             OR tenant_id::text = current_setting('app.tenant_id', true))
      WITH CHECK (current_setting('app.bypass_rls', true) = 'on'
             OR tenant_id::text = current_setting('app.tenant_id', true));
    """


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE devices (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            name text NOT NULL,
            zone_id uuid,
            capture_method text NOT NULL DEFAULT 'webcam',
            device_token text NOT NULL,
            status text NOT NULL DEFAULT 'offline',
            last_seen timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_devices_tenant_id ON devices(tenant_id);
        CREATE INDEX ix_devices_token ON devices(device_token);
        """
    )

    op.execute(
        """
        CREATE TABLE face_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid NOT NULL REFERENCES users(id),
            milvus_vector_id text NOT NULL,
            minio_object_key text,
            is_active boolean NOT NULL DEFAULT true,
            enrolled_at timestamptz NOT NULL DEFAULT now(),
            enrolled_by text
        );
        CREATE INDEX ix_face_tenant_id ON face_records(tenant_id);
        CREATE INDEX ix_face_user_id ON face_records(user_id);
        """
    )

    op.execute(
        """
        CREATE TABLE attendance_logs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid NOT NULL REFERENCES users(id),
            event_type text NOT NULL,
            match_score double precision,
            device_id uuid,
            zone_id uuid,
            session_id uuid,
            latitude double precision,
            longitude double precision,
            request_id text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        -- per-user history
        CREATE INDEX ix_att_tenant_user_created ON attendance_logs(tenant_id, user_id, created_at);
        -- dashboard date filters
        CREATE INDEX ix_att_tenant_created ON attendance_logs(tenant_id, created_at);
        """
    )

    op.execute(
        """
        CREATE TABLE current_presence (
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid NOT NULL REFERENCES users(id),
            entered_at timestamptz NOT NULL,
            zone_id uuid,
            device_id uuid,
            PRIMARY KEY (tenant_id, user_id)
        );
        CREATE INDEX ix_presence_tenant ON current_presence(tenant_id);
        """
    )

    for table in ["devices", "face_records", "attendance_logs", "current_presence"]:
        op.execute(_rls(table))


def downgrade() -> None:
    for table in ["current_presence", "attendance_logs", "face_records", "devices"]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
