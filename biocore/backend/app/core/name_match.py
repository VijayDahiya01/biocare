"""Comparing the name a person gave us with the name a government record returns.

Exact string equality is the wrong test and would lock out honest people. Real records differ
in ways that carry no meaning:

    "Asha Rao"          vs "ASHA RAO"              case
    "Asha Rao"          vs "Asha Kumari Rao"       a middle name the person did not type
    "Asha Rao"          vs "Rao Asha"              order
    "A Rao"             vs "Asha Rao"              an initial
    "Asha  Rao "        vs "Asha Rao"              spacing
    "D'Souza"           vs "DSouza"                punctuation

So the test is: **every name part one side holds must be present on the other**, where an
initial matches a word starting with that letter. The government record is allowed to carry
MORE parts than the person typed, and vice versa — extra middle names prove nothing either way.

What this deliberately does NOT do is accept a near-miss. "Asha Rao" and "Usha Rao" are one
letter apart and are different people; there is no edit-distance fuzziness here, because a
false accept on identity is far worse than asking someone to retype their name.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Honorifics and suffixes that appear on one record and not the other, and mean nothing here.
_NOISE = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "shri", "smt", "sri", "kum",
    "md", "mohd", "jr", "sr", "late", "s", "o", "d", "w", "c",   # s/o, d/o, w/o, c/o fragments
}


@dataclass
class NameMatch:
    matched: bool
    reason: str          # why, in words — this ends up in an audit record
    compared: int = 0    # how many name parts actually lined up


def _normalise(name: str) -> list[str]:
    """Lowercase, strip accents and punctuation, split into meaningful parts."""
    if not name:
        return []
    flat = unicodedata.normalize("NFKD", name)
    flat = "".join(c for c in flat if not unicodedata.combining(c)).lower()
    flat = re.sub(r"[^a-z0-9\s]", "", flat)          # D'Souza -> dsouza, S/O -> s o
    return [t for t in flat.split() if t and t not in _NOISE]


def _covers(part: str, others: list[str]) -> bool:
    """Is this name part present in the other name — as a word, or as its initial?"""
    if part in others:
        return True
    if len(part) == 1:                                # "a" matches "asha"
        return any(o.startswith(part) for o in others)
    return any(len(o) == 1 and part.startswith(o) for o in others)


def compare_names(given: str, official: str) -> NameMatch:
    """Does the name the person gave us match the one on the government record?"""
    a, b = _normalise(given), _normalise(official)
    if not a:
        return NameMatch(False, "no name on file for this person")
    if not b:
        return NameMatch(False, "the government record returned no name")

    # Compare in the direction that has fewer parts: the other side may hold extra middle
    # names, which is normal and proves nothing.
    fewer, more = (a, b) if len(a) <= len(b) else (b, a)
    missing = [p for p in fewer if not _covers(p, more)]
    if missing:
        return NameMatch(False, f"name does not match the government record "
                                f"({len(missing)} of {len(fewer)} parts differ)",
                         compared=len(fewer))

    # One matching part is not identification — half the country shares a surname.
    if len(fewer) < 2 and not (len(a) >= 2 or len(b) >= 2):
        return NameMatch(False, "only one name part to compare — too little to confirm",
                         compared=len(fewer))

    return NameMatch(True, "name matches the government record", compared=len(fewer))
