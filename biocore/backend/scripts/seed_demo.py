"""Seed a demo tenant + admin so you can log in immediately.

    python -m scripts.seed_demo

Prints the admin credentials and a current 2FA code. Safe to re-run (it reuses
the demo tenant if it already exists).
"""
from urllib.parse import parse_qs, urlparse

import pyotp
from sqlalchemy import select

from app.core.db import SessionLocal, bypass_rls
from app.models import Tenant, User
from app.services.auth_service import provision_tenant

ORG = "DEMO-2026"
EMAIL = "admin@acme.com"
PASSWORD = "demopass123"


def main() -> None:
    db = SessionLocal()
    try:
        existing = None
        with bypass_rls(db):
            existing = db.execute(select(Tenant).where(Tenant.org_code == ORG)).scalar_one_or_none()

        if existing:
            with bypass_rls(db):
                admin = db.execute(
                    select(User).where(User.tenant_id == existing.id, User.email == EMAIL)
                ).scalar_one_or_none()
            secret = admin.totp_secret if admin else None
            print(f"Demo tenant already exists (org_code={ORG}).")
        else:
            res = provision_tenant(
                db, name="Demo Co", org_code=ORG, vertical="office", plan="business",
                admin_email=EMAIL, admin_password=PASSWORD, admin_name="Demo Admin",
            )
            secret = parse_qs(urlparse(res["totp_provisioning_uri"]).query)["secret"][0]
            print("Created demo tenant + admin.")

        print("\n--- Sign in at /admin/login ---")
        print(f"  org code : {ORG}")
        print(f"  email    : {EMAIL}")
        print(f"  password : {PASSWORD}")
        if secret:
            print(f"  2FA secret (add to your authenticator): {secret}")
            print(f"  2FA code right now: {pyotp.TOTP(secret).now()}")
        print("\nMembers self-register at /register using the org code above.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
