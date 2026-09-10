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
`palette.JOINT_TOPIC_COLOR` -- a hue DEDICATED to this one segment,
distinct from `palette.MOMENTUM_COLORS["up"]` (an earlier pass reused that
green, and review rejected it: one colour, one meaning, and this section's
own legend sits right beside the scatter above it, so the bars' centre
segment must never read as "momentum: up" restated). Full validation
(`design-system/palette_validation.txt` run 39): comfortably clear of both
institution navy slots, of SHARED_FRONTIER, and of the momentum hue it
replaces as a candidate, on the SAME co-occurrence screen SHARED_FRONTIER
itself was measured against (`palette.JOINT_TOPIC_COLOR`'s own docstring
carries the full per-pair numbers).
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
PAIR_VOLUME_FLOOR = 3            # topic_data.pair_topics' own per-institution floor
                                  # (inst_topic_impact.parquet's own n_ar>=3 minimum) --
                                  # below this an institution's OWN volume on a topic
                                  # its PARTNER'S top set pulled in is reported as the
                                  # bucketed 0 `pair_topics` ships, never a literal
                                  # zero-publications claim


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

# `balance_bars`' own five "Topics shown" modes -- MUST match
# `lib.topic_data.MODE_*` verbatim (duplicated here rather than imported, the
# SAME convention `OWNER_*` above already documents: no `lib/*_data.py`
# module in this codebase imports a `lib/charts*.py` module, and this module
# imports nothing below `lib.charts`/`lib.palette` by its own house rule --
# `tests/test_topic_data.py` cross-checks these five against `topic_data.
# MODES` directly, the same way it already cross-checks `OWNER_*`).
BAR_MODE_VOLUME = "volume"
BAR_MODE_FWCI = "fwci"
BAR_MODE_LED = "led"
BAR_MODE_STARS = "stars"
BAR_MODE_EMERGENCE = "emergence"
BAR_MODES = (BAR_MODE_VOLUME, BAR_MODE_FWCI, BAR_MODE_LED, BAR_MODE_STARS, BAR_MODE_EMERGENCE)

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
# (`docs/tooltip_spec.yaml`'s `label_style: bold_colon`): labels for the
# three lines that used to draw as a bare, unlabelled clause.
HOVER_TOPIC_LEADER = "topic leader"          # world_rank_and_leader
HOVER_FRONTIER_STANDING = "frontier standing"  # frontier_flag
HOVER_HELD_BY = "held by"                    # owner_clause

# `balance_bars`' own per-mode hover vocabulary (`docs/tooltip_spec.yaml`'s
# `compare_balance_bars` entry, five modes). The two change-window years are
# COMPOSED from int constants (this module's own digit-ban), duplicated from
# `topic_data.CHANGE_W1_YEARS`/`CHANGE_W2_YEARS` rather than imported -- same
# reasoning as `WORLD_LEADERBOARD_SIZE` above (a data-module constant a
# chart-layer builder needs only for its own label wording).
BAR_CHANGE_W1_START, BAR_CHANGE_W1_END = 2020, 2022
BAR_CHANGE_W2_START, BAR_CHANGE_W2_END = 2023, 2024
HOVER_WORLD_RANK_PAIR = "world rank"
HOVER_STAR_PAPERS_PAIR = "star papers"
HOVER_JOINT_STAR_PAPERS = "joint star papers"
HOVER_OWN_CHANGE_PAIR = (f"change {BAR_CHANGE_W1_START}-{BAR_CHANGE_W1_END} to "
                        f"{BAR_CHANGE_W2_START}-{BAR_CHANGE_W2_END}")

# The link column's fixed pixel width (Plotly annotations, `margin.r` --
# the design target is roughly an eighth of the chart width, a fixed px
# margin); 110px is roughly an eighth of
# this app's own 1280px reference layout width, the same reference the
# bar-layout contract's other fixed columns (`LABEL_COL_PX`) were sized
# against). BALANCE_BAR_LINK_TARGET (module header) is the anchor's own
# `target="_blank"`.
LINK_COL_PX = 110
LINK_COL_HEADER_TEXT = "Joint pubs"
LINK_COL_FONT_PX = C.GUTTER_FONT_PX     # same size as every other small chart label
LINK_COL_DASH = P.NA_MARK                # unlinked cell: pair under the joint floor
FWCI_REFERENCE_TICK = 1.0                 # the fwci mode's own red dashed tick, both sides
FWCI_HALF_RANGE_FLOOR = 2.0                # the fwci axis half-range never shrinks below this
FWCI_HALF_RANGE_P90_MULT = 1.25            # ... nor below 1.25x the 90th percentile of the
                                           # drawn values -- capped at the true max regardless
                                           # (a robust scale: one outlier never dictates it)
FWCI_CLIP_TIP_ARROW = "\N{BLACK RIGHT-POINTING SMALL TRIANGLE} "  # a fwci bar clipped at the
                                           # half-range keeps its real value at the tip, this
                                           # arrow marking "runs off the visible axis"
LED_REFERENCE_RANK = 20                   # the led mode's own red dashed tick (world #20)
LED_REFERENCE_DISTANCE = (WORLD_LEADERBOARD_SIZE + 1) - LED_REFERENCE_RANK  # 181


# ---------------------------------------------------------------------------
# Shared per-topic formatters -- `docs/tooltip_spec.yaml`'s own `formats:`
# block, the entries none of `lib/charts.py`'s existing `_fmt_*` helpers
# already cover (topic name flagging, keywords, rank/leader, pair volumes,
# joint-or-floor, owner clause).
# ---------------------------------------------------------------------------

