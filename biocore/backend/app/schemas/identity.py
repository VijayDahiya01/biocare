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


class RetentionPolicyBody(BaseModel):
    data_category: str = "face_credential"
    retention_period: str | None = None   # e.g. "30d", "1y", "8h"
    expiry_trigger: str | None = None      # e.g. "event_end", "checkout", "employment_end"
    deletion_method: str = "hard_delete"
    legal_hold_allowed: bool = True
