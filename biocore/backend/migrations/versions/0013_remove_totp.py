"""0013 — remove two-factor authentication.

Admin login is email + password only. The `users.totp_secret` column is dropped rather than
left behind: it holds shared secrets for a feature that no longer exists, and keeping live
authentication secrets for a removed mechanism is worse than losing them.

IRREVERSIBLE in practice. The downgrade re-adds the column, but every secret is gone, so any
account that had 2FA would need to enrol a new authenticator. That is the right trade — the
alternative is retaining credentials nothing can use.
"""
from alembic import op

revision = "0013_remove_totp"
down_revision = "0012_bioverify_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS totp_secret;")


def downgrade() -> None:
    # The column comes back empty — the secrets themselves are not recoverable.
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret text;")
