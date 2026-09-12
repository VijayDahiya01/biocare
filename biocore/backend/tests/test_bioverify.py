"""BioVerify credential adapter (§15.1): fake behaviour, response mapping, fail-closed guards.

Pure unit tests — no stack and no network (httpx is stubbed).
"""
import base64

import httpx
import pytest

from app.adapters.bioverify import BioVerifyError, get_bioverify
from app.adapters.bioverify.base import EnrolmentEvidence, band_for, classify_outcome
from app.adapters.bioverify.client import BioVerifyClient
from app.adapters.bioverify.fake import FakeBioVerify
from app.core.config import settings


def _capture(seed: bytes) -> str:
    """A plausible capture: real PNG magic and enough bytes to clear a quality gate."""
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + seed * 600).decode()


_PNG = _capture(b"A1")
_OTHER = _capture(b"B2")


class _Resp:
    """Minimal httpx.Response stand-in."""

    def __init__(self, status_code=200, body=None, text=""):
        self.status_code, self._body, self.text = status_code, body, text

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def _stub(monkeypatch, resp, captured=None):
    def _request(method, url, **kwargs):
        if captured is not None:
            captured.update({"method": method, "url": url, **kwargs})
        return resp
    monkeypatch.setattr(httpx, "request", _request)


# ---- the dev fake ------------------------------------------------------------------

def test_fake_enrol_then_verify_round_trip():
    bv = FakeBioVerify()
    cred = bv.enrol(image=_PNG, expires_in_s=3600)
    assert cred.qr_text and cred.credential_id
    assert len(cred.credential_id) == 32          # 16 bytes hex, as the real service demands
    ok = bv.verify(image=_PNG, qr_text=cred.qr_text)
    assert ok.allowed and not ok.retry and ok.band == "high"
    miss = bv.verify(image=_OTHER, qr_text=cred.qr_text)
    assert not miss.allowed and miss.reason == "FACE_MISMATCH"


def test_fake_undecodable_qr_is_retry_not_deny():
    """Matches the live service: a garbage credential came back RETRY / DECODE_FAILED."""
    r = FakeBioVerify().verify(image=_PNG, qr_text="NOT-A-REAL-CREDENTIAL")
    assert r.retry and not r.allowed and r.reason == "DECODE_FAILED"


def test_fake_revoke_denies_a_later_verify():
    bv = FakeBioVerify()
    cred = bv.enrol(image=_PNG, expires_in_s=3600)
    assert bv.verify(image=_PNG, qr_text=cred.qr_text).allowed
    bv.revoke_credential(credential_id=cred.credential_id)
    denied = bv.verify(image=_PNG, qr_text=cred.qr_text)
    assert not denied.allowed and denied.reason == "CREDENTIAL_REVOKED"
    assert bv.credential_status(credential_id=cred.credential_id)["status"] == "revoked"
    assert cred.credential_id in bv.revocations_sync()["revoked"]


def test_fake_document_enrol_reports_what_it_cannot_prove():
    cred = FakeBioVerify().enrol_with_document(live=_PNG, document=_OTHER, expires_in_s=3600)
    assert cred.document_match["document_screen_replay_pass"] is False
    assert cred.document_match["document_authenticity_pass"] is None


# ---- evidence + outcome rules ------------------------------------------------------

def test_evidence_always_emits_deepfake_pass():
    """The service requires the key present even when the check did not run, so that
    'not checked' is recorded and not merely absent."""
    body = EnrolmentEvidence(quality_pass=True, pad_pass=True).to_dict()
    assert "deepfake_pass" in body and body["deepfake_pass"] is None
    assert EnrolmentEvidence(quality_pass=True, pad_pass=True,
                             deepfake_pass=False).to_dict()["deepfake_pass"] is False


def test_issue_rejects_a_failed_capture():
    bv = FakeBioVerify()
    with pytest.raises(BioVerifyError, match="quality_pass"):
        bv.issue_credential(evidence=EnrolmentEvidence(quality_pass=False, pad_pass=True))
    with pytest.raises(BioVerifyError, match="pad_pass"):
        bv.issue_credential(evidence=EnrolmentEvidence(quality_pass=True, pad_pass=False))
    assert bv.issue_credential(
        evidence=EnrolmentEvidence(quality_pass=True, pad_pass=True))["status"] == "active"


def test_unknown_outcome_fails_closed():
    assert classify_outcome("ACCEPT") == (True, False)
    assert classify_outcome("RETRY") == (False, True)
    for unknown in ("SOMETHING_NEW", "", None):
        assert classify_outcome(unknown) == (False, False)


def test_band_never_leaks_the_score():
    assert band_for(None, 0.35) == "none"
    assert band_for(0.9, 0.35) == "high"
    assert band_for(0.4, 0.35) == "medium"
    assert band_for(0.2, 0.35) == "none"


# ---- the real client ---------------------------------------------------------------

def test_client_requires_url_and_key():
    with pytest.raises(BioVerifyError, match="BIOVERIFY_URL"):
        BioVerifyClient(url="", api_key="k")
    with pytest.raises(BioVerifyError, match="BIOVERIFY_API_KEY"):
        BioVerifyClient(url="https://example.test", api_key="")


