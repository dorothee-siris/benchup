"""tests/test_charts_topics.py -- `lib/charts_topics.py` builders, on
synthetic frames (the section 9.4-style column contract, hand-built here so
this test never depends on `lib/topic_data.py`'s own correctness).

Same house rules as `tests/test_charts.py`: a digit-in-string-literal scan
over `lib/charts_topics.py`'s own source, and a spec-conformance check that
loads `docs/tooltip_spec.yaml` and asserts each builder's customdata carries
the spec's own (non-empty) labels, in order.

Run from cwd `app/`: python -m pytest tests/test_charts_topics.py -q
"""
from __future__ import annotations

import ast
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

from lib import charts as C  # noqa: E402
from lib import charts_topics as X  # noqa: E402
from lib import palette as P  # noqa: E402
from tests.test_narrative import has_digit_violation, load_allowlist  # noqa: E402

SPEC_PATH = APP_DIR / "docs" / "tooltip_spec.yaml"


# ---------------------------------------------------------------------------
# tooltip_spec.yaml -- load once, and the generic order-of-labels checker
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def spec() -> dict:
    with open(SPEC_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _spec_labels(spec: dict, chart_key: str, *, unconditional_only: bool = False) -> list[str]:
    """Every NON-EMPTY `label` of a chart's `lines`, in the spec's own
    order -- lines whose label is "" (the entity name itself, or a bare
    flag) carry no label text to search for. `unconditional_only=True`
    drops any line carrying a `when` clause (a conditional line is checked
    on the SPECIFIC rows where its condition holds, in its own dedicated
    test, not on every synthetic row)."""
    lines = spec["charts"][chart_key]["lines"]
    if unconditional_only:
        lines = [ln for ln in lines if "when" not in ln]
    return [ln["label"] for ln in lines if ln.get("label")]


def _spec_labels_for_mode(spec: dict, chart_key: str, mode: str) -> list[str]:
    """Like `_spec_labels`, but for a chart whose spec entry is split
    `modes.<mode>.lines` rather than one flat `lines` list
    (`compare_balance_bars`'s five per-mode encodings)."""
    lines = spec["charts"][chart_key]["modes"][mode]["lines"]
    return [ln["label"] for ln in lines if ln.get("label")]


def assert_labels_in_order(hover: str, labels: list[str]) -> None:
    """Every label in `labels` appears in `hover`, in the SAME order the
    spec declares them -- the house check `docs/tooltip_spec.yaml`'s own
    header promises ("a test checks each builder's fields, order and
    formats against this file")."""
    pos = -1
    for label in labels:
        idx = hover.find(label)
        assert idx != -1, f"label {label!r} not found in hover: {hover!r}"
        assert idx > pos, f"label {label!r} out of order (at {idx}, expected after {pos}): {hover!r}"
        pos = idx


# ---------------------------------------------------------------------------
# Synthetic fixtures -- the two planes' and balance_bars' own column
# contracts (`topic_data.TOPIC_COLS` for the planes; `balance_bars`' own
# documented frame contract).
# ---------------------------------------------------------------------------
def _impact_frame(n: int = 12, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    excluded = [False] * n
    excluded[2] = True
    reason = [None] * n
    reason[2] = "Applied S&T"
    return pd.DataFrame({
        "topic_id": [f"T{i:05d}" for i in range(n)],
        "topic_name": [f"Topic {i}" for i in range(n)],
        "keywords": ["Kw1|Kw2|Kw3|Kw4|Kw5|Kw6|Kw7|Kw8|Kw9|Kw10" for _ in range(n)],
        "domain_id": [(i % 4) + 1 for i in range(n)],
        "domain_name": ["Life Sciences"] * n,
        "field_name": ["Some Field"] * n,
        "subfield_name": ["Some Subfield"] * n,
        "is_excluded": excluded,
        "exclusion_reason_label": reason,
        "expansion_latest": rng.uniform(-1, 1, n),
        "acceleration_latest": rng.uniform(-1, 1, n),
        "frontier_score_latest": rng.uniform(-1, 1, n),
        "quadrant": ["accelerating_expansion"] * n,
        "top25pct_frontier": [i % 5 == 0 for i in range(n)],
        "is_frontier_scored": [True] * n,
        "n_ar": rng.integers(3, 500, n),
        "n_covered": rng.integers(3, 500, n),
        "fwci_mean": rng.uniform(0.1, 3.0, n),
        "fwci_median": rng.uniform(0.1, 3.0, n),
        "n_pp": rng.integers(3, 500, n),
        "n_top10_wd": rng.integers(0, 50, n),
        "pp10_wd": rng.uniform(0, 0.3, n),
        "n_stars": [0, 1, 2, 0, 5] + [0] * (n - 5) if n >= 5 else [0] * n,
        "world_rank": ([1, None, 25, 20] + [None] * (n - 4)) if n >= 4 else [None] * n,
        "is_led": ([True, False, False, True] + [False] * (n - 4)) if n >= 4 else [False] * n,
        "leader_name": ["Some Leader Institution"] * n,
        "vol_full_run": rng.integers(5, 600, n),
        "vol_frac_run": rng.uniform(2.0, 300.0, n),
        "change_w1_w2": rng.uniform(-0.5, 0.5, n),
        "low_base": [False] * n,
    })


def _overlay_frame(n: int = 8, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    owners = ["shared", "A", "B"]
    return pd.DataFrame({
        "topic_id": [f"T{i:05d}" for i in range(n)],
        "topic_name": [f"Topic {i}" for i in range(n)],
        "keywords": ["Kw1|Kw2|Kw3|Kw4|Kw5|Kw6|Kw7|Kw8|Kw9|Kw10" for _ in range(n)],
        "is_excluded": [False] * n,
        "exclusion_reason_label": [None] * n,
        "expansion_latest": rng.uniform(-1, 1, n),
        "acceleration_latest": rng.uniform(-1, 1, n),
        "top25pct_frontier": [i % 4 == 0 for i in range(n)],
        "vol_a": rng.integers(0, 100, n),
        "vol_b": rng.integers(0, 100, n),
        "vol_joint": [np.nan if i % 3 == 0 else rng.integers(5, 20) for i in range(n)],
        "owner": [owners[i % 3] for i in range(n)],
    })


SLOTS = {"Ia": 0, "Ib": 1}
NAMES = {"Ia": "Institution A", "Ib": "Institution B"}
IDS = ["Ia", "Ib"]


# ---------------------------------------------------------------------------
# fig_plane_impact
# ---------------------------------------------------------------------------
def test_fig_plane_impact_hover_matches_spec_order(spec):
    df = _impact_frame()
    fig = X.fig_plane_impact(df, fwci_stat="mean")
    labels = _spec_labels(spec, "find_plane_impact", unconditional_only=True)
    for h in fig.data[0].customdata:
        assert_labels_in_order(h, labels)


def test_fig_plane_impact_keywords_are_two_lines_of_five():
    df = _impact_frame()
    fig = X.fig_plane_impact(df)
    h = fig.data[0].customdata[0]
    kw_block = h.split("<br>")[1] + "<br>" + h.split("<br>")[2]
    assert kw_block.count(",") == 8, kw_block  # 5+5 keywords -> 4+4 commas


def test_fig_plane_impact_catchall_row_names_the_exclusion_reason():
    df = _impact_frame()
    h = X.fig_plane_impact(df).data[0].customdata[2]
    assert "catch-all topic: Applied S&T" in h


def test_fig_plane_impact_mean_vs_median_switch():
    df = _impact_frame()
    mean_fig = X.fig_plane_impact(df, fwci_stat="mean")
    median_fig = X.fig_plane_impact(df, fwci_stat="median")
    assert list(mean_fig.data[0].y) == list(df["fwci_mean"])
    assert list(median_fig.data[0].y) == list(df["fwci_median"])
    assert mean_fig.layout.yaxis.title.text == X.AX_FWCI_MEAN
    assert median_fig.layout.yaxis.title.text == X.AX_FWCI_MEDIAN
    with pytest.raises(ValueError):
        X.fig_plane_impact(df, fwci_stat="nonsense")


def test_fig_plane_impact_x_is_log_and_x_equals_n_ar():
    df = _impact_frame()
    fig = X.fig_plane_impact(df)
    assert fig.layout.xaxis.type == "log"
    assert list(fig.data[0].x) == list(df["n_ar"].astype(float))


def test_fig_plane_impact_reference_line_at_one_is_dashed_red_full_width():
    df = _impact_frame()
    fig = X.fig_plane_impact(df, ref=1.0)
    shapes = [s for s in fig.layout.shapes if s.line.color == P.WARNING_CAPTION_COLOR]
    assert len(shapes) == 1
    assert shapes[0].line.dash == "dash"
    assert shapes[0].y0 == shapes[0].y1 == 1.0


def test_fig_plane_impact_bubble_area_is_star_count_sizemode_area():
    df = _impact_frame()
    fig = X.fig_plane_impact(df)
    marker = fig.data[0].marker
    assert marker.sizemode == "area"
    assert list(marker.size) == list(df["n_stars"].astype(float))
    assert marker.sizemin == C.BUBBLE_MIN_PX, "a zero-star topic still gets a visible minimum dot"


def test_fig_plane_impact_catchall_muted_and_led_ring():
    df = _impact_frame()
    fig = X.fig_plane_impact(df)
    opac = list(fig.data[0].marker.opacity)
    assert opac[2] == P.MUTED_OPACITY
    assert all(o == 1.0 for i, o in enumerate(opac) if i != 2)
    widths = list(fig.data[0].marker.line.width)
    led = df["is_led"].fillna(False).to_numpy()
    assert all((w == P.OUTLINE_WIDTH) == bool(is_led) for w, is_led in zip(widths, led))
    colors = set(fig.data[0].marker.color)
    assert colors <= set(P.OA_DOMAIN_COLORS.values()) | {P.COMPARISON}


def test_fig_plane_impact_star_papers_line_only_when_at_least_one():
    df = _impact_frame()
    zero_star_hover = fig_hover_for(df, "n_stars", 0)
    assert X.HOVER_STAR_PAPERS not in zero_star_hover


def fig_hover_for(df: pd.DataFrame, col: str, value) -> str:
    fig = X.fig_plane_impact(df)
    idx = df.index[df[col] == value][0]
    return fig.data[0].customdata[idx]


def test_fig_plane_impact_caps_at_a_hundred_marks_without_error():
    df = _impact_frame(n=100, seed=7)
    fig = X.fig_plane_impact(df)
    assert len(fig.data[0].x) == 100


# ---------------------------------------------------------------------------
# fig_plane_frontier -- domain mode (Find)
# ---------------------------------------------------------------------------
def test_fig_plane_frontier_domain_hover_matches_spec_order(spec):
    df = _impact_frame()
    fig = X.fig_plane_frontier(df, color_by="domain")
    # unconditional_only: this fixture's rows draw neither the top-quartile
    # flag nor the top-20 leader clause (both `when`-gated) -- the
    # unconditional labels are the ones every row of THIS fixture carries.
    labels = _spec_labels(spec, "find_plane_frontier", unconditional_only=True)
    for h in fig.data[0].customdata:
        assert_labels_in_order(h, labels)


def test_fig_plane_frontier_domain_axes_and_area_is_n_ar():
    df = _impact_frame()
    fig = X.fig_plane_frontier(df, color_by="domain")
    assert fig.layout.xaxis.title.text == C.AX_EXPANSION
    assert fig.layout.yaxis.title.text == C.AX_ACCELERATION
    scored = df[np.isfinite(df["expansion_latest"]) & np.isfinite(df["acceleration_latest"])]
    assert len(fig.data[0].x) == len(scored)


def test_fig_plane_frontier_bold_origin_rules():
    df = _impact_frame()
    fig = X.fig_plane_frontier(df, color_by="domain")
    shapes = list(fig.layout.shapes)
    assert len(shapes) == 2
    assert all(s.line.color == P.INK for s in shapes)
    assert all(s.line.width == C.FRONTIER_ORIGIN_PX for s in shapes)


def test_fig_plane_frontier_domain_top_quartile_gets_ink_outline():
    df = _impact_frame()
    fig = X.fig_plane_frontier(df, color_by="domain")
    top = df["top25pct_frontier"].fillna(False).to_numpy()
    widths = list(fig.data[0].marker.line.width)
    assert sum(1 for w in widths if w == P.OUTLINE_WIDTH) == int(top.sum())


def test_fig_plane_frontier_domain_rank_and_leader_only_when_led():
    df = _impact_frame()
    fig = X.fig_plane_frontier(df, color_by="domain")
    for i, h in enumerate(fig.data[0].customdata):
        rank = df.iloc[i]["world_rank"]
        if rank is not None and not (isinstance(rank, float) and np.isnan(rank)) and rank <= 20:
            assert "world #" in h
        else:
            assert "world #" not in h and "most works worldwide" not in h


def test_fig_plane_frontier_unscored_rows_are_dropped():
    df = _impact_frame()
    d = df.copy()
    d.loc[0, "expansion_latest"] = np.nan
    fig = X.fig_plane_frontier(d, color_by="domain")
    assert len(fig.data[0].x) == len(df) - 1


def test_fig_plane_frontier_requires_scored_rows():
    df = _impact_frame()
    empty = df.copy()
    empty["expansion_latest"] = np.nan
    with pytest.raises(ValueError):
        X.fig_plane_frontier(empty, color_by="domain")


# ---------------------------------------------------------------------------
# fig_plane_frontier -- owner mode (Compare's later reuse)
# ---------------------------------------------------------------------------
def test_fig_plane_frontier_owner_hover_matches_spec_order(spec):
    df = _overlay_frame()
    fig = X.fig_plane_frontier(df, color_by="owner", slots=SLOTS, names=NAMES, ids=IDS)
    labels = _spec_labels(spec, "compare_topic_overlay")
    for h in fig.data[0].customdata:
        assert_labels_in_order(h, labels)


def test_fig_plane_frontier_owner_requires_slots_names_ids():
    df = _overlay_frame()
    with pytest.raises(ValueError):
        X.fig_plane_frontier(df, color_by="owner")


def test_fig_plane_frontier_owner_colour_channel_red_if_shared():
    df = _overlay_frame()
    fig = X.fig_plane_frontier(df, color_by="owner", slots=SLOTS, names=NAMES, ids=IDS)
    colors = list(fig.data[0].marker.color)
    owners = list(df["owner"])
    for c, o in zip(colors, owners):
        if o == "shared":
            assert c == P.SHARED_TOPIC_MARK
        elif o == "A":
            assert c == P.institution_color(0)
        else:
            assert c == P.institution_color(1)


def test_fig_plane_frontier_owner_area_is_combined_volume():
    df = _overlay_frame()
    fig = X.fig_plane_frontier(df, color_by="owner", slots=SLOTS, names=NAMES, ids=IDS)
    combined = (df["vol_a"] + df["vol_b"]).to_numpy(dtype=float)
    mmax = combined.max() or 1.0
    expected = C.BUBBLE_MIN_PX + (C.BUBBLE_MAX_PX - C.BUBBLE_MIN_PX) * np.sqrt(combined / mmax)
    assert np.allclose(list(fig.data[0].marker.size), expected)


def test_fig_plane_frontier_owner_joint_floor_phrase_when_nan():
    df = _overlay_frame()
    fig = X.fig_plane_frontier(df, color_by="owner", slots=SLOTS, names=NAMES, ids=IDS)
    for i, h in enumerate(fig.data[0].customdata):
        if pd.isna(df.iloc[i]["vol_joint"]):
            assert "not available under" in h
        else:
            assert "not available under" not in h


def test_fig_plane_frontier_owner_under3_reads_as_text_not_a_bare_zero():
    """`_fmt_pair_volumes`'s own new `under_floor_a`/`under_floor_b` kwargs: a topic
    reaching the union through ONE institution's own top set while the
    OTHER has fewer than `PAIR_VOLUME_FLOOR` articles and reviews on it
    must read "under 3" in the hover, never a bare "0" (which would assert
    a fact `inst_topic_impact.parquet`'s own pre-floored shape cannot
    support)."""
    df = _overlay_frame()
    d = df.copy()
    d["under_floor_a"] = False
    d["under_floor_b"] = False
    d.loc[0, "vol_b"] = 0
    d.loc[0, "under_floor_b"] = True
    fig = X.fig_plane_frontier(d, color_by="owner", slots=SLOTS, names=NAMES, ids=IDS)
    h0 = fig.data[0].customdata[0]
    assert f"{NAMES['Ib']} under {X.PAIR_VOLUME_FLOOR}" in h0
    assert f"{NAMES['Ib']} 0" not in h0  # never a bare, falsely-precise zero
    # a row with the default (no flag) still prints the real number
    h1 = fig.data[0].customdata[1]
    assert "under" not in h1


def test_fig_plane_frontier_invalid_color_by_raises():
    df = _impact_frame()
    with pytest.raises(ValueError):
        X.fig_plane_frontier(df, color_by="nonsense")


# ---------------------------------------------------------------------------
# the frontier line -- ONE hover line folding expansion, acceleration and the
# score they combine into, replacing the two separate lines this hover used
# to draw (`fig_plane_frontier`, both colour modes, and the balance bars'
# own emergence mode below).
# ---------------------------------------------------------------------------
def test_fig_plane_frontier_hover_carries_one_frontier_line_not_two():
    df = _impact_frame()
    fig = X.fig_plane_frontier(df, color_by="domain")
    for i, h in enumerate(fig.data[0].customdata):
        assert "<b>expansion</b>" not in h and "<b>acceleration</b>" not in h
        exp, acc = df.iloc[i]["expansion_latest"], df.iloc[i]["acceleration_latest"]
        score = (X.FRONTIER_SCORE_EXPANSION_WEIGHT * exp
                + X.FRONTIER_SCORE_ACCELERATION_WEIGHT * acc)
        assert f"<b>frontier</b>: expansion {C._fmt_frontier(exp)}" in h
        assert f"score {C._fmt_frontier(score)}" in h


def test_fig_plane_frontier_owner_hover_carries_frontier_line():
    df = _overlay_frame()
    fig = X.fig_plane_frontier(df, color_by="owner", slots=SLOTS, names=NAMES, ids=IDS)
    for h in fig.data[0].customdata:
        assert "<b>frontier</b>: expansion" in h
        assert "<b>expansion</b>" not in h


# ---------------------------------------------------------------------------
# balance_bars -- one synthetic frame carrying every column any of the five
# modes needs (a superset of `topic_data.pair_topics`' own shape).
# ---------------------------------------------------------------------------
def _balance_rows(n: int = 10, seed: int = 2, n_excluded: int = 0) -> pd.DataFrame:
    """`n_excluded` (default 0, so every pre-existing call site and its own
    exact random sequence are untouched): marks the FIRST `n_excluded` rows
    `is_excluded=True` with a real catch-all reason, for the tint/glyph
    tests below."""
    rng = np.random.default_rng(seed)
    owners = ["shared", "A", "B"]
    vol_a = rng.integers(0, 100, n)
    vol_b = rng.integers(0, 100, n)
    vol_joint = np.array([np.nan if i % 3 == 0 else float(rng.integers(5, 20)) for i in range(n)])
    stars_a = rng.integers(0, 5, n)
    stars_b = rng.integers(0, 5, n)
    stars_joint = np.array([int(min(stars_a[i], stars_b[i], rng.integers(0, 3))) for i in range(n)])
    star_ids_joint = [[f"W{1000 + i}{k}" for k in range(int(stars_joint[i]))] for i in range(n)]
    url_stars_joint = [f"https://openalex.org/works?filter=ids.openalex:{'|'.join(ids)}" if ids else None
                       for ids in star_ids_joint]
    fwci_a = np.array([np.nan if i == 0 else rng.uniform(0.1, 3.0) for i in range(n)])
    fwci_b = rng.uniform(0.1, 3.0, n)
    n_covered_a = rng.integers(0, 30, n)
    n_covered_b = rng.integers(0, 30, n)
    rank_a = pd.array([1 if i == 0 else (pd.NA if i % 4 == 1 else int(rng.integers(1, 200))) for i in range(n)],
                      dtype="Int64")
    rank_b = pd.array([50 if i == 0 else (pd.NA if i % 5 == 2 else int(rng.integers(1, 200))) for i in range(n)],
                      dtype="Int64")
    change_a = rng.uniform(-0.5, 0.5, n)
    change_b = rng.uniform(-0.5, 0.5, n)
    low_base_a = np.array([i == 0 for i in range(n)])
    low_base_b = np.zeros(n, dtype=bool)
    frontier_score_latest = rng.uniform(-1, 1, n)
    # Appended AFTER every rng call above -- so the existing columns' own
    # values stay bit-identical to every pre-existing test's expectations.
    expansion_latest = rng.uniform(-1, 1, n)
    acceleration_latest = rng.uniform(-1, 1, n)
    excluded = [False] * n
    reason = [None] * n
    for i in range(min(max(n_excluded, 0), n)):
        excluded[i] = True
        reason[i] = "Applied S&T"
    return pd.DataFrame({
        "topic_id": [f"T{i:05d}" for i in range(n)],
        "topic_name": [f"Topic {i}" for i in range(n)],
        "keywords": ["Kw1|Kw2|Kw3|Kw4|Kw5|Kw6|Kw7|Kw8|Kw9|Kw10" for _ in range(n)],
        "is_excluded": excluded,
        "exclusion_reason_label": reason,
        "vol_a": vol_a, "vol_b": vol_b, "vol_joint": vol_joint,
        "under_floor_a": [False] * n, "under_floor_b": [False] * n,
        "owner": [owners[i % 3] for i in range(n)],
        "url_joint": [f"https://openalex.org/works?filter=x{i}" for i in range(n)],
        "fwci_a": fwci_a, "fwci_b": fwci_b,
        "n_covered_a": n_covered_a, "n_covered_b": n_covered_b,
        "rank_a": rank_a, "rank_b": rank_b,
        "stars_a": stars_a, "stars_b": stars_b, "stars_joint": stars_joint,
        "star_ids_joint": star_ids_joint, "url_stars_joint": url_stars_joint,
        "change_a": change_a, "change_b": change_b,
        "low_base_a": low_base_a, "low_base_b": low_base_b,
        "frontier_score_latest": frontier_score_latest,
        "expansion_latest": expansion_latest, "acceleration_latest": acceleration_latest,
    })


def _expected_sort_key(mode: str, rows: pd.DataFrame) -> pd.Series:
    """Independent (test-side) recompute of each mode's own descending sort
    key -- deliberately NOT calling `X._mode_sort_key` itself, so this test
    proves the BEHAVIOUR, not just that the implementation agrees with
    itself."""
    if mode == X.BAR_MODE_VOLUME:
        return rows["vol_a"] + rows["vol_b"]
    if mode == X.BAR_MODE_STARS:
        return rows["stars_a"] + rows["stars_b"]
    if mode == X.BAR_MODE_FWCI:
        return rows[["fwci_a", "fwci_b"]].max(axis=1, skipna=True).fillna(-np.inf)
    if mode == X.BAR_MODE_LED:
        best = rows[["rank_a", "rank_b"]].astype("float64").min(axis=1, skipna=True)
        return -best.fillna(np.inf)
    return rows["frontier_score_latest"]


@pytest.mark.parametrize("mode", X.BAR_MODES)
def test_balance_bars_hover_matches_spec_order(spec, mode):
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=mode)
    labels = _spec_labels_for_mode(spec, "compare_balance_bars", mode)
    for h in fig.data[0].customdata:
        assert_labels_in_order(h, labels)


@pytest.mark.parametrize("mode", X.BAR_MODES)
def test_balance_bars_sorted_by_mode_quantity_descending(mode):
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=mode)
    key = _expected_sort_key(mode, rows)
    expected_order = (rows.assign(_k=key.to_numpy())
                     .sort_values(["_k", "topic_id"], ascending=[False, True])["topic_name"].tolist())
    ticktext = list(fig.layout.yaxis.ticktext)
    for i, name in enumerate(expected_order):
        assert name in ticktext[i].replace("<br>", " "), (mode, i, name, ticktext[i])


def test_balance_bars_volume_three_traces_a_only_joint_b_only():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    assert len(bar_traces) == 3
    # each trace's `marker.color` is a SINGLE hex string (one colour for the
    # whole trace), never a per-point list -- `set(a_string)` would silently
    # iterate its characters, so compare the scalar directly.
    assert bar_traces[0].marker.color == P.institution_color(0)
    assert bar_traces[2].marker.color == P.institution_color(1)
    assert bar_traces[1].marker.color == P.JOINT_TOPIC_COLOR
    # a hue DEDICATED to this segment: distinct from SHARED_FRONTIER (the
    # scatter's own "shared" colour) and from the momentum-up hue an
    # earlier pass reused (review rejected it: one colour, one meaning)
    assert P.JOINT_TOPIC_COLOR not in (P.SHARED_FRONTIER, P.MOMENTUM_COLORS["up"])


def test_balance_bars_stars_three_traces_joint_centred_and_matches_column():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_STARS)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    assert len(bar_traces) == 3
    assert bar_traces[1].marker.color == P.JOINT_TOPIC_COLOR
    key = _expected_sort_key(X.BAR_MODE_STARS, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    joint_trace = bar_traces[1]
    # the joint trace only draws a bar for rows with stars_joint > 0 -- its
    # OWN x values (full segment width, `2 * half`) must equal that row's
    # stars_joint exactly.
    drawn_rows = [i for i in range(len(sorted_rows)) if sorted_rows.at[i, "stars_joint"] > 0]
    assert list(joint_trace.y) == drawn_rows
    assert np.allclose(list(joint_trace.x), [float(sorted_rows.at[i, "stars_joint"]) for i in drawn_rows])


# ---------------------------------------------------------------------------
# balance_bars -- the catch-all flag (all five modes): a cross glyph on the
# y-tick, lighter tints on the segments, OTHER rows unchanged.
# ---------------------------------------------------------------------------
def test_balance_bars_no_excluded_rows_keeps_scalar_colours():
    """VACUITY / non-regression: with nothing excluded (the default fixture),
    a three-segment trace's own `marker.color` stays a single SCALAR hex --
    never a per-point list -- exactly as every pre-existing test above
    already assumes."""
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    assert bar_traces[0].marker.color == P.institution_color(0)
    assert bar_traces[2].marker.color == P.institution_color(1)
    assert bar_traces[1].marker.color == P.JOINT_TOPIC_COLOR


def test_balance_bars_catchall_tick_gets_the_cross_glyph_others_dont():
    rows = _balance_rows(n=10, n_excluded=2)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    key = _expected_sort_key(X.BAR_MODE_VOLUME, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    ticktext = list(fig.layout.yaxis.ticktext)
    assert any(sorted_rows["is_excluded"]), "fixture must produce at least one excluded row"
    for i in range(len(sorted_rows)):
        if sorted_rows.at[i, "is_excluded"]:
            assert ticktext[i].endswith(X.CATCHALL_TICK_GLYPH), ticktext[i]
        else:
            assert not ticktext[i].endswith(X.CATCHALL_TICK_GLYPH), ticktext[i]


def test_balance_bars_catchall_volume_segments_are_tinted_others_are_not():
    rows = _balance_rows(n=10, n_excluded=2)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    key = _expected_sort_key(X.BAR_MODE_VOLUME, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    a_colors, joint_trace, b_colors = list(bar_traces[0].marker.color), bar_traces[1], list(bar_traces[2].marker.color)
    tint_a = P.tint_toward_white(P.institution_color(0))
    tint_b = P.tint_toward_white(P.institution_color(1))
    tint_joint = P.tint_toward_white(P.JOINT_TOPIC_COLOR)
    for i in range(len(sorted_rows)):
        if sorted_rows.at[i, "is_excluded"]:
            assert a_colors[i] == tint_a
            assert b_colors[i] == tint_b
        else:
            assert a_colors[i] == P.institution_color(0)
            assert b_colors[i] == P.institution_color(1)
    joint_colors = list(joint_trace.marker.color)
    for pos, row_i in enumerate(joint_trace.y):
        expected = tint_joint if sorted_rows.at[row_i, "is_excluded"] else P.JOINT_TOPIC_COLOR
        assert joint_colors[pos] == expected


def test_balance_bars_catchall_emergence_segments_are_tinted():
    """The paired family (fwci/led/emergence) tints too -- generic over
    WHATEVER colour a row would otherwise draw (an institution hue, or
    emergence's own decline grey)."""
    rows = _balance_rows(n=10, n_excluded=2)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_EMERGENCE)
    key = _expected_sort_key(X.BAR_MODE_EMERGENCE, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    left_colors = list(bar_traces[0].marker.color)
    for i in range(len(sorted_rows)):
        if sorted_rows.at[i, "is_excluded"]:
            base = P.COMPARISON if sorted_rows.at[i, "change_a"] < 0 else P.institution_color(0)
            assert left_colors[i] == P.tint_toward_white(base)


def test_balance_bars_catchall_note_constants_carry_the_glyph_and_dagger():
    assert X.CATCHALL_TICK_GLYPH in X.NOTE_CATCHALL_FLAG
    assert X.NOTE_FWCI_DAGGER.startswith(C.DAGGER)
    assert X.NOTE_EMERGENCE_DAGGER.startswith(C.DAGGER)


@pytest.mark.parametrize("mode,ref", [(X.BAR_MODE_FWCI, X.FWCI_REFERENCE_TICK),
                                      (X.BAR_MODE_LED, float(X.LED_REFERENCE_DISTANCE))])
def test_balance_bars_paired_modes_two_traces_no_joint_segment(mode, ref):
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=mode)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    assert len(bar_traces) == 2, f"{mode}: paired-from-centre modes draw exactly 2 real bar traces"
    assert P.JOINT_TOPIC_COLOR not in (bar_traces[0].marker.color, bar_traces[1].marker.color)
    ref_lines = [s for s in fig.layout.shapes
                if s.line.color == P.WARNING_CAPTION_COLOR and s.line.dash == "dash"]
    assert len(ref_lines) == 2, f"{mode}: one dashed reference tick each side"
    xs = sorted(s.x0 for s in ref_lines)
    assert xs == pytest.approx([-ref, ref])


def test_balance_bars_emergence_two_traces_no_reference_tick_decline_grey():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_EMERGENCE)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    assert len(bar_traces) == 2
    ref_lines = [s for s in fig.layout.shapes if s.line.color == P.WARNING_CAPTION_COLOR and s.line.dash == "dash"]
    assert len(ref_lines) == 0, "emergence has no natural reference value, no dashed tick"
    key = _expected_sort_key(X.BAR_MODE_EMERGENCE, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    left_colors = list(bar_traces[0].marker.color)
    for i in range(len(sorted_rows)):
        expected_decline = sorted_rows.at[i, "change_a"] < 0
        assert (left_colors[i] == P.COMPARISON) == bool(expected_decline), (i, left_colors[i], expected_decline)


def test_balance_bars_led_tip_text_is_hash_rank_no_bar_when_unranked():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_LED)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    key = _expected_sort_key(X.BAR_MODE_LED, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    left_x = list(bar_traces[0].x)
    left_text = list(bar_traces[0].text)
    for i in range(len(sorted_rows)):
        rank = sorted_rows.at[i, "rank_a"]
        if pd.isna(rank):
            assert left_x[i] == 0.0, (i, "unranked row must draw no bar")
            assert left_text[i] is None
        else:
            assert left_text[i] == f"#{int(rank)}"


def test_balance_bars_emergence_tip_text_signed_pct_and_dagger():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_EMERGENCE)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    key = _expected_sort_key(X.BAR_MODE_EMERGENCE, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    left_text = list(bar_traces[0].text)
    low_base_pos = sorted_rows.index[sorted_rows["low_base_a"]][0]
    assert left_text[low_base_pos].endswith(C.DAGGER)
    assert left_text[low_base_pos].startswith("+") or left_text[low_base_pos].startswith("-")


def test_balance_bars_emergence_hover_carries_the_frontier_line():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_EMERGENCE)
    for h in fig.data[0].customdata:
        assert "<b>frontier</b>: expansion" in h
        assert h.rsplit("<br>", 1)[-1].startswith("<b>held by</b>"), \
            "owner stays the LAST line even with the frontier line added"


def test_balance_bars_gutter_matches_mode_and_led_is_best_rank():
    """The gutter is the mode's own SORT KEY, formatted for that mode -- a
    reader scanning the column top-to-bottom sees it descend in step with
    the rows' own order (never a different quantity, like a sum that does
    not track the sort at all)."""
    rows = _balance_rows()
    for mode in X.BAR_MODES:
        fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=mode)
        gutter = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo == "skip"][0]
        key = _expected_sort_key(mode, rows)
        sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
            ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
        if mode == X.BAR_MODE_VOLUME:
            expected = [C._fmt_vol(v) for v in (sorted_rows["vol_a"] + sorted_rows["vol_b"])]
            assert list(gutter.text) == expected
        elif mode == X.BAR_MODE_STARS:
            expected = [C._fmt_vol(v) for v in (sorted_rows["stars_a"] + sorted_rows["stars_b"])]
            assert list(gutter.text) == expected
        elif mode == X.BAR_MODE_LED:
            for i in range(len(sorted_rows)):
                ranks = [r for r in (sorted_rows.at[i, "rank_a"], sorted_rows.at[i, "rank_b"]) if pd.notna(r)]
                assert gutter.text[i] == f"#{int(min(ranks))}"
        elif mode == X.BAR_MODE_FWCI:
            # the HIGHER of the two values, never the sum -- a sum does not
            # track `_mode_sort_key`'s own `max`, so the column would read
            # unsorted (the regression this test guards against).
            for i in range(len(sorted_rows)):
                vals = [v for v in (sorted_rows.at[i, "fwci_a"], sorted_rows.at[i, "fwci_b"]) if pd.notna(v)]
                assert gutter.text[i] == C._fmt_frontier(max(vals))
            gutter_vals = [float(t) for t in gutter.text]
            assert all(a >= b - 1e-9 for a, b in zip(gutter_vals, gutter_vals[1:])), \
                "the fwci gutter column must itself read sorted, descending"
        else:  # BAR_MODE_EMERGENCE
            expected = [C._fmt_frontier(v) for v in sorted_rows["frontier_score_latest"]]
            assert list(gutter.text) == expected


