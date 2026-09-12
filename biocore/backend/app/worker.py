"""Async event-bus worker.

Consumes tasks published to the `biocore.events` topic exchange and performs the
work out-of-band: webhook delivery (with retry) and notification sending. Messages
that exhaust their retries are dead-lettered to `biocore.dead`.

Run as its own process:  python -m app.worker
(Only needed when RABBITMQ_URL is set; otherwise the API delivers inline.)
"""
import json
import logging

import pika

from app.core.config import settings
from app.services import notifier, webhook_service

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("biocore.worker")

WORK_QUEUE = "biocore.work"
DEAD_EXCHANGE = "biocore.dead"
DEAD_QUEUE = "biocore.dead.q"
MAX_ATTEMPTS = 5


def _handle(task: dict) -> bool:
    """Return True if handled (ack), False to retry/dead-letter."""
    kind = task.get("kind")
    if kind == "webhook.deliver":
        return webhook_service.deliver_one(
            url=task["url"], secret=task["secret"],
            event=task["event"], payload=task["payload"], max_retries=1,
        )
    if kind == "notify.email":
        notifier.deliver_email(task["to"], task["subject"], task["body"])
        return True
    if kind == "notify.sms":
        notifier.deliver_sms(task["to"], task["body"])
        return True
    log.warning("unknown task kind: %s", kind)
    return True  # drop unknown tasks (ack) rather than loop forever


def _on_message(ch, method, props, body):
    attempt = 1
    if props.headers and "x-attempt" in props.headers:
        attempt = int(props.headers["x-attempt"])
    try:
        task = json.loads(body)
        ok = _handle(task)
    except Exception as e:
        log.exception("handler error: %s", e)
        ok = False

    if ok:
        ch.basic_ack(method.delivery_tag)
        return

    if attempt >= MAX_ATTEMPTS:
        log.error("dead-lettering after %s attempts: %s", attempt, body[:200])
        ch.basic_publish(exchange=DEAD_EXCHANGE, routing_key="dead", body=body)
        ch.basic_ack(method.delivery_tag)
    else:
        ch.basic_publish(
            exchange=settings.rabbitmq_exchange, routing_key=method.routing_key, body=body,
            properties=pika.BasicProperties(delivery_mode=2, headers={"x-attempt": attempt + 1}),
        )
        ch.basic_ack(method.delivery_tag)


def main() -> None:
    if not settings.rabbitmq_url:
        raise SystemExit("RABBITMQ_URL not set — the API delivers inline; no worker needed.")
    conn = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
    ch = conn.channel()
    ch.exchange_declare(exchange=settings.rabbitmq_exchange, exchange_type="topic", durable=True)
    ch.exchange_declare(exchange=DEAD_EXCHANGE, exchange_type="fanout", durable=True)
    ch.queue_declare(queue=WORK_QUEUE, durable=True)
    ch.queue_declare(queue=DEAD_QUEUE, durable=True)
    ch.queue_bind(WORK_QUEUE, settings.rabbitmq_exchange, routing_key="#")
    ch.queue_bind(DEAD_QUEUE, DEAD_EXCHANGE)
    ch.basic_qos(prefetch_count=16)
    ch.basic_consume(WORK_QUEUE, _on_message)
    log.info("worker consuming from %s", WORK_QUEUE)
    ch.start_consuming()


if __name__ == "__main__":
    main()
