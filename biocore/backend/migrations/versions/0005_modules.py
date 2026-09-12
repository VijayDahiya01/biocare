"""module tables (Phase 3)

Revision ID: 0005_modules
Revises: 0004_settings
Create Date: 2026-06-15
"""
from alembic import op

revision = "0005_modules"
down_revision = "0004_settings"
branch_labels = None
depends_on = None

_TABLES = [
    "wage_config", "memberships", "guardian_links", "timetables",
    "donations", "geofences", "leave_requests", "events", "integrations",
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
        CREATE TABLE wage_config (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid NOT NULL REFERENCES users(id),
            rate_per_hour numeric NOT NULL,
            overtime_multiplier numeric NOT NULL DEFAULT 1.5,
            effective_from date NOT NULL
        );
        CREATE INDEX ix_wage_tenant ON wage_config(tenant_id);
        CREATE INDEX ix_wage_user ON wage_config(user_id);

        CREATE TABLE memberships (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid NOT NULL REFERENCES users(id),
            plan_type text NOT NULL,
            start_date date NOT NULL,
            end_date date NOT NULL,
            amount_paid numeric,
            payment_ref text
        );
        CREATE INDEX ix_membership_tenant ON memberships(tenant_id);
        CREATE INDEX ix_membership_user ON memberships(user_id);

        CREATE TABLE guardian_links (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            guardian_user_id uuid NOT NULL REFERENCES users(id),
            student_user_id uuid NOT NULL REFERENCES users(id),
            relationship text NOT NULL DEFAULT 'parent'
        );
        CREATE INDEX ix_guardian_tenant ON guardian_links(tenant_id);
        CREATE INDEX ix_guardian_student ON guardian_links(student_user_id);

        CREATE TABLE timetables (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            class_id text NOT NULL,
            subject text,
            teacher_user_id uuid,
            day_of_week int NOT NULL,
            start_time time NOT NULL,
            end_time time NOT NULL
        );
        CREATE INDEX ix_timetable_tenant ON timetables(tenant_id);

        CREATE TABLE donations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            donor_user_id uuid NOT NULL REFERENCES users(id),
            amount numeric NOT NULL,
            purpose text,
            payment_ref text,
            receipt_url text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_donation_tenant ON donations(tenant_id);
        CREATE INDEX ix_donation_donor ON donations(donor_user_id);

        CREATE TABLE geofences (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            name text NOT NULL,
            center_lat numeric NOT NULL,
            center_lng numeric NOT NULL,
            radius_km numeric NOT NULL
        );
        CREATE INDEX ix_geofence_tenant ON geofences(tenant_id);

        CREATE TABLE leave_requests (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid NOT NULL REFERENCES users(id),
            type text NOT NULL,
            from_date date NOT NULL,
            to_date date NOT NULL,
            reason text,
            status text NOT NULL DEFAULT 'pending',
            note text,
            decided_by text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_leave_tenant ON leave_requests(tenant_id);
        CREATE INDEX ix_leave_user ON leave_requests(user_id);

        CREATE TABLE events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            name text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_event_tenant ON events(tenant_id);

        CREATE TABLE integrations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            kind text NOT NULL,
            config jsonb NOT NULL DEFAULT '{}'::jsonb,
            status text NOT NULL DEFAULT 'configured',
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_integration_tenant ON integrations(tenant_id);
        """
    )
    for table in _TABLES:
        op.execute(_rls(table))


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