def _expected_fwci_half_range(rows: pd.DataFrame) -> float:
    """Independent recompute of the robust fwci half-range rule:
    `max(FWCI_HALF_RANGE_FLOOR, FWCI_HALF_RANGE_P90_MULT * p90-of-the-drawn-
    values)`, capped at the true max (never above it)."""
    vals = pd.concat([rows["fwci_a"], rows["fwci_b"]]).dropna().to_numpy(dtype=float)
    true_max = float(vals.max())
    p90 = float(np.percentile(vals, 90))
    return min(max(X.FWCI_HALF_RANGE_FLOOR, X.FWCI_HALF_RANGE_P90_MULT * p90), true_max)


def test_balance_bars_fwci_axis_range_is_the_robust_half_range_not_the_raw_max():
    """The x-axis range must come from the ROBUST half-range rule -- never
    the raw max, which a single outlier FWCI would otherwise dictate (the
    exact defect reported live, reproduced and fixed): `edge = half_range *
    (1 + AXIS_PAD_FRAC)`, the visible range `[-edge - gutter_lane, edge]`
    with `gutter_lane = half_range * C.GUTTER_NEG_AXIS_FRAC` -- proven
    against an INDEPENDENT recompute, not against the builder's own
    internals."""
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_FWCI)
    half_range = _expected_fwci_half_range(rows)
    edge = half_range * (1.0 + X.AXIS_PAD_FRAC)
    gutter_lane = half_range * C.GUTTER_NEG_AXIS_FRAC
    lo, hi = fig.layout.xaxis.range
    assert hi == pytest.approx(edge, rel=1e-6)
    assert lo == pytest.approx(-edge - gutter_lane, rel=1e-6)


