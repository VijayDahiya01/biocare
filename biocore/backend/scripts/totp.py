"""Print a live 2FA code for an admin, straight from the database.

For when you have an account but the authenticator app was never set up — the secret is only
shown once, on the screen that created the account. This reads it back.

    .venv/Scripts/python.exe scripts/totp.py vijay@oolix.in
    .venv/Scripts/python.exe scripts/totp.py vijay@oolix.in --watch

DEV ONLY. It prints a second factor in the clear, which defeats the point of having one.
Never run it against a production database.
"""
import os
import sys
import time

import pyotp
from sqlalchemy import create_engine, text

# Work whether you run this as `scripts/totp.py` or `-m scripts.totp`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402


def lookup(email: str):
    engine = create_engine(settings.database_url)
    with engine.connect() as c:
        # The app role is subject to FORCE row-level security, and this lookup has no tenant
        # context yet — without the bypass the query returns nothing rather than an error.
        c.execute(text("SET app.bypass_rls = 'on'"))
        row = c.execute(text("""
            select u.email, u.role, u.totp_secret, t.name, t.org_code
            from users u join tenants t on t.id = u.tenant_id
            where lower(u.email) = lower(:e)
        """), {"e": email}).first()
    return row


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    email = args[0]
    watch = "--watch" in sys.argv

    row = lookup(email)
    if row is None:
        print(f"No user '{email}' in this database.")
        print(f"  (DATABASE_URL ends with: ...{settings.database_url.rsplit('/', 1)[-1]})")
        return 1
    _, role, secret, tenant, org_code = row
    if not secret:
        print(f"{email} has no 2FA secret set — nothing to generate.")
        return 1

    print(f"{email}  ·  {role}  ·  {tenant} ({org_code})")
    totp = pyotp.TOTP(secret)
    print("\nScan this once and you will not need this script again:")
    print(f"  {pyotp.TOTP(secret, name=email, issuer='BioCore').provisioning_uri()}\n")

    while True:
        left = 30 - int(time.time()) % 30
        print(f"  code {totp.now()}   valid {left:2d}s more", end="\r" if watch else "\n")
        if not watch:
            break
        time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
