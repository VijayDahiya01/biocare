"""Credential Vault service (BIOCORE_COMPLETE_CHANGE_SPEC §4.3).

Stores tenant-specific ENCRYPTED entry templates and decrypts them ONLY inside the matcher
boundary (`match_credential`). Never returns a plaintext or encrypted template to a
caller/admin (§10.2, §29.13). Every key operation is recorded in `template_key_events`
(§6.7).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.core import metrics
from app.core.config import settings
from app.core.crypto import EncryptedTemplate, KmsError, decrypt_template, encrypt_template
from app.core.policy import ConsentPurpose
from app.models import FaceCredential, TemplateKeyEvent


def _key_event(db: Session, cred: FaceCredential, operation: str, service_identity: str) -> None:
    db.add(TemplateKeyEvent(
        tenant_id=cred.tenant_id, face_credential_id=cred.id, operation=operation,
        key_version=cred.key_version, service_identity=service_identity,
    ))


def create_credential(db: Session, *, tenant_id, tenant_subject_id, vector: bytes,
                      purpose: str = ConsentPurpose.ENTRY_AUTHENTICATION.value,
                      expires_at: datetime | None = None, source: str = "template",
                      external_credential_id: str | None = None) -> FaceCredential:
    """Encrypt a FRESH entry-template vector and store it (§5.11, §6). `vector` is a
    short-lived plaintext from the matcher — never logged/persisted here (§14.1).

    `source="bioverify"` stores an external credential TEXT (`qr_text.encode()`) in the same
    field instead of an embedding. It gets the same envelope, the same AAD binding to
    tenant/subject/purpose, the same key events and the same erase-zeroize — only the meaning
    of the plaintext differs, which is why `credential_source` must travel with it (§15.1).
    """
    enc = encrypt_template(
        vector, tenant_id=str(tenant_id), subject_id=str(tenant_subject_id), purpose_id=purpose,
        model_version=settings.face_model_version, template_version=settings.face_template_version,
    )
    cred = FaceCredential(
        tenant_id=tenant_id, tenant_subject_id=tenant_subject_id, purpose_id=purpose,
        encrypted_template=enc.ciphertext, encrypted_dek=enc.encrypted_dek, nonce=enc.nonce,
        key_version=enc.key_version, model_version=enc.model_version,
        template_version=enc.template_version, status="active", expires_at=expires_at,
        credential_source=source, external_credential_id=external_credential_id,
    )
    db.add(cred)
    db.flush()
    _key_event(db, cred, "encrypt", "credential_vault")
    return cred


def _usable(credential: FaceCredential) -> bool:
    if credential.status != "active":
        return False
    return not (credential.expires_at and credential.expires_at < datetime.now(timezone.utc))


def _plaintext(db: Session, credential: FaceCredential) -> bytes:
    """Decrypt inside the matcher boundary, recording the key event (§6.7)."""
    rec = EncryptedTemplate(
        ciphertext=credential.encrypted_template, encrypted_dek=credential.encrypted_dek,
        nonce=credential.nonce, key_version=credential.key_version,
        model_version=credential.model_version, template_version=credential.template_version,
    )
    try:
        with metrics.timer("kms.unwrap_latency_ms"):  # §23 KMS latency
            plain = decrypt_template(
                rec, tenant_id=str(credential.tenant_id),
                subject_id=str(credential.tenant_subject_id), purpose_id=credential.purpose_id,
            )
    except KmsError:
        metrics.incr("kms.decrypt_failure")  # §23 decrypt failure rate / alert
        raise
    _key_event(db, credential, "decrypt", "entry_matcher")
    return plain


def credential_text(db: Session, *, credential: FaceCredential) -> str | None:
    """The decrypted BioVerify credential text (`qr_text`) for a usable credential, else None.

    Returned rather than compared because the match happens at BioVerify, not here. It is
    credential material: hand it straight to the verifier, never log it (§7.5, §14.1).
    """
    if credential.credential_source != "bioverify" or not _usable(credential):
        return None
    return _plaintext(db, credential).decode("utf-8", "strict")


def match_credential(db: Session, *, credential: FaceCredential, live_vector: bytes,
                     compare: Callable[[bytes, bytes], bool]) -> bool:
    """Decrypt the stored template INSIDE this matcher boundary, compare it with the live
    vector via `compare`, then let the plaintext go out of scope. Never logs/persists it
    (§7.5, §14.1). Returns False for a non-active or expired credential."""
    if not _usable(credential):
        return False
    return compare(_plaintext(db, credential), live_vector)


def revoke_credential(db: Session, *, credential: FaceCredential) -> None:
    credential.status = "revoked"
    credential.revoked_at = datetime.now(timezone.utc)
    _key_event(db, credential, "revoke", "credential_vault")


def erase_credential(db: Session, *, credential: FaceCredential) -> None:
    """Zeroize the ciphertext + wrapped key so nothing recoverable remains (§13.4)."""
    credential.encrypted_template = b""
    credential.encrypted_dek = b""
    credential.nonce = b""
    credential.status = "erased"
    credential.erased_at = datetime.now(timezone.utc)
    _key_event(db, credential, "erase", "erasure_service")
