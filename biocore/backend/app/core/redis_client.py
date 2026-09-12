"""Redis client + key helpers (sessions, CSRF, OTP, rate limit, presence)."""
import redis

from app.core.config import settings

if settings.fake_redis:
    # In-memory Redis for local testing — only Postgres is then required to run.
    import fakeredis

    client = fakeredis.FakeRedis(decode_responses=True)
else:
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


# --- key patterns (mirror Doc 3 §5.3) ---
def session_key(session_id: str) -> str:
    return f"session:{session_id}"


def csrf_key(session_id: str) -> str:
    return f"csrf:{session_id}"


def otp_key(email: str) -> str:
    return f"otp:{email.lower()}"


def ratelimit_key(scope: str) -> str:
    return f"ratelimit:{scope}"


def presence_key(tenant_id: str) -> str:
    return f"presence:{tenant_id}"


def guardian_invite_key(token: str) -> str:
    return f"guardian_invite:{token}"