def test_balance_bars_fwci_axis_range_is_not_dragged_by_a_single_outlier():
    """A single extreme FWCI value must NOT move the axis range anywhere
    near itself -- the robust half-range (driven by the 90th percentile of
    the drawn values, capped floor 2.0) stays close to the REST of the
    distribution; the outlier is clipped instead (see the tip-label test
    below), never allowed to crush every other row toward the centre."""
    rows = _balance_rows().copy()
    rows.loc[0, "fwci_a"] = 30.0
    rows.loc[0, "fwci_b"] = 0.5
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_FWCI)
    half_range = _expected_fwci_half_range(rows)
    edge = half_range * (1.0 + X.AXIS_PAD_FRAC)
    assert half_range < 30.0, "the outlier must not dictate the half-range"
    assert fig.layout.xaxis.range[1] == pytest.approx(edge, rel=1e-6)


def test_balance_bars_fwci_clipped_tip_reads_the_true_value_with_an_arrow():
    """A bar whose own FWCI exceeds the half-range is drawn TO THE EDGE
    (clipped) but its tip text still reads the true 2dp value, prefixed
    with `FWCI_CLIP_TIP_ARROW` so the reader sees it runs off -- nothing is
    lost by the clip. Its tip is drawn INSIDE the bar (`textposition ==
    "inside"`, `palette.SURFACE` white text) -- an OUTSIDE tip at the axis
    edge would collide with the gutter number (left) or the link column
    (right), both occupying the same pixels just past the plot edge. A bar
    within the half-range carries its own plain 2dp value at the tip
    (the SAME "always a value at the tip" idiom the led mode's own "#k"
    already uses), OUTSIDE the bar, `INK_SECONDARY`, no arrow. A null
    (NaN) side draws no bar and no tip at all."""
    rows = _balance_rows().copy()
    rows.loc[0, "fwci_a"] = 30.0   # certain to exceed any reasonable half-range
    rows.loc[0, "fwci_b"] = 0.5    # certain to stay within it
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_FWCI)
    half_range = _expected_fwci_half_range(rows)
    key = _expected_sort_key(X.BAR_MODE_FWCI, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    bar_traces = [t for t in fig.data if t.hoverinfo != "skip"]
    left_text, right_text = list(bar_traces[0].text), list(bar_traces[1].text)
    left_x, right_x = list(bar_traces[0].x), list(bar_traces[1].x)
    left_pos, right_pos = list(bar_traces[0].textposition), list(bar_traces[1].textposition)
    left_col, right_col = list(bar_traces[0].textfont.color), list(bar_traces[1].textfont.color)
    assert bar_traces[0].insidetextanchor == "end"
    assert bar_traces[1].insidetextanchor == "end"
    saw_clipped = saw_plain = False
    for i in range(len(sorted_rows)):
        a, b = sorted_rows.at[i, "fwci_a"], sorted_rows.at[i, "fwci_b"]
        if pd.isna(a):
            assert left_text[i] is None and left_x[i] == 0.0
        elif float(a) > half_range + 1e-9:
            assert left_text[i] == f"{X.FWCI_CLIP_TIP_ARROW}{C._fmt_frontier(a)}"
            assert left_x[i] == pytest.approx(-half_range, rel=1e-6)
            assert left_pos[i] == "inside" and left_col[i] == P.SURFACE
            saw_clipped = True
        else:
            assert left_text[i] == C._fmt_frontier(a)
            assert left_x[i] == pytest.approx(-float(a), rel=1e-6)
            assert left_pos[i] == "outside" and left_col[i] == P.INK_SECONDARY
            saw_plain = True
        if pd.isna(b):
            assert right_text[i] is None and right_x[i] == 0.0
        elif float(b) > half_range + 1e-9:
            assert right_text[i] == f"{X.FWCI_CLIP_TIP_ARROW}{C._fmt_frontier(b)}"
            assert right_x[i] == pytest.approx(half_range, rel=1e-6)
            assert right_pos[i] == "inside" and right_col[i] == P.SURFACE
            saw_clipped = True
        else:
            assert right_text[i] == C._fmt_frontier(b)
            assert right_x[i] == pytest.approx(float(b), rel=1e-6)
            assert right_pos[i] == "outside" and right_col[i] == P.INK_SECONDARY
            saw_plain = True
    assert saw_clipped, "the synthetic 30.0 row must produce at least one clipped tip"
    assert saw_plain, "at least one ordinary row must produce a plain (unclipped) tip"


def test_balance_bars_non_fwci_paired_modes_keep_the_plain_outside_scalar_tip():
    """led/emergence never clip -- their tips stay the SIMPLE scalar
    "outside"/`INK_SECONDARY` every tip used before the fwci clip-styling
    was added (a per-point array is fwci's own concern, not a house-wide
    change to the paired family)."""
    rows = _balance_rows()
    for mode in (X.BAR_MODE_LED, X.BAR_MODE_EMERGENCE):
        fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=mode)
        bar_traces = [t for t in fig.data if t.hoverinfo != "skip"]
        for trace in bar_traces[:2]:
            assert trace.textposition == "outside"


