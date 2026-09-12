"""grievances (DPDP grievance redressal)

Revision ID: 0006_grievances
Revises: 0005_modules
Create Date: 2026-06-16
"""
from alembic import op

revision = "0006_grievances"
down_revision = "0005_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE grievances (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid NOT NULL REFERENCES users(id),
            subject text,
            message text NOT NULL,
            status text NOT NULL DEFAULT 'open',
            resolution text,
            resolved_by text,
            resolved_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_grievance_tenant ON grievances(tenant_id);
        CREATE INDEX ix_grievance_user ON grievances(user_id);

        ALTER TABLE grievances ENABLE ROW LEVEL SECURITY;
        ALTER TABLE grievances FORCE ROW LEVEL SECURITY;
        CREATE POLICY grievances_isolation ON grievances
          USING (current_setting('app.bypass_rls', true) = 'on'
                 OR tenant_id::text = current_setting('app.tenant_id', true))
          WITH CHECK (current_setting('app.bypass_rls', true) = 'on'
                 OR tenant_id::text = current_setting('app.tenant_id', true));
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS grievances CASCADE;")
