"""zones, badges, access, blacklist, webhooks, alerts, visitors (Phase 2)

Revision ID: 0003_phase2
Revises: 0002_phase1
Create Date: 2026-06-15
"""
from alembic import op

revision = "0003_phase2"
down_revision = "0002_phase1"
branch_labels = None
depends_on = None

_TABLES = [
    "zones", "badges", "user_badges", "access_events",
    "blacklist", "webhook_configs", "alerts", "visitor_invites",
]


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
        CREATE TABLE zones (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            name text NOT NULL,
            type text NOT NULL,
            access_rule jsonb NOT NULL DEFAULT '{}'::jsonb,
            door_webhook_url text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_zones_tenant_id ON zones(tenant_id);

        CREATE TABLE badges (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            name text NOT NULL,
            zones jsonb NOT NULL DEFAULT '[]'::jsonb,
            time_rule text NOT NULL DEFAULT 'always',
            time_windows jsonb NOT NULL DEFAULT '[]'::jsonb,
            expiry date,
            print_badge boolean NOT NULL DEFAULT false
        );
        CREATE INDEX ix_badges_tenant_id ON badges(tenant_id);

        CREATE TABLE user_badges (
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid NOT NULL REFERENCES users(id),
            badge_id uuid NOT NULL REFERENCES badges(id),
            assigned_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, badge_id)
        );
        CREATE INDEX ix_user_badges_tenant_id ON user_badges(tenant_id);

        CREATE TABLE access_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid,
            zone_id uuid,
            device_id uuid,
            granted boolean NOT NULL,
            reason text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_access_tenant_created ON access_events(tenant_id, created_at);

        CREATE TABLE blacklist (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            milvus_vector_id text NOT NULL,
            reason text,
            added_by uuid,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_blacklist_tenant_id ON blacklist(tenant_id);

        CREATE TABLE webhook_configs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            event text NOT NULL,
            url text NOT NULL,
            secret text NOT NULL,
            active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_webhook_tenant_id ON webhook_configs(tenant_id);

        CREATE TABLE alerts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            type text NOT NULL,
            priority text NOT NULL DEFAULT 'high',
            message text NOT NULL,
            status text NOT NULL DEFAULT 'active',
            target_id text,
            device_id uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            dismissed_by text,
            dismissed_at timestamptz
        );
        CREATE INDEX ix_alerts_tenant_status ON alerts(tenant_id, status);

        CREATE TABLE visitor_invites (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            token text NOT NULL,
            visitor_name text,
            host_user_id uuid,
            expires_at timestamptz NOT NULL,
            used boolean NOT NULL DEFAULT false,
            user_id uuid,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_visitor_tenant_id ON visitor_invites(tenant_id);
        CREATE INDEX ix_visitor_token ON visitor_invites(token);
        """
    )

    for table in _TABLES:
        op.execute(_rls(table))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
