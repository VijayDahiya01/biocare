"""Smoke-test the Sandbox (api.sandbox.co.in) government KYC provider.

Runs the SandboxGovernmentProvider directly against the live API, independent of the
FAKE_GOV_IDENTITY flag, so you can prove the wiring without routing the whole app through it.

Run as a module from biocore/backend:
    python -m scripts.gov_sandbox_check                 # auth handshake only (FREE)
    python -m scripts.gov_sandbox_check --pan ABCDE1234F --name "NAME" --dob 01/01/1990   # BILLED
    python -m scripts.gov_sandbox_check --aadhaar 123412341234        # sends a real OTP (BILLED)
    python -m scripts.gov_sandbox_check --aadhaar-verify <ref_id> <otp>                    # BILLED

Only --pan / --aadhaar* make billed calls; the default is the free authenticate handshake.
"""
import argparse
import sys

from app.adapters.gov_identity.sandbox import SandboxGovernmentProvider


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pan")
    ap.add_argument("--name", default="")
    ap.add_argument("--dob", default="")
    ap.add_argument("--aadhaar")
    ap.add_argument("--aadhaar-verify", nargs=2, metavar=("REF_ID", "OTP"))
    args = ap.parse_args()

    p = SandboxGovernmentProvider()
    print(f"base_url = {p._base}   api_version = {p._version}   key = {p._key[:12]}…")

    # 1) FREE auth handshake — proves creds + base URL + header contract.
    token = p.authenticate()
    print(f"[OK] authenticate -> JWT ({len(token)} chars, {token[:16]}…)")

    if args.pan:
        s = p.create_session(tenant_id="cli", subject_ref="cli", purpose="verify")
        res = p.fetch_verified_data(session=s, credential={
            "type": "pan", "pan": args.pan, "name": args.name, "dob": args.dob})
        print(f"[OK] PAN verify -> {res.claims}")

    if args.aadhaar:
        ref = p.aadhaar_okyc_send_otp(aadhaar_number=args.aadhaar)
        print(f"[OK] Aadhaar OKYC OTP sent -> reference_id={ref} "
              f"(re-run with: --aadhaar-verify {ref} <otp-you-received>)")

    if args.aadhaar_verify:
        ref_id, otp = args.aadhaar_verify
        s = p.create_session(tenant_id="cli", subject_ref="cli", purpose="verify")
        res = p.fetch_verified_data(session=s, credential={
            "type": "aadhaar_okyc", "reference_id": ref_id, "otp": otp})
        has_photo = res.government_photo is not None
        print(f"[OK] Aadhaar OKYC verify -> {res.claims}  (photo={'yes' if has_photo else 'no'})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