def _fmt_topic_name_flagged(name, is_excluded, exclusion_reason_label) -> str:
    """`topic_name_flagged`: the PLAIN name, plus ' - catch-all topic:
    {label}' when the topic is on the catch-all list. Plain text on
    purpose: `views_compare.py`'s own topic TABLE ("Topic" column) calls
    this directly and renders it through a data-grid cell, never a hover --
    `<b>` markup there would leak as literal text, not bold. A hover
    caller wraps the SAME clause in bold via `_hover_topic_line1`, below,
    which keeps the flag text outside the bold span."""
    if is_excluded:
        label = P.NA_MARK if _is_na(exclusion_reason_label) else str(exclusion_reason_label)
        return f"{name} - catch-all topic: {label}"
    return str(name)


def _hover_topic_line1(name, is_excluded, exclusion_reason_label) -> str:
    """Line 1 of every topic HOVER (never the table): the bold entity,
    no label, the catch-all flag clause (if any) OUTSIDE the bold span --
    the same clause `_fmt_topic_name_flagged` computes, wrapped for a
    hover instead of a table cell."""
    if is_excluded:
        label = P.NA_MARK if _is_na(exclusion_reason_label) else str(exclusion_reason_label)
        return C.hover_entity(name, suffix=f" - catch-all topic: {label}")
    return C.hover_entity(name)


def _fmt_keywords_2x5(keywords) -> str:
    """`keywords_2x5`: `<b>keywords</b>: ` on the topic's first five
    pipe-delimited keywords, comma-separated, then a SECOND line of the
    next five with no repeated label (one `<br>` inside this single hover
    "line" -- it counts as 2 against the 8-line cap, never as 1)."""
    if _is_na(keywords):
        return C.hover_line("keywords", P.NA_MARK)
    parts = [k.strip() for k in str(keywords).split("|") if k.strip()]
    line1 = ", ".join(parts[:5])
    line2 = ", ".join(parts[5:10])
    value = f"{line1}<br>{line2}" if line2 else line1
    return C.hover_line("keywords", value)


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


def _fmt_pair_volumes(name_a, vol_a, name_b, vol_b, *,
                      under_floor_a: bool = False, under_floor_b: bool = False) -> str:
    """`pair_volumes`: one volume per institution, in slot order --
    "{name A} 120 - {name B} 84". `under_floor_a`/`under_floor_b` (default False,
    so every Find-side caller and every existing Compare test keeps its
    exact prior text): a topic can reach this pair's union set through ONE
    institution's own top set while the OTHER institution has fewer than
    `PAIR_VOLUME_FLOOR` articles and reviews on it -- `inst_topic_impact.
    parquet` ships pre-floored at that same minimum, so `pair_topics` genuinely
    cannot distinguish zero works from one or two, and stores a bucketed 0
    for exactly that case. Printing that bucketed 0 as a bare "0" would
    assert a fact this pipeline cannot see; the honest reading is "under
    3", not zero."""
    a_text = f"under {PAIR_VOLUME_FLOOR}" if under_floor_a else C._fmt_vol(vol_a)
    b_text = f"under {PAIR_VOLUME_FLOOR}" if under_floor_b else C._fmt_vol(vol_b)
    return f"{name_a} {a_text} - {name_b} {b_text}"


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
# balance_bars' own per-mode pair formatters (`docs/tooltip_spec.yaml`'s
# `fwci_pair_plain`/`fwci_pair_dagger`/`rank_pair`/`star_pair`/
# `change_pair_dagger`) -- same "{name A} x - {name B} y" shape
# `_fmt_pair_volumes` already established, one per mode's own quantity.
# ---------------------------------------------------------------------------
EMERGENCE_PCT_DECIMALS = 0    # `pct_signed_0dp`: no decimal, e.g. "+18%"/"-7%"
_EMERGENCE_PCT_FMT = f"+.{EMERGENCE_PCT_DECIMALS}%"
EMERGENCE_MIN_BAR_FRAC = 0.05   # a nonzero emergence bar's own visible-minimum
                                # floor, as a fraction of the axis max -- see
                                # `balance_bars`' own call site for why


def _fmt_pct_signed(v) -> str:
    if _is_na(v):
        return P.NA_MARK
    return format(float(v), _EMERGENCE_PCT_FMT)


def _fmt_pair_fwci(name_a, fwci_a, name_b, fwci_b, *,
                   n_covered_a=None, n_covered_b=None, dagger: bool = False) -> str:
    """`fwci_pair_plain` (`dagger=False`) or `fwci_pair_dagger` (`dagger=True`,
    needs `n_covered_a`/`n_covered_b`): one FWCI_EU value per institution,
    "n/a" on a side with no FWCI (fewer than 3 covered works -- the source
    table's own floor, `fwci_a`/`fwci_b` already NaN in that case), a dagger
    after a side's own value when `dagger=True` and that side's covered-work
    count is under `C.PCT_DAGGER_FLOOR` (10)."""
    a_text = C._fmt_frontier(fwci_a)
    b_text = C._fmt_frontier(fwci_b)
    if dagger:
        if a_text != P.NA_MARK and not _is_na(n_covered_a) and float(n_covered_a) < C.PCT_DAGGER_FLOOR:
            a_text += C.DAGGER
        if b_text != P.NA_MARK and not _is_na(n_covered_b) and float(n_covered_b) < C.PCT_DAGGER_FLOOR:
            b_text += C.DAGGER
    return f"{name_a} {a_text} - {name_b} {b_text}"


def _fmt_pair_rank(name_a, rank_a, name_b, rank_b) -> str:
    """`rank_pair`: one world rank per institution, "not ranked" past the
    world top `WORLD_LEADERBOARD_SIZE` (200) -- `leaders_data.topic_rank`'s
    own None-past-200 convention, never a fabricated worst rank."""
    a_text = f"#{int(rank_a)}" if not _is_na(rank_a) else "not ranked"
    b_text = f"#{int(rank_b)}" if not _is_na(rank_b) else "not ranked"
    return f"{name_a} {a_text} - {name_b} {b_text}"


