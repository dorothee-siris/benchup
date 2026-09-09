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
            assert c == P.SHARED_FRONTIER
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


def test_balance_bars_owner_under3_reads_as_text_not_a_bare_zero():
    rows = _balance_rows()
    d = rows.copy()
    d["under_floor_a"] = False
    d["under_floor_b"] = False
    d.loc[0, "vol_a"] = 0
    d.loc[0, "under_floor_a"] = True
    fig = X.balance_bars(d, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
    # find the row now flagged, wherever sorting placed it
    sorted_d = d.sort_values(["n_ar_combined", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    flagged_pos = sorted_d.index[sorted_d["under_floor_a"]][0]
    h = fig.data[0].customdata[flagged_pos]
    assert f"under {X.PAIR_VOLUME_FLOOR}" in h


def test_fig_plane_frontier_invalid_color_by_raises():
    df = _impact_frame()
    with pytest.raises(ValueError):
        X.fig_plane_frontier(df, color_by="nonsense")


# ---------------------------------------------------------------------------
# balance_bars
# ---------------------------------------------------------------------------
def _balance_rows(n: int = 10, seed: int = 2) -> pd.DataFrame:
    df = _overlay_frame(n=n, seed=seed).rename(
        columns={"expansion_latest": "expansion", "acceleration_latest": "acceleration"})
    df["n_ar_combined"] = df["vol_a"] + df["vol_b"]
    return df


def test_balance_bars_hover_matches_spec_order(spec):
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
    labels = _spec_labels(spec, "compare_balance_bars")
    for h in fig.data[0].customdata:
        assert_labels_in_order(h, labels)


def test_balance_bars_sorted_by_caller_sort_col_descending():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
    n = len(rows)
    ticktext = list(fig.layout.yaxis.ticktext)
    combined_sorted = rows.sort_values(["n_ar_combined", "topic_id"], ascending=[False, True])
    for i, name in enumerate(combined_sorted["topic_name"]):
        assert name.replace(" ", "").lower() in ticktext[i].replace(" ", "").replace("<br>", " ").lower() \
            or name in ticktext[i].replace("<br>", " "), (i, name, ticktext[i])
    assert n == len(rows)


def test_balance_bars_three_traces_a_only_joint_b_only():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
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


def test_balance_bars_gutter_carries_combined_volume_no_header():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
    gutter = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo == "skip"][0]
    combined_sorted = rows.sort_values(["n_ar_combined", "topic_id"], ascending=[False, True])
    expected = [C._fmt_vol(v) for v in (combined_sorted["vol_a"] + combined_sorted["vol_b"])]
    assert list(gutter.text) == expected
    assert len(fig.layout.annotations) == 0, "no header text above the gutter"


def test_balance_bars_row_pitch_34_bar_20():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
    n = len(rows)
    assert fig.layout.height == C.row_height_single(n)
    bargap = fig.layout.bargap
    assert bargap == pytest.approx(C.BAR_GAP_SINGLE, abs=1e-9)
    bar_px = (1.0 - bargap) * C.ROW_PITCH_SINGLE
    assert bar_px == pytest.approx(C.BAR_PX_SINGLE, abs=0.5)


def test_balance_bars_label_column_is_the_compare_constant():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
    expected = C.LABEL_COL_PX["compare"] + C.GUTTER_COL_PX["compare"] + C.COL_PAD_PX
    assert fig.layout.margin.l == expected


def test_balance_bars_bold_zero_line():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
    zero_lines = [s for s in fig.layout.shapes if s.line.color == P.INK and s.x0 == s.x1 == 0]
    assert len(zero_lines) == 1


def test_balance_bars_owner_clause_matches_owner_column():
    rows = _balance_rows()
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
    combined_sorted = rows.sort_values(["n_ar_combined", "topic_id"], ascending=[False, True]).reset_index(drop=True)
    for i, h in enumerate(fig.data[0].customdata):
        owner = combined_sorted.iloc[i]["owner"]
        if owner == "shared":
            assert "in both top sets" in h
        elif owner == "A":
            assert f"{NAMES['Ia']} only" in h
        else:
            assert f"{NAMES['Ib']} only" in h


def test_balance_bars_top_n_caps_and_missing_column_raises():
    rows = _balance_rows(n=10)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined", top_n=4)
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    assert len(bar_traces[0].x) == 4
    with pytest.raises(ValueError):
        X.balance_bars(rows.drop(columns=["vol_joint"]), IDS, slots=SLOTS, names=NAMES,
                       sort_col="n_ar_combined")


def test_balance_bars_caps_at_a_hundred_rows_without_error():
    rows = _balance_rows(n=100, seed=9)
    fig = X.balance_bars(rows, IDS, slots=SLOTS, names=NAMES, sort_col="n_ar_combined")
    bar_traces = [t for t in fig.data if isinstance(t, go.Bar) and t.hoverinfo != "skip"]
    assert len(bar_traces[0].x) == 100


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