def test_client_sends_api_key_and_data_uri_capture(monkeypatch):
    captured = {}
    _stub(monkeypatch, _Resp(200, {"qr_text": "QR", "credential_id": "ab" * 16}), captured)
    c = BioVerifyClient(url="https://example.test/", api_key="secret")
    cred = c.enrol(image=f"data:image/png;base64,{_PNG}", expires_in_s=900)
    assert cred.qr_text == "QR" and cred.credential_id == "ab" * 16
    assert captured["url"] == "https://example.test/poc/enrol"
    assert captured["headers"]["X-API-Key"] == "secret"
    assert captured["data"]["expires_in_s"] == "900"      # BioCore policy, not the 30-day default
    assert captured["files"]["image"][2] == "image/png"   # sniffed, not assumed


def test_client_rejects_an_unusable_capture(monkeypatch):
    _stub(monkeypatch, _Resp(200, {"qr_text": "QR"}))
    c = BioVerifyClient(url="https://example.test", api_key="k")
    for bad in ("", "   ", "!!!not base64!!!"):
        with pytest.raises(BioVerifyError):
            c.enrol(image=bad, expires_in_s=60)


def test_client_enrol_without_credential_text_is_an_error(monkeypatch):
    _stub(monkeypatch, _Resp(200, {"status": "ok"}))
    with pytest.raises(BioVerifyError, match="no credential text"):
        BioVerifyClient(url="https://example.test", api_key="k").enrol(image=_PNG, expires_in_s=60)


def test_client_maps_a_verify_response(monkeypatch):
    _stub(monkeypatch, _Resp(200, {"outcome": "ACCEPT", "reason": "MATCH", "similarity": 0.91,
                                   "threshold": 0.35, "policy_version": 7}))
    r = BioVerifyClient(url="https://example.test", api_key="k").verify(image=_PNG, qr_text="QR")
    assert r.allowed and r.band == "high" and r.policy_version == 7


def test_client_denies_an_outcome_it_does_not_recognise(monkeypatch):
    _stub(monkeypatch, _Resp(200, {"outcome": "WAT", "similarity": 0.99, "threshold": 0.35}))
    r = BioVerifyClient(url="https://example.test", api_key="k").verify(image=_PNG, qr_text="QR")
    assert not r.allowed and not r.retry and r.outcome == "WAT"


def test_client_surfaces_the_service_reason_on_an_error(monkeypatch):
    _stub(monkeypatch, _Resp(422, {"detail": "enrolment evidence does not show quality_pass"}))
    with pytest.raises(BioVerifyError, match="quality_pass"):
        BioVerifyClient(url="https://example.test", api_key="k").issue_credential(
            evidence=EnrolmentEvidence(quality_pass=False, pad_pass=True))


def test_client_maps_an_unreachable_service(monkeypatch):
    def _boom(method, url, **kwargs):
        raise httpx.ConnectError("no route to host")
    monkeypatch.setattr(httpx, "request", _boom)
    with pytest.raises(BioVerifyError, match="unreachable"):
        BioVerifyClient(url="https://example.test", api_key="k").health()


# ---- the factory -------------------------------------------------------------------

def test_factory_returns_the_fake_in_dev(monkeypatch):
    monkeypatch.setattr(settings, "bioverify_url", "")
    monkeypatch.setattr(settings, "fake_bioverify", True)
    get_bioverify.cache_clear()
    try:
        assert get_bioverify().name == "fake-bioverify"
    finally:
        get_bioverify.cache_clear()


def test_factory_forbids_the_fake_in_production(monkeypatch):
    monkeypatch.setattr(settings, "bioverify_url", "")
    monkeypatch.setattr(settings, "fake_bioverify", True)
    monkeypatch.setattr(settings, "environment", "production")
    get_bioverify.cache_clear()
    try:
        with pytest.raises(BioVerifyError, match="forbidden in production"):
            get_bioverify()
    finally:
        get_bioverify.cache_clear()


def test_enrol_refuses_a_capture_it_cannot_use():
    """The live service refuses a poor capture with QUALITY_INSUFFICIENT rather than minting.
    A credential from a bad capture stays valid for its whole lifetime, so this must fail."""
    bv = FakeBioVerify()
    for rubbish in ("", "Zm9vYmFy", base64.b64encode(b"not an image at all").decode()):
        with pytest.raises(BioVerifyError, match="QUALITY_INSUFFICIENT"):
            bv.enrol(image=rubbish, expires_in_s=3600)


def test_a_credential_always_gets_an_expiry():
    """`retention_service.credential_expiry` returns None for a tenant with no policy — every
    brand-new tenant. Falling through on that would mint credentials that never expire."""
    from datetime import datetime, timedelta, timezone

    from app.services.credential_issuing import expiry_or_default

    explicit = datetime.now(timezone.utc) + timedelta(days=3)
    assert expiry_or_default(explicit) == explicit          # a tenant policy still wins
    fallback = expiry_or_default(None)
    assert fallback is not None and fallback > datetime.now(timezone.utc)
