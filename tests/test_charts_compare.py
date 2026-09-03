"""tests/test_charts_compare.py -- BenchUp V4 trim,.

Every `lib/charts_compare.py` builder is exercised against the frame
contracts documented in each builder's own docstring; the module's source is
scanned for a colour literal and for a digit inside a string literal, the
same house rules `tests/test_charts.py` enforces on `lib/charts.py`.

The frames are built INLINE, from `lib/charts_compare.py`'s own builder
docstrings, rather than imported from `lib/compare_data.py`: that module is
, built in a later wave, and this test must not block on it. The
column names below ARE the contract the charts must satisfy.

Run from cwd `app/`: python -m pytest tests/test_charts_compare.py -q
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib import charts as C                 # noqa: E402
from lib import charts_compare as X         # noqa: E402
from lib import palette as P                # noqa: E402
from tests.test_narrative import has_digit_violation, load_allowlist  # noqa: E402

MODULE = APP_DIR / "lib" / "charts_compare.py"
DATA = APP_DIR / "data"

IDS = ["Iz", "Ia"]                       # deliberately NOT in id order
KEYS = {"Iz": 11, "Ia": 22}
NAMES = {"Iz": "Institution Z", "Ia": "Institution A"}


@pytest.fixture
def slots() -> dict:
    # slot = rank by ascending inst_key, id insertion order does not matter
    return {k: i for i, k in enumerate(sorted(KEYS, key=KEYS.get))}


# ---------------------------------------------------------------------------
# Inline frames -- exactly the shapes each builder's own docstring documents
# ---------------------------------------------------------------------------
def two_tab_frame(ids, *, grouped_by_field: bool) -> pd.DataFrame:
    n_covered = [80, 40, 90, 30, 70, 20]   # alternates above/below the floor of fifty
    rows = []
    for n, iid in enumerate(ids):
        for i in range(6):
            rows.append(dict(
                row_id=i, row_label=f"Row {i}",
                group_label=(f"Field {i // 3}" if grouped_by_field else None),
                domain_id=(i % 4) + 1,
                institution_id=iid,
                value=0.05 + 0.01 * i + 0.002 * n,
                ref_value=0.06,
                vol_full=100 + 10 * i + n,
                n_covered=n_covered[i],
                si=1.0 + 0.1 * i, fwci_median=1.05 + 0.02 * i, vol_frac=60.0 + i,
            ))
    return pd.DataFrame(rows)


def mirror_frame(n_rows: int = 4) -> pd.DataFrame:
    rows = []
    for i in range(n_rows):
        rows.append(dict(
            topic_id=1000 + i, topic_name=f"Topic {i}",
            url_joint=f"https://openalex.org/works?filter=topic.id:T{i}",
            vol_a=10.0 + i, vol_b=8.0 + i,
            vol_joint=(np.nan if i == 1 else 6.0 + i),
            expansion=0.3 * i - 0.5, acceleration=0.1 * i,
            is_top_decile=(i % 2 == 0),
        ))
    return pd.DataFrame(rows)


def yearly_frame() -> pd.DataFrame:
    years = list(range(2020, 2025))
    domains = [(1, "Physical Sciences"), (2, "Health Sciences"),
               (3, "Life Sciences"), (4, "Social Sciences")]
    rows = []
    for y in years:
        for did, dname in domains:
            rows.append(dict(year=y, domain_id=did, domain_name=dname,
                             vol=float(5 + did + (y - 2020))))
    return pd.DataFrame(rows)


def reciprocity_frame(n_fields: int = 4, with_ranks: bool = True) -> pd.DataFrame:
    """The WIDE, one-row-per-field contract
    field_id, field_name, domain_id, vol_joint, share_a, share_b, and the
    OPTIONAL rank_in_a/rank_in_b."""
    rows = []
    for f in range(n_fields):
        row = dict(field_id=f, field_name=f"Field {f}", domain_id=(f % 4) + 1,
                  vol_joint=float(40 - 8 * f), share_a=0.05 + 0.01 * f,
                  share_b=0.04 + 0.015 * f)
        if with_ranks:
            row["rank_in_a"] = f + 1
            row["rank_in_b"] = n_fields - f
        rows.append(row)
    return pd.DataFrame(rows)


def _bar_traces(fig: go.Figure) -> list[go.Bar]:
    return [t for t in fig.data if isinstance(t, go.Bar)]


def _real_bars(fig: go.Figure) -> list[go.Bar]:
    """The visible bars only -- the phantom gutter column is also a `go.Bar`
    trace, drawn with `X.GUTTER_PHANTOM_FILL` (fully transparent) as its
    marker colour, never an institution hex."""
    return [t for t in _bar_traces(fig)
           if not (isinstance(t.marker.color, (list, tuple))
                   and set(t.marker.color) == {X.GUTTER_PHANTOM_FILL})]


# ---------------------------------------------------------------------------
# two_tab_bars -- Thematic shape / SDG profile
# ---------------------------------------------------------------------------
def test_two_tab_bars_rejects_an_unknown_tab(slots):
    with pytest.raises(ValueError):
        X.two_tab_bars(two_tab_frame(IDS, grouped_by_field=True), "dynamics",
                       NAMES, slots, grouped_by_field=True)


def test_two_tab_bars_profile_trace_count_and_institution_colour(slots):
    df = two_tab_frame(IDS, grouped_by_field=True)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    bars = _bar_traces(fig)
    # one visible bar trace + one phantom gutter trace per institution
    assert len(bars) == len(IDS) * 2
    real = _real_bars(fig)
    assert len(real) == len(IDS)
    colours = {c for t in real for c in t.marker.color}
    expected = {P.institution_color(slots[i]) for i in IDS}
    assert colours == expected
    assert not (colours & set(P.OA_DOMAIN_COLORS.values())), "colour must be institution, not domain"


def test_two_tab_bars_gutter_names_the_full_count_basis(slots):
    df = two_tab_frame(IDS, grouped_by_field=True)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    gutters = [t for t in _bar_traces(fig) if t not in _real_bars(fig)]
    assert len(gutters) == len(IDS)
    headers = [a for a in fig.layout.annotations if a.text == X.GUTTER_HEADER_FULL]
    assert len(headers) == 1
    fig_off = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True, gutter=False)
    assert len(_real_bars(fig_off)) == len(IDS)
    assert len(_bar_traces(fig_off)) == len(IDS), "gutter=False draws no phantom column"


def test_two_tab_bars_diamond_reference_on_a_varying_ref_value(slots):
    df = two_tab_frame(IDS, grouped_by_field=True)
    df.loc[df["row_id"] == 1, "ref_value"] = 0.12   # make ref_value vary by row
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    diamonds = [t for t in fig.data if isinstance(t, go.Scatter)
               and t.marker.symbol == X.REF_MARKER_SYMBOL]
    assert len(diamonds) == 1
    assert diamonds[0].marker.color == P.INK


def test_two_tab_bars_impact_cautions_under_fifty_covered_never_the_profile_tab(slots):
    df = two_tab_frame(IDS, grouped_by_field=False)
    impact = X.two_tab_bars(df, "impact", NAMES, slots, grouped_by_field=False)
    texts = [t for tr in _real_bars(impact) for t in tr.text]
    assert any(X.LOW_VOLUME_GLYPH in t for t in texts), "some row sits under n_covered=50"
    inks = [c for tr in _real_bars(impact) for c in tr.textfont.color]
    assert P.WARNING_CAPTION_COLOR in inks

    profile = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=False)
    p_texts = [t for tr in _real_bars(profile) for t in tr.text]
    assert not any(X.LOW_VOLUME_GLYPH in t for t in p_texts), (
        "the profile tab has no low_vol_col in its frame and must never caution")


def test_two_tab_bars_rows_ordered_as_given_and_grouped_under_field_boundaries(slots):
    df = two_tab_frame(IDS, grouped_by_field=True)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    # row order is preserved (row_id 0.5, never re-ranked by value)
    real = _real_bars(fig)[0]
    assert list(real.y) == [0, 1, 2, 3, 4, 5]
    domain_edges = [s for s in fig.layout.shapes if s.line.color == P.GRID
                    and s.line.width == X.DOMAIN_RULE_PX]
    assert len(domain_edges) == 1, "one boundary between Field 0 (rows 0-2) and Field 1 (rows 3-5)"

    sdg = two_tab_frame(IDS, grouped_by_field=False)
    fig_sdg = X.two_tab_bars(sdg, "profile", NAMES, slots, grouped_by_field=False)
    assert not [s for s in fig_sdg.layout.shapes if s.line.color == P.GRID
               and s.line.width == X.DOMAIN_RULE_PX], "SDG rows carry no field grouping"


def test_two_tab_bars_hover_carries_the_extra_reader_prose_lines(slots):
    df = two_tab_frame(IDS, grouped_by_field=True)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    hovers = [h for tr in _real_bars(fig) for h in tr.customdata]
    assert any(C.HOVER_SI in h for h in hovers)
    assert any(X.HOVER_FWCI_MEDIAN in h for h in hovers)
    assert any(C.HOVER_VOL_FRAC in h for h in hovers)


def test_two_tab_bars_missing_institution_row_is_absent_not_zero(slots):
    df = two_tab_frame(IDS, grouped_by_field=True)
    df = df.drop(index=df[(df["institution_id"] == "Ia") & (df["row_id"] == 2)].index)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    real = _real_bars(fig)
    ia_bar = next(t for t in real if str(NAMES["Ia"]) in t.customdata[0])
    assert 2 not in list(ia_bar.y), "a missing cell draws no bar, never a zero-length one"

def test_two_tab_bars_grouped_by_field_draws_a_domain_accent_glyph(slots):
    """The same small colour-coded square `reciprocity_
    bars` already uses, driven by the frame's own `domain_id`."""
    df = two_tab_frame(IDS, grouped_by_field=True)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    styled = list(fig.layout.yaxis.ticktext)
    assert all(X.ACCENT_GLYPH in t for t in styled)
    assert any(P.domain_color(d) in "".join(styled) for d in P.OA_DOMAIN_ORDER)


