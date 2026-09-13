"""Email OTP for member registration + login. Stored in Redis with a TTL.

A six-digit code is only a million guesses. Left unlimited inside a ten-minute window that is
comfortably brute-forceable — a few thousand requests a second covers the space — and the prize
is somebody's account and every face credential in it. So a wrong guess has to cost something:
after MAX_ATTEMPTS the code is destroyed and a fresh one has to be requested.

Sending is limited too, for a different reason: without it, anyone can point the endpoint at a
stranger's inbox and flood it, at our expense.
"""
import secrets

from app.core.redis_client import client, otp_key, ratelimit_key
from app.services.notifier import send_email

OTP_TTL_SECONDS = 600       # 10 minutes (acceptance criterion)
MAX_ATTEMPTS = 5            # wrong guesses before the code is destroyed
MAX_SENDS = 5               # codes per address per window
SEND_WINDOW_SECONDS = 600


class OtpRateLimited(Exception):
    """Too many codes requested for one address."""


def _attempts_key(email: str) -> str:
    return ratelimit_key(f"otp-attempts:{email.lower()}")


def _sends_key(email: str) -> str:
    return ratelimit_key(f"otp-sends:{email.lower()}")


def request_otp(email: str) -> int:
    sends = client.incr(_sends_key(email))
    if sends == 1:
        client.expire(_sends_key(email), SEND_WINDOW_SECONDS)
    if sends > MAX_SENDS:
        raise OtpRateLimited("Too many codes requested for this address.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    client.set(otp_key(email), code, ex=OTP_TTL_SECONDS)
    client.delete(_attempts_key(email))      # a new code starts with a clean slate
    send_email(
        to=email,
        subject="Your BioCore verification code",
        body=f"Your one-time code is {code}. It expires in 10 minutes.",
    )
    return OTP_TTL_SECONDS


def verify_otp(email: str, code: str) -> bool:
    key = otp_key(email)
    stored = client.get(key)
    if not stored:
        return False

    if stored != code:
        attempts = client.incr(_attempts_key(email))
        if attempts == 1:
            # Live no longer than the code itself, so a stale counter cannot lock anyone out.
            client.expire(_attempts_key(email), OTP_TTL_SECONDS)
        if attempts >= MAX_ATTEMPTS:
            # Burn it. Guessing again now means starting from a code that does not exist yet.
            client.delete(key)
            client.delete(_attempts_key(email))
        return False

    client.delete(key)                       # single-use
    client.delete(_attempts_key(email))
    return True
