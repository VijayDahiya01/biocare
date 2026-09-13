"""0014 — who the person actually is, and how much proof their organisation wants.

Two gaps this closes.

**Nobody was ever asked their name.** `resolve_or_create_person` filled `first_name` with the
part of the email before the "@", so a guard at a gate saw "asha_8f8906" rather than a person.
Gender and date of birth had nowhere to live at all. Both are needed for their own sake, and
`date_of_birth` + `full_name` are what a government KYC response can actually be checked
against — a name match is impossible while the only name on file is invented from an address.

**Every organisation got the same onboarding.** `tenants.verification_level` lets one require a
selfie only, another a selfie plus an identity document, and another a government check. It
defaults to `face_only`, which is what every existing tenant is doing today.

Additive: no column is dropped and nothing is rewritten.
"""
from alembic import op

revision = "0014_person_details"
down_revision = "0013_remove_totp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE persons
            ADD COLUMN IF NOT EXISTS gender text,
            ADD COLUMN IF NOT EXISTS date_of_birth date,
            -- Set once the person has confirmed their own details, so the app can tell a real
            -- name from one that was derived from an email address before this migration.
            ADD COLUMN IF NOT EXISTS profile_completed_at timestamptz;
        """
    )
    op.execute(
        """
        ALTER TABLE tenants
            ADD COLUMN IF NOT EXISTS verification_level text NOT NULL DEFAULT 'face_only';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE persons
            DROP COLUMN IF EXISTS gender,
            DROP COLUMN IF EXISTS date_of_birth,
            DROP COLUMN IF EXISTS profile_completed_at;
        """
    )
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS verification_level;")
