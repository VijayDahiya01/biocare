"""Database engine + session, with RLS tenant binding that survives mid-request
commits and connection pooling.

Tenant isolation is enforced two ways:
  1. App layer always filters by tenant_id (services).
  2. Postgres Row-Level Security as a safety net, reading the current tenant from
     the `app.tenant_id` GUC.

The tenant (and an explicit `bypass_rls` flag) are stored on `session.info` — the
SAME Session object the dependency yields to the endpoint. An `after_begin`
listener re-applies them as transaction-local (`SET LOCAL`) settings at the START
of every transaction, so even when a service commits and a later statement (e.g.
the audit insert) opens a fresh transaction, the GUC is restored automatically.
Because the values are transaction-local, nothing leaks onto pooled connections.
"""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=20,          # the face-search path is connection-heavy under load
    max_overflow=20,       # burst headroom; scale workers/replicas for true peak
    pool_timeout=10,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@event.listens_for(SessionLocal, "after_begin")
def _apply_rls_guc(session: Session, transaction, connection) -> None:
    """Bind the RLS settings for every new transaction (transaction-local)."""
    tid = session.info.get("tenant_id")
    bypass = session.info.get("bypass", False)
    connection.execute(
        text("SELECT set_config('app.tenant_id', :t, true), "
             "       set_config('app.bypass_rls', :b, true)"),
        {"t": str(tid) if tid else "", "b": "on" if bypass else "off"},
    )


def set_tenant_guc(db: Session, tenant_id: str | None) -> None:
    """Bind the RLS tenant for the rest of this session. None clears it."""
    db.info["tenant_id"] = str(tenant_id) if tenant_id else None
    if db.in_transaction():  # also apply to an already-open transaction
        db.execute(text("SELECT set_config('app.tenant_id', :t, true)"),
                   {"t": str(tenant_id) if tenant_id else ""})


@contextmanager
def bypass_rls(db: Session) -> Iterator[Session]:
    """Explicitly opt a narrow operation out of RLS — ONLY for legitimate
    cross-tenant work: login lookup (no tenant known yet), tenant provisioning,
    and super-admin reads. Every call site is a deliberate, auditable exception."""
    prev = db.info.get("bypass", False)
    db.info["bypass"] = True
    if db.in_transaction():
        db.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
    try:
        yield db
    finally:
        db.info["bypass"] = prev
        if db.in_transaction():
            db.execute(text("SELECT set_config('app.bypass_rls', :b, true)"),
                       {"b": "on" if prev else "off"})


def get_db() -> Iterator[Session]:
    """FastAPI dependency. Tenant GUC is set by the auth dependency, not here."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
