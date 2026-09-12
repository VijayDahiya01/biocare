"""Pure PPE (personal protective equipment) decision logic — unit-tested.

`detections` maps gear -> present?  e.g. {"helmet": True, "vest": False}.
`required` is the list a zone demands, e.g. ["helmet", "vest"].
"""

DEFAULT_REQUIRED = ["helmet", "vest"]


def evaluate_ppe(detections: dict[str, bool], required: list[str] | None = None) -> tuple[bool, list[str]]:
    """Return (ok, missing). ok is True only when every required item is present."""
    req = required or DEFAULT_REQUIRED
    missing = [item for item in req if not detections.get(item, False)]
    return (len(missing) == 0, missing)
