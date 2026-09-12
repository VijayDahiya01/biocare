"""Security-testing program (BIOCORE_COMPLETE_CHANGE_SPEC §22.5).

Executable security-acceptance checks against the real controls:

  tenant-isolation · template-copy · KMS-policy · replay · session/CSRF · log leakage ·
  backup leakage · erasure verification.

Full external-scope items (third-party API penetration test, live device-compromise, backup
infrastructure) are exercised in representative slices here and completed out-of-band at
operational acceptance (§22.6). Integration test — skips if Postgres/Redis are unreachable.
"""
import base64
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import DeviceContext
from app.core.config import settings
from app.core.crypto import EncryptedTemplate, KmsError, decrypt_template
from app.core.db import SessionLocal, bypass_rls, set_tenant_guc
from app.core.policy import ConsentPurpose, VerificationOutcome
from app.models import AuditLog, ErasureJob, TenantSubject
from app.services import (
    credential_vault,
    entry_service,
    erasure_service,
    identity_proofing,
    request_context,
)
from app.services.auth_service import provision_tenant
from app.services.device_service import register_device

CONSENTS = [p.value for p in ConsentPurpose if p.value not in ("cross_tenant_reuse", "marketing")]


def _tenant():
    db = SessionLocal()
    t = provision_tenant(db, name="SEC", org_code=f"SEC-{uuid.uuid4().hex[:8]}", vertical="office",
                         plan="starter", admin_email=f"sec_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="SEC Admin")
    db.close()
    return t["tenant_id"]


@pytest.fixture
def tenant(require_stack):
    return _tenant()


def _verified_cred(db, tid, ref, tag):
    subj = TenantSubject(tenant_id=tid, external_reference=ref, subject_type="member")
    db.add(subj); db.flush()
    s = identity_proofing.start_session(db, tenant_id=tid, tenant_subject_id=subj.id, provider_label="fake")
    for p in CONSENTS:
        identity_proofing.record_consent(db, tenant_id=tid, tenant_subject_id=subj.id, purpose=p)
    identity_proofing.run_government_fetch(db, session=s, subject_ref=ref, credential={"reference": ref})
    identity_proofing.complete_verification(db, session=s, outcome=VerificationOutcome.VERIFIED)
    cred = credential_vault.create_credential(
        db, tenant_id=tid, tenant_subject_id=subj.id, vector=entry_service._embed(tag),
        purpose=ConsentPurpose.ENTRY_AUTHENTICATION.value)
    db.flush()
    return subj, cred


# --- tenant isolation (RLS) ---
def test_tenant_isolation(require_stack):
    a, b = _tenant(), _tenant()
    dba = SessionLocal(); set_tenant_guc(dba, a)
    subj = TenantSubject(tenant_id=a, external_reference="ISO-1", subject_type="member")
    dba.add(subj); dba.commit(); sid = subj.id; dba.close()

    dbb = SessionLocal(); set_tenant_guc(dbb, b)
    assert dbb.get(TenantSubject, sid) is None          # RLS hides A's row from B
    dbb.close()

    dbx = SessionLocal()
    with bypass_rls(dbx):
        assert dbx.get(TenantSubject, sid) is not None   # ...but the row really exists
    dbx.close()


# --- template copy (envelope AAD binding) ---
def test_template_copy_rejected(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        _, cred = _verified_cred(db, tenant, "SEC-CP", "face-A")
        rec = EncryptedTemplate(
            ciphertext=cred.encrypted_template, encrypted_dek=cred.encrypted_dek, nonce=cred.nonce,
            key_version=cred.key_version, model_version=cred.model_version,
            template_version=cred.template_version)
        # correct context decrypts
        assert decrypt_template(rec, tenant_id=str(tenant), subject_id=str(cred.tenant_subject_id),
                                purpose_id=cred.purpose_id)
        # copied to another subject -> AAD mismatch -> fails
        with pytest.raises(KmsError):
            decrypt_template(rec, tenant_id=str(tenant), subject_id=str(uuid.uuid4()),
                             purpose_id=cred.purpose_id)
        # copied to another purpose -> fails
        with pytest.raises(KmsError):
            decrypt_template(rec, tenant_id=str(tenant), subject_id=str(cred.tenant_subject_id),
                             purpose_id="marketing")
        # copied to another tenant -> wrong KEK -> fails
        with pytest.raises(KmsError):
            decrypt_template(rec, tenant_id=str(uuid.uuid4()), subject_id=str(cred.tenant_subject_id),
                             purpose_id=cred.purpose_id)
        db.commit()
    finally:
        db.close()


# --- KMS policy + fake-gov policy: forbidden in production ---
def test_software_kms_and_fake_gov_forbidden_in_production(monkeypatch):
    from app.adapters.gov_identity import get_gov_identity
    from app.core.crypto.envelope import get_kms
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "fake_gov_identity", True)
    try:
        get_kms.cache_clear()
        with pytest.raises(KmsError):
            get_kms()
        get_gov_identity.cache_clear()
        with pytest.raises(Exception):
            get_gov_identity()
    finally:
        get_kms.cache_clear()          # so later tests get the dev providers back
        get_gov_identity.cache_clear()


# --- replay attack (signed request nonce) ---
def test_replay_attack_rejected(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        res = register_device(db, tenant_id=tenant, name="GATE", zone_id=None, capture_method="face")
        dc = DeviceContext(device_id=res["device_id"], tenant_id=tenant, zone_id=None, db=db,
                           token=res["pairing_token"])
        ctx = {"device_id": dc.device_id, "tenant_id": dc.tenant_id, "gate_id": None, "zone_id": None,
               "timestamp": time.time(), "nonce": uuid.uuid4().hex,
               "software_version": "1.4.0", "policy_version": "v1"}
        ctx["signature"] = request_context.sign(res["pairing_token"], ctx)
        request_context.verify(db, device_ctx=dc, ctx=ctx, secret=res["pairing_token"])   # first ok
        with pytest.raises(Exception):                                                     # replay
            request_context.verify(db, device_ctx=dc, ctx=ctx, secret=res["pairing_token"])
        db.commit()
    finally:
        db.close()


# --- session required + CSRF enforced (session-hijack facet) ---
@pytest.fixture
def app_client(require_stack):
    from app.main import app
    return TestClient(app)


def test_session_required_and_csrf_enforced(app_client):
    # no session -> 401
    assert app_client.post("/api/v1/retention/sweep").status_code == 401

    org = f"SEC-{uuid.uuid4().hex[:8]}"; email = f"a_{uuid.uuid4().hex[:8]}@x.com"
    r = app_client.post("/api/v1/admin/tenants", json={
        "name": "Org", "org_code": org, "vertical": "office",
        "admin_email": email, "admin_password": "supersecret123", "admin_name": "A"})
    secret = parse_qs(urlparse(r.json()["data"]["totp_provisioning_uri"]).query)["secret"][0]
    app_client.post("/api/v1/auth/login", json={
        "email": email, "password": "supersecret123", "totp_code": pyotp.TOTP(secret).now()})
    # authenticated but no X-CSRF-Token on a mutating call -> 403
    r = app_client.post("/api/v1/retention/sweep")
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_FAILED"


# --- log leakage + backup leakage ---
def test_no_biometric_in_logs_or_at_rest(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj, cred = _verified_cred(db, tenant, "SEC-LOG", "face-Z")
        entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None,
                                subject_id=subj.id, image="face-Z")
        db.commit()

        # backup leakage: at rest the template is ciphertext, never the plaintext vector
        assert cred.encrypted_template != entry_service._embed("face-Z")

        # log leakage: no biometric payload / gov photo marker / template appears in audit
        rows = db.execute(select(AuditLog).where(AuditLog.tenant_id == tenant)).scalars().all()
        blob = json.dumps([{"a": r.action, "t": r.target_id, "m": r.metadata_} for r in rows])
        tb64 = base64.b64encode(entry_service._embed("face-Z")).decode()
        for forbidden in ("FAKE_GOV_PHOTO", tb64, "encrypted_template"):
            assert forbidden not in blob
    finally:
        db.close()


# --- erasure verification ---
def test_erasure_leaves_nothing_recoverable(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj, cred = _verified_cred(db, tenant, "SEC-ERZ", "face-E")
        job = ErasureJob(tenant_id=tenant, tenant_subject_id=subj.id, scope="subject", status="pending")
        db.add(job); db.flush()
        erasure_service.run_job(db, job=job); db.flush()
        db.refresh(cred); db.refresh(subj)
        assert cred.encrypted_template == b"" and cred.encrypted_dek == b"" and cred.status == "erased"
        assert subj.verification_status == "erased"
        assert job.status == "completed" and job.certificate_id           # verifiable proof
        db.commit()
    finally:
        db.close()


def test_production_refuses_to_boot_on_dev_shortcuts(monkeypatch):
    """The dev flags are individually guarded at point of use, which means a misconfiguration
    is discovered by whoever is standing at a gate. This catches it at startup instead."""
    from app.core import guards
    from app.core.config import settings as s

    monkeypatch.setattr(s, "environment", "production")
    monkeypatch.setattr(s, "dev_login", True)
    problems = guards.production_problems()
    assert any("DEV_LOGIN" in p for p in problems)
    with pytest.raises(RuntimeError, match="not safe for production"):
        guards.assert_production_safe()

    # In development it must never interfere.
    monkeypatch.setattr(s, "environment", "development")
    guards.assert_production_safe()


def test_dev_login_is_absent_in_production(monkeypatch):
    """A complete authentication bypass: it sessions as any email with no password and no OTP.
    The route must be gone in production even if the flag is left on by mistake."""
    from app.core.config import settings as s
    from app.main import app as fastapi_app
    monkeypatch.setattr(s, "dev_login", True)
    monkeypatch.setattr(s, "environment", "production")
    with TestClient(fastapi_app) as c:
        r = c.post("/api/v1/person/auth/dev-login", json={"email": "someone@example.com"})
    assert r.status_code == 404, "dev-login must not exist in production"
