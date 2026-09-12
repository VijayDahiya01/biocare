"""Integration connectors + hardware bridge (§19, §22).

§19.1 gov-adapter contract (validate/extract), §19.2 business connectors (roster sync +
event push, capability guard), §19.3 hardware bridge (signed allow/deny command, no biometric).
Integration parts skip if Postgres/Redis are unreachable.
"""
import base64
import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.adapters.connectors import ConnectorError, get_roster_source
from app.core.config import settings
from app.core.db import SessionLocal, set_tenant_guc
from app.models import EntryAttempt, TenantSubject
from app.services import hardware_bridge, integration_sync
from app.services.auth_service import provision_tenant


# --- §19.1 government adapter contract ---
def test_fake_gov_contract():
    from app.adapters.gov_identity.fake import FakeGovernmentProvider
    p = FakeGovernmentProvider()
    s = p.create_session(tenant_id="t", subject_ref="r", purpose="verify")
    res = p.fetch_verified_data(session=s, credential={"reference": "X"})
    assert res.claims.identity_verified and res.government_photo == b"FAKE_GOV_PHOTO"
    assert p.validate_response(raw={"ok": True}) and not p.validate_response(raw={"ok": False})


def test_sandbox_extract_claims_and_photo():
    if not settings.sandbox_api_key:
        pytest.skip("SANDBOX_API_KEY not configured")
    from app.adapters.gov_identity.sandbox import SandboxGovernmentProvider
    p = SandboxGovernmentProvider()
    pan = {"_type": "pan", "status": "valid", "name_as_per_pan_match": True,
           "date_of_birth_match": True, "category": "individual",
           "aadhaar_seeding_status": "y", "transaction_id": "tx-123"}
    assert p.validate_response(raw=pan)
    claims = p.extract_allowed_claims(raw=pan, context={"dob": "14/04/1998", "pan": "BKXPV7479J",
                                                        "session_ref": "s"})
    assert claims.identity_verified and claims.name_verified and claims.age_over_18
    assert claims.assurance_level == "sandbox_pan"
    assert p.extract_temporary_photo(raw=pan) is None            # PAN carries no photo

    aadhaar = {"_type": "aadhaar", "name": "VIJAY", "date_of_birth": "1998",
               "photo": base64.b64encode(b"IMG").decode()}
    assert p.extract_temporary_photo(raw=aadhaar) == b"IMG"       # Aadhaar carries a temp photo


# --- §19.2 business connectors ---
@pytest.fixture
def tenant(require_stack):
    db = SessionLocal()
    t = provision_tenant(db, name="IN", org_code=f"IN-{uuid.uuid4().hex[:8]}", vertical="office",
                         plan="starter", admin_email=f"in_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="IN Admin")
    db.close()
    return t["tenant_id"]


def test_connector_capability_guard():
    with pytest.raises(ConnectorError):
        get_roster_source("access_controller")   # events-only connector has no roster
    with pytest.raises(ConnectorError):
        get_roster_source("does_not_exist")


def test_roster_sync_upserts_subjects(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        r1 = integration_sync.sync_roster(db, tenant_id=tenant, kind="school_sis",
                                          config={"count": 2, "prefix": "SIS"})
        assert (r1["fetched"], r1["created"]) == (2, 2)
        r2 = integration_sync.sync_roster(db, tenant_id=tenant, kind="school_sis",
                                          config={"count": 2, "prefix": "SIS"})
        assert (r2["created"], r2["updated"]) == (0, 2)     # idempotent by external_reference
        subj = db.execute(select(TenantSubject).where(
            TenantSubject.external_reference == "SIS-001")).scalars().first()
        assert subj is not None and subj.verification_status == "unverified"  # imported, not verified
        db.commit()
    finally:
        db.close()


def test_push_entry_events(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        db.add(EntryAttempt(tenant_id=tenant, authorization_result="allow", reason_code="ALLOWED"))
        db.flush()
        res = integration_sync.push_entry_events(db, tenant_id=tenant, kind="notifications", config={})
        assert res["events"] >= 1 and res["pushed"] == res["events"]
        db.commit()
    finally:
        db.close()


# --- §19.3 hardware bridge ---
def test_hardware_command_signed_and_template_free():
    dc = SimpleNamespace(device_id="dev-1", tenant_id="t", zone_id=None, token="secret-token")
    cmd = hardware_bridge.build_command(device_ctx=dc, decision="allow", reason="ALLOWED")
    assert cmd["action"] == "open" and cmd["duration_ms"] > 0
    assert hardware_bridge.verify_command("secret-token", cmd)      # valid server signature
    assert not hardware_bridge.verify_command("wrong-token", cmd)   # forged rejected

    deny = hardware_bridge.build_command(device_ctx=dc, decision="deny", reason="FACE_MISMATCH")
    assert deny["action"] == "deny" and deny["duration_ms"] == 0

    # the command carries NO biometric material (§19.3)
    blob = json.dumps(cmd).lower()
    for forbidden in ("template", "embedding", "encrypted", "image", "vector", "subject"):
        assert forbidden not in blob
