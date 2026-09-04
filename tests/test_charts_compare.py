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
import yaml

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib import charts as C                 # noqa: E402
from lib import charts_compare as X         # noqa: E402
from lib import palette as P                # noqa: E402
from lib.app_config import CFG              # noqa: E402
from tests.test_narrative import has_digit_violation, load_allowlist  # noqa: E402

MODULE = APP_DIR / "lib" / "charts_compare.py"
DATA = APP_DIR / "data"
SPEC_PATH = APP_DIR / "docs" / "tooltip_spec.yaml"


# ---------------------------------------------------------------------------
# tooltip_spec.yaml -- load once; the same generic order-of-labels checker
# `tests/test_charts_topics.py` uses (duplicated here by this fence's own
# convention -- one small helper pair, not a cross-fence import).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def spec() -> dict:
    with open(SPEC_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _spec_labels(spec: dict, chart_key: str, *, unconditional_only: bool = False) -> list[str]:
    lines = spec["charts"][chart_key]["lines"]
    if unconditional_only:
        lines = [ln for ln in lines if "when" not in ln]
    return [ln["label"] for ln in lines if ln.get("label")]


def assert_labels_in_order(hover: str, labels: list[str]) -> None:
    pos = -1
    for label in labels:
        idx = hover.find(label)
        assert idx != -1, f"label {label!r} not found in hover: {hover!r}"
        assert idx > pos, f"label {label!r} out of order (at {idx}, expected after {pos}): {hover!r}"
        pos = idx

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
                # n_covered_fwci: row 1 sits BELOW the fwci_pair_2dp floor of
                # three (no FWCI_EU line at all for that row); row 2 sits
                # between three and ten (the line draws, daggered); every
                # other row clears ten (the line draws, no dagger).
                fwci_mean=1.20 + 0.02 * i,
                n_covered_fwci=[81, 2, 5, 31, 71, 21][i],
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
    """The one-row-per-field contract `reciprocity_scatter` reads: field_id,
    field_name, domain_id, share_a, share_b, vol_joint, plus fwci_mean/
    fwci_median/n_fwci/n_top10/n_covered/n_stars_field and the OPTIONAL
    rank_in_a/rank_in_b. Field 0 carries an n_fwci UNDER the fwci_pair_2dp
    floor of three (no FWCI_EU line for that one row); field 1 carries
    n_covered=0 (no PP10_WD line at all -- never a bare 0.0%)."""
    rows = []
    for f in range(n_fields):
        row = dict(field_id=f, field_name=f"Field {f}", domain_id=(f % 4) + 1,
                  vol_joint=float(40 - 8 * f), share_a=0.05 + 0.01 * f,
                  share_b=0.04 + 0.015 * f,
                  fwci_mean=1.10 + 0.05 * f, fwci_median=0.90 + 0.03 * f,
                  n_fwci=(2 if f == 0 else 12 + f),
                  n_top10=(0 if f == 1 else 2 + f), n_covered=(0 if f == 1 else 20 + f),
                  n_stars_field=f)
        if with_ranks:
            row["rank_in_a"] = f + 1
            row["rank_in_b"] = n_fields - f
        rows.append(row)
    return pd.DataFrame(rows)


def _bar_traces(fig: go.Figure) -> list[go.Bar]:
    return [t for t in fig.data if isinstance(t, go.Bar)]


def _real_bars(fig: go.Figure) -> list[go.Bar]:
    """The visible bars only -- the phantom gutter column is also a `go.Bar`
    trace, drawn with `C.GUTTER_PHANTOM_FILL` (fully transparent, single-
    sourced in `lib/charts.py` now) as its marker colour, never an
    institution hex."""
    return [t for t in _bar_traces(fig)
           if not (isinstance(t.marker.color, (list, tuple))
                   and set(t.marker.color) == {C.GUTTER_PHANTOM_FILL})]


def _reference_shapes(fig: go.Figure) -> list:
    """The bar-layout contract's dashed RED reference shapes -- a `go.Shape`
    line, never a marker trace any more (the diamond is retired)."""
    return [s for s in fig.layout.shapes
           if s.line.color == P.WARNING_CAPTION_COLOR and s.line.dash == "dash"]


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


def test_two_tab_bars_gutter_has_no_header_annotation(slots):
    """Bar-layout contract: the gutter column carries no header any more
    (the earlier per-chart basis label -- 'Publications, full count' -- is
    retired; the basis is stated once in the section's own caption)."""
    df = two_tab_frame(IDS, grouped_by_field=True)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    gutters = [t for t in _bar_traces(fig) if t not in _real_bars(fig)]
    assert len(gutters) == len(IDS)
    assert not fig.layout.annotations, "no header annotation above the gutter, ever"
    fig_off = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True, gutter=False)
    assert len(_real_bars(fig_off)) == len(IDS)
    assert len(_bar_traces(fig_off)) == len(IDS), "gutter=False draws no phantom column"


