"""Unit tests for verified-identity crypto, the authorization plane, and retention parsing.

No DB required (§22.1). Covers: envelope round-trip, AAD context-binding rejection, the
production guard on SoftwareKms, the authorization decision order, and period parsing.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.crypto import KmsError, decrypt_template, encrypt_template, get_kms
from app.core.policy import EntryReason
from app.services import authorization, retention_service


def test_envelope_roundtrip():
    vec = b"\x01\x02\x03" * 40
    enc = encrypt_template(vec, tenant_id="t1", subject_id="s1", purpose_id="entry_authentication",
                           model_version="m1", template_version="v1")
    assert enc.ciphertext != vec
    assert decrypt_template(enc, tenant_id="t1", subject_id="s1", purpose_id="entry_authentication") == vec


@pytest.mark.parametrize("bad", [
    {"tenant_id": "t2", "subject_id": "s1", "purpose_id": "entry_authentication"},
    {"tenant_id": "t1", "subject_id": "sX", "purpose_id": "entry_authentication"},
    {"tenant_id": "t1", "subject_id": "s1", "purpose_id": "marketing"},
])
def test_envelope_aad_rejects_cross_context(bad):
    enc = encrypt_template(b"v" * 32, tenant_id="t1", subject_id="s1", purpose_id="entry_authentication",
                           model_version="m1", template_version="v1")
    with pytest.raises(KmsError):
        decrypt_template(enc, **bad)


def test_software_kms_forbidden_in_production(monkeypatch):
    get_kms.cache_clear()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "kms_provider", "software")
    with pytest.raises(KmsError):
        get_kms()
    get_kms.cache_clear()  # restore dev provider for other tests


class _Subj:
    def __init__(self, status="verified", verification_status="verified", valid_until=None):
        self.status, self.verification_status, self.valid_until = status, verification_status, valid_until


class _Cred:
    def __init__(self, status="active", expires_at=None):
        self.status, self.expires_at = status, expires_at


def _ev(**kw):
    base = dict(face_match_passed=True, liveness_passed=True, subject=_Subj(), credential=_Cred(), consent_active=True)
    base.update(kw)
    return authorization.evaluate(**base)


def test_authorization_allow():
    assert _ev() == EntryReason.ALLOWED


def test_authorization_liveness_checked_first():
    assert _ev(liveness_passed=False, face_match_passed=False) == EntryReason.LIVENESS_FAILED


def test_authorization_no_credential_before_face():
    # a revoked/absent credential must not misreport as FACE_MISMATCH
    assert _ev(credential=None, face_match_passed=False) == EntryReason.CREDENTIAL_EXPIRED


def test_authorization_face_mismatch():
    assert _ev(face_match_passed=False) == EntryReason.FACE_MISMATCH


def test_authorization_consent_withdrawn():
    assert _ev(consent_active=False) == EntryReason.CONSENT_WITHDRAWN


def test_authorization_unverified_subject():
    assert _ev(subject=_Subj(verification_status="unverified")) == EntryReason.ACCESS_NOT_ALLOWED


def test_authorization_expired_credential():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert _ev(credential=_Cred(expires_at=past)) == EntryReason.CREDENTIAL_EXPIRED


def test_retention_parse_period():
    assert retention_service.parse_period("30d") == timedelta(days=30)
    assert retention_service.parse_period("1y") == timedelta(days=365)
    assert retention_service.parse_period("8h") == timedelta(hours=8)
    assert retention_service.parse_period("2w") == timedelta(weeks=2)
    assert retention_service.parse_period("") is None
    assert retention_service.parse_period(None) is None
