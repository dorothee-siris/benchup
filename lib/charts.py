"""BenchUp -- pure Plotly figure builders for the profile section.

NO Streamlit import lives in this module (the same rule the engine package
follows): every function takes a plain DataFrame or plain sequences and returns
a `plotly.graph_objects.Figure`, so it can be unit-tested headless and reused
outside the app. `lib/views_find.py` is the only place that puts a figure on a
page.

Two hard house rules this module is written to satisfy, and the mechanics that
make them true rather than aspirational:

1. **No colour literal.** Every hue comes from `lib.palette`; `tests/test_palette.py`
    fails the build on a `#RRGGBB` anywhere under `lib/` except `palette.py`.
    That includes the chart surface (`palette.SURFACE`), the gridlines
    (`palette.GRID`), the annotation ink (`palette.INK_SECONDARY`) and the
    hairlines (`palette.BORDER`).

2. **No digit in any string.** `tests/test_charts.py` scans this file's source
    for a digit inside a string literal, using the SAME allowlist as the
    narrative digit-ban (`tests/digit_allowlist.txt`, read-only -- the allowlist
    is full at its cap and this module adds nothing to it). Consequences that
    are easy to undo by accident:
      * number formats are COMPOSED from int constants
        (`f".{SHARE_DECIMALS}%"`), never typed as `".1%"`;
      * hover text is PRE-FORMATTED in Python and passed through `customdata`
        with `hovertemplate="%{customdata}<extra></extra>"`,
        so no `%{x:.1%}` and no `%{customdata[0]}` -- both of which carry a
        digit -- ever appears in this file;
      * the SI reference is a LINE at the neutral value, never a text label
        naming that value; the caller writes any such sentence into `copy.py`
        with a `{placeholder}`.
    Anything parametric (counts, thresholds, the year window) is a caller-filled
    `{placeholder}` in a title/caption string the caller owns -- this module
    only accepts already-composed text. `wrap_label`'s `width` is an INT
    constant (`WRAP_WIDTH`), never a string -- the digit-ban only reaches into
    string literals, and an int default argument is not one.

Grammar decided by side-by-side comparison on real data:
  * A/B #3 -> the share + SI pair is TWO ALIGNED PANELS of one figure sharing a
    y-axis: share bars on the left, SI as a lollipop from a dashed reference at
    the neutral value on the right. The rejected rival encoded SI as a tick on
    the share row itself, which put SI on a per-row scale (not comparable
    across rows) and stretched the share axis to fit the tick, degrading the
    primary measure.
  * A/B #4 -> volume sits in a LEFT TEXT GUTTER, right-aligned against the
    zero baseline, not as a right-of-bar annotation. The rival clipped at the
    narrow width and scattered the numbers across the full plot width.
  * The grouped-bar geometry below is shared with an earlier SIRIS
    Streamlit tool, because `offsetgroup` is BROKEN on the pinned plotly
    5.24.1.

A later pass changed two things about the paired share + SI form above, both
still inside the A/B #3/#4 winning geometry -- neither reopens either A/B:
  * **Full names, never an ellipsis.** A category label longer than
    `WRAP_WIDTH` now WRAPS onto at most two lines at a word boundary
    (`wrap_label`) instead of being cut short from the right. The row's own
    height grows to fit a two-line label (`row_height`'s `n_wrapped` term).
    This REVERSES the earlier truncation rule below what used to be
    `MAX_LABEL_CHARS`/`_truncate_label`/`ELLIPSIS` -- all three are retired,
    not kept as dead code, since a reversed decision is worth being explicit
    about.
  * **`si_status` (solid / thin / none) drives the SI mark**, when the
    caller's frame carries that column: a `solid` row keeps the FILLED dot
    this section already used; a `thin` row draws a HOLLOW dot (white fill,
    coloured outline) instead of no mark at all, so a below-the-old-floor cell
    is disclosed rather than erased; a `none` row gets no mark and no stem,
    same as the pre-existing NaN rule. **A zero-volume row never gets a mark,
    whatever `si_status` says** -- the fix for a display bug where a
    specialisation dot floated at a fabricated value for a panel with
    no publications at all. When the column is absent, the earlier rule
    applies unchanged: a defined `si` gets a filled dot, a NaN `si` gets none.

This module also changes four more things,
all scoped to the FIND panels this module builds for (`views_find.py`'s
collapsed fields/subfields/topics/frontier/SDG/ERC panels), none of them
touching the Compare-page geometry `lib/charts_compare.py` borrows this
module's private helpers for:

  * **No more wrapping -- widen the gutter instead.** The change above
    replaced truncation with a two-line wrap; REVERSES that for the Find
    panels in turn: "full label on one row wins over bar length" is now the
    stated priority, small bars being an acceptable cost. `fig_share_si` and
    `fig_topics` gain a `wrap: bool = False` keyword (default OFF -- the new
    behaviour needs no caller change) that reaches `_tick_display` through
    its own new `wrap` keyword (default `True`, UNCHANGED for any call that
    doesn't pass it). That default matters: `lib/charts_compare.py` calls
    `_tick_display`, `wrap_label`, `row_height`'s `n_wrapped`, `WRAP_WIDTH`
    and `WRAP_ROW_FACTOR` directly, for the Compare page's own geometry,
    which does not touch -- so none of that machinery is retired,
    only defaulted OFF for this module's own two Find builders. With
    `wrap=False` a label is never split with `<br>`, `_gutter_margin_px`
    measures the full single-line string (its "longest LINE" is now the
    whole label), and `row_height`'s `n_wrapped` count is always zero, which
    is also most of why this refinement compresses panel height: the old
    "every row pays the two-line pitch the moment ONE row wraps" penalty
    (`row_height`'s note above) never fires once wrapping itself never fires.
  * **The SI unit grid is retired for an outer-end value label.** The old
    per-integer vertical gridline set was a second thing to cross-reference
    against the dashed neutral line; now each row's own SI marker carries its
    OWN formatted value as text, anchored on the side AWAY from the neutral
    reference (`SI_NEUTRAL`) -- left of the dot for a sub-neutral value,
    right for an above-neutral one -- so the reading is local to the row, not
    a lookup against an axis. The dashed neutral reference line itself is
    NOT a "unit gridline" and is kept; only `showgrid` on the SI axis goes to
    `False`.
  * **The frontier quadrant lines are bold ink, not hairline grid.** Same
    `FRONTIER_ORIGIN` split, drawn in `palette.INK` at `FRONTIER_ORIGIN_PX`
    instead of `palette.GRID` at a hairline, so the quadrant read is
    immediate rather than something the eye has to find.
  * **`fig_frontier` takes an optional `top_n`.** The SAME keyword serves
    BOTH of `views_find.py`'s modes (top-N-by-volume and the global
    top-quartile set) -- the builder itself keeps only the `top_n`
    highest-mass rows of whatever frame it receives (`_frontier_topn`,
    ties broken by stable sort so a re-render of the same frame never
    reorders), so the axes autorange to exactly what is drawn either way.
    `None` (the default) reproduces the pre- behaviour: every row the
    caller already filtered is plotted, uncapped. `frontier_coverage` runs
    the IDENTICAL selection to hand the caller the disclosure numbers a
    caption needs (rows dropped, their mass share, the minimum mass that
    made the cut, how many catch-all rows are among the shown set) as plain
    numbers -- never a string, per this module's digit-ban above -- so chart
    and caption can never drift apart. `fig_topics`'s sort-order toggle is
    also retired here: the `sort` keyword stays (nothing calling it errors)
    but the panel is now ALWAYS volume-ordered, since "top N" is itself a
    volume-defined cut and a taxonomy re-sort of it reads as arbitrary order.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lib import palette as P

# ---------------------------------------------------------------------------
# Numeric + geometric constants (ints/floats -- never inside a string literal)
# ---------------------------------------------------------------------------
SHARE_DECIMALS = 1          # a share is shown to one decimal of a percent IN HOVER
AXIS_DECIMALS = 0           # .but the share AXIS ticks carry none: a tick is a
                            # scale marker, not a measurement, and a column of
                            # ".0%" suffixes is noise the reader has to filter
                            # (one precision level PER ROLE, RULES section 5)
SI_DECIMALS = 2             # SI / ESI to two decimals (they cluster near the neutral value)
FRONTIER_DECIMALS = 2

ROW_PX = 18                 # one category row's vertical budget (:
                            # compressed from 22 -- was 26 rows Compare
                            # geometry adds `n_wrapped` on top of; the Find
                            # panels below no longer wrap at all, so this
                            # pitch alone decides their height)
BASE_PX = 50                # axes + margins (: 60 -> 50, tightened
                            # alongside ROW_PX so a 30-row panel clears the
                            # one-screen budget with room to spare)
MIN_HEIGHT = 300
SCATTER_HEIGHT = 520

BAR_GAP = 0.25              # : 0.3 -> 0.25, tighter inter-row gap to
                            # match the compressed pitch above

# --- Volume-gutter collision fix --------------------------------------------
# The volume gutter used to be a SEPARATE `add_annotation` sitting in a
# negative-x sliver reserved left of the zero baseline (`GUTTER_FRACTION`/
# `GUTTER_INSET`, retired by this fix), drawn independently of the y-axis
# category label. At a narrow plot width the two
# text elements are laid out by two different systems with no shared
# knowledge of each other's extent, so they can (and at 390 px, did) end up
# with zero space between them, reading as one garbled word.
#
# Measured on plotly 5.24.1: `yaxis.automargin`
# does NOT reserve room away from the plot's own bars for a long tick label
# it only stops a label being clipped by the OUTER edge of the figure. A
# label longer than the current margin simply draws on top of the plot area
# instead. So automargin alone cannot be the fix; it stays on as a backstop
# for a container narrower than our own estimate, below.
#
# The fix (STILL the mechanism -- only the treatment of an over-length label
# changed, see the note below): fold the volume INTO the y tick text as one
# right-anchored string (`_tick_display`) -- there is then only ONE text
# element per row, so there is nothing left for it to collide with -- and
# reserve the left margin ourselves from the longest resulting LINE
# (`_gutter_margin_px`) rather than assume automargin will do it.
#
# --- Wrap instead of truncate -------------------------
# The gutter fix originally ellipsised a label past `MAX_LABEL_CHARS` from
# the right (`_truncate_label`). That approach was reversed: no chart may
# ever shorten a name, so `MAX_LABEL_CHARS`/`_truncate_label`/`ELLIPSIS` are
# GONE (not left as dead code -- a reversed decision is worth being explicit
# about).
# `wrap_label` replaces truncation: a label over `WRAP_WIDTH` chars wraps onto
# at most two lines at a word boundary instead of losing any text, and the row
# grows taller to fit (`row_height`'s `n_wrapped` term, `WRAP_ROW_FACTOR`).
# `_gutter_margin_px` now measures the longest LINE of a (possibly two-line)
# tick string, not the longest whole string, since a wrapped label's second
# line usually holds the trailing words plus the folded-in volume.
TICK_LABEL_GAP = "  "       # between the (possibly wrapped) label and its
                            # volume inside one right-anchored tick string
CHAR_WIDTH_EM = 0.6         # empirical average glyph width, as a fraction of
                            # font size, for the shipped sans stack -- used
                            # ONLY to reserve a left margin big enough that a
                            # long label never overlaps the bars (verified by
                            # `tests/ui/smoke.py`'s bounding-box check, not by
                            # this estimate alone)
GUTTER_MARGIN_PAD_PX = 12   # extra breathing room beyond the estimated width
GUTTER_MARGIN_MIN_PX = 8    # the old fixed margin, kept as the floor when
                            # there is nothing long enough to reserve room for
WRAP_WIDTH = 40             # `wrap_label` default -- a label longer than this
                            # many characters wraps at the last word boundary
                            # before it, never mid-word
WRAP_ROW_FACTOR = 1.7       # a wrapped (two-line) row needs ~1.7x a single
                            # -line row's vertical budget (measured); folded
                            # into `row_height` via its `n_wrapped` count
MARKER_PX = 10
LINE_PX = 2
HAIRLINE_PX = 1
FONT_PX = 12
GUTTER_FONT_PX = 11
BUBBLE_MIN_PX = 6
BUBBLE_MAX_PX = 34

DEFAULT_GROUP_SPAN = 0.82   # "bar-group span": was 0.8/0.9, matches the
                            # grouped-bar geometry `charts_compare.py`
                            # independently carried its OWN pair for the SAME
                            # `_series_offset_width` geometry (0.82/0.86, its
                            # `BAR_GROUP_SPAN`/`BAR_GROUP_FILL`). The Compare
                            # page's own `fig_metric_bars` chrome is the
                            # app's reference to converge ON, not away from, so
                            # this pair now matches Compare's exactly and IS the
                            # single source -- `charts_compare.py` should import
                            # these two names rather than redefine its own.
                            # Changes the Find
                            # panels' own yearly-breakdown geometry fractionally
                            # (was 0.8/0.9); Compare's own geometry is UNCHANGED
                            # since the values it already used are what this
                            # constant now equals.
DEFAULT_GROUP_FILL = 0.86

SI_NEUTRAL = 1.0            # SI/ESI reference: at the neutral value the institution's
                            # share equals the reference population's share
SI_LABEL_PAD_FRAC = 0.26    # : extra headroom (as a fraction of the SI
                            # panel's own value span) reserved on BOTH ends of
                            # the SI x-axis so the outer-end value label does
                            # not clip against the plot border.
                            # -7: 0.18 -> 0.26, and see SI_LABEL_MARGIN_PX
                            # below -- the pad ALONE cannot do this job. It is a
                            # fraction of the value SPAN, while the label it has
                            # to clear is a fixed ~30 px, so the clearance it
                            # buys collapses exactly where the span is widest.
                            # Measured on the worst case in the index (Ifremer's
                            # top-30 subfields at 1280 px: SI 0.17 to 21.35, and
                            # a 430 px name gutter that leaves the SI panel just
                            # 113 px wide): clearing "21.35" by padding alone
                            # needs a pad the size of the whole span, i.e. the
                            # data compressed into a third of the panel. 0.26 is
                            # what keeps the INNER labels off each other's ends
                            # without deforming the figure.
SI_LABEL_MARGIN_PX = 24     # -7: and this is what actually stops the
                            # OUTERMOST label clipping -- the SI trace draws
                            # with `cliponaxis=False`, so its text may run past
                            # the axis end, and the figure reserves a right
                            # margin wide enough to hold one label (~5 glyphs at
                            # GUTTER_FONT_PX plus the marker gap) instead of the
                            # 16 px of chrome every other figure uses. 24 rather
                            # than the 44 and 32 first tried, both MEASURED on the
                            # two worst panels: every px of right margin also
                            # narrows the plot region, and on the ERC panel (name
                            # gutter ~510 px) 44 and 32 pushed the two axis TITLES
                            # into each other. At 24 the worst-case label clears
                            # the paper edge by ~14 px AND the titles keep the
                            # separation they had. Nothing else in the layout
                            # moves: same heights, same column widths, same left
                            # gutter, same ranges.
FRONTIER_ORIGIN = 0.0       # the quadrant split on BOTH frontier axes (verified on
                            # topics_dim: `quadrant` flips sign at zero on expansion
                            # and on acceleration)
FRONTIER_ORIGIN_PX = 2      # : bold-ink width for the quadrant split lines
                            # (was a GRID hairline) -- visually dominant, the
                            # quadrant read is immediate rather than found

THIN_SPACE = "\N{NARROW NO-BREAK SPACE}"
EXCLUDED_GLYPH = "\N{ASTERISK OPERATOR}"   # catch-all / out-of-scope topic marker

# ---------------------------------------------------------------------------
# Axis + hover vocabulary. Digit-free by construction. A caller that wants
# different wording passes it in; nothing here is a sentence, only a label.
# ---------------------------------------------------------------------------
AX_SHARE = "Share of output"
AX_SI = "Specialisation index"
AX_ESI = "Specialisation index (SDG)"
AX_WORKS = "Publications"  # renamed from "works" for reader clarity
AX_YEAR = "Year"
AX_EXPANSION = "Expansion"
AX_ACCELERATION = "Acceleration"

HOVER_SHARE = "share"
HOVER_SI = "SI"
HOVER_ESI = "ESI"
HOVER_VOL_FULL = "works (full counting)"
HOVER_VOL_FRAC = "works (fractional)"
HOVER_MASS = "classified mass"
HOVER_EXPANSION = "expansion"
HOVER_ACCELERATION = "acceleration"
HOVER_EXCLUDED = "catch-all / out-of-scope topic"

FAMILIES = ("oa", "erc", "sdg", "doctype")
SORTS = ("volume", "taxonomy")

_PCT_FMT = f".{SHARE_DECIMALS}%"
_AXIS_PCT_FMT = f".{AXIS_DECIMALS}%"
_SI_FMT = f".{SI_DECIMALS}f"
_FRONTIER_FMT = f".{FRONTIER_DECIMALS}f"

# Column-name candidates, in preference order, for the frames of section 9.4.
# `sdg_label_numbered` ("SDG 1. No poverty") is preferred over the plain
# `sdg_label` whenever the caller's frame carries it; `fig_sdg` never picks the
# column itself, `_first_col` does, so the preference lives in ONE place.
_LABEL_COLS = ("topic_name", "subfield_name", "field_name", "panel_label",
               "sdg_label_numbered", "sdg_label", "doc_type", "label", "domain_name")
_VOLUME_COLS = ("vol_full", "vol_frac", "mass", "total")


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------
def row_height(n: int, minimum: int = MIN_HEIGHT, n_wrapped: int = 0) -> int:
    """Figure height for `n` category rows -- the shared idiom, one place.

    `n_wrapped` counts rows whose label WRAPPED to two lines
    (`wrap_label` inserted a `<br>`): each such row needs `WRAP_ROW_FACTOR`
    normal rows' worth of vertical space instead of one, so the extra height
    is `(WRAP_ROW_FACTOR - 1)` rows per wrapped row, not per label character
    wrapping is binary (one line or two, never more), so the row-height cost
    is too. Default `0` reproduces the earlier formula exactly."""
    # Measured on a rendered chart: plotly spaces a categorical axis
    # UNIFORMLY, so adding height only in proportion to the number of
    # wrapped rows left each two-line label overlapping its neighbours
    # (3 wrapped rows of 30 grew the pitch by 7 %).
    # If ANY label wraps, every row must get the two-line pitch.
    n_wrapped = min(max(int(n_wrapped), 0), int(n))
    pitch = ROW_PX * (WRAP_ROW_FACTOR if n_wrapped > 0 else 1.0)
    return max(minimum, int(round(pitch * int(n))) + BASE_PX)


def _fmt_pct(v: float) -> str:
    return P.NA_MARK if v is None or (isinstance(v, float) and np.isnan(v)) else format(float(v), _PCT_FMT)


def _fmt_si(v: float) -> str:
    return P.NA_MARK if v is None or (isinstance(v, float) and np.isnan(v)) else format(float(v), _SI_FMT)


def _fmt_frontier(v: float) -> str:
    return P.NA_MARK if v is None or (isinstance(v, float) and np.isnan(v)) else format(float(v), _FRONTIER_FMT)


def _fmt_vol(v) -> str:
    """Volumes print with a narrow no-break space thousands separator (the
    `fr_int` convention). A fractional volume keeps one decimal; a full count
    prints as an integer."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return P.NA_MARK
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return format(int(round(v)), ",").replace(",", THIN_SPACE)
    return format(v, f",.{SHARE_DECIMALS}f").replace(",", THIN_SPACE)