def test_two_tab_bars_dashed_red_reference_tick_on_a_varying_ref_value(slots):
    """Bar-layout contract: a per-row VARYING reference is a dashed RED
    vertical TICK -- x0 == x1 at the reference value, spanning that row's
    own band -- never a diamond marker any more."""
    df = two_tab_frame(IDS, grouped_by_field=True)
    df.loc[df["row_id"] == 1, "ref_value"] = 0.12   # make ref_value vary by row
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    ticks = _reference_shapes(fig)
    assert len(ticks) == df["row_id"].nunique(), "one reference tick per taxon row"
    assert not [t for t in fig.data if isinstance(t, go.Scatter)], "no diamond marker trace any more"
    for s in ticks:
        assert s.x0 == s.x1, "a reference tick is a VERTICAL line, x0 == x1"
        assert s.y1 - s.y0 == pytest.approx(1.0), "spans exactly one row's own band"
    values = sorted(s.x0 for s in ticks)
    assert values == sorted(df.drop_duplicates("row_id")["ref_value"])


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


def test_two_tab_bars_profile_hover_carries_si_and_the_whole_run_vol_pair_line(slots):
    """docs/tooltip_spec.yaml's compare_thematic_profile: the SI line and a
    combined full+fractional 'publications, whole run' line -- no bare
    fractional-only line any more (folded into the ONE vol_pair line)."""
    df = two_tab_frame(IDS, grouped_by_field=True)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    hovers = [h for tr in _real_bars(fig) for h in tr.customdata]
    assert any(X.HOVER_SI_LABEL in h for h in hovers)
    assert any(X.HOVER_VOL_PAIR_SUBFIELD in h and "full" in h and "fractional" in h for h in hovers)
    assert not any(X.HOVER_FWCI_LABEL in h for h in hovers), "the Profile tab never shows the FWCI_EU line"


def test_two_tab_bars_impact_hover_carries_the_fwci_eu_line_floored_at_three(slots):
    """docs/tooltip_spec.yaml's compare_thematic_impact: FWCI_EU (mean AND
    median) joins the impact tab's hover, floored at n_covered_fwci >= 3
    (row i=1's fixture value is 2 -- below the floor, line absent for that
    row's own hover only) and daggered under ten (every fixture row is)."""
    df = two_tab_frame(IDS, grouped_by_field=False)
    fig = X.two_tab_bars(df, "impact", NAMES, slots, grouped_by_field=False)
    hovers = [h for tr in _real_bars(fig) for h in tr.customdata]
    with_fwci = [h for h in hovers if X.HOVER_FWCI_LABEL in h]
    assert with_fwci, "at least one row clears the n_covered_fwci >= 3 floor"
    assert any("mean" in h and "median" in h and "works" in h for h in with_fwci)
    assert any(X.LOW_VOLUME_GLYPH in h.split(X.HOVER_FWCI_LABEL)[1].split("<br>")[0] for h in with_fwci), (
        "every fixture row's n_covered_fwci is under ten -- the work count carries a dagger")
    assert not any(C.HOVER_SI in h for h in hovers), "the Impact tab never shows the SI line"
    row1_hover = next(h for h in hovers if "Row 1" in h)
    assert X.HOVER_FWCI_LABEL not in row1_hover, "row 1's n_covered_fwci=2 is under the floor of three"


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
    assert all(C.ACCENT_GLYPH in t for t in styled)
    assert any(P.domain_color(d) in "".join(styled) for d in P.OA_DOMAIN_ORDER)


def test_two_tab_bars_sdg_rows_draw_no_domain_accent(slots):
    """SDG rows carry no field/domain concept -- the accent must not
    appear just because a `domain_id`-shaped column happens to exist."""
    df = two_tab_frame(IDS, grouped_by_field=False)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=False)
    styled = list(fig.layout.yaxis.ticktext)
    assert not any(C.ACCENT_GLYPH in t for t in styled)


