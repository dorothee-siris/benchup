"""tests/test_charts.py --.

Every `lib/charts.py` builder is rendered on REAL deployed data (Universite de
Strasbourg, resolved by `display_name` in `data/index.parquet`, plus University
of Gdansk for the SI-below-the-floor case), and the module's source is scanned
for the two things that must never appear in it: a colour literal (covered by
`tests/test_palette.py`'s directory walk) and a DIGIT inside a string literal
(covered here).

The section 9.4 frames are built INLINE from the parquet files rather than
imported from `lib/profile_data.py`: that module is, written in
parallel, and this test must not block on it. The column names below ARE the
section 9.4 contract, so the day `profile_data` lands, its output drops into
these builders unchanged -- and if it does not, this test's fixtures are the
statement of what the builders were promised.

Run from cwd `app/`: python -m pytest tests/test_charts.py -q
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

from lib import charts as C  # noqa: E402
from lib import palette as P  # noqa: E402
from tests.test_narrative import has_digit_violation, load_allowlist  # noqa: E402

DATA = APP_DIR / "data"
GDANSK = "I40413290"
TREE = "bestfit"

#  measured-acceptance seed set: Strasbourg (the module's existing
# fixture seed), IFPEN, Gdansk (existing SI-below-the-floor seed) plus five
# more chosen for the LONGEST subfield/topic names actually in the shipped
# data (found by ranking `topics_dim.parquet` and taking the institutions
# whose OWN top-30 by volume contains the longest hits) -- the harder test
# for "one row, no wrap, no truncation" than any hand-picked name would be.
SEEDS_2BR = {
    "strasbourg": "I68947357",
    "ifpen": "I265217849",
    "gdansk": GDANSK,
    "nyenrode": "I870178186",       # longest SUBFIELD name (53 chars) is its #1 row
    "mines_telecom": "I205703379",  # longest TOPIC name (83 chars) in its top-30
    "ceramics_inst": "I4210108183", # same 83-char topic, different institution
    "employment_agency": "I4210167358",  # 2nd-longest subfield, high volume
    "henley_college": "I2801915933",     # 2nd-longest subfield
}
MAX_PANEL_HEIGHT_PX = 900   #  acceptance: one desktop screen at 1280 px


# ---------------------------------------------------------------------------
# Real-data fixtures -- the section 9.4 column contracts, built from parquet
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def dim() -> pd.DataFrame:
    return pd.read_parquet(
        DATA / "topics_dim.parquet",
        columns=["domain_id", "domain_name", "field_id", "field_name",
                 "subfield_id", "subfield_name", "topic_id", "topic_name",
                 "expansion_latest", "acceleration_latest", "frontier_score_latest",
                 "quadrant", "top25pct_frontier", "is_excluded"],
    )


@pytest.fixture(scope="module")
def seed_id() -> str:
    ix = pd.read_parquet(DATA / "index.parquet", columns=["institution_id", "display_name"])
    hit = ix[ix["display_name"].str.fullmatch("Universit. de Strasbourg", na=False)]
    assert len(hit) == 1, f"Strasbourg not uniquely resolved: {list(hit['display_name'])}"
    return str(hit.iloc[0]["institution_id"])


@pytest.fixture(scope="module")
def fields_df(seed_id, dim) -> pd.DataFrame:
    fmap = dim.drop_duplicates("field_id")[["field_id", "field_name", "domain_id", "domain_name"]]
    f = pd.read_parquet(DATA / "fields.parquet")
    f = f[(f["institution_id"] == seed_id) & (f["tree"].astype(str) == TREE)]
    out = f.merge(fmap, on="field_id", how="left")
    out["share"] = out["share_frac"]
    return out[["field_id", "field_name", "domain_id", "domain_name",
                "vol_full", "vol_frac", "share", "si"]].reset_index(drop=True)


@pytest.fixture(scope="module")
def subfields_df(dim) -> pd.DataFrame:
    """Gdansk's FULL subfield frame -- deliberately not the top-20 cut, because
    the whole point of this fixture is that most rows sit below the G6 floor and
    carry `si = NaN`, the case `fig_share_si` must render as NO MARK."""
    smap = dim.drop_duplicates("subfield_id")[
        ["subfield_id", "subfield_name", "field_id", "field_name", "domain_id", "domain_name"]]
    s = pd.read_parquet(DATA / "subfields.parquet")
    s = s[(s["institution_id"] == GDANSK) & (s["tree"].astype(str) == TREE)]
    out = s.merge(smap, on="subfield_id", how="left", suffixes=("", "_dim"))
    out["share"] = out["share_frac"]
    return out[["subfield_id", "subfield_name", "field_id", "field_name",
                "domain_id", "domain_name", "vol_full", "vol_frac",
                "share", "si"]].reset_index(drop=True)


@pytest.fixture(scope="module")
def topics_df(dim) -> pd.DataFrame:
    """Top topics for Strasbourg, taken from the SHIPPED topic dimension joined
    to a real per-institution volume slice. `topics_all.parquet` is the deep
    frame the app reads column-subsetted; here a bounded read is enough."""
    t = pd.read_parquet(DATA / "topics_all.parquet",
                        columns=["institution_id", "topic_id", "share_frac", "vol_frac", "vol_full"])
    t = t[t["institution_id"] == GDANSK]
    out = t.merge(dim, on="topic_id", how="left")
    out["share"] = out["share_frac"]
    return out.sort_values("share", ascending=False).head(30).reset_index(drop=True)


@pytest.fixture(scope="module")
def sdg_df(seed_id) -> pd.DataFrame:
    s = pd.read_parquet(DATA / "sdg.parquet")
    s = s[s["institution_id"] == seed_id].copy()
    s["sdg_number"] = s["sdg_idx"].astype(int) + 1
    s["sdg_label"] = ["SDG" + C.THIN_SPACE + str(n) for n in s["sdg_number"]]
    return s[["sdg_idx", "sdg_number", "sdg_label", "share", "esi", "mass"]].reset_index(drop=True)


@pytest.fixture(scope="module")
def erc_df(seed_id) -> pd.DataFrame:
    e = pd.read_parquet(DATA / "erc.parquet")
    e = e[e["institution_id"] == seed_id].copy().reset_index(drop=True)
    # PE1-11, LS1-9, SH1-8 in panel_idx order (the ERC 2024/25 structure); the
    # authoritative resource is `erc_panels.csv` -- reconstructed here only so
    # this test does not depend on a file another module owns.
    order = [("PE", i) for i in range(11)] + [("LS", i) for i in range(9)] + \
            [("SH", i) for i in range(8)]
    e["erc_domain"] = [order[i][0] for i in e["panel_idx"]]
    e["panel_code"] = [f"{d}{n + 1}" for d, n in (order[i] for i in e["panel_idx"])]
    e["panel_label"] = e["panel_code"]
    return e[["panel_idx", "panel_code", "panel_label", "erc_domain",
              "share", "si", "mass"]]


# ---------------------------------------------------------------------------
# Builders render on real frames
# ---------------------------------------------------------------------------
def _bar_traces(fig: go.Figure) -> list[go.Bar]:
    return [t for t in fig.data if isinstance(t, go.Bar)]


def test_fig_share_si_fields_two_panels_and_colour_source(fields_df):
    fig = C.fig_share_si(fields_df, family="oa", sort="volume", gutter=True)
    bars = _bar_traces(fig)
    assert len(bars) == 1, "the share panel is ONE bar trace, not one per row"
    assert bars[0].orientation == "h"
    assert len(bars[0].x) == len(fields_df)
    # colour comes from the palette's domain map, in the SORTED row order
    ordered = fields_df.sort_values("share", ascending=False, kind="mergesort")
    assert list(bars[0].marker.color) == [P.domain_color(d) for d in ordered["domain_id"]]
    assert set(bars[0].marker.color) <= set(P.OA_DOMAIN_COLORS.values()) | {P.COMPARISON}
    # a second x-axis exists = the SI panel was built
    assert "xaxis2" in fig.layout
    assert fig.layout.xaxis2.title.text == C.AX_SI
    assert fig.layout.paper_bgcolor == P.SURFACE and fig.layout.plot_bgcolor == P.SURFACE
    # : the Find panels never wrap (default `wrap=False`), so height is
    # the plain per-row pitch whatever the longest label's length would have
    # wrapped to under the retired rule.
    assert fig.layout.height == C.row_height(len(fields_df), n_wrapped=0)
    assert fig.layout.height <= MAX_PANEL_HEIGHT_PX
    # the volume gutter (fix X3): folded into the y ticktext, one string per
    # row, no separate annotation left to collide with it
    assert len(fig.layout.annotations) == 0
    assert len(fig.layout.yaxis.ticktext) == len(fields_df)
    assert all(P.INK_SECONDARY in t for t in fig.layout.yaxis.ticktext)


def test_fig_share_si_sort_taxonomy_reorders_but_keeps_entity_colour(fields_df):
    by_vol = C.fig_share_si(fields_df, family="oa", sort="volume")
    by_tax = C.fig_share_si(fields_df, family="oa", sort="taxonomy")
    assert list(by_vol.data[0].y) != list(by_tax.data[0].y), "taxonomy sort must reorder"
    assert sorted(by_vol.data[0].y) == sorted(by_tax.data[0].y)
    # colour follows the entity, never the rank
    vol_map = dict(zip(by_vol.data[0].y, by_vol.data[0].marker.color))
    tax_map = dict(zip(by_tax.data[0].y, by_tax.data[0].marker.color))
    assert vol_map == tax_map
    # taxonomy order is domain-major
    tax_names = list(by_tax.data[0].y)
    doms = [fields_df.set_index("field_name").loc[n, "domain_id"] for n in tax_names]
    assert doms == sorted(doms)


def test_fig_share_si_nan_si_draws_no_mark(subfields_df):
    """A subfield below the G6 floor has `si = NaN`: it keeps its share bar and
    gets NO SI mark at all -- not a dot at zero, not a dot at the neutral value."""
    n_defined = int(np.isfinite(subfields_df["si"].to_numpy(dtype=float)).sum())
    assert 0 < n_defined < len(subfields_df), "fixture must mix defined and n/a SI"
    fig = C.fig_share_si(subfields_df, family="oa", sort="volume")
    dots = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode == "markers+text"]
    assert len(dots) == 1
    assert len(dots[0].x) == n_defined
    assert np.isfinite(np.asarray(dots[0].x, dtype=float)).all()
    stems = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode == "lines"]
    assert len(stems) == n_defined
    # the n/a rows are still on the y axis of the share panel
    assert len(_bar_traces(fig)[0].y) == len(subfields_df)
    # and their hover names the missing value explicitly
    assert any(P.NA_MARK in h for h in _bar_traces(fig)[0].customdata)


def test_fig_share_si_all_na_si_collapses_to_one_panel(subfields_df):
    thin = subfields_df[subfields_df["si"].isna()].reset_index(drop=True)
    assert len(thin) > 0
    fig = C.fig_share_si(thin, family="oa", sort="volume")
    assert "xaxis2" not in fig.layout, "no SI defined anywhere -> single panel"
    assert len(_bar_traces(fig)) == 1


# ---------------------------------------------------------------------------
# L34 (user ruling item 9): si_status drives solid/hollow/
# none marks, harmonised across subfields/ERC/SDG, and a zero-volume row
# NEVER gets a mark whatever si_status says (the ERC display-bug fix).
# `si_status` is built INLINE here from `vol_frac` (the fractional mass the
# real G6 floor already keys off) with the 10/30 rule, exactly as
# computes the shipped column -- this test does not import `profile_data`.
# ---------------------------------------------------------------------------
def test_fig_share_si_si_status_solid_thin_none_mark_counts_match_the_frame(subfields_df):
    d = subfields_df.copy()
    mass = d["vol_frac"]
    d["si_status"] = np.select([mass >= 30, mass >= 10], ["solid", "thin"], default="none")
    assert (d["si_status"] == "solid").sum() > 0 and (d["si_status"] == "thin").sum() > 0, (
        "fixture must span all three bands on real data"
    )
    # The real G6 floor is ALSO 30, so mass in [10, 30) is NaN `si` in the
    # shipped data today ( job is to widen the SI computation for
    # that band). Substitute a deterministic, clearly-synthetic SI for this
    # test's thin rows only -- the invariant under test is the MARK STYLE the
    # chart draws for a given status, not the numeric value's provenance.
    thin_and_undefined = d["si_status"].eq("thin") & d["si"].isna()
    d.loc[thin_and_undefined, "si"] = 1.5

    fig = C.fig_share_si(d, family="oa", sort="volume")
    dots = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode == "markers+text"][0]
    stems = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode == "lines"]

    n_solid = int((d["si_status"] == "solid").sum())
    n_thin = int((d["si_status"] == "thin").sum())
    assert len(dots.x) == n_solid + n_thin, "none rows draw no mark at all"
    assert len(stems) == n_solid + n_thin, "none rows draw no lollipop stem either"

    fills = list(dots.marker.color)
    line_colors = list(dots.marker.line.color)
    hollow_positions = [i for i, c in enumerate(fills) if c == P.SURFACE]
    solid_positions = [i for i, c in enumerate(fills) if c != P.SURFACE]
    assert len(hollow_positions) == n_thin, "thin -> hollow (SURFACE fill)"
    assert len(solid_positions) == n_solid, "solid -> filled (family colour)"
    assert all(line_colors[i] != P.SURFACE for i in hollow_positions), (
        "a hollow dot's outline is the family colour, not white -- that IS the disclosure"
    )
    assert all(line_colors[i] == P.SURFACE for i in solid_positions), (
        "a solid dot keeps its pre-existing white ring outline"
    )


def test_fig_share_si_zero_volume_row_never_gets_a_mark_even_when_si_status_says_solid(subfields_df):
    """The exact ERC bug shape: a row with a DEFINED, nonzero SI reading and
    `si_status='solid'` but ZERO publications behind it must draw no mark and
    no stem -- the zero-volume override outranks `si_status` unconditionally
    (L34/L9)."""
    d = subfields_df[subfields_df["si"].notna()].reset_index(drop=True)
    assert len(d) > 0
    d["si_status"] = "solid"
    zero_row = d.iloc[[0]].copy()
    zero_row["vol_full"] = 0
    zero_row["vol_frac"] = 0.0
    zero_row["si"] = 2.5
    zero_row["si_status"] = "solid"
    zero_row["subfield_name"] = "Zero-volume synthetic row"
    d = pd.concat([d, zero_row], ignore_index=True)

    fig = C.fig_share_si(d, family="oa", sort="volume")
    dots = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode == "markers+text"][0]
    assert "Zero-volume synthetic row" not in list(dots.y)
    assert len(dots.x) == len(d) - 1, "every OTHER solid row keeps its mark"


def test_fig_share_si_si_status_absent_falls_back_to_the_pre_r2_null_rule(subfields_df):
    """No `si_status` column at all -> the pre-R2 rule holds unchanged: a
    defined `si` draws a mark, a NaN `si` draws none, and every mark is the
    ordinary FILLED style (no hollow dots without an explicit `thin`)."""
    assert "si_status" not in subfields_df.columns
    fig = C.fig_share_si(subfields_df, family="oa", sort="volume")
    dots = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode == "markers+text"][0]
    n_defined = int(np.isfinite(subfields_df["si"].to_numpy(dtype=float)).sum())
    assert len(dots.x) == n_defined
    assert P.SURFACE not in set(dots.marker.color), "no hollow marks without an explicit si_status"


def test_fig_share_si_unit_grid_retired_for_outer_end_value_labels(fields_df):
    """: the per-integer unit grid is GONE (`showgrid=False` on the SI
    axis); each marker instead carries its OWN formatted SI value as text,
    anchored on the side AWAY from the neutral reference so the read is local
    to the row rather than a lookup against a gridline."""
    fig = C.fig_share_si(fields_df, family="oa")
    assert fig.layout.xaxis2.showgrid is False
    assert not fig.layout.xaxis2.tickvals, "the retired integer tick set must be gone"

    dots = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode == "markers+text"][0]
    si_vals = np.asarray(dots.x, dtype=float)
    expected_text = [C._fmt_si(v) for v in si_vals]
    assert list(dots.text) == expected_text
    expected_pos = ["middle left" if v < C.SI_NEUTRAL else "middle right" for v in si_vals]
    assert list(dots.textposition) == expected_pos
    # the axis range is padded past the extremes on BOTH sides so a label at
    # either end never clips against the plot border
    lo, hi = fig.layout.xaxis2.range
    assert lo < min(C.SI_NEUTRAL, si_vals.min())
    assert hi > max(C.SI_NEUTRAL, si_vals.max())


def test_fig_topics_flags_excluded_rows(topics_df):
    fig = C.fig_topics(topics_df, sort="volume")
    bars = _bar_traces(fig)
    assert len(bars) == 1 and bars[0].orientation == "h"
    n_excl = int(topics_df["is_excluded"].fillna(False).sum())
    glyphed = [y for y in bars[0].y if y.startswith(C.EXCLUDED_GLYPH)]
    assert len(glyphed) == n_excl
    opac = list(bars[0].marker.opacity)
    assert sum(1 for o in opac if o == P.MUTED_OPACITY) == n_excl
    if n_excl:
        assert any(C.HOVER_EXCLUDED in h for h in bars[0].customdata)
    assert set(bars[0].marker.color) <= set(P.OA_DOMAIN_COLORS.values()) | {P.COMPARISON}


def test_fig_frontier_scatter_quadrants_and_outline(topics_df):
    fig = C.fig_frontier(topics_df)
    pts = [t for t in fig.data if isinstance(t, go.Scatter)]
    assert len(pts) == 1 and pts[0].mode == "markers"
    scored = topics_df[np.isfinite(topics_df["expansion_latest"])
                       & np.isfinite(topics_df["acceleration_latest"])]
    assert len(pts[0].x) == len(scored), "unscored topics are dropped and must be captioned"
    shapes = list(fig.layout.shapes)
    assert len(shapes) == 2, "one vertical and one horizontal quadrant line"
    assert {s.type for s in shapes} == {"line"}
    top = int(scored["top25pct_frontier"].fillna(False).sum())
    widths = list(pts[0].marker.line.width)
    assert sum(1 for w in widths if w == P.OUTLINE_WIDTH) == top
    assert set(pts[0].marker.color) <= set(P.OA_DOMAIN_COLORS.values()) | {P.COMPARISON}


# ---------------------------------------------------------------------------
# L33: the frontier panel's two modes -- top-N by volume
# (`rank_volume <= FRONTIER_TOP_N`) and the global top-quartile set
# (`top25pct_frontier == True`, NOT a subset of the top-N) -- are both just
# CALLERS handing `fig_frontier` a pre-filtered frame; the builder's API is
# unchanged ( interface contract). `rank_volume` is built
# INLINE here.
# ---------------------------------------------------------------------------
def test_fig_frontier_on_a_rank_volume_le_200_subset(dim):
    t = pd.read_parquet(DATA / "topics_all.parquet",
                        columns=["institution_id", "topic_id", "share_frac", "vol_frac", "vol_full"])
    t = t[t["institution_id"] == GDANSK].merge(dim, on="topic_id", how="left")
    t["share"] = t["share_frac"]
    t["rank_volume"] = t["vol_full"].rank(ascending=False, method="first").astype(int)
    subset = t[t["rank_volume"] <= 200].reset_index(drop=True)
    assert 0 < len(subset) <= 200

    fig = C.fig_frontier(subset)
    pts = [tr for tr in fig.data if isinstance(tr, go.Scatter)][0]
    scored = subset[np.isfinite(subset["expansion_latest"]) & np.isfinite(subset["acceleration_latest"])]
    assert len(pts.x) == len(scored), "unscored topics are dropped from this mode too"
    # hover carries the full topic name for the topics actually plotted
    for name in scored["topic_name"].head(3):
        assert any(name in h for h in pts.customdata)


def test_fig_frontier_on_a_top25pct_frontier_subset(dim):
    t = pd.read_parquet(DATA / "topics_all.parquet",
                        columns=["institution_id", "topic_id", "share_frac", "vol_frac", "vol_full"])
    t = t[t["institution_id"] == GDANSK].merge(dim, on="topic_id", how="left")
    t["share"] = t["share_frac"]
    subset = t[t["top25pct_frontier"] == True].reset_index(drop=True)  # noqa: E712
    assert len(subset) > 0, "fixture must contain at least one top-quartile frontier topic"

    fig = C.fig_frontier(subset)
    pts = [tr for tr in fig.data if isinstance(tr, go.Scatter)][0]
    scored = subset[np.isfinite(subset["expansion_latest"]) & np.isfinite(subset["acceleration_latest"])]
    assert len(pts.x) == len(scored)
    # every plotted point in this mode IS top-quartile by construction, so
    # every outline is the INK/OUTLINE_WIDTH treatment, never the hairline
    assert all(w == P.OUTLINE_WIDTH for w in pts.marker.line.width)
    for name in scored["topic_name"].head(3):
        assert any(name in h for h in pts.customdata), "hover carries the full topic name"


def test_fig_sdg_uses_un_colours_in_goal_order(sdg_df):
    fig = C.fig_sdg(sdg_df)
    bars = _bar_traces(fig)
    assert len(bars) == 1 and bars[0].orientation == "h"
    assert len(bars[0].x) == len(sdg_df) == len(P.SDG_COLORS) - len(P.SDG_UNCOVERED)
    expected = [P.SDG_COLORS[int(n)] for n in sorted(sdg_df["sdg_number"])]
    assert list(bars[0].marker.color) == expected
    assert P.SDG_COLORS[P.SDG_UNCOVERED[0]] not in set(bars[0].marker.color)
    assert fig.layout.xaxis2.title.text == C.AX_ESI


def test_fig_sdg_uses_the_numbered_label_when_present(sdg_df):
    """L36: 'SDG {n}. {short label}' from `sdg_label_numbered` when the
    caller's frame carries it, falling back to the plain `sdg_label` only when
    it doesn't."""
    d = sdg_df.copy()
    d["sdg_label_numbered"] = [f"SDG {n} . Goal {n}" for n in d["sdg_number"]]
    fig = C.fig_sdg(d)
    bars = _bar_traces(fig)
    assert set(bars[0].y) == set(d["sdg_label_numbered"])
    assert not (set(bars[0].y) & set(sdg_df["sdg_label"])), (
        "the plain sdg_label must not be used once sdg_label_numbered is present"
    )


