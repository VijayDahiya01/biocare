"""Verified-identity & entry-management data model (BIOCORE_COMPLETE_CHANGE_SPEC §9).

**Additive & parallel** to the existing `persons`/`users` model — nothing here replaces the
current flows; tenants migrate onto tenant-subjects gradually.

`platform_accounts` is GLOBAL (optional login/self-service, hashed contacts only, no RLS,
not customer-queryable). Everything else is TENANT-scoped (`tenant_id` + FORCE RLS), so a
subject/credential in one tenant is invisible to another (§8.3, §29.12). No raw government
data, government photo, or plaintext template is ever stored here (§5.5, §14.1, §29).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


def _ts(nullable: bool = True):
    return mapped_column(DateTime(timezone=True), nullable=nullable)


class PlatformAccount(Base):
    """Optional account-level login/self-service. GLOBAL, no RLS, hashed contacts only —
    customers cannot query it (§8.1, §9.1 platform_accounts)."""
    __tablename__ = "platform_accounts"

    id: Mapped[uuid.UUID] = uuid_pk()
    email_hash: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String, server_default=text("'active'"))
    created_at: Mapped[datetime] = created_at_col()
    last_login_at: Mapped[datetime | None] = _ts()


class TenantSubject(Base):
    """A person INSIDE one tenant — separate id/status/consent per tenant (§8.1, §8.3)."""
    __tablename__ = "tenant_subjects"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    # optional internal link to a platform account — NOT exposed to customers.
    platform_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    subject_type: Mapped[str] = mapped_column(String, server_default=text("'member'"))
    status: Mapped[str] = mapped_column(String, server_default=text("'pending_verification'"))
    verification_status: Mapped[str] = mapped_column(String, server_default=text("'unverified'"))
    authorization_status: Mapped[str] = mapped_column(String, server_default=text("'inactive'"))
    valid_from: Mapped[datetime | None] = _ts()
    valid_until: Mapped[datetime | None] = _ts()
    created_at: Mapped[datetime] = created_at_col()


class IdentityVerificationSession(Base):
    """One identity-proofing transaction (§4.2, §9.1). Stores metadata/results only —
    never the raw government response or images (§5.5)."""
    __tablename__ = "identity_verification_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    tenant_subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    government_provider: Mapped[str | None] = mapped_column(String, nullable=True)  # provider label, not a hard-coded KYC
    provider_reference_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, server_default=text("'started'"))
    assurance_level: Mapped[str | None] = mapped_column(String, nullable=True)
    liveness_result: Mapped[str | None] = mapped_column(String, nullable=True)
    face_match_result: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[datetime | None] = _ts()
    expires_at: Mapped[datetime | None] = _ts()


class VerifiedClaim(Base):
    """A minimal retained claim (§5.5, §9.1 verified_claims). e.g. age_over_18=true."""
    __tablename__ = "verified_claims"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    tenant_subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    claim_type: Mapped[str] = mapped_column(String, nullable=False)
    claim_value: Mapped[str] = mapped_column(String, nullable=False)
    verified_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime | None] = _ts()
    source: Mapped[str | None] = mapped_column(String, nullable=True)


class ConsentNotice(Base):
    """A versioned privacy notice for a purpose (§5.2, §9.1 consent_notices)."""
    __tablename__ = "consent_notices"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    purpose_id: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, server_default=text("'v1'"))
    language: Mapped[str] = mapped_column(String, server_default=text("'en'"))
    notice_text_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    active_from: Mapped[datetime] = created_at_col()
    active_until: Mapped[datetime | None] = _ts()


class FaceCredential(Base):
    """Tenant-specific ENCRYPTED entry template (§4.3, §6, §9.1 face_credentials). The
    template is never returned to callers/admins (§10.2). AES-GCM ciphertext includes the
    authentication tag, so no separate tag column is needed."""
    __tablename__ = "face_credentials"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    tenant_subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    purpose_id: Mapped[str] = mapped_column(String, server_default=text("'entry_authentication'"))
    encrypted_template: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encrypted_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    template_version: Mapped[str] = mapped_column(String, nullable=False)
    # BioVerify (§15.1). A 'bioverify' row holds an encrypted qr_text in `encrypted_template`
    # instead of an embedding, so the matcher must branch on this — handing a qr_text to the
    # local cosine path (or an embedding to BioVerify) answers wrongly instead of failing.
    # `external_credential_id` is BioVerify's own id: revoke/status upstream are keyed by it.
    # Its indexes (partial + unique per tenant) are owned by migration 0012.
    credential_source: Mapped[str] = mapped_column(String, server_default=text("'template'"))  # template|bioverify
    external_credential_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, server_default=text("'active'"))  # active|revoked|expired|erased
    created_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime | None] = _ts()
    revoked_at: Mapped[datetime | None] = _ts()
    erased_at: Mapped[datetime | None] = _ts()


class ConsentReceipt(Base):
    """Per-purpose consent decision + withdrawal (§5.3, §9.1 consent_receipts)."""
    __tablename__ = "consent_receipts"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    tenant_subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    notice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    purpose_id: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)  # granted|denied
    method: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime] = created_at_col()
    withdrawn_at: Mapped[datetime | None] = _ts()
    device_context: Mapped[str | None] = mapped_column(String, nullable=True)


class EntryAttempt(Base):
    """A minimal gate/entry event — no biometric payload (§7.5, §9.1 entry_attempts)."""
    __tablename__ = "entry_attempts"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    tenant_subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    gate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    match_result: Mapped[str | None] = mapped_column(String, nullable=True)
    liveness_result: Mapped[str | None] = mapped_column(String, nullable=True)
    authorization_result: Mapped[str | None] = mapped_column(String, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence_band: Mapped[str | None] = mapped_column(String, nullable=True)  # band, not exact score (§7.5)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_offline: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))  # §16 sync
    created_at: Mapped[datetime] = created_at_col()


class TemplateKeyEvent(Base):
    """Audit of every decrypt/encrypt/rotate/revoke/erase on a credential (§6.7, §9.1)."""
    __tablename__ = "template_key_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    face_credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False)  # encrypt|decrypt|rotate|revoke|erase
    key_version: Mapped[str | None] = mapped_column(String, nullable=True)
    service_identity: Mapped[str | None] = mapped_column(String, nullable=True)
    authorized_context: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = created_at_col()


class DataRetentionPolicy(Base):
    """Per-tenant retention config by data category (§13.3, §9.1)."""
    __tablename__ = "data_retention_policies"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    data_category: Mapped[str] = mapped_column(String, nullable=False)
    retention_period: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. '30 days'
    expiry_trigger: Mapped[str | None] = mapped_column(String, nullable=True)
    legal_hold_allowed: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    deletion_method: Mapped[str] = mapped_column(String, server_default=text("'hard_delete'"))
    created_at: Mapped[datetime] = created_at_col()


class ErasureJob(Base):
    """A verified erasure job + certificate reference (§13.4, §9.1 erasure_jobs)."""
    __tablename__ = "erasure_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    tenant_subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    scope: Mapped[str] = mapped_column(String, server_default=text("'subject'"))  # subject|credential|tenant
    status: Mapped[str] = mapped_column(String, server_default=text("'pending'"))
    started_at: Mapped[datetime | None] = _ts()
    completed_at: Mapped[datetime | None] = _ts()
    certificate_id: Mapped[str | None] = mapped_column(String, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = created_at_col()


class DeviceCertificate(Base):
    """A production terminal's certificate — paired, certified, revocable (§12.2, §9.1)."""
    __tablename__ = "device_certificates"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    certificate_thumbprint: Mapped[str] = mapped_column(String, nullable=False)
    issued_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime | None] = _ts()
    revoked_at: Mapped[datetime | None] = _ts()


class DeviceRequestNonce(Base):
    """Anti-replay store for signed gate requests (§12.4). One row per (device, nonce); a
    repeated nonce inside its freshness window means replay → the request is rejected."""
    __tablename__ = "device_request_nonces"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    nonce: Mapped[str] = mapped_column(String, nullable=False)
    seen_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime | None] = _ts()


class OfflineRoster(Base):
    """Accountability record for an encrypted offline roster issued to a terminal (§16 Option
    B). The encrypted, device-bound payload is NEVER stored here — only metadata (who got a
    roster, how many subjects, when it expires, whether the terminal confirmed auto-wipe)."""
    __tablename__ = "offline_rosters"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    subject_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    key_version: Mapped[str] = mapped_column(String, server_default=text("'roster-v1'"))
    status: Mapped[str] = mapped_column(String, server_default=text("'active'"))  # active|expired|wiped
    issued_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime | None] = _ts()
    wiped_at: Mapped[datetime | None] = _ts()
