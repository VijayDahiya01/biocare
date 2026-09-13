"""A six-digit code must not be guessable (app/core/otp.py).

A million combinations inside a ten-minute window is comfortably brute-forceable at a few
thousand requests a second, and the prize is somebody's account and every face credential in
it. Wrong guesses have to cost something.
"""
import pytest

from app.core import otp as otp_mod
from app.core.otp import MAX_ATTEMPTS, MAX_SENDS, OtpRateLimited, request_otp, verify_otp
from app.core.redis_client import client, otp_key


@pytest.fixture
def email():
    addr = "bruteforce-probe@mailbox.co.in"
    for k in (otp_key(addr), otp_mod._attempts_key(addr), otp_mod._sends_key(addr)):
        client.delete(k)
    yield addr
    for k in (otp_key(addr), otp_mod._attempts_key(addr), otp_mod._sends_key(addr)):
        client.delete(k)


def test_guessing_destroys_the_code(email):
    request_otp(email)
    real = client.get(otp_key(email))

    for _ in range(MAX_ATTEMPTS):
        assert verify_otp(email, "000000") is False

    # Even the CORRECT code no longer works: the attacker burned it, and a genuine person
    # simply asks for a new one.
    assert verify_otp(email, real) is False
    assert client.get(otp_key(email)) is None


def test_a_few_wrong_guesses_do_not_lock_out_an_honest_person(email):
    """Fat fingers must not cost someone their sign-in."""
    request_otp(email)
    real = client.get(otp_key(email))
    for _ in range(MAX_ATTEMPTS - 1):
        assert verify_otp(email, "111111") is False
    assert verify_otp(email, real) is True


def test_a_fresh_code_clears_the_count(email):
    """Otherwise a persistent attacker could lock a person out for as long as they liked."""
    request_otp(email)
    for _ in range(MAX_ATTEMPTS - 1):
        verify_otp(email, "222222")
    request_otp(email)
    real = client.get(otp_key(email))
    for _ in range(MAX_ATTEMPTS - 1):
        assert verify_otp(email, "333333") is False
    assert verify_otp(email, real) is True


def test_sending_is_limited_so_an_inbox_cannot_be_flooded(email):
    """Unlimited sends let anyone point this at a stranger's inbox, at our expense."""
    for _ in range(MAX_SENDS):
        request_otp(email)
    with pytest.raises(OtpRateLimited):
        request_otp(email)


def test_the_code_is_still_single_use(email):
    request_otp(email)
    real = client.get(otp_key(email))
    assert verify_otp(email, real) is True
    assert verify_otp(email, real) is False
