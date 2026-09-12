"""Unit tests for toggle logic (acceptance 2.2 — alternates check-in/out)."""
from app.services.toggle import CHECK_IN, CHECK_OUT, decide_event


def test_auto_first_scan_is_check_in():
    assert decide_event("auto", is_inside=False) == CHECK_IN


def test_auto_when_inside_is_check_out():
    assert decide_event("auto", is_inside=True) == CHECK_OUT


def test_auto_alternates_across_a_day():
    inside = False
    events = []
    for _ in range(4):
        ev = decide_event("auto", inside)
        events.append(ev)
        inside = ev == CHECK_IN  # entering puts you inside; leaving takes you out
    assert events == [CHECK_IN, CHECK_OUT, CHECK_IN, CHECK_OUT]


def test_explicit_in_and_out_override_state():
    assert decide_event("in", is_inside=True) == CHECK_IN
    assert decide_event("out", is_inside=False) == CHECK_OUT
