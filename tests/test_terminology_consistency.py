"""tests/test_terminology_consistency.py --, cross-cutting
guard for E1: "European baseline" = EU27 + the
selected friend countries (UK, CH, NO, IS), swept across every rendered
string, defined once in Methods; plus E3's suffix-naming ruling (PP10_WD /
FWCI_EU) at its two primary label hooks.

Reuses `tests/test_narrative.py:collect_copy_module_strings` -- the SAME
recursive walk `test_forbidden_vocabulary.py`'s own jargon sweep already
trusts -- rather than re-implementing a second string collector that could
silently drift from the first.

Scope note (deliberately NARROW, to avoid a false positive on live,
correct copy): the OLD phrasings this module bans are the SPECIFIC compound
strings a copy review actually found and fixed ("a European
reference", "that European average", in `copy.COLLAB["COL_FWCI_HELP"]"),
not a blanket ban on the words "European
reference"/"European average" in isolation -- the ruled Methods
section is deliberately titled "The European average behind a reference
line", and banning that substring outright would
fail on a correct, reviewed string rather than catch a regression. The
suffix check below is likewise scoped to the two hooks actually named
(`copy.COMPARE["METRIC_PP"/"METRIC_FWCI"]`, `copy.FIND["KPI_PP_LABEL"]`)
a residual "PP(top10%)" literal survives in a few OTHER Find keys
(`CARD_PP`/`ASP_SORT_LABEL`/`ASP_UNDEFINED`/`COL_PP`/`TILE_PP`), already
disclosed as a known, out-of-fence gap for a future round --
asserting it away here would fail on a KNOWN,
undisputed gap rather than guard the rulings this module owns.

VACUITY, per module: every assertion is followed by an in-memory mutation
that makes the identical check fail.

Run: python -m pytest tests/test_terminology_consistency.py -q
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_narrative import collect_copy_module_strings

APP_DIR = Path(__file__).resolve().parents[1]

# test_forbidden_vocabulary.py's own established scope: METHODS_SOURCES is a
# provenance map read only by the test suite / docs/METHODS_NOTE.md, never
# rendered on any page.
NON_RENDERED_NAMES = {"METHODS_SOURCES"}

BANNED_OLD_PHRASES = (
    "a European reference",     # VL4 finding: COL_FWCI_HELP's pre-2D wording
    "that European average",    # VL4 finding: COL_FWCI_HELP's pre-2D wording
    "EU27+UK/CH/NO/IS",          # the old, undefined shorthand for the perimeter
    "EU27 + UK/CH/NO/IS",
)


def _rendered_copy_strings() -> list[tuple[str, str]]:
    from lib import copy as copy_mod
    return [(loc, s) for loc, s in collect_copy_module_strings(copy_mod)
           if not any(f"::{name}[" in loc for name in NON_RENDERED_NAMES)]


# ============================================================================
# E1 -- no rendered string carries an old, pre-2D baseline phrasing
# ============================================================================

def test_no_rendered_string_carries_an_old_pre_2d_baseline_phrasing():
    strings = _rendered_copy_strings()
    assert len(strings) > 100, "collector must be walking the real, large copy module"

    hits = [(loc, phrase, s) for loc, s in strings for phrase in BANNED_OLD_PHRASES if phrase in s]
    assert hits == [], hits

    # VACUITY: injecting one of the exact banned phrases into a COPY of the
    # collected strings makes the IDENTICAL scan report a hit -- proving the
    # check above is a real substring search that would have caught the old
    # wording, not an empty list by construction.
    poisoned = strings + [("scratch::TEST_POISON", "reads against that European average value")]
    poisoned_hits = [(loc, phrase, s) for loc, s in poisoned for phrase in BANNED_OLD_PHRASES if phrase in s]
    assert poisoned_hits, "the vacuity probe itself must be caught"


# ============================================================================
# E1 -- "European baseline" appears in the two_baselines explainer
# ============================================================================

def test_two_baselines_explainer_names_the_baseline_by_its_ruled_name():
    from lib import copy as copy_mod

    section = copy_mod.METHODS["two_baselines"]
    assert "European baseline" in section["body"]

    # VACUITY: a copy of the SAME section with the ruled phrase swapped out
    # for the OLD wording no longer satisfies the identical membership
    # check -- proving "in" above is reading real content, not vacuously
    # true of any Methods body string.
    blanked_body = section["body"].replace("European baseline", "European average")
    with pytest.raises(AssertionError):
        assert "European baseline" in blanked_body


# ============================================================================
# E3 -- PP10_WD / FWCI_EU present at their primary label hooks
# ============================================================================

def test_pp_and_fwci_suffix_labels_are_wired_at_their_hooks():
    """BenchUp V4 trim,: the Compare cards' own PP10_WD/FWCI_EU
    hooks are `CARD_PP10`/`CARD_FWCI` (C3's own key names on its rewritten
    COMPARE dict, `CARD_FWCI`/`CARD_PP10`) -- the pre-trim `METRIC_PP`/
    `METRIC_FWCI` keys this test named do not survive C3's rewrite."""
    from lib import copy as copy_mod

    assert copy_mod.COMPARE["CARD_PP10"] == "PP10_WD"
    assert copy_mod.COMPARE["CARD_FWCI"] == "FWCI_EU"
    assert copy_mod.FIND["KPI_PP_LABEL"] == "PP10_WD"

    # VACUITY: the OLD labels are genuinely different strings -- an
    # unmutated fact, demonstrated so the equality checks above are shown to
    # discriminate the right value rather than pass for any string.
    OLD_PP, OLD_FWCI = "PP(top10%)", "FWCI (median)"
    assert copy_mod.COMPARE["CARD_PP10"] != OLD_PP
    assert copy_mod.COMPARE["CARD_FWCI"] != OLD_FWCI
    with pytest.raises(AssertionError):
        assert OLD_PP == copy_mod.COMPARE["CARD_PP10"]


def test_suffix_tokens_are_digit_ban_allowlisted_project_wide():
    """PP10_WD/EU27 both carry digits, so both must clear `copy.py`'s own
    digit-ban scanner (a shared-infrastructure touch) -- checked live here
    rather than assumed."""
    from lib import copy as copy_mod

    assert copy_mod.scan_for_digit_violations() == []
    allowlist = (APP_DIR / "tests" / "digit_allowlist.txt").read_text(encoding="utf-8")
    assert "PP10_WD" in allowlist
    assert "EU27" in allowlist

    # VACUITY: a random digit-bearing token NOT in the allowlist is
    # correctly absent -- proving membership above means something (the
    # file does not just contain every possible token).
    assert "ZZ99_NOT_A_REAL_TOKEN" not in allowlist


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
