"""RabbitMQ event bus (publisher) with a graceful fallback.

`publish()` returns True if the task was handed to the broker, or False if the
bus is disabled/unreachable — in which case the caller performs the work inline
(synchronous fallback). This keeps the platform fully functional without a broker
(local dev) while enabling out-of-band, retried delivery in production.

Topology (declared by the worker): a topic exchange `biocore.events`, a durable
`biocore.work` queue bound to `#`, and a dead-letter exchange/queue for messages
that exhaust their retries.
"""
import json
import logging
import threading

from app.core.config import settings

log = logging.getLogger("biocore.eventbus")

_local = threading.local()


def enabled() -> bool:
    return bool(settings.rabbitmq_url)


def _channel():
    """Lazily create a per-thread channel; returns None on any failure."""
    if not enabled():
        return None
    ch = getattr(_local, "channel", None)
    if ch is not None and not getattr(ch, "is_closed", True):
        return ch
    try:
        import pika

        params = pika.URLParameters(settings.rabbitmq_url)
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.exchange_declare(exchange=settings.rabbitmq_exchange, exchange_type="topic", durable=True)
        _local.connection = conn
        _local.channel = ch
        return ch
    except Exception as e:  # broker down / pika missing -> fall back inline
        log.warning("event bus unavailable, falling back inline: %s", e)
        _local.channel = None
        return None


def publish(routing_key: str, body: dict) -> bool:
    """Publish a task. Returns False if not delivered (caller should run inline)."""
    ch = _channel()
    if ch is None:
        return False
    try:
        import pika

        ch.basic_publish(
            exchange=settings.rabbitmq_exchange,
            routing_key=routing_key,
            body=json.dumps(body).encode(),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
        return True
    except Exception as e:
        log.warning("event bus publish failed (%s), inline fallback: %s", routing_key, e)
        _local.channel = None
        return False