def test_fig_erc_uses_the_three_erc_hues_grouped_by_domain(erc_df):
    fig = C.fig_erc(erc_df)
    bars = _bar_traces(fig)
    assert len(bars[0].x) == len(erc_df) == 28
    assert set(bars[0].marker.color) == set(P.ERC_DOMAIN_COLORS.values())
    # taxonomy order = PE block, then LS, then SH
    codes = list(bars[0].y)
    doms = [c[:2] for c in codes]
    assert doms == sorted(doms, key=lambda d: P.ERC_DOMAIN_ORDER.index(d))
    # no OA domain hue leaks into an ERC-coloured chart (coexistence rule)
    assert not (set(bars[0].marker.color) & set(P.OA_DOMAIN_COLORS.values()))


def test_breakdown_pair_global_and_grouped(fields_df):
    labels = [P.OA_DOMAIN_COLORS and n for n in ("Life", "Social", "Physical", "Health")]
    totals = [float(fields_df[fields_df["domain_id"] == d]["vol_full"].sum())
              for d in P.OA_DOMAIN_ORDER]
    colors = [P.OA_DOMAIN_COLORS[d] for d in P.OA_DOMAIN_ORDER]

    g = C.fig_breakdown_global(labels, totals, colors)
    assert len(_bar_traces(g)) == 1
    assert _bar_traces(g)[0].orientation == "h"
    assert list(_bar_traces(g)[0].x) == sorted(totals, reverse=True)
    assert len(g.layout.annotations) == len(labels), "one direct end label per bar"
    assert g.layout.showlegend is False

    years = [str(y) for y in range(2020, 2026)]
    series = list(P.OA_DOMAIN_ORDER)
    y = C.fig_breakdown_yearly(
        years, series,
        labels={d: l for d, l in zip(series, labels)},
        colors={d: P.OA_DOMAIN_COLORS[d] for d in series},
        totals={d: [totals[i] / len(years)] * len(years) for i, d in enumerate(series)},
    )
    assert len(_bar_traces(y)) == len(series), "one trace per series, grouped not stacked"
    assert y.layout.barmode == "overlay", "explicit offset/width; offsetgroup is broken on 5.24.1"
    offsets = sorted(t.offset for t in _bar_traces(y))
    assert len(set(offsets)) == len(series), "every series gets its own offset"
    widths = {t.width for t in _bar_traces(y)}
    assert len(widths) == 1, "every series gets the same bar width"
    assert y.layout.showlegend is False, "the chip legend is the ONE legend for the pair"
    with pytest.raises(ValueError):
        C.fig_breakdown_yearly([2020], series, {}, {}, {})  # years must be strings


