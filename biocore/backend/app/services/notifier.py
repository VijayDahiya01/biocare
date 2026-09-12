"""Outbound notifications.

Email: real SMTP when SMTP_URL is set; otherwise a logging stub so the
registration/OTP flows work locally without a mail server. SMS/WhatsApp remain
stubs pending provider credentials. Priority routing + async delivery (RabbitMQ)
are a later step; today email is sent synchronously with a short timeout.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import unquote, urlparse

from app.core.config import settings

log = logging.getLogger("biocore.notifier")


def _send_smtp(to: str, subject: str, body: str) -> None:
    url = urlparse(settings.smtp_url)
    host = url.hostname or "localhost"
    use_ssl = url.scheme == "smtps"
    port = url.port or (465 if use_ssl else 587)
    user = unquote(url.username) if url.username else None
    password = unquote(url.password) if url.password else None

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    timeout = settings.smtp_timeout_seconds
    if use_ssl:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx) as s:
            if user:
                s.login(user, password or "")
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as s:
            try:
                s.starttls(context=ssl.create_default_context())
            except smtplib.SMTPNotSupportedError:
                pass  # plain SMTP (e.g. local relay)
            if user:
                s.login(user, password or "")
            s.send_message(msg)


def deliver_email(to: str, subject: str, body: str) -> None:
    """Actually send (or stub-log) an email. Shared by inline + worker paths."""
    if not settings.smtp_url:
        log.info("[email:stub] to=%s subject=%s body=%s", to, subject, body)
        return
    try:
        _send_smtp(to, subject, body)
        log.info("[email] sent to=%s subject=%s", to, subject)
    except Exception as e:  # email failure must not break the calling request
        log.error("[email] FAILED to=%s subject=%s err=%s", to, subject, e)


def send_email(*, to: str, subject: str, body: str) -> None:
    """Enqueue on the event bus if available; else send inline."""
    from app.core import eventbus

    task = {"kind": "notify.email", "to": to, "subject": subject, "body": body}
    if not eventbus.publish("notify.email", task):
        deliver_email(to, subject, body)


def deliver_sms(to: str, body: str) -> None:
    if not settings.sms_provider_key:
        log.info("[sms:stub] to=%s body=%s", to, body)
        return
    # TODO: real SMS provider (e.g. MSG91/Twilio) when credentials are configured.
    log.info("[sms] to=%s", to)


def send_sms(*, to: str, body: str) -> None:
    from app.core import eventbus

    task = {"kind": "notify.sms", "to": to, "body": body}
    if not eventbus.publish("notify.sms", task):
        deliver_sms(to, body)
