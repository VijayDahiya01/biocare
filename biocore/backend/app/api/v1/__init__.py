from fastapi import APIRouter

from app.api.v1 import (
    admin_enroll,
    admin_tenants,
    alerts,
    attendance,
    auth,
    blacklist,
    breaks,
    connectors,
    device_trust,
    devices,
    documents,
    donations,
    dpdp,
    enrollment,
    entry,
    events,
    face_credentials,
    gps,
    grievances,
    health,
    hr,
    identity,
    integrations,
    invites,
    kiosk,
    leave,
    memberships,
    monitoring,
    notifications,
    offline,
    person,
    person_identity,
    privacy,
    reports,
    retention,
    roles,
    school,
    security,
    settings,
    users,
    visitors,
    zones,
)

router = APIRouter(prefix="/api/v1")

# Phase 0/1
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(admin_tenants.router)
router.include_router(enrollment.router)
router.include_router(devices.router)
router.include_router(kiosk.router)
router.include_router(attendance.router)
router.include_router(users.router)

# Phase 2
router.include_router(zones.router)
router.include_router(admin_enroll.router)
router.include_router(visitors.router)
router.include_router(dpdp.router)
router.include_router(blacklist.router)
router.include_router(alerts.router)
router.include_router(settings.router)

# Phase 3
router.include_router(hr.router)
router.include_router(breaks.router)
router.include_router(gps.router)
router.include_router(leave.router)
router.include_router(roles.router)
router.include_router(reports.router)
router.include_router(school.router)
router.include_router(memberships.router)
router.include_router(donations.router)
router.include_router(events.router)
router.include_router(integrations.router)
router.include_router(notifications.router)
router.include_router(security.router)
router.include_router(grievances.router)
router.include_router(documents.router)

# Person-centric app
router.include_router(person.router)
router.include_router(invites.router)
router.include_router(person_identity.router)

# Verified-identity & entry management (BIOCORE_COMPLETE_CHANGE_SPEC §10)
router.include_router(identity.router)
router.include_router(face_credentials.router)
router.include_router(privacy.router)
router.include_router(entry.router)
router.include_router(device_trust.router)
router.include_router(retention.router)
router.include_router(offline.router)
router.include_router(monitoring.router)
router.include_router(connectors.router)
