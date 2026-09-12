"""0012 — §15.1 BioVerify credentials: external credential id + credential source.

Additive only. ZepIris is replaced by the external BioVerify credential API, which enrols a
face and returns a sealed, scannable credential. For those subjects BioCore stores the
credential TEXT — encrypted through the existing vault, with the same AAD binding and the same
`template_key_events` trail — instead of an embedding. That needs two columns:

  * face_credentials.external_credential_id — BioVerify's own id. `/credentials/{id}/revoke`
    and `/credentials/{id}/status` are keyed by it, so without it a BioCore revoke or erase has
    nothing to address upstream.
  * face_credentials.credential_source — 'template' (an encrypted embedding: every row that
    exists today) or 'bioverify' (an encrypted qr_text). The matcher MUST know which one it is
    holding. An embedding sent to BioVerify, or a qr_text fed to the local cosine path, is a
    silent wrong answer rather than an error, so this is a correctness column, not a label.

Every existing row defaults to 'template' and keeps behaving exactly as before. Nothing is
dropped or altered; face_credentials keeps its FORCE RLS policy from 0008.
"""
from alembic import op

revision = "0012_bioverify_credentials"
down_revision = "0011_offline_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE face_credentials
            ADD COLUMN IF NOT EXISTS external_credential_id text,
            ADD COLUMN IF NOT EXISTS credential_source text NOT NULL DEFAULT 'template';
        """
    )
    # Partial: only BioVerify-minted rows carry an id, and this is the lookup a revocation
    # reconciliation walks (spec 6.4 sync -> the local credentials it refers to).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_face_credentials_external
            ON face_credentials(external_credential_id)
            WHERE external_credential_id IS NOT NULL;
        """
    )
    # An upstream id identifies exactly one local credential; a duplicate means a mint was
    # recorded twice and a revoke would then miss one of them.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_face_credentials_external
            ON face_credentials(tenant_id, external_credential_id)
            WHERE external_credential_id IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_face_credentials_external;")
    op.execute("DROP INDEX IF EXISTS ix_face_credentials_external;")
    op.execute(
        """
        ALTER TABLE face_credentials
            DROP COLUMN IF EXISTS external_credential_id,
            DROP COLUMN IF EXISTS credential_source;
        """
    )
