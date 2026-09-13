"""The real Sandbox adapter, against realistic Aadhaar OKYC payloads.

The Sandbox TEST environment replays examples configured in their dashboard and answers 404
"Request does not match any saved example" to everything else, so no live call can exercise
this parsing. These tests run the real parser over the shapes the provider documents, so the
integration is covered by something other than hope while that account is unconfigured.

Pure unit tests — no network.
"""
import base64

import pytest

from app.adapters.gov_identity.sandbox import SandboxGovernmentProvider


@pytest.fixture
def provider(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "sandbox_api_key", "key_test_x")
    monkeypatch.setattr(settings, "sandbox_api_secret", "secret_test_x")
    return SandboxGovernmentProvider()


def _aadhaar(name="Asha Kumari Rao", dob="1994-07-12"):
    return {"_type": "aadhaar", "name": name, "date_of_birth": dob, "gender": "F",
            "transaction_id": "txn-abc-123",
            "photo": base64.b64encode(b"\xff\xd8\xff-a-real-jpeg").decode()}


def test_name_on_the_record_is_compared_with_the_one_we_hold(provider):
    ok = provider.extract_allowed_claims(raw=_aadhaar(), context={"expected_name": "Asha Rao"})
    assert ok.name_verified is True

    other = provider.extract_allowed_claims(raw=_aadhaar(), context={"expected_name": "Bob Smith"})
    assert other.name_verified is False
    assert "does not match" in other.extra["name_match_reason"]


def test_no_name_on_file_cannot_pass(provider):
    """It once returned bool(name) — true whenever the record had a name, which confirmed
    nothing about who was registering."""
    c = provider.extract_allowed_claims(raw=_aadhaar(), context={"expected_name": ""})
    assert c.name_verified is False


def test_age_comes_from_the_record_not_from_us(provider):
    adult = provider.extract_allowed_claims(raw=_aadhaar(dob="1994-07-12"),
                                            context={"expected_name": "Asha Rao"})
    child = provider.extract_allowed_claims(raw=_aadhaar(dob="2015-01-01"),
                                            context={"expected_name": "Asha Rao"})
    assert adult.age_over_18 is True and child.age_over_18 is False


def test_the_photo_is_extracted_for_face_matching(provider):
    """Aadhaar returns a face. Without it there is nothing to match the live capture against,
    and the government check degrades to a name comparison alone."""
    assert provider.extract_temporary_photo(raw=_aadhaar())


def test_the_government_name_is_never_retained(provider):
    """Only the verdict is kept, never the name itself (§5.5)."""
    c = provider.extract_allowed_claims(raw=_aadhaar(name="Asha Kumari Rao"),
                                        context={"expected_name": "Asha Rao"})
    assert "Kumari" not in str(c.extra) and "Kumari" not in c.verification_reference_hash
