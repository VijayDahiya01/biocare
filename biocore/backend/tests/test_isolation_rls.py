"""Tenant isolation safety-net test.

Proves Row-Level Security blocks a cross-tenant read even when the application
query has NO explicit tenant_id filter (i.e. a developer forgot it). This is the
last line of defence required by the non-negotiables.
"""
import uuid

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal, set_tenant_guc
from app.services.auth_service import provision_tenant


@pytest.fixture
def two_tenants(require_stack):
    db = SessionLocal()
    a = provision_tenant(db, name="A", org_code=f"A-{uuid.uuid4().hex[:8]}",
                         vertical="office", plan="starter",
                         admin_email=f"a_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="A Admin")
    b = provision_tenant(db, name="B", org_code=f"B-{uuid.uuid4().hex[:8]}",
                         vertical="office", plan="starter",
                         admin_email=f"b_{uuid.uuid4().hex[:6]}@x.com",
                         admin_password="supersecret123", admin_name="B Admin")
    db.close()
    return a, b


def test_rls_blocks_unfiltered_cross_tenant_read(two_tenants):
    a, b = two_tenants
    db = SessionLocal()
    try:
        # Scope to tenant A, then run an UNFILTERED query (no WHERE tenant_id).
        set_tenant_guc(db, a["tenant_id"])
        rows = db.execute(text("SELECT tenant_id FROM users")).fetchall()
        seen = {str(r[0]) for r in rows}
        assert seen == {a["tenant_id"]}, "RLS must hide other tenants even without a filter"
        assert b["tenant_id"] not in seen
    finally:
        db.close()


def test_no_tenant_context_sees_nothing(two_tenants):
    db = SessionLocal()
    try:
        set_tenant_guc(db, None)  # no tenant bound
        rows = db.execute(text("SELECT id FROM users")).fetchall()
        assert rows == [], "With no tenant context, RLS must expose zero rows"
    finally:
        db.close()
