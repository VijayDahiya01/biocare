"""Password hashing and token generation."""
import hmac
import secrets
from hashlib import sha256

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)



# --- tokens ---
def new_token(prefix: str = "") -> str:
    token = secrets.token_urlsafe(32)
    return f"{prefix}{token}" if prefix else token


def hash_token(token: str) -> str:
    """Store device/pairing tokens hashed, never raw."""
    return sha256(token.encode()).hexdigest()


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
