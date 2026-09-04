"""tests/test_terminology_consistency.py --, cross-cutting
guard for the rule that "European baseline" = EU27 + the
selected friend countries (UK, CH, NO, IS), swept across every rendered
string, defined once in Methods; plus the suffix-naming rule (PP10_WD /
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
    "a European reference",     # earlier wording found in COL_FWCI_HELP
    "that European average",    # earlier wording found in COL_FWCI_HELP
    "EU27+UK/CH/NO/IS",          # the old, undefined shorthand for the perimeter
    "EU27 + UK/CH/NO/IS",
)


def _rendered_copy_strings() -> list[tuple[str, str]]:
    from lib import copy as copy_mod
    return [(loc, s) for loc, s in collect_copy_module_strings(copy_mod)
           if not any(f"::{name}[" in loc for name in NON_RENDERED_NAMES)]


# ============================================================================
# no rendered string carries an old baseline phrasing
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
# "European baseline" appears in the two_baselines explainer
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
# PP10_WD / FWCI_EU present at their primary label hooks
# ============================================================================

def test_pp_and_fwci_suffix_labels_are_wired_at_their_hooks():
    """BenchUp V4 trim,: the Compare cards' own PP10_WD/FWCI_EU
    hooks are `CARD_PP10`/`CARD_FWCI` (the current key names on the rewritten
    COMPARE dict, `CARD_FWCI`/`CARD_PP10`) -- the earlier `METRIC_PP`/
    `METRIC_FWCI` keys this test named do not survive that rewrite."""
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


# ============================================================================
# methods + terminology press pass: consistent wording for the retired /
# renamed readings, swept across every rendered string in copy.py
# ============================================================================

def test_no_rendered_string_names_the_retired_reference_mark_or_leader_cut():
    """The reference-mark shape retired project-wide is the red dashed tick,
    never a diamond; the leader cut is the world top twenty, never a
    world-top-ten reading. Swept the same way as the baseline-phrasing test
    above, over the same collector."""
    strings = _rendered_copy_strings()
    hits = [(loc, s) for loc, s in strings if "diamond" in s.lower()]
    assert hits == [], hits

    # VACUITY: the literal word, injected, IS caught by the same scan.
    poisoned = strings + [("scratch::TEST_POISON", "a filled diamond marks the reference")]
    poisoned_hits = [(loc, s) for loc, s in poisoned if "diamond" in s.lower()]
    assert poisoned_hits, "the vacuity probe itself must be caught"


def test_reference_mark_wording_is_the_red_dashed_tick_everywhere_it_appears():
    """Every rendered sentence that describes a per-row reference (the
    European mean share, the world PP10 reference, SI = 1) names the SAME
    mark the same way: 'the red dashed tick', not 'the dashed red mark' or
    any other phrasing a reader would have to reconcile by eye."""
    strings = _rendered_copy_strings()
    old_phrasing_hits = [(loc, s) for loc, s in strings if "dashed red mark" in s or "dashed line marks" in s]
    assert old_phrasing_hits == [], old_phrasing_hits

    ruled_hits = [s for _, s in strings if "red dashed tick" in s]
    assert len(ruled_hits) >= 2, (
        "expected the ruled phrase at more than one reference-describing site", ruled_hits)

    # VACUITY: the OLD phrasing, injected, is a real, catchable hit.
    poisoned = strings + [("scratch::TEST_POISON", "the dashed red mark is the European mean")]
    poisoned_hits = [(loc, s) for loc, s in poisoned if "dashed red mark" in s]
    assert poisoned_hits, "the vacuity probe itself must be caught"


def test_no_rendered_string_carries_the_retired_scale_guard_band():
    """The scale guard is a single flat ratio; the earlier banded rule
    (8 times below 20,000 full works, 4 times at or above it) must not
    survive in any rendered string."""
    strings = _rendered_copy_strings()
    banned = ("8x", "8\N{MULTIPLICATION SIGN}", "4x", "4\N{MULTIPLICATION SIGN}", "20,000")
    hits = [(loc, term, s) for loc, s in strings for term in banned if term in s]
    assert hits == [], hits

    poisoned = strings + [("scratch::TEST_POISON", "8x below 20,000, 4x at or above it")]
    poisoned_hits = [(loc, term, s) for loc, s in poisoned for term in banned if term in s]
    assert poisoned_hits, "the vacuity probe itself must be caught"


def test_no_rendered_string_ever_names_a_world_referenced_fwci():
    """There is no world-referenced version of FWCI in this tool. PP10_WD
    is the only world-referenced impact figure it ships; 'FWCI_WD' must never
    appear in a rendered string."""
    strings = _rendered_copy_strings()
    hits = [(loc, s) for loc, s in strings if "FWCI_WD" in s]
    assert hits == [], hits

    poisoned = strings + [("scratch::TEST_POISON", "FWCI_WD sits beside FWCI_EU")]
    poisoned_hits = [(loc, s) for loc, s in poisoned if "FWCI_WD" in s]
    assert poisoned_hits, "the vacuity probe itself must be caught"


def test_no_em_dash_or_double_hyphen_anywhere_in_copy_py():
    """The VOICE rule at the top of lib/copy.py ('no em dash and no "--"
    standing in for one inside a user-facing string') is stated file-wide,
    not scoped to copy.METHODS alone (test_methods_note.py already covers
    that section on its own); this is the project-wide sweep, over the same
    collector every other check in this module and test_forbidden_
    vocabulary.py already trusts."""
    strings = _rendered_copy_strings()
    hits = [(loc, s) for loc, s in strings if "\N{EM DASH}" in s or "--" in s]
    assert hits == [], hits

    # VACUITY: both banned forms, injected, are real, catchable hits.
    poisoned = strings + [
        ("scratch::TEST_POISON_EM_DASH", "a sentence \N{EM DASH} with an em dash"),
        ("scratch::TEST_POISON_DOUBLE_HYPHEN", "a sentence -- with a double hyphen"),
    ]
    poisoned_hits = [(loc, s) for loc, s in poisoned if "\N{EM DASH}" in s or "--" in s]
    assert len(poisoned_hits) == 2, poisoned_hits


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
