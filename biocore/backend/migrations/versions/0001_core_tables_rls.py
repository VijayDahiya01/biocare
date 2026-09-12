"""core tables + RLS + append-only audit + role presets

Revision ID: 0001_core
Revises:
Create Date: 2026-06-15

Phase 0 foundation. Creates tenants, roles, users, consent_records, audit_logs.
Enforces tenant isolation with FORCE ROW LEVEL SECURITY as a safety net beyond
the app layer. A controlled `app.bypass_rls` GUC lets the narrow set of legitimate
cross-tenant operations (login lookup, tenant provisioning, super-admin) opt out
explicitly — see app/core/db.py:tenant_scope / bypass_rls.
"""
from alembic import op

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


TENANT_TABLES = ["users", "consent_records"]  # plain tenant_id isolation


def _policy(table: str, tenant_col: str = "tenant_id", allow_null: bool = False) -> str:
    null_clause = f" OR {tenant_col} IS NULL" if allow_null else ""
    return f"""
    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
    ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
    CREATE POLICY {table}_isolation ON {table}
      USING (
        current_setting('app.bypass_rls', true) = 'on'
        {null_clause}
        OR {tenant_col}::text = current_setting('app.tenant_id', true)
      )
      WITH CHECK (
        current_setting('app.bypass_rls', true) = 'on'
        OR {tenant_col}::text = current_setting('app.tenant_id', true)
      );
    """


def upgrade() -> None:
    # Migrations need to write global presets etc.; bypass RLS for this txn only.
    op.execute("SET LOCAL app.bypass_rls = 'on';")

    op.execute(
        """
        CREATE TABLE tenants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name text NOT NULL,
            org_code text UNIQUE NOT NULL,
            vertical text NOT NULL,
            plan text NOT NULL DEFAULT 'starter',
            status text NOT NULL DEFAULT 'active',
            branding jsonb NOT NULL DEFAULT '{}'::jsonb,
            dpdp_config jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE roles (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid REFERENCES tenants(id),
            key text NOT NULL,
            name text NOT NULL,
            is_preset boolean NOT NULL DEFAULT false,
            permissions jsonb NOT NULL DEFAULT '[]'::jsonb,
            scope jsonb NOT NULL DEFAULT '{}'::jsonb
        );
        CREATE INDEX ix_roles_tenant_id ON roles(tenant_id);
        """
    )

    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_type text NOT NULL,
            role text,
            first_name text NOT NULL,
            last_name text,
            email text,
            member_id text,
            department text,
            status text NOT NULL DEFAULT 'pending_email',
            enrolled_by text,
            expiry_date date,
            extra jsonb NOT NULL DEFAULT '{}'::jsonb,
            password_hash text,
            totp_secret text,
            created_at timestamptz NOT NULL DEFAULT now(),
            deleted_at timestamptz,
            CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email)
        );
        CREATE INDEX ix_users_tenant_id ON users(tenant_id);
        """
    )

    op.execute(
        """
        CREATE TABLE consent_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid NOT NULL REFERENCES users(id),
            purpose text NOT NULL,
            method text NOT NULL,
            acknowledgements jsonb NOT NULL,
            active boolean NOT NULL DEFAULT true,
            consent_ref text NOT NULL,
            given_at timestamptz NOT NULL DEFAULT now(),
            revoked_at timestamptz
        );
        CREATE INDEX ix_consent_tenant_id ON consent_records(tenant_id);
        CREATE INDEX ix_consent_user_id ON consent_records(user_id);
        """
    )

    op.execute(
        """
        CREATE TABLE audit_logs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid REFERENCES tenants(id),
            actor_id text,
            action text NOT NULL,
            target_id text,
            request_id text,
            ip_address text,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_audit_tenant_id ON audit_logs(tenant_id);
        CREATE INDEX ix_audit_created_at ON audit_logs(created_at);
        """
    )

    # --- RLS isolation (safety net) ---
    # tenants: a tenant sees only its own row (keyed on id, not tenant_id).
    op.execute(
        """
        ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
        ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenants_isolation ON tenants
          USING (current_setting('app.bypass_rls', true) = 'on'
                 OR id::text = current_setting('app.tenant_id', true))
          WITH CHECK (current_setting('app.bypass_rls', true) = 'on'
                 OR id::text = current_setting('app.tenant_id', true));
        """
    )
    for table in TENANT_TABLES:
        op.execute(_policy(table))
    # roles: global presets (tenant_id NULL) are readable by everyone.
    op.execute(_policy("roles", allow_null=True))
    # audit: tenant-scoped; platform (null-tenant) rows only visible under bypass.
    op.execute(_policy("audit_logs"))

    # --- append-only audit: reject UPDATE/DELETE at the DB level ---
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_logs_append_only()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only (% blocked)', TG_OP;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_audit_append_only
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only();
        """
    )

    # --- seed the 12 global role presets ---
    presets = [
        ("super_admin", "Super Admin", ["*"]),
        ("entity_admin", "Entity Admin", ["users.*", "zones.*", "badges.*", "devices.*",
                                          "attendance.*", "reports.*", "settings.*", "roles.*",
                                          "alerts.*", "admin.enroll", "dpdp.*"]),
        ("manager", "Manager / Supervisor", ["users.view", "attendance.view", "attendance.edit",
                                             "reports.view", "alerts.view"]),
        ("contractor_sub_admin", "Contractor Sub-admin", ["users.view", "users.create",
                                                          "attendance.view", "wage.view", "reports.view"]),
        ("hr_payroll", "HR / Payroll", ["attendance.view", "wage.*", "payroll.*", "reports.view", "leave.*"]),
        ("auditor_dpo", "Auditor / DPO", ["audit.view", "consent.view", "reports.view", "dpdp.view"]),
        ("security_reception", "Security / Reception", ["kiosk.operate", "visitors.*",
                                                        "alerts.view", "alerts.dismiss", "blacklist.view"]),
        ("self_user", "Self-registered User", ["me.*"]),
        ("admin_enrolled", "Admin-enrolled Person", ["me.view"]),
        ("guardian", "Guardian", ["me.view", "pickup.verify"]),
        ("visitor", "Visitor", []),
        ("kiosk_device", "Kiosk Device", ["faces.search"]),
    ]
    for key, name, perms in presets:
        perms_json = "[" + ",".join(f'"{p}"' for p in perms) + "]"
        op.execute(
            f"""
            INSERT INTO roles (tenant_id, key, name, is_preset, permissions)
            VALUES (NULL, '{key}', '{name}', true, '{perms_json}'::jsonb);
            """
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_append_only ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_append_only();")
    for table in ["audit_logs", "consent_records", "users", "roles", "tenants"]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
