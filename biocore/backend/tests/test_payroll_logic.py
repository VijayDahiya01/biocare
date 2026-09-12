"""Unit tests for payroll / productive-time logic."""
from datetime import datetime

from app.services.payroll_logic import calc_pay, worked_break_minutes


def _dt(h, m=0):
    return datetime(2026, 6, 15, h, m)


def test_worked_minutes_simple_day():
    events = [("check_in", _dt(9)), ("check_out", _dt(17))]
    worked, brk = worked_break_minutes(events)
    assert worked == 8 * 60
    assert brk == 0


def test_worked_minutes_subtracts_break():
    events = [("check_in", _dt(9)), ("break_start", _dt(13)),
              ("break_end", _dt(13, 30)), ("check_out", _dt(17))]
    worked, brk = worked_break_minutes(events)
    assert brk == 30
    assert worked == 8 * 60 - 30


def test_worked_minutes_unordered_input():
    events = [("check_out", _dt(17)), ("check_in", _dt(9))]
    worked, _ = worked_break_minutes(events)
    assert worked == 8 * 60


def test_calc_pay_no_overtime():
    pay = calc_pay([8, 8], rate_per_hour=100)
    assert pay["regular_hours"] == 16
    assert pay["overtime_hours"] == 0
    assert pay["base_pay"] == 1600
    assert pay["total"] == 1600


def test_calc_pay_with_overtime():
    # 10h day -> 8 regular + 2 OT at 1.5x
    pay = calc_pay([10], rate_per_hour=100, overtime_multiplier=1.5)
    assert pay["regular_hours"] == 8
    assert pay["overtime_hours"] == 2
    assert pay["base_pay"] == 800
    assert pay["overtime_pay"] == 300  # 2 * 100 * 1.5
    assert pay["total"] == 1100