def wrap_label(text, width: int = WRAP_WIDTH) -> str:
    """Wrap a category label onto AT MOST TWO LINES at a word boundary,
    never splitting a word, never dropping a character (replaces the
    earlier ellipsis rule; `tests/test_charts.py` pins that the joined-back text
    always equals the original).

    Greedy word-wrap: a word is added to the current line whenever the result
    still fits `width`; a line already over `width` on its own (one very long
    word) is kept whole rather than split, because "words never split" outranks
    the width target. If greedy wrapping would need a THIRD line, every line
    past the first is joined back into ONE second line with a single space
    the cap is "two lines", not "keep wrapping"; nothing is ever truncated, so
    the full text always survives, just possibly as a longer second line."""
    words = str(text).split()
    if not words:
        return str(text)
    lines: list[str] = [words[0]]
    for w in words[1:]:
        candidate = f"{lines[-1]} {w}"
        if len(candidate) <= width:
            lines[-1] = candidate
        else:
            lines.append(w)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return "<br>".join(lines)


def _tick_display(label: str, vol_text: str | None, *, wrap: bool = True) -> tuple[str, str]:
    """One right-anchored tick string carrying BOTH the (possibly wrapped)
    label and its volume, so there is a single text element per row instead
    of two independently-laid-out ones (the X3 fix, unchanged mechanism).
    Returns `(plain, styled)`: `plain` uses a bare `\\n` line break (never
    `<br>`) so `_gutter_margin_px` can split on it to find the longest LINE;
    `styled` is what plotly actually draws, wrapped label lines joined by
    `<br>` and the volume in the secondary ink and gutter font size via
    plotly's limited tick pseudo-html (`<span style=".">`, verified to
    render as a coloured, resized `<tspan>` on the pinned plotly 5.24.1).

    `wrap`: `False` skips `wrap_label` entirely and keeps the label on
    its one line, whatever its length -- the Find panels' new priority ("full
    label on one row wins over bar length"), which pushes the cost onto
    `_gutter_margin_px` reserving a wider margin instead."""
    wrapped = wrap_label(label) if wrap else str(label)
    plain = wrapped.replace("<br>", "\n")
    if vol_text is None:
        return plain, wrapped
    plain = f"{plain}{TICK_LABEL_GAP}{vol_text}"
    styled = (f"{wrapped}{TICK_LABEL_GAP}"
              f'<span style="color:{P.INK_SECONDARY};font-size:{GUTTER_FONT_PX}px">{vol_text}</span>')
    return plain, styled


