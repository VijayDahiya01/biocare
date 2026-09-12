"""Unit tests for the event-bus fallback + webhook delivery routine."""
import httpx
import respx

from app.core import eventbus
from app.services.webhook_service import deliver_one


def test_eventbus_disabled_without_broker():
    # no RABBITMQ_URL in the test env -> bus disabled, publish is a no-op
    assert eventbus.enabled() is False
    assert eventbus.publish("webhook.deliver", {"kind": "webhook.deliver"}) is False


@respx.mock
def test_deliver_one_success():
    route = respx.post("https://hook.example/door").mock(return_value=httpx.Response(200))
    ok = deliver_one(url="https://hook.example/door", secret="s",
                     event="access.granted", payload={"zone_id": "z1"})
    assert ok is True
    # payload is signed
    body = route.calls.last.request.content
    assert b"signature" in body and b"sha256=" in body


@respx.mock
def test_deliver_one_failure_after_retries():
    respx.post("https://hook.example/door").mock(return_value=httpx.Response(500))
    ok = deliver_one(url="https://hook.example/door", secret="s",
                     event="access.granted", payload={"zone_id": "z1"}, max_retries=2)
    assert ok is False


@respx.mock
def test_deliver_one_network_error_is_false():
    respx.post("https://hook.example/door").mock(side_effect=httpx.ConnectError("down"))
    assert deliver_one(url="https://hook.example/door", secret="s",
                       event="x", payload={}, max_retries=1) is False
