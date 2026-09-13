"""Test fixtures. Integration tests that need Postgres+Redis skip automatically
when those stores are unreachable (e.g. running unit tests without the stack).
"""

# --- test environment isolation (must run before anything imports app.core.config) ---
# app/core/config.py uses SettingsConfigDict(env_file=".env"), so without this the
# developer's backend/.env leaks into the suite. Concretely, FACE_ENGINE=remote pointed
# the tests at a cloudflared tunnel and caused 13 spurious failures. Real environment
# variables take precedence over env_file in pydantic-settings, so setting them here wins.
#
# Set BIOCORE_TEST_USE_REAL_ENV=1 to opt out and test against whatever .env holds.
import os

if os.environ.get("BIOCORE_TEST_USE_REAL_ENV") != "1":
    os.environ.update({
        "FACE_ENGINE": "fake",
        "FAKE_ZEPIRIS": "true",
        "FAKE_REDIS": "true",
        "FAKE_GOV_IDENTITY": "true",
        "ENVIRONMENT": "development",
    })

import pytest



def _postgres_reachable() -> bool:
    try:
        from sqlalchemy import text

        from app.core.db import engine
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _redis_reachable() -> bool:
    try:
        from app.core.redis_client import client
        return bool(client.ping())
    except Exception:
        return False


@pytest.fixture(scope="session")
def stack_available() -> bool:
    return _postgres_reachable() and _redis_reachable()


@pytest.fixture
def require_stack(stack_available):
    if not stack_available:
        pytest.skip("Postgres/Redis not reachable — bring the stack up to run integration tests.")
