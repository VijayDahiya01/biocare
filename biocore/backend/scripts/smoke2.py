"""Smoke for the newly-added features (grievance + guardian) against the live server."""
import httpx

BASE = "http://127.0.0.1:8080/api/v1"
IMG = "data:image/jpeg;base64,Zm9vYmFy"



c = httpx.Client(base_url=BASE, timeout=10)
c.post("/auth/login", json={"email": "admin@acme.com", "password": "demopass123"})
csrf = {"X-CSRF-Token": c.cookies.get("csrf")}

# --- grievance (admin files one to exercise the endpoint, then resolves it) ---
g = c.post("/grievance", headers=csrf, json={"subject": "Test", "message": "Please review my data."}).json()["data"]
print("grievance filed ->", g["grievance_id"][:8], g["status"])
lst = c.get("/grievances").json()["data"]["items"]
print("grievances visible ->", len(lst))
res = c.post(f"/grievances/{g['grievance_id']}/resolve", headers=csrf, json={"resolution": "Handled."}).json()["data"]
print("grievance resolved ->", res["status"])

# --- guardian: student -> invite (token) -> enroll -> pickup verify ---
dev = c.post("/devices", headers=csrf, json={"name": "PICKUP-KIOSK"}).json()["data"]
student = c.post("/admin/enroll", headers=csrf, json={
    "person_type": "patient", "first_name": "Kid", "last_name": "Student", "purpose": "student",
    "image": IMG, "consent_method": "in_person_verbal",
    "person_present": True, "purpose_explained": True, "person_consented": True, "admin_responsible": True,
}).json()["data"]
inv = c.post("/guardians/invite", headers=csrf, json={
    "student_user_id": student["user_id"], "guardian_name": "Parent One",
    "guardian_email": "parent@acme.com", "relationship": "parent",
}).json()["data"]
print("guardian invited ->", inv["enroll_url"])
enr = c.post("/guardians/enroll", json={"token": inv["token"], "image": IMG}).json()["data"]
print("guardian enrolled ->", enr["status"])
pv = c.post("/pickup/verify", headers={"X-Device-Token": dev["pairing_token"]},
            json={"image": IMG, "student_id": student["user_id"]}).json()["data"]
print("pickup verify ->", "authorised" if pv["authorised"] else "DENIED", "(", pv.get("guardian_name"), ")")

print("\nSMOKE2 OK  (grievance file/list/resolve, guardian invite/enroll/pickup-verify)")
