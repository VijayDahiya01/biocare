"""Comparing a given name with a government record (app/core/name_match.py).

Two failure modes matter, and they pull in opposite directions: refusing an honest person
because their Aadhaar carries a middle name, and accepting a different person because the
surname happens to match. Both are tested.
"""
from app.core.name_match import compare_names


class TestAccepts:
    """Differences that carry no meaning must not block anyone."""

    def test_identical(self):
        assert compare_names("Asha Rao", "Asha Rao").matched

    def test_case_and_spacing(self):
        assert compare_names("  asha   RAO ", "Asha Rao").matched

    def test_government_has_a_middle_name(self):
        assert compare_names("Asha Rao", "Asha Kumari Rao").matched

    def test_person_typed_a_middle_name_the_record_lacks(self):
        assert compare_names("Asha Kumari Rao", "Asha Rao").matched

    def test_order_differs(self):
        assert compare_names("Asha Rao", "Rao Asha").matched

    def test_initial_against_full_name(self):
        assert compare_names("A Rao", "Asha Rao").matched
        assert compare_names("Asha Rao", "A Rao").matched

    def test_punctuation_and_accents(self):
        assert compare_names("D'Souza Maria", "DSouza Maria").matched
        assert compare_names("José Álvarez", "Jose Alvarez").matched

    def test_honorifics_ignored(self):
        assert compare_names("Dr Asha Rao", "Asha Rao").matched
        assert compare_names("Asha Rao", "Smt. Asha Rao").matched


class TestRejects:
    """A false accept on identity is the expensive mistake."""

    def test_different_people(self):
        assert not compare_names("Asha Rao", "Bob Smith").matched

    def test_one_letter_apart_is_a_different_person(self):
        # Deliberately NOT fuzzy: Asha and Usha are different people.
        assert not compare_names("Asha Rao", "Usha Rao").matched

    def test_surname_alone_is_not_identification(self):
        assert not compare_names("Rao", "Rao").matched

    def test_first_name_matches_but_surname_does_not(self):
        assert not compare_names("Asha Rao", "Asha Mehta").matched

    def test_missing_names(self):
        assert not compare_names("", "Asha Rao").matched
        assert not compare_names("Asha Rao", "").matched


def test_reason_is_readable():
    """The reason is written into a verification record a person may later ask about."""
    ok = compare_names("Asha Rao", "Asha Kumari Rao")
    bad = compare_names("Asha Rao", "Bob Smith")
    assert "matches" in ok.reason
    assert "does not match" in bad.reason and bad.compared == 2


# --- the providers must actually compare, not just report that a name came back ---

def _claims(expected: str, official: str):
    from app.adapters.gov_identity.fake import FakeGovernmentProvider
    return FakeGovernmentProvider().extract_allowed_claims(
        raw={"session_ref": "s", "reference": "r"},
        context={"expected_name": expected, "fake_government_name": official})


def test_provider_rejects_a_different_name():
    """The whole point: registering as one person and holding another's Aadhaar must fail."""
    c = _claims("Asha Rao", "Bob Smith")
    assert c.name_verified is False
    assert "does not match" in c.extra["name_match_reason"]


def test_provider_accepts_the_same_person():
    c = _claims("Asha Rao", "Asha Kumari Rao")
    assert c.name_verified is True


def test_provider_refuses_when_we_hold_no_name():
    """`name_verified` used to be `bool(name)` — true whenever ANY name came back, which
    confirmed nothing. With no name on file there is nothing to compare, so it must be false."""
    c = _claims("", "Asha Rao")
    assert c.name_verified is False
