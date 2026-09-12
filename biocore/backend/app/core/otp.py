"""Email OTP for member registration + login. Stored in Redis with a TTL."""
import secrets

from app.core.redis_client import client, otp_key
from app.services.notifier import send_email

OTP_TTL_SECONDS = 600  # 10 minutes (acceptance criterion)


def request_otp(email: str) -> int:
    code = f"{secrets.randbelow(1_000_000):06d}"
    client.set(otp_key(email), code, ex=OTP_TTL_SECONDS)
    send_email(
        to=email,
        subject="Your BioCore verification code",
        body=f"Your one-time code is {code}. It expires in 10 minutes.",
    )
    return OTP_TTL_SECONDS


def verify_otp(email: str, code: str) -> bool:
    key = otp_key(email)
    stored = client.get(key)
    if not stored or stored != code:
        return False
    client.delete(key)  # single-use
    return True
