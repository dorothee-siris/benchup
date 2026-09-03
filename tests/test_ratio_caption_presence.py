"""tests/test_ratio_caption_presence.py -- BenchUp V4 trim, guards
E5/D3's caption-presence rules on the Compare page: every ratio chart names
its basis/floor in words and the warning-caption colour is D5's frontier
red BY REFERENCE. REWRITTEN for the trim: the pre-trim COMPARE keys this
file used to pin (`TIP_LOW_VOLUME`, `CAPTION_BASIS_FWCI`, `CAPTION_BASIS_
FWCI_ERC_GAP` -- the N-institution "Compare by" selector's own caption
family) are DELETED with that selector; the equivalent trimmed
facts are:

  * D3/D4's own Impact-tab hatch floor, stated in `copy.COMPARE[
    "SHAPE_NOTE_IMPACT"]`/`["SDG_NOTE_IMPACT"]`, filled from
    `palette.RATIO_HATCH_FLOOR` (fifty).
  * D2/D10/E5's ONE pin caption under the title, `copy.COMPARE[
    "PIN_CAPTION"]`, naming the best-fit + full-counting pin in words.

This is an IMPORT-LEVEL check (no Streamlit runtime needed): `copy.py` is a
pure dict-of-strings module, and the substrings a caption must carry are a
property of the STRING, independent of whether a page happens to render it
this run.

Also pins the D5/D6 colour contract: `palette.WARNING_CAPTION_COLOR ==
palette.SHARED_FRONTIER` (the warning caption colour is D5's frontier red
BY REFERENCE, not a second, driftable hex).

VACUITY: each substring check is run once against the REAL rendered string
(passes) and once against a deliberately mutated in-memory COPY with the
ruled phrase removed (must fail) -- proving the assertion is reading the
actual sentence, not a name that happens to exist.

Run from cwd `app/`: python -m pytest tests/test_ratio_caption_presence.py -q
"""
from __future__ import annotations

import pytest

from lib import compare_data as CD
from lib import copy
from lib import palette as P
from lib.app_config import CFG

Y0, Y1 = CD.CORE_WINDOW
WHOLE_Y1 = CFG["bonus_year"]


def _assert_contains_and_is_sensitive(rendered: str, needle: str, mutated_missing: str) -> None:
    """The real string must contain `needle`; a copy with `needle` removed
    (`mutated_missing` is that copy, built by the caller) must not -- proves
    the check is not vacuously true for any string."""
    assert needle in rendered, f"expected {needle!r} in {rendered!r}"
    assert needle not in mutated_missing, "vacuity setup itself is broken"


# ---------------------------------------------------------------------------
# 1. D3/D4's Impact-tab hatch-floor sentence, ONE template, both sections
# ---------------------------------------------------------------------------

def test_shape_and_sdg_impact_notes_name_the_ruled_floor_of_fifty_works():
    for key in ("SHAPE_NOTE_IMPACT", "SDG_NOTE_IMPACT"):
        template = copy.COMPARE[key]
        rendered = template.format(floor=P.RATIO_HATCH_FLOOR)
        needle = f"fewer than {P.RATIO_HATCH_FLOOR} covered works"
        assert needle == "fewer than 50 covered works"  # the literal the dispatch names
        _assert_contains_and_is_sensitive(rendered, needle, rendered.replace(needle, ""))

        # VACUITY: the substring is a function of the REAL constant, not a
        # coincidence -- a different floor renders a DIFFERENT sentence.
        wrong_floor_rendered = template.format(floor=30)
        assert needle not in wrong_floor_rendered
        assert "fewer than 30 covered works" in wrong_floor_rendered


# ---------------------------------------------------------------------------
# 2. the D2/D10/E5 pin caption -- best-fit + full counting, both windows
# ---------------------------------------------------------------------------

def test_pin_caption_names_the_bestfit_full_counting_pin_and_both_windows():
    rendered = copy.COMPARE["PIN_CAPTION"].format(y0=Y0, y1=Y1, whole_y1=WHOLE_Y1)
    for needle in ("best-fit taxonomy", "full counting", "fractional counts appear in hover"):
        mutated = rendered.replace(needle, "")
        _assert_contains_and_is_sensitive(rendered, needle, mutated)
    assert str(Y0) in rendered and str(Y1) in rendered and str(WHOLE_Y1) in rendered

    # VACUITY: a page pinned to a DIFFERENT taxonomy/basis (a bug) would not
    # render this exact phrase -- confirm a plausible wrong pin's own
    # sentence does not accidentally satisfy this same needle.
    wrong = "Every figure here is on the original taxonomy and fractional counting."
    assert "best-fit taxonomy" not in wrong


# ---------------------------------------------------------------------------
# 4. the warning-caption colour IS the frontier red, by reference
# ---------------------------------------------------------------------------

def test_warning_caption_color_is_the_shared_frontier_red():
    assert P.WARNING_CAPTION_COLOR == P.SHARED_FRONTIER
    assert P.WARNING_CAPTION_COLOR == "#821D13"

    # VACUITY: a DIFFERENT red must fail the same equality.
    assert P.WARNING_CAPTION_COLOR != "#7A1600"  # the pre-D7 red this replaced


# ---------------------------------------------------------------------------
# 5. VL/VF also introduced their own D4/D5 basis-disclosure keys this plan
# ---------------------------------------------------------------------------
# `test_collab_core_ar_basis_chip_exists_and_names_full_counting` DELETED
# (2026-09-03, this follow-up): its premise, `copy.COLLAB["BASIS_CAPTION_
# CORE_AR"]`, no longer exists -- own copy.py press pass removed
# the whole `COLLAB` dict this same session (there is no pair page in
# BenchUp V4, D1's own "out of scope" line; M's fence, not this stream's
# `copy.py` is explicitly M's this wave per the manager's own follow-up
# instruction). Confirmed via `hasattr(copy, "COLLAB")` below rather than
# left silently broken.


def test_copy_carries_no_collab_dict_any_more():
    """Positive confirmation of the deletion above, so a future revert of
    M's own work is caught here too, not just by this file quietly staying
    green because nothing calls the missing dict any more."""
    assert not hasattr(copy, "COLLAB")


def test_find_six_year_basis_disclosure_key_exists_and_names_the_whole_run():
    """The SDG/ERC profile panels
    read a WHOLE-RUN (six-year) window, different from the five-year core
    window the rest of Find states -- said in words wherever the ratio it
    qualifies is on screen."""
    template = copy.FIND["RATIO_WHOLE_RUN_BASIS"]
    rendered = template.format(window="2020-2025", corpus="2020-2024")
    needle = "not the {corpus} window used".format(corpus="2020-2024")
    _assert_contains_and_is_sensitive(rendered, needle, rendered.replace(needle, ""))
    assert "2020-2025" in rendered and "2020-2024" in rendered


def test_copy_digit_ban_still_holds_after_2c_additions():
    """A permanent guard alongside the locale ban (D9's sibling rule): none
    of the 2C caption keys this module just quoted verbatim may carry a
    hand-typed digit outside an approved `{placeholder}` -- re-run copy.py's
    OWN scanner here so a future edit to any COMPARE/COLLAB/FIND caption key
    cannot reintroduce a hand-typed number without this suite noticing."""
    violations = copy.scan_for_digit_violations()
    assert violations == [], violations