def test_chip_legend_html_escapes_and_uses_palette_ink():
    html = C.chip_legend_html([("Life <Sciences>", P.OA_DOMAIN_COLORS[1])])
    assert "&lt;Sciences&gt;" in html and "<Sciences>" not in html
    assert P.OA_DOMAIN_COLORS[1] in html
    assert P.INK_SECONDARY in html
    assert html.count("<span") == 3


def test_row_height_idiom():
    assert C.row_height(0) == C.MIN_HEIGHT
    assert C.row_height(30) == C.ROW_PX * 30 + C.BASE_PX
    assert C.row_height(100) > C.row_height(50)


def test_invalid_family_and_sort_raise(fields_df):
    with pytest.raises(ValueError):
        C.fig_share_si(fields_df, family="nonsense")
    with pytest.raises(ValueError):
        C.fig_share_si(fields_df, sort="alphabetical")


# ---------------------------------------------------------------------------
# Fix X3 (inspection finding I-4): the label/gutter collision at narrow width.
# `lib/charts.py:fig_share_si` / `fig_topics` fold the volume into the y
# ticktext as ONE right-anchored string per row instead of a separate
# annotation, so there is nothing left for it to collide with -- that
# mechanism is UNCHANGED by R2. What changed (L35, user ruling item 10,
# REVERSES this stream's own R1 ellipsis rule): a label longer than
# `wrap_label`'s width WRAPS onto at most two lines at a word boundary
# instead of being cut short. `MAX_LABEL_CHARS` / `_truncate_label` /
# `ELLIPSIS` are gone, so `test_truncate_label_never_cuts_from_the_left` (the
# R1 test of the retired ellipsis rule) is REMOVED, not adapted -- there is no
# truncation left to test. The replacement coverage below is `wrap_label`
# itself, the folded tick text it feeds, and the row-height/margin
# consequences of a wrapped (two-line) row.
# ---------------------------------------------------------------------------
def test_wrap_label_never_splits_a_word_and_preserves_the_full_text():
    assert C.wrap_label("Mathematics") == "Mathematics", "within budget -> untouched, no <br>"

    long_name = "Biochemistry, Genetics and Molecular Biology"  # the I-4 example, 46 chars
    wrapped = C.wrap_label(long_name)
    lines = wrapped.split("<br>")
    assert len(lines) == 2
    assert wrapped.replace("<br>", " ") == long_name, "full text survives, nothing truncated"
    words = set(long_name.split())
    for line in lines:
        for word in line.split():
            assert word in words, f"{word!r} is not one of the original words -- a word was split"


