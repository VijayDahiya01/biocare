"""0010 — §12.3–4 device hardening + trusted request context.

Additive only. Adds:
  * device_request_nonces — anti-replay store for signed gate requests (§12.4), tenant-scoped
    with FORCE RLS like the rest of the platform.
  * devices.software_version / devices.hardening / devices.posture_attested_at — the terminal
    hardening posture a device attests to (§12.3).

Nothing is dropped or altered; existing device/entry flows keep working.
"""
from alembic import op

revision = "0010_device_trust_context"
down_revision = "0009_role_separation"
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
        CREATE TABLE device_request_nonces (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            device_id uuid NOT NULL REFERENCES devices(id),
            nonce text NOT NULL,
            seen_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz
        );
        CREATE INDEX ix_device_nonces_tenant ON device_request_nonces(tenant_id);
        CREATE INDEX ix_device_nonces_expires ON device_request_nonces(expires_at);
        -- a nonce is unique per device: a repeat is a replay
        CREATE UNIQUE INDEX uq_device_nonce ON device_request_nonces(device_id, nonce);
        """
    )
    op.execute(_rls("device_request_nonces"))

    # --- device hardening posture (§12.3) ---
    op.execute(
        """
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS software_version text;
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS hardening jsonb NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS posture_attested_at timestamptz;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS device_request_nonces CASCADE;")
    op.execute(
        """
        ALTER TABLE devices DROP COLUMN IF EXISTS software_version;
        ALTER TABLE devices DROP COLUMN IF EXISTS hardening;
        ALTER TABLE devices DROP COLUMN IF EXISTS posture_attested_at;
        """
    )
