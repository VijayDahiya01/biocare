"""Production safety guards — refuse to boot in an unsafe configuration.

Individual dev shortcuts are already blocked at their point of use (fake engines, fake gov
provider, SoftwareKms). Those fire lazily, which means the first person to
discover a misconfiguration is whoever is standing at a gate. This checks the whole
configuration once, at startup, and refuses to start rather than serving a broken promise.

Nothing here runs outside `ENVIRONMENT=production`, so local development is untouched.
"""
from __future__ import annotations

from app.core.config import settings

_DEV_SECRETS = {"dev-session-secret", "dev-csrf-secret", "", "changeme", "secret"}


def production_problems() -> list[str]:
    """Every reason this configuration must not serve real people. Empty list = safe.

    Each entry names the setting and what goes wrong, because a deployment error at 2am is
    read by someone who did not write this code.
    """
    problems: list[str] = []

    if settings.dev_login:
        problems.append(
            "DEV_LOGIN=true — POST /person/auth/dev-login lets ANYONE sign in as ANY email "
            "with no password and no one-time code. Set DEV_LOGIN=false.")

    for flag, name in ((settings.fake_zepiris, "FAKE_ZEPIRIS"),
                       (settings.fake_bioverify, "FAKE_BIOVERIFY"),
                       (settings.fake_gov_identity, "FAKE_GOV_IDENTITY"),
                       (settings.fake_redis, "FAKE_REDIS"),
                       # Only a problem when connectors are actually in use: a stand-in that
                       # nothing ever calls is not answering for anything.
                       (settings.fake_connectors and settings.connectors_enabled,
                        "FAKE_CONNECTORS")):
        if flag:
            problems.append(f"{name}=true — a stand-in is answering instead of the real service. "
                            f"Set {name}=false.")


    if not settings.cookie_secure:
        problems.append(
            "COOKIE_SECURE=false — session cookies would be sent over plain HTTP and can be "
            "stolen in transit. Serve the app over HTTPS and set COOKIE_SECURE=true.")

    if settings.session_secret in _DEV_SECRETS or settings.csrf_secret in _DEV_SECRETS:
        problems.append(
            "SESSION_SECRET / CSRF_SECRET is still the built-in development value. Anyone who "
            "has read this source can forge a session. Generate fresh random values.")

    if settings.kms_provider == "software" and not settings.kms_root_key:
        problems.append(
            "KMS_PROVIDER=software with no KMS_ROOT_KEY — face templates would be encrypted "
            "with a key derived from the session secret. Use a real KMS/HSM, or at minimum set "
            "KMS_ROOT_KEY from a secret store.")

    if not settings.smtp_url and not settings.brevo_api_key:
        problems.append(
            "Neither SMTP_URL nor BREVO_API_KEY is set — one-time codes are only written to "
            "the log, so nobody can actually sign in. Configure outbound email.")

    if settings.credential_engine == "bioverify" and not settings.bioverify_url:
        problems.append("CREDENTIAL_ENGINE=bioverify but BIOVERIFY_URL is unset.")

    if settings.face_engine == "remote" and not settings.face_engine_url:
        problems.append("FACE_ENGINE=remote but FACE_ENGINE_URL is unset.")

    return problems


def assert_production_safe() -> None:
    """Raise on startup if this configuration must not serve real people."""
    if not settings.is_production:
        return
    problems = production_problems()
    if problems:
        listed = "\n".join(f"  {i}. {p}" for i, p in enumerate(problems, 1))
        raise RuntimeError(
            "Refusing to start: this configuration is not safe for production.\n"
            f"{listed}\n"
            "Fix these, or run with ENVIRONMENT=development if this is a test machine."
        )
