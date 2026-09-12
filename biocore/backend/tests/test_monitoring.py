"""Monitoring metrics + alerts (§23, §22): DB-derived rates/counts, in-process counters,
and the alert rules. Integration test — skips if Postgres/Redis unreachable. FAKE_GOV_IDENTITY=true.
"""
import uuid

import pytest

from app.core import metrics
from app.core.db import SessionLocal, set_tenant_guc
from app.core.policy import ConsentPurpose, VerificationOutcome
from app.models import TenantSubject
from app.services import (
    credential_vault,
    entry_service,
    identity_proofing,
    monitoring_service,
)
from app.services.auth_service import provision_tenant

CONSENTS = [p.value for p in ConsentPurpose if p.value not in ("cross_tenant_reuse", "marketing")]


@pytest.fixture
def tenant(require_stack):
    db = SessionLocal()
    t = provision_tenant(db, name="MON", org_code=f"MON-{uuid.uuid4().hex[:8]}", vertical="office",
                         plan="starter", admin_email=f"mon_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="MON Admin")
    db.close()
    return t["tenant_id"]


def _subject_with_cred(db, tid, ref, tag):
    subj = TenantSubject(tenant_id=tid, external_reference=ref, subject_type="member")
    db.add(subj); db.flush()
    s = identity_proofing.start_session(db, tenant_id=tid, tenant_subject_id=subj.id, provider_label="fake")
    for p in CONSENTS:
        identity_proofing.record_consent(db, tenant_id=tid, tenant_subject_id=subj.id, purpose=p)
    identity_proofing.run_government_fetch(db, session=s, subject_ref=ref, credential={"reference": ref})
    identity_proofing.complete_verification(db, session=s, outcome=VerificationOutcome.VERIFIED)
    credential_vault.create_credential(
        db, tenant_id=tid, tenant_subject_id=subj.id, vector=entry_service._embed(tag),
        purpose=ConsentPurpose.ENTRY_AUTHENTICATION.value)
    db.flush()
    return subj


def test_metrics_reflect_activity(tenant):
    metrics.reset()
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj = _subject_with_cred(db, tenant, "MON-1", "face-A")
        entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None,
                                subject_id=subj.id, image="face-A")     # allow
        entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None,
                                subject_id=subj.id, image="intruder")   # mismatch
        db.flush()
        m = monitoring_service.collect_metrics(db, window_hours=24)
        assert m["verification"]["government_api_success_rate"] == 1.0   # fake gov fetch succeeded
        assert m["gate"]["attempts"] >= 2
        assert (m["gate"]["face_mismatch_rate"] or 0) > 0
        assert m["gate"]["match_latency_ms"]["count"] >= 2               # latency histogram populated
        db.commit()
    finally:
        db.close()


def test_mismatch_spike_alert(tenant):
    metrics.reset()
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        subj = _subject_with_cred(db, tenant, "MON-2", "face-B")
        for _ in range(12):  # all mismatches -> rate 1.0 over MIN_SAMPLE
            entry_service.run_entry(db, tenant_id=tenant, device_id=None, zone_id=None,
                                    subject_id=subj.id, image="intruder")
        db.flush()
        m = monitoring_service.collect_metrics(db, window_hours=24)
        alerts = {a["id"] for a in monitoring_service.evaluate_alerts(db, m)}
        assert "mismatch_spike" in alerts
        db.commit()
    finally:
        db.close()


def test_counter_driven_alerts(tenant):
    metrics.reset()
    db = SessionLocal(); set_tenant_guc(db, tenant)
    try:
        metrics.incr("device_trust.failure", 3)
        metrics.incr("kms.access_denied", 1)
        metrics.incr("tenant.isolation_violation", 1)
        m = monitoring_service.collect_metrics(db, window_hours=24)
        ids = {a["id"] for a in monitoring_service.evaluate_alerts(db, m)}
        assert {"device_trust_failures", "kms_access_denied", "tenant_isolation_violation"} <= ids
        db.commit()
    finally:
        db.close()