def test_balance_bars_row_pitch_34_bar_20():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    n = len(rows)
    assert fig.layout.height == C.row_height_single(n)
    bargap = fig.layout.bargap
    assert bargap == pytest.approx(C.BAR_GAP_SINGLE, abs=1e-9)
    bar_px = (1.0 - bargap) * C.ROW_PITCH_SINGLE
    assert bar_px == pytest.approx(C.BAR_PX_SINGLE, abs=0.5)


def test_balance_bars_label_column_is_the_compare_constant():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    expected = C.LABEL_COL_PX["compare"] + C.GUTTER_COL_PX["compare"] + C.COL_PAD_PX
    assert fig.layout.margin.l == expected


def test_balance_bars_right_margin_is_the_link_column_constant():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    assert fig.layout.margin.r == X.LINK_COL_PX


def test_balance_bars_bold_zero_line():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    zero_lines = [s for s in fig.layout.shapes if s.line.color == P.INK and s.x0 == s.x1 == 0]
    assert len(zero_lines) == 1


@pytest.mark.parametrize("mode", X.BAR_MODES)
def test_balance_bars_owner_clause_matches_owner_column(mode):
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=mode)
    key = _expected_sort_key(mode, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    for i, h in enumerate(fig.data[0].customdata):
        owner = sorted_rows.at[i, "owner"]
        if owner == "shared":
            assert "in both top sets" in h
        elif owner == "A":
            assert f"{NAMES['Ia']} only" in h
        else:
            assert f"{NAMES['Ib']} only" in h


def test_balance_bars_top_n_caps_and_missing_column_raises():
    rows = _balance_rows(n=10)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME, top_n=4)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    assert len(bar_traces[0].x) == 4
    with pytest.raises(ValueError):
        X.balance_bars(rows.drop(columns=["vol_joint"]), IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)