def test_two_tab_bars_sdg_rows_draw_no_domain_accent(slots):
    """SDG rows carry no field/domain concept -- the accent must not
    appear just because a `domain_id`-shaped column happens to exist."""
    df = two_tab_frame(IDS, grouped_by_field=False)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=False)
    styled = list(fig.layout.yaxis.ticktext)
    assert not any(X.ACCENT_GLYPH in t for t in styled)


def test_two_tab_bars_grouped_by_field_hover_names_the_field_first(slots):
    df = two_tab_frame(IDS, grouped_by_field=True)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    real = _real_bars(fig)
    hovers = [h for tr in real for h in tr.customdata]
    assert hovers
    first_lines = [h.split("<br>")[0] for h in hovers]
    assert all(fl.startswith(X.HOVER_FIELD_PREFIX) for fl in first_lines), (
        "'Field: {name}' must be the literal FIRST hover line")
    assert any("Field 0" in fl for fl in first_lines)


def test_two_tab_bars_sdg_hover_has_no_field_line(slots):
    df = two_tab_frame(IDS, grouped_by_field=False)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=False)
    real = _real_bars(fig)
    hovers = [h for tr in real for h in tr.customdata]
    assert hovers
    assert not any(h.startswith(X.HOVER_FIELD_PREFIX) for h in hovers)
    assert not any(X.HOVER_FIELD_PREFIX in h for h in hovers)

