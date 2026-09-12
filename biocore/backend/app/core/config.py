"""Central settings, loaded from environment only (never hardcoded)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    api_port: int = 8080
    data_region: str = "india"

    # stores
    database_url: str = "postgresql+psycopg://biocore:biocore@localhost:5432/biocore"
    redis_url: str = "redis://localhost:6379/0"
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    minio_endpoint: str = "localhost:9000"
    minio_key: str = "biocore-minio"
    minio_secret: str = "biocore-minio"
    minio_secure: bool = False

    # zepiris
    zepiris_url: str = "http://localhost:8000"
    zepiris_timeout_seconds: float = 15.0
    match_threshold: float = 0.5

    # PPE / safety-gear detection (Phase 4). Pluggable ML service; if the URL is
    # unset, PPE checks are skipped (the model is a deployment-time artifact).
    ppe_service_url: str = ""
    ppe_timeout_seconds: float = 10.0

    # --- dev / testing toggles (never enable in production) ---
    # fake_zepiris: run the full face flow in-process without Milvus/MinIO/ML.
    # fake_redis: use an in-memory Redis so only Postgres is needed to run.
    fake_zepiris: bool = False
    fake_redis: bool = False
    # dev_login: allow skipping OTP on the person app (POST /person/auth/dev-login).
    # NEVER enable in production — it lets anyone session as any email.
    dev_login: bool = False

    # outbound messaging. SMTP_URL like smtp://user:pass@host:587 or smtps://…:465.
    # Unset => emails are logged (dev stub), so OTPs still work locally.
    smtp_url: str = ""
    smtp_from: str = "BioCore <no-reply@biocore.local>"
    smtp_timeout_seconds: float = 10.0
    sms_provider_key: str = ""

    # where generated PDFs (certificates/receipts/musters) are written. In
    # production these go to MinIO; locally they go to this directory.
    files_dir: str = "generated"

    # key for encrypting the person master face template at rest (person app,
    # Option A). Set MASTER_KEY (urlsafe-base64 32 bytes) from a KMS in prod;
    # in dev a stable key is derived from SESSION_SECRET.
    master_key: str = ""

    # RabbitMQ async event bus. Unset => webhooks/notifications run inline
    # (synchronous fallback), so the platform works without a broker locally.
    rabbitmq_url: str = ""
    rabbitmq_exchange: str = "biocore.events"

    # --- Verified-identity re-architecture (BIOCORE_COMPLETE_CHANGE_SPEC) ---
    # KMS for face-template envelope encryption (§6). 'software' derives per-tenant keys
    # from KMS_ROOT_KEY (dev/MVP); use aws|gcp|vault|hsm in production (implement KmsProvider).
    kms_provider: str = "software"
    kms_root_key: str = ""
    # Government identity proofing (§19.1). Fake provider is DEV ONLY — never in prod/pilots.
    fake_gov_identity: bool = False
    gov_identity_provider: str = ""          # fake | sandbox | aadhaar | digilocker | vendor | ...
    identity_verification_required: bool = False
    # Sandbox (api.sandbox.co.in) KYC provider — real vendor API (PAN verify + Aadhaar OKYC).
    # Secrets come from the environment only; never commit them. Selected via
    # gov_identity_provider="sandbox" with fake_gov_identity=false.
    sandbox_base_url: str = "https://api.sandbox.co.in"
    sandbox_api_key: str = ""
    sandbox_api_secret: str = ""
    sandbox_api_version: str = "2.0"
    # Face engine (§15.1). Dev uses the fake (FAKE_ZEPIRIS / FACE_ENGINE=fake); a real engine is
    # wired via a remote HTTP client (FACE_ENGINE=remote + FACE_ENGINE_URL) — no business change.
    face_engine: str = ""                    # "" | fake | remote
    face_engine_url: str = ""
    face_engine_token: str = ""
    face_match_threshold: float = 0.62       # 1:1 similarity threshold for the real engine
    # Face model/template versioning (§15.3) — bound into the template's encryption AAD.
    face_model_version: str = "dev-fake-v1"
    face_template_version: str = "v1"
    # BioVerify credential API (§15.1) — the external service that now owns the WHOLE face
    # credential lifecycle: it enrols, seals and issues the scannable credential (`qr_text`)
    # and decides the 1:1 verification at the gate. Replaces ZepIris. Secrets from env only.
    bioverify_url: str = ""
    bioverify_api_key: str = ""
    bioverify_timeout_seconds: float = 30.0         # enrol/issue: real model work, allow headroom
    bioverify_verify_timeout_seconds: float = 10.0  # gate: fail fast, there is a queue behind them
    bioverify_qr_scale: int = 8
    fake_bioverify: bool = False                    # dev only; the factory blocks it in production
    # Which engine mints NEW credentials. Existing rows keep working either way — the matcher
    # branches on each row's own `credential_source`, so the two coexist during the cutover.
    credential_engine: str = "template"             # template | bioverify
    # Floor for a new credential's lifetime when the tenant has no retention policy yet.
    # Without it a brand-new tenant mints credentials that never expire.
    default_credential_retention_days: int = 365
    # Walk-up 1:N over BioVerify costs ONE network verify per candidate (there is no 1:N route),
    # so it is bounded rather than unbounded. Raise the cap only with the latency in hand.
    bioverify_identify_max_candidates: int = 200
    bioverify_identify_concurrency: int = 8
    # Default tenant entry policy profile (§24): see app.core.policy.POLICY_PROFILES.
    default_policy_profile: str = "standard_entry"
    # Trusted request context (§12.4) — every gate request carries signed device/tenant/gate/
    # zone/timestamp/nonce/version context. Enforcement is opt-in in dev so existing kiosk
    # flows keep working; turn require_signed_context on for hardened production terminals.
    require_signed_context: bool = False
    trusted_context_skew_seconds: int = 120     # timestamp freshness window (± seconds)
    nonce_ttl_seconds: int = 900                # how long a nonce is remembered for replay checks
    min_terminal_software_version: str = ""     # empty = no floor; else e.g. "1.4.0"
    current_policy_version: str = "v1"          # policy version terminals must acknowledge
    require_hardened_terminal: bool = False     # §12.3 — require an attested hardening posture
    # Offline / poor-network mode (§16). "off" = online only; "manual" = QR/manual fallback
    # (Option A, strongest privacy); "roster" = encrypted device-bound local roster (Option B).
    # Option C (on-site edge matcher) is a deployment topology, not an app flag.
    offline_mode: str = "off"
    offline_roster_ttl_seconds: int = 28800     # 8h — strict expiry on the local roster
    offline_roster_max_subjects: int = 5000     # sanity cap on roster size
    # Business integration connectors (§19.2). Fake (in-memory) by default for dev; real
    # per-vendor connectors implement the Protocols and register when their access is provisioned.
    fake_connectors: bool = True
    # Local hardware bridge (§19.3) — receives only allow/deny + signed context, never a template.
    hardware_bridge_enabled: bool = False
    hardware_open_ms: int = 3000                # relay pulse on an allow decision

    # security / sessions
    session_secret: str = "dev-session-secret"
    csrf_secret: str = "dev-csrf-secret"
    session_ttl_admin_seconds: int = 28800
    session_ttl_member_seconds: int = 14400
    cookie_secure: bool = True
    cookie_domain: str = ""
    # DEMO ONLY: skip the admin 2FA/TOTP step so a demo login is frictionless. Hard-blocked in
    # production (see authenticate()) — never trust this to weaken a real deployment.
    demo_disable_totp: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