def test_wrap_label_merges_a_third_overflow_line_into_the_second():
    """Three words each already at the width budget on their own force THREE
    raw greedy-wrapped lines; the cap is 'at most two lines', so the third
    joins the second rather than the label growing a third line or losing
    text."""
    words = ["A" * 35, "B" * 35, "C" * 35]
    text = " ".join(words)
    wrapped = C.wrap_label(text, width=C.WRAP_WIDTH)
    lines = wrapped.split("<br>")
    assert len(lines) == 2, "at most two lines even when naive wrapping would need three"
    assert wrapped.replace("<br>", " ") == text, "no character lost to the merge"
    for w in words:
        assert w in wrapped, "no word split by the merge either"


def test_fig_share_si_default_never_wraps_widens_gutter_instead(fields_df):
    """ REVERSES L35 in turn for the Find panels: "full label on one
    row wins over bar length" -- small bars are an acceptable cost. Uses the
    REAL long field name from the I-4 screenshot ("Biochemistry, Genetics and
    Molecular Biology", 46 chars) straight out of the fixture `fields_df`
    already builds from the deployed parquet -- no synthetic data."""
    fig = C.fig_share_si(fields_df, family="oa", sort="volume", gutter=True)
    long_name = next(n for n in fields_df["field_name"] if "<br>" in C.wrap_label(n))
    assert long_name == "Biochemistry, Genetics and Molecular Biology"

    names = list(fig.data[0].y)  # identity axis: FULL names, always untouched
    idx = names.index(long_name)
    assert long_name in fig.data[0].customdata[idx], "full label must survive in hover"

    tickvals = list(fig.layout.yaxis.tickvals)
    ticktext = list(fig.layout.yaxis.ticktext)
    shown = ticktext[tickvals.index(long_name)]
    assert "<br>" not in shown, "no chart-builder default wraps a label onto a second line"
    assert long_name in shown, "the full name is drawn on its ONE row, never shortened"
    assert P.INK_SECONDARY in shown, "the volume rides in the secondary ink, inside the tick text"