# ---------------------------------------------------------------------------
# mirror_frontier -- shared-frontier mirror
# ---------------------------------------------------------------------------
def test_mirror_frontier_trace_count_is_fixed_at_three():
    fig = X.mirror_frontier(mirror_frame(), ["A", "B"], [0, 1])
    bars = _bar_traces(fig)
    assert len(bars) == 3, "A-only, joint, B-only -- always three, even when a row's joint is NaN"


def test_mirror_frontier_geometry_matches_the_ruled_example():
    """vol_a=10, vol_b=8, vol_joint=6 -> A-only 4 on [-7,-3], joint on
    [-3,+3], B-only 2 on [+3,+5]."""
    df = pd.DataFrame([dict(topic_id=1, topic_name="T", url_joint="https://openalex.org/works?x",
                            vol_a=10.0, vol_b=8.0, vol_joint=6.0,
                            expansion=0.1, acceleration=0.1, is_top_decile=False)])
    fig = X.mirror_frontier(df, ["A", "B"], [0, 1])
    a, j, b = fig.data
    assert a.base[0] == pytest.approx(-7.0) and a.x[0] == pytest.approx(4.0)
    assert j.base[0] == pytest.approx(-3.0) and j.x[0] == pytest.approx(6.0)
    assert b.base[0] == pytest.approx(3.0) and b.x[0] == pytest.approx(2.0)
    assert a.base[0] + a.x[0] == pytest.approx(j.base[0])
    assert j.base[0] + j.x[0] == pytest.approx(b.base[0])


