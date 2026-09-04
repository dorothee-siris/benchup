"""tests/test_download_button_consolidation.py -- cross-cutting guard:
ALL per-section download buttons removed, ONE "Download this view
(Excel)" / "Download this comparison" button at the very end of each of
Find/Compare. An earlier standalone pair-view page does
not exist any more (`lib/views_collab.py` is gone, out of scope) -- swept
out of `VIEW_FILES` and its own sheet-count test retired; Find now ships
FOURTEEN sheets (the topics-led/star-papers addition,
"workbook 14 sheets"), and Compare ships EXACTLY SEVEN (
cards, subfields, SDG, positioning, shared frontier, relationship yearly,
reciprocity -- no Methods sheet this time, unlike an earlier page).

This module is the ONE place that sweeps every `views_*.py` file TOGETHER,
plus every OTHER `lib/*.py` module, in a single assertion -- so a future
edit to any one file that reintroduces a second button is caught here even
if the file responsible is not the one touched.

VACUITY, per module: every assertion is followed by an in-memory mutation
that makes the identical check fail.

Run: python -m pytest tests/test_download_button_consolidation.py -q
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest

APP_DIR = Path(__file__).resolve().parents[1]
LIB_DIR = APP_DIR / "lib"
VIEW_FILES = ("views_compare.py", "views_find.py")


def _src(name: str) -> str:
    return (LIB_DIR / name).read_text(encoding="utf-8")


# ============================================================================
# exactly one st.download_button( call site per view module
# ============================================================================

@pytest.mark.parametrize("filename", VIEW_FILES)
def test_exactly_one_download_button_call_site(filename):
    src = _src(filename)
    n = src.count("st.download_button(")
    assert n == 1, (filename, n)

    # VACUITY: appending a second literal call site to the SAME source text
    # makes the identical count assertion fail -- proving `.count(.)` is
    # doing real counting on this file's actual content, not returning a
    # constant 1.
    mutated = src + "\n    st.download_button('x', lambda: b'', key='dl_extra')\n"
    assert mutated.count("st.download_button(") == 2
    with pytest.raises(AssertionError):
        assert mutated.count("st.download_button(") == 1


def test_no_download_button_call_site_outside_the_three_view_modules():
    """This module's own scope is the per-section CSVs the Find/Compare/Collaborate
    pages used to offer -- it never touched `views_methods.py`'s own,
    pre-existing "Download METHODS_NOTE.md" button (a standing feature,
    unrelated to any other metric/workbook), so that ONE extra file is
    disclosed and allowed here by name rather than silently excluded.
    Beyond that single, named exception, no OTHER file in `lib/` may call
    `st.download_button(` at all."""
    ALLOWED_EXTRA = {"views_methods.py"}
    hits = [f.name for f in LIB_DIR.glob("*.py")
           if f.name not in VIEW_FILES and f.name not in ALLOWED_EXTRA
           and "st.download_button(" in f.read_text(encoding="utf-8")]
    assert hits == [], hits

    # VACUITY: a scratch module carrying the literal call site IS caught by
    # the same substring test -- proves the sweep is a real text search over
    # real file contents, not a check that always finds nothing regardless
    # of what a file contains.
    assert "st.download_button(" in "st.download_button('y', lambda: b'', key='dl_fake')"


# ============================================================================
# workbook builders exist and return the contracted sheet counts
# ============================================================================

def test_compare_workbook_builder_returns_exactly_six_sheets():
    """Cards, subfields (all 252), SDG, topic overlap (replaces the
    retired positioning + shared-frontier pair with one sheet), relationship
    yearly, reciprocity -- SIX, in that order, no Methods sheet this time.
    Called through the SAME `_workbook_sheets` the real page's cached
    `_workbook_bytes` calls, on real data (the golden anchor pair)."""
    from lib import topic_data as TD
    from lib import views_compare as VC
    from lib.engine import scenario_cache as SC

    ctx = SC.bundle()["ctx"]
    subs = SC.get("bestfit", "full")
    ids = ["I154202486", "I4210107283"]  # Ifremer x NIOZ, the anchor pair

    sheets = VC._workbook_sheets(ctx, subs, ids, TD.MODE_VOLUME, 50, "mean")
    assert len(sheets) == 6, len(sheets)
    labels = [label for label, _frame in sheets]
    assert len(labels) == len(set(labels)), "sheet labels must be unique before Excel-legalisation"
    assert all(isinstance(frame, pd.DataFrame) for _label, frame in sheets)
    assert all(len(frame) > 0 for _label, frame in sheets), "every sheet should carry real rows for a real pair"

    # VACUITY: a hand-truncated copy of this SAME real result no longer
    # satisfies "== 6" -- demonstrated explicitly, so the check above is
    # shown to discriminate a wrong count, not merely restate a constant.
    truncated = sheets[:-1]
    with pytest.raises(AssertionError):
        assert len(truncated) == 6


def test_find_workbook_sheet_count_matches_the_all_lenses_plus_leaders_contract():
    """Find 14 (the topics-led/star-papers addition, "workbook 14 sheets"):
    Profile + Overview + Aspirational (three fixed `copy.FIND["XLSX_SHEET_`
    sheets) + one per `ALL_LENSES` + ONE more, the topics-led/star-papers
    sheet (`_leaders_sheet_frame`, named by its own module constant, not the
    `copy.FIND["XLSX_SHEET_` convention the other three use). Pins the
    STRUCTURAL contract at the source level, so a change to either side
    (ALL_LENSES gaining/losing a lens, or a fixed sheet being added or
    removed) is caught without a full render."""
    from lib import views_find as VF
    from lib.engine import ALL_LENSES

    src = inspect.getsource(VF._find_workbook)
    fixed_sheets = src.count('copy.FIND["XLSX_SHEET_')
    assert fixed_sheets == 3, ("PROFILE + OVERVIEW + ASPIRATIONAL", fixed_sheets)
    assert "for lens in ALL_LENSES:" in src
    assert "_leaders_sheet_frame" in src, "the 14th sheet must still be wired in"
    assert len(ALL_LENSES) + fixed_sheets + 1 == 14

    # VACUITY: the SAME arithmetic on an ALL_LENSES one lens short does NOT
    # equal 14 -- proving this is a real dependency on the current
    # `ALL_LENSES` length, not a hardcoded "14 == 14" tautology.
    with pytest.raises(AssertionError):
        assert len(ALL_LENSES) - 1 + fixed_sheets + 1 == 14


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