def _fmt_pair_stars(name_a, stars_a, name_b, stars_b) -> str:
    """`star_pair`: one star-paper count per institution -- always a real
    count (never NaN, `pair_topics`' own `stars_a`/`stars_b` are ints)."""
    return f"{name_a} {C._fmt_vol(stars_a)} - {name_b} {C._fmt_vol(stars_b)}"


def _fmt_pair_change(name_a, change_a, low_base_a, name_b, change_b, low_base_b) -> str:
    """`change_pair_dagger`: one signed percentage change per institution, a
    dagger after a side's own value when that side's own `low_base_a`/
    `low_base_b` is True (the 2020-22 total is under `topic_data.
    LOW_BASE_FLOOR`) -- never appended to an already-missing "n/a"."""
    a_text = _fmt_pct_signed(change_a)
    if low_base_a and a_text != P.NA_MARK:
        a_text += C.DAGGER
    b_text = _fmt_pct_signed(change_b)
    if low_base_b and b_text != P.NA_MARK:
        b_text += C.DAGGER
    return f"{name_a} {a_text} - {name_b} {b_text}"


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
            _hover_topic_line1(row["topic_name"], excluded[i], row.get("exclusion_reason_label")),
            _fmt_keywords_2x5(row.get("keywords")),
            C.hover_line(HOVER_N_AR_CORE, C._fmt_vol(row["n_ar"])),
            C.hover_line(HOVER_FWCI_EU,
                        C._fmt_fwci_pair(row.get("fwci_mean"), row.get("fwci_median"), row.get("n_covered"))),
        ]
        n_stars_v = row.get("n_stars")
        if not _is_na(n_stars_v) and float(n_stars_v) >= 1:
            parts.append(C.hover_line(HOVER_STAR_PAPERS, C._fmt_vol(n_stars_v)))
        parts.append(C.hover_line(HOVER_VOL_PAIR_RUN_ALL_TYPES,
                                  C._fmt_vol_pair(row.get("vol_full_run"), row.get("vol_frac_run"))))
        rank_leader = _fmt_rank_and_leader(row.get("world_rank"), row.get("leader_name"))
        if rank_leader is not None:
            parts.append(C.hover_line(HOVER_TOPIC_LEADER, rank_leader))
        hover.append("<br>".join(p for p in parts if p is not None))

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
            _hover_topic_line1(row["topic_name"], excluded[i], row.get("exclusion_reason_label")),
            _fmt_keywords_2x5(row.get("keywords")),
            C.hover_line(HOVER_EXPANSION, C._fmt_frontier(x[i])),
            C.hover_line(HOVER_ACCELERATION, C._fmt_frontier(y[i])),
        ]
        if color_by == COLOR_BY_DOMAIN:
            parts.append(C.hover_line(HOVER_N_AR_CORE, C._fmt_vol(row["n_ar"])))
            if top[i]:
                parts.append(C.hover_line(HOVER_FRONTIER_STANDING, FRONTIER_FLAG_TEXT))
            rank_leader = None
            rank = row.get("world_rank")
            if not _is_na(rank) and int(rank) <= FIND_LED_RANK_FLOOR:
                rank_leader = _fmt_rank_and_leader(rank, row.get("leader_name"))
            if rank_leader is not None:
                parts.append(C.hover_line(HOVER_TOPIC_LEADER, rank_leader))
        else:
            name_a, name_b = str(names.get(ids[0], ids[0])), str(names.get(ids[1], ids[1]))
            pair_vol = _fmt_pair_volumes(
                name_a, row.get("vol_a"), name_b, row.get("vol_b"),
                under_floor_a=bool(row.get("under_floor_a", False)), under_floor_b=bool(row.get("under_floor_b", False)))
            parts.append(C.hover_line(HOVER_PUBLICATIONS_CORE_PAIR, pair_vol))
            parts.append(C.hover_line(HOVER_JOINT_PUBLICATIONS, _fmt_joint_or_floor(row.get("vol_joint"))))
            parts.append(C.hover_line(HOVER_HELD_BY, _fmt_owner_clause(row.get("owner"), name_a, name_b)))
        hover.append("<br>".join(p for p in parts if p is not None))

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


AX_STAR_PAPERS = "Star papers"
AX_FWCI_EU_BARS = "FWCI_EU"
AX_DISTANCE_TO_NUMBER_ONE = "Distance to world number one"
AX_OWN_CHANGE_PCT = "Change in publications (%)"