def _gutter_margin_px(plain_texts: Sequence[str], font_px: int = FONT_PX) -> int:
    """The left margin to RESERVE for the longest tick LINE actually shown,
    since automargin will not do this on its own (see the fix note above).
    `plain_texts` may hold `\\n`-separated lines (a wrapped label): the margin
    is sized off the single longest line across every row, not off a whole
    (possibly two-line) string's total character count, which would reserve
    far more margin than either line alone needs. A generous per-character
    estimate plus padding; the real proof that this is enough is
    `tests/ui/smoke.py`'s bounding-box check on the real app, not this
    estimate."""
    lines = [ln for t in plain_texts for ln in str(t).split("\n")]
    longest = max((len(ln) for ln in lines), default=0)
    return max(GUTTER_MARGIN_MIN_PX, int(round(longest * font_px * CHAR_WIDTH_EM)) + GUTTER_MARGIN_PAD_PX)


def _first_col(df: pd.DataFrame, candidates: Sequence[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _nice_ticks(vmax: float, target: int = 5) -> list[float]:
    """Non-negative tick positions for an axis whose RANGE starts below zero
    (the volume gutter). Without explicit `tickvals`, plotly would label the
    gutter with negative percentages -- a number the chart does not mean."""
    if not np.isfinite(vmax) or vmax <= 0:
        return [0.0]
    raw = vmax / max(target, 1)
    mag = 10.0 ** np.floor(np.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        step = mult * mag
        if raw <= step:
            break
    n = int(np.floor(vmax / step)) + 1
    return [round(i * step, 12) for i in range(n)]


def _colors_for(df: pd.DataFrame, family: str) -> list[str]:
    """The ONE place a family maps to hues. Coexistence rule (palette.py
    docstring): a figure uses exactly one family, so this returns one list and
    nothing merges two."""
    if family == "oa":
        col = _first_col(df, ("domain_id",))
        return [P.domain_color(v) for v in df[col]] if col else [P.COMPARISON] * len(df)
    if family == "erc":
        col = _first_col(df, ("erc_domain",))
        return [P.erc_color(v) for v in df[col]] if col else [P.COMPARISON] * len(df)
    if family == "sdg":
        col = _first_col(df, ("sdg_number", "sdg_idx"))
        if col is None:
            return [P.COMPARISON] * len(df)
        offset = 1 if col == "sdg_idx" else 0
        return [P.sdg_color(int(v) + offset) for v in df[col]]
    if family == "doctype":
        col = _first_col(df, ("doc_type", "type"))
        return [P.doctype_color(v) for v in df[col]] if col else [P.COMPARISON] * len(df)
    raise ValueError(f"family must be one of {FAMILIES}, got {family!r}")


def _taxonomy_keys(df: pd.DataFrame, family: str) -> list[str]:
    if family == "erc":
        return [c for c in ("erc_domain_rank", "panel_idx", "panel_code") if c in df.columns]
    if family == "sdg":
        return [c for c in ("sdg_number", "sdg_idx") if c in df.columns]
    if family == "doctype":
        return [c for c in ("doctype_rank", "doc_type") if c in df.columns]
    return [c for c in ("domain_id", "field_id", "subfield_id", "topic_id") if c in df.columns]


def _ordered(df: pd.DataFrame, family: str, sort: str, value_col: str) -> pd.DataFrame:
    if sort not in SORTS:
        raise ValueError(f"sort must be one of {SORTS}, got {sort!r}")
    out = df.copy()
    if sort == "volume":
        return out.sort_values(value_col, ascending=False, kind="mergesort").reset_index(drop=True)
    if family == "erc" and "erc_domain" in out.columns and "erc_domain_rank" not in out.columns:
        rank = {d: i for i, d in enumerate(P.ERC_DOMAIN_ORDER)}
        out["erc_domain_rank"] = out["erc_domain"].astype(str).str.upper().map(rank).fillna(len(rank))
    if family == "doctype" and "doc_type" in out.columns and "doctype_rank" not in out.columns:
        rank = {d: i for i, d in enumerate(P.DOCTYPE_ORDER)}
        out["doctype_rank"] = out["doc_type"].astype(str).str.lower().map(rank).fillna(len(rank))
    keys = _taxonomy_keys(out, family)
    if not keys:
        return out.reset_index(drop=True)
    return out.sort_values(keys, kind="mergesort").reset_index(drop=True)


def _base_layout(fig: go.Figure, height: int, *, margin: dict) -> go.Figure:
    fig.update_layout(
        height=height,
        bargap=BAR_GAP,
        showlegend=False,
        paper_bgcolor=P.SURFACE,
        plot_bgcolor=P.SURFACE,
        margin=margin,
        font=dict(color=P.INK, size=FONT_PX),
        hoverlabel=dict(bgcolor=P.SURFACE, font=dict(color=P.INK, size=FONT_PX)),
    )
    return fig


# ---------------------------------------------------------------------------
# 1. share + SI -- the paired form (A/B #3 winner), with the volume gutter
#    (A/B #4 winner). Used by the Fields, Top subfields, SDG and ERC panels.
# ---------------------------------------------------------------------------
def fig_share_si(
    df: pd.DataFrame,
    *,
    family: str = "oa",
    sort: str = "volume",
    gutter: bool = True,
    si_col: str = "si",
    share_col: str = "share",
    label_col: str | None = None,
    volume_col: str | None = None,
    si_axis_title: str = AX_SI,
    si_hover_label: str = HOVER_SI,
    stacked: bool = False,
    wrap: bool = False,
) -> go.Figure:
    """Two aligned panels of ONE figure, sharing the y (category) axis.

    LEFT horizontal share bars, coloured by `family`; with `gutter=True` the
           volume prints right-aligned in a fixed gutter left of the zero
           baseline, so every number sits in one column (A/B #4).
    RIGHT the SI lollipop: a stem from the neutral reference to the value and
           a dot at the value, on ONE scale shared by every row, with a dashed
           vertical reference line AND unit grid lines at every integer up to
           the axis max. Mark style is driven by the frame's OWN
           `si_status` column when present -- `solid` -> a FILLED dot (this
           panel's original mark); `thin` -> a HOLLOW dot (white fill, coloured
           outline), disclosing a below-the-old-floor cell instead of erasing
           it; `none` -> no mark and no stem, same treatment as a NaN `si_col`.
           **A zero-volume row NEVER gets a mark, whatever `si_status` says**
           (the ERC display-bug fix): a panel with no publications
           cannot have a specialisation reading. When `si_status` is absent,
           the earlier rule applies unchanged -- a defined `si` gets a filled
           dot, a NaN `si` gets none -- and its hover says so with
           `palette.NA_MARK`.

    `stacked=True` puts the SI panel BELOW the share panel instead of beside it,
    same row order, for the narrow breakpoint: side by side at 390 px each panel
    measures 61 px of plot area, which is not a chart (the
    measured cost of the A/B #3 winner). Streamlit cannot read the viewport width
    server-side, so the caller decides when to pass it -- the builder only makes
    the layout available.

    `sort="volume"` orders by the share descending; `sort="taxonomy"` orders by
    the family's own hierarchy (domain -> field -> subfield -> topic; ERC domain
    then panel; SDG number). Colours never move with the sort: they follow the
    entity (dataviz non-negotiable "colour follows the entity, never its rank").

    `wrap`: the Find panels never wrap a label onto
    a second line any more -- the left gutter widens to fit the full name on
    ONE row instead (`_tick_display`'s own `wrap` keyword). Pass `wrap=True`
    to get the pre- two-line-wrap behaviour back; nothing in this app
    does, today.
    """
    if share_col not in df.columns:
        raise ValueError(f"missing column {share_col!r}")
    d = _ordered(df, family, sort, share_col)
    n = len(d)
    label_col = label_col or _first_col(d, _LABEL_COLS)
    if label_col is None:
        raise ValueError("no label column found; pass label_col=")
    volume_col = volume_col or _first_col(d, _VOLUME_COLS)

    names = [str(v) for v in d[label_col]]
    colors = _colors_for(d, family)
    share = d[share_col].to_numpy(dtype=float)
    si = (d[si_col].to_numpy(dtype=float) if si_col in d.columns
          else np.full(n, np.nan, dtype=float))
    vol = d[volume_col].to_numpy() if volume_col else None

    # A zero-volume row never gets a mark under any rule (the ERC
    # display bug): NaN volume is NOT zero (it means "unknown", not "none"),
    # only an actual zero counts.
    if vol is not None:
        vol_num = pd.to_numeric(pd.Series(vol), errors="coerce").to_numpy(dtype=float)
        zero_volume = np.isclose(vol_num, 0.0)
    else:
        zero_volume = np.zeros(n, dtype=bool)

    if "si_status" in d.columns:
        status = d["si_status"].astype(str).to_numpy()
        shown = np.isin(status, ["solid", "thin"])
        hollow = status == "thin"
    else:
        shown = np.ones(n, dtype=bool)
        hollow = np.zeros(n, dtype=bool)
    ok = shown & np.isfinite(si) & ~zero_volume
    has_si = bool(ok.any())

    # No mark eligible anywhere in the frame (every row below the floor, or
    # `si_status` says `none` throughout) -> ONE panel, not a two-panel figure
    # with an empty right half. The share read is unaffected and the caller's
    # caption says why the column is gone.
    if not has_si:
        fig = make_subplots(rows=1, cols=1)
        si_row, si_col = 1, 1
    elif stacked:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=False,
                            row_heights=[0.5, 0.5], vertical_spacing=0.08)
        si_row, si_col = 2, 1
    else:
        fig = make_subplots(rows=1, cols=2, shared_yaxes=True,
                            column_widths=[0.62, 0.38], horizontal_spacing=0.03)
        si_row, si_col = 1, 2

    bar_hover = []
    for i in range(n):
        parts = [names[i], f"{HOVER_SHARE}{THIN_SPACE}{_fmt_pct(share[i])}"]
        if vol is not None:
            lab = HOVER_VOL_FULL if volume_col == "vol_full" else (
                HOVER_VOL_FRAC if volume_col == "vol_frac" else HOVER_MASS)
            parts.append(f"{lab}{THIN_SPACE}{_fmt_vol(vol[i])}")
        parts.append(f"{si_hover_label}{THIN_SPACE}{_fmt_si(si[i])}")
        bar_hover.append("<br>".join(parts))

    fig.add_trace(go.Bar(
        x=share, y=names, orientation="h",
        marker_color=colors, marker_line_color=P.SURFACE, marker_line_width=HAIRLINE_PX,
        customdata=bar_hover, hovertemplate="%{customdata}<extra></extra>",
        showlegend=False,
    ), row=1, col=1)

    # Volume gutter (A/B #4): folded into the y tick text as ONE right-anchored
    # string per row -- see the fix note above. Wrapping applies to every
    # row's label whether or not `gutter` is on, because a long category name
    # can overrun the plot on its own.
    if gutter and vol is not None:
        pairs = [_tick_display(names[i], _fmt_vol(vol[i]), wrap=wrap) for i in range(n)]
    else:
        pairs = [_tick_display(names[i], None, wrap=wrap) for i in range(n)]
    plain_display = [p for p, _ in pairs]
    styled_display = [s for _, s in pairs]
    n_wrapped = sum(1 for s in styled_display if "<br>" in s)
    fig.update_yaxes(tickmode="array", tickvals=names, ticktext=styled_display)

    xmax = float(np.nanmax(share)) if n and np.isfinite(share).any() else 1.0
    xmax = xmax if xmax > 0 else 1.0
    if gutter and vol is not None:
        fig.add_shape(type="line", x0=0, x1=0, y0=-0.5, y1=n - 0.5,
                      xref="x", yref="y", line=dict(color=P.BORDER, width=HAIRLINE_PX))
    fig.update_xaxes(range=[0, xmax * 1.02], tickvals=_nice_ticks(xmax), row=1, col=1)

    if has_si:
        for i, nm in enumerate(names):
            if not ok[i]:
                continue
            fig.add_trace(go.Scatter(
                x=[SI_NEUTRAL, si[i]], y=[nm, nm], mode="lines",
                line=dict(color=colors[i], width=LINE_PX),
                hoverinfo="skip", showlegend=False,
            ), row=si_row, col=si_col)
        # solid -> filled dot (family colour fill, SURFACE outline, as before);
        # thin -> HOLLOW dot (SURFACE fill, family-colour outline at
        #          OUTLINE_WIDTH) -- a below-the-old-floor cell is disclosed,
        #          never erased. Per-point colour/line arrays, not a
        #          second trace, so the two states share one legend-free trace.
        mk_fill = [P.SURFACE if hollow[i] else colors[i] for i in range(n) if ok[i]]
        mk_line_color = [colors[i] if hollow[i] else P.SURFACE for i in range(n) if ok[i]]
        mk_line_width = [P.OUTLINE_WIDTH if hollow[i] else LINE_PX for i in range(n) if ok[i]]
        si_shown = si[ok]
        # : the marker carries its OWN value as text, anchored on the
        # side AWAY from the neutral reference -- left of the dot below
        # neutral, right above it -- so the read is local to the row instead
        # of a lookup against the retired unit grid (below). One trace, so
        # the label can never fall out of sync with its own dot.
        si_text = [_fmt_si(v) for v in si_shown]
        si_textpos = ["middle left" if v < SI_NEUTRAL else "middle right" for v in si_shown]
        fig.add_trace(go.Scatter(
            x=si_shown, y=[nm for nm, k in zip(names, ok) if k], mode="markers+text",
            marker=dict(color=mk_fill, size=MARKER_PX,
                        line=dict(color=mk_line_color, width=mk_line_width)),
            text=si_text, textposition=si_textpos,
            textfont=dict(color=P.INK_SECONDARY, size=GUTTER_FONT_PX),
            customdata=[h for h, k in zip(bar_hover, ok) if k],
            hovertemplate="%{customdata}<extra></extra>", showlegend=False,
            # -7: the label may run PAST the axis end rather than losing
            # its last glyphs to the plot border. The right margin below is
            # sized to hold it (`SI_LABEL_MARGIN_PX`); on the inner side the
            # label runs into the gap between the two panels, which is blank
            # (the share bars nearest the SI panel are the shortest rows).
            cliponaxis=False,
        ), row=si_row, col=si_col)
        fig.add_vline(x=SI_NEUTRAL, row=si_row, col=si_col,
                      line=dict(color=P.INK_SECONDARY, width=HAIRLINE_PX, dash="dash"))
        # The per-integer unit grid is retired in favour of the
        # outer-end label above -- `showgrid=False` removes it. The dashed
        # neutral-reference line just above is NOT a "unit gridline" and
        # stays. The axis range is padded on BOTH ends (`SI_LABEL_PAD_FRAC`)
        # so the new text never clips against the plot border, whichever side
        # of the neutral value a row's marker falls on.
        si_lo = min(0.0, SI_NEUTRAL, float(si_shown.min()) if si_shown.size else SI_NEUTRAL)
        si_hi = max(SI_NEUTRAL, float(si_shown.max()) if si_shown.size else SI_NEUTRAL)
        pad = max(si_hi - si_lo, HAIRLINE_PX) * SI_LABEL_PAD_FRAC
        fig.update_xaxes(title_text=si_axis_title, showgrid=False,
                         range=[si_lo - pad, si_hi + pad], row=si_row, col=si_col)

    fig.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
    fig.update_xaxes(gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)
    fig.update_xaxes(title_text=AX_SHARE, tickformat=_AXIS_PCT_FMT, row=1, col=1)
    height = row_height(n, n_wrapped=n_wrapped) * (2 if (has_si and stacked) else 1)
    margin_l = _gutter_margin_px(plain_display)
    margin_r = SI_LABEL_MARGIN_PX if has_si else 16
    return _base_layout(fig, height, margin=dict(t=BASE_PX // 2, l=margin_l, r=margin_r,
                                                 b=BASE_PX))


# ---------------------------------------------------------------------------
# 2. Top topics -- share bars, catch-all topics flagged (glyph + muted fill)
# ---------------------------------------------------------------------------
def fig_topics(
    df: pd.DataFrame,
    *,
    sort: str = "volume",
    gutter: bool = True,
    share_col: str = "share",
    label_col: str = "topic_name",
    volume_col: str | None = None,
    wrap: bool = False,
) -> go.Figure:
    """Horizontal share bars for topics, coloured by the topic's DOMAIN (topics
    inherit; `palette.domain_color`). A row flagged `is_excluded` (the catch-all
    / out-of-scope topics) keeps its domain hue at `palette.MUTED_OPACITY`, is
    prefixed with `EXCLUDED_GLYPH` on the axis, and says why on hover -- it is
    shown and counted, never silently dropped.

    `sort` is retired: the keyword stays so no existing caller
    breaks, but the panel is now ALWAYS volume-ordered whatever value is
    passed, since "top N" is itself a volume-defined cut -- a taxonomy
    re-sort of it would read as an arbitrary row order, not a second view.
    `wrap` (default `False`, see `fig_share_si`): topic names are the longest
    labels in the app, so this panel never wraps them -- the gutter widens
    to fit the full name on one row instead."""
    if sort not in SORTS:
        raise ValueError(f"sort must be one of {SORTS}, got {sort!r}")
    d = _ordered(df, "oa", "volume", share_col)  # : fixed, `sort` ignored
    n = len(d)
    volume_col = volume_col or _first_col(d, _VOLUME_COLS)
    excluded = (d["is_excluded"].fillna(False).to_numpy(dtype=bool)
                if "is_excluded" in d.columns else np.zeros(n, dtype=bool))
    colors = _colors_for(d, "oa")
    names = [f"{EXCLUDED_GLYPH}{THIN_SPACE}{v}" if excluded[i] else str(v)
             for i, v in enumerate(d[label_col])]
    # `names` is the identity (y positions / hover), full and untouched;
    # `_tick_display` wraps it for the volume-folded tick actually drawn
    # see fig_share_si's fix note above; topic names are the longest labels
    # in the app, so this panel is the wrap mechanism's harder test.
    share = d[share_col].to_numpy(dtype=float)
    vol = d[volume_col].to_numpy() if volume_col else None

    hover = []
    for i in range(n):
        parts = [str(d[label_col].iloc[i]), f"{HOVER_SHARE}{THIN_SPACE}{_fmt_pct(share[i])}"]
        if vol is not None:
            parts.append(f"{HOVER_VOL_FULL if volume_col == 'vol_full' else HOVER_VOL_FRAC}"
                         f"{THIN_SPACE}{_fmt_vol(vol[i])}")
        if excluded[i]:
            parts.append(HOVER_EXCLUDED)
        hover.append("<br>".join(parts))

    fig = go.Figure(go.Bar(
        x=share, y=names, orientation="h",
        marker=dict(color=colors, opacity=[P.MUTED_OPACITY if e else 1.0 for e in excluded],
                    line=dict(color=P.SURFACE, width=HAIRLINE_PX)),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False,
    ))
    if gutter and vol is not None:
        pairs = [_tick_display(names[i], _fmt_vol(vol[i]), wrap=wrap) for i in range(n)]
    else:
        pairs = [_tick_display(names[i], None, wrap=wrap) for i in range(n)]
    plain_display = [p for p, _ in pairs]
    styled_display = [s for _, s in pairs]
    n_wrapped = sum(1 for s in styled_display if "<br>" in s)
    fig.update_yaxes(tickmode="array", tickvals=names, ticktext=styled_display)

    xmax = float(np.nanmax(share)) if n and np.isfinite(share).any() else 1.0
    xmax = xmax if xmax > 0 else 1.0
    if gutter and vol is not None:
        fig.add_shape(type="line", x0=0, x1=0, y0=-0.5, y1=n - 0.5,
                      line=dict(color=P.BORDER, width=HAIRLINE_PX))
    fig.update_xaxes(range=[0, xmax * 1.02], tickvals=_nice_ticks(xmax))
    fig.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
    fig.update_xaxes(title_text=AX_SHARE, tickformat=_AXIS_PCT_FMT,
                     gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)
    margin_l = _gutter_margin_px(plain_display)
    return _base_layout(fig, row_height(n, n_wrapped=n_wrapped),
                        margin=dict(t=BASE_PX // 2, l=margin_l, r=16, b=BASE_PX))


# ---------------------------------------------------------------------------
# 3. Frontier positioning -- topics scatter, Expansion x Acceleration
# ---------------------------------------------------------------------------
def _frontier_topn(d: pd.DataFrame, top_n: int | None, size_col: str | None) -> pd.DataFrame:
    """The ONE selection rule 's top-N slider drives, shared by
    `fig_frontier` and `frontier_coverage` so the chart drawn and the
    caption describing it can never disagree. Keeps the `top_n` highest-mass
    rows of `d` (already the placeable subset); `None`, non-positive, or a
    `top_n` at least as large as `len(d)` is a no-op -- every row stays, the
    pre- behaviour. Ties broken by a STABLE sort on the frame's own
    row order, so a re-render of the identical frame never reshuffles which
    rows land on the cut line."""
    if top_n is None or top_n <= 0 or len(d) <= top_n:
        return d
    if size_col and size_col in d.columns:
        key = pd.to_numeric(d[size_col], errors="coerce").fillna(0.0)
    else:
        key = pd.Series(np.arange(len(d), 0, -1), index=d.index, dtype=float)
    order = key.sort_values(ascending=False, kind="mergesort").index[:top_n]
    return d.loc[order].reset_index(drop=True)


def frontier_coverage(
    df: pd.DataFrame,
    *,
    x_col: str = "expansion_latest",
    y_col: str = "acceleration_latest",
    size_col: str | None = None,
    top_n: int | None = None,
    excluded_col: str = "is_excluded",
) -> dict:
    """The disclosure NUMBERS `fig_frontier`'s caller needs, computed
    from the SAME placeable-then-`top_n` selection `fig_frontier` itself draws
    never a string (this module's digit-ban, see the module docstring): the
    caller composes its own `{placeholder}` sentence in `copy.py` from these.

      n_placeable -- rows with BOTH axes scored, before any `top_n` cut
      n_shown -- rows actually plotted after the cut (mirrors
                            `fig_frontier`'s own row count exactly)
      n_catchall_shown -- how many of the SHOWN rows are catch-all /
                            out-of-scope (`excluded_col`) -- states that
                            catch-all topics are INCLUDED in the `top_n`
                            count, not hidden inside it
      mass_shown / mass_placeable -- summed `size_col` mass, shown vs. every
                            placeable row (equal when `top_n` is a no-op)
      pct_mass_not_shown -- `1 - mass_shown / mass_placeable`, floored at
                            zero and returned as `0.0` (never a division by
                            zero) when nothing is placeable
      min_mass_shown -- the smallest `size_col` value among the shown
                            rows -- the minimum mass that made the cut;
                            `None` (n/a-safe) when nothing is shown
    """
    size_col = size_col or _first_col(df, _VOLUME_COLS)
    placeable = df[np.isfinite(pd.to_numeric(df[x_col], errors="coerce"))
                   & np.isfinite(pd.to_numeric(df[y_col], errors="coerce"))].reset_index(drop=True)
    shown = _frontier_topn(placeable, top_n, size_col)
    if size_col and size_col in placeable.columns:
        mass_all = pd.to_numeric(placeable[size_col], errors="coerce").fillna(0.0)
        mass_shown_s = pd.to_numeric(shown[size_col], errors="coerce").fillna(0.0)
    else:
        mass_all = pd.Series(1.0, index=placeable.index)
        mass_shown_s = pd.Series(1.0, index=shown.index)
    mass_total = float(mass_all.sum())
    mass_shown = float(mass_shown_s.sum())
    excluded_shown = (int(shown[excluded_col].fillna(False).sum())
                      if excluded_col in shown.columns else 0)
    return {
        "n_placeable": int(len(placeable)),
        "n_shown": int(len(shown)),
        "n_catchall_shown": excluded_shown,
        "mass_shown": mass_shown,
        "mass_placeable": mass_total,
        "pct_mass_not_shown": (0.0 if mass_total <= 0 else max(0.0, 1.0 - mass_shown / mass_total)),
        "min_mass_shown": (float(mass_shown_s.min()) if len(shown) else None),
    }


def fig_frontier(
    df: pd.DataFrame,
    *,
    x_col: str = "expansion_latest",
    y_col: str = "acceleration_latest",
    size_col: str | None = None,
    label_col: str = "topic_name",
    top_n: int | None = None,
) -> go.Figure:
    """One bubble per SCORED topic: x = expansion, y = acceleration, area = the
    topic's mass on the current basis, colour = its domain. The two quadrant
    lines sit at the origin on both axes (verified against `topics_dim.quadrant`,
    which flips sign exactly there), drawn BOLD in `palette.INK` so the quadrant read is immediate. A top-quartile
    frontier topic (`top25pct_frontier`) carries an INK outline -- a shape
    signal on top of its family colour, never a new hue. A row flagged
    `is_excluded` (catch-all / out-of-scope, present or not depending on
    whether the caller kept those rows in) gets the same muted-opacity + hover
    disclosure `fig_topics` uses, so it is shown and counted rather than being
    invisible inside the `top_n` cut.

    Rows with no score (`x_col`/`y_col` NaN) are DROPPED here and must be
    counted in the caller's caption: the panel states what it could not place
    rather than letting it vanish.

    `top_n`: keeps only the `top_n` highest-mass placeable rows
    (`_frontier_topn`) -- the SAME keyword serves BOTH of the app's modes
    (top-N-by-volume and the global top-quartile set), so one slider value
    drives either. The axes always autorange to whatever ends up plotted, so
    a smaller `top_n` is a tighter plot, never a fixed one. `None` (default)
    reproduces the pre- behaviour: everything the caller already
    filtered is plotted, uncapped. `frontier_coverage` (above) computes the
    caption figures from the IDENTICAL cut."""
    size_col = size_col or _first_col(df, _VOLUME_COLS)
    d = df.copy()
    d = d[np.isfinite(pd.to_numeric(d[x_col], errors="coerce"))
          & np.isfinite(pd.to_numeric(d[y_col], errors="coerce"))].reset_index(drop=True)
    d = _frontier_topn(d, top_n, size_col)
    n = len(d)
    x = d[x_col].to_numpy(dtype=float)
    y = d[y_col].to_numpy(dtype=float)
    colors = _colors_for(d, "oa")
    mass = (pd.to_numeric(d[size_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
            if size_col else np.ones(n))
    mmax = float(mass.max()) if n and mass.max() > 0 else 1.0
    sizes = BUBBLE_MIN_PX + (BUBBLE_MAX_PX - BUBBLE_MIN_PX) * np.sqrt(mass / mmax)
    top = (d["top25pct_frontier"].fillna(False).to_numpy(dtype=bool)
           if "top25pct_frontier" in d.columns else np.zeros(n, dtype=bool))
    excluded = (d["is_excluded"].fillna(False).to_numpy(dtype=bool)
                if "is_excluded" in d.columns else np.zeros(n, dtype=bool))

    hover = []
    for i in range(n):
        parts = [str(d[label_col].iloc[i]),
                 f"{HOVER_EXPANSION}{THIN_SPACE}{_fmt_frontier(x[i])}",
                 f"{HOVER_ACCELERATION}{THIN_SPACE}{_fmt_frontier(y[i])}"]
        if size_col:
            parts.append(f"{HOVER_MASS}{THIN_SPACE}{_fmt_vol(mass[i])}")
        if excluded[i]:
            parts.append(HOVER_EXCLUDED)
        hover.append("<br>".join(parts))

    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="markers",
        marker=dict(color=colors, size=sizes, sizemode="diameter",
                    opacity=[P.MUTED_OPACITY if e else 1.0 for e in excluded],
                    line=dict(color=[P.INK if t else P.SURFACE for t in top],
                              width=[P.OUTLINE_WIDTH if t else HAIRLINE_PX for t in top])),
        customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False,
    ))
    fig.add_vline(x=FRONTIER_ORIGIN, line=dict(color=P.INK, width=FRONTIER_ORIGIN_PX))
    fig.add_hline(y=FRONTIER_ORIGIN, line=dict(color=P.INK, width=FRONTIER_ORIGIN_PX))
    fig.update_xaxes(title_text=AX_EXPANSION, gridcolor=P.GRID,
                     zerolinecolor=P.GRID, linecolor=P.BORDER)
    fig.update_yaxes(title_text=AX_ACCELERATION, gridcolor=P.GRID,
                     zerolinecolor=P.GRID, linecolor=P.BORDER)
    return _base_layout(fig, SCATTER_HEIGHT, margin=dict(t=BASE_PX // 2, l=8, r=16, b=BASE_PX))


# ---------------------------------------------------------------------------
# 4. SDG profile -- share bars in goal order + ESI dots (UN colours)
# ---------------------------------------------------------------------------
def fig_sdg(df: pd.DataFrame, *, sort: str = "taxonomy", gutter: bool = True) -> go.Figure:
    """The SDG panel. Delegates to `fig_share_si` with `esi` presented in the SI
    slot, so the reader learns ONE form and reuses it
    (`same-read-same-form`).

    The share denominator is SDG-TAGGED fractional mass and the labelling is
    MULTI-LABEL -- one work can carry several goals, so these shares do NOT sum
    to one. The caller's caption must say so; this builder deliberately draws no
    total and no stack that would imply a partition."""
    d = df.copy()
    if "esi" in d.columns and "si" not in d.columns:
        d = d.rename(columns={"esi": "si"})
    if "sdg_number" not in d.columns and "sdg_idx" in d.columns:
        d["sdg_number"] = pd.to_numeric(d["sdg_idx"], errors="coerce") + 1
    return fig_share_si(d, family="sdg", sort=sort, gutter=gutter,
                        si_axis_title=AX_ESI, si_hover_label=HOVER_ESI)


# ---------------------------------------------------------------------------
# 5. ERC profile -- panels grouped by ERC domain, share + SI
# ---------------------------------------------------------------------------
def fig_erc(df: pd.DataFrame, *, sort: str = "taxonomy", gutter: bool = True) -> go.Figure:
    """The ERC panel view: one row per ERC evaluation panel, coloured by its ERC
    DOMAIN (three hues -- `palette.ERC_DOMAIN_COLORS`), share on the left and SI
    on the right, `sort="taxonomy"` grouping the panels by domain in the fixed
    PE -> LS -> SH order. The weak-panel caveat (some panels are thinly
    populated) is the caller's caption, not a mark on the chart."""
    return fig_share_si(df, family="erc", sort=sort, gutter=gutter)


# ---------------------------------------------------------------------------
# 6. The yearly-breakdown PAIR: global horizontal bars + per-year GROUPED bars
# ---------------------------------------------------------------------------
def fig_breakdown_global(
    labels: Sequence[str],
    totals: Sequence[float],
    colors: Sequence[str],
) -> go.Figure:
    """LEFT panel of the pair: one horizontal bar per series, sorted by volume
    descending, with a DIRECT END LABEL and no legend (the y-axis names the
    series; the shared chip legend serves the pair).

    Why the direct end label here and a left gutter in `fig_share_si`: there the
    number is a SECOND measure sitting beside a share bar, and A/B #4 showed it
    belongs in an aligned column; here the number IS the bar's own value, which
    is the textbook direct-label case (dataviz marks-and-anatomy, "selective
    direct labels"). Same pattern as an earlier SIRIS Streamlit tool's
    global-breakdown chart."""
    order = sorted(range(len(labels)), key=lambda i: float(totals[i]), reverse=True)
    cats = [str(labels[i]) for i in order]
    tot = [float(totals[i]) for i in order]
    cols = [colors[i] for i in order]
    hover = [f"{c}<br>{AX_WORKS.lower()}{THIN_SPACE}{_fmt_vol(t)}" for c, t in zip(cats, tot)]

    fig = go.Figure(go.Bar(
        x=tot, y=cats, orientation="h",
        marker_color=cols, marker_line_color=P.SURFACE, marker_line_width=HAIRLINE_PX,
        customdata=hover, hovertemplate="%{customdata}<extra></extra>", showlegend=False,
    ))
    for c, t in zip(cats, tot):
        fig.add_annotation(x=t, y=c, text=_fmt_vol(t), showarrow=False,
                           xanchor="left", xshift=8, yanchor="middle",
                           font=dict(size=GUTTER_FONT_PX, color=P.INK_SECONDARY))
    tmax = max(tot) if tot else 1.0
    fig.update_xaxes(title_text=AX_WORKS, range=[0, tmax * 1.18],
                     gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)
    fig.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
    return _base_layout(fig, row_height(len(cats), minimum=260),
                        margin=dict(t=BASE_PX // 2, l=8, r=70, b=BASE_PX))


def _series_offset_width(n: int, k: int, group_span: float, group_fill: float) -> tuple[float, float]:
    """Grouped-bar offset geometry, VERBATIM from an earlier SIRIS
    Streamlit tool.

    `offsetgroup` is BROKEN on the pinned plotly (5.24.1) -- under every
    `barmode` it stacks or overlaps instead of grouping -- so every grouped bar
    is positioned with an EXPLICIT `offset`/`width` under `barmode="overlay"`.
    Do not "simplify" this back to `offsetgroup`."""
    slot = group_span / n
    bar_w = slot * group_fill
    offset = -group_span / 2 + k * slot + (slot - bar_w) / 2
    return offset, bar_w


def fig_breakdown_yearly(
    years: Sequence[str],
    series: Sequence[str],
    labels: Mapping[str, str],
    colors: Mapping[str, str],
    totals: Mapping[str, Sequence[float]],
    *,
    group_span: float = DEFAULT_GROUP_SPAN,
    group_fill: float = DEFAULT_GROUP_FILL,
    y_title: str = AX_WORKS,
) -> go.Figure:
    """RIGHT panel of the pair: category x year GROUPED bars.

    GROUPED, never stacked -- a standing house rule, "a bar chart may never
    stack a second categorical dimension" (a stack would make the year total the
    figure and hide every series' own trajectory, which is the claim here).

    `years` must be STRINGS (a numeric x-axis autoranges and ticks differently
    from every other chart in the app). `series` is the FIXED semantic order
    `palette.OA_DOMAIN_ORDER` for domains, `palette.DOCTYPE_ORDER` for document
    types -- never a data-dependent sort, and a series that is zero across every
    year is KEPT, never dropped, so the reader sees the absence.

    Both panels of the pair render `showlegend=False`: `chip_legend_html` is the
    ONE legend for the two figures."""
    if not all(isinstance(g, str) for g in years):
        raise ValueError("years must be strings")
    if len(series) == 0:
        raise ValueError("series must not be empty")
    missing = [k for k in series if k not in labels or k not in colors or k not in totals]
    if missing:
        raise ValueError(f"series key(s) missing from labels/colors/totals: {missing}")
    n_groups = len(years)
    for k in series:
        if len(totals[k]) != n_groups:
            raise ValueError(f"totals[{k!r}] must have one value per year")

    fig = go.Figure()
    for k, key in enumerate(series):
        offset, bar_w = _series_offset_width(len(series), k, group_span, group_fill)
        vals = [float(v) for v in totals[key]]
        hover = [f"{labels[key]}<br>{AX_YEAR.lower()}{THIN_SPACE}{g}"
                 f"<br>{AX_WORKS.lower()}{THIN_SPACE}{_fmt_vol(v)}"
                 for g, v in zip(years, vals)]
        fig.add_trace(go.Bar(
            x=list(years), y=vals, offset=offset, width=bar_w,
            marker_color=colors[key],
            marker_line_color=P.SURFACE, marker_line_width=HAIRLINE_PX,
            name=labels[key], legendgroup=key,
            customdata=hover, hovertemplate="%{customdata}<extra></extra>",
        ))
    fig.update_layout(barmode="overlay")
    fig.update_xaxes(type="category", gridcolor=P.GRID, linecolor=P.BORDER)
    fig.update_yaxes(title_text=y_title, gridcolor=P.GRID,
                     zerolinecolor=P.GRID, linecolor=P.BORDER)
    fig = _base_layout(fig, SCATTER_HEIGHT - BASE_PX * 2,
                       margin=dict(t=BASE_PX // 2, l=8, r=16, b=BASE_PX))
    fig.update_layout(bargap=0)   # explicit offsets already own the spacing
    # Measured at a narrow viewport: with l=8 the rotated y-axis
    # title clipped to "Publicatio" at 390 px; automargin lets plotly reserve
    # the title's width whatever the viewport.
    fig.update_yaxes(automargin=True, title_standoff=6)
    return fig


# ---------------------------------------------------------------------------
# 7. The shared chip legend -- ONE legend for the breakdown pair
# ---------------------------------------------------------------------------
CHIP_PX = 12
CHIP_RADIUS_PX = 3
CHIP_GAP_PX = 6
CHIP_MARGIN_PX = 14
NO_PX = 0            # a literal zero belongs in an int, never inside a CSS string


def chip_legend_html(items: Sequence[tuple[str, str]]) -> str:
    """HTML chip strip (ported from an earlier SIRIS Streamlit tool's
    chip-legend renderer, de-Streamlit-ed: this
    module returns the markup and `views_find.py` is the only caller that hands
    it to `st.markdown(., unsafe_allow_html=True)`).

    ONE legend serves BOTH figures of the breakdown pair, which is why both are
    built with `showlegend=False`; the strip is rebuilt whenever the segmented
    control swaps the identity family, so a legend never mixes two families
    (palette.py coexistence rule)."""
    def esc(s: str) -> str:
        return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;'
        f'margin-right:{CHIP_MARGIN_PX}px;">'
        f'<span style="width:{CHIP_PX}px;height:{CHIP_PX}px;background:{esc(hexcol)};'
        f'border-radius:{CHIP_RADIUS_PX}px;margin-right:{CHIP_GAP_PX}px;"></span>'
        f'<span style="font-size:{FONT_PX}px;color:{P.INK_SECONDARY};">{esc(label)}</span>'
        f'</span>'
        for label, hexcol in items
    )
    return (f'<div style="display:flex;flex-wrap:wrap;gap:{HAIRLINE_PX}px;'
            f'margin:{CHIP_GAP_PX}px {NO_PX}px;">{chips}</div>')