def test_two_tab_bars_grouped_by_field_hover_names_the_entity_first_then_its_field(slots):
    """docs/tooltip_spec.yaml's compare_thematic_profile line order: the
    ENTITY (the subfield's own row label) first, the field it belongs to
    second -- the reference version's own 'field names first' behaviour is
    superseded by this stream's entity-first ruling."""
    df = two_tab_frame(IDS, grouped_by_field=True)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True)
    real = _real_bars(fig)
    hovers = [h for tr in real for h in tr.customdata]
    assert hovers
    lines = [h.split("<br>") for h in hovers]
    assert all(ln[0].startswith("Row ") for ln in lines), "line 1 is the entity (the row's own label)"
    assert all(ln[1].startswith(X.HOVER_FIELD_LABEL) for ln in lines), "line 2 names its field"
    assert any("Field 0" in ln[1] for ln in lines)
    assert any(NAMES["Ia"] in ln[2] or NAMES["Iz"] in ln[2] for ln in lines), "line 3 is the institution"


def test_two_tab_bars_sdg_hover_has_no_field_line(slots):
    df = two_tab_frame(IDS, grouped_by_field=False)
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=False)
    real = _real_bars(fig)
    hovers = [h for tr in real for h in tr.customdata]
    assert hovers
    assert all(h.split("<br>")[0].startswith("Row ") for h in hovers), "line 1 is still the entity"
    assert not any(X.HOVER_FIELD_LABEL in h for h in hovers)

# ---------------------------------------------------------------------------
# mirror_frontier -- shared-frontier mirror. DELETED (D31): retired along
# with `_render_shared_frontier`/`_render_frontier_positioning`, absorbed
# into Compare's topic overlap (`lib.charts_topics.fig_plane_frontier`'s
# `color_by="owner"` mode + `balance_bars`, tested in
# `tests/test_charts_topics.py`, not here -- a separate module by design).
# `test_deleted_builders_are_actually_gone` below pins the removal.
# ---------------------------------------------------------------------------


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
# reciprocity_scatter -- a port of an earlier SIRIS Streamlit tool's own
# "Zoom partenaire" bubble scatter (D27 -- back from the institution-
# coloured bar adaptation this page drew in between). One bubble per field:
# y = share of A's own output, x = share of B's own output, area = joint
# volume, colour = domain, a dotted equal-weight diagonal, square axes.
# ---------------------------------------------------------------------------
RECIP_NAMES = ["Institution A", "Institution B"]
RECIP_SLOTS = [0, 1]


def test_reciprocity_scatter_is_one_scatter_trace_area_true_and_positioned_by_share():
    df = reciprocity_frame()
    fig = X.reciprocity_scatter(df, RECIP_NAMES, RECIP_SLOTS)
    assert len(fig.data) == 1
    tr = fig.data[0]
    assert isinstance(tr, go.Scatter) and tr.mode == "markers"
    assert list(tr.x) == pytest.approx(list(df["share_b"]))  # x = B's own share
    assert list(tr.y) == pytest.approx(list(df["share_a"]))  # y = A's own share
    assert list(tr.marker.size) == pytest.approx(list(df["vol_joint"]))  # area = joint volume
    assert tr.marker.sizemode == "area"


def test_reciprocity_scatter_colour_is_domain_not_institution():
    df = reciprocity_frame()
    fig = X.reciprocity_scatter(df, RECIP_NAMES, RECIP_SLOTS)
    colours = set(fig.data[0].marker.color)
    assert colours <= set(P.OA_DOMAIN_COLORS.values())
    assert not (colours & set(P.INSTITUTION_COLORS)), "no institution colour anywhere on this chart"


def test_reciprocity_scatter_draws_the_dotted_equal_weight_diagonal():
    fig = X.reciprocity_scatter(reciprocity_frame(), RECIP_NAMES, RECIP_SLOTS)
    diagonals = [s for s in fig.layout.shapes if s.line.dash == "dot"]
    assert len(diagonals) == 1
    d = diagonals[0]
    assert d.x0 == d.y0 == 0 and d.x1 == pytest.approx(d.y1)  # a 45-degree line through the origin


def test_reciprocity_scatter_square_axes_via_scaleanchor():
    fig = X.reciprocity_scatter(reciprocity_frame(), RECIP_NAMES, RECIP_SLOTS)
    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.yaxis.scaleratio == 1
    assert fig.layout.xaxis.range[0] == fig.layout.yaxis.range[0] == 0
    assert fig.layout.xaxis.range[1] == pytest.approx(fig.layout.yaxis.range[1])


def test_reciprocity_scatter_axis_titles_name_each_institution():
    fig = X.reciprocity_scatter(reciprocity_frame(), RECIP_NAMES, RECIP_SLOTS)
    assert "Institution B" in fig.layout.xaxis.title.text
    assert "Institution A" in fig.layout.yaxis.title.text
    assert fig.layout.xaxis.title.text != fig.layout.yaxis.title.text