def test_mirror_frontier_clamps_an_inconsistent_row_at_zero():
    """vol_a=10, vol_b=4, vol_joint=6: B-only (vol_b - vol_joint) is negative
    clamp at zero rather than draw a bar of negative length."""
    df = pd.DataFrame([dict(topic_id=1, topic_name="T", url_joint="u",
                            vol_a=10.0, vol_b=4.0, vol_joint=6.0,
                            expansion=0.0, acceleration=0.0, is_top_decile=False)])
    fig = X.mirror_frontier(df, ["A", "B"], [0, 1])
    _, _, b = fig.data
    assert b.x[0] == 0.0


def test_mirror_frontier_no_joint_segment_and_hover_says_why_under_the_floor():
    fig = X.mirror_frontier(mirror_frame(), ["A", "B"], [0, 1])
    a, j, b = fig.data
    ticktext = list(fig.layout.yaxis.ticktext)
    row_of_topic1 = next(i for i, t in enumerate(ticktext) if "Topic 1<" in t or "Topic 1 " in t)
    assert row_of_topic1 not in list(j.y), (
        "Topic 1 has NaN vol_joint in the fixture, no joint segment drawn for it")
    hover_topic1 = next(h for h in a.customdata if "Topic 1" in h)
    assert X.HOVER_JOINT_UNAVAILABLE.format(floor=X._fmt_vol(X.JOINT_FLOOR)) in hover_topic1


def test_mirror_frontier_ticktext_carries_a_clickable_anchor_and_the_top_decile_glyph():
    fig = X.mirror_frontier(mirror_frame(), ["A", "B"], [0, 1])
    ticktext = list(fig.layout.yaxis.ticktext)
    assert all("<a href" in t and 'target="_blank"' in t for t in ticktext)
    assert any(X.TOP_DECILE_GLYPH in t for t in ticktext)
    topic0_tick = next(t for t in ticktext if "Topic 0" in t)
    assert "https://openalex.org/works?filter=topic.id:T0" in topic0_tick


def test_mirror_frontier_top_n_keeps_the_largest_combined_volume():
    df = mirror_frame(n_rows=4)
    fig = X.mirror_frontier(df, ["A", "B"], [0, 1], top_n=2)
    a, _, _ = fig.data
    assert len(a.y) == 2, "two rows drawn"
    # combined = vol_a + vol_b strictly ascending with i in the fixture, so
    # the two rows kept are topics 2 and 3 (the largest combined volume)
    ticktext = list(fig.layout.yaxis.ticktext)
    assert any("Topic 3" in t for t in ticktext)
    assert any("Topic 2" in t for t in ticktext)
    assert not any("Topic 0" in t for t in ticktext)


def test_mirror_frontier_symmetric_axis_shows_counts_on_both_sides():
    fig = X.mirror_frontier(mirror_frame(), ["A", "B"], [0, 1])
    tickvals = list(fig.layout.xaxis.tickvals)
    assert min(tickvals) < 0 < max(tickvals)
    assert tickvals == sorted(tickvals)
    ticktext = list(fig.layout.xaxis.ticktext)
    assert not any(t.startswith("-") for t in ticktext), "axis labels are ABSOLUTE counts"


def test_mirror_frontier_rejects_a_missing_column():
    bad = mirror_frame().drop(columns=["vol_joint"])
    with pytest.raises(ValueError):
        X.mirror_frontier(bad, ["A", "B"], [0, 1])


# ---------------------------------------------------------------------------
# mirror_frontier -- wrap + ellipsis + margin cap,
# fixing the 390 px "zero visible bars" defect found in a screenshot at that width.
# ---------------------------------------------------------------------------
LONG_TOPIC_NAME = ("A realistically long OpenAlex topic name that runs well "
                   "past the wrap width on purpose, to prove the ellipsis path")


def _long_mirror_frame() -> pd.DataFrame:
    return pd.DataFrame([dict(
        topic_id=1, topic_name=LONG_TOPIC_NAME, url_joint="https://openalex.org/works?x",
        vol_a=10.0, vol_b=8.0, vol_joint=6.0, expansion=0.1, acceleration=0.1,
        is_top_decile=True)])


