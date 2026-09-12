"""Pure payroll / productive-time logic (no DB) — unit-tested.

Worked time pairs check_in -> check_out, subtracting any break_start -> break_end
inside the day. Overtime is computed per day above a threshold (default 8h).
"""
from datetime import datetime

CHECK_IN, CHECK_OUT = "check_in", "check_out"
BREAK_START, BREAK_END = "break_start", "break_end"


def worked_break_minutes(events: list[tuple[str, datetime]]) -> tuple[int, int]:
    """events: (event_type, timestamp) for ONE day, any order. Returns
    (worked_minutes, break_minutes) where worked excludes breaks."""
    ordered = sorted(events, key=lambda e: e[1])
    gross = 0.0
    brk = 0.0
    work_open: datetime | None = None
    break_open: datetime | None = None
    for etype, t in ordered:
        if etype == CHECK_IN:
            work_open = t
        elif etype == CHECK_OUT:
            if work_open is not None:
                gross += (t - work_open).total_seconds()
                work_open = None
        elif etype == BREAK_START:
            break_open = t
        elif etype == BREAK_END:
            if break_open is not None:
                brk += (t - break_open).total_seconds()
                break_open = None
    worked = max(0.0, gross - brk)
    return int(worked // 60), int(brk // 60)


def calc_pay(daily_hours: list[float], rate_per_hour: float, overtime_multiplier: float = 1.5,
             daily_threshold: float = 8.0) -> dict:
    """Given a list of hours worked per day, split regular vs overtime per day
    and compute pay."""
    regular = 0.0
    overtime = 0.0
    for h in daily_hours:
        reg = min(h, daily_threshold)
        ot = max(0.0, h - daily_threshold)
        regular += reg
        overtime += ot
    base_pay = round(regular * rate_per_hour, 2)
    overtime_pay = round(overtime * rate_per_hour * overtime_multiplier, 2)
    return {
        "hours": round(regular + overtime, 2),
        "regular_hours": round(regular, 2),
        "overtime_hours": round(overtime, 2),
        "base_pay": base_pay,
        "overtime_pay": overtime_pay,
        "total": round(base_pay + overtime_pay, 2),
    }
