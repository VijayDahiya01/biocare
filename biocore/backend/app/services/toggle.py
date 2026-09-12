"""Toggle logic — the rule that decides whether a scan is a check-in or check-out.

Pure and side-effect-free so it can be unit-tested in isolation (acceptance 2.2:
"Toggle logic correctly alternates check-in and check-out").
"""

CHECK_IN = "check_in"
CHECK_OUT = "check_out"


def decide_event(action: str, is_inside: bool) -> str:
    """Given the requested action and whether the person is currently inside,
    return the event to record.

    action:
      "in"   -> always check_in
      "out"  -> always check_out
      "auto" -> toggle: check_out if inside, else check_in (the default)
    """
    if action == "in":
        return CHECK_IN
    if action == "out":
        return CHECK_OUT
    # auto
    return CHECK_OUT if is_inside else CHECK_IN
