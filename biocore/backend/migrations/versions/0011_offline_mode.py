"""0011 — §16 offline mode: encrypted roster accountability + offline entry marker.

Additive only. Adds:
  * offline_rosters — metadata for each encrypted, device-bound roster issued to a terminal
    (§16 Option B). The payload itself is never stored; only accountability metadata is.
  * entry_attempts.captured_offline — marks a gate decision made offline and later synced.

Tenant-scoped with FORCE RLS; nothing is dropped or altered.
"""
from alembic import op

revision = "0011_offline_mode"
down_revision = "0010_device_trust_context"
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
        CREATE TABLE offline_rosters (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            device_id uuid NOT NULL REFERENCES devices(id),
            zone_id uuid,
            subject_count integer NOT NULL DEFAULT 0,
            key_version text NOT NULL DEFAULT 'roster-v1',
            status text NOT NULL DEFAULT 'active',
            issued_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz,
            wiped_at timestamptz
        );
        CREATE INDEX ix_offline_rosters_tenant ON offline_rosters(tenant_id);
        CREATE INDEX ix_offline_rosters_device ON offline_rosters(device_id);
        """
    )
    op.execute(_rls("offline_rosters"))

    op.execute(
        "ALTER TABLE entry_attempts ADD COLUMN IF NOT EXISTS captured_offline boolean NOT NULL DEFAULT false;"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS offline_rosters CASCADE;")
    op.execute("ALTER TABLE entry_attempts DROP COLUMN IF EXISTS captured_offline;")
