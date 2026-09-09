"""tests/test_hover_format.py -- the bold-colon hover
contract, checked once, generically, across every builder that emits
`customdata` (`docs/tooltip_spec.yaml`'s `label_style: bold_colon`).

Reuses the plain frame-building FUNCTIONS the other chart test modules
already define (not their pytest-fixture-injected real-data ones, which would
need the pytest fixture graph to run standalone here) -- these functions are
the same synthetic-but-representative shapes those modules' own hover-order
tests already exercise, so this file adds no new frame contract, only a new,
builder-agnostic sweep over the RENDERED TEXT every one of them produces.

Run from cwd `app/`: python -m pytest tests/test_hover_format.py -q
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib import charts as C                       # noqa: E402
from lib import charts_compare as XC              # noqa: E402
from lib import charts_topics as XT                # noqa: E402

from tests.test_charts_compare import (            # noqa: E402
    two_tab_frame, yearly_frame, reciprocity_frame,
    IDS as COMPARE_IDS, NAMES as COMPARE_NAMES,
)
from tests.test_charts_topics import (             # noqa: E402
    _impact_frame, _overlay_frame, _balance_rows,
    SLOTS as TOPIC_SLOTS, NAMES as TOPIC_NAMES, IDS as TOPIC_IDS,
)

# ---------------------------------------------------------------------------
# The house regex, verbatim from this stream's own acceptance criterion:
#   * line 1 matches ^<b>[^<]+</b>  (the bold entity, no label, no colon)
#   * every OTHER line matches ^<b>[^<:]+</b>: .. OR is the keywords
#     continuation line (the line right after one starting with
#     "<b>keywords</b>: ")
# ---------------------------------------------------------------------------
LINE1_RE = re.compile(r"^<b>[^<]+</b>")
LABEL_LINE_RE = re.compile(r"^<b>[^<:]+</b>: ")
KEYWORDS_OPEN_RE = re.compile(r"^<b>keywords</b>: ")
MAX_HOVER_LINES = 8


def _assert_hover_format(hover: str) -> None:
    lines = hover.split("<br>")
    assert lines, f"empty hover: {hover!r}"
    assert LINE1_RE.match(lines[0]), f"line 1 is not the bold entity: {lines[0]!r} (hover: {hover!r})"
    assert not lines[0].startswith("<b>keywords</b>"), \
        f"line 1 must be the entity, never the keywords line: {hover!r}"

    n_capped_lines = 0   # the keywords PAIR counts as 2 against the cap, every other line as 1
    i = 1
    n_capped_lines += 1  # line 1 (the entity) always counts as 1
    while i < len(lines):
        ln = lines[i]
        if KEYWORDS_OPEN_RE.match(ln):
            n_capped_lines += 2
            i += 1   # the keywords continuation line carries no label of its own
        else:
            assert LABEL_LINE_RE.match(ln), (
                f"line {i + 1} is neither '<b>label</b>: value' nor a keywords "
                f"continuation: {ln!r} (hover: {hover!r})")
            n_capped_lines += 1
        i += 1
    assert n_capped_lines <= MAX_HOVER_LINES, (
        f"hover exceeds the {MAX_HOVER_LINES}-line cap ({n_capped_lines} counted): {hover!r}")


def _customdata_of(fig) -> list[str]:
    out: list[str] = []
    for tr in fig.data:
        cd = getattr(tr, "customdata", None)
        if cd is None:
            continue
        for h in cd:
            if h:   # the balance_bars gutter trace ships "" (hoverinfo="skip") -- not a hover
                out.append(str(h))
    return out


# ---------------------------------------------------------------------------
# One synthetic frame per Find bar family (find_fields / find_subfields /
# find_sdg / find_erc): `fig_share_si` is the ONE builder behind all four
# (`lib/charts.py`'s own module docstring for that section) -- one frame,
# carrying every optional column (si, fwci, pp10), exercises every line each
# of the four callers can draw.
# ---------------------------------------------------------------------------
def _share_si_frame(label_col: str, *, with_field_name: bool) -> pd.DataFrame:
    n = 6
    d = pd.DataFrame({
        label_col: [f"{label_col} {i}" for i in range(n)],
        "share": np.linspace(0.02, 0.30, n),
        "vol_full": np.arange(10, 10 + n * 10, 10),
        "vol_frac": np.linspace(5.0, 55.0, n),
        "mass": np.linspace(3.0, 33.0, n),
        "si": np.linspace(0.5, 2.0, n),
        "si_status": ["solid"] * n,
        "fwci_mean": np.linspace(0.5, 2.5, n),
        "fwci_median": np.linspace(0.4, 2.0, n),
        "n_covered": np.linspace(3, 60, n),
        "pp10_wd": np.linspace(0.01, 0.25, n),
        "n_covered_pp": np.linspace(1, 60, n),
    })
    if with_field_name and label_col != "field_name":
        d["field_name"] = "Some Field"
    return d


def _hovers_share_si() -> list[str]:
    out = []
    out += _customdata_of(C.fig_share_si(_share_si_frame("field_name", with_field_name=False),
                                          family="oa", share_hover_label=C.HOVER_SHARE_CLASSIFIED))
    out += _customdata_of(C.fig_share_si(_share_si_frame("subfield_name", with_field_name=True),
                                          family="oa", share_hover_label=C.HOVER_SHARE_CLASSIFIED))
    out += _customdata_of(C.fig_share_si(_share_si_frame("sdg_label", with_field_name=False),
                                          family="sdg", share_hover_label=C.HOVER_SHARE_TAGGED_INST,
                                          mass_hover_label=C.HOVER_MASS_TAGGED_RUN))
    out += _customdata_of(C.fig_share_si(_share_si_frame("panel_label", with_field_name=False),
                                          family="erc", share_hover_label=C.HOVER_SHARE_CLASSIFIED_INST,
                                          mass_hover_label=C.HOVER_MASS_CLASSIFIED_RUN))
    return out


def _hovers_breakdowns() -> list[str]:
    labels = ["Domain A", "Domain B", "Domain C"]
    totals = [120.0, 80.0, 40.0]
    colors = ["#111111", "#222222", "#333333"]  # not under lib/ -- a test literal, not a chart one
    out = _customdata_of(C.fig_breakdown_global(labels, totals, colors))
    years = ["2020", "2021", "2022"]
    series = ["domA", "domB"]
    ylabels = {"domA": "Domain A", "domB": "Domain B"}
    ycolors = {"domA": "#111111", "domB": "#222222"}
    ytotals = {"domA": [10.0, 20.0, 30.0], "domB": [5.0, 15.0, 25.0]}
    out += _customdata_of(C.fig_breakdown_yearly(years, series, ylabels, ycolors, ytotals))
    return out


def _hovers_topic_planes() -> list[str]:
    out = _customdata_of(XT.fig_plane_impact(_impact_frame()))
    out += _customdata_of(XT.fig_plane_frontier(_impact_frame(), color_by=XT.COLOR_BY_DOMAIN))
    overlay = _overlay_frame()
    out += _customdata_of(XT.fig_plane_frontier(
        overlay, color_by=XT.COLOR_BY_OWNER, slots=TOPIC_SLOTS, names=TOPIC_NAMES, ids=TOPIC_IDS))
    rows = _balance_rows()
    out += _customdata_of(XT.balance_bars(rows, TOPIC_IDS, slots=TOPIC_SLOTS, names=TOPIC_NAMES,
                                          sort_col="n_ar_combined"))
    return out


def _hovers_compare_bars() -> list[str]:
    slots = {k: i for i, k in enumerate(COMPARE_IDS)}
    out = []
    for grouped in (True, False):
        df = two_tab_frame(COMPARE_IDS, grouped_by_field=grouped)
        for tab in ("profile", "impact"):
            fig = XC.two_tab_bars(df, tab, COMPARE_NAMES, slots, grouped_by_field=grouped)
            out += _customdata_of(fig)
    return out


def _hovers_compare_relationship() -> list[str]:
    out = _customdata_of(XC.yearly_domain_stack(yearly_frame()))
    out += _customdata_of(XC.reciprocity_scatter(
        reciprocity_frame(with_ranks=True), list(COMPARE_NAMES.values())[:2], [0, 1]))
    return out


ALL_HOVER_SOURCES = {
    "find_fields/find_subfields/find_sdg/find_erc": _hovers_share_si,
    "find_breakdown_global/find_breakdown_yearly": _hovers_breakdowns,
    "find_plane_impact/find_plane_frontier/compare_topic_overlay/compare_balance_bars": _hovers_topic_planes,
    "compare_thematic_profile/compare_thematic_impact/compare_sdg": _hovers_compare_bars,
    "compare_yearly_stack/compare_reciprocity": _hovers_compare_relationship,
}


@pytest.mark.parametrize("source_name", list(ALL_HOVER_SOURCES))
def test_every_hover_is_bold_colon_formatted(source_name):
    hovers = ALL_HOVER_SOURCES[source_name]()
    assert hovers, f"{source_name} produced no hovers to check"
    for h in hovers:
        _assert_hover_format(h)


def test_at_least_one_topic_hover_carries_the_catch_all_flag_outside_the_bold_name():
    """`_impact_frame`'s row 2 is `is_excluded=True` -- the flag clause
    ('- catch-all topic: ...') must sit OUTSIDE the bold span, and line 1
    must still match the entity regex as a whole line."""
    hovers = _customdata_of(XT.fig_plane_impact(_impact_frame()))
    flagged = [h for h in hovers if "catch-all topic" in h]
    assert flagged, "fixture row 2 should have produced a flagged hover"
    for h in flagged:
        line1 = h.split("<br>")[0]
        assert LINE1_RE.match(line1)
        assert "catch-all topic" in line1 and "catch-all topic" not in re.match(r"<b>.*?</b>", line1).group()


def test_keywords_line_is_labelled_once_on_two_lines():
    hovers = _customdata_of(XT.fig_plane_impact(_impact_frame()))
    assert hovers
    for h in hovers:
        lines = h.split("<br>")
        kw_idx = [i for i, ln in enumerate(lines) if ln.startswith("<b>keywords</b>: ")]
        assert len(kw_idx) == 1, h
        i = kw_idx[0]
        assert i + 1 < len(lines), "the keywords pair needs a second line"
        assert not lines[i + 1].startswith("<b>"), \
            "the keywords continuation line carries no label of its own"
