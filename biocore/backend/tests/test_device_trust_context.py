"""Device hardening + trusted request context (§12.3–4, §22).

Signed gate context: freshness, identity binding, version/policy gates, HMAC signature and
nonce anti-replay; plus terminal hardening posture attestation. Integration test — skips if
Postgres/Redis are unreachable.
"""
import time
import uuid

import pytest

from app.api.deps import DeviceContext
from app.core.config import settings
from app.core.db import SessionLocal, set_tenant_guc
from app.services import device_trust, request_context
from app.services.auth_service import provision_tenant
from app.services.device_service import register_device
from app.services.request_context import TrustedContextError


@pytest.fixture
def tenant(require_stack):
    db = SessionLocal()
    t = provision_tenant(db, name="DT", org_code=f"DT-{uuid.uuid4().hex[:8]}", vertical="office",
                         plan="starter", admin_email=f"dt_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="DT Admin")
    db.close()
    return t["tenant_id"]


def _device(db, tid):
    res = register_device(db, tenant_id=tid, name=f"KIOSK-{uuid.uuid4().hex[:4]}",
                          zone_id=None, capture_method="face")
    return res["device_id"], res["pairing_token"]


def _ctx(device_id, tid, token, **over):
    base = {
        "device_id": device_id, "tenant_id": tid, "gate_id": None, "zone_id": None,
        "timestamp": time.time(), "nonce": uuid.uuid4().hex,
        "software_version": "1.4.0", "policy_version": settings.current_policy_version,
    }
    base.update(over)
    base["signature"] = request_context.sign(token, base)
    return base


def test_signed_context_valid_then_replay(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        device_id, token = _device(db, tenant)
        dc = DeviceContext(device_id=device_id, tenant_id=tenant, zone_id=None, db=db, token=token)
        ctx = _ctx(device_id, tenant, token)

        request_context.verify(db, device_ctx=dc, ctx=ctx, secret=token)  # first use: ok
        with pytest.raises(TrustedContextError, match="Replayed"):        # same nonce: replay
            request_context.verify(db, device_ctx=dc, ctx=ctx, secret=token)
        db.commit()
    finally:
        db.close()


def test_bad_signature_stale_and_wrong_device(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        device_id, token = _device(db, tenant)
        dc = DeviceContext(device_id=device_id, tenant_id=tenant, zone_id=None, db=db, token=token)

        tampered = _ctx(device_id, tenant, token)
        tampered["signature"] = "deadbeef"
        with pytest.raises(TrustedContextError, match="signature"):
            request_context.verify(db, device_ctx=dc, ctx=tampered, secret=token)

        stale = _ctx(device_id, tenant, token, timestamp=time.time() - 10_000)
        with pytest.raises(TrustedContextError, match="Stale"):
            request_context.verify(db, device_ctx=dc, ctx=stale, secret=token)

        wrong = _ctx(str(uuid.uuid4()), tenant, token)
        with pytest.raises(TrustedContextError, match="device_id"):
            request_context.verify(db, device_ctx=dc, ctx=wrong, secret=token)
        db.commit()
    finally:
        db.close()


def test_version_and_policy_gates(tenant, monkeypatch):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        device_id, token = _device(db, tenant)
        dc = DeviceContext(device_id=device_id, tenant_id=tenant, zone_id=None, db=db, token=token)

        monkeypatch.setattr(settings, "min_terminal_software_version", "2.0.0")
        old = _ctx(device_id, tenant, token, software_version="1.4.0")
        with pytest.raises(TrustedContextError, match="software version"):
            request_context.verify(db, device_ctx=dc, ctx=old, secret=token)

        monkeypatch.setattr(settings, "min_terminal_software_version", "")
        monkeypatch.setattr(settings, "current_policy_version", "v2")
        wrongpol = _ctx(device_id, tenant, token, policy_version="v1")
        with pytest.raises(TrustedContextError, match="policy_version"):
            request_context.verify(db, device_ctx=dc, ctx=wrongpol, secret=token)
        db.commit()
    finally:
        db.close()


def test_posture_attestation_and_gate(tenant):
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        device_id, _ = _device(db, tenant)
        full = {k: True for k in device_trust.POSTURE_BASELINE}
        d = device_trust.record_posture(db, device_id=device_id, posture=full, software_version="1.4.0")
        db.flush()
        assert device_trust.posture_ok(d) is True
        assert d.software_version == "1.4.0" and d.posture_attested_at is not None

        partial = dict(full); partial["disk_encryption"] = False
        d2 = device_trust.record_posture(db, device_id=device_id, posture=partial)
        db.flush()
        assert device_trust.posture_ok(d2) is False
        db.commit()
    finally:
        db.close()