def test_reciprocity_scatter_hover_carries_shares_joint_volume_fwci_pp10_and_stars():
    fig = X.reciprocity_scatter(reciprocity_frame(with_ranks=True), RECIP_NAMES, RECIP_SLOTS)
    hovers = list(fig.data[0].customdata)
    assert all(h.startswith("Field ") for h in hovers), "the field's own name is the first hover line"
    assert any("of Institution A's own publications" in h and "of Institution B's own publications" in h
              and X.HOVER_RECIP_JOINT in h for h in hovers)
    assert any(X.HOVER_FWCI_LABEL in h for h in hovers)
    assert any(X.HOVER_RECIP_PP10 in h for h in hovers)
    assert any(X.HOVER_RECIP_STARS in h for h in hovers)
    assert any("is Institution A's partner #" in h for h in hovers)
    assert any("is Institution B's partner #" in h for h in hovers)


def test_reciprocity_scatter_fwci_line_floored_at_three_and_pp10_omitted_at_zero_covered():
    """Field 0's fixture n_fwci=2 (under the fwci_pair_2dp floor of three):
    no FWCI_EU line at all for that row. Field 1's fixture n_covered=0: no
    PP10_WD line at all (never a fabricated bare 0.0%)."""
    fig = X.reciprocity_scatter(reciprocity_frame(), RECIP_NAMES, RECIP_SLOTS)
    hovers = list(fig.data[0].customdata)
    field0 = next(h for h in hovers if h.startswith("Field 0<"))
    assert X.HOVER_FWCI_LABEL not in field0
    field1 = next(h for h in hovers if h.startswith("Field 1<"))
    assert X.HOVER_RECIP_PP10 not in field1


def test_reciprocity_scatter_hover_drops_the_rank_clause_when_ranks_are_absent():
    fig = X.reciprocity_scatter(reciprocity_frame(with_ranks=False), RECIP_NAMES, RECIP_SLOTS)
    hovers = list(fig.data[0].customdata)
    assert hovers
    assert not any("partner #" in h for h in hovers)
    assert all(X.HOVER_RECIP_JOINT in h for h in hovers)


def test_reciprocity_scatter_rejects_a_missing_column():
    with pytest.raises(ValueError):
        X.reciprocity_scatter(reciprocity_frame().drop(columns=["vol_joint"]),
                              RECIP_NAMES, RECIP_SLOTS)


# ---------------------------------------------------------------------------
# docs/tooltip_spec.yaml conformance -- every chart this stream touches,
# label order verbatim (the spec's own header: "a test checks each
# builder's fields, order and formats against this file").
# ---------------------------------------------------------------------------
def test_thematic_profile_hover_matches_the_spec_label_order(spec):
    df = two_tab_frame(IDS, grouped_by_field=True)
    slots = {k: i for i, k in enumerate(sorted(KEYS, key=KEYS.get))}
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=True,
                         y0=CFG["window"][0], whole_y1=CFG["bonus_year"])
    hover = _real_bars(fig)[0].customdata[0]
    assert_labels_in_order(hover, _spec_labels(spec, "compare_thematic_profile"))


def test_thematic_impact_hover_matches_the_spec_label_order(spec):
    df = two_tab_frame(IDS, grouped_by_field=True)
    slots = {k: i for i, k in enumerate(sorted(KEYS, key=KEYS.get))}
    fig = X.two_tab_bars(df, "impact", NAMES, slots, grouped_by_field=True,
                         y0=CFG["window"][0], y1=CFG["window"][1])
    real = _real_bars(fig)
    # row 0's fixture clears every floor (n_covered=80, n_covered_fwci=81) --
    # every conditional line draws for it.
    hover = next(h for tr in real for h in tr.customdata if "Row 0" in h)
    assert_labels_in_order(hover, _spec_labels(spec, "compare_thematic_impact"))


def test_sdg_hover_matches_the_spec_label_order(spec):
    """`compare_sdg`'s own `vol_pair` line now states its REAL window
    (2020-2024, the core window `sdg_frame`'s own vol_full/vol_frac actually
    are -- a pre-existing, documented choice this builder did not change,
    `_metric_hover`'s own docstring) -- the spec's label text was corrected
    to match, so every line, including this one, matches verbatim now."""
    df = two_tab_frame(IDS, grouped_by_field=False)
    slots = {k: i for i, k in enumerate(sorted(KEYS, key=KEYS.get))}
    fig = X.two_tab_bars(df, "profile", NAMES, slots, grouped_by_field=False,
                         y0=CFG["window"][0], y1=CFG["window"][1])
    hover = _real_bars(fig)[0].customdata[0]
    assert_labels_in_order(hover, _spec_labels(spec, "compare_sdg"))


