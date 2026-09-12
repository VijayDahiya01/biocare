"""Monitoring metrics + alerts (BIOCORE_COMPLETE_CHANGE_SPEC §23).

Combines DB-derived rates/counts (tenant-scoped by the RLS session) with the in-process
metrics registry (operational counters/latencies) into the §23 metric set, then evaluates the
§23 alert rules. Read-only: computes over what is already persisted, mutates nothing.

Process counters (gov API, KMS, gate latency, device trust) are per-process/operational and
not tenant-scoped; DB metrics are tenant-scoped. Production would export these to Prometheus.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import metrics
from app.models import (
    ConsentReceipt,
    DeviceCertificate,
    DeviceRequestNonce,
    EntryAttempt,
    ErasureJob,
    FaceCredential,
    IdentityVerificationSession,
    OfflineRoster,
)

# --- §23 alert thresholds (sane defaults; tune per deployment) ---
MISMATCH_RATE_ALERT = 0.5
LIVENESS_FAILURE_RATE_ALERT = 0.5
REPEATED_DEVICE_REQUESTS = 100          # signed requests per device within the window
ERASURE_MAX_PENDING_HOURS = 24
MIN_SAMPLE = 10                         # don't fire rate alerts below this many samples

# process counters that, if non-zero, are themselves alerts (detection wired elsewhere)
_COUNTER_ALERTS = {
    "kms.access_denied": ("kms_access_denied", "high", "KMS access denied."),
    "gov_api.leakage": ("gov_api_leakage_detected", "critical", "Government API response leakage detected."),
    "tenant.isolation_violation": ("tenant_isolation_violation", "critical", "Tenant-isolation violation detected."),
    "match_engine.unavailable": ("matching_unavailable", "high", "Matching service unavailable."),
}


def _count(db: Session, model, *where) -> int:
    q = select(func.count()).select_from(model)
    for w in where:
        q = q.where(w)
    return int(db.execute(q).scalar_one())


def _ratio(num: int, den: int) -> float | None:
    return (num / den) if den else None


def collect_metrics(db: Session, *, window_hours: int = 24) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    # --- verification (§5) ---
    sessions_total = _count(db, IdentityVerificationSession)
    sessions_verified = _count(db, IdentityVerificationSession,
                               IdentityVerificationSession.status == "verified")
    sessions_completed = _count(db, IdentityVerificationSession,
                                IdentityVerificationSession.completed_at.isnot(None))

    # --- entry attempts (windowed) ---
    att_total = _count(db, EntryAttempt, EntryAttempt.created_at >= since)
    att_mismatch = _count(db, EntryAttempt, EntryAttempt.created_at >= since,
                          EntryAttempt.reason_code == "FACE_MISMATCH")
    att_liveness = _count(db, EntryAttempt, EntryAttempt.created_at >= since,
                          EntryAttempt.liveness_result == "failed")
    att_quality = _count(db, EntryAttempt, EntryAttempt.created_at >= since,
                         EntryAttempt.reason_code == "QUALITY_FAILED")
    att_override = _count(db, EntryAttempt, EntryAttempt.created_at >= since,
                          EntryAttempt.authorization_result == "override")
    att_offline = _count(db, EntryAttempt, EntryAttempt.created_at >= since,
                         EntryAttempt.captured_offline.is_(True))

    # --- lifecycle ---
    templates_expired = _count(db, FaceCredential, FaceCredential.status == "expired")
    consent_withdrawn = _count(db, ConsentReceipt, ConsentReceipt.withdrawn_at.isnot(None))
    completed = db.execute(select(ErasureJob).where(ErasureJob.status == "completed")).scalars().all()
    durations = [(j.completed_at - j.created_at).total_seconds()
                 for j in completed if j.completed_at and j.created_at]
    erasure_avg = (sum(durations) / len(durations)) if durations else None
    erasure_pending = _count(db, ErasureJob, ErasureJob.status == "pending")
    offline_backlog = _count(db, OfflineRoster, OfflineRoster.status == "active")

    proc = metrics.snapshot()
    counters, hist = proc["counters"], proc["histograms"]

    return {
        "window_hours": window_hours,
        "verification": {
            "sessions_total": sessions_total,
            "verified": sessions_verified,
            "completion_rate": _ratio(sessions_completed, sessions_total),
            "government_api_success_rate": metrics.rate("gov_api.success", "gov_api.failure"),
        },
        "gate": {
            "attempts": att_total,
            "face_mismatch_rate": _ratio(att_mismatch, att_total),
            "liveness_failure_rate": _ratio(att_liveness, att_total),
            "quality_retry_rate": _ratio(att_quality, att_total),
            "manual_override_rate": _ratio(att_override, att_total),
            "match_latency_ms": hist.get("gate.match_latency_ms", {}),
            "offline_synced": att_offline,
        },
        "crypto": {
            "kms_latency_ms": hist.get("kms.unwrap_latency_ms", {}),
            "decrypt_failures": counters.get("kms.decrypt_failure", 0),
        },
        "device": {"trust_failures": counters.get("device_trust.failure", 0)},
        "lifecycle": {
            "templates_expired": templates_expired,
            "consent_withdrawals": consent_withdrawn,
            "erasure_avg_completion_seconds": erasure_avg,
            "erasure_pending": erasure_pending,
            "offline_sync_backlog": offline_backlog,
        },
        "process": {"uptime_seconds": proc["uptime_seconds"], "counters": counters},
    }


def evaluate_alerts(db: Session, m: dict) -> list[dict]:
    """Apply the §23 alert rules to a metrics snapshot; return only the firing alerts."""
    alerts: list[dict] = []

    def fire(alert_id: str, severity: str, detail: str, value=None, threshold=None) -> None:
        alerts.append({"id": alert_id, "severity": severity, "detail": detail,
                       "value": value, "threshold": threshold})

    gate = m["gate"]
    if gate["attempts"] >= MIN_SAMPLE and (gate["face_mismatch_rate"] or 0) > MISMATCH_RATE_ALERT:
        fire("mismatch_spike", "high", "Sudden spike in face mismatches.",
             round(gate["face_mismatch_rate"], 3), MISMATCH_RATE_ALERT)
    if gate["attempts"] >= MIN_SAMPLE and (gate["liveness_failure_rate"] or 0) > LIVENESS_FAILURE_RATE_ALERT:
        fire("liveness_spike", "high", "Sudden spike in liveness failures.",
             round(gate["liveness_failure_rate"], 3), LIVENESS_FAILURE_RATE_ALERT)

    # repeated requests from one device (signed-request nonce volume in the window)
    since = datetime.now(timezone.utc) - timedelta(hours=m["window_hours"])
    for device_id, cnt in db.execute(
        select(DeviceRequestNonce.device_id, func.count())
        .where(DeviceRequestNonce.seen_at >= since)
        .group_by(DeviceRequestNonce.device_id)
    ).all():
        if cnt >= REPEATED_DEVICE_REQUESTS:
            fire("repeated_device_requests", "medium",
                 f"Device {device_id} made {int(cnt)} requests in window.", int(cnt),
                 REPEATED_DEVICE_REQUESTS)

    now = datetime.now(timezone.utc)
    expired_certs = _count(db, DeviceCertificate, DeviceCertificate.revoked_at.is_(None),
                           DeviceCertificate.expires_at.isnot(None), DeviceCertificate.expires_at < now)
    if expired_certs:
        fire("device_cert_expired", "medium",
             f"{expired_certs} active device certificate(s) expired.", expired_certs, 0)

    if m["crypto"]["decrypt_failures"]:
        fire("decrypt_failures", "high", "Template decrypt failures observed.",
             m["crypto"]["decrypt_failures"], 0)
    if m["device"]["trust_failures"]:
        fire("device_trust_failures", "medium", "Device trust verification failures observed.",
             m["device"]["trust_failures"], 0)

    delayed = _count(db, ErasureJob, ErasureJob.status == "pending",
                     ErasureJob.created_at < now - timedelta(hours=ERASURE_MAX_PENDING_HOURS))
    if delayed:
        fire("erasure_delayed", "high", f"{delayed} erasure job(s) pending beyond SLA.",
             delayed, ERASURE_MAX_PENDING_HOURS)

    counters = m["process"]["counters"]
    for counter, (alert_id, severity, detail) in _COUNTER_ALERTS.items():
        if counters.get(counter, 0):
            fire(alert_id, severity, detail, counters[counter], 0)

    return alerts
