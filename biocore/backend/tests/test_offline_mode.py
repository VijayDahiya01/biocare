"""Offline / poor-network mode (§16 Option B, §22): encrypted device-bound roster build +
decrypt round-trip, consent filtering, idempotent decision sync, and auto-wipe.

Integration test — skips if Postgres/Redis are unreachable. Needs FAKE_GOV_IDENTITY=true.
"""
import base64
import json
import uuid
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select

from app.api.deps import DeviceContext
from app.core.db import SessionLocal, set_tenant_guc
from app.core.policy import ConsentPurpose, VerificationOutcome
from app.models import ConsentReceipt, OfflineRoster, TenantSubject
from app.services import (
    credential_vault,
    entry_service,
    identity_proofing,
    offline_roster,
)
from app.services.auth_service import provision_tenant
from app.services.device_service import register_device

CONSENTS = [p.value for p in ConsentPurpose if p.value not in ("cross_tenant_reuse", "marketing")]


@pytest.fixture
def tenant(require_stack):
    db = SessionLocal()
    t = provision_tenant(db, name="OF", org_code=f"OF-{uuid.uuid4().hex[:8]}", vertical="office",
                         plan="starter", admin_email=f"of_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="OF Admin")
    db.close()
    return t["tenant_id"]


def _verified_subject_with_cred(db, tid, ref, tag):
    subj = TenantSubject(tenant_id=tid, external_reference=ref, subject_type="member")
    db.add(subj); db.flush()
    s = identity_proofing.start_session(db, tenant_id=tid, tenant_subject_id=subj.id, provider_label="fake")
    for p in CONSENTS:
        identity_proofing.record_consent(db, tenant_id=tid, tenant_subject_id=subj.id, purpose=p)
    identity_proofing.run_government_fetch(db, session=s, subject_ref=ref, credential={"reference": ref})
    identity_proofing.complete_verification(db, session=s, outcome=VerificationOutcome.VERIFIED)
    credential_vault.create_credential(
        db, tenant_id=tid, tenant_subject_id=subj.id, vector=entry_service._embed(tag),
        purpose=ConsentPurpose.ENTRY_AUTHENTICATION.value)
    db.flush()
    return subj


def _device_ctx(db, tid):
    res = register_device(db, tenant_id=tid, name=f"GATE-{uuid.uuid4().hex[:4]}",
                          zone_id=None, capture_method="face")
    return DeviceContext(device_id=res["device_id"], tenant_id=tid, zone_id=None, db=db,
                         token=res["pairing_token"]), res["pairing_token"]


def test_roster_build_and_device_decrypt(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        _verified_subject_with_cred(db, tenant, "OFF-1", "face-A")
        dc, token = _device_ctx(db, tenant)
        result = offline_roster.build_roster(db, device_ctx=dc)
        assert result["subject_count"] == 1

        # the terminal derives the same device-bound key and decrypts
        key = offline_roster.device_roster_key(token, result["roster_id"])
        blob = base64.b64decode(result["roster"]); nonce = base64.b64decode(result["nonce"])
        payload = json.loads(AESGCM(key).decrypt(nonce, blob, result["roster_id"].encode()))
        assert payload["roster_id"] == result["roster_id"]
        entry = payload["entries"][0]
        assert entry["external_reference"] == "OFF-1"
        assert base64.b64decode(entry["template"]) == entry_service._embed("face-A")

        # wrong device key can't open it
        with pytest.raises(Exception):
            AESGCM(offline_roster.device_roster_key("other-token", result["roster_id"])).decrypt(
                nonce, blob, result["roster_id"].encode())
        db.commit()
    finally:
        db.close()


def test_roster_excludes_withdrawn_consent(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject_with_cred(db, tenant, "OFF-2", "face-B")
        rcpt = db.execute(select(ConsentReceipt).where(
            ConsentReceipt.tenant_subject_id == subj.id,
            ConsentReceipt.purpose_id == ConsentPurpose.ENTRY_AUTHENTICATION.value)).scalars().first()
        rcpt.withdrawn_at = datetime.now(timezone.utc); db.flush()
        dc, _ = _device_ctx(db, tenant)
        result = offline_roster.build_roster(db, device_ctx=dc)
        assert result["subject_count"] == 0  # consent withdrawn -> not in roster
        db.commit()
    finally:
        db.close()


def test_offline_sync_is_idempotent(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj = _verified_subject_with_cred(db, tenant, "OFF-3", "face-C")
        dc, _ = _device_ctx(db, tenant)
        decisions = [{"subject_id": str(subj.id), "decision": "allow", "reason": "ALLOWED",
                      "nonce": uuid.uuid4().hex}]
        first = offline_roster.sync_decisions(db, device_ctx=dc, decisions=decisions)
        second = offline_roster.sync_decisions(db, device_ctx=dc, decisions=decisions)
        assert first == {"recorded": 1, "skipped": 0}
        assert second == {"recorded": 0, "skipped": 1}  # same nonce -> deduped
        db.commit()
    finally:
        db.close()


def test_roster_wipe(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        _verified_subject_with_cred(db, tenant, "OFF-4", "face-D")
        dc, _ = _device_ctx(db, tenant)
        result = offline_roster.build_roster(db, device_ctx=dc)
        assert offline_roster.wipe(db, device_ctx=dc, roster_id=result["roster_id"]) is True
        r = db.get(OfflineRoster, result["roster_id"])
        assert r.status == "wiped" and r.wiped_at is not None
        db.commit()
    finally:
        db.close()