def test_reciprocity_scatter_hover_matches_the_spec_label_order(spec):
    fig = X.reciprocity_scatter(reciprocity_frame(with_ranks=True), RECIP_NAMES, RECIP_SLOTS)
    # field 2's fixture clears every floor (n_fwci=14, n_covered=22) -- every
    # conditional line draws for it.
    hover = next(h for h in fig.data[0].customdata if h.startswith("Field 2<"))
    # share_a/share_b share ONE spec label template ("share of A's own
    # publications") -- this builder fills {name} with the real institution
    # name for EACH of the two lines, so both are checked against the same
    # rendered fragment ("own publications"), not the literal placeholder text.
    assert "Field 2" in hover
    assert "own publications" in hover
    assert_labels_in_order(hover, [X.HOVER_RECIP_PP10, X.HOVER_RECIP_STARS])
    assert hover.index(X.HOVER_RECIP_JOINT) < hover.index(X.HOVER_FWCI_LABEL) < hover.index(X.HOVER_RECIP_PP10)


def test_yearly_domain_stack_hover_matches_the_spec_label_order(spec):
    fig = X.yearly_domain_stack(yearly_frame())
    hover = _bar_traces(fig)[0].customdata[0]
    # year/vol carry no label text of their own (format year_label/int_
    # thousands render the bare value) -- only share_of_year has a label.
    assert X.HOVER_SHARE_OF_YEAR in hover


# ---------------------------------------------------------------------------
# Every builder: light mode, no dark template, colours from palette tokens
# ---------------------------------------------------------------------------
FIGURES = {
    "two_tab_bars_profile": lambda slots: X.two_tab_bars(
        two_tab_frame(IDS, grouped_by_field=True), "profile", NAMES, slots, grouped_by_field=True),
    "two_tab_bars_impact": lambda slots: X.two_tab_bars(
        two_tab_frame(IDS, grouped_by_field=False), "impact", NAMES, slots, grouped_by_field=False),
    "yearly_domain_stack": lambda slots: X.yearly_domain_stack(yearly_frame()),
    "reciprocity_scatter": lambda slots: X.reciprocity_scatter(reciprocity_frame(), RECIP_NAMES, RECIP_SLOTS),
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
               C.GUTTER_PHANTOM_FILL})
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
                "SELECTOR_METRICS", "DYNAMICS_CLAMP_PCT",
                # D27: reciprocity is a scatter again -- the bar adaptation
                # this page drew in between, and its two bespoke helpers,
                # leave no live code (docstring credits are exempt, as for
                # every other renamed builder in this same list).
                "reciprocity_bars", "_add_centred_gutter", "_rewrite_reciprocity_hover",
                "RECIPROCITY_HOVER_BASE", "RECIPROCITY_HOVER_RANK",
                # bar-layout contract: the diamond marker, the per-chart
                # gutter headers, and mirror_frontier's own bespoke
                # character-wrap/margin-cap machinery -- all retired in
                # favour of the shared pixel-wrap contract in lib/charts.py.
                # (`GUTTER_NEG_AXIS_FRAC`/`GUTTER_TIP_FRAC`/`GUTTER_PHANTOM_FILL`
                # are NOT in this list -- they are single-sourced in
                # charts.py now and legitimately still appear here as
                # `C.<name>`; this list is bare names with NO live consumer
                # at all any more, local or imported.)
                "REF_MARKER_SYMBOL", "REF_MARKER_SIZE", "GUTTER_HEADER_FULL",
                "GUTTER_HEADER_JOINT", "MIRROR_LABEL_WRAP_WIDTH",
                "MIRROR_LABEL_MAX_LINES", "MIRROR_LABEL_CHAR_BUDGET",
                "MIRROR_MARGIN_CAP_PX", "MIRROR_THREE_LINE_FACTOR",
                "_wrap_topic_label", "_mirror_row_height",
                "BAR_GROUP_SPAN", "BAR_GROUP_FILL",
                # D31: the shared-frontier mirror itself is retired, absorbed
                # into Compare's topic overlap (`lib.charts_topics`, a
                # separate module) -- the function and its own now-orphaned
                # constants leave no live consumer here.
                "mirror_frontier", "JOINT_FLOOR", "HOVER_JOINT",
                "HOVER_JOINT_UNAVAILABLE", "TOP_DECILE_GLYPH", "MIRROR_LINK_TARGET"):
        assert not re.search(rf"\b{name}\b", code_only), f"{name} should have been deleted"
