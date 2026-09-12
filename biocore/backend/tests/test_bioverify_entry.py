"""BioVerify wired into the entry flow (§15.1): mint → 1:1 gate → 1:N walk-up → revoke → erase.

Integration test — skips if Postgres is unreachable. Runs against the in-process fake service,
so it proves the WIRING (what is stored, what is asked, what is decided), not the biometrics.
"""
import base64
import uuid

import pytest

from app.adapters.bioverify import get_bioverify
from app.api.v1 import face_credentials
from app.core.config import settings
from app.core.db import SessionLocal, set_tenant_guc
from app.core.policy import ConsentPurpose, VerificationOutcome
from app.models import TenantSubject
from app.services import credential_vault, entry_service, identity_proofing
from app.services.auth_service import provision_tenant

CONSENTS = [p.value for p in ConsentPurpose if p.value not in ("cross_tenant_reuse", "marketing")]
def _capture(tag: bytes) -> str:
    """A plausible capture — the fake service runs a quality gate, as the real one does."""
    return "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff" + tag * 600).decode()


FACE_A, FACE_B, INTRUDER = _capture(b"A1"), _capture(b"B2"), _capture(b"C3")


@pytest.fixture
def tenant(require_stack):
    db = SessionLocal()
    t = provision_tenant(db, name="BV", org_code=f"BV-{uuid.uuid4().hex[:8]}", vertical="office",
                         plan="starter", admin_email=f"bv_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="BV Admin")
    db.close()
    return t["tenant_id"]


@pytest.fixture
def service(monkeypatch):
    """Route every credential through the fake BioVerify, and hand the test the same instance
    the app will use (the factory is lru_cached, so its revocation state is shared)."""
    monkeypatch.setattr(settings, "credential_engine", "bioverify")
    monkeypatch.setattr(settings, "fake_bioverify", True)
    monkeypatch.setattr(settings, "bioverify_url", "")
    get_bioverify.cache_clear()
    yield get_bioverify()
    get_bioverify.cache_clear()


def _verified_subject(db, tid, ref):
    subj = TenantSubject(tenant_id=tid, external_reference=ref, subject_type="member")
    db.add(subj)
    db.flush()
    s = identity_proofing.start_session(db, tenant_id=tid, tenant_subject_id=subj.id,
                                        provider_label="fake")
    for p in CONSENTS:
        identity_proofing.record_consent(db, tenant_id=tid, tenant_subject_id=subj.id, purpose=p)
    identity_proofing.run_government_fetch(db, session=s, subject_ref=ref,
                                           credential={"reference": ref})
    identity_proofing.complete_verification(db, session=s, outcome=VerificationOutcome.VERIFIED)
    db.flush()
    return subj


def _mint(db, tid, subj, image):
    cred, png = face_credentials._mint(
        db, tenant_id=tid, subject_id=subj.id, image=image,
        purpose=ConsentPurpose.ENTRY_AUTHENTICATION.value, expires=None)
    db.flush()
    return cred, png


def test_mint_stores_the_credential_text_and_never_an_embedding(tenant, service):
    db = SessionLocal()
    set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, f"bv-{uuid.uuid4().hex[:6]}")
        cred, png = _mint(db, tenant, subj, FACE_A)

        assert cred.credential_source == "bioverify"
        assert cred.external_credential_id            # revoke/status upstream need this
        assert png                                    # the scannable credential for the subject

        # What is at rest is the sealed qr_text, encrypted by the SAME vault as a template.
        stored = credential_vault.credential_text(db, credential=cred)
        assert stored and stored.startswith("BVFAKE.")
        assert cred.encrypted_template and stored.encode() != cred.encrypted_template
        db.commit()
    finally:
        db.close()


def test_gate_allows_the_same_face_and_denies_another(tenant, service):
    db = SessionLocal()
    set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, f"bv-{uuid.uuid4().hex[:6]}")
        _mint(db, tenant, subj, FACE_A)

        ok = entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None,
                                     subject_id=subj.id, image=FACE_A)
        assert (ok["decision"], ok["reason"]) == ("allow", "ALLOWED")
        assert ok["confidence_band"] == "high"

        bad = entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None,
                                      subject_id=subj.id, image=INTRUDER)
        assert (bad["decision"], bad["reason"]) == ("deny", "FACE_MISMATCH")
        db.commit()
    finally:
        db.close()


