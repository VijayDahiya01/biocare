"""Entry orchestration (BIOCORE_COMPLETE_CHANGE_SPEC §7.2).

resolve claim → live capture → 1:1 match (inside the vault matcher) → authorization plane →
record a MINIMAL entry event (§7.5). No biometric payload is persisted or returned; only the
decision, reason, confidence band, device/zone and versions are kept.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.bioverify import get_bioverify
from app.adapters.face_engine import FaceEngineError, get_face_engine
from app.core import metrics
from app.core.config import settings
from app.core.crypto import EncryptedTemplate, decrypt_template
from app.core.envelope import ApiError
from app.core.policy import ConsentPurpose, EntryReason
from app.models import ConsentReceipt, EntryAttempt, FaceCredential, TenantSubject
from app.services import authorization, credential_vault


def _engine():
    """Resolve the face engine, mapping an unavailable engine to a clean 503 (fails closed —
    the fake is forbidden in production, §15.1/§22.6)."""
    try:
        return get_face_engine()
    except FaceEngineError as e:
        raise ApiError(503, "FACE_ENGINE_UNAVAILABLE", str(e))


def _embed(image_b64: str) -> bytes:
    """Produce the entry-template embedding via the configured face engine (dev fake / real)."""
    return _engine().embed(image=image_b64)


def _bioverify():
    """Resolve the BioVerify service. `BioVerifyError` is a `FaceEngineError`, so an
    unavailable service already fails closed through the same 503 as the local engine."""
    try:
        return get_bioverify()
    except FaceEngineError as e:
        raise ApiError(503, "FACE_ENGINE_UNAVAILABLE", str(e))


_PAD_REASON_TOKENS = ("PAD", "SPOOF", "LIVENESS", "PRESENTATION")


def _liveness_from(result) -> bool:
    """Whether BioVerify's PAD stage passed. Its `pad` vocabulary is not pinned by the published
    schema, so read the structured field when present and fall back to the reason token: a shape
    we do not recognise must not read as 'live' when the service denied for a spoof, or the §23
    liveness-spike alert goes blind."""
    pad = result.raw.get("pad")
    if isinstance(pad, bool):
        return pad
    if isinstance(pad, dict):
        for key in ("pass", "passed", "live", "is_live"):
            if isinstance(pad.get(key), bool):
                return bool(pad[key])
    return not any(t in (result.reason or "").upper() for t in _PAD_REASON_TOKENS)


def _verify_template(db: Session, *, credential, image: str) -> tuple[bool, str, bool]:
    """Local-engine path: embed, liveness, and a 1:1 compare inside the vault matcher boundary."""
    engine = _engine()
    live_vector = engine.embed(image=image)
    liveness_passed = engine.assess_liveness(image=image).passed  # real liveness/PAD (§5.6)
    face_match, band = False, "none"
    with metrics.timer("gate.match_latency_ms"):  # §23 gate match latency
        if credential is not None:
            result = {"m": None}

            def _cmp(stored, live):  # engine decides the 1:1 match inside the vault boundary
                result["m"] = engine.compare(stored=stored, live=live)
                return result["m"].matched

            face_match = credential_vault.match_credential(
                db, credential=credential, live_vector=live_vector, compare=_cmp)
            if result["m"] is not None:
                band = result["m"].band
    return face_match, band, liveness_passed


def _verify_bioverify(db: Session, *, credential, image: str) -> tuple[bool, str, bool]:
    """BioVerify path: the template lives sealed inside the credential and the service decides
    the match, so nothing is embedded or compared here (§15.1)."""
    qr_text = credential_vault.credential_text(db, credential=credential)
    if qr_text is None:
        # Not usable (revoked/expired/erased). Report liveness as passed so `evaluate` reaches
        # the credential check and gives the TRUE reason instead of masking it as a liveness
        # failure — the outcome is a deny either way.
        return False, "none", True
    with metrics.timer("gate.match_latency_ms"):
        result = _bioverify().verify(image=image, qr_text=qr_text)
    return result.allowed, result.band, _liveness_from(result)


def resolve_claim(db: Session, *, claim: str) -> TenantSubject | None:
    if not claim:
        return None
    return db.execute(
        select(TenantSubject).where(TenantSubject.external_reference == claim)
    ).scalars().first()


def active_credential(db: Session, subject_id) -> FaceCredential | None:
    """The subject's current entry credential — NEWEST first.

    Ordering is not cosmetic. A re-enrolled subject can briefly hold more than one active row,
    and without an order the gate picks an arbitrary one: a stale credential, or one whose
    `credential_source` needs an engine that is no longer wired, would shadow the current one.
    """
    return db.execute(
        select(FaceCredential).where(
            FaceCredential.tenant_subject_id == subject_id,
            FaceCredential.status == "active",
            FaceCredential.purpose_id == ConsentPurpose.ENTRY_AUTHENTICATION.value,
        ).order_by(FaceCredential.created_at.desc())
    ).scalars().first()


def consent_active(db: Session, subject_id) -> bool:
    return db.execute(
        select(ConsentReceipt).where(
            ConsentReceipt.tenant_subject_id == subject_id,
            ConsentReceipt.purpose_id == ConsentPurpose.ENTRY_AUTHENTICATION.value,
            ConsentReceipt.decision == "granted",
            ConsentReceipt.withdrawn_at.is_(None),
        )
    ).scalars().first() is not None


def run_entry(db: Session, *, tenant_id, device_id, zone_id, subject_id, image,
              policy_version: str = "v1") -> dict:
    """The combined transactional gate decision (§7.2): capture → 1:1 match → authorize →
    record. Returns {decision, reason, attempt_id, subject_id, confidence_band}."""
    subject = db.get(TenantSubject, subject_id)
    credential = active_credential(db, subject_id) if subject else None
    try:
        if credential is not None and credential.credential_source == "bioverify":
            face_match, band, liveness_passed = _verify_bioverify(
                db, credential=credential, image=image)
        elif credential is None and settings.credential_engine == "bioverify":
            # Nothing to verify against, so no capture was sent and nothing was checked. Let
            # `evaluate` reach the credential check and report the true reason; always a deny.
            face_match, band, liveness_passed = False, "none", True
        else:
            face_match, band, liveness_passed = _verify_template(
                db, credential=credential, image=image)
    except FaceEngineError as e:
        raise ApiError(503, "FACE_ENGINE_UNAVAILABLE", str(e))
    reason = authorization.evaluate(
        face_match_passed=face_match, liveness_passed=liveness_passed, subject=subject,
        credential=credential, consent_active=(consent_active(db, subject_id) if subject else False),
    )
    metrics.incr("gate.total")
    if reason == EntryReason.FACE_MISMATCH:
        metrics.incr("gate.mismatch")
    if not liveness_passed:
        metrics.incr("gate.liveness_failure")
    decision = "allow" if reason == EntryReason.ALLOWED else "deny"
    attempt = EntryAttempt(
        tenant_id=tenant_id, tenant_subject_id=subject_id, device_id=device_id, zone_id=zone_id,
        match_result=("passed" if face_match else "failed"),
        liveness_result=("passed" if liveness_passed else "failed"),
        authorization_result=decision, reason_code=reason.value, confidence_band=band,
        model_version=settings.face_model_version, policy_version=policy_version,
    )
    db.add(attempt)
    db.flush()
    return {"decision": decision, "reason": reason.value, "attempt_id": str(attempt.id),
            "subject_id": str(subject_id), "confidence_band": band}


def _best_match(db: Session, *, live_vector: bytes, tenant_id):
    """Walk-up 1:N: embed once, then cosine the live face against every active entry credential
    in the tenant (decrypt in the matcher boundary; compare locally — no per-credential engine
    round-trips). Returns (subject, credential, score) of the best match ≥ threshold, or Nones.
    O(N) — instant for a site; production uses a vector DB (ZepIris) for large 1:N."""
    live = np.frombuffer(live_vector, dtype=np.float32)
    threshold = settings.face_match_threshold or 0.4
    best = (None, None, threshold)
    rows = db.execute(
        select(FaceCredential, TenantSubject)
        .join(TenantSubject, TenantSubject.id == FaceCredential.tenant_subject_id)
        .where(FaceCredential.status == "active",
               FaceCredential.purpose_id == ConsentPurpose.ENTRY_AUTHENTICATION.value)
        .limit(2000)
    ).all()
    for cred, subj in rows:
        rec = EncryptedTemplate(
            ciphertext=cred.encrypted_template, encrypted_dek=cred.encrypted_dek, nonce=cred.nonce,
            key_version=cred.key_version, model_version=cred.model_version,
            template_version=cred.template_version)
        try:
            stored = decrypt_template(rec, tenant_id=str(cred.tenant_id),
                                      subject_id=str(cred.tenant_subject_id), purpose_id=cred.purpose_id)
        except Exception:  # noqa: BLE001 — skip an unreadable credential, keep scanning
            continue
        v = np.frombuffer(stored, dtype=np.float32)
        if v.size == 0 or v.size != live.size or not np.isfinite(v).all():
            continue
        cos = float(np.dot(live, v) / (np.linalg.norm(live) * np.linalg.norm(v) + 1e-9))
        if cos > best[2]:
            best = (subj, cred, cos)
    return best


def _identify_bioverify(db: Session, *, tenant_id, image: str):
    """Walk-up 1:N over BioVerify credentials.

    The service has no 1:N route, so this is ONE verify call per candidate and the live image is
    re-detected, re-PAD-ed and re-embedded by the service every single time. That cost is linear
    in the tenant's population: fine for tens, painful for hundreds, hopeless for thousands. It
    is therefore bounded by `bioverify_identify_max_candidates`, overlapped
    `bioverify_identify_concurrency` at a time, and stops at the first accept. A single 1:N
    endpoint on the service (one image, many qr_texts) would collapse this to one round trip and
    one embed — get that before raising the cap.

    Returns (subject, credential, band, liveness_passed).
    """
    service = _bioverify()
    rows = db.execute(
        select(FaceCredential, TenantSubject)
        .join(TenantSubject, TenantSubject.id == FaceCredential.tenant_subject_id)
        .where(FaceCredential.status == "active",
               FaceCredential.credential_source == "bioverify",
               FaceCredential.purpose_id == ConsentPurpose.ENTRY_AUTHENTICATION.value)
        .limit(max(1, settings.bioverify_identify_max_candidates))
    ).all()
    width = max(1, settings.bioverify_identify_concurrency)
    spoof_seen = False
    for start in range(0, len(rows), width):
        # Decrypt on THIS thread only: the Session is not thread-safe and every decrypt writes a
        # key event. Batching also bounds how many credential plaintexts exist at once (§14.1).
        pending = []
        for cred, subj in rows[start:start + width]:
            text = credential_vault.credential_text(db, credential=cred)
            if text:
                pending.append((cred, subj, text))
        if not pending:
            continue
        with ThreadPoolExecutor(max_workers=len(pending)) as pool:
            futures = {pool.submit(service.verify, image=image, qr_text=text): (cred, subj)
                       for cred, subj, text in pending}
            for future in as_completed(futures):
                cred, subj = futures[future]
                try:
                    result = future.result()
                except FaceEngineError:
                    metrics.incr("match_engine.candidate_error")  # one bad candidate, keep going
                    continue
                if result.allowed:
                    return subj, cred, result.band, True
                if not _liveness_from(result):
                    spoof_seen = True
    return None, None, "none", not spoof_seen


def identify_face(db: Session, *, tenant_id, device_id, zone_id, image, direction: str = "in") -> dict:
    """The guard walk-up flow: capture a face → recognise WHO it is (1:N) → authorize → record.
    No claim/ID needed. `direction` = 'in' (check-in) or 'out' (check-out)."""
    try:
        with metrics.timer("gate.identify_latency_ms"):
            if settings.credential_engine == "bioverify":
                subject, credential, band, liveness_passed = _identify_bioverify(
                    db, tenant_id=tenant_id, image=image)
            else:
                engine = _engine()
                live_vector = engine.embed(image=image)
                liveness_passed = engine.assess_liveness(image=image).passed
                subject, credential, score = _best_match(
                    db, live_vector=live_vector, tenant_id=tenant_id)
                band = ("high" if score >= 0.6 else "medium") if subject is not None else "none"
    except FaceEngineError:
        # engine unreachable — degrade gracefully so the guard falls back to a manual check
        metrics.incr("match_engine.unavailable")
        return {"matched": False, "decision": "deny",
                "reason": EntryReason.MATCH_ENGINE_UNAVAILABLE.value, "direction": direction,
                "attempt_id": None, "subject_id": None, "name": None, "confidence_band": "none"}
    if subject is None:
        reason = EntryReason.LIVENESS_FAILED if not liveness_passed else EntryReason.FACE_MISMATCH
    else:
        reason = authorization.evaluate(
            face_match_passed=True, liveness_passed=liveness_passed, subject=subject,
            credential=credential, consent_active=consent_active(db, subject.id))
    decision = "allow" if reason == EntryReason.ALLOWED else "deny"
    metrics.incr("gate.identify")
    if reason == EntryReason.FACE_MISMATCH:
        metrics.incr("gate.mismatch")
    attempt = EntryAttempt(
        tenant_id=tenant_id, tenant_subject_id=(subject.id if subject else None), device_id=device_id,
        zone_id=zone_id, match_result=("passed" if subject is not None else "failed"),
        liveness_result=("passed" if liveness_passed else "failed"), authorization_result=decision,
        reason_code=reason.value, confidence_band=band, model_version=settings.face_model_version,
        policy_version=settings.current_policy_version)
    db.add(attempt)
    db.flush()
    return {"matched": subject is not None, "decision": decision, "reason": reason.value,
            "direction": direction, "attempt_id": str(attempt.id),
            "subject_id": (str(subject.id) if subject else None),
            "name": ((subject.display_name or subject.external_reference) if subject else None),
            "confidence_band": band}


def record_attempt(db: Session, *, tenant_id, device_id, zone_id, subject_id,
                   reason: str, authorization_result: str, policy_version: str = "v1") -> EntryAttempt:
    """Record a minimal entry event for a manual/override/committed decision (§7.6)."""
    attempt = EntryAttempt(
        tenant_id=tenant_id, tenant_subject_id=subject_id, device_id=device_id, zone_id=zone_id,
        authorization_result=authorization_result, reason_code=reason,
        model_version=settings.face_model_version, policy_version=policy_version,
    )
    db.add(attempt)
    db.flush()
    return attempt
