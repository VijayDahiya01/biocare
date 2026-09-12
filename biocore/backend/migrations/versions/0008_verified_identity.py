"""verified-identity & entry-management model (BIOCORE_COMPLETE_CHANGE_SPEC §9)

Revision ID: 0008_verified_identity
Revises: 0007_person
Create Date: 2026-06-24

Additive & parallel to the existing person/user model — nothing is dropped or altered, so
current demo data and flows keep working. `platform_accounts` is GLOBAL (no RLS); the other
11 tables are tenant-scoped with FORCE RLS like the rest of the platform.
"""
from alembic import op

revision = "0008_verified_identity"
down_revision = "0007_person"
branch_labels = None
depends_on = None

_TENANT_TABLES = [
    "tenant_subjects",
    "identity_verification_sessions",
    "verified_claims",
    "consent_notices",
    "face_credentials",
    "consent_receipts",
    "entry_attempts",
    "template_key_events",
    "data_retention_policies",
    "erasure_jobs",
    "device_certificates",
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
    # --- global optional account (no tenant, no RLS; hashed contacts only) ---
    op.execute(
        """
        CREATE TABLE platform_accounts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email_hash text UNIQUE,
            phone_hash text UNIQUE,
            status text NOT NULL DEFAULT 'active',
            created_at timestamptz NOT NULL DEFAULT now(),
            last_login_at timestamptz
        );
        """
    )

    # --- tenant subject (a person inside one tenant) ---
    op.execute(
        """
        CREATE TABLE tenant_subjects (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            platform_account_id uuid REFERENCES platform_accounts(id),
            external_reference text,
            display_name text,
            subject_type text NOT NULL DEFAULT 'member',
            status text NOT NULL DEFAULT 'pending_verification',
            verification_status text NOT NULL DEFAULT 'unverified',
            authorization_status text NOT NULL DEFAULT 'inactive',
            valid_from timestamptz,
            valid_until timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_tenant_subjects_tenant ON tenant_subjects(tenant_id);
        CREATE INDEX ix_tenant_subjects_ref ON tenant_subjects(external_reference);
        """
    )

    op.execute(
        """
        CREATE TABLE identity_verification_sessions (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            tenant_subject_id uuid NOT NULL REFERENCES tenant_subjects(id),
            government_provider text,
            provider_reference_hash text,
            status text NOT NULL DEFAULT 'started',
            assurance_level text,
            liveness_result text,
            face_match_result text,
            failure_category text,
            model_version text,
            started_at timestamptz NOT NULL DEFAULT now(),
            completed_at timestamptz,
            expires_at timestamptz
        );
        CREATE INDEX ix_ivs_tenant ON identity_verification_sessions(tenant_id);
        CREATE INDEX ix_ivs_subject ON identity_verification_sessions(tenant_subject_id);
        """
    )

    op.execute(
        """
        CREATE TABLE verified_claims (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            tenant_subject_id uuid NOT NULL REFERENCES tenant_subjects(id),
            claim_type text NOT NULL,
            claim_value text NOT NULL,
            verified_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz,
            source text
        );
        CREATE INDEX ix_verified_claims_tenant ON verified_claims(tenant_id);
        CREATE INDEX ix_verified_claims_subject ON verified_claims(tenant_subject_id);
        """
    )

    op.execute(
        """
        CREATE TABLE consent_notices (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            purpose_id text NOT NULL,
            version text NOT NULL DEFAULT 'v1',
            language text NOT NULL DEFAULT 'en',
            notice_text_hash text,
            active_from timestamptz NOT NULL DEFAULT now(),
            active_until timestamptz
        );
        CREATE INDEX ix_consent_notices_tenant ON consent_notices(tenant_id);
        """
    )

    op.execute(
        """
        CREATE TABLE face_credentials (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            tenant_subject_id uuid NOT NULL REFERENCES tenant_subjects(id),
            purpose_id text NOT NULL DEFAULT 'entry_authentication',
            encrypted_template bytea NOT NULL,
            encrypted_dek bytea NOT NULL,
            nonce bytea NOT NULL,
            key_version text NOT NULL,
            model_version text NOT NULL,
            template_version text NOT NULL,
            status text NOT NULL DEFAULT 'active',
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz,
            revoked_at timestamptz,
            erased_at timestamptz
        );
        CREATE INDEX ix_face_credentials_tenant ON face_credentials(tenant_id);
        CREATE INDEX ix_face_credentials_subject ON face_credentials(tenant_subject_id);
        """
    )

    op.execute(
        """
        CREATE TABLE consent_receipts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            tenant_subject_id uuid NOT NULL REFERENCES tenant_subjects(id),
            notice_id uuid REFERENCES consent_notices(id),
            purpose_id text NOT NULL,
            decision text NOT NULL,
            method text,
            captured_at timestamptz NOT NULL DEFAULT now(),
            withdrawn_at timestamptz,
            device_context text
        );
        CREATE INDEX ix_consent_receipts_tenant ON consent_receipts(tenant_id);
        CREATE INDEX ix_consent_receipts_subject ON consent_receipts(tenant_subject_id);
        """
    )

    op.execute(
        """
        CREATE TABLE entry_attempts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            tenant_subject_id uuid,
            device_id uuid,
            gate_id uuid,
            zone_id uuid,
            match_result text,
            liveness_result text,
            authorization_result text,
            reason_code text,
            confidence_band text,
            model_version text,
            policy_version text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_entry_attempts_tenant ON entry_attempts(tenant_id);
        CREATE INDEX ix_entry_attempts_subject ON entry_attempts(tenant_subject_id);
        """
    )

    op.execute(
        """
        CREATE TABLE template_key_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            face_credential_id uuid NOT NULL REFERENCES face_credentials(id),
            operation text NOT NULL,
            key_version text,
            service_identity text,
            authorized_context text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_template_key_events_tenant ON template_key_events(tenant_id);
        CREATE INDEX ix_template_key_events_cred ON template_key_events(face_credential_id);
        """
    )

    op.execute(
        """
        CREATE TABLE data_retention_policies (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            data_category text NOT NULL,
            retention_period text,
            expiry_trigger text,
            legal_hold_allowed boolean NOT NULL DEFAULT true,
            deletion_method text NOT NULL DEFAULT 'hard_delete',
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_retention_tenant ON data_retention_policies(tenant_id);
        """
    )

    op.execute(
        """
        CREATE TABLE erasure_jobs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            tenant_subject_id uuid NOT NULL REFERENCES tenant_subjects(id),
            scope text NOT NULL DEFAULT 'subject',
            status text NOT NULL DEFAULT 'pending',
            started_at timestamptz,
            completed_at timestamptz,
            certificate_id text,
            failure_reason text,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_erasure_jobs_tenant ON erasure_jobs(tenant_id);
        CREATE INDEX ix_erasure_jobs_subject ON erasure_jobs(tenant_subject_id);
        """
    )

    op.execute(
        """
        CREATE TABLE device_certificates (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            device_id uuid NOT NULL REFERENCES devices(id),
            certificate_thumbprint text NOT NULL,
            issued_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz,
            revoked_at timestamptz
        );
        CREATE INDEX ix_device_certs_tenant ON device_certificates(tenant_id);
        CREATE INDEX ix_device_certs_device ON device_certificates(device_id);
        """
    )

    for table in _TENANT_TABLES:
        op.execute(_rls(table))


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
    op.execute("DROP TABLE IF EXISTS platform_accounts CASCADE;")
