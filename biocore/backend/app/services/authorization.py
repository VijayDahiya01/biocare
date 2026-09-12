"""Authorization plane (BIOCORE_COMPLETE_CHANGE_SPEC §4.5, §7.3).

A face match proves identity; THIS decides access. Even a passing match is denied unless the
credential, consent, subject and gate/zone/time/booking/blacklist conditions all hold.
Returns the first failing `EntryReason` (§15.4), or `ALLOWED`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.policy import EntryReason


def evaluate(*, face_match_passed: bool, liveness_passed: bool, subject, credential,
             consent_active: bool, tenant_active: bool = True, gate_allowed: bool = True,
             zone_allowed: bool = True, time_allowed: bool = True, booking_active: bool = True,
             blacklisted: bool = False) -> EntryReason:
    now = datetime.now(timezone.utc)
    # capture quality / liveness gate
    if not liveness_passed:
        return EntryReason.LIVENESS_FAILED
    # safety
    if blacklisted:
        return EntryReason.ACCESS_NOT_ALLOWED
    # a valid credential must exist BEFORE a match can be trusted against it — otherwise a
    # revoked/absent credential would misreport as FACE_MISMATCH.
    if credential is None or credential.status != "active":
        return EntryReason.CREDENTIAL_EXPIRED
    if credential.expires_at and credential.expires_at < now:
        return EntryReason.CREDENTIAL_EXPIRED
    # identity
    if not face_match_passed:
        return EntryReason.FACE_MISMATCH
    # consent
    if not consent_active:
        return EntryReason.CONSENT_WITHDRAWN
    # subject standing
    if subject is None or subject.status in ("suspended", "erased") \
            or subject.verification_status != "verified":
        return EntryReason.ACCESS_NOT_ALLOWED
    if subject.valid_until and subject.valid_until < now:
        return EntryReason.ACCESS_NOT_ALLOWED
    # policy (gate/zone/time/booking/tenant). NOTE: gate/zone/time/booking/blacklist are
    # authorization-plane hooks fed by the caller — wired to zones/roster/blacklist as the
    # policy engine matures. Defaults are permissive ONLY for the checks not yet sourced.
    if not (tenant_active and gate_allowed and zone_allowed and time_allowed and booking_active):
        return EntryReason.ACCESS_NOT_ALLOWED
    return EntryReason.ALLOWED