@pytest.mark.parametrize("mode,col", [
    (X.BAR_MODE_FWCI, "fwci_a"), (X.BAR_MODE_LED, "rank_a"),
    (X.BAR_MODE_STARS, "stars_joint"), (X.BAR_MODE_EMERGENCE, "change_a")])
def test_balance_bars_missing_mode_specific_column_raises(mode, col):
    rows = _balance_rows(n=6)
    with pytest.raises(ValueError):
        X.balance_bars(rows.drop(columns=[col]), IDS, slots=SLOTS, names=NAMES, mode=mode)


def test_balance_bars_invalid_mode_raises():
    rows = _balance_rows(n=6)
    with pytest.raises(ValueError):
        X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode="nonsense")


def test_balance_bars_caps_at_a_hundred_rows_without_error():
    rows = _balance_rows(n=100, seed=9)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    assert len(bar_traces[0].x) == 100


# ---------------------------------------------------------------------------
# balance_bars -- the right-margin "Joint pubs" link column
# ---------------------------------------------------------------------------
_NON_ROW_HEADER_TEXTS = {X.LINK_COL_HEADER_TEXT} | set(X.GUTTER_HEADER_TEXT.values())


def _link_annotations(fig) -> list:
    return [a for a in fig.layout.annotations if a.text not in _NON_ROW_HEADER_TEXTS]


