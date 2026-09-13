"""Seed a demo tenant + admin so you can log in immediately.

    python -m scripts.seed_demo

Prints the admin credentials. Safe to re-run (it reuses
the demo tenant if it already exists).
"""

from sqlalchemy import select

from app.core.db import SessionLocal, bypass_rls
from app.models import Tenant
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
            print(f"Demo tenant already exists (org_code={ORG}).")
        else:
            provision_tenant(
                db, name="Demo Co", org_code=ORG, vertical="office", plan="business",
                admin_email=EMAIL, admin_password=PASSWORD, admin_name="Demo Admin",
            )
            print("Created demo tenant + admin.")

        print("\n--- Sign in at /admin/login ---")
        print(f"  org code : {ORG}")
        print(f"  email    : {EMAIL}")
        print(f"  password : {PASSWORD}")
        print("\nMembers self-register at /register using the org code above.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
