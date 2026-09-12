"""Offline / poor-network mode (BIOCORE_COMPLETE_CHANGE_SPEC §16, Option B).

Builds an ENCRYPTED, DEVICE-BOUND local roster so a terminal can keep admitting authorized
subjects when the network drops (events, schools, factories, remote sites):

  * the roster holds only currently-authorized subjects (active entry credential + verified +
    consent), with their entry templates decrypted inside this authorized boundary and
    re-encrypted for the terminal;
  * it is sealed with a key derived from the device token (device-bound) and bound to the
    roster id (AES-256-GCM AAD), so it is useless on any other terminal;
  * strict expiry + no export + terminal auto-wipe (the platform records the accountability
    metadata in `offline_rosters`, never the payload);
  * decisions made offline are synced back idempotently (deduped by nonce) when the network
    returns, recorded as `captured_offline` entry events.

Enabling this ships templates to the edge — a deliberate privacy trade-off (Option B is weaker
than Option A's QR/manual fallback), so it is gated behind settings.offline_mode == "roster".
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import EncryptedTemplate, decrypt_template
from app.core.policy import ConsentPurpose
from app.models import (
    DeviceRequestNonce,
    EntryAttempt,
    FaceCredential,
    OfflineRoster,
    TemplateKeyEvent,
    TenantSubject,
)
from app.services import entry_service

KEY_VERSION = "roster-v1"


def device_roster_key(token: str, roster_id: str) -> bytes:
    """A 256-bit key bound to BOTH the device token and this roster id (HKDF-SHA256). The
    terminal derives the same key from its token + roster id; no one else can."""
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=roster_id.encode(),
                info=b"biocore-offline-roster").derive(token.encode())


def _authorized_credentials(db: Session):
    """Active entry credentials whose subject is verified — filtered further by live consent."""
    return db.execute(
        select(FaceCredential, TenantSubject)
        .join(TenantSubject, TenantSubject.id == FaceCredential.tenant_subject_id)
        .where(
            FaceCredential.status == "active",
            FaceCredential.purpose_id == ConsentPurpose.ENTRY_AUTHENTICATION.value,
            TenantSubject.verification_status == "verified",
            TenantSubject.status != "erased",
        )
        .limit(settings.offline_roster_max_subjects)
    ).all()


def build_roster(db: Session, *, device_ctx) -> dict:
    """Assemble, seal and record a device-bound offline roster. Returns the encrypted blob
    (base64) + metadata; the plaintext templates never leave this function unencrypted."""
    roster = OfflineRoster(
        tenant_id=device_ctx.tenant_id, device_id=device_ctx.device_id, zone_id=device_ctx.zone_id,
        key_version=KEY_VERSION, status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.offline_roster_ttl_seconds),
    )
    db.add(roster)
    db.flush()  # need roster.id for the key salt + AAD

    entries: list[dict] = []
    for cred, subj in _authorized_credentials(db):
        if not entry_service.consent_active(db, subj.id):
            continue
        rec = EncryptedTemplate(
            ciphertext=cred.encrypted_template, encrypted_dek=cred.encrypted_dek, nonce=cred.nonce,
            key_version=cred.key_version, model_version=cred.model_version,
            template_version=cred.template_version)
        template = decrypt_template(rec, tenant_id=str(cred.tenant_id),
                                    subject_id=str(cred.tenant_subject_id), purpose_id=cred.purpose_id)
        db.add(TemplateKeyEvent(  # every decrypt is audited (§6.7)
            tenant_id=cred.tenant_id, face_credential_id=cred.id, operation="decrypt",
            key_version=cred.key_version, service_identity="offline_roster"))
        entries.append({
            "subject_id": str(subj.id), "external_reference": subj.external_reference,
            "template": base64.b64encode(template).decode(),
            "model_version": cred.model_version, "template_version": cred.template_version,
        })

    roster.subject_count = len(entries)
    payload = json.dumps({"roster_id": str(roster.id), "entries": entries}).encode()
    key = device_roster_key(device_ctx.token or "", str(roster.id))
    nonce = os.urandom(12)
    blob = AESGCM(key).encrypt(nonce, payload, str(roster.id).encode())  # AAD = roster id
    return {
        "roster_id": str(roster.id),
        "subject_count": roster.subject_count,
        "key_version": KEY_VERSION,
        "expires_at": roster.expires_at.isoformat(),
        "nonce": base64.b64encode(nonce).decode(),
        "roster": base64.b64encode(blob).decode(),
    }


def sync_decisions(db: Session, *, device_ctx, decisions: list[dict]) -> dict:
    """Record offline gate decisions when the network returns. Idempotent: a decision's nonce
    is deduped via the device nonce store so re-uploads don't double-count (§16 Option B)."""
    recorded = skipped = 0
    for d in decisions:
        nonce = str(d.get("nonce") or "")
        if nonce:
            seen = db.execute(select(DeviceRequestNonce).where(
                DeviceRequestNonce.device_id == device_ctx.device_id,
                DeviceRequestNonce.nonce == nonce)).scalars().first()
            if seen is not None:
                skipped += 1
                continue
            db.add(DeviceRequestNonce(
                tenant_id=device_ctx.tenant_id, device_id=device_ctx.device_id, nonce=nonce,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7)))
        db.add(EntryAttempt(
            tenant_id=device_ctx.tenant_id, tenant_subject_id=d.get("subject_id"),
            device_id=device_ctx.device_id, zone_id=device_ctx.zone_id,
            match_result=d.get("match_result"), authorization_result=d.get("decision"),
            reason_code=d.get("reason"), confidence_band=d.get("confidence_band"),
            model_version=settings.face_model_version, policy_version=settings.current_policy_version,
            captured_offline=True))
        recorded += 1
    db.flush()
    return {"recorded": recorded, "skipped": skipped}


def wipe(db: Session, *, device_ctx, roster_id: str) -> bool:
    """The terminal confirms it auto-wiped the local roster (§16 Option B)."""
    r = db.get(OfflineRoster, roster_id)
    if r is None or str(r.device_id) != str(device_ctx.device_id):
        return False
    r.status = "wiped"
    r.wiped_at = datetime.now(timezone.utc)
    return True