def test_wrap_topic_label_never_splits_a_word_and_caps_at_three_lines():
    lines = X._wrap_topic_label(LONG_TOPIC_NAME)
    assert len(lines) <= X.MIRROR_LABEL_MAX_LINES
    original_words = LONG_TOPIC_NAME.split()
    # every line EXCEPT a possible trailing ellipsis cut is word-boundary-safe
    clean_lines = [ln for ln in lines if X.ELLIPSIS not in ln]
    joined_words = " ".join(clean_lines).split()
    assert joined_words == original_words[: len(joined_words)], "no kept word is split or reordered"


def test_wrap_topic_label_a_name_that_fits_never_truncates():
    fitting = "Short words need two lines"  # 27 chars, fits inside MIRROR_LABEL_WRAP_WIDTH x lines
    lines = X._wrap_topic_label(fitting)
    assert len(lines) <= X.MIRROR_LABEL_MAX_LINES
    assert X.ELLIPSIS not in " ".join(lines)
    assert " ".join(lines).split() == fitting.split(), "every word survives when it fits the budget"


def test_wrap_topic_label_ellipsis_only_past_the_character_budget():
    """The ellipsis decision is keyed on the ORIGINAL
    name's own character count (60), never on how many lines greedy wrap
    happens to want."""
    short = X._wrap_topic_label("Short topic")
    assert short == ["Short topic"]
    assert X.ELLIPSIS not in short[0]
    long = X._wrap_topic_label(LONG_TOPIC_NAME)
    assert len(LONG_TOPIC_NAME) > X.MIRROR_LABEL_CHAR_BUDGET
    assert X.ELLIPSIS in long[-1]


def test_wrap_topic_label_real_openalex_name_survives_whole():
    """A realistic example (CHROME_CONTRACT.md SS13.8): a realistic
    25-60 char OpenAlex topic name must render in full, never ellipsised."""
    name = "Geological and Geochemical Analysis"
    assert len(name) <= X.MIRROR_LABEL_CHAR_BUDGET
    lines = X._wrap_topic_label(name)
    assert len(lines) <= X.MIRROR_LABEL_MAX_LINES
    assert X.ELLIPSIS not in " ".join(lines)
    assert " ".join(lines).split() == name.split()


def test_wrap_topic_label_under_budget_merges_overflow_instead_of_truncating():
    """A name at or under the 60-char budget that still needs a FOURTH
    greedy-wrap line (word lengths tile imperfectly against the 20-char
    width) gets the overflow MERGED into the last kept line -- never cut,
    never ellipsised, unlike the over-budget case above."""
    name = "Complex Network Structures and Dynamics in Social Systems"  # 59 chars
    assert len(name) <= X.MIRROR_LABEL_CHAR_BUDGET
    lines = X._wrap_topic_label(name)
    assert len(lines) == X.MIRROR_LABEL_MAX_LINES
    assert X.ELLIPSIS not in " ".join(lines)
    assert " ".join(lines).split() == name.split(), "every word survives, just a longer last line"


def test_mirror_row_height_grows_with_the_lines_a_row_actually_needs():
    h1 = X._mirror_row_height(20, 1)
    h2 = X._mirror_row_height(20, 2)
    h3 = X._mirror_row_height(20, 3)
    assert h1 < h2 < h3, "three-line rows must get more room than two, which must get more than one"
    # the two-line case must reproduce charts.row_height's OWN calibrated
    # two-line pitch exactly -- not a new, independently-guessed number
    assert h2 == C.row_height(20, n_wrapped=20)


def test_mirror_frontier_long_label_wraps_to_at_most_three_lines_glyph_on_the_last():
    fig = X.mirror_frontier(_long_mirror_frame(), ["A", "B"], [0, 1])
    tick = fig.layout.yaxis.ticktext[0]
    assert tick.count("<br>") <= X.MIRROR_LABEL_MAX_LINES - 1
    assert tick.startswith("<a href=") and tick.endswith("</a>")
    assert tick.removesuffix("</a>").endswith(X.TOP_DECILE_GLYPH), (
        "the glyph must sit on the LAST line, inside the single <a>")
    # the href still wraps the WHOLE (possibly three-line) label, not just one line
    assert tick.count("<a href") == 1 and tick.count("</a>") == 1


