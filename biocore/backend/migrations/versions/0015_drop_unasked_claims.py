"""0015 — remove government claims that were never asked for.

The government fetch used to run at every verification level, so organisations that asked for
nothing but a selfie still had claims recorded against their people:

    identity_verified = true
    document_valid    = true
    age_over_18       = true

Nobody checked any of it. "age_over_18: true" for a person no one age-checked is a false record,
and it is the kind a school or a licensed venue would rely on.

This deletes claims that came from a stand-in provider for tenants that never asked for a
government check. It does NOT touch claims from a real provider, and it does not touch the audit
log — the events stay, only the untrue assertions go.

Not reversible, and should not be: restoring a false claim about a person has no value.
"""
from alembic import op

revision = "0015_drop_unasked_claims"
down_revision = "0014_person_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # verified_claims is tenant-scoped with FORCE row-level security, and a migration runs as
    # the application role — so without this the DELETE simply matches nothing and reports
    # success. (Migration 0009 needed the same for the same reason.)
    op.execute("SET LOCAL app.bypass_rls = 'on';")
    op.execute(
        """
        DELETE FROM verified_claims vc
        USING tenant_subjects ts, tenants t
        WHERE vc.tenant_subject_id = ts.id
          AND ts.tenant_id = t.id
          AND COALESCE(t.verification_level, 'face_only') <> 'face_and_government'
          AND vc.source IN ('fake_gov', 'fake');
        """
    )


def downgrade() -> None:
    # Deliberately empty. These rows asserted things nobody verified; putting them back would
    # reintroduce the defect this migration exists to clear.
    pass
