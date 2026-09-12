"""person-centric app: persons, membership link, invites, event registrations

Revision ID: 0007_person
Revises: 0006_grievances
Create Date: 2026-06-19

persons + person_faces are GLOBAL (no tenant_id, no RLS) — gated to the
authenticated person in the app. business_invites + event_registrations are
tenant-scoped (FORCE RLS). Additive + backwards compatible.
"""
from alembic import op

revision = "0007_person"
down_revision = "0006_grievances"
branch_labels = None
depends_on = None

_TENANT_TABLES = ["business_invites", "event_registrations"]


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
    # --- global identity (no tenant, no RLS) ---
    op.execute(
        """
        CREATE TABLE persons (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email text UNIQUE,
            phone text UNIQUE,
            first_name text NOT NULL,
            last_name text,
            created_at timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE person_faces (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            person_id uuid NOT NULL REFERENCES persons(id),
            milvus_vector_id text NOT NULL,
            object_key text,
            is_active boolean NOT NULL DEFAULT true,
            enrolled_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_person_faces_person ON person_faces(person_id);
        """
    )

    # --- link memberships to a person ---
    op.execute("ALTER TABLE users ADD COLUMN person_id uuid REFERENCES persons(id);")
    op.execute("CREATE INDEX ix_users_person_id ON users(person_id);")

    # --- tenant-scoped invites + event registrations ---
    op.execute(
        """
        CREATE TABLE business_invites (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            email text,
            phone text,
            role text NOT NULL DEFAULT 'self_user',
            status text NOT NULL DEFAULT 'pending',
            person_id uuid,
            created_by text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_business_invites_tenant ON business_invites(tenant_id);
        CREATE INDEX ix_business_invites_email ON business_invites(email);

        CREATE TABLE event_registrations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            event_id uuid NOT NULL REFERENCES events(id),
            user_id uuid NOT NULL REFERENCES users(id),
            person_id uuid,
            status text NOT NULL DEFAULT 'registered',
            consent_ref text,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (event_id, user_id)
        );
        CREATE INDEX ix_event_reg_tenant ON event_registrations(tenant_id);
        CREATE INDEX ix_event_reg_event ON event_registrations(event_id);
        """
    )
    for table in _TENANT_TABLES:
        op.execute(_rls(table))


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    op.execute("DROP INDEX IF EXISTS ix_users_person_id;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS person_id;")
    op.execute("DROP TABLE IF EXISTS person_faces CASCADE;")
    op.execute("DROP TABLE IF EXISTS persons CASCADE;")
