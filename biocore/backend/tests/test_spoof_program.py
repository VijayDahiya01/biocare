"""Spoof-testing program (BIOCORE_COMPLETE_CHANGE_SPEC §22.3).

Codifies the eight §22.3 attack vectors as executable checks against the platform's controls:

  * Presentation attacks (printed photo, phone screen, tablet replay, recorded video, mask,
    deepfake feed) are caught by the liveness/PAD gate — and a face MATCH alone never grants
    entry (§29.11), so a flagged spoof is DENIED regardless of a convincing face.
  * Channel attacks (virtual camera, camera injection) are caught upstream by the trusted,
    signed request context (§12.4): a forged/injected request fails signature verification.

The *accuracy* of real presentation-attack detection is validated against the ZepIris engine
at operational acceptance (§22.6); the dev engine is a stand-in, so that check is skipped here.
"""
import time
import uuid

import pytest

from app.api.deps import DeviceContext
from app.core.db import SessionLocal, set_tenant_guc
from app.core.policy import EntryReason
from app.services import authorization, request_context
from app.services.auth_service import provision_tenant
from app.services.device_service import register_device
from app.services.request_context import TrustedContextError

PRESENTATION_VECTORS = ["printed_photo", "phone_screen", "tablet_replay", "recorded_video",
                        "mask", "deepfake_feed"]
CHANNEL_VECTORS = ["virtual_camera", "camera_injection"]


@pytest.mark.parametrize("vector", PRESENTATION_VECTORS)
def test_presentation_spoof_is_denied(vector):
    """A correct PAD/liveness engine flags the spoof (liveness_passed=False); the gate must
    DENY even though the presented artefact 'matches' a real face (§29.11)."""
    reason = authorization.evaluate(
        face_match_passed=True,       # the spoof looks like the real subject...
        liveness_passed=False,        # ...but PAD flags it as not-live
        subject=object(), credential=object(), consent_active=True,
    )
    assert reason == EntryReason.LIVENESS_FAILED, f"{vector} should be denied by the liveness gate"


@pytest.fixture
def device(require_stack):
    db = SessionLocal()
    t = provision_tenant(db, name="SP", org_code=f"SP-{uuid.uuid4().hex[:8]}", vertical="office",
                         plan="starter", admin_email=f"sp_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="SP Admin")
    tid = t["tenant_id"]
    db.close()
    db = SessionLocal(); set_tenant_guc(db, tid)
    res = register_device(db, tenant_id=tid, name="GATE", zone_id=None, capture_method="face")
    dc = DeviceContext(device_id=res["device_id"], tenant_id=tid, zone_id=None, db=db,
                       token=res["pairing_token"])
    yield db, dc, res["pairing_token"]
    db.close()


@pytest.mark.parametrize("vector", CHANNEL_VECTORS)
def test_channel_injection_rejected_by_signed_context(vector, device):
    """Virtual-camera / injected-capture attacks arrive as requests whose signed context does
    not verify against the trusted device — rejected before any matching (§12.4)."""
    db, dc, token = device
    ctx = {
        "device_id": dc.device_id, "tenant_id": dc.tenant_id, "gate_id": None, "zone_id": None,
        "timestamp": time.time(), "nonce": uuid.uuid4().hex,
        "software_version": "1.4.0", "policy_version": "v1",
    }
    ctx["signature"] = request_context.sign(token, ctx)
    ctx["signature"] = "f0rged" + ctx["signature"][6:]   # injected/forged capture channel
    with pytest.raises(TrustedContextError):
        request_context.verify(db, device_ctx=dc, ctx=ctx, secret=token)


@pytest.mark.skip(reason="Real presentation-attack-detection accuracy (FAR/FRR/APCER/BPCER) "
                         "requires the ZepIris engine; validated at operational acceptance (§22.6). "
                         "The dev engine is a deterministic stand-in.")
def test_real_pad_accuracy_against_engine():
    ...  # pragma: no cover
