"""Request schemas for the entry & device-trust APIs (BIOCORE_COMPLETE_CHANGE_SPEC §10.3, §10.5)."""
from pydantic import BaseModel


class RequestContext(BaseModel):
    """Signed gate-request context (§12.4). device_id/tenant_id are echoed here and verified
    against the authenticated device; the signature is HMAC-SHA256(device_token, canonical)."""
    device_id: str
    tenant_id: str
    gate_id: str | None = None
    zone_id: str | None = None
    timestamp: float
    nonce: str
    software_version: str = ""
    policy_version: str = "v1"
    signature: str


class ResolveClaim(BaseModel):
    claim: str


class MatchRequest(BaseModel):
    subject_id: str
    image: str
    context: RequestContext | None = None


class IdentifyRequest(BaseModel):
    """Walk-up 1:N: capture a face, recognise who it is. No claim/ID needed."""
    image: str
    gate_id: str | None = None
    direction: str = "in"   # in = check-in, out = check-out


class AuthorizeRequest(BaseModel):
    subject_id: str


class CommitRequest(BaseModel):
    subject_id: str
    decision: str
    reason: str


class ManualReview(BaseModel):
    subject_id: str
    note: str | None = None


class ManualOverride(BaseModel):
    subject_id: str
    operator: str
    supervisor: str | None = None
    reason: str
    note: str | None = None


class DevicePair(BaseModel):
    name: str
    zone_id: str | None = None
    capture_method: str = "face"


class DeviceAttest(BaseModel):
    certificate: str


class DeviceIdBody(BaseModel):
    device_id: str


class DevicePosture(BaseModel):
    """A terminal's attested hardening posture (§12.3)."""
    kiosk_mode: bool = False
    disk_encryption: bool = False
    screen_lock: bool = False
    os_auto_update: bool = False
    ports_restricted: bool = False
    downloads_disabled: bool = False
    local_export_disabled: bool = False
    software_version: str | None = None


class OfflineDecision(BaseModel):
    """One gate decision a terminal made while offline (§16 Option B)."""
    subject_id: str | None = None
    decision: str                        # allow | deny | manual_review
    reason: str
    nonce: str                           # idempotency key for sync dedupe
    match_result: str | None = None
    confidence_band: str | None = None
    timestamp: float | None = None


class OfflineSyncRequest(BaseModel):
    decisions: list[OfflineDecision]


class RosterWipe(BaseModel):
    roster_id: str
