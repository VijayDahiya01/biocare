"""Pure leave-balance logic (no DB) — unit-tested."""

DEFAULT_ALLOCATIONS = {"casual": 12, "sick": 12, "earned": 15}


def days_inclusive(from_ordinal: int, to_ordinal: int) -> int:
    """Inclusive day count between two date ordinals."""
    return max(0, to_ordinal - from_ordinal + 1)


def balance(used: dict[str, int], allocations: dict[str, int] | None = None) -> dict:
    """Given days used per type, return remaining + used per type."""
    alloc = allocations or DEFAULT_ALLOCATIONS
    out: dict = {"used": {}}
    for kind, total in alloc.items():
        u = used.get(kind, 0)
        out[kind] = max(0, total - u)
        out["used"][kind] = u
    return out
