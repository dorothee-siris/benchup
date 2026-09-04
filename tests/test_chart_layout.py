"""tests/test_chart_layout.py -- the bar-layout contract, systematically,
across every bar-family builder in `lib/charts.py` and `lib/charts_compare.py`:
ONE fixed label column + ONE fixed gutter column per view, ONE row pitch per
row-shape, ONE tick/gutter font pair, ONE red-dashed reference form (a
vertical tick spanning its row when the reference varies, a full-height line
when it is constant -- never a diamond, never a dot-and-stem). Per-builder
render checks (colours, hover, sort, empty states) stay in `tests/
test_charts.py` / `tests/test_charts_compare.py`; this file is the CONTRACT
a manager reads once, checked the same way on every builder that claims it.

Run from cwd `app/`: python -m pytest tests/test_chart_layout.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib import charts as C              # noqa: E402
from lib import charts_compare as X      # noqa: E402
from lib import palette as P             # noqa: E402

DATA = APP_DIR / "data"
FORBIDDEN_TEXT = "Publications, full count"


# ---------------------------------------------------------------------------
# 1. Fonts, one constant pair, shared by both modules
# ---------------------------------------------------------------------------
def test_tick_and_gutter_fonts_are_the_declared_constants():
    assert C.TICK_FONT_PX == 13
    assert C.GUTTER_FONT_PX == 12
    # charts_compare.py imports these rather than keeping its own copies
    assert X.C.TICK_FONT_PX == C.TICK_FONT_PX
    assert X.C.GUTTER_FONT_PX == C.GUTTER_FONT_PX


def test_pitch_and_bar_thickness_constants_are_declared_exactly():
    assert C.ROW_PITCH_SINGLE == 34 and C.BAR_PX_SINGLE == 20  # : 27 -> 34
    # a real two-line label at TICK_FONT_PX (13px) renders at ~15px per
    # line (measured); the pitch must clear that with >= 4px of breathing
    # room before the next row's own text -- see test_pitch_hosts_the_widest_wrap
    assert 2 * 15 + 4 <= C.ROW_PITCH_SINGLE
    assert C.ROW_PITCH_PAIR == 40 and C.BAR_PX_PAIR == 16


# ---------------------------------------------------------------------------
# 2. Fixtures -- small, synthetic, enough rows to measure pitch/bar geometry
#    from the figure without depending on any one seed's own data
# ---------------------------------------------------------------------------
def _fields_frame(n: int = 6) -> pd.DataFrame:
    return pd.DataFrame({
        "field_id": range(n), "field_name": [f"Field {i}" for i in range(n)],
        "domain_id": [(i % 4) + 1 for i in range(n)],
        "vol_full": [100 + 10 * i for i in range(n)], "vol_frac": [80.0 + i for i in range(n)],
        "share": [0.30 - 0.02 * i for i in range(n)], "si": [1.0 + 0.05 * i for i in range(n)],
    })


def _sdg_frame(n: int = 6) -> pd.DataFrame:
    return pd.DataFrame({
        "sdg_idx": range(n), "sdg_number": [i + 1 for i in range(n)],
        "sdg_label": [f"SDG {i + 1}" for i in range(n)],
        "share": [0.05 + 0.01 * i for i in range(n)], "esi": [1.0 + 0.1 * i for i in range(n)],
        "mass": [20.0 + i for i in range(n)],
    })


def _two_tab_frame(ids, n_rows: int = 6, *, grouped: bool = True) -> pd.DataFrame:
    rows = []
    for k, iid in enumerate(ids):
        for i in range(n_rows):
            rows.append(dict(
                row_id=i, row_label=f"Row {i}",
                group_label=(f"Field {i // 3}" if grouped else None),
                domain_id=(i % 4) + 1, institution_id=iid,
                value=0.05 + 0.01 * i + 0.002 * k, ref_value=0.06 + 0.001 * i,
                vol_full=100 + 10 * i + k, n_covered=60 + i, si=1.0 + 0.1 * i,
                fwci_median=1.0, vol_frac=50.0 + i,
            ))
    return pd.DataFrame(rows)


IDS = ["Ia", "Ib"]
SLOTS = {"Ia": 0, "Ib": 1}
NAMES = {"Ia": "Institution A", "Ib": "Institution B"}


# ---------------------------------------------------------------------------
# 3. margin.l == LABEL_COL_PX[view] + GUTTER_COL_PX[view] + pad, EVERY builder
# ---------------------------------------------------------------------------
FIND_BUILDERS = {
    "fig_share_si_fields": lambda: C.fig_share_si(_fields_frame(), family="oa", label_col="field_name",
                                                  volume_col="vol_full"),
    "fig_share_si_subfields": lambda: C.fig_share_si(
        _fields_frame().rename(columns={"field_id": "subfield_id", "field_name": "subfield_name"}),
        family="oa", label_col="subfield_name", volume_col="vol_full"),
    "fig_sdg": lambda: C.fig_sdg(_sdg_frame()),
    "fig_erc": lambda: C.fig_erc(pd.DataFrame({
        "panel_idx": range(6), "panel_code": [f"PE{i}" for i in range(6)],
        "panel_label": [f"Panel {i}" for i in range(6)], "erc_domain": ["PE"] * 6,
        "share": [0.1] * 6, "si": [1.0] * 6, "mass": [10.0] * 6,
    })),
}

COMPARE_BUILDERS = {
    "two_tab_bars_subfields_profile": lambda: X.two_tab_bars(
        _two_tab_frame(IDS, grouped=True), "profile", NAMES, SLOTS, grouped_by_field=True),
    "two_tab_bars_subfields_impact": lambda: X.two_tab_bars(
        _two_tab_frame(IDS, grouped=True), "impact", NAMES, SLOTS, grouped_by_field=True),
    "two_tab_bars_sdg_profile": lambda: X.two_tab_bars(
        _two_tab_frame(IDS, grouped=False), "profile", NAMES, SLOTS, grouped_by_field=False),
}


@pytest.mark.parametrize("name", sorted(FIND_BUILDERS))
def test_find_builders_margin_is_the_constant_label_and_gutter_columns(name):
    fig = FIND_BUILDERS[name]()
    expected = C.LABEL_COL_PX["find"] + C.GUTTER_COL_PX["find"] + C.COL_PAD_PX
    assert fig.layout.margin.l == expected, f"{name}: margin.l={fig.layout.margin.l}, expected {expected}"


@pytest.mark.parametrize("name", sorted(COMPARE_BUILDERS))
def test_compare_builders_margin_is_the_constant_label_and_gutter_columns(name):
    fig = COMPARE_BUILDERS[name]()
    expected = C.LABEL_COL_PX["compare"] + C.GUTTER_COL_PX["compare"] + C.COL_PAD_PX
    assert fig.layout.margin.l == expected, f"{name}: margin.l={fig.layout.margin.l}, expected {expected}"


# test_mirror_frontier_margin_is_the_compare_label_column -- DELETED (D31):
# `mirror_frontier` itself is retired, absorbed into Compare's topic
# overlap (`lib.charts_topics.balance_bars`, a separate module); that
# builder's own margin-column test lives in tests/test_charts_topics.py
# (`test_balance_bars_label_column_is_the_compare_constant`).


# ---------------------------------------------------------------------------
# 4. Row pitch and bar thickness, derived from the rendered figure -- not
#    re-asserting the constant against itself, but checking the GEOMETRY a
#    builder actually emits reproduces it.
# ---------------------------------------------------------------------------
def test_find_single_bar_builders_use_row_pitch_single_and_bar_px_single():
    for name, build in FIND_BUILDERS.items():
        fig = build()
        n = len(fig.data[0].y)
        assert fig.layout.height == C.row_height_single(n), name
        # bar thickness: with exactly one series and no explicit width, plotly
        # derives it from `bargap` -- (1 - bargap) * ROW_PITCH_SINGLE must equal
        # BAR_PX_SINGLE (the pitch this figure was actually given).
        bargap = fig.layout.bargap
        assert bargap == pytest.approx(C.BAR_GAP_SINGLE, abs=1e-9), name
        bar_px = (1.0 - bargap) * C.ROW_PITCH_SINGLE
        assert bar_px == pytest.approx(C.BAR_PX_SINGLE, abs=0.5), (name, bar_px)


def test_compare_two_series_builders_use_row_pitch_pair_and_bar_px_pair():
    for name, build in COMPARE_BUILDERS.items():
        fig = build()
        n_rows = max(int(y) for tr in fig.data if isinstance(tr, go.Bar) for y in tr.y) + 1
        assert fig.layout.height == C.row_height_pair(n_rows), name
        # explicit width per trace (offset/width geometry): convert the
        # category-unit width into px via ROW_PITCH_PAIR (1 category unit).
        widths = {tr.width for tr in fig.data
                 if isinstance(tr, go.Bar) and tr.marker.color != C.GUTTER_PHANTOM_FILL}
        assert len(widths) == 1, (name, widths)
        bar_px = list(widths)[0] * C.ROW_PITCH_PAIR
        assert bar_px == pytest.approx(C.BAR_PX_PAIR, abs=0.5), (name, bar_px)


# ---------------------------------------------------------------------------
# 5. No header text above the gutter, anywhere
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(list(FIND_BUILDERS) + list(COMPARE_BUILDERS)))
def test_no_builder_draws_the_retired_gutter_header_text(name):
    fig = FIND_BUILDERS[name]() if name in FIND_BUILDERS else COMPARE_BUILDERS[name]()
    for ann in fig.layout.annotations:
        assert ann.text != FORBIDDEN_TEXT, name
    for tr in fig.data:
        text = getattr(tr, "text", None) or ()
        assert FORBIDDEN_TEXT not in text, name


# `test_reciprocity_bars_no_header_either` retired here: strategic
# reciprocity by field is a bubble SCATTER again (`charts_compare.
# reciprocity_scatter`), not a bar-family builder -- the gutter-header
# contract this file's own docstring scopes to no longer applies to it at
# all. `tests/test_charts_compare.py` covers the scatter's own contract.


# ---------------------------------------------------------------------------
# 6. Reference shapes: dashed red, x0 == x1, spanning the row (varying) or
#    full height (constant) -- never a diamond, never a dot-and-stem trace.
# ---------------------------------------------------------------------------
def test_find_si_neutral_reference_is_one_full_height_red_dashed_line():
    fig = FIND_BUILDERS["fig_share_si_fields"]()
    lines = [s for s in fig.layout.shapes
            if s.line.color == P.WARNING_CAPTION_COLOR and s.type == "line"]
    assert len(lines) == 1, "SI=1 is CONSTANT across every row -> one rule, not one per row"
    line = lines[0]
    assert line.x0 == line.x1 == C.SI_NEUTRAL
    assert line.line.dash == "dash"
    assert line.line.width == C.LINE_PX
    # no stem/dot-and-stem trace survives
    assert not [tr for tr in fig.data if isinstance(tr, go.Scatter) and tr.mode == "lines"]


def test_compare_varying_reference_is_a_dashed_red_tick_per_row_spanning_its_band():
    df = _two_tab_frame(IDS, grouped=True)
    df.loc[df["row_id"] == 2, "ref_value"] = 0.5   # ensure genuine variation
    fig = X.two_tab_bars(df, "profile", NAMES, SLOTS, grouped_by_field=True)
    ticks = [s for s in fig.layout.shapes
            if s.line.color == P.WARNING_CAPTION_COLOR and s.line.dash == "dash"]
    assert len(ticks) == df["row_id"].nunique()
    for s in ticks:
        assert s.x0 == s.x1
        assert (s.y1 - s.y0) == pytest.approx(1.0)
    assert not [tr for tr in fig.data if isinstance(tr, go.Scatter)
               and getattr(tr.marker, "symbol", None) == "diamond-tall"]


def test_compare_constant_reference_is_one_full_height_red_dashed_line():
    df = _two_tab_frame(IDS, grouped=True)
    df["ref_value"] = 0.06   # identical on every row
    fig = X.two_tab_bars(df, "profile", NAMES, SLOTS, grouped_by_field=True)
    red_dashed = [s for s in fig.layout.shapes
                 if s.line.color == P.WARNING_CAPTION_COLOR and s.line.dash == "dash"]
    # a per-row TICK is anchored in DATA y-coordinates (yref="y"); the
    # CONSTANT rule (`add_vline`) is anchored in PAPER-relative domain
    # coordinates (yref="y domain", y0=0/y1=1) -- that is what "full height"
    # means mechanically, and the two must never be confused by span alone
    # (a row band also happens to span 1.0 unit).
    row_ticks = [s for s in red_dashed if s.yref != "y domain"]
    full_lines = [s for s in red_dashed if s.yref == "y domain"]
    assert not row_ticks, "a CONSTANT reference must be one rule, never one tick per row"
    assert len(full_lines) == 1
    assert full_lines[0].y0 == 0 and full_lines[0].y1 == 1, "full-height: spans the whole domain"
    assert full_lines[0].x0 == full_lines[0].x1 == pytest.approx(0.06)


def test_reference_red_is_the_validated_palette_token_not_a_new_literal():
    """The reference colour is `palette.WARNING_CAPTION_COLOR` -- already the
    validated red (`design-system/palette_validation.txt`), never a second
    hex invented for this contract."""
    assert P.WARNING_CAPTION_COLOR == P.SHARED_FRONTIER == "#821D13"


# ---------------------------------------------------------------------------
# 7. Compare SDG: profile-only (no tabs), and the accent square shows
# ---------------------------------------------------------------------------
def test_two_tab_bars_sdg_frame_can_carry_an_sdg_accent_via_sdg_number():
    """`views_compare._render_sdg` passes `accent_key_col="sdg_number"`
    through `_render_two_tab_section`'s `_frame()` helper -- this is the
    frame-level contract that fix relies on: `two_tab_bars`/`fig_metric_bars`
    already resolve an SDG accent from a `sdg_number` column when present
    (`_ACCENT_COLS["sdg"]`), the identical mechanism subfields use via
    `domain_id`."""
    df = _two_tab_frame(IDS, grouped=False)
    df["sdg_number"] = df["row_id"] + 1   # 1-based, matching palette.sdg_color's own convention
    fig = X.two_tab_bars(df, "profile", NAMES, SLOTS, grouped_by_field=False)
    styled = list(fig.layout.yaxis.ticktext)
    assert all(C.ACCENT_GLYPH in t for t in styled), "every SDG row must carry the accent square"
    expected_hexes = {P.sdg_color(n) for n in df["sdg_number"].unique()}
    assert any(h in "".join(styled) for h in expected_hexes)

    # VACUITY: withOUT sdg_number (today's un-patched frame shape) draws NO
    # accent at all -- proves the square above is the column's own effect.
    bare = _two_tab_frame(IDS, grouped=False)
    fig_bare = X.two_tab_bars(bare, "profile", NAMES, SLOTS, grouped_by_field=False)
    assert not any(C.ACCENT_GLYPH in t for t in fig_bare.layout.yaxis.ticktext)


# ---------------------------------------------------------------------------
# 8. Label-universe test: every label of {field, subfield, erc, sdg} wraps to
#    <= 2 lines within its OWN family's WRAP_PX using the committed glyph
#    table; topic ellipsis share < 1 % of the 4,516.
# ---------------------------------------------------------------------------
def _codebook():
    return pd.read_csv(APP_DIR / "lib" / "engine" / "resources" / "openalex_subfield_codebook_v1.csv",
                       usecols=["subfield_id", "subfield_name", "field_name"])


def _label_universe() -> dict:
    dim = pd.read_parquet(DATA / "topics_dim.parquet", columns=["topic_name"])
    cb = _codebook()
    erc = pd.read_csv(APP_DIR / "lib" / "engine" / "resources" / "erc_panels.csv")
    sdg = pd.read_csv(APP_DIR / "lib" / "engine" / "resources" / "sdg_labels.csv")
    return {
        "field": sorted(cb["field_name"].dropna().unique().tolist()),
        "subfield": sorted(cb["subfield_name"].dropna().unique().tolist()),
        "erc": sorted(erc["panel_label"].dropna().unique().tolist()),
        "sdg": sorted(sdg["sdg_label_numbered"].dropna().unique().tolist()),
        "topic": sorted(dim["topic_name"].dropna().unique().tolist()),
    }


@pytest.fixture(scope="module")
def label_universe() -> dict:
    return _label_universe()


FIND_FAMILIES = ("field", "subfield", "erc", "sdg")
COMPARE_FAMILIES = ("subfield", "sdg", "topic")
_ACCENT_FAMILIES_FIND = {"sdg"}          # only Find's SDG panel carries the square
_ACCENT_FAMILIES_COMPARE = {"subfield", "sdg", "topic"}   # every Compare family does


def _accent_w() -> float:
    return C.text_width_px(C.ACCENT_GLYPH) + C.text_width_px(C.ACCENT_GAP)


def _normalize_ws(text: str) -> str:
    """`wrap_label_px` (like its character-based sibling `wrap_label`) splits
    on Python's default whitespace rule and rejoins words with a SINGLE
    space -- a run of two-or-more spaces in the SOURCE text collapses to one.
    Found on the real 4,516-topic universe: exactly one topic name
    ("Media Discourse and Social  Analysis", a genuine upstream double-space
    in `topics_dim.parquet`, not introduced here) has this. Not a text-loss
    bug: SVG/HTML text rendering (what plotly actually draws) already
    collapses consecutive whitespace visually, so a reader never sees a
    difference -- this normalizes the SAME way before comparing, rather than
    asserting byte-for-byte identity on a distinction the render itself
    does not preserve."""
    return " ".join(text.split())


@pytest.mark.parametrize("family", FIND_FAMILIES)
def test_every_find_label_wraps_to_at_most_two_lines_at_the_view_wrap_px(label_universe, family):
    """WRAP_PX is now ONE budget PER VIEW (`WRAP_PX["find"]`), not one per
    family -- every Find family wraps at the SAME width, so a short family
    (Fields) is no longer forced to wrap far tighter than the column it
    actually sits in. Still verifies the same two invariants as before: no
    label exceeds two lines (barring the standing ellipsis safety net, at
    0 occurrences today), and no rendered line exceeds the column."""
    labels = label_universe[family]
    assert len(labels) > 0
    accent = _accent_w() if family in _ACCENT_FAMILIES_FIND else 0.0
    wrap_px = C.WRAP_PX["find"] - accent
    over = []
    for lab in labels:
        lines = C.wrap_label_px(lab, wrap_px)
        rejoined = " ".join(lines)
        if lines[0].endswith(C.ELLIPSIS) or (len(lines) > 1 and lines[-1].endswith(C.ELLIPSIS)):
            continue  # the standing ellipsis safety net, not a failure by itself
        if len(lines) > 2 or rejoined != _normalize_ws(lab):
            over.append(lab)
    assert not over, f"{family}: {len(over)}/{len(labels)} label(s) exceed 2 lines or lost text: {over[:5]}"
    col = C.LABEL_COL_PX["find"]
    worst = max(max(C.text_width_px(ln) for ln in C.wrap_label_px(lab, wrap_px)) + accent
               for lab in labels)
    assert worst <= col, f"{family}: widest wrapped line {worst:.1f}px exceeds LABEL_COL_PX['find']={col}"


@pytest.mark.parametrize("family", COMPARE_FAMILIES)
def test_every_compare_label_wraps_to_at_most_two_lines_at_the_view_wrap_px(label_universe, family):
    labels = label_universe[family]
    accent = _accent_w() if family in _ACCENT_FAMILIES_COMPARE else 0.0
    wrap_px = C.WRAP_PX["compare"] - accent
    col = C.LABEL_COL_PX["compare"]
    over = []
    for lab in labels:
        lines = C.wrap_label_px(lab, wrap_px)
        rejoined = " ".join(lines)
        if lines[0].endswith(C.ELLIPSIS) or (len(lines) > 1 and lines[-1].endswith(C.ELLIPSIS)):
            continue
        if len(lines) > 2 or rejoined != _normalize_ws(lab):
            over.append(lab)
            continue
        worst = max(C.text_width_px(ln) for ln in lines) + accent
        if worst > col:
            over.append(lab)
    assert not over, f"{family}: {len(over)}/{len(labels)} label(s) exceed the Compare column: {over[:5]}"


def test_topic_names_ellipsis_share_is_under_one_percent_of_4516(label_universe):
    """D28's own stated ceiling: topic names may fall back to an ellipsis for
    at most 1% of the universe in the Compare column, else the column must
    widen. Measured at zero occurrences at the (now view-level) wrap width;
    this test is the standing regression guard."""
    topics = label_universe["topic"]
    assert len(topics) >= 4000, "fixture must be the real, ~4,516-topic universe"
    accent = _accent_w()
    col = C.LABEL_COL_PX["compare"]
    wrap_px = C.WRAP_PX["compare"] - accent
    n_over = 0
    for name in topics:
        lines = C.wrap_label_px(name, wrap_px)
        needs_ellipsis = any(ln.endswith(C.ELLIPSIS) for ln in lines)
        worst = max(C.text_width_px(ln) for ln in lines) + accent
        if needs_ellipsis or worst > col:
            n_over += 1
    share = n_over / len(topics)
    assert share < 0.01, f"{n_over}/{len(topics)} topics ({share:.4%}) need an ellipsis -- widen the column"


def test_per_family_two_line_counts_reported(label_universe, capsys):
    """Not a pass/fail gate on its own (informational, per the manager's own
    follow-up request) -- prints, per family, how many labels need two
    lines at the (now generous, view-level) wrap width, so the count is
    read off a live run rather than hand-copied into a report."""
    accent = _accent_w()
    rows = []
    for view, families, accent_set in (
        ("find", FIND_FAMILIES, _ACCENT_FAMILIES_FIND),
        ("compare", COMPARE_FAMILIES, _ACCENT_FAMILIES_COMPARE),
    ):
        for fam in families:
            labels = label_universe[fam]
            a = accent if fam in accent_set else 0.0
            wrap_px = C.WRAP_PX[view] - a
            n2 = sum(1 for lab in labels if len(C.wrap_label_px(lab, wrap_px)) >= 2)
            rows.append((view, fam, n2, len(labels)))
    with capsys.disabled():
        print("\nper-family two-line counts at the view-level WRAP_PX:")
        for view, fam, n2, tot in rows:
            print(f"  {view:8s} {fam:10s} {n2:5d}/{tot:<5d} ({n2 / tot:.1%}) need 2 lines")
    assert rows


# ---------------------------------------------------------------------------
# 8b. Pitch vs wrap-line-height invariant (manager follow-up, item 2):
#    max_lines * 15 + 4 <= pitch, computed from the SAME wrap the constants
#    above use -- 15 px is the measured rendered line height of a two-line
#    label at TICK_FONT_PX (13 px), 4 px the minimum row-to-row breathing
#    room above that before the next row's own text.
# ---------------------------------------------------------------------------
LINE_HEIGHT_PX = 15
MIN_BREATHING_PX = 4


def test_pitch_hosts_the_widest_wrap_with_measured_line_height(label_universe):
    accent = _accent_w()
    for view, families, accent_set, pitch in (
        ("find", FIND_FAMILIES, _ACCENT_FAMILIES_FIND, C.ROW_PITCH_SINGLE),
        ("compare", COMPARE_FAMILIES, _ACCENT_FAMILIES_COMPARE, C.ROW_PITCH_PAIR),
    ):
        max_lines = 1
        for fam in families:
            a = accent if fam in accent_set else 0.0
            wrap_px = C.WRAP_PX[view] - a
            for lab in label_universe[fam]:
                max_lines = max(max_lines, len(C.wrap_label_px(lab, wrap_px)))
        needed = max_lines * LINE_HEIGHT_PX + MIN_BREATHING_PX
        assert needed <= pitch, (
            f"{view}: {max_lines}-line labels need {needed}px "
            f"(={max_lines}*{LINE_HEIGHT_PX}+{MIN_BREATHING_PX}) > pitch {pitch}px"
        )


@pytest.mark.parametrize("n_rows,n_series,pitch,fn", [
    (10, 1, C.ROW_PITCH_SINGLE, lambda n: C.row_height_single(n)),
    (10, 2, C.ROW_PITCH_PAIR, lambda n: C.row_height_pair(n)),
])
def test_two_line_row_fits_the_declared_pitch_directly(n_rows, n_series, pitch, fn):
    """The same invariant, stated directly against the two declared pitches
    (27->34 for single rows was the manager's own fix; pair stays 40) --
    two TICK_FONT_PX lines fit with the minimum breathing room, independent
    of any one family's own measured wrap."""
    assert 2 * LINE_HEIGHT_PX + MIN_BREATHING_PX <= pitch, (n_rows, n_series, pitch)


def test_glyph_widths_resource_is_committed_and_matches_the_live_font_contract():
    path = APP_DIR / "lib" / "resources" / "glyph_widths.json"
    assert path.exists(), "lib/resources/glyph_widths.json must be committed"
    import json
    with open(path, "r", encoding="utf-8") as f:
        table = json.load(f)
    assert table["label_font_px"] == C.TICK_FONT_PX
    assert table["gutter_font_px"] == C.GUTTER_FONT_PX
    assert f"widths_{C.TICK_FONT_PX}px" in table
    assert f"widths_{C.GUTTER_FONT_PX}px" in table
    assert len(table[f"widths_{C.TICK_FONT_PX}px"]) > 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
