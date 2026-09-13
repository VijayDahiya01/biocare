"""Envelope encryption for biometric face templates.

BIOCORE_COMPLETE_CHANGE_SPEC §6 — every face credential is stored as ciphertext under
authenticated envelope encryption:

  * a random 256-bit **Data Encryption Key (DEK)** encrypts the template with AES-256-GCM;
  * the DEK is wrapped by a per-tenant **Key Encryption Key (KEK)** held by the KMS —
    never stored in plaintext and never in the application database (§6.2, §29.9);
  * the ciphertext is bound (AES-GCM *associated data*) to tenant + subject + purpose +
    model/template versions, so a template cannot be copied into another tenant/purpose
    without the GCM tag failing (§6.4, §29.7/§29.12).

`SoftwareKms` derives per-tenant KEKs from a root key for the SaaS MVP. Swap in
AWS/GCP/Vault/HSM by implementing `KmsProvider` and wiring `get_kms()` — nothing else in
the platform changes (§6.5). Only the proofing/matching/erasure/rotation services should
ever call the KMS (§6.6); admins/support/DB operators must not (enforced at the service
layer, not here).
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings


class KmsError(Exception):
    pass


@dataclass
class WrappedKey:
    encrypted_dek: bytes  # DEK wrapped by the tenant KEK (nonce ‖ ciphertext ‖ tag)
    key_version: str      # KEK version used (for rotation, §6.7)


class KmsProvider(Protocol):
    """Contract every KMS backend implements."""
    def generate_data_key(self, *, tenant_id: str) -> tuple[bytes, WrappedKey]: ...
    def unwrap_data_key(self, *, tenant_id: str, wrapped: WrappedKey) -> bytes: ...


class SoftwareKms:
    """Dev/MVP KMS: per-tenant KEK derived (HKDF-SHA256) from a root key; DEK wrapped with
    AES-256-GCM. NOT an HSM — for high-security customers implement `KmsProvider` against a
    real KMS/HSM (§6.5, §17.4). Keys still stay out of the app DB (root from env/secret)."""
    KEY_VERSION = "sw-v1"

    def _root(self) -> bytes:
        raw = settings.kms_root_key or settings.master_key or settings.session_secret
        return hashlib.sha256(raw.encode()).digest()

    def _tenant_kek(self, tenant_id: str) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"biocore-kek",
                    info=f"tenant:{tenant_id}".encode()).derive(self._root())

    def generate_data_key(self, *, tenant_id: str) -> tuple[bytes, WrappedKey]:
        dek = AESGCM.generate_key(bit_length=256)
        kek = self._tenant_kek(tenant_id)
        nonce = os.urandom(12)
        wrapped = nonce + AESGCM(kek).encrypt(nonce, dek, f"kek:{tenant_id}".encode())
        return dek, WrappedKey(encrypted_dek=wrapped, key_version=self.KEY_VERSION)

    def unwrap_data_key(self, *, tenant_id: str, wrapped: WrappedKey) -> bytes:
        kek = self._tenant_kek(tenant_id)
        blob = wrapped.encrypted_dek
        nonce, ct = blob[:12], blob[12:]
        try:
            return AESGCM(kek).decrypt(nonce, ct, f"kek:{tenant_id}".encode())
        except Exception as e:  # noqa: BLE001
            raise KmsError("DEK unwrap failed (wrong tenant key or tampered)") from e


@lru_cache
def get_kms() -> KmsProvider:
    provider = (settings.kms_provider or "software").lower()
    if provider in ("software", "dev", ""):
        # SoftwareKms with no real root key derives from SESSION_SECRET/MASTER_KEY (§6.5,
        # §17.4) — anyone who reads the app config can then decrypt every template. That is
        # what production must never run on. A real KMS_ROOT_KEY closes that gap: this matches
        # the acceptable minimum guards.py already documents and enforces at startup.
        if settings.is_production and not settings.kms_root_key:
            raise KmsError(
                "SoftwareKms with no KMS_ROOT_KEY is forbidden in production. Set KMS_ROOT_KEY "
                "from a secret store, or set KMS_PROVIDER to a real KMS/HSM (aws | gcp | vault)."
            )
        return SoftwareKms()
    # Real backends (aws | gcp | vault | hsm) implement KmsProvider and wire in here.
    raise KmsError(
        f"KMS provider '{provider}' not implemented. Set KMS_PROVIDER=software for dev/MVP, "
        "or add a KmsProvider backend."
    )


@dataclass
class EncryptedTemplate:
    ciphertext: bytes       # AES-256-GCM(template) incl. tag
    encrypted_dek: bytes    # DEK wrapped by the tenant KEK
    nonce: bytes            # 96-bit GCM nonce for the template
    key_version: str
    model_version: str
    template_version: str


def _aad(*, tenant_id: str, subject_id: str, purpose_id: str,
         model_version: str, template_version: str) -> bytes:
    # binds ciphertext to its context (§6.4) — GCM verification fails if any field differs.
    return "|".join([tenant_id, subject_id, purpose_id, model_version, template_version]).encode()


def encrypt_template(vector: bytes, *, tenant_id: str, subject_id: str, purpose_id: str,
                     model_version: str, template_version: str) -> EncryptedTemplate:
    """Encrypt a face-template vector for storage. The plaintext `vector` must be a
    short-lived value from the matcher — never logged/persisted (§14.1)."""
    dek, wrapped = get_kms().generate_data_key(tenant_id=tenant_id)
    nonce = os.urandom(12)
    aad = _aad(tenant_id=tenant_id, subject_id=subject_id, purpose_id=purpose_id,
               model_version=model_version, template_version=template_version)
    ciphertext = AESGCM(dek).encrypt(nonce, vector, aad)
    # NB: Python can't truly zeroize immutable bytes; real short-lived-plaintext/zeroization
    # guarantees come from the isolated matching service (§6.9), not this layer.
    return EncryptedTemplate(
        ciphertext=ciphertext, encrypted_dek=wrapped.encrypted_dek, nonce=nonce,
        key_version=wrapped.key_version, model_version=model_version,
        template_version=template_version,
    )


def decrypt_template(rec: EncryptedTemplate, *, tenant_id: str, subject_id: str,
                     purpose_id: str) -> bytes:
    """Return the plaintext template vector. The caller MUST use it only inside the matcher
    and never log/queue/persist it (§7.5, §14.1). Raises `KmsError` if the ciphertext was
    copied to a different tenant/subject/purpose or tampered (AAD/tag mismatch)."""
    wrapped = WrappedKey(encrypted_dek=rec.encrypted_dek, key_version=rec.key_version)
    dek = get_kms().unwrap_data_key(tenant_id=tenant_id, wrapped=wrapped)
    aad = _aad(tenant_id=tenant_id, subject_id=subject_id, purpose_id=purpose_id,
               model_version=rec.model_version, template_version=rec.template_version)
    try:
        return AESGCM(dek).decrypt(rec.nonce, rec.ciphertext, aad)
    except Exception as e:  # noqa: BLE001
        raise KmsError("template decrypt/verify failed (wrong tenant/subject/purpose or tampered)") from e