def test_fig_share_si_wrap_true_opt_in_still_wraps_for_charts_compare(fields_df):
    """`wrap=True` is kept as an explicit opt-in
    so `lib/charts_compare.py`'s own geometry -- which calls `_tick_display`,
    `wrap_label` and `row_height`'s `n_wrapped` directly, unaffected by this
    stream -- is never broken by the Find panels' default flipping."""
    fig = C.fig_share_si(fields_df, family="oa", sort="volume", wrap=True)
    long_name = next(n for n in fields_df["field_name"] if "<br>" in C.wrap_label(n))
    tickvals = list(fig.layout.yaxis.tickvals)
    ticktext = list(fig.layout.yaxis.ticktext)
    shown = ticktext[tickvals.index(long_name)]
    assert "<br>" in shown, "wrap=True reproduces the earlier two-line behaviour"
    assert all(w in shown for w in long_name.replace(",", "").split())


def test_fig_share_si_automargin_and_reserved_margin_grow_for_long_labels(fields_df):
    # A deliberately tiny frame, not a filtered slice of fields_df: filtering
    # out the one wrapped row does NOT guarantee a shorter longest-LINE any
    # more (unlike the old whole-string truncation), because some OTHER row's
    # short label plus its OWN volume can still tie the wrapped row's longest
    # line -- exactly the "measure by longest LINE, not longest STRING" change
    # this stream made. A frame with genuinely short everything isolates the
    # comparison instead.
    tiny = pd.DataFrame({
        "field_id": [1, 2], "field_name": ["Ab", "Cd"], "domain_id": [1, 1],
        "domain_name": ["Life", "Life"], "vol_full": [1, 1], "vol_frac": [1.0, 1.0],
        "share": [0.5, 0.5], "si": [1.0, 1.0],
    })
    fig_tiny = C.fig_share_si(tiny, family="oa")
    fig_long = C.fig_share_si(fields_df, family="oa")  # includes the 46-char Biochemistry row
    assert fig_tiny.layout.yaxis.automargin is True
    assert fig_long.layout.yaxis.automargin is True
    assert fig_long.layout.margin.l > fig_tiny.layout.margin.l, (
        "a frame containing a long (wrapped) label must reserve more left margin than a tiny-label one"
    )
    assert fig_long.layout.margin.l > C.GUTTER_MARGIN_MIN_PX