def test_mirror_frontier_row_height_follows_the_tallest_wrapped_row():
    # enough rows that MIN_HEIGHT (the 300 px floor) does not mask the
    # per-row pitch difference between a one-line and a three-line frame
    short_df = pd.concat([mirror_frame(n_rows=1)] * 20, ignore_index=True)
    short_df["topic_id"] = range(20)
    short_df["url_joint"] = [f"https://openalex.org/works?x{i}" for i in range(20)]
    long_df = pd.concat([_long_mirror_frame()] * 20, ignore_index=True)
    long_df["topic_id"] = range(20)
    long_df["url_joint"] = [f"https://openalex.org/works?y{i}" for i in range(20)]
    one_line = X.mirror_frontier(short_df, ["A", "B"], [0, 1])
    three_line = X.mirror_frontier(long_df, ["A", "B"], [0, 1])
    assert one_line.layout.height < three_line.layout.height, (
        "a frame whose longest label needs three lines must be taller than one whose labels fit on one")


def test_mirror_frontier_left_margin_is_capped():
    fig = X.mirror_frontier(_long_mirror_frame(), ["A", "B"], [0, 1])
    assert fig.layout.margin.l <= X.MIRROR_MARGIN_CAP_PX
    short_fig = X.mirror_frontier(mirror_frame(), ["A", "B"], [0, 1])
    assert short_fig.layout.margin.l < fig.layout.margin.l, (
        "a short label must still reserve less room than a capped long one")


# ---------------------------------------------------------------------------
# yearly_domain_stack -- relationship yearly stack
# ---------------------------------------------------------------------------
def test_yearly_domain_stack_sums_equal_the_input_totals():
    df = yearly_frame()
    fig = X.yearly_domain_stack(df)
    assert fig.layout.barmode == "stack"
    bars = _bar_traces(fig)
    assert len(bars) == 4, "one trace per OpenAlex domain present"
    per_year_drawn = {}
    for t in bars:
        for y, v in zip(t.x, t.y):
            per_year_drawn[y] = per_year_drawn.get(y, 0.0) + float(v)
    expected = df.groupby(df["year"].astype(str))["vol"].sum().to_dict()
    assert per_year_drawn == pytest.approx(expected)


def test_yearly_domain_stack_totals_are_annotated_and_colours_are_domain_tokens():
    df = yearly_frame()
    fig = X.yearly_domain_stack(df)
    assert len(fig.layout.annotations) == df["year"].nunique()
    bars = _bar_traces(fig)
    colours = {t.marker.color for t in bars}
    assert colours <= set(P.OA_DOMAIN_COLORS.values())
    assert not (colours & set(P.INSTITUTION_COLORS)), "colour is domain, never institution"


def test_yearly_domain_stack_rejects_a_missing_column():
    with pytest.raises(ValueError):
        X.yearly_domain_stack(yearly_frame().drop(columns=["domain_name"]))


# ---------------------------------------------------------------------------
# reciprocity_bars -- adapted from views_collab._reciprocity_chart.
# The WIDE one-row-per-field contract, a gutter
# value drawn ONCE per row (not once per institution), and a custom
# narrative hover sentence.
# ---------------------------------------------------------------------------
RECIP_NAMES = ["Institution A", "Institution B"]
RECIP_SLOTS = [0, 1]


def test_reciprocity_bars_ranked_by_descending_joint_volume():
    df = reciprocity_frame()
    fig = X.reciprocity_bars(df, RECIP_NAMES, RECIP_SLOTS)
    real = _real_bars(fig)[0]
    # field 0 carries the largest vol_joint (40), field 3 the smallest (16)
    assert list(real.y) == [0, 1, 2, 3]


def test_reciprocity_bars_gutter_drawn_once_per_row_centred_institution_colour_is_the_mark():
    df = reciprocity_frame()
    fig = X.reciprocity_bars(df, RECIP_NAMES, RECIP_SLOTS)
    bars = _bar_traces(fig)
    gutters = [t for t in bars if t not in _real_bars(fig)]
    assert len(bars) == 3, "two institution bars + exactly ONE gutter trace (not one per institution)"
    assert len(gutters) == 1
    assert list(gutters[0].text) == [X._gutter_value(v) for v in df.sort_values(
        "vol_joint", ascending=False)["vol_joint"]]
    headers = [a for a in fig.layout.annotations if a.text == X.GUTTER_HEADER_JOINT]
    assert len(headers) == 1
    real = _real_bars(fig)
    colours = {c for t in real for c in t.marker.color}
    assert colours == {P.institution_color(s) for s in RECIP_SLOTS}
    assert not (colours & set(P.OA_DOMAIN_COLORS.values()))


