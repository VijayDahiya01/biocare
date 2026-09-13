"""Phase 3 endpoint coverage (integration, real Postgres).

One authenticated-admin flow that exercises the happy path of every Phase 3
module so they're no longer untested. ZepIris face ops are mocked (respx).
"""
import base64
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import settings

Z = settings.zepiris_url.rstrip("/")
IMG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xd9img").decode()


@pytest.fixture
def admin(require_stack):
    from app.main import app
    tc = TestClient(app)
    org = f"P3-{uuid.uuid4().hex[:8]}"
    email = f"admin_{uuid.uuid4().hex[:6]}@acme.com"
    r = tc.post("/api/v1/admin/tenants", json={
        "name": "P3", "org_code": org, "vertical": "office",
        "admin_email": email, "admin_password": "supersecret123"})
    tc.post("/api/v1/auth/login", json={"email": email, "password": "supersecret123"})
    tc.headers.update({"X-CSRF-Token": tc.cookies.get("csrf")})
    return tc, org


def _ok(r):
    assert r.status_code in (200, 201), f"{r.request.url} -> {r.status_code} {r.text}"
    return r.json()["data"]


@respx.mock
def test_phase3_happy_paths(admin):
    c, org = admin
    respx.post(f"{Z}/v1/faces/insert").mock(return_value=httpx.Response(200, json={
        "requestId": "r", "imageQualityAssessment": {"passed": True, "spoof": {"is_spoof": False}},
        "userOperationResult": {"status": "success"}}))

    # a worker to attach wage/membership/donation to
    worker = _ok(c.post("/api/v1/admin/enroll", json={
        "person_type": "patient", "first_name": "Worker", "last_name": "One", "purpose": "t",
        "image": IMG, "consent_method": "in_person_verbal", "person_present": True,
        "purpose_explained": True, "person_consented": True, "admin_responsible": True}))
    uid = worker["user_id"]

    # HR / wages / payroll
    _ok(c.post("/api/v1/wage-config", json={"user_id": uid, "rate_per_hour": 120,
               "overtime_multiplier": 1.5, "effective_from": "2026-06-01"}))
    assert "history" in _ok(c.get(f"/api/v1/wage-config/{uid}"))
    _ok(c.get("/api/v1/payroll/calculate?from=2026-06-01&to=2026-06-30"))
    assert "headcount" in _ok(c.get("/api/v1/hr/summary"))

    # leave
    lv = _ok(c.post("/api/v1/leave", json={"type": "casual", "from": "2026-07-01", "to": "2026-07-02"}))
    _ok(c.get("/api/v1/leave"))
    _ok(c.post(f"/api/v1/leave/{lv['leave_id']}/approve", json={"note": "ok"}))
    _ok(c.get(f"/api/v1/leave/balance/{uid}"))

    # roles
    _ok(c.get("/api/v1/roles"))
    _ok(c.get("/api/v1/permissions"))
    role = _ok(c.post("/api/v1/roles", json={"name": f"Custom {uuid.uuid4().hex[:4]}",
               "permissions": ["attendance.view"], "scope": {}}))
    _ok(c.delete(f"/api/v1/roles/{role['role_id']}"))

    # reports
    for rep in ("attendance", "late", "footfall"):
        _ok(c.get(f"/api/v1/reports/{rep}?from=2026-06-01&to=2026-06-30"))
    _ok(c.get("/api/v1/reports/absent?on=2026-06-15"))

    # zones + badges + assign
    zone = _ok(c.post("/api/v1/zones", json={"name": "Floor A", "type": "restricted", "access_rule": {}}))
    badge = _ok(c.post("/api/v1/badges", json={"name": "Crew", "zones": [zone["zone_id"]]}))
    _ok(c.post("/api/v1/badges/assign", json={"user_id": uid, "badge_id": badge["badge_id"]}))

    # membership + donation (donation generates a real PDF)
    _ok(c.post("/api/v1/memberships", json={"user_id": uid, "plan_type": "monthly", "start_date": "2026-06-01"}))
    _ok(c.get("/api/v1/memberships/expiring?days=60"))
    don = _ok(c.post("/api/v1/donations", json={"donor_user_id": uid, "amount": 500, "purpose": "general"}))
    assert don["receipt_url"].startswith("/api/v1/documents/receipts/")

    # events: create + CSV import + footfall
    ev = _ok(c.post("/api/v1/events", json={"name": "Conf"}))
    csv_bytes = b"first_name,last_name,email\nDel,Egate,del@acme.com\n"
    imp = _ok(c.post("/api/v1/events/import", data={"event_id": ev["event_id"]},
                     files={"file": ("d.csv", csv_bytes, "text/csv")}))
    assert imp["created"] == 1
    _ok(c.get(f"/api/v1/events/{ev['event_id']}/footfall"))

    # geofences + emergency (muster generates a real PDF)
    _ok(c.post("/api/v1/geofences", json={"name": "HQ", "center_lat": 28.7, "center_lng": 77.1, "radius_km": 1}))
    _ok(c.get("/api/v1/geofences"))
    mus = _ok(c.post("/api/v1/emergency/trigger", json={}))
    assert mus["muster_report_url"].startswith("/api/v1/documents/musters/")
    _ok(c.get("/api/v1/emergency/status"))

    # timetable + session attendance
    tt = _ok(c.post("/api/v1/timetable", json={"class_id": "9A", "subject": "Math",
             "day_of_week": 0, "start_time": "09:00", "end_time": "10:00"}))
    _ok(c.get(f"/api/v1/attendance/session?session_id={tt['session_id']}"))

    # grievance lifecycle
    g = _ok(c.post("/api/v1/grievance", json={"subject": "x", "message": "concern about data"}))
    _ok(c.get("/api/v1/grievances"))
    _ok(c.post(f"/api/v1/grievances/{g['grievance_id']}/resolve", json={"resolution": "done"}))

    # security analytics
    _ok(c.get(f"/api/v1/security/movement?user_id={uid}&from=2026-06-01&to=2026-06-30"))
    _ok(c.get("/api/v1/security/ppe-violations?from=2026-06-01&to=2026-06-30"))

    # settings + webhooks + alerts
    _ok(c.get("/api/v1/settings"))
    _ok(c.patch("/api/v1/settings", json={"match_threshold": 0.6}))
    hook = _ok(c.post("/api/v1/settings/webhooks", json={"event": "attendance.recorded",
               "url": "https://x.example/hook", "secret": "s"}))
    _ok(c.get("/api/v1/settings/webhooks"))
    _ok(c.delete(f"/api/v1/settings/webhooks/{hook['id']}"))
    _ok(c.get("/api/v1/alerts"))
    _ok(c.patch("/api/v1/alerts/settings", json={"late_threshold": "09:30"}))

    # visitor invite
    inv = _ok(c.post("/api/v1/visitors/invite", json={"visitor_name": "Guest", "valid_hours": 4}))
    assert inv["token"]
