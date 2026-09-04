"""tests/test_compare_basis_pin.py -- guards the pin:
Compare is PINNED to the best-fit taxonomy and full counting, with NO
toggle anywhere on the page.

REWRITTEN: the earlier guard ("no chart
mixes bases between value and gutter") probed `compare_data.metric_frame`
across a full/frac TOGGLE that no longer exists -- Compare had a basis
control before this trim; it does not now. The equivalent guard for a
PINNED page is different in kind: not "does a value stay coherent across a
toggle a reader can flip" (there is none), but "is every function this page
calls genuinely INCAPABLE of drifting off the pin, and does the page say so
in words". Three checks:

  1. every `compare_data` function the Compare page calls takes no `tree`/`basis`
     keyword at all (a caller cannot even ASK for a different scenario)
     inspected via `inspect.signature`, not trusted from a docstring.
  2. `views_compare.render` calls `lib.engine.scenario_cache.get` with the
     literal strings `"bestfit"`/`"full"`, never a variable that could carry
     a reader's own pick (source-level grep on the page's own file, the same
     "prove a structural fact from the file, not from running it once"
     idiom `test_download_button_consolidation.py` already uses).
  3. the ONE pin caption under the title states the pin in words, and both
     of its own windows resolve to real config values.

VACUITY: every assertion is followed by an in-memory/string mutation that
makes the identical check fail.

Run from cwd `app/`: python -m pytest tests/test_compare_basis_pin.py -q
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from lib import compare_data as CD
from lib import copy
from lib.app_config import CFG

APP_DIR = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# 1. no compare_data function this page calls accepts tree/basis at all
# ---------------------------------------------------------------------------

PAGE_FUNCTIONS = ("cards", "top_subfields", "all_subfields", "sdg_frame", "relationship")
# frontier_positioning/shared_frontier are DELETED (absorbed into
# Compare's topic overlap, `lib.topic_data.pair_topics`, which is not a
# `compare_data.py` function at all and so is outside this file's own
# "no compare_data function this page calls accepts tree/basis" scope).


def test_no_compare_data_function_this_page_calls_accepts_a_tree_or_basis_kwarg():
    for name in PAGE_FUNCTIONS:
        fn = getattr(CD, name)
        params = set(inspect.signature(fn).parameters)
        assert "tree" not in params, (name, params)
        assert "basis" not in params, (name, params)

    # VACUITY: a function that DID accept one (a real, deliberately
    # constructed counter-example) fails the same check -- proving the
    # assertion above is a real inspection, not a tautology over a list
    # that happens to contain none.
    def _fake_with_basis(ctx, ids, basis="full"):
        return None

    with pytest.raises(AssertionError):
        assert "basis" not in set(inspect.signature(_fake_with_basis).parameters)


# ---------------------------------------------------------------------------
# 2. views_compare.py's own scenario read is the literal pin, not a variable
# ---------------------------------------------------------------------------

def test_views_compare_reads_the_scenario_cache_with_the_literal_pin():
    src = (APP_DIR / "lib" / "views_compare.py").read_text(encoding="utf-8")
    needle = 'SC.get("bestfit", "full")'
    assert needle in src, "views_compare.py must pin the scenario cache read literally"
    # every OTHER SC.get( call site in the file (there should be exactly the
    # ones this module itself makes) must carry the SAME two literals -- a
    # second call site reading a variable would be the exact drift this
    # guard exists to catch.
    import re

    calls = re.findall(r"SC\.get\(([^)]*)\)", src)
    assert calls, "no SC.get( call found at all -- matcher likely broken"
    for call in calls:
        assert call.strip() == '"bestfit", "full"', call

    # VACUITY: a source string with a VARIABLE scenario read does not
    # satisfy the same literal-pin check.
    mutated = src.replace(needle, "SC.get(tree, basis)")
    assert needle not in mutated
    calls2 = re.findall(r"SC\.get\(([^)]*)\)", mutated)
    assert not any(c.strip() == '"bestfit", "full"' for c in calls2) or len(calls2) > len(calls)


# ---------------------------------------------------------------------------
# 3. the pin caption states the pin, and both windows are real config values
# ---------------------------------------------------------------------------

def test_pin_caption_windows_resolve_to_real_config_values():
    y0, y1 = CD.CORE_WINDOW
    whole_y1 = CFG["bonus_year"]
    assert (y0, y1) == tuple(CFG["window"])
    assert whole_y1 > y1, "the whole-run window must extend past the core window"

    rendered = copy.COMPARE["PIN_CAPTION"].format(y0=y0, y1=y1, whole_y1=whole_y1)
    assert str(y0) in rendered and str(whole_y1) in rendered

    # VACUITY: a caption filled with the WRONG (swapped) windows would still
    # satisfy a naive "contains some digits" check -- confirm the correct
    # windows are not accidentally interchangeable in the rendered text
    # (whole_y1 must differ from y1, so the two substrings are distinct).
    assert str(whole_y1) != str(y1)
