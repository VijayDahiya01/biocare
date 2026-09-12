"""Human roles, service identities, and separation of duties (BIOCORE_COMPLETE_CHANGE_SPEC §20).

Endpoint groups bake in §20.3 separation of duties:
  * Enrollment operator does identity proofing + mints credentials — but not privacy ops,
    device management, or gate overrides.
  * Privacy administrator manages consent, erasure and retention — but not gate overrides
    or device pairing.
  * Security administrator manages devices/certificates — but never KMS keys (service-only).
  * Auditor gets read-only status/metadata; Support has no decrypt/export.
The tenant owner (entity_admin / super_admin) is always allowed.
"""

# --- human roles (§20.2) ---
SUPER_ADMIN = "super_admin"
ENTITY_ADMIN = "entity_admin"           # tenant owner
MANAGER = "manager"
PRIVACY_ADMIN = "privacy_admin"
SECURITY_ADMIN = "security_admin"
ENROLLMENT_OPERATOR = "enrollment_operator"
GUARD = "security_reception"
SUPERVISOR = "supervisor"
AUDITOR = "auditor"
SUPPORT = "support"
HR_PAYROLL = "hr_payroll"

_OWNER = (SUPER_ADMIN, ENTITY_ADMIN)    # tenant owner — always allowed

# --- endpoint role groups (§20.3) ---
ENROLL = _OWNER + (MANAGER, ENROLLMENT_OPERATOR)             # identity proofing + credential mint
PRIVACY = _OWNER + (PRIVACY_ADMIN,)                          # consent · erasure · retention
SECURITY = _OWNER + (SECURITY_ADMIN, MANAGER)                # device pairing / certificates
READ_STATUS = _OWNER + (AUDITOR, PRIVACY_ADMIN, SECURITY_ADMIN, MANAGER, ENROLLMENT_OPERATOR)  # status-only views


# --- service identities (§20.1) — service-plane, not human. Only these may decrypt (§6.6). ---
class Service:
    IDENTITY_PROOFING = "identity_proofing_service"
    ENTRY_MATCHING = "entry_matching_service"
    AUTHORIZATION = "authorization_service"
    ERASURE = "erasure_service"
    KEY_ROTATION = "key_rotation_service"
    DEVICE_ATTESTATION = "device_attestation_service"