def test_revoke_closes_the_gate_locally_and_upstream(tenant, service):
    db = SessionLocal()
    set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, f"bv-{uuid.uuid4().hex[:6]}")
        cred, _ = _mint(db, tenant, subj, FACE_A)
        external = cred.external_credential_id

        credential_vault.revoke_credential(db, credential=cred)
        face_credentials._revoke_upstream(cred)
        db.flush()

        # Local: the gate never even reaches the service, and says why truthfully.
        r = entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None,
                                    subject_id=subj.id, image=FACE_A)
        assert (r["decision"], r["reason"]) == ("deny", "CREDENTIAL_EXPIRED")
        # Upstream: the credential is dead there too, so a gate that bypassed BioCore is shut.
        assert service.credential_status(credential_id=external)["status"] == "revoked"
        assert external in service.revocations_sync()["revoked"]
        db.commit()
    finally:
        db.close()


def test_walk_up_identifies_the_right_subject_among_several(tenant, service):
    db = SessionLocal()
    set_tenant_guc(db, tenant)
    try:
        a = _verified_subject(db, tenant, f"bv-a-{uuid.uuid4().hex[:6]}")
        b = _verified_subject(db, tenant, f"bv-b-{uuid.uuid4().hex[:6]}")
        _mint(db, tenant, a, FACE_A)
        _mint(db, tenant, b, FACE_B)

        hit = entry_service.identify_face(db, tenant_id=tenant, device_id=None, zone_id=None,
                                          image=FACE_B)
        assert hit["matched"] and hit["subject_id"] == str(b.id)
        assert (hit["decision"], hit["reason"]) == ("allow", "ALLOWED")

        miss = entry_service.identify_face(db, tenant_id=tenant, device_id=None, zone_id=None,
                                           image=INTRUDER)
        assert not miss["matched"] and miss["decision"] == "deny"
        db.commit()
    finally:
        db.close()


def test_walk_up_respects_the_candidate_cap(tenant, service, monkeypatch):
    """The cap is what keeps an O(N)-network walk-up bounded; if it stops applying, a large
    tenant quietly becomes a per-scan storm of verify calls."""
    db = SessionLocal()
    set_tenant_guc(db, tenant)
    try:
        for i in range(3):
            _mint(db, tenant, _verified_subject(db, tenant, f"bv-c{i}-{uuid.uuid4().hex[:6]}"),
                  _capture(f"S{i}".encode()))
        calls = {"n": 0}
        real = service.verify

        def counted(*, image, qr_text):
            calls["n"] += 1
            return real(image=image, qr_text=qr_text)

        monkeypatch.setattr(service, "verify", counted)
        monkeypatch.setattr(settings, "bioverify_identify_max_candidates", 2)
        entry_service.identify_face(db, tenant_id=tenant, device_id=None, zone_id=None,
                                    image=_capture(b"ZZ"))
        assert calls["n"] <= 2
        db.commit()
    finally:
        db.close()


def test_erase_zeroizes_the_credential_text(tenant, service):
    db = SessionLocal()
    set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, f"bv-{uuid.uuid4().hex[:6]}")
        cred, _ = _mint(db, tenant, subj, FACE_A)
        credential_vault.erase_credential(db, credential=cred)
        db.flush()
        assert cred.encrypted_template == b"" and cred.status == "erased"
        assert credential_vault.credential_text(db, credential=cred) is None
        db.commit()
    finally:
        db.close()


def test_re_enrolling_supersedes_the_old_credential(tenant, service):
    """A person holds ONE active entry credential. Stacking them left the gate choosing
    arbitrarily between a current and a stale one."""
    db = SessionLocal()
    set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, f"bv-{uuid.uuid4().hex[:6]}")
        first, _ = _mint(db, tenant, subj, FACE_A)
        second, _ = _mint(db, tenant, subj, FACE_B)
        db.flush()

        assert first.status == "revoked" and second.status == "active"
        assert entry_service.active_credential(db, subj.id).id == second.id
        db.commit()
    finally:
        db.close()


def test_a_refused_re_enrolment_keeps_the_working_credential(tenant, service, monkeypatch):
    """If the new capture is refused, the person must NOT be left with nothing."""
    db = SessionLocal()
    set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, f"bv-{uuid.uuid4().hex[:6]}")
        good, _ = _mint(db, tenant, subj, FACE_A)
        db.flush()

        with pytest.raises(Exception):           # quality gate refuses a rubbish capture
            _mint(db, tenant, subj, "data:image/jpeg;base64,Zm9vYmFy")

        db.refresh(good)
        assert good.status == "active"            # still usable
        assert entry_service.active_credential(db, subj.id).id == good.id
        db.commit()
    finally:
        db.close()
