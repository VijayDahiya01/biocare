"""End-to-end verified-identity flow (§22.1): consent → government fetch → 1:1 verify →
encrypted credential → gate allow/deny → revoke → expiry sweep → erasure + certificate.

Integration test — skips if Postgres/Redis are unreachable. Needs FAKE_GOV_IDENTITY=true.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal, set_tenant_guc
from app.core.policy import ConsentPurpose, VerificationOutcome
from app.models import ConsentReceipt, ErasureJob, TenantSubject
from app.services import (
    credential_vault,
    entry_service,
    erasure_service,
    identity_proofing,
    retention_service,
)
from app.services.auth_service import provision_tenant

CONSENTS = [p.value for p in ConsentPurpose if p.value not in ("cross_tenant_reuse", "marketing")]


@pytest.fixture
def tenant(require_stack):
    db = SessionLocal()
    t = provision_tenant(db, name="VI", org_code=f"VI-{uuid.uuid4().hex[:8]}", vertical="office",
                         plan="starter", admin_email=f"vi_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="VI Admin")
    db.close()
    return t["tenant_id"]


def _verified_subject(db, tid, ref):
    subj = TenantSubject(tenant_id=tid, external_reference=ref, subject_type="member")
    db.add(subj)
    db.flush()
    s = identity_proofing.start_session(db, tenant_id=tid, tenant_subject_id=subj.id, provider_label="fake")
    for p in CONSENTS:
        identity_proofing.record_consent(db, tenant_id=tid, tenant_subject_id=subj.id, purpose=p)
    identity_proofing.run_government_fetch(db, session=s, subject_ref=ref, credential={"reference": ref})
    identity_proofing.complete_verification(db, session=s, outcome=VerificationOutcome.VERIFIED)
    db.flush()
    assert subj.verification_status == "verified"
    return subj


def _cred(db, tid, subj, tag, expires_at=None):
    c = credential_vault.create_credential(
        db, tenant_id=tid, tenant_subject_id=subj.id, vector=entry_service._embed(tag),
        purpose=ConsentPurpose.ENTRY_AUTHENTICATION.value, expires_at=expires_at)
    db.flush()
    return c


def test_full_flow_allow_deny_revoke_erase(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, "EMP-1")
        vec = entry_service._embed("face-A")
        cred = _cred(db, tenant, subj, "face-A")
        assert cred.encrypted_template != vec and cred.status == "active"

        r1 = entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None, subject_id=subj.id, image="face-A")
        assert (r1["decision"], r1["reason"]) == ("allow", "ALLOWED")

        r2 = entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None, subject_id=subj.id, image="intruder")
        assert (r2["decision"], r2["reason"]) == ("deny", "FACE_MISMATCH")

        credential_vault.revoke_credential(db, credential=cred); db.flush()
        r3 = entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None, subject_id=subj.id, image="face-A")
        assert (r3["decision"], r3["reason"]) == ("deny", "CREDENTIAL_EXPIRED")

        credential_vault.erase_credential(db, credential=cred); db.flush()
        assert cred.encrypted_template == b"" and cred.status == "erased"
        db.commit()
    finally:
        db.close()


def test_consent_withdrawal_blocks_entry(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, "EMP-2")
        _cred(db, tenant, subj, "face-B")
        rcpt = db.execute(select(ConsentReceipt).where(
            ConsentReceipt.tenant_subject_id == subj.id,
            ConsentReceipt.purpose_id == ConsentPurpose.ENTRY_AUTHENTICATION.value)).scalars().first()
        rcpt.withdrawn_at = datetime.now(timezone.utc); db.flush()
        r = entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None, subject_id=subj.id, image="face-B")
        assert r["reason"] == "CONSENT_WITHDRAWN"
        db.commit()
    finally:
        db.close()


def test_credential_expiry_sweep(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, "EMP-3")
        past = datetime.now(timezone.utc) - timedelta(days=1)
        cred = _cred(db, tenant, subj, "face-C", expires_at=past)
        assert retention_service.sweep_expired(db, tenant) >= 1
        assert cred.status == "expired"  # sweep mutated the in-session credential
        db.commit()
    finally:
        db.close()


def test_erasure_job_zeroizes_and_certifies(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject(db, tenant, "EMP-4")
        cred = _cred(db, tenant, subj, "face-D")
        job = ErasureJob(tenant_id=tenant, tenant_subject_id=subj.id, scope="subject", status="pending")
        db.add(job); db.flush()
        erasure_service.run_job(db, job=job); db.flush()
        db.refresh(cred); db.refresh(subj)
        assert cred.status == "erased" and cred.encrypted_template == b""
        assert job.status == "completed" and job.certificate_id
        assert subj.verification_status == "erased"
        db.commit()
    finally:
        db.close()