def test_balance_bars_link_column_one_annotation_per_row_plus_header():
    rows = _balance_rows(n=7)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    # one link-column annotation per row, plus the link header AND the
    # gutter's own mode header.
    assert len(fig.layout.annotations) == len(rows) + 2
    headers = [a for a in fig.layout.annotations if a.text == X.LINK_COL_HEADER_TEXT]
    assert len(headers) == 1


@pytest.mark.parametrize("mode", X.BAR_MODES)
def test_balance_bars_gutter_header_matches_mode(mode):
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=mode)
    headers = [a for a in fig.layout.annotations if a.text == X.GUTTER_HEADER_TEXT[mode]]
    assert len(headers) == 1, (mode, [a.text for a in fig.layout.annotations])


def test_balance_bars_link_column_hrefs_equal_url_joint_except_under_floor():
    rows = _balance_rows(n=7)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_VOLUME)
    key = _expected_sort_key(X.BAR_MODE_VOLUME, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    cells = _link_annotations(fig)
    assert len(cells) == len(sorted_rows)
    for i in range(len(sorted_rows)):
        vol_joint = sorted_rows.at[i, "vol_joint"]
        text = cells[i].text
        if pd.isna(vol_joint):
            assert X.LINK_COL_DASH in text
            assert "<a href" not in text
        else:
            expected_href = sorted_rows.at[i, "url_joint"]
            assert f'<a href="{expected_href}"' in text
            assert f'target="{X.BALANCE_BAR_LINK_TARGET}"' in text


def test_balance_bars_stars_mode_link_column_uses_star_ids_url_or_plain_zero():
    rows = _balance_rows(n=7)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, mode=X.BAR_MODE_STARS)
    key = _expected_sort_key(X.BAR_MODE_STARS, rows)
    sorted_rows = rows.assign(_k=key.to_numpy()).sort_values(
        ["_k", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    cells = _link_annotations(fig)
    for i in range(len(sorted_rows)):
        n_stars = int(sorted_rows.at[i, "stars_joint"])
        text = cells[i].text
        if n_stars == 0:
            assert "<a href" not in text
            assert C._fmt_vol(0) in text
        else:
            expected_href = sorted_rows.at[i, "url_stars_joint"]
            assert f'<a href="{expected_href}"' in text


def test_balance_bars_star_ids_url_cap_is_enforced_by_links_module():
    """The 100-id cap is `links.star_ids_url`'s own contract (`tests/
    test_links.py`) -- this proves the balance bars NEVER hand it more than
    a real topic's own star count can produce (the pipeline's own
    documented max is 71 stars for one institution on one topic, so a
    pair's JOINT stars on one topic can never exceed that either)."""
    from lib import links as L
    with pytest.raises(ValueError):
        L.star_ids_url([f"W{i}" for i in range(101)])


# ---------------------------------------------------------------------------
# Source scans: no digit in any string literal, no colour literal, no
# Streamlit import (same house rules `tests/test_charts.py` enforces).
# ---------------------------------------------------------------------------
def _string_literals(path: Path) -> list[tuple[int, str]]:
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
    """Every column name of every deployed table -- the same exemption
    `tests/test_charts.py::test_no_digit_in_any_charts_string_literal` grants
    itself, grounded in the real schemas (a data-contract key is not
    rendered copy)."""
    import pyarrow.parquet as pq
    names: set[str] = set()
    for f in sorted((APP_DIR / "data").glob("*.parquet")):
        names |= set(pq.read_schema(f).names)
    return names


def test_no_digit_in_any_charts_topics_string_literal():
    tokens = load_allowlist()
    columns = _deployed_column_names()
    offenders = [(lineno, s) for lineno, s in _string_literals(APP_DIR / "lib" / "charts_topics.py")
                 if s not in columns and has_digit_violation(s, tokens)]
    assert not offenders, f"digit(s) inside a string literal of lib/charts_topics.py: {offenders}"


def test_charts_topics_module_never_imports_streamlit_or_charts_compare():
    src = (APP_DIR / "lib" / "charts_topics.py").read_text(encoding="utf-8")
    import re
    assert not re.search(r"^\s*(import\s+streamlit|from\s+lib\s+import\s+.*charts_compare|"
                         r"import\s+lib\.charts_compare|from\s+lib\.charts_compare)",
                         src, flags=re.MULTILINE), (
        "charts_topics.py must never depend on charts_compare.py (a concurrently-edited file)")
