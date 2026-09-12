"""Unit tests for leave balance logic."""
from datetime import date

from app.services.leave_logic import DEFAULT_ALLOCATIONS, balance, days_inclusive


def test_days_inclusive():
    a = date(2026, 6, 20).toordinal()
    b = date(2026, 6, 22).toordinal()
    assert days_inclusive(a, b) == 3
    assert days_inclusive(a, a) == 1


def test_balance_subtracts_used():
    b = balance({"casual": 2, "sick": 1})
    assert b["casual"] == DEFAULT_ALLOCATIONS["casual"] - 2
    assert b["sick"] == DEFAULT_ALLOCATIONS["sick"] - 1
    assert b["earned"] == DEFAULT_ALLOCATIONS["earned"]
    assert b["used"]["casual"] == 2


def test_balance_never_negative():
    b = balance({"casual": 999})
    assert b["casual"] == 0
