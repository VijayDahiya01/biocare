"""In-process metrics registry (BIOCORE_COMPLETE_CHANGE_SPEC §23).

A tiny, dependency-free, thread-safe collector for the operational signals that are NOT
derivable from the database — call counts, failure counts and latencies observed as code
runs (gov API outcomes, KMS/decrypt, gate match latency, device-trust failures).

This is a per-process, in-memory view (resets on restart, not aggregated across workers) — the
production target is Prometheus/OTel, but the *instrumentation points* live here so swapping
the backend later touches only this file. DB-derived rates/counts live in monitoring_service.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from contextlib import contextmanager

_lock = threading.Lock()
_counters: dict[str, float] = defaultdict(float)
_hist: dict[str, dict] = defaultdict(lambda: {"count": 0, "sum": 0.0, "min": None, "max": None})
_started_at = time.time()


def incr(name: str, n: float = 1.0) -> None:
    with _lock:
        _counters[name] += n


def observe(name: str, value: float) -> None:
    """Record a sample (e.g. a latency in ms) into a lightweight histogram summary."""
    with _lock:
        h = _hist[name]
        h["count"] += 1
        h["sum"] += value
        h["min"] = value if h["min"] is None else min(h["min"], value)
        h["max"] = value if h["max"] is None else max(h["max"], value)


@contextmanager
def timer(name: str):
    """Time a block and record its duration in milliseconds under `name`."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        observe(name, (time.perf_counter() - t0) * 1000.0)


def rate(success: str, failure: str) -> float | None:
    """success / (success + failure) from two counters, or None if no samples yet."""
    with _lock:
        s = _counters.get(success, 0.0)
        f = _counters.get(failure, 0.0)
    total = s + f
    return (s / total) if total else None


def snapshot() -> dict:
    with _lock:
        counters = dict(_counters)
        hist = {k: {**v, "avg": (v["sum"] / v["count"] if v["count"] else 0.0)}
                for k, v in _hist.items()}
    return {"uptime_seconds": round(time.time() - _started_at, 1),
            "counters": counters, "histograms": hist}


def reset() -> None:
    """Clear all metrics (used by tests)."""
    with _lock:
        _counters.clear()
        _hist.clear()