def test_reciprocity_bars_x_title_is_explicit():
    fig = X.reciprocity_bars(reciprocity_frame(), RECIP_NAMES, RECIP_SLOTS)
    assert fig.layout.xaxis.title.text == X.AX_RECIPROCITY
    assert fig.layout.xaxis.title.text != "Share of output", "must not be the bare generic axis label"


def test_reciprocity_bars_hover_is_a_narrative_sentence_with_rank_when_present():
    fig = X.reciprocity_bars(reciprocity_frame(with_ranks=True), RECIP_NAMES, RECIP_SLOTS)
    real = _real_bars(fig)
    all_hovers = [h for t in real for h in t.customdata]
    assert any("of Institution A's output" in h and "of Institution B's" in h
               and "joint publications" in h for h in all_hovers)
    assert any("is Institution A's partner #" in h for h in all_hovers)
    assert any("is Institution B's partner #" in h for h in all_hovers)
    # the skeleton's generic vocabulary must NOT leak into this custom hover
    assert not any(X.HOVER_DENOMINATOR in h or X.HOVER_REFERENCE in h for h in all_hovers)


def test_reciprocity_bars_hover_drops_the_rank_clause_when_ranks_are_absent():
    fig = X.reciprocity_bars(reciprocity_frame(with_ranks=False), RECIP_NAMES, RECIP_SLOTS)
    real = _real_bars(fig)
    all_hovers = [h for t in real for h in t.customdata]
    assert all_hovers
    assert not any("partner #" in h for h in all_hovers)
    assert all("joint publications" in h for h in all_hovers)


def test_reciprocity_bars_domain_survives_as_a_label_accent_only():
    df = reciprocity_frame()
    fig = X.reciprocity_bars(df, RECIP_NAMES, RECIP_SLOTS)
    styled = list(fig.layout.yaxis.ticktext)
    assert any(P.domain_color(d) in "".join(styled) for d in P.OA_DOMAIN_ORDER)
    real = _real_bars(fig)
    colours = {c for t in real for c in t.marker.color}
    assert not (colours & set(P.OA_DOMAIN_COLORS.values())), "bars stay institution-coloured"


def test_reciprocity_bars_draws_no_reference_diamond():
    fig = X.reciprocity_bars(reciprocity_frame(), RECIP_NAMES, RECIP_SLOTS)
    assert not [t for t in fig.data if isinstance(t, go.Scatter)]


def test_reciprocity_bars_rejects_a_missing_column():
    with pytest.raises(ValueError):
        X.reciprocity_bars(reciprocity_frame().drop(columns=["vol_joint"]),
                           RECIP_NAMES, RECIP_SLOTS)


# ---------------------------------------------------------------------------
# Every builder: light mode, no dark template, colours from palette tokens
# ---------------------------------------------------------------------------
FIGURES = {
    "two_tab_bars_profile": lambda slots: X.two_tab_bars(
        two_tab_frame(IDS, grouped_by_field=True), "profile", NAMES, slots, grouped_by_field=True),
    "two_tab_bars_impact": lambda slots: X.two_tab_bars(
        two_tab_frame(IDS, grouped_by_field=False), "impact", NAMES, slots, grouped_by_field=False),
    "mirror_frontier": lambda slots: X.mirror_frontier(mirror_frame(), ["A", "B"], [0, 1]),
    "yearly_domain_stack": lambda slots: X.yearly_domain_stack(yearly_frame()),
    "reciprocity_bars": lambda slots: X.reciprocity_bars(reciprocity_frame(), RECIP_NAMES, RECIP_SLOTS),
}
# `yearly_domain_stack` is the ONE builder in this
# module with its OWN native Plotly legend (four unlabelled domain colours
# were unreadable without one) -- every other chart still defers to the
# app-wide HTML chip strip and keeps `showlegend=False`.
NATIVE_LEGEND_CHARTS = {"yearly_domain_stack"}


@pytest.mark.parametrize("name", sorted(FIGURES))
def test_every_builder_is_light_mode_and_hides_the_plotly_legend(name, slots):
    fig = FIGURES[name](slots)
    assert fig.layout.paper_bgcolor == P.SURFACE
    assert fig.layout.plot_bgcolor == P.SURFACE
    assert not fig.layout.template or fig.layout.template.layout.paper_bgcolor in (None, P.SURFACE)
    if name in NATIVE_LEGEND_CHARTS:
        assert fig.layout.showlegend is True
        assert fig.layout.legend.orientation == "h"
    else:
        assert fig.layout.showlegend is not True
        for tr in fig.data:
            assert getattr(tr, "showlegend", False) is not True


