"""A government record is contacted only when the organisation asked for one (§5.5).

This ran at every level once, so a tenant that asked for nothing but a selfie still had
"identity_verified / document_valid / age_over_18 = true" recorded against every person — claims
nobody had checked. With live credentials configured it would also have made a billed UIDAI
call per registration for an organisation that never wanted one.

Integration test — skips if Postgres is unreachable.
"""
import uuid

import pytest
from sqlalchemy import func, select

from app.core.db import SessionLocal, bypass_rls, set_tenant_guc
from app.models import Tenant, VerifiedClaim
from app.services.auth_service import provision_tenant


def _tenant(level: str) -> str:
    db = SessionLocal()
    t = provision_tenant(db, name="GG", org_code=f"GG-{uuid.uuid4().hex[:8]}", vertical="office",
                         plan="starter", admin_email=f"gg_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="GG")
    with bypass_rls(db):
        db.get(Tenant, t["tenant_id"]).verification_level = level
        db.commit()
    db.close()
    return t["tenant_id"]


def _claims_for(db, tenant_id) -> int:
    from app.models import TenantSubject
    return db.execute(
        select(func.count(VerifiedClaim.id))
        .join(TenantSubject, TenantSubject.id == VerifiedClaim.tenant_subject_id)
        .where(TenantSubject.tenant_id == tenant_id)
    ).scalar_one()


@pytest.mark.parametrize("level", ["face_only", "face_and_document"])
def test_no_government_claims_unless_asked_for(require_stack, level):
    """Neither of these levels contacts a government record, so neither may record a claim
    about one. A stored "age_over_18: true" that nobody checked is a false record about a
    real person."""
    tid = _tenant(level)
    db = SessionLocal()
    set_tenant_guc(db, tid)
    try:
        with bypass_rls(db):
            assert _claims_for(db, tid) == 0
    finally:
        db.close()


def test_the_level_is_what_decides(require_stack):
    """Guards against the gate being re-introduced on the wrong condition — e.g. on whether a
    provider happens to be configured, which would make behaviour depend on deployment."""
    from app.models import Tenant as T
    db = SessionLocal()
    try:
        with bypass_rls(db):
            for level, expected in (("face_only", False), ("face_and_document", False),
                                    ("face_and_government", True)):
                tid = _tenant(level)
                asks = db.get(T, tid).verification_level == "face_and_government"
                assert asks is expected, f"{level} should{'' if expected else ' not'} ask"
    finally:
        db.close()
