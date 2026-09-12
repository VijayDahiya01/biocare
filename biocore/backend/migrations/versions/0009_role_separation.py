"""0009 — §20 role separation: add granular human-role presets.

Additive only. Introduces the BIOCORE_COMPLETE_CHANGE_SPEC §20.2 human roles as global
presets (tenant_id NULL) so separation of duties (§20.3) is assignable, not merely enforced
at the endpoint layer. The tenant owner (super_admin/entity_admin), manager, security_reception
(Guard) and hr_payroll already exist from 0001; this splits the conflated `auditor_dpo` into a
read-only `auditor` and a consent/erasure-owning `privacy_admin`, and adds `security_admin`,
`enrollment_operator`, `supervisor` and a restricted `support` operator.

Upgrade is idempotent (INSERT ... WHERE NOT EXISTS) so re-running is safe.
"""
from alembic import op

revision = "0009_role_separation"
down_revision = "0008_verified_identity"
branch_labels = None
depends_on = None

# key, display name, permission globs (informational — endpoint gating is by role key, §20.3)
_PRESETS = [
    ("privacy_admin", "Privacy Administrator",
     ["consent.*", "erasure.*", "retention.*", "dpdp.*", "reports.view"]),
    ("security_admin", "Security Administrator",
     ["devices.*", "certificates.*", "zones.view", "alerts.view"]),  # no KMS keys (§20.3)
    ("enrollment_operator", "Enrollment Operator",
     ["identity.enroll", "faces.enroll", "attendance.view"]),        # cannot export (§20.3)
    ("supervisor", "Supervisor",
     ["entry.override", "attendance.view", "attendance.edit", "alerts.view"]),
    ("auditor", "Auditor",
     ["audit.view", "consent.view", "reports.view", "dpdp.view"]),   # read-only metadata (§20.3)
    ("support", "Support Operator",
     ["support.view"]),                                              # no decrypt/export (§20.3)
]


def upgrade() -> None:
    # Global presets have tenant_id NULL; the roles WITH CHECK policy requires bypass for that.
    op.execute("SET LOCAL app.bypass_rls = 'on';")
    for key, name, perms in _PRESETS:
        perms_json = "[" + ",".join(f'"{p}"' for p in perms) + "]"
        op.execute(
            f"""
            INSERT INTO roles (tenant_id, key, name, is_preset, permissions)
            SELECT NULL, '{key}', '{name}', true, '{perms_json}'::jsonb
            WHERE NOT EXISTS (
                SELECT 1 FROM roles WHERE tenant_id IS NULL AND key = '{key}'
            );
            """
        )


def downgrade() -> None:
    keys = ",".join(f"'{k}'" for k, _, _ in _PRESETS)
    op.execute(f"DELETE FROM roles WHERE tenant_id IS NULL AND key IN ({keys});")