def _mode_bar_geometry(mode: str, d: pd.DataFrame, name_a: str, name_b: str,
                       color_a: str, color_b: str) -> dict:
    """The one place a mode's own quantity becomes bar geometry -- three
    families:
      "three_segment" (volume, stars): A-only / joint / B-only, a centre
        segment drawn whenever the joint quantity is known and > 0.
      "paired" (fwci, led, emergence): one bar per side, running outward
        from a shared centre zero, no joint segment at all -- each mode's
        own null/no-bar rule zeroes a side's length rather than omitting
        the row (a topic always occupies its row; only the BAR can be
        absent).
    Returns: kind, left, right (arrays, len n, >=0), joint (array or None,
    the "three_segment" family's own half-length source), joint_valid
    (bool array or None), tip_left/tip_right (list of str|None, outside-tip
    text at that side's own bar end, "paired" family only), color_left/
    color_right (list of hex, per-row -- only emergence ever overrides the
    institution colour), reference (float|None, symmetric dashed tick),
    axis_title (str)."""
    n = len(d)

    if mode == BAR_MODE_VOLUME:
        va = pd.to_numeric(d["vol_a"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        vb = pd.to_numeric(d["vol_b"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        vj_raw = pd.to_numeric(d["vol_joint"], errors="coerce")
        vj = vj_raw.fillna(0.0).to_numpy(dtype=float)
        joint_valid = (vj_raw.notna() & (vj_raw > 0)).to_numpy()
        return dict(kind="three_segment", left=va, right=vb, joint=vj, joint_valid=joint_valid,
                   tip_left=None, tip_right=None,
                   color_left=[color_a] * n, color_right=[color_b] * n,
                   reference=None, axis_title=C.AX_WORKS)

    if mode == BAR_MODE_STARS:
        sa = pd.to_numeric(d["stars_a"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        sb = pd.to_numeric(d["stars_b"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        sj = pd.to_numeric(d["stars_joint"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        joint_valid = sj > 0   # no floor concept for stars -- star_works.parquet is a direct fact table
        return dict(kind="three_segment", left=sa, right=sb, joint=sj, joint_valid=joint_valid,
                   tip_left=None, tip_right=None,
                   color_left=[color_a] * n, color_right=[color_b] * n,
                   reference=None, axis_title=AX_STAR_PAPERS)

    if mode == BAR_MODE_FWCI:
        fa = pd.to_numeric(d["fwci_a"], errors="coerce")
        fb = pd.to_numeric(d["fwci_b"], errors="coerce")
        # no bar at all under 3 covered works -- fwci_a/fwci_b are already
        # NaN in that case (the source table's own floor), never a
        # separate check here.
        #
        # The axis half-range is NOT the raw max: one topic's own outlier
        # FWCI would otherwise dictate the whole scale and crush every
        # other row toward the centre (a real, reproduced defect -- one
        # dominant value on a linear scale, live-verified against real
        # data). Robust rule: `max(FWCI_HALF_RANGE_FLOOR, FWCI_HALF_RANGE_
        # P90_MULT * p90-of-the-drawn-values)`, capped at the true max (a
        # half-range never invents room past what any row actually needs).
        # A value past the half-range is drawn TO THE EDGE (clipped) with
        # its tip label prefixed `FWCI_CLIP_TIP_ARROW` so the reader sees it
        # runs off, never a silently-truncated bar; EVERY fwci bar carries
        # its own 2dp value at the tip (clipped or not), the same "outside"
        # idiom the led mode's own "#k" tip already uses.
        all_vals = pd.concat([fa, fb]).dropna().to_numpy(dtype=float)
        if len(all_vals):
            true_max = float(all_vals.max())
            p90 = float(np.percentile(all_vals, 90))
            half_range = min(max(FWCI_HALF_RANGE_FLOOR, FWCI_HALF_RANGE_P90_MULT * p90), true_max)
        else:
            half_range = FWCI_HALF_RANGE_FLOOR

        def _clip_and_tip(v):
            if _is_na(v):
                return 0.0, None, False
            v = float(v)
            if v <= half_range + 1e-9:
                return v, C._fmt_frontier(v), False
            return half_range, f"{FWCI_CLIP_TIP_ARROW}{C._fmt_frontier(v)}", True

        left_and_tip = [_clip_and_tip(v) for v in fa]
        right_and_tip = [_clip_and_tip(v) for v in fb]
        left = np.array([v for v, _, _ in left_and_tip], dtype=float)
        right = np.array([v for v, _, _ in right_and_tip], dtype=float)
        tip_left = [t for _, t, _ in left_and_tip]
        tip_right = [t for _, t, _ in right_and_tip]
        # A CLIPPED bar's own tip sits right at the axis edge -- drawn
        # "outside" (the every-other-fwci-bar default) it collides with the
        # gutter number on the left, or the link column on the right (both
        # occupy the same pixels just past the plot edge). Only a clipped
        # bar's tip moves INSIDE the bar itself, anchored at its own far end
        # (`insidetextanchor="end"`, set once at the trace level below --
        # harmless for the "outside" points sharing that trace, which
        # ignore it), in a colour that reads against the institution fill
        # (`palette.SURFACE`, white) rather than the ordinary
        # `INK_SECONDARY` an outside label uses.
        tip_position_left = ["inside" if clipped else "outside" for _, _, clipped in left_and_tip]
        tip_position_right = ["inside" if clipped else "outside" for _, _, clipped in right_and_tip]
        tip_color_left = [P.SURFACE if clipped else P.INK_SECONDARY for _, _, clipped in left_and_tip]
        tip_color_right = [P.SURFACE if clipped else P.INK_SECONDARY for _, _, clipped in right_and_tip]
        return dict(kind="paired", left=left, right=right, joint=None, joint_valid=None,
                   tip_left=tip_left, tip_right=tip_right,
                   tip_position_left=tip_position_left, tip_position_right=tip_position_right,
                   tip_color_left=tip_color_left, tip_color_right=tip_color_right,
                   color_left=[color_a] * n, color_right=[color_b] * n,
                   reference=FWCI_REFERENCE_TICK, axis_title=AX_FWCI_EU_BARS)

    if mode == BAR_MODE_LED:
        ra = pd.to_numeric(d["rank_a"], errors="coerce")
        rb = pd.to_numeric(d["rank_b"], errors="coerce")
        left = np.where(ra.notna().to_numpy(),
                       (WORLD_LEADERBOARD_SIZE + 1) - ra.fillna(0.0).to_numpy(dtype=float), 0.0)
        right = np.where(rb.notna().to_numpy(),
                        (WORLD_LEADERBOARD_SIZE + 1) - rb.fillna(0.0).to_numpy(dtype=float), 0.0)
        tip_left = [f"#{int(v)}" if pd.notna(v) else None for v in ra]
        tip_right = [f"#{int(v)}" if pd.notna(v) else None for v in rb]
        return dict(kind="paired", left=left, right=right, joint=None, joint_valid=None,
                   tip_left=tip_left, tip_right=tip_right,
                   color_left=[color_a] * n, color_right=[color_b] * n,
                   reference=float(LED_REFERENCE_DISTANCE), axis_title=AX_DISTANCE_TO_NUMBER_ONE)

    # BAR_MODE_EMERGENCE
    ca = pd.to_numeric(d["change_a"], errors="coerce")
    cb = pd.to_numeric(d["change_b"], errors="coerce")
    low_a = (d["low_base_a"].fillna(True).to_numpy(dtype=bool)
            if "low_base_a" in d.columns else np.zeros(n, dtype=bool))
    low_b = (d["low_base_b"].fillna(True).to_numpy(dtype=bool)
            if "low_base_b" in d.columns else np.zeros(n, dtype=bool))
    left = (ca.abs().fillna(0.0) * 100.0).to_numpy(dtype=float)
    right = (cb.abs().fillna(0.0) * 100.0).to_numpy(dtype=float)
    tip_left, tip_right, color_left, color_right = [], [], [], []
    for i in range(n):
        va_i, vb_i = ca.iloc[i], cb.iloc[i]
        if pd.isna(va_i):
            tip_left.append(None); color_left.append(color_a)
        else:
            t = _fmt_pct_signed(va_i) + (C.DAGGER if low_a[i] else "")
            tip_left.append(t)
            color_left.append(P.COMPARISON if va_i < 0 else color_a)
        if pd.isna(vb_i):
            tip_right.append(None); color_right.append(color_b)
        else:
            t = _fmt_pct_signed(vb_i) + (C.DAGGER if low_b[i] else "")
            tip_right.append(t)
            color_right.append(P.COMPARISON if vb_i < 0 else color_b)
    return dict(kind="paired", left=left, right=right, joint=None, joint_valid=None,
               tip_left=tip_left, tip_right=tip_right,
               color_left=color_left, color_right=color_right,
               reference=None, axis_title=AX_OWN_CHANGE_PCT)


def _mode_sort_key(mode: str, d: pd.DataFrame) -> pd.Series:
    """One descending sort key per mode (`topic_id` ascending tie-break is
    applied by the caller): volume/stars -- combined count; fwci -- the
    HIGHER of the two FWCI values (NaN treated as -inf, never sorted first);
    led -- the BEST (lowest) of the two world ranks, expressed as
    `-rank` so "descending" still means "best first" (NaN, unranked, sorts
    last); emergence -- `frontier_score_latest` (this mode's own selection
    order, ported from `select_topics`)."""
    if mode == BAR_MODE_VOLUME:
        return (pd.to_numeric(d["vol_a"], errors="coerce").fillna(0.0)
               + pd.to_numeric(d["vol_b"], errors="coerce").fillna(0.0))
    if mode == BAR_MODE_STARS:
        return (pd.to_numeric(d["stars_a"], errors="coerce").fillna(0.0)
               + pd.to_numeric(d["stars_b"], errors="coerce").fillna(0.0))
    if mode == BAR_MODE_FWCI:
        fa = pd.to_numeric(d["fwci_a"], errors="coerce")
        fb = pd.to_numeric(d["fwci_b"], errors="coerce")
        return pd.concat([fa, fb], axis=1).max(axis=1, skipna=True).fillna(-np.inf)
    if mode == BAR_MODE_LED:
        ra = pd.to_numeric(d["rank_a"], errors="coerce")
        rb = pd.to_numeric(d["rank_b"], errors="coerce")
        best = pd.concat([ra, rb], axis=1).min(axis=1, skipna=True)
        return -best.fillna(np.inf)
    # BAR_MODE_EMERGENCE
    return pd.to_numeric(d["frontier_score_latest"], errors="coerce").fillna(-np.inf)


def _mode_hover_lines(mode: str, row: pd.Series, name_a: str, name_b: str, excluded: bool) -> str:
    """One hover string for `row`, per `docs/tooltip_spec.yaml`'s
    `compare_balance_bars.modes.<mode>` -- entity, keywords, this mode's own
    quantity, then up to two supporting lines, then "held by" (7 lines every
    mode, well under the 8-line cap)."""
    pair_vol = _fmt_pair_volumes(
        name_a, row.get("vol_a"), name_b, row.get("vol_b"),
        under_floor_a=bool(row.get("under_floor_a", False)), under_floor_b=bool(row.get("under_floor_b", False)))
    fwci_plain = _fmt_pair_fwci(name_a, row.get("fwci_a"), name_b, row.get("fwci_b"))
    owner_line = C.hover_line(HOVER_HELD_BY, _fmt_owner_clause(row.get("owner"), name_a, name_b))
    parts = [
        _hover_topic_line1(row["topic_name"], excluded, row.get("exclusion_reason_label")),
        _fmt_keywords_2x5(row.get("keywords")),
    ]
    if mode == BAR_MODE_VOLUME:
        parts += [
            C.hover_line(HOVER_PUBLICATIONS_CORE_PAIR, pair_vol),
            C.hover_line(HOVER_JOINT_PUBLICATIONS, _fmt_joint_or_floor(row.get("vol_joint"))),
            C.hover_line(HOVER_FWCI_EU, fwci_plain),
        ]
    elif mode == BAR_MODE_FWCI:
        fwci_dagger = _fmt_pair_fwci(name_a, row.get("fwci_a"), name_b, row.get("fwci_b"),
                                     n_covered_a=row.get("n_covered_a"), n_covered_b=row.get("n_covered_b"),
                                     dagger=True)
        parts += [
            C.hover_line(HOVER_FWCI_EU, fwci_dagger),
            C.hover_line(HOVER_PUBLICATIONS_CORE_PAIR, pair_vol),
            C.hover_line(HOVER_WORLD_RANK_PAIR, _fmt_pair_rank(name_a, row.get("rank_a"), name_b, row.get("rank_b"))),
        ]
    elif mode == BAR_MODE_LED:
        parts += [
            C.hover_line(HOVER_WORLD_RANK_PAIR, _fmt_pair_rank(name_a, row.get("rank_a"), name_b, row.get("rank_b"))),
            C.hover_line(HOVER_PUBLICATIONS_CORE_PAIR, pair_vol),
            C.hover_line(HOVER_FWCI_EU, fwci_plain),
        ]
    elif mode == BAR_MODE_STARS:
        parts += [
            C.hover_line(HOVER_STAR_PAPERS_PAIR, _fmt_pair_stars(name_a, row.get("stars_a"), name_b, row.get("stars_b"))),
            C.hover_line(HOVER_JOINT_STAR_PAPERS, C._fmt_vol(row.get("stars_joint", 0))),
            C.hover_line(HOVER_PUBLICATIONS_CORE_PAIR, pair_vol),
        ]
    else:  # BAR_MODE_EMERGENCE
        change_pair = _fmt_pair_change(name_a, row.get("change_a"), bool(row.get("low_base_a", False)),
                                       name_b, row.get("change_b"), bool(row.get("low_base_b", False)))
        parts += [
            C.hover_line(HOVER_OWN_CHANGE_PAIR, change_pair),
            C.hover_line(HOVER_PUBLICATIONS_CORE_PAIR, pair_vol),
            C.hover_line(HOVER_FWCI_EU, fwci_plain),
        ]
    parts.append(owner_line)
    return "<br>".join(p for p in parts if p is not None)


def _mode_gutter_text(mode: str, row: pd.Series) -> str:
    """The gutter's own text is the mode's own SORT KEY (`_mode_sort_key`),
    formatted for that mode -- a reader scanning the column top-to-bottom
    sees the SAME quantity the rows are actually ordered by, so the column
    itself always reads sorted. volume/stars: the sum of the two per-
    institution counts (matching `_mode_sort_key`'s own combined-count
    rule). led: the best (lowest) of the two world ranks, printed as "#k"
    (a rank has no meaningful sum -- matches `_mode_sort_key`'s own
    best-rank rule). fwci: the HIGHER of the two FWCI values, 2 decimals
    (matches `_mode_sort_key`'s own `max` -- a SUM does not track the sort
    order, so an earlier version of this column read as unsorted).
    emergence: `frontier_score_latest` itself, 2 decimals (matches
    `_mode_sort_key`'s own selection order for this mode -- an earlier
    version summed the two change percentages instead, a number with no
    relationship to the actual row order, and wide enough at the high end
    to run into the label column)."""
    if mode == BAR_MODE_LED:
        ranks = [r for r in (row.get("rank_a"), row.get("rank_b")) if not _is_na(r)]
        return f"#{int(min(ranks))}" if ranks else P.NA_MARK
    if mode == BAR_MODE_VOLUME:
        return C._fmt_vol(row.get("vol_a", 0.0) + row.get("vol_b", 0.0))
    if mode == BAR_MODE_STARS:
        return C._fmt_vol(row.get("stars_a", 0.0) + row.get("stars_b", 0.0))
    if mode == BAR_MODE_FWCI:
        a, b = row.get("fwci_a"), row.get("fwci_b")
        vals = [float(v) for v in (a, b) if not _is_na(v)]
        return C._fmt_frontier(max(vals)) if vals else P.NA_MARK
    # BAR_MODE_EMERGENCE
    score = row.get("frontier_score_latest")
    return C._fmt_frontier(score) if not _is_na(score) else P.NA_MARK


def _link_column_text(mode: str, row: pd.Series) -> tuple[str, str | None]:
    """The right-margin link column's own cell: the joint publication
    count -> `row["url_joint"]` in every mode except stars, where the cell
    is the joint STAR count -> `row["url_stars_joint"]` (both URLs already
    built by `topic_data.pair_topics` -- this module never imports
    `lib.links` itself, its own "imports only lib.charts/lib.palette" house
    rule). Returns (display_text, href|None) -- `href is None` draws a
    plain, unlinked cell (a dash under the joint-publication floor, or "0"
    when a real, linkable count is genuinely zero -- `stars_joint == 0` has
    a real href-less "0", `vol_joint` NaN has the dash, never the
    reverse)."""
    if mode == BAR_MODE_STARS:
        stars_joint = row.get("stars_joint", 0)
        n = 0 if _is_na(stars_joint) else int(stars_joint)
        if n == 0:
            return C._fmt_vol(0), None
        return C._fmt_vol(n), row.get("url_stars_joint")
    vol_joint = row.get("vol_joint")
    if _is_na(vol_joint):
        return LINK_COL_DASH, None
    return C._fmt_vol(vol_joint), row.get("url_joint")


# ---------------------------------------------------------------------------
# 3. balance_bars -- the mirror chart generalised (Compare's topic overlap),
#    now FIVE per-mode encodings plus the right-margin OpenAlex link column.
#    Built and tested here on synthetic frames.
# ---------------------------------------------------------------------------

def balance_bars(
    rows: pd.DataFrame,
    ids: Sequence,
    *,
    slots: Mapping,
    names: Mapping,
    mode: str = BAR_MODE_VOLUME,
    top_n: int | None = None,
) -> go.Figure:
    """One row per topic, encoding CHOSEN BY `mode` (one of `BAR_MODES`):
    "volume"/"stars" draw the familiar three-segment bar (A-only left,
    joint centred in `palette.JOINT_TOPIC_COLOR`, B-only right); "fwci"/
    "led"/"emergence" draw a PAIRED bar per side, no joint segment (neither
    an institution's own FWCI_EU, world rank nor own volume change has a
    "joint" reading). Sorted by that mode's own quantity, descending
    (`_mode_sort_key`, `topic_id` ascending tie-break) -- never the caller's
    own column choice any more (the retired `sort_col` argument).

    The right-margin "Joint pubs" link column (Plotly annotations,
    `LINK_COL_PX` fixed width): the joint publication count in every mode
    except "stars" (the joint STAR count there), linked to OpenAlex, a dash
    when the pair is under the 5-joint-publication floor.

    On the bar-layout contract: the Compare label column
    (`charts.LABEL_COL_PX["compare"]`), one-bar row pitch (34 px,
    `ROW_PITCH_SINGLE`) and bar thickness (20 px, `BAR_PX_SINGLE`), no
    header text above the gutter (the link column gets its OWN header
    annotation, "Joint pubs", the one exception). Hover per
    `compare_balance_bars.modes.<mode>` (<=8 lines every mode).

    INPUT FRAME CONTRACT (one row per topic, `topic_data.pair_topics`'
    shape): `topic_id`, `topic_name`, `keywords`, `is_excluded`,
    `exclusion_reason_label`, `vol_a`, `vol_b`, `vol_joint` (NaN under
    `JOINT_FLOOR`), `owner`, `url_joint`, plus whatever the CHOSEN mode
    needs (`fwci_a`/`fwci_b`/`n_covered_a`/`n_covered_b` for "fwci",
    `rank_a`/`rank_b` for "led", `stars_a`/`stars_b`/`stars_joint`/
    `star_ids_joint` for "stars", `change_a`/`change_b`/`low_base_a`/
    `low_base_b`/`frontier_score_latest` for "emergence").

    `ids`/`slots`/`names`: the two compared institutions, in slot order --
    `ids=[id_a, id_b]` matching `vol_a`/`vol_b`'s own order."""
    if mode not in BAR_MODES:
        raise ValueError(f"mode must be one of {BAR_MODES}, got {mode!r}")
    required = ["topic_id", "topic_name", "vol_a", "vol_b", "vol_joint", "owner", "url_joint"]
    if mode == BAR_MODE_FWCI:
        required += ["fwci_a", "fwci_b"]
    elif mode == BAR_MODE_LED:
        required += ["rank_a", "rank_b"]
    elif mode == BAR_MODE_STARS:
        required += ["stars_a", "stars_b", "stars_joint", "star_ids_joint", "url_stars_joint"]
    elif mode == BAR_MODE_EMERGENCE:
        required += ["change_a", "change_b", "frontier_score_latest"]
    for col in required:
        if col not in rows.columns:
            raise ValueError(f"missing column {col!r}")
    if len(ids) < 2:
        raise ValueError("balance_bars needs ids=[id_a, id_b]")

    sort_key = _mode_sort_key(mode, rows)
    d = rows.assign(_sort_key=sort_key.to_numpy()).sort_values(
        ["_sort_key", "topic_id"], ascending=[False, True], kind="mergesort").drop(columns=["_sort_key"])
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
    joint_color = P.JOINT_TOPIC_COLOR

    geo = _mode_bar_geometry(mode, d, name_a, name_b, color_a, color_b)
    left, right = geo["left"], geo["right"]

    if mode == BAR_MODE_EMERGENCE and n:
        # A visible-minimum floor for a NONZERO bar (never for a genuine
        # zero change) -- the emergence mode's own value distribution
        # clusters many rows near a small percentage change on BOTH sides,
        # and Plotly's own "outside" text for a near-zero bar sits right at
        # the shared centre, where the left and right tip labels collide
        # and render illegibly on top of each other. The SAME "always a
        # visible mark" idea `BUBBLE_MIN_PX`/`sizemin` already applies to
        # the topic-plane bubbles, ported here as a bar-length floor: the
        # HOVER and the tip TEXT both still read the true value (`geo`'s
        # own `tip_left`/`tip_right` are computed from the real change,
        # never from this floor) -- only the drawn bar length is stretched.
        vmax_raw = float(max(left.max(), right.max())) if len(left) else 1.0
        floor = max(vmax_raw, 1.0) * EMERGENCE_MIN_BAR_FRAC
        left = np.where(left > 0, np.maximum(left, floor), left)
        right = np.where(right > 0, np.maximum(right, floor), right)

    excluded = (d["is_excluded"].fillna(False).to_numpy(dtype=bool)
                if "is_excluded" in d.columns else np.zeros(n, dtype=bool))

    hover = [_mode_hover_lines(mode, d.iloc[i], name_a, name_b, bool(excluded[i])) for i in range(n)]

    fig = go.Figure()
    if geo["kind"] == "three_segment":
        joint, joint_valid = geo["joint"], geo["joint_valid"]
        half = np.where(joint_valid, joint / 2.0, 0.0)
        a_only = np.maximum(0.0, left - np.where(joint_valid, joint, 0.0))
        b_only = np.maximum(0.0, right - np.where(joint_valid, joint, 0.0))
        left_extent = half + a_only
        right_extent = half + b_only
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
    else:  # "paired" -- one bar per side, no joint segment, an optional tip
        left_extent, right_extent = left, right
        color_left, color_right = geo["color_left"], geo["color_right"]
        tip_left, tip_right = geo["tip_left"], geo["tip_right"]
        # A mode whose tip can be CLIPPED (fwci) supplies its own per-row
        # position/colour (a clipped bar's tip moves inside the bar, see
        # `_mode_bar_geometry`'s own fwci branch); every other mode falls
        # back to the plain scalar "outside"/`INK_SECONDARY` every tip used
        # before this. `insidetextanchor="end"` is a TRACE-level setting
        # (Plotly has no per-point anchor) -- harmless for this trace's
        # "outside" points, which never read it.
        pos_left = geo.get("tip_position_left") or "outside"
        pos_right = geo.get("tip_position_right") or "outside"
        color_left_text = geo.get("tip_color_left") or P.INK_SECONDARY
        color_right_text = geo.get("tip_color_right") or P.INK_SECONDARY
        # The left bar is drawn base=0 EXTENDING NEGATIVE (`x=-left`), never
        # `base=-left, x=left` (which spans -left..0): Plotly's own
        # "outside" text sits just past the bar's FAR end IN ITS OWN
        # DRAWN DIRECTION, so a bar spanning -left..0 has its far end AT
        # ZERO -- its tip label would render at the shared centre, on top
        # of the right bar's own label, not out past its true left tip.
        # base=0, x=-left spans 0..-left, far end correctly at -left.
        fig.add_trace(go.Bar(
            x=list(-left), y=list(range(n)), base=[0.0] * n, orientation="h",
            marker=dict(color=color_left, line=dict(color=color_left, width=C.HAIRLINE_PX)),
            text=tip_left, textposition=pos_left, insidetextanchor="end", cliponaxis=False,
            textfont=dict(size=C.GUTTER_FONT_PX, color=color_left_text), constraintext="none",
            customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False))
        fig.add_trace(go.Bar(
            x=list(right), y=list(range(n)), base=[0.0] * n, orientation="h",
            marker=dict(color=color_right, line=dict(color=color_right, width=C.HAIRLINE_PX)),
            text=tip_right, textposition=pos_right, insidetextanchor="end", cliponaxis=False,
            textfont=dict(size=C.GUTTER_FONT_PX, color=color_right_text), constraintext="none",
            customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False))

    names_ids = list(range(n))
    vmax = float(max(left_extent.max(), right_extent.max())) if n else 1.0
    vmax = vmax if vmax > 0 else 1.0
    pad = vmax * AXIS_PAD_FRAC
    edge = vmax + pad   # the diverging chart's own visible left/right edge

    combined_text = [_mode_gutter_text(mode, d.iloc[i]) for i in range(n)]

    # The gutter column: a phantom zero-fill bar carrying the row's own
    # combined value as outside text -- placed just PAST this chart's own
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
        text=combined_text, textposition="outside", cliponaxis=False,
        textfont=dict(size=C.GUTTER_FONT_PX, color=P.INK_SECONDARY), constraintext="none",
        customdata=[""] * n, hoverinfo="skip", showlegend=False,
    ))
    fig.update_layout(barmode="overlay")
    fig.add_vline(x=0, line=dict(color=P.INK, width=C.FRONTIER_ORIGIN_PX))

    reference = geo["reference"]
    if reference is not None and reference > 0:
        for x0 in (reference, -reference):
            fig.add_vline(x=x0, line=dict(color=P.WARNING_CAPTION_COLOR, width=C.LINE_PX, dash="dash"))

    pairs = [C._tick_label(str(d.at[i, "topic_name"]), wrap_px=C.WRAP_PX["compare"]) for i in range(n)]
    styled = [s for _, s in pairs]
    fig.update_yaxes(tickmode="array", tickvals=names_ids, ticktext=styled,
                     range=[n - 0.5, -0.5], showgrid=False, automargin=True,
                     tickfont=dict(size=C.TICK_FONT_PX))

    if mode == BAR_MODE_EMERGENCE:
        ticks = [t for t in C._nice_ticks(vmax) if t > 0]
        tick_text = lambda t: f"{int(round(t))}%"
        fig.update_xaxes(
            range=[-edge - gutter_lane, edge], tickmode="array",
            tickvals=[-t for t in reversed(ticks)] + [0.0] + ticks,
            ticktext=([tick_text(t) for t in reversed(ticks)] + [tick_text(0.0)] + [tick_text(t) for t in ticks]),
            title_text=geo["axis_title"], gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)
    else:
        ticks = [t for t in C._nice_ticks(vmax) if t > 0]
        fmt = C._fmt_frontier if mode == BAR_MODE_FWCI else C._fmt_vol
        fig.update_xaxes(
            range=[-edge - gutter_lane, edge], tickmode="array",
            tickvals=[-t for t in reversed(ticks)] + [0.0] + ticks,
            ticktext=([fmt(t) for t in reversed(ticks)] + [fmt(0.0)] + [fmt(t) for t in ticks]),
            title_text=geo["axis_title"], gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)

    # The right-margin link column: one Plotly annotation per row,
    # aligned with that row's y position (`yref="y", y=i`), just past the
    # chart's own right edge (`xref="paper", x=1.0 + pad`) -- native Plotly
    # markup, an `<a href target="_blank">` inside annotation text renders
    # as a real SVG anchor (a y-tick label carrying `<a href>` markup
    # renders the same way, an established Plotly behaviour), no new
    # dependency. A header annotation ("Joint
    # pubs") sits above the column, and `margin.r` is WIDENED to
    # `LINK_COL_PX` (a fixed px width, not a fraction of the plot area) so
    # the column never overlaps the last tick label.
    annotations = list(fig.layout.annotations or ())
    for i in range(n):
        text, href = _link_column_text(mode, d.iloc[i])
        cell_text = (f'<a href="{href}" target="{BALANCE_BAR_LINK_TARGET}">{text}</a>'
                    if href else text)
        annotations.append(dict(
            xref="paper", x=1.0, xanchor="left", xshift=8,
            yref="y", y=i, yanchor="middle",
            text=cell_text, showarrow=False, align="left",
            font=dict(size=LINK_COL_FONT_PX, color=P.INK_SECONDARY),
        ))
    annotations.append(dict(
        xref="paper", x=1.0, xanchor="left", xshift=8,
        yref="y", y=-1.0, yanchor="middle",
        text=LINK_COL_HEADER_TEXT, showarrow=False, align="left",
        font=dict(size=LINK_COL_FONT_PX, color=P.INK_SECONDARY),
    ))
    fig.update_layout(annotations=annotations)

    margin_l = C.LABEL_COL_PX["compare"] + C.GUTTER_COL_PX["compare"] + C.COL_PAD_PX
    return C._base_layout(fig, C.row_height_single(n), bargap=C.BAR_GAP_SINGLE,
                          margin=dict(t=C.BASE_PX // 2, l=margin_l, r=LINK_COL_PX, b=C.BASE_PX))
