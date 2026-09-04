"""
app/lib/charts_topics.py -- pure Plotly figure builders for the topic planes:
Find's "Topics: volume, impact and frontier" expander (`fig_plane_impact`,
`fig_plane_frontier` in `color_by="domain"` mode) and, for Compare's own
future use, its topic overlap (`fig_plane_frontier` in `color_by="owner"`
mode, `balance_bars`).

Same house rules as `lib/charts.py`: NO Streamlit import, NO `#RRGGBB`
literal (every hue comes from `lib.palette`), and every number format is
COMPOSED from an int constant, never typed as a digit inside a string
literal (`tests/test_charts_topics.py` scans this file the same way
`tests/test_charts.py` scans `lib/charts.py`). Every hover string is
pre-formatted Python, passed as `customdata` with
`hovertemplate="%{customdata}<extra></extra>"` -- the house mechanism every
builder in this app uses, never plotly's own `%{x:.1%}` templating.

This module imports ONLY `lib.charts` (the bar-layout contract: constants,
`_tick_label`, `_add_gutter_column`, `_base_layout`, `_nice_ticks`,
`row_height_single`, the small `_fmt_*` formatters) and `lib.palette` --
never `lib.charts_compare` or anything under Compare's own module, so a
topic-plane change here can never collide with independent work on that
file. Every field/subfield/domain constant it needs (`FRONTIER_ORIGIN`,
`BUBBLE_MIN_PX`/`MAX_PX`, `AX_EXPANSION`/`ACCELERATION`,
`HOVER_EXPANSION`/`ACCELERATION`) is already exported by `lib/charts.py`
for exactly this reuse.

TOOLTIP CONTRACT (`docs/tooltip_spec.yaml`): `fig_plane_impact` implements
`find_plane_impact`; `fig_plane_frontier` implements `find_plane_frontier`
(`color_by="domain"`) and `compare_topic_overlay` (`color_by="owner"`);
`balance_bars` implements `compare_balance_bars`. Field order, labels and
formats are taken from that file verbatim -- `tests/test_charts_topics.py`
loads it and asserts each builder's customdata carries the spec's labels,
in order.

THE JOINT-SEGMENT COLOUR (`balance_bars` needs a distinct colour for
"shared" in the scatter and for copublications in the bars): the scatter's
"shared" mark is `palette.SHARED_FRONTIER` (the dark red every pooled-
frontier view already uses); the bar chart's "joint" segment is
`palette.MOMENTUM_COLORS["up"]` (the SAME hue as `palette.
ERC_DOMAIN_COLORS["LS"]`, a saturated green) -- picked FROM the existing
palette (no new hex), never SHARED_FRONTIER itself. Chosen because it is
the only non-institution, non-SHARED_FRONTIER hue already validated
(`design-system/palette_validation.txt` run 37) against every colour this
figure and the SHARED_FRONTIER scatter can co-occur with in sequential
memory: comfortably clear of SHARED_FRONTIER (the ERC trio's own worst-case
normal-vision distance to it, run 37), and a different hue family entirely
from the navy institution trio (saturated green vs. desaturated blue-grey)
-- so a reader who has just seen the red "shared" bubble on the scatter
above does not mistake the bars' green segment for the same fact restated.
The one disclosed residual: this same hue also means "momentum: up" in
Compare's OWN relationship section (`palette.MOMENTUM_COLORS["up"]`) -- a
different section of the same page, never on screen at the same time as
this chart, and the joint segment is never colour-alone (its own hover
line and the section's caption both name it "joint" in words). Flagged
for confirmation or override at review.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from lib import charts as C
from lib import palette as P

# ---------------------------------------------------------------------------
# Small constants (ints/floats only in code; every string below is either
# digit-free or an f-string composed from one of these -- this module's own
# digit-ban, identical mechanism to `lib/charts.py`'s).
# ---------------------------------------------------------------------------
WORLD_LEADERBOARD_SIZE = 200     # topic_leaders.parquet's own rank range, 1..200
FIND_LED_RANK_FLOOR = 20         # "topics led" -- world rank at or above this
JOINT_FLOOR = 5                  # collab_topic_vols' own joint-publication floor


def _is_na(v) -> bool:
    """A single-value missing check that is robust across every missing
    representation this app's frames can carry a value in: plain `None`,
    `float('nan')`, and pandas' own nullable-dtype sentinel `pd.NA` (which
    `isinstance(v, float)` does NOT catch -- a nullable `Int64`/`boolean`
    column's missing cell is `pd.NA`, not `np.nan`, and `topic_data.
    institution_topics`'s own `world_rank` column is exactly this dtype)."""
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


OWNER_A = "A"
OWNER_B = "B"
OWNER_SHARED = "shared"
OWNERS = (OWNER_A, OWNER_B, OWNER_SHARED)

COLOR_BY_DOMAIN = "domain"
COLOR_BY_OWNER = "owner"
COLOR_BY_MODES = (COLOR_BY_DOMAIN, COLOR_BY_OWNER)

FRONTIER_FLAG_TEXT = "in the global top quarter of emergence"
AXIS_PAD_FRAC = 0.20   # balance_bars' own diverging-axis headroom, matching
                       # the equivalent constant `charts_compare.mirror_frontier`
                       # already uses for the same "outer-end label never
                       # collides with the plot frame" job

# The bar-family contract: balance_bars is ONE bar per topic (a
# floating three-segment row, not a bar-family trace, but its PITCH and BAR
# THICKNESS converge on the single-bar form ("one-bar
# row pitch 34 px, bar 20 px").
BALANCE_BAR_LINK_TARGET = "_blank"

AX_N_AR_CORE = f"Articles and reviews {C.CORE_WINDOW_START}-{C.CORE_WINDOW_END}, full counting"
AX_FWCI_MEAN = "FWCI_EU (mean)"
AX_FWCI_MEDIAN = "FWCI_EU (median)"

HOVER_N_AR_CORE = f"articles and reviews {C.CORE_WINDOW_START}-{C.CORE_WINDOW_END}, full counting"
HOVER_FWCI_EU = "FWCI_EU"
HOVER_STAR_PAPERS = "star papers"
HOVER_VOL_PAIR_RUN_ALL_TYPES = (
    f"whole run {C.RUN_WINDOW_START}-{C.RUN_WINDOW_END}, all document types")
HOVER_EXPANSION = C.HOVER_EXPANSION
HOVER_ACCELERATION = C.HOVER_ACCELERATION
HOVER_PUBLICATIONS_CORE_PAIR = f"publications {C.CORE_WINDOW_START}-{C.CORE_WINDOW_END}, full counting"
HOVER_JOINT_PUBLICATIONS = "joint publications"


# ---------------------------------------------------------------------------
# Shared per-topic formatters -- `docs/tooltip_spec.yaml`'s own `formats:`
# block, the entries none of `lib/charts.py`'s existing `_fmt_*` helpers
# already cover (topic name flagging, keywords, rank/leader, pair volumes,
# joint-or-floor, owner clause).
# ---------------------------------------------------------------------------

def _fmt_topic_name_flagged(name, is_excluded, exclusion_reason_label) -> str:
    """`topic_name_flagged`: the name, plus ' - catch-all topic: {label}'
    when the topic is on the catch-all list."""
    if is_excluded:
        label = P.NA_MARK if _is_na(exclusion_reason_label) else str(exclusion_reason_label)
        return f"{name} - catch-all topic: {label}"
    return str(name)


def _fmt_keywords_2x5(keywords) -> str:
    """`keywords_2x5`: the topic's 10 pipe-delimited keywords, comma-
    separated, as TWO lines of five (one `<br>` inside this single hover
    "line" -- it counts as 2 against the 8-line cap, never as 1)."""
    if _is_na(keywords):
        return P.NA_MARK
    parts = [k.strip() for k in str(keywords).split("|") if k.strip()]
    line1 = ", ".join(parts[:5])
    line2 = ", ".join(parts[5:10])
    return f"{line1}<br>{line2}" if line2 else line1


def _fmt_rank_and_leader(rank, leader_name) -> str | None:
    """`rank_and_leader`: "world #4 of 200 - most works: {institution}" when
    `rank` is at/above `FIND_LED_RANK_FLOOR`, else "most works worldwide:
    {institution}". `None` (never a fabricated line) when `leader_name`
    itself is unknown -- the caller omits the whole line in that case."""
    if _is_na(leader_name):
        return None
    if not _is_na(rank) and int(rank) <= FIND_LED_RANK_FLOOR:
        return f"world #{int(rank)} of {WORLD_LEADERBOARD_SIZE} - most works: {leader_name}"
    return f"most works worldwide: {leader_name}"


def _fmt_pair_volumes(name_a, vol_a, name_b, vol_b) -> str:
    """`pair_volumes`: one volume per institution, in slot order --
    "{name A} 120 - {name B} 84"."""
    return f"{name_a} {C._fmt_vol(vol_a)} - {name_b} {C._fmt_vol(vol_b)}"


def _fmt_joint_or_floor(vol_joint) -> str:
    """`joint_or_floor`: the joint count, or the fixed floor phrase under
    `JOINT_FLOOR` joint publications (a missing/NaN `vol_joint` means the
    pair does not clear the floor -- `collab_topic_vols.parquet`'s own
    convention, ships only qualifying pairs)."""
    if _is_na(vol_joint):
        return f"joint count not available under {JOINT_FLOOR} joint publications"
    return C._fmt_vol(vol_joint)


def _fmt_owner_clause(owner, name_a, name_b) -> str:
    """`owner_clause`: "in both top sets" when shared, otherwise
    "{institution} only"."""
    if owner == OWNER_SHARED:
        return "in both top sets"
    if owner == OWNER_A:
        return f"{name_a} only"
    if owner == OWNER_B:
        return f"{name_b} only"
    return P.NA_MARK


# ---------------------------------------------------------------------------
# 1. Plane A -- Volume and impact: x = n_ar (log), y = FWCI_EU mean|median
# ---------------------------------------------------------------------------

def fig_plane_impact(
    df: pd.DataFrame,
    *,
    fwci_stat: str = "mean",
    ref: float = 1.0,
) -> go.Figure:
    """One bubble per topic of `df` (`topic_data.institution_topics`'
    shape): x = `n_ar` on a LOG axis, y = `fwci_mean` or `fwci_median`,
    bubble AREA = `n_stars` (plotly-native `sizemode="area"`, one `sizeref`
    for the whole plane, `sizemin` guaranteeing a visible dot at zero
    stars), colour = OpenAlex domain, catch-all topics (`is_excluded`) at
    `palette.MUTED_OPACITY`, a topic this institution LEADS (`is_led`)
    carries a thin `palette.INK` ring. A full-width dashed red line marks
    `ref` (the FWCI neutral value, 1.0) on the y axis.

    The caller (`topic_data.institution_topics`, itself built from
    `inst_topic_impact.parquet`, floored upstream at n_ar>=3) is expected to
    hand this builder only topics with a defined FWCI -- verified on the
    shipped data, every row already has n_covered>=3 by construction (the
    file's own minimum is exactly 3), so the FWCI_EU hover line always has
    real data to draw; this builder does not re-filter.

    `fwci_stat`: "mean" (default) or "median" -- picks BOTH the y column and
    the axis title (`AX_FWCI_MEAN`/`AX_FWCI_MEDIAN`); the hover's own
    FWCI_EU line always states BOTH statistics regardless (`fwci_pair_2dp`)."""
    if fwci_stat not in ("mean", "median"):
        raise ValueError(f"fwci_stat must be 'mean' or 'median', got {fwci_stat!r}")
    d = df.reset_index(drop=True)
    n = len(d)
    x = pd.to_numeric(d["n_ar"], errors="coerce").to_numpy(dtype=float)
    y_col = "fwci_mean" if fwci_stat == "mean" else "fwci_median"
    y = pd.to_numeric(d[y_col], errors="coerce").to_numpy(dtype=float)
    stars = pd.to_numeric(d["n_stars"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    colors = [P.domain_color(v) for v in d["domain_id"]]
    excluded = (d["is_excluded"].fillna(False).to_numpy(dtype=bool)
                if "is_excluded" in d.columns else np.zeros(n, dtype=bool))
    is_led = (d["is_led"].fillna(False).to_numpy(dtype=bool)
              if "is_led" in d.columns else np.zeros(n, dtype=bool))

    hover = []
    for i in range(n):
        row = d.iloc[i]
        parts = [
            _fmt_topic_name_flagged(row["topic_name"], excluded[i], row.get("exclusion_reason_label")),
            _fmt_keywords_2x5(row.get("keywords")),
            f"{HOVER_N_AR_CORE}{C.THIN_SPACE}{C._fmt_vol(row['n_ar'])}",
            f"{HOVER_FWCI_EU}{C.THIN_SPACE}"
            f"{C._fmt_fwci_pair(row.get('fwci_mean'), row.get('fwci_median'), row.get('n_covered'))}",
        ]
        n_stars_v = row.get("n_stars")
        if not _is_na(n_stars_v) and float(n_stars_v) >= 1:
            parts.append(f"{HOVER_STAR_PAPERS}{C.THIN_SPACE}{C._fmt_vol(n_stars_v)}")
        parts.append(f"{HOVER_VOL_PAIR_RUN_ALL_TYPES}{C.THIN_SPACE}"
                     f"{C._fmt_vol_pair(row.get('vol_full_run'), row.get('vol_frac_run'))}")
        rank_leader = _fmt_rank_and_leader(row.get("world_rank"), row.get("leader_name"))
        if rank_leader is not None:
            parts.append(rank_leader)
        hover.append("<br>".join(parts))

    star_max = float(stars.max()) if n and np.isfinite(stars).any() else 0.0
    size_ref = 2.0 * max(star_max, 1.0) / (C.BUBBLE_MAX_PX ** 2)
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="markers",
        marker=dict(
            color=colors,
            size=stars, sizemode="area", sizeref=size_ref, sizemin=C.BUBBLE_MIN_PX,
            opacity=[P.MUTED_OPACITY if e else 1.0 for e in excluded],
            line=dict(color=[P.INK if led else P.SURFACE for led in is_led],
                      width=[P.OUTLINE_WIDTH if led else C.HAIRLINE_PX for led in is_led]),
        ),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False,
    ))
    fig.add_hline(y=ref, line=dict(color=P.WARNING_CAPTION_COLOR, width=C.LINE_PX, dash="dash"))
    fig.update_xaxes(type="log", title_text=AX_N_AR_CORE,
                     gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)
    fig.update_yaxes(title_text=(AX_FWCI_MEAN if fwci_stat == "mean" else AX_FWCI_MEDIAN),
                     gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)
    return C._base_layout(fig, C.SCATTER_HEIGHT, margin=dict(t=C.BASE_PX // 2, l=8, r=16, b=C.BASE_PX))


# ---------------------------------------------------------------------------
# 2. Plane B -- Frontier: x = expansion, y = acceleration
# ---------------------------------------------------------------------------

def fig_plane_frontier(
    df: pd.DataFrame,
    *,
    color_by: str = COLOR_BY_DOMAIN,
    slots: Mapping | None = None,
    names: Mapping | None = None,
    ids: Sequence | None = None,
) -> go.Figure:
    """One bubble per SCORED topic of `df`: x = `expansion_latest`, y =
    `acceleration_latest`, BOLD `palette.INK` rules at the origin on both
    axes (the quadrant split, the frontier map's own bold-origin semantics -- the one
    line allowed to out-weigh the grid), a top-quartile topic
    (`top25pct_frontier`) carries an INK outline.

    `color_by="domain"` (Find): colour = OpenAlex domain (`domain_id`),
    bubble area proportional to `n_ar` (the SAME measure plane A puts on
    its own x axis) -- hover per `find_plane_frontier`.

    `color_by="owner"` (Compare's own future topic overlap): colour =
    the institution that exclusively holds the topic
    (`palette.institution_color`, resolved via `slots`/`ids`) or
    `palette.SHARED_FRONTIER` when `owner` is `"shared"` (both institutions'
    top sets), bubble area proportional to `combined_vol` (`vol_a+vol_b`,
    computed here when the caller does not already carry it). A shared
    topic ALSO carries `palette.FRONTIER_SHARED_HALO` (a SURFACE-coloured
    ring, `1.5` px) -- distinct from, and subordinate to, the top-quartile
    INK outline when a mark is both. Hover per `compare_topic_overlay`.
    Requires `slots`, `names` and `ids` (`[id_a, id_b]`, slot order).

    Rows with no score (`expansion_latest`/`acceleration_latest` NaN) are
    DROPPED -- the caller's caption states how many (`topic_data.
    topic_set_caption`'s `n_no_frontier`)."""
    if color_by not in COLOR_BY_MODES:
        raise ValueError(f"color_by must be one of {COLOR_BY_MODES}, got {color_by!r}")
    if color_by == COLOR_BY_OWNER and (slots is None or names is None or ids is None or len(ids) < 2):
        raise ValueError("color_by='owner' needs slots, names and ids=[id_a, id_b]")

    d = df[np.isfinite(pd.to_numeric(df["expansion_latest"], errors="coerce"))
          & np.isfinite(pd.to_numeric(df["acceleration_latest"], errors="coerce"))].reset_index(drop=True)
    n = len(d)
    if n == 0:
        raise ValueError("no scored topics to draw")
    x = d["expansion_latest"].to_numpy(dtype=float)
    y = d["acceleration_latest"].to_numpy(dtype=float)
    top = (d["top25pct_frontier"].fillna(False).to_numpy(dtype=bool)
           if "top25pct_frontier" in d.columns else np.zeros(n, dtype=bool))
    excluded = (d["is_excluded"].fillna(False).to_numpy(dtype=bool)
                if "is_excluded" in d.columns else np.zeros(n, dtype=bool))

    if color_by == COLOR_BY_DOMAIN:
        size_col_vals = pd.to_numeric(d["n_ar"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        colors = [P.domain_color(v) for v in d["domain_id"]]
        line_color = [P.INK if t else P.SURFACE for t in top]
        line_width = [P.OUTLINE_WIDTH if t else C.HAIRLINE_PX for t in top]
    else:
        if "combined_vol" in d.columns:
            size_col_vals = pd.to_numeric(d["combined_vol"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        else:
            size_col_vals = (pd.to_numeric(d["vol_a"], errors="coerce").fillna(0.0)
                             + pd.to_numeric(d["vol_b"], errors="coerce").fillna(0.0)).to_numpy(dtype=float)
        slot_a, slot_b = int(slots.get(ids[0], -1)), int(slots.get(ids[1], -1))
        color_a, color_b = P.institution_color(slot_a), P.institution_color(slot_b)
        is_shared = (d["owner"] == OWNER_SHARED).to_numpy()
        colors = [P.SHARED_FRONTIER if sh else (color_a if o == OWNER_A else color_b)
                  for sh, o in zip(is_shared, d["owner"])]
        halo_color = P.FRONTIER_SHARED_HALO["color"]
        halo_w = P.FRONTIER_SHARED_HALO["width"]
        line_color = [P.INK if t else (halo_color if sh else P.SURFACE)
                     for t, sh in zip(top, is_shared)]
        line_width = [P.OUTLINE_WIDTH if t else (halo_w if sh else C.HAIRLINE_PX)
                     for t, sh in zip(top, is_shared)]

    mmax = float(size_col_vals.max()) if n and size_col_vals.max() > 0 else 1.0
    sizes = C.BUBBLE_MIN_PX + (C.BUBBLE_MAX_PX - C.BUBBLE_MIN_PX) * np.sqrt(size_col_vals / mmax)

    hover = []
    for i in range(n):
        row = d.iloc[i]
        parts = [
            _fmt_topic_name_flagged(row["topic_name"], excluded[i], row.get("exclusion_reason_label")),
            _fmt_keywords_2x5(row.get("keywords")),
            f"{HOVER_EXPANSION}{C.THIN_SPACE}{C._fmt_frontier(x[i])}",
            f"{HOVER_ACCELERATION}{C.THIN_SPACE}{C._fmt_frontier(y[i])}",
        ]
        if color_by == COLOR_BY_DOMAIN:
            parts.append(f"{HOVER_N_AR_CORE}{C.THIN_SPACE}{C._fmt_vol(row['n_ar'])}")
            if top[i]:
                parts.append(FRONTIER_FLAG_TEXT)
            rank_leader = None
            rank = row.get("world_rank")
            if not _is_na(rank) and int(rank) <= FIND_LED_RANK_FLOOR:
                rank_leader = _fmt_rank_and_leader(rank, row.get("leader_name"))
            if rank_leader is not None:
                parts.append(rank_leader)
        else:
            name_a, name_b = str(names.get(ids[0], ids[0])), str(names.get(ids[1], ids[1]))
            parts.append(f"{HOVER_PUBLICATIONS_CORE_PAIR}{C.THIN_SPACE}"
                         f"{_fmt_pair_volumes(name_a, row.get('vol_a'), name_b, row.get('vol_b'))}")
            parts.append(f"{HOVER_JOINT_PUBLICATIONS}{C.THIN_SPACE}"
                         f"{_fmt_joint_or_floor(row.get('vol_joint'))}")
            parts.append(_fmt_owner_clause(row.get("owner"), name_a, name_b))
        hover.append("<br>".join(parts))

    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="markers",
        marker=dict(color=colors, size=sizes, sizemode="diameter",
                    opacity=[P.MUTED_OPACITY if e else 1.0 for e in excluded],
                    line=dict(color=line_color, width=line_width)),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False,
    ))
    fig.add_vline(x=C.FRONTIER_ORIGIN, line=dict(color=P.INK, width=C.FRONTIER_ORIGIN_PX))
    fig.add_hline(y=C.FRONTIER_ORIGIN, line=dict(color=P.INK, width=C.FRONTIER_ORIGIN_PX))
    fig.update_xaxes(title_text=C.AX_EXPANSION, gridcolor=P.GRID,
                     zerolinecolor=P.GRID, linecolor=P.BORDER)
    fig.update_yaxes(title_text=C.AX_ACCELERATION, gridcolor=P.GRID,
                     zerolinecolor=P.GRID, linecolor=P.BORDER)
    return C._base_layout(fig, C.SCATTER_HEIGHT, margin=dict(t=C.BASE_PX // 2, l=8, r=16, b=C.BASE_PX))


# ---------------------------------------------------------------------------
# 3. balance_bars -- the mirror chart generalised (Compare's topic overlap,
#    Compare's own future UI; built and tested here on synthetic frames)
# ---------------------------------------------------------------------------

def balance_bars(
    rows: pd.DataFrame,
    ids: Sequence,
    *,
    slots: Mapping,
    names: Mapping,
    sort_col: str,
    top_n: int | None = None,
) -> go.Figure:
    """One row per topic: A-only publications LEFT of a bold zero in A's
    colour, JOINT publications centred in `palette.MOMENTUM_COLORS["up"]`
    (module docstring: the joint-segment colour, distinct from the scatter's
    `palette.SHARED_FRONTIER`), B-only RIGHT in B's colour -- the same
    floating three-segment geometry `charts_compare.mirror_frontier` uses,
    generalised: sort by the CALLER's own `sort_col` (descending, `topic_id`
    ascending tie-break) rather than a fixed combined-volume rule, and a
    GUTTER column ("every gutter... aligned vertically") carrying the
    row's combined volume (`vol_a+vol_b`) -- `mirror_frontier` itself has no
    gutter column; this generalised form adds one.

    On the bar-layout contract: the Compare label column
    (`charts.LABEL_COL_PX["compare"]`), one-bar row pitch (34 px,
    `ROW_PITCH_SINGLE`) and bar thickness (20 px, `BAR_PX_SINGLE`), no
    header text above the gutter. Hover per `compare_balance_bars`.

    INPUT FRAME CONTRACT (one row per topic): `topic_id`, `topic_name`,
    `keywords`, `is_excluded`, `exclusion_reason_label`, `vol_a`, `vol_b`,
    `vol_joint` (NaN under `JOINT_FLOOR`), `expansion`, `acceleration`,
    `owner` (`"A"`/`"B"`/`"shared"`), and `sort_col` itself.

    `ids`/`slots`/`names`: the two compared institutions, in slot order --
    `ids=[id_a, id_b]` matching `vol_a`/`vol_b`'s own order."""
    required = ("topic_id", "topic_name", "vol_a", "vol_b", "vol_joint",
               "expansion", "acceleration", "owner", sort_col)
    for col in required:
        if col not in rows.columns:
            raise ValueError(f"missing column {col!r}")
    if len(ids) < 2:
        raise ValueError("balance_bars needs ids=[id_a, id_b]")

    d = rows.sort_values([sort_col, "topic_id"], ascending=[False, True], kind="mergesort")
    if top_n is not None and top_n > 0:
        d = d.head(int(top_n))
    d = d.reset_index(drop=True)
    n = len(d)
    if n == 0:
        raise ValueError("no topics to draw")

    id_a, id_b = ids[0], ids[1]
    name_a, name_b = str(names.get(id_a, id_a)), str(names.get(id_b, id_b))
    color_a = P.institution_color(int(slots.get(id_a, -1)))
    color_b = P.institution_color(int(slots.get(id_b, -1)))
    joint_color = P.MOMENTUM_COLORS["up"]

    va = pd.to_numeric(d["vol_a"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    vb = pd.to_numeric(d["vol_b"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    vj_raw = pd.to_numeric(d["vol_joint"], errors="coerce")
    vj = vj_raw.fillna(0.0).to_numpy(dtype=float)
    joint_valid = (vj_raw.notna() & (vj_raw > 0)).to_numpy()
    combined = va + vb

    half = np.where(joint_valid, vj / 2.0, 0.0)
    a_only = np.maximum(0.0, va - np.where(joint_valid, vj, 0.0))
    b_only = np.maximum(0.0, vb - np.where(joint_valid, vj, 0.0))
    left_extent = half + a_only
    right_extent = half + b_only

    excluded = (d["is_excluded"].fillna(False).to_numpy(dtype=bool)
                if "is_excluded" in d.columns else np.zeros(n, dtype=bool))

    hover = []
    for i in range(n):
        row = d.iloc[i]
        parts = [
            _fmt_topic_name_flagged(row["topic_name"], excluded[i], row.get("exclusion_reason_label")),
            _fmt_keywords_2x5(row.get("keywords")),
            f"{HOVER_PUBLICATIONS_CORE_PAIR}{C.THIN_SPACE}"
            f"{_fmt_pair_volumes(name_a, row['vol_a'], name_b, row['vol_b'])}",
            f"{HOVER_JOINT_PUBLICATIONS}{C.THIN_SPACE}{_fmt_joint_or_floor(row.get('vol_joint'))}",
            f"{HOVER_EXPANSION}{C.THIN_SPACE}{C._fmt_frontier(row.get('expansion'))}",
            f"{HOVER_ACCELERATION}{C.THIN_SPACE}{C._fmt_frontier(row.get('acceleration'))}",
            _fmt_owner_clause(row.get("owner"), name_a, name_b),
        ]
        hover.append("<br>".join(parts))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(a_only), y=list(range(n)), base=list(-left_extent), orientation="h",
        marker=dict(color=color_a, line=dict(color=color_a, width=C.HAIRLINE_PX)),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False))
    joint_idx = [i for i in range(n) if joint_valid[i]]
    fig.add_trace(go.Bar(
        x=[2.0 * half[i] for i in joint_idx], y=joint_idx,
        base=[-half[i] for i in joint_idx], orientation="h",
        marker=dict(color=joint_color, line=dict(color=joint_color, width=C.HAIRLINE_PX)),
        customdata=[hover[i] for i in joint_idx],
        hovertemplate="%{customdata}<extra></extra>", showlegend=False))
    fig.add_trace(go.Bar(
        x=list(b_only), y=list(range(n)), base=list(half), orientation="h",
        marker=dict(color=color_b, line=dict(color=color_b, width=C.HAIRLINE_PX)),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False))

    names_ids = list(range(n))
    vmax = float(max(left_extent.max(), right_extent.max())) if n else 1.0
    vmax = vmax if vmax > 0 else 1.0
    pad = vmax * AXIS_PAD_FRAC
    edge = vmax + pad   # the diverging chart's own visible left/right edge

    # The gutter column: a phantom zero-fill bar carrying the row's
    # combined volume as outside text -- placed just PAST this chart's own
    # LEFT edge (`-edge`), never at a small offset from zero (this chart's
    # own "zero" is the diverging centre, already deep inside the plotted
    # bars, not a baseline the gutter can sit beside). `gutter_lane` reserves
    # the same fractional width `_add_gutter_column` uses for a single-sided
    # chart, just anchored at `-edge` instead of at 0.
    gutter_lane = vmax * C.GUTTER_NEG_AXIS_FRAC
    gutter_x = -edge - gutter_lane * C.GUTTER_TIP_FRAC
    fig.add_trace(go.Bar(
        x=[gutter_x] * n, y=names_ids, orientation="h",
        marker=dict(color=C.GUTTER_PHANTOM_FILL, line=dict(width=0)),
        text=[C._fmt_vol(v) for v in combined], textposition="outside", cliponaxis=False,
        textfont=dict(size=C.GUTTER_FONT_PX, color=P.INK_SECONDARY), constraintext="none",
        customdata=[""] * n, hoverinfo="skip", showlegend=False,
    ))
    fig.update_layout(barmode="overlay")
    fig.add_vline(x=0, line=dict(color=P.INK, width=C.FRONTIER_ORIGIN_PX))

    pairs = [C._tick_label(str(d.at[i, "topic_name"]), wrap_px=C.WRAP_PX["compare"]) for i in range(n)]
    styled = [s for _, s in pairs]
    fig.update_yaxes(tickmode="array", tickvals=names_ids, ticktext=styled,
                     range=[n - 0.5, -0.5], showgrid=False, automargin=True,
                     tickfont=dict(size=C.TICK_FONT_PX))

    ticks = [t for t in C._nice_ticks(vmax) if t > 0]
    fig.update_xaxes(
        range=[-edge - gutter_lane, edge], tickmode="array",
        tickvals=[-t for t in reversed(ticks)] + [0.0] + ticks,
        ticktext=([C._fmt_vol(t) for t in reversed(ticks)] + [C._fmt_vol(0.0)]
                  + [C._fmt_vol(t) for t in ticks]),
        title_text=C.AX_WORKS, gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)

    margin_l = C.LABEL_COL_PX["compare"] + C.GUTTER_COL_PX["compare"] + C.COL_PAD_PX
    return C._base_layout(fig, C.row_height_single(n), bargap=C.BAR_GAP_SINGLE,
                          margin=dict(t=C.BASE_PX // 2, l=margin_l, r=C.BASE_PX, b=C.BASE_PX))
