"""Sandbox (api.sandbox.co.in) government KYC provider — REAL vendor API (§19.1).

Implements GovernmentIdentityProvider against Sandbox's KYC endpoints:
  * PAN verification (single-shot)          -> minimal claims, no photo.
  * Aadhaar paperless offline eKYC (OKYC)   -> OTP to the registered mobile, then verify ->
                                               minimal claims + a TEMPORARY government photo.

Only allowlisted minimal claims are returned to the caller. The raw vendor response, the
plain PAN/Aadhaar number and the government photo are TEMPORARY (§5.5, §5.10, §14.1): the
Identity Proofing Service deletes them once the transaction completes. This adapter never
persists or logs them.

Auth: exchange api key + secret for a short-lived JWT via /authenticate, cached in memory.
Secrets come from settings/env only (SANDBOX_API_KEY / SANDBOX_API_SECRET) — never hardcoded.
"""
from __future__ import annotations

import base64
import hashlib
import time
import uuid
from datetime import date, datetime

import httpx

from app.adapters.gov_identity.base import (
    GovernmentIdentityError,
    GovResult,
    GovSession,
    VerifiedClaims,
)
from app.core.config import settings
from app.core.name_match import compare_names


def _age_over_18(dob: str | None) -> bool:
    if not dob:
        return False
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y"):
        try:
            d = datetime.strptime(dob.strip(), fmt).date()
            break
        except ValueError:
            continue
    else:
        return False
    today = date.today()
    years = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    return years >= 18


