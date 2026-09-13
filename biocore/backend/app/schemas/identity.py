"""Request schemas for the verified-identity APIs (BIOCORE_COMPLETE_CHANGE_SPEC §10)."""
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    external_reference: str | None = None
    display_name: str | None = None
    subject_type: str = "member"
    provider_label: str = ""


class ConsentGrant(BaseModel):
    purposes: list[str]
    notice_id: str | None = None
    method: str = "app"


class GovFetch(BaseModel):
    # provider-agnostic credential payload (e.g. a reference id) — never a raw ID number.
    credential: dict = Field(default_factory=dict)


class VerifyRequest(BaseModel):
    live_image: str | None = None


class CredentialCreate(BaseModel):
    tenant_subject_id: str
    image: str
    purpose: str | None = None
    expires_at: str | None = None  # ISO-8601


class ReEnroll(BaseModel):
    image: str


class ErasureRequest(BaseModel):
    tenant_subject_id: str
    scope: str = "subject"


class StartVerify(BaseModel):
    consents: list[str]


class CompleteVerify(BaseModel):
    reference: str = ""
    image: str
    document: str | None = None      # required when the org asks for one
    document_type: str = "PASSPORT"
    # Aadhaar is a two-step check: send the number to get a code on the registered mobile,
    # then verify with the reference and that code. The number itself never reaches this call.
    gov_reference_id: str | None = None
    gov_otp: str | None = None


class RetentionPolicyBody(BaseModel):
    data_category: str = "face_credential"
    retention_period: str | None = None   # e.g. "30d", "1y", "8h"
    expiry_trigger: str | None = None      # e.g. "event_end", "checkout", "employment_end"
    deletion_method: str = "hard_delete"
    legal_hold_allowed: bool = True


class GovOtpRequest(BaseModel):
    """Step 1 of an Aadhaar check — the number is used once and never stored."""
    aadhaar_number: str