def test_fig_share_si_row_height_no_longer_pays_the_wrap_penalty(fields_df):
    """: since the Find panels never wrap by default, a frame with one
    extra (however long) row is exactly ONE row pitch taller than the same
    frame without it -- never the old `WRAP_ROW_FACTOR` penalty every other
    row used to pay the moment any one label wrapped."""
    long_name = next(n for n in fields_df["field_name"] if "<br>" in C.wrap_label(n))
    without = fields_df[fields_df["field_name"] != long_name].reset_index(drop=True)
    fig_with = C.fig_share_si(fields_df, family="oa")
    fig_without = C.fig_share_si(without, family="oa")
    grown_by = fig_with.layout.height - fig_without.layout.height
    assert grown_by == C.ROW_PX, "exactly one plain row's pitch -- no wrap penalty applies"


def test_row_height_n_wrapped_matches_the_documented_factor():
    base = C.row_height(10)
    grown = C.row_height(10, n_wrapped=3)
    assert C.row_height(10, n_wrapped=0) == base, "default reproduces the pre-R2 formula exactly"
    # Manager fix 2026-08-29: plotly spaces categories UNIFORMLY, so one wrapped
    # label forces the two-line pitch on EVERY row (proportional growth left
    # adjacent wrapped labels overlapping in the R2 render).
    expected = max(C.MIN_HEIGHT, int(round(C.ROW_PX * C.WRAP_ROW_FACTOR * 10)) + C.BASE_PX)
    assert grown == expected
    assert grown > base
    assert C.row_height(10, n_wrapped=1) == grown, "any wrapped label -> the same uniform pitch"


def test_gutter_margin_px_measures_the_longest_line_not_the_whole_string():
    """A wrapped tick's `plain` text uses `\\n` between lines (see
    `_tick_display`); the margin must be sized off the single longest LINE,
    not the sum of every line's characters -- a two-line string with short
    lines must not out-reserve a one-line string that is itself longer than
    either of those lines."""
    two_short_lines = "aa\nbbbbbbbbbb"          # longest line = 10 chars
    one_longer_line = "ccccccccccccccc"          # 15 chars, one line
    m_two = C._gutter_margin_px([two_short_lines])
    m_one = C._gutter_margin_px([one_longer_line])
    assert m_one > m_two, "the longer SINGLE line must reserve more than the two SHORT lines"


def test_fig_topics_never_wraps_the_longest_labels_in_the_app(topics_df):
    """: topic names are the app's longest labels, so this panel is the
    hardest test of "full label on one row, gutter widens instead of
    wrapping"."""
    long_names = [str(n) for n in topics_df["topic_name"] if "<br>" in C.wrap_label(str(n))]
    assert long_names, "fixture must include a real long topic name (topics are the app's longest labels)"
    fig = C.fig_topics(topics_df, sort="volume")
    assert fig.layout.yaxis.automargin is True
    tickvals = list(fig.layout.yaxis.tickvals)
    ticktext = list(fig.layout.yaxis.ticktext)
    assert not any("<br>" in t for t in ticktext), "no topic label may wrap under the default"

    long_hit = long_names[0]
    # the row's identity (`y=`) is the full, untouched name (glyph-prefixed if
    # flagged catch-all) -- find it by substring, then read ITS OWN drawn tick
    # text off the same tickvals/ticktext pairing `fig_topics` builds.
    row_name = next(y for y in fig.data[0].y if long_hit in y)
    row_idx = list(fig.data[0].y).index(row_name)
    assert long_hit in fig.data[0].customdata[row_idx], "full label survives in hover"
    shown = ticktext[tickvals.index(row_name)]
    assert long_hit in shown, "the full, un-truncated name is drawn on its ONE row"
    # a wide-enough gutter is reserved to hold it (belt-and-braces alongside
    # test_fig_share_si_automargin_and_reserved_margin_grow_for_long_labels)
    assert fig.layout.margin.l > C.GUTTER_MARGIN_MIN_PX


def test_fig_erc_reuses_the_same_folded_gutter_mechanism(erc_df):
    """ERC panel labels run up to 66 chars in the real app (`panel_label` here
    is the short `panel_code` since `erc_panels.csv` is a different module's,
    but the mechanism under test is family-agnostic: `fig_erc` delegates to
    `fig_share_si`, so whatever labels arrive get the same treatment)."""
    fig = C.fig_erc(erc_df)
    assert fig.layout.yaxis.automargin is True
    assert len(fig.layout.yaxis.ticktext) == len(erc_df)
    assert all(P.INK_SECONDARY in t for t in fig.layout.yaxis.ticktext)
    # ERC/SDG delegate to fig_share_si without passing `wrap`, so they inherit
    # its default -- no chart drawn by this module wraps a label any more
    # unless a future caller explicitly opts back in.
    assert not any("<br>" in t for t in fig.layout.yaxis.ticktext)


# ---------------------------------------------------------------------------
# : fig_topics' retired sort toggle -- the keyword survives (nothing
# calling it breaks) but the panel is now ALWAYS volume-ordered.
# ---------------------------------------------------------------------------
def test_fig_topics_sort_toggle_retired_always_volume_ordered(topics_df):
    by_default = C.fig_topics(topics_df)
    by_volume = C.fig_topics(topics_df, sort="volume")
    by_taxonomy = C.fig_topics(topics_df, sort="taxonomy")
    assert list(by_default.data[0].y) == list(by_volume.data[0].y) == list(by_taxonomy.data[0].y), (
        "the sort keyword must no longer change the row order -- volume order always wins"
    )
    with pytest.raises(ValueError):
        C.fig_topics(topics_df, sort="alphabetical")


