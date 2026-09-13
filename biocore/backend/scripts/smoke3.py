"""Smoke for PDF generation (erasure cert, 80G receipt) against the live server."""
import httpx

BASE = "http://127.0.0.1:8080/api/v1"
IMG = "data:image/jpeg;base64,Zm9vYmFy"



def is_pdf(c: httpx.Client, url: str) -> tuple[bool, int, str]:
    r = c.get(url.replace("/api/v1", ""))  # client base_url already has /api/v1
    return (r.content[:4] == b"%PDF", len(r.content), r.headers.get("content-type", ""))


c = httpx.Client(base_url=BASE, timeout=10)
c.post("/auth/login", json={"email": "admin@acme.com", "password": "demopass123"})
csrf = {"X-CSRF-Token": c.cookies.get("csrf")}

# --- donation -> 80G receipt PDF ---
donor = c.post("/admin/enroll", headers=csrf, json={
    "person_type": "devotee", "first_name": "Generous", "last_name": "Donor", "purpose": "donation",
    "image": IMG, "consent_method": "in_person_verbal",
    "person_present": True, "purpose_explained": True, "person_consented": True, "admin_responsible": True,
}).json()["data"]
dn = c.post("/donations", headers=csrf, json={
    "donor_user_id": donor["user_id"], "amount": 5000, "purpose": "general",
}).json()["data"]
ok, size, ct = is_pdf(c, dn["receipt_url"])
print(f"80G receipt -> url={dn['receipt_url']}  pdf={ok} bytes={size} type={ct}")

# --- erasure -> certificate PDF (admin DELETE path; same erase_user cascade) ---
victim = c.post("/admin/enroll", headers=csrf, json={
    "person_type": "patient", "first_name": "ToErase", "last_name": "Person", "purpose": "test",
    "image": IMG, "consent_method": "in_person_verbal",
    "person_present": True, "purpose_explained": True, "person_consented": True, "admin_responsible": True,
}).json()["data"]
er = c.request("DELETE", f"/users/{victim['user_id']}", headers=csrf).json()["data"]
ok2, size2, ct2 = is_pdf(c, er["certificate_url"])
print(f"erasure cert -> ref={er['erasure_ref']} url={er['certificate_url']}  pdf={ok2} bytes={size2} type={ct2}")

print("\nSMOKE3 OK" if (ok and ok2) else "\nSMOKE3 FAILED")