class SandboxGovernmentProvider:
    provider = "sandbox"

    def __init__(self) -> None:
        if not settings.sandbox_api_key or not settings.sandbox_api_secret:
            raise GovernmentIdentityError(
                "SANDBOX_API_KEY / SANDBOX_API_SECRET are not set — cannot use the Sandbox "
                "government provider.", category="system_error")
        self._base = settings.sandbox_base_url.rstrip("/")
        self._key = settings.sandbox_api_key
        self._secret = settings.sandbox_api_secret
        self._version = settings.sandbox_api_version
        self._token: str | None = None
        self._token_exp: float = 0.0

    # --- auth -------------------------------------------------------------
    def authenticate(self) -> str:
        """Exchange key+secret for a JWT; cached (~24h) and refreshed conservatively."""
        now = time.time()
        if self._token and now < self._token_exp:
            return self._token
        try:
            r = httpx.post(
                f"{self._base}/authenticate",
                headers={
                    "x-api-key": self._key,
                    "x-api-secret": self._secret,
                    "x-api-version": self._version,
                },
                timeout=20.0,
            )
        except httpx.HTTPError as e:
            raise GovernmentIdentityError(f"Sandbox authenticate failed: {e}", "system_error")
        if r.status_code != 200:
            raise GovernmentIdentityError(
                f"Sandbox authenticate HTTP {r.status_code}: {r.text[:200]}", "system_error")
        data = r.json()
        token = data.get("access_token") or (data.get("data") or {}).get("access_token")
        if not token:
            raise GovernmentIdentityError("Sandbox authenticate: no access_token in response",
                                          "system_error")
        self._token = token
        self._token_exp = now + 23 * 3600  # JWTs last ~24h; refresh with a margin
        return token

    def _headers(self) -> dict:
        return {
            "Authorization": self.authenticate(),
            "x-api-key": self._key,
            "x-api-version": self._version,
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: dict) -> dict:
        try:
            r = httpx.post(f"{self._base}{path}", headers=self._headers(), json=body, timeout=30.0)
        except httpx.HTTPError as e:
            raise GovernmentIdentityError(f"Sandbox {path} failed: {e}", "system_error")
        if r.status_code in (401, 403):
            raise GovernmentIdentityError(f"Sandbox {path} auth error {r.status_code}", "authorization")
        if r.status_code >= 400:
            raise GovernmentIdentityError(
                f"Sandbox {path} HTTP {r.status_code}: {r.text[:200]}", "provider_error")
        payload = r.json()
        # Sandbox wraps results under `data` with a top-level `transaction_id`; surface the
        # transaction_id into the data dict for audit traceability, tolerating a flat response.
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if isinstance(data, dict) and payload.get("transaction_id") and "transaction_id" not in data:
            data["transaction_id"] = payload["transaction_id"]
        return data

    # --- protocol (§19.1) -------------------------------------------------
    def create_session(self, *, tenant_id, subject_ref, purpose) -> GovSession:
        # Sandbox is stateless per call; a local ref correlates the txn in our audit trail.
        return GovSession(provider=self.provider, session_ref=str(uuid.uuid4()))

    def fetch_verified_data(self, *, session: GovSession, credential: dict) -> GovResult:
        """Orchestrate the §19.1 flow: call provider → validate → extract claims + photo."""
        ctype = (credential.get("type") or "pan").lower()
        if ctype == "pan":
            raw = self._post("/kyc/pan/verify", self._pan_body(credential))
            raw["_type"] = "pan"
        elif ctype in ("aadhaar_okyc", "aadhaar"):
            raw = self._post("/kyc/aadhaar/okyc/otp/verify", self._aadhaar_body(credential))
            raw["_type"] = "aadhaar"
        else:
            raise GovernmentIdentityError(
                f"Unsupported sandbox credential type: {ctype}", "invalid_request")
        if not self.validate_response(raw=raw):
            raise GovernmentIdentityError("Sandbox returned an unrecognised response.", "provider_error")
        context = {**credential, "session_ref": session.session_ref}
        claims = self.extract_allowed_claims(raw=raw, context=context)
        return GovResult(claims=claims, government_photo=self.extract_temporary_photo(raw=raw))

    def validate_response(self, *, raw: dict) -> bool:
        # HTTP/status errors already raised in _post; a populated dict is a usable response.
        return isinstance(raw, dict) and bool(raw)

    def extract_allowed_claims(self, *, raw: dict, context: dict) -> VerifiedClaims:
        """Map a validated provider response to the ONLY retained claims (§5.5)."""
        ref_src = raw.get("transaction_id") or (
            f"{context.get('session_ref')}:{context.get('pan') or context.get('reference_id')}")
        ref = hashlib.sha256(str(ref_src).encode()).hexdigest()
        if raw.get("_type") == "aadhaar":
            name = raw.get("name") or raw.get("full_name") or ""
            dob = raw.get("date_of_birth") or raw.get("dob") or ""
            # Aadhaar returns the REAL name, so check it against the one the person gave us.
            # This used to be `bool(name)` — merely "a name came back" — which confirmed
            # nothing: someone could register as anybody and still pass.
            expected = str(context.get("expected_name") or "").strip()
            if expected:
                verdict = compare_names(expected, name)
                name_ok, name_reason = verdict.matched, verdict.reason
            else:
                name_ok, name_reason = False, "no name on file to compare against"
            return VerifiedClaims(
                identity_verified=True, name_verified=name_ok, document_valid=True,
                age_over_18=_age_over_18(dob), assurance_level="sandbox_aadhaar_okyc",
                verification_reference_hash=ref,
                # The government name itself is NOT retained — only the verdict (§5.5).
                extra={"gender": raw.get("gender"), "name_match_reason": name_reason})
        # PAN — confirmed live schema: status "valid", name_as_per_pan_match, date_of_birth_match,
        # category, aadhaar_seeding_status ("y"/"n"). Tolerant of status variants.
        status = str(raw.get("status", "")).upper()
        valid = status in ("VALID", "EXISTING AND VALID", "ACTIVE")
        name_ok = bool(raw.get("name_as_per_pan_match", raw.get("name_match", False)))
        dob_ok = bool(raw.get("date_of_birth_match", raw.get("dob_match", False)))
        return VerifiedClaims(
            identity_verified=valid, name_verified=name_ok, document_valid=valid,
            age_over_18=_age_over_18(context.get("dob")), assurance_level="sandbox_pan",
            verification_reference_hash=ref,
            extra={"category": raw.get("category"), "dob_match": dob_ok,
                   "aadhaar_seeding_status": raw.get("aadhaar_seeding_status")})

    def extract_temporary_photo(self, *, raw: dict) -> bytes | None:
        """The short-lived government face (Aadhaar OKYC only); deleted by the service after use."""
        photo_b64 = raw.get("photo") or raw.get("photo_base64") or ""
        if not photo_b64:
            return None
        try:
            return base64.b64decode(photo_b64)
        except Exception:  # noqa: BLE001 — a bad photo must not fail verification
            return None

    def revoke_or_close_session(self, *, session: GovSession) -> None:
        return None

    # --- request bodies ---------------------------------------------------
    def _pan_body(self, cred: dict) -> dict:
        return {
            "@entity": "in.co.sandbox.kyc.pan_verification.request",
            "pan": (cred.get("pan") or "").upper(),
            "name_as_per_pan": cred.get("name", ""),
            "date_of_birth": cred.get("dob", ""),
            "consent": "Y",
            "reason": cred.get("reason", "Identity verification for entry authorization"),
        }

    def _aadhaar_body(self, cred: dict) -> dict:
        ref_id = cred.get("reference_id")
        otp = cred.get("otp")
        if not ref_id or not otp:
            raise GovernmentIdentityError(
                "Aadhaar OKYC requires reference_id + otp (call aadhaar_okyc_send_otp first).",
                "invalid_request")
        return {"@entity": "in.co.sandbox.kyc.aadhaar.okyc.request",
                "reference_id": ref_id, "otp": str(otp)}

    # --- Aadhaar OTP send (step 1) ----------------------------------------
    def aadhaar_okyc_send_otp(self, *, aadhaar_number: str, reason: str = "") -> str:
        """Step 1 — trigger an OTP to the Aadhaar-registered mobile; returns a reference_id."""
        body = {
            "@entity": "in.co.sandbox.kyc.aadhaar.okyc.otp.request",
            "aadhaar_number": aadhaar_number,
            "consent": "Y",
            "reason": reason or "Identity verification for entry authorization",
        }
        data = self._post("/kyc/aadhaar/okyc/otp", body)
        ref = data.get("reference_id") or data.get("ref_id")
        if not ref:
            raise GovernmentIdentityError("Sandbox OKYC: no reference_id returned", "provider_error")
        return str(ref)