@pytest.mark.parametrize("name", sorted(FIGURES))
def test_every_builder_takes_every_colour_from_a_palette_constant(name, slots):
    """Colours DRAWN on marks must equal a `lib.palette` constant -- never a
    literal the test itself invented, so this compares against the palette
    module's own values rather than hard-coded hexes."""
    fig = FIGURES[name](slots)
    known = (set(P.INSTITUTION_COLORS) | set(P.OA_DOMAIN_COLORS.values())
            | {P.SHARED_FRONTIER, P.SURFACE, P.INK, P.INK_SECONDARY, P.BORDER,
               P.GRID, P.WARNING_CAPTION_COLOR, P.FRONTIER_SHARED_HALO["color"],
               X.GUTTER_PHANTOM_FILL})
    found = set()
    for tr in fig.data:
        mc = getattr(getattr(tr, "marker", None), "color", None)
        if mc is None:
            continue
        if isinstance(mc, str):
            found.add(mc)
        else:
            found |= {c for c in mc if isinstance(c, str)}
    assert found, f"{name} draws no marker colour at all"
    assert found <= known, f"{name} draws a colour outside lib.palette: {found - known}"


# ---------------------------------------------------------------------------
# Module-wide house rules
# ---------------------------------------------------------------------------
def _string_literals(path: Path) -> list[tuple[int, str]]:
    """Every str constant EXCEPT docstrings (module, class, function) -- a
    docstring is prose for a reader of the source, never text the app
    renders."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_nodes.add(id(body[0].value))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in doc_nodes]


def _deployed_column_names() -> set[str]:
    import pyarrow.parquet as pq
    names: set[str] = set()
    for f in sorted(DATA.glob("*.parquet")):
        names |= set(pq.read_schema(f).names)
    return names


def test_no_digit_in_any_charts_compare_string_literal():
    tokens = load_allowlist()
    columns = _deployed_column_names()
    offenders = [(n, s) for n, s in _string_literals(MODULE)
                 if s not in columns and has_digit_violation(s, tokens)]
    assert not offenders, f"digit(s) inside a string literal of lib/charts_compare.py: {offenders}"


def test_charts_compare_takes_every_colour_from_palette():
    src = MODULE.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9A-Fa-f]{6}\b", src)
    assert "from lib import palette as P" in src


def test_charts_compare_never_imports_streamlit():
    src = MODULE.read_text(encoding="utf-8")
    assert not re.search(r"^\s*import\s+streamlit", src, flags=re.MULTILINE)
    assert not re.search(r"^\s*from\s+streamlit", src, flags=re.MULTILINE)


def test_the_hex_scan_actually_covers_this_module():
    from tests.test_palette import ALLOWLIST, SCAN_DIRS
    scanned: list[Path] = []
    for d in SCAN_DIRS:
        if d.exists():
            scanned.extend(sorted(d.rglob("*.py")))
    assert MODULE in scanned
    assert MODULE not in ALLOWLIST


def test_deleted_builders_are_actually_gone():
    """Non-vacuity proof for the deletion list (item 5): none of
    these names may be DEFINED or USED as code any more (a docstring
    module, class or function -- is free to still NAME them in prose,
    crediting what changed and why: the same "a docstring is prose for a
    reader of the source, never text the app renders" exemption
    `_string_literals` already applies, reused here to blank out doc SPANS
    instead of doc STRING VALUES)."""
    text = MODULE.read_text(encoding="utf-8")
    tree = ast.parse(text)
    doc_spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_spans.append((body[0].lineno, body[0].end_lineno))
    lines = text.splitlines()
    for start, end in doc_spans:
        for i in range(start - 1, end):
            lines[i] = ""
    code_only = "\n".join(lines)
    for name in ("fig_mirror_dots", "fig_quadrant_mix", "fig_frontier_overlay",
                "fig_frontier_small_multiples", "fig_impact_intervals",
                "fig_impact_subfields", "fig_frontier_map", "fig_diverging_shared",
                "fig_pulse", "LOW_VOLUME_PATTERN_SHAPE", "LOW_VOLUME_PATTERN_SOLIDITY",
                "SELECTOR_METRICS", "DYNAMICS_CLAMP_PCT"):
        assert not re.search(rf"\b{name}\b", code_only), f"{name} should have been deleted"