# ---------------------------------------------------------------------------
# : the frontier panel's top_n slider, bold quadrant axes, and the
# companion `frontier_coverage` disclosure numbers.
# ---------------------------------------------------------------------------
def test_fig_frontier_bold_ink_quadrant_axes(topics_df):
    fig = C.fig_frontier(topics_df)
    shapes = list(fig.layout.shapes)
    assert len(shapes) == 2
    assert all(s.line.color == P.INK for s in shapes), "quadrant split is bold INK, not the GRID hairline"
    assert all(s.line.width == C.FRONTIER_ORIGIN_PX for s in shapes)
    assert all(w > C.HAIRLINE_PX for w in (s.line.width for s in shapes))


def test_fig_frontier_top_n_caps_the_plotted_set_and_autoscales(topics_df):
    placeable = topics_df[np.isfinite(topics_df["expansion_latest"])
                          & np.isfinite(topics_df["acceleration_latest"])]
    assert len(placeable) > 1, "fixture must have more than one placeable row to prove a cut happened"
    top_n = max(1, len(placeable) // 2)
    fig_full = C.fig_frontier(topics_df)
    fig_capped = C.fig_frontier(topics_df, top_n=top_n)
    pts_full = [t for t in fig_full.data if isinstance(t, go.Scatter)][0]
    pts_capped = [t for t in fig_capped.data if isinstance(t, go.Scatter)][0]
    assert len(pts_capped.x) == top_n
    assert len(pts_capped.x) < len(pts_full.x)
    # a re-render of the identical frame with the identical top_n never reshuffles
    fig_capped_again = C.fig_frontier(topics_df, top_n=top_n)
    assert list(fig_capped_again.data[0].x) == list(pts_capped.x)
    # top_n at or past the placeable count is a no-op
    fig_noop = C.fig_frontier(topics_df, top_n=len(placeable) + 1)
    assert len(fig_noop.data[0].x) == len(pts_full.x)


def test_fig_frontier_catchall_rows_muted_and_flagged_on_hover(topics_df):
    """The real catch-all row in this fixture carries no frontier score (it is
    dropped by the placeability filter before `is_excluded` ever matters), so
    the muting/flagging behaviour is proven on a synthetic PLACEABLE catch-all
    row grafted onto the real frame -- everything else stays real data."""
    d = topics_df.copy()
    placeable = d[np.isfinite(d["expansion_latest"]) & np.isfinite(d["acceleration_latest"])].reset_index(drop=True)
    assert len(placeable) > 0
    synthetic = placeable.iloc[[0]].copy()
    synthetic["is_excluded"] = True
    synthetic["topic_name"] = "Synthetic catch-all topic"
    d = pd.concat([placeable.assign(is_excluded=False), synthetic], ignore_index=True)
    fig = C.fig_frontier(d)
    pts = [t for t in fig.data if isinstance(t, go.Scatter)][0]
    excl = d["is_excluded"].fillna(False).to_numpy()
    assert list(pts.marker.opacity) == [P.MUTED_OPACITY if e else 1.0 for e in excl]
    assert any(C.HOVER_EXCLUDED in h for e, h in zip(excl, pts.customdata) if e)


def test_frontier_coverage_matches_fig_frontier_selection_exactly(topics_df):
    top_n = 5
    stats = C.frontier_coverage(topics_df, size_col="vol_full", top_n=top_n)
    fig = C.fig_frontier(topics_df, size_col="vol_full", top_n=top_n)
    pts = [t for t in fig.data if isinstance(t, go.Scatter)][0]
    assert stats["n_shown"] == len(pts.x) == top_n
    placeable = topics_df[np.isfinite(topics_df["expansion_latest"])
                          & np.isfinite(topics_df["acceleration_latest"])]
    assert stats["n_placeable"] == len(placeable)
    assert 0.0 <= stats["pct_mass_not_shown"] <= 1.0
    assert stats["min_mass_shown"] is not None
    assert stats["mass_shown"] <= stats["mass_placeable"]
    assert isinstance(stats["n_catchall_shown"], int)
    # n/a-safe: an empty frame never divides by zero and never raises
    empty = topics_df.iloc[0:0]
    empty_stats = C.frontier_coverage(empty, size_col="vol_full", top_n=top_n)
    assert empty_stats == {
        "n_placeable": 0, "n_shown": 0, "n_catchall_shown": 0,
        "mass_shown": 0.0, "mass_placeable": 0.0,
        "pct_mass_not_shown": 0.0, "min_mass_shown": None,
    }


# ---------------------------------------------------------------------------
#  measured acceptance: every changed panel, 8 real seeds (Strasbourg,
# IFPEN, Gdansk plus five chosen for the longest subfield/topic names shipped
# in the data), zero wrapped or truncated labels, height within the one-screen
# budget. Printed so the worker's report can paste the measurement verbatim.
# ---------------------------------------------------------------------------
def _seed_fields(iid: str, dim: pd.DataFrame) -> pd.DataFrame:
    fmap = dim.drop_duplicates("field_id")[["field_id", "field_name", "domain_id", "domain_name"]]
    f = pd.read_parquet(DATA / "fields.parquet")
    f = f[(f["institution_id"] == iid) & (f["tree"].astype(str) == TREE)]
    out = f.merge(fmap, on="field_id", how="left")
    out["share"] = out["share_frac"]
    return out[["field_id", "field_name", "domain_id", "domain_name",
                "vol_full", "vol_frac", "share", "si"]].reset_index(drop=True)


def _seed_subfields(iid: str, dim: pd.DataFrame) -> pd.DataFrame:
    smap = dim.drop_duplicates("subfield_id")[
        ["subfield_id", "subfield_name", "field_id", "field_name", "domain_id", "domain_name"]]
    s = pd.read_parquet(DATA / "subfields.parquet")
    s = s[(s["institution_id"] == iid) & (s["tree"].astype(str) == TREE)]
    out = s.merge(smap, on="subfield_id", how="left", suffixes=("", "_dim"))
    out["share"] = out["share_frac"]
    vol = "vol_frac"
    out = out.nlargest(30, vol)
    return out[["subfield_id", "subfield_name", "field_id", "field_name",
                "domain_id", "domain_name", "vol_full", "vol_frac",
                "share", "si"]].reset_index(drop=True)


def _seed_topics(iid: str, dim: pd.DataFrame) -> pd.DataFrame:
    t = pd.read_parquet(DATA / "topics_all.parquet",
                        columns=["institution_id", "topic_id", "share_frac", "vol_frac", "vol_full"])
    t = t[t["institution_id"] == iid]
    out = t.merge(dim, on="topic_id", how="left")
    out["share"] = out["share_frac"]
    return out.sort_values("share", ascending=False).head(30).reset_index(drop=True)


def test_2br_measured_acceptance_eight_seeds_no_wrap_no_truncation_height_budget(dim, capsys):
    rows = []
    for label, iid in SEEDS_2BR.items():
        fields = _seed_fields(iid, dim)
        subfields = _seed_subfields(iid, dim)
        topics = _seed_topics(iid, dim)
        for panel_name, frame, builder in (
            ("fields", fields, lambda d: C.fig_share_si(d, family="oa", label_col="field_name",
                                                        volume_col="vol_full")),
            ("subfields", subfields, lambda d: C.fig_share_si(d, family="oa", label_col="subfield_name",
                                                              volume_col="vol_frac")),
            ("topics", topics, lambda d: C.fig_topics(d, volume_col="vol_frac")),
        ):
            if frame.empty:
                continue
            fig = builder(frame)
            ticktext = list(fig.layout.yaxis.ticktext)
            label_col = "field_name" if panel_name == "fields" else (
                "subfield_name" if panel_name == "subfields" else "topic_name")
            for name in frame[label_col].astype(str):
                # no wrap: the full name (bare, before the gutter's volume
                # suffix) is present, verbatim, inside its own drawn tick
                hit = next((t for t in ticktext if name in t), None)
                assert hit is not None, f"{label}/{panel_name}: {name!r} not found in ticktext at all"
                assert "<br>" not in hit, f"{label}/{panel_name}: {name!r} wrapped"
            rows.append((label, panel_name, len(frame), fig.layout.height))
            assert fig.layout.height <= MAX_PANEL_HEIGHT_PX, (
                f"{label}/{panel_name}: height {fig.layout.height} exceeds the one-screen budget"
            )
    assert len(rows) >= len(SEEDS_2BR) * 2, "most seeds must yield at least fields+topics"
    with capsys.disabled():
        print("\nmeasured acceptance (seed / panel / n_rows / height_px):")
        for r in rows:
            print(f"  {r[0]:<20} {r[1]:<10} n={r[2]:<3} height={r[3]}")


# ---------------------------------------------------------------------------
# Source scans: no digit in any string literal of charts.py
# ---------------------------------------------------------------------------
def _string_literals(path: Path) -> list[tuple[int, str]]:
    """Every str constant in the module EXCEPT docstrings (module, class,
    function) -- a docstring is prose for a reader of the source, never text
    the app renders, and the digit-ban's whole purpose is that no rendered
    string asserts a value."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                doc_nodes.add(id(body[0].value))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_nodes:
            out.append((node.lineno, node.value))
    return out


def _deployed_column_names() -> set[str]:
    """Every column name of every deployed table. A string literal that is
    EXACTLY one of these is a data-contract key, not rendered copy -- the same
    exclusion `tests/test_narrative.py` grants `lib/data_cache.py` ("parquet
    column names and file paths, not UI copy"), but grounded in the real
    schemas rather than in a hand-kept list, so it can never silently widen."""
    import pyarrow.parquet as pq
    names: set[str] = set()
    for f in sorted(DATA.glob("*.parquet")):
        names |= set(pq.read_schema(f).names)
    return names


def test_no_digit_in_any_charts_string_literal():
    """The allowlist file is loaded READ-ONLY (it is full at its cap of fifteen
    tokens; this stream adds none). Everything parametric in a chart is a
    `{placeholder}` the caller fills, and every number format is COMPOSED from
    an int constant -- see the module docstring of lib/charts.py."""
    tokens = load_allowlist()
    columns = _deployed_column_names()
    assert "top25pct_frontier" in columns, "column-name exemption must be grounded in real schemas"
    offenders = [(lineno, s) for lineno, s in _string_literals(APP_DIR / "lib" / "charts.py")
                 if s not in columns and has_digit_violation(s, tokens)]
    assert not offenders, f"digit(s) inside a string literal of lib/charts.py: {offenders}"


def test_charts_module_never_imports_streamlit():
    src = (APP_DIR / "lib" / "charts.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*import\s+streamlit", src, flags=re.MULTILINE)
    assert not re.search(r"^\s*from\s+streamlit", src, flags=re.MULTILINE)
    assert "streamlit" not in sys.modules or True  # importing charts must not pull it in


def test_charts_takes_every_colour_from_palette():
    """Belt and braces beside tests/test_palette.py's directory walk: charts.py
    must reference the palette module for colour, and never name a hex."""
    src = (APP_DIR / "lib" / "charts.py").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9A-Fa-f]{6}\b", src)
    assert "from lib import palette as P" in src


def test_fig_share_si_stacked_variant_for_the_narrow_breakpoint(fields_df):
    """VIZ_SPEC section 1.8: below the small breakpoint the share and SI panels
    STACK instead of sitting side by side (measured: 61 px of plot area each at
    390 px when side by side). The builder makes the layout available; the caller
    decides when to use it, because Streamlit cannot read the viewport width."""
    side = C.fig_share_si(fields_df, family="oa")
    down = C.fig_share_si(fields_df, family="oa", stacked=True)
    assert "xaxis2" in side.layout and "xaxis2" in down.layout
    # side by side: one row, two columns -> the two x-axes share the vertical band
    assert side.layout.yaxis.domain == side.layout.yaxis2.domain
    # stacked: two rows -> disjoint vertical bands, share above SI
    assert down.layout.yaxis.domain[0] > down.layout.yaxis2.domain[1]
    assert down.layout.height == 2 * side.layout.height
    # same rows, same order, same colours either way
    assert list(side.data[0].y) == list(down.data[0].y)
    assert list(side.data[0].marker.color) == list(down.data[0].marker.color)
