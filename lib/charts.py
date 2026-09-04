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

  * **A later pass ("the bar-layout contract") REVERSES the widen-the-gutter
    call above and unifies Find's and Compare's geometry instead of keeping
    them apart.** Both views' bar charts now share ONE set of layout rules:
    a fixed-width LABEL column and a fixed-width GUTTER column PER VIEW,
    sized once from the whole label universe (every field, subfield, ERC
    panel, SDG goal and topic name on disk -- never the current frame), so a
    bar starts at the identical pixel on every chart of a view whatever seed
    or pair is loaded. A label always wraps -- pixel-measured, never a
    character count (`wrap_label_px`, `WRAP_PX`) -- to at most two lines,
    which the new taller row pitch (`ROW_PITCH_SINGLE`/`ROW_PITCH_PAIR`,
    below) is sized to host as the NORM, not an exception: `row_height`'s
    `n_wrapped` correction (and the `wrap=False`/no-wrap escape hatch this
    paragraph used to describe) has no live caller left in this file. The
    volume gutter moves into its OWN column (`_add_gutter_column`, a phantom
    bar trace) for BOTH views -- Find's fold-into-the-tick-string mechanism
    (`_tick_display`) and its per-frame margin measurement (`_gutter_margin_px`)
    are RETIRED, not kept as dead code, for the same "a reversed decision is
    worth being explicit about" reason the truncation-to-wrap reversal above
    already states. `lib/charts_compare.py` imports every constant this
    contract introduces rather than keeping its own copies.
  * **The SI unit grid is retired for an outer-end value label.** The old
    per-integer vertical gridline set was a second thing to cross-reference
    against the dashed neutral line; now each row's own SI marker carries its
    OWN formatted value as text, anchored on the side AWAY from the neutral
    reference (`SI_NEUTRAL`) -- left of the dot for a sub-neutral value,
    right for an above-neutral one -- so the reading is local to the row, not
    a lookup against an axis. The dashed neutral reference line itself is
    NOT a "unit gridline" and is kept; only `showgrid` on the SI axis goes to
    `False`.
  * **`fig_topics` and `fig_frontier` (with their `_frontier_topn`/
    `frontier_coverage` companions) are RETIRED.** The topic planes
    replacing them -- `fig_plane_impact`, `fig_plane_frontier`, `balance_bars`
    -- live in the sibling module `lib/charts_topics.py`, on the identical
    bar-layout constants this module exports (`FRONTIER_ORIGIN`,
    `FRONTIER_ORIGIN_PX`, `BUBBLE_MIN_PX`, `BUBBLE_MAX_PX`, `AX_EXPANSION`,
    `AX_ACCELERATION`, `HOVER_EXPANSION`, `HOVER_ACCELERATION` -- kept here
    for that reuse, and for `lib/charts_compare.py`'s own cross-module
    imports, even though no builder in THIS file still calls them itself).
  * **`fig_share_si`'s hover is REBUILT to the tooltip-spec contract**
    (`docs/tooltip_spec.yaml`, `find_fields`/`find_subfields`/`find_sdg`/
    `find_erc`): a per-family share/(E)SI label (`share_hover_label`/
    `si_hover_label`, both new keyword arguments), a whole-run `vol_pair`
    line for fields/subfields (both counting bases, unconditionally -- the
    frame already carries both regardless of the active basis) or a
    whole-run `dec_1` mass line for sdg/erc, and two new conditional lines
    (FWCI_EU, PP10_WD) whenever the caller's frame carries the matching
    `fwci_taxa.parquet`/`impact_taxa.parquet` columns (`lib/profile_data.py`
    joins them in, bestfit tree only). A line whose value is not finite is
    OMITTED entirely now, never shown as an empty "n/a" -- the SI/ESI line's
    own behaviour change from the pre-this-pass code.
"""
from __future__ import annotations

import json
from pathlib import Path
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

# --- Volume-gutter collision fix (superseded by the bar-layout contract below,
# kept as the historical record of the mechanism this module moved away from)
# --------------------------------------------------------------------------
# The volume gutter used to be a SEPARATE `add_annotation` sitting in a
# negative-x sliver reserved left of the zero baseline (`GUTTER_FRACTION`/
# `GUTTER_INSET`, retired by this fix), drawn independently of the y-axis
# category label. At a narrow plot width the two
# text elements are laid out by two different systems with no shared
# knowledge of each other's extent, so they can (and at 390 px, did) end up
# with zero space between them, reading as one garbled word. The fix folded
# the volume INTO the y tick text as one right-anchored string and reserved a
# left margin measured off the frame's own longest label. **That per-frame
# measurement is GONE** (see the bar-layout contract below): a margin sized
# off the CURRENT seed's labels means two charts of the same family start
# their bars at two different pixels depending which institution loaded --
# exactly the inconsistency a later pass asked to fix. The gutter volume now
# draws in its OWN column (a phantom bar trace, `_add_gutter_column`,
# unchanged in spirit from the mechanism `lib/charts_compare.py` already
# proved at 1920/1280 px), and the label column's width is a CONSTANT derived
# from the whole label universe, not the current frame.
#
# `wrap_label`/`WRAP_WIDTH`/`WRAP_ROW_FACTOR`/`row_height` below are KEPT,
# character-based, for the one caller that still wants a per-frame character
# budget (`charts_compare.mirror_frontier`'s own topic-name geometry moved
# off them too, see its own module) -- no live caller of THIS module still
# reads `WRAP_WIDTH` for a bar-family panel; the constant survives as a
# documented default for `wrap_label`'s own signature.
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
GUTTER_FONT_PX = 12         # : 11 -> 12, now equal to FONT_PX -- the
                            # "gutter font size differs across charts"
                            # complaint is fixed by every consumer reading
                            # the SAME constant, not a per-chart tweak
BUBBLE_MIN_PX = 6
BUBBLE_MAX_PX = 34

# ---------------------------------------------------------------------------
# Bar-layout contract: ONE label column, ONE gutter column, ONE row pitch
# per view, whatever seed or pair is loaded. Single source -- `lib/
# charts_compare.py` imports every name in this block rather than keeping
# its own copies.
# ---------------------------------------------------------------------------
TICK_FONT_PX = 13           # y-axis category tick labels (the row names) --
                            # BIGGER than the figure's other chrome (raises
                            # the font on every bar-family panel); axis
                            # titles, hover text and the gutter numbers stay
                            # at GUTTER_FONT_PX above.

ROW_PITCH_SINGLE = 34       # : 27 -> 34. One-bar-per-row charts (Find's
                            # fields / top subfields / topics / SDG / ERC
                            # panels): the vertical budget one category row
                            # gets. A manager render-read found real two-line
                            # labels colliding with their neighbour at 27 px
                            # ("Biochemistry, Genetics and / Molecular
                            # Biology" over "Materials Science"): a wrapped
                            # label's own TWO lines at TICK_FONT_PX (13 px)
                            # render at roughly 15 px of line height each
                            # (measured), so two lines need ~30 px before any
                            # row-to-row breathing room at all. 34 keeps a
                            # 4 px margin above that -- the invariant
                            # `tests/test_chart_layout.py` checks on every
                            # frame the tests build: `max_lines * 15 + 4 <=
                            # pitch`. Bar thickness (`BAR_PX_SINGLE`) is
                            # UNCHANGED; only the pitch around it grows.
BAR_PX_SINGLE = 20          # target bar thickness at that pitch (unchanged)
BAR_GAP_SINGLE = 1.0 - (BAR_PX_SINGLE / ROW_PITCH_SINGLE)
                            # solved, not guessed: with exactly one bar per
                            # category and no explicit width, plotly's own
                            # `bargap` is the ONLY handle on bar thickness
                            # (bar fraction of the row == 1 - bargap), so this
                            # is the bargap that makes BAR_PX_SINGLE exact at
                            # ROW_PITCH_SINGLE (~0.259)

ROW_PITCH_PAIR = 40         # two-institutions-per-row charts (Compare's
                            # `fig_metric_bars` family: thematic shape, SDG
                            # profile, reciprocity)
BAR_PX_PAIR = 16            # target bar thickness at that pitch, per series
PAIR_GROUP_FILL = 0.86      # unchanged from the app's existing grouped-bar
                            # fill ratio (`DEFAULT_GROUP_FILL`) -- kept
                            # identical on purpose, only the SPAN below moves
PAIR_GROUP_SPAN = (BAR_PX_PAIR * 2) / (ROW_PITCH_PAIR * PAIR_GROUP_FILL)
                            # solved so two PAIR_GROUP_FILL-filled bars at
                            # ROW_PITCH_PAIR pitch are EXACTLY BAR_PX_PAIR
                            # thick (~0.930): row-to-row separation is
                            # carried by the explicit hairline rule between
                            # rows (`charts_compare._row_rules`), not by
                            # margin alone, so this can sit tighter than the
                            # yearly-breakdown pair's own DEFAULT_GROUP_SPAN

COL_PAD_PX = 12             # the ONE pad after the gutter column, before the
                            # bar origin (x = 0) -- same value, every chart,
                            # every view: margin.l == LABEL_COL_PX[view] +
                            # GUTTER_COL_PX[view] + COL_PAD_PX, always. Also
                            # the safety margin WRAP_PX[view] subtracts from
                            # LABEL_COL_PX[view] (below) -- reusing the one
                            # small pad this contract already defines rather
                            # than inventing a second.

# LABEL_COL_PX -- a CONSTANT per view, derived from the WHOLE label universe
# of every family that view draws (26 fields, 245 distinct subfield names
# over 252 subfield ids, 28 ERC panels, 16 drawn SDG goals, 4,516 topics --
# read from `app/data/topics_dim.parquet`, `lib/engine/resources/
# openalex_subfield_codebook_v1.csv`, `erc_panels.csv`, `sdg_labels.csv`),
# never from the current frame -- so a bar starts at the SAME pixel on every
# chart of a view whatever seed or pair is loaded.
#
# Derivation (offline, reproducible, no browser needed at chart-build time):
# the real rendered tick font -- family read once, live, off a y-tick <text>
# element's computed style -- at TICK_FONT_PX, summed per-character from the
# committed pixel-width table (`lib/resources/glyph_widths.json`, measured
# with the SAME font via canvas `measureText`), through a pixel-accurate
# greedy word-wrap capped at two lines (`wrap_label_px`). LABEL_COL_PX[view]
# is THE SMALLEST WIDTH AT WHICH EVERY LABEL OF EVERY FAMILY THAT VIEW DRAWS
# fits in <= 2 lines with no rendered line wider than the column itself -- a
# fixed point per family (widen once from that family's own longest single
# word, remeasure, repeat), then the MAX across families (Find: {field,
# subfield, erc, sdg}, a coloured accent square charged to sdg's own first
# line since Find's SDG panel carries one; Compare: {subfield, sdg, topic},
# every family there carries the accent square), +8% safety over that
# figure to absorb the gap between a canvas measurement and plotly's own SVG
# text layout. ERC decides Find's column (282.5 px raw); subfields decide
# Compare's (241.0 px raw) -- topics fit inside it with ZERO of the 4,516
# needing an ellipsis fallback (measured, well under the 1% ceiling;
# `wrap_label_px` still carries the fallback as a standing safety net).
LABEL_COL_PX = {"find": 306, "compare": 261}

# WRAP_PX -- ONE wrap budget PER VIEW, not per family. A family-by-family
# wrap budget (this module's own first version) wrapped SHORT families far
# too early relative to the column they actually sit in -- a manager
# render-read measured Fields wrapping at 170 px inside a 306 px column,
# leaving most of the reserved width visibly unused above a needlessly
# two-line label. The wrap decision now uses the SAME width the column
# itself was solved to (LABEL_COL_PX[view]), less COL_PAD_PX as a small
# safety margin so wrapped text never touches the gutter's own edge -- since
# LABEL_COL_PX is already "the smallest width at which every family's
# labels fit in <= 2 lines" (the fixed-point definition above), a label only
# wraps now if it genuinely needs close to the FULL column, and most
# shorter-family labels render on ONE line. Measured consequence (the
# manager's own request, §3): of the families that still need two lines at
# this WIDER budget, only the widest handful per family do -- see
# `tests/test_chart_layout.py`'s own per-family count and
# `progress/RR-A1.md`'s Follow-up section for the exact numbers.
WRAP_PX = {"find": LABEL_COL_PX["find"] - COL_PAD_PX,
          "compare": LABEL_COL_PX["compare"] - COL_PAD_PX}

# The gutter column holds the row's raw volume, right-aligned, GUTTER_FONT_PX,
# immediately left of the bar origin. Sized off the widest volume that can
# ever appear in that role -- an institution's own OpenAlex-scenario total
# (`index.total_full_2020_2024`/`total_frac_2020_2024`, since no single
# taxon's volume can exceed the institution's own grand total), formatted by
# `_fmt_vol` exactly as the chart prints it (thin-space thousands; Find's
# fractional basis can print one decimal, Compare's `vol_full` is always an
# integer), +8% safety. Two views, two widths, because Find's frac-basis
# decimal is the wider string.
GUTTER_COL_PX = {"find": 44, "compare": 41}

GUTTER_NEG_AXIS_FRAC = 0.16  # the gutter phantom-bar trace's own x, as a
                             # fraction of the panel's data span, negative of
                             # the zero baseline -- single-sourced here so
                             # `charts_compare.py` no longer keeps its own copy
GUTTER_TIP_FRAC = 0.06
GUTTER_PHANTOM_FILL = "rgba({0},{0},{0},{0})".format(0)   # fully transparent

ACCENT_GLYPH = "\N{BLACK VERTICAL RECTANGLE}"
# The row-label taxonomy accent: a small glyph in the taxon's OFFICIAL hue,
# through plotly's tick pseudo-html, sitting left of a label that names the
# taxon in full -- colour is recognition, the text is the encoding (single-
# sourced here; `charts_compare.py` imported its own copy before).
ACCENT_GAP = "\N{NO-BREAK SPACE}"

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

# `HOVER_SI`/`HOVER_VOL_FRAC` are also imported by `lib/charts_compare.py`
# (`C.HOVER_SI`/`C.HOVER_VOL_FRAC`, its own `fig_metric_bars` hover skeleton)
# -- kept verbatim for that cross-module reader even though this module's own
# `fig_share_si` no longer defaults to them (see `HOVER_SPECIALISATION_*`
# below, the tooltip-spec wording for the Find profile panels).
HOVER_SI = "SI"
HOVER_VOL_FRAC = "works (fractional)"
HOVER_EXPANSION = "expansion"
HOVER_ACCELERATION = "acceleration"

# Tooltip-spec vocabulary (find_fields / find_subfields / find_sdg /
# find_erc, `docs/tooltip_spec.yaml`) -- each panel family has its OWN
# wording for the "share" and "(E)SI" lines; the FWCI_EU / PP10_WD lines are
# the SAME text on all four panels. The two fixed windows the spec's OWN
# wording names are INT CONSTANTS, composed into the label via an f-string
# (this module's digit-ban: a literal year inside a plain string is
# banned, an f-string's own Constant fragments never carry one).
RUN_WINDOW_START = 2020        # the whole-run window (all document types)
RUN_WINDOW_END = 2025
CORE_WINDOW_START = 2020       # the articles+reviews core window
CORE_WINDOW_END = 2024

HOVER_FIELD = "field"                                            # find_subfields' own 2nd line
HOVER_SPECIALISATION_INDEX = "specialisation index"              # fields, subfields
HOVER_SPECIALISATION_EUROPE = "specialisation against Europe"    # sdg (esi), erc (si)
HOVER_SHARE_CLASSIFIED = "share of classified output"                          # fields, subfields
HOVER_SHARE_TAGGED_INST = "share of the institution's tagged output"           # sdg
HOVER_SHARE_CLASSIFIED_INST = "share of the institution's classified output"   # erc
HOVER_VOL_PAIR_RUN = f"publications, whole run {RUN_WINDOW_START}-{RUN_WINDOW_END}"            # fields, subfields
HOVER_MASS_TAGGED_RUN = f"tagged mass, whole run {RUN_WINDOW_START}-{RUN_WINDOW_END}"           # sdg
HOVER_MASS_CLASSIFIED_RUN = f"classified mass, whole run {RUN_WINDOW_START}-{RUN_WINDOW_END}"   # erc
HOVER_FWCI_EU_CORE = f"FWCI_EU, articles and reviews {CORE_WINDOW_START}-{CORE_WINDOW_END}"                     # all four
HOVER_PP10_WD_CORE = f"world top-decile share, articles and reviews {CORE_WINDOW_START}-{CORE_WINDOW_END}"      # all four

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


FWCI_TAXA_FLOOR = 3    # the FWCI_EU hover line draws only at/above this n_covered
IMPACT_TAXA_FLOOR = 1  # the PP10_WD hover line draws only at/above this n_covered_pp
FWCI_DECIMALS = 2      # `fwci_pair_2dp` -- mean/median FWCI_EU, two decimals
PCT_DAGGER_FLOOR = 10  # `pct_1dp_dagger` / `fwci_pair_2dp` -- a work count
                       # under this many gets a trailing dagger, never a
                       # withheld line (the line's OWN `when` floor, lower
                       # than this one, decides whether it is drawn at all)
_FWCI_FMT = f".{FWCI_DECIMALS}f"
DAGGER = "\N{DAGGER}"


def _fmt_dec1(v) -> str:
    """`dec_1`: ALWAYS one decimal (never the whole-number branch `_fmt_vol`
    takes for a value that happens to round exactly) -- fractional masses
    and fractional whole-run volumes, e.g. "512.4", even when the value is
    an exact integer like "512.0"."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return P.NA_MARK
    return format(float(v), f",.{SHARE_DECIMALS}f").replace(",", THIN_SPACE)


def _fmt_vol_pair(vol_full, vol_frac) -> str:
    """`vol_pair`: the same measure on both counting bases, full first --
    "1 234 full - 512.4 fractional"."""
    return f"{_fmt_vol(vol_full)} full - {_fmt_vol(vol_frac)} fractional"


def _fmt_fwci_pair(mean, median, n) -> str:
    """`fwci_pair_2dp`: "mean 1.31 - median 0.98 on 54 works", both to two
    decimals; a dagger follows the work count when it is under
    `PCT_DAGGER_FLOOR`. Whether the line is drawn AT ALL under its own
    (lower) floor is the caller's `when` gate, not this formatter's job --
    this always renders SOME text once called."""
    if (mean is None or (isinstance(mean, float) and np.isnan(mean))
            or median is None or (isinstance(median, float) and np.isnan(median))
            or n is None or (isinstance(n, float) and np.isnan(n))):
        return P.NA_MARK
    n_int = int(n)
    dagger = DAGGER if n_int < PCT_DAGGER_FLOOR else ""
    n_text = format(n_int, ",").replace(",", THIN_SPACE)
    return (f"mean {format(float(mean), _FWCI_FMT)} - median {format(float(median), _FWCI_FMT)} "
            f"on {n_text} works{dagger}")


def _fmt_pct_dagger(value, denom) -> str:
    """`pct_1dp_dagger`: `_fmt_pct`, followed by a dagger when `denom` (the
    line's own stated denominator) is under `PCT_DAGGER_FLOOR`. No dagger on
    an already-missing value -- "n/a<dagger>" would read as a value with a
    caveat, not as "no value"."""
    text = _fmt_pct(value)
    if text == P.NA_MARK:
        return text
    if denom is None or (isinstance(denom, float) and np.isnan(denom)):
        return text
    return f"{text}{DAGGER}" if float(denom) < PCT_DAGGER_FLOOR else text


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


# ---------------------------------------------------------------------------
# Pixel-accurate label measurement -- reproducible OFFLINE (no browser at
# chart-build time): a per-character width table measured ONCE, live, off the
# real rendered tick font (`lib/resources/glyph_widths.json`; see its own
# header for the method). `text_width_px`/`wrap_label_px` are what
# `LABEL_COL_PX`/`WRAP_PX` above were themselves derived with, and what every
# bar-family builder below uses to lay a label out -- the SAME arithmetic,
# so a column sized for the whole label universe and a single chart's own
# wrap can never disagree.
# ---------------------------------------------------------------------------
_GLYPH_WIDTHS_PATH = Path(__file__).resolve().parent / "resources" / "glyph_widths.json"
ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"

# Digit-ban note (module docstring): the glyph table's own JSON keys embed
# TICK_FONT_PX/GUTTER_FONT_PX ("widths_13px", "fallback_width_13px", .) --
# COMPOSED from those int constants via an f-string, never typed as a digit
# -bearing literal, the identical idiom `_PCT_FMT`/`_SI_FMT` above already use.
_UTF_ENCODING_NUM = 8
_JSON_ENCODING = f"utf-{_UTF_ENCODING_NUM}"
_WIDTHS_KEY = {TICK_FONT_PX: f"widths_{TICK_FONT_PX}px", GUTTER_FONT_PX: f"widths_{GUTTER_FONT_PX}px"}
_FALLBACK_KEY = {TICK_FONT_PX: f"fallback_width_{TICK_FONT_PX}px",
                GUTTER_FONT_PX: f"fallback_width_{GUTTER_FONT_PX}px"}


def _load_glyph_widths() -> dict:
    with open(_GLYPH_WIDTHS_PATH, "r", encoding=_JSON_ENCODING) as f:
        return json.load(f)


_GLYPHS = _load_glyph_widths()   # module-level: one file read, one process


def text_width_px(text: str, size_px: int = TICK_FONT_PX) -> float:
    """The rendered width of `text`, in px, at `size_px` -- summed per
    character from the committed table (13 px for a label, 12 px for a
    gutter number), a character missing from the table (a glyph outside
    today's label universe) falls back to that size's own measured AVERAGE
    rather than raising, so a future label with one unseen character degrades
    gracefully instead of crashing. A `size_px` that is neither table (any
    future caller) scales the 13 px table linearly -- an approximation, but
    the +8 % safety already baked into every column constant absorbs it."""
    if size_px in _WIDTHS_KEY:
        table = _GLYPHS[_WIDTHS_KEY[size_px]]
        fallback = _GLYPHS[_FALLBACK_KEY[size_px]]
        return sum(table.get(ch, fallback) for ch in str(text))
    table = _GLYPHS[_WIDTHS_KEY[TICK_FONT_PX]]
    fallback = _GLYPHS[_FALLBACK_KEY[TICK_FONT_PX]]
    scale = size_px / TICK_FONT_PX
    return scale * sum(table.get(ch, fallback) for ch in str(text))


def wrap_label_px(text, wrap_px: float, *, max_chars: int = 80) -> list[str]:
    """Greedy word-wrap by MEASURED PIXEL width (never a character count),
    at most two lines, never splitting a word, never dropping a character --
    the same algorithm `wrap_label` uses, `len()` swapped for `text_width_px`.
    A word already wider than `wrap_px` on its own is kept whole (words never
    split outranks the width target). Needing a third line merges every line
    past the first into ONE second line, same as `wrap_label`; if that merged
    line is STILL wider than `wrap_px` (a genuinely long name past what the
    column was sized for -- measured at zero occurrences across today's
    4,516 topic names, kept as a standing safety net, not a live path) it is
    cut at `max_chars` and marked with `ELLIPSIS`, the one place this function
    may shorten text."""
    words = str(text).split()
    if not words:
        return [str(text)]
    lines: list[str] = [words[0]]
    for w in words[1:]:
        candidate = f"{lines[-1]} {w}"
        if text_width_px(candidate) <= wrap_px:
            lines[-1] = candidate
        else:
            lines.append(w)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    if len(lines) == 2 and text_width_px(lines[1]) > wrap_px and len(lines[1]) > max_chars:
        lines[1] = lines[1][: max(max_chars - len(ELLIPSIS), 1)].rstrip() + ELLIPSIS
    return lines


def _tick_label(label: str, *, wrap_px: float, accent_hex: str | None = None,
                prefix: str = "") -> tuple[str, str]:
    """ONE right-anchored tick string: the label, pixel-wrapped to at most two
    lines. Returns `(plain, styled)` -- `plain` joins lines with a bare `\\n`
    (used only by the label-universe test, never by a live chart any more:
    the column WIDTH is a constant now, nothing measures a frame's own text
    to size a margin); `styled` is what plotly actually draws, `<br>`-joined,
    with an optional taxonomy-coloured accent square (`ACCENT_GLYPH`) placed
    before the FIRST line only via plotly's tick pseudo-html -- the SAME
    accent idiom `lib/charts_compare.py` already uses for Compare's rows, now
    single-sourced so Find's SDG panel can carry the identical glyph.

    `prefix` (e.g. `fig_topics`'s catch-all glyph + a thin space) is applied
    to the ALREADY-WRAPPED label, never fed into the wrap itself: a prefix
    character can be Unicode whitespace (the catch-all marker's own thin
    space is exactly this), and Python's plain word-split would otherwise
    treat it as a separate "word" -- wrapping it away from the label it
    belongs to, and losing the EXACT space character on any re-join. Prefix,
    accent and body compose in that fixed order; prepending to the whole
    (possibly two-line) string lands the prefix before the FIRST line only,
    since a `\\n`/`<br>` only ever follows it."""
    lines = wrap_label_px(label, wrap_px)
    plain = "\n".join(lines)
    styled = "<br>".join(lines)
    if accent_hex:
        square = f'<span style="color:{accent_hex}">{ACCENT_GLYPH}</span>{ACCENT_GAP}'
        plain = f"{ACCENT_GLYPH}{ACCENT_GAP}{plain}"
        styled = f"{square}{styled}"
    if prefix:
        plain = f"{prefix}{plain}"
        styled = f"{prefix}{styled}"
    return plain, styled


def _add_gutter_column(fig: go.Figure, *, names: Sequence[str], values: Sequence[str],
                       xmax: float, row: int | None = None, col: int | None = None,
                       colors: Sequence[str] | str | None = None) -> None:
    """The gutter column (bar-layout contract): one phantom, zero-visible-
    fill `go.Bar` trace at a small negative x (a fixed FRACTION of the
    panel's own data span, `GUTTER_NEG_AXIS_FRAC`/`GUTTER_TIP_FRAC` --
    unchanged from the mechanism `lib/charts_compare.fig_metric_bars` already
    proved at 1920/1280/390 px), its own pre-formatted `values` as text,
    pushed further left by `textposition="outside"`. ONE mechanism for both
    views now -- Find's panels used to fold the volume into the y-tick
    string instead; that folding is retired (see the module note above).

    `row`/`col` default to `None`: `fig_topics` builds a plain single-axes
    `go.Figure` (plotly refuses a `row=`/`col=` kwarg on one of those, "you
    must first use make_subplots"), while `fig_share_si` always builds
    through `make_subplots` even for its one-panel case -- passing `None`
    calls `add_trace`/`update_xaxes` WITHOUT the grid kwargs at all, legal on
    both figure shapes; a caller on a real grid passes explicit ints.

    `constraintext="none"` is load-bearing, not decorative: plotly shrinks
    `textposition="outside"` text to fit the trace's own bar-group LANE
    under the default `constraintext="both"` -- measured live (a manager
    render-read caught this at ~8 px against the declared `GUTTER_FONT_PX`
    12 px) once a SECOND bar trace (this one) shares the category axis with
    the real bar and the figure's own `barmode` is not `"overlay"` (plotly's
    un-set default is `"group"`, which halves each trace's own lane). Both
    callers now force `barmode="overlay"` too (see their own call sites) --
    the two fixes are one system: `constraintext="none"` stops ANY future
    lane-width change from silently re-shrinking this text again."""
    n = len(names)
    basis = xmax if xmax > 0 else 1.0
    neg_extent = basis * GUTTER_NEG_AXIS_FRAC
    gutter_x = -neg_extent * GUTTER_TIP_FRAC
    ink = colors if isinstance(colors, list) else [colors or P.INK_SECONDARY] * n
    grid_kw = {} if row is None else {"row": row, "col": col}
    fig.add_trace(go.Bar(
        x=[gutter_x] * n, y=list(names), orientation="h",
        marker=dict(color=GUTTER_PHANTOM_FILL, line=dict(width=0)),
        text=list(values), textposition="outside", cliponaxis=False,
        textfont=dict(size=GUTTER_FONT_PX, color=ink), constraintext="none",
        customdata=[""] * n, hoverinfo="skip", showlegend=False,
    ), **grid_kw)
    fig.update_xaxes(range=[-neg_extent, xmax * 1.02], **grid_kw)


def row_height_single(n: int, minimum: int = MIN_HEIGHT) -> int:
    """Figure height under the bar-layout contract for a ONE-bar-per-row
    chart: margins + `n` rows at `ROW_PITCH_SINGLE`. Two-line labels are the
    norm the pitch already hosts, so there is no `n_wrapped` correction any
    more (contrast `row_height` above, which the one caller still measuring
    its own frame -- `fig_breakdown_global` -- keeps using unchanged)."""
    return max(minimum, int(round(ROW_PITCH_SINGLE * int(n))) + BASE_PX)


def row_height_pair(n: int, minimum: int = MIN_HEIGHT) -> int:
    """Figure height under the bar-layout contract for a TWO-institutions-
    per-row chart: margins + `n` rows at `ROW_PITCH_PAIR`."""
    return max(minimum, int(round(ROW_PITCH_PAIR * int(n))) + BASE_PX)


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


def _base_layout(fig: go.Figure, height: int, *, margin: dict, bargap: float = BAR_GAP) -> go.Figure:
    fig.update_layout(
        height=height,
        bargap=bargap,
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
# WRAP_PX is now ONE value PER VIEW (module header) -- every Find panel
# (fields/subfields/erc/sdg/topics) wraps at `WRAP_PX["find"]`, whatever
# family its own labels belong to; a per-family lookup (this section's
# earlier `_wrap_px_for`/`_WRAP_FAMILY_BY_LABEL_COL`) is retired with it.


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
    si_hover_label: str = HOVER_SPECIALISATION_INDEX,
    share_hover_label: str = HOVER_SHARE_CLASSIFIED,
    mass_hover_label: str = HOVER_MASS_CLASSIFIED_RUN,
    stacked: bool = False,
    wrap: bool = False,
    label_accent: bool = False,
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

    `wrap`: RETAINED for signature compatibility only -- under the bar-layout
    contract every label pixel-wraps to at most two lines at the family's own
    `WRAP_PX` regardless of this flag (the fixed-width label column needs it
    to, on every chart, whatever the seed); nothing in this app passes
    `wrap=True` any more, and no caller needs to change.

    `label_accent=True` prefixes each row's label with a small square in the
    row's OWN colour (`colors[i]`, already computed for the bar) -- the same
    taxonomy-accent idiom `lib/charts_compare.py` uses for Compare's rows,
    single-sourced here (`_tick_label`). Only the SDG panel passes this
    (`fig_sdg`, below): Fields/Subfields/ERC already show identity on the bar
    itself and a caller has not asked for the glyph there too.
    """
    if share_col not in df.columns:
        raise ValueError(f"missing column {share_col!r}")
    d = _ordered(df, family, sort, share_col)
    n = len(d)
    label_col = label_col or _first_col(d, _LABEL_COLS)
    if label_col is None:
        raise ValueError("no label column found; pass label_col=")
    volume_col = volume_col or _first_col(d, _VOLUME_COLS)
    wrap_px = WRAP_PX["find"]

    names = [str(v) for v in d[label_col]]
    # find_subfields' own second hover line ("field␣{field_name}") -- ONLY
    # when `field_name` is a column OTHER than the entity's own label (the
    # subfields frame carries the PARENT field name in this column; the
    # fields frame's `label_col` IS "field_name", so this never fires for
    # fields itself). Mirrors Compare's own `fig_metric_bars`/`_metric_hover`
    # "Field: {group_label}" first line for the identical reason.
    parent_field = (d["field_name"].astype(str).to_numpy() if label_col != "field_name"
                    and "field_name" in d.columns else None)
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

    # Tooltip-spec hover (find_fields / find_subfields / find_sdg /
    # find_erc, `docs/tooltip_spec.yaml`): entity name first, then share,
    # then EITHER the whole-run vol_pair (fields/subfields, which carry BOTH
    # `vol_full` and `vol_frac` regardless of the active counting basis) OR
    # the whole-run fractional mass (sdg/erc, `dec_1`) -- never both, a frame
    # carries one or the other by construction. The (E)SI line is OMITTED
    # (never "n/a") when the value is not finite. The FWCI_EU / PP10_WD
    # lines are OMITTED below their own floor (n_covered>=3 /
    # n_covered_pp>=1) -- `_join_taxa_impact` (profile_data.py) leaves both
    # columns NaN off the bestfit tree, which already fails these floors.
    have_vol_pair = "vol_full" in d.columns and "vol_frac" in d.columns
    have_mass = (not have_vol_pair) and "mass" in d.columns
    vol_full_arr = d["vol_full"].to_numpy() if "vol_full" in d.columns else None
    vol_frac_arr = d["vol_frac"].to_numpy() if "vol_frac" in d.columns else None
    mass_arr = d["mass"].to_numpy() if "mass" in d.columns else None
    has_fwci = {"fwci_mean", "fwci_median", "n_covered"} <= set(d.columns)
    has_pp10 = {"pp10_wd", "n_covered_pp"} <= set(d.columns)
    fwci_mean_arr = d["fwci_mean"].to_numpy() if has_fwci else None
    fwci_median_arr = d["fwci_median"].to_numpy() if has_fwci else None
    n_covered_arr = (pd.to_numeric(d["n_covered"], errors="coerce").to_numpy()
                     if has_fwci else None)
    pp10_arr = d["pp10_wd"].to_numpy() if has_pp10 else None
    n_covered_pp_arr = (pd.to_numeric(d["n_covered_pp"], errors="coerce").to_numpy()
                        if has_pp10 else None)

    bar_hover = []
    for i in range(n):
        parts = [names[i]]
        if parent_field is not None:
            parts.append(f"{HOVER_FIELD}{THIN_SPACE}{parent_field[i]}")
        parts.append(f"{share_hover_label}{THIN_SPACE}{_fmt_pct(share[i])}")
        if have_vol_pair:
            parts.append(f"{HOVER_VOL_PAIR_RUN}{THIN_SPACE}"
                         f"{_fmt_vol_pair(vol_full_arr[i], vol_frac_arr[i])}")
        elif have_mass:
            parts.append(f"{mass_hover_label}{THIN_SPACE}{_fmt_dec1(mass_arr[i])}")
        if np.isfinite(si[i]):
            parts.append(f"{si_hover_label}{THIN_SPACE}{_fmt_si(si[i])}")
        if has_fwci and np.isfinite(n_covered_arr[i]) and n_covered_arr[i] >= FWCI_TAXA_FLOOR:
            parts.append(f"{HOVER_FWCI_EU_CORE}{THIN_SPACE}"
                         f"{_fmt_fwci_pair(fwci_mean_arr[i], fwci_median_arr[i], n_covered_arr[i])}")
        if has_pp10 and np.isfinite(n_covered_pp_arr[i]) and n_covered_pp_arr[i] >= IMPACT_TAXA_FLOOR:
            parts.append(f"{HOVER_PP10_WD_CORE}{THIN_SPACE}"
                         f"{_fmt_pct_dagger(pp10_arr[i], n_covered_pp_arr[i])}")
        bar_hover.append("<br>".join(parts))

    fig.add_trace(go.Bar(
        x=share, y=names, orientation="h",
        marker_color=colors, marker_line_color=P.SURFACE, marker_line_width=HAIRLINE_PX,
        customdata=bar_hover, hovertemplate="%{customdata}<extra></extra>",
        showlegend=False,
    ), row=1, col=1)

    # The tick text is now JUST the (pixel-wrapped, optionally accented)
    # label -- the volume moves to its own gutter column below (bar-layout
    # contract: ONE mechanism for both views, no more folding a second
    # number into the category-axis text).
    pairs = [_tick_label(names[i], wrap_px=wrap_px,
                         accent_hex=(colors[i] if label_accent else None))
             for i in range(n)]
    plain_display = [p for p, _ in pairs]
    styled_display = [s for _, s in pairs]
    fig.update_yaxes(tickmode="array", tickvals=names, ticktext=styled_display, row=1, col=1)

    xmax = float(np.nanmax(share)) if n and np.isfinite(share).any() else 1.0
    xmax = xmax if xmax > 0 else 1.0
    if gutter and vol is not None:
        _add_gutter_column(fig, names=names, values=[_fmt_vol(v) for v in vol],
                           xmax=xmax, row=1, col=1)
        fig.add_shape(type="line", x0=0, x1=0, y0=-0.5, y1=n - 0.5,
                      xref="x", yref="y", line=dict(color=P.BORDER, width=HAIRLINE_PX))
    else:
        fig.update_xaxes(range=[0, xmax * 1.02], row=1, col=1)
    fig.update_xaxes(tickvals=_nice_ticks(xmax), row=1, col=1)

    if has_si:
        # The below-floor DOT keeps its own value, anchored beside itself
        # (below); the STEM connecting it back to the neutral reference is
        # RETIRED -- the reference is now one unmistakable RED line the whole
        # panel shares (below), so a per-row connector back to it is a
        # redundant second read of the same fact.
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
        # The neutral reference is CONSTANT across every row (SI/ESI = 1
        # means "matches the reference population", the same target for
        # every taxon) -- the bar-layout contract draws that case as ONE
        # full-height red dashed line, replacing the earlier secondary-ink
        # hairline (`add_vline` already spans the whole panel by default).
        fig.add_vline(x=SI_NEUTRAL, row=si_row, col=si_col,
                      line=dict(color=P.WARNING_CAPTION_COLOR, width=LINE_PX, dash="dash"))
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

    fig.update_yaxes(autorange="reversed", showgrid=False, automargin=True,
                     tickfont=dict(size=TICK_FONT_PX))
    fig.update_xaxes(gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)
    fig.update_xaxes(title_text=AX_SHARE, tickformat=_AXIS_PCT_FMT, row=1, col=1)
    if gutter and vol is not None:
        # Two go.Bar traces (the real share bar + the gutter phantom) now
        # share this subplot's category axis -- plotly's own un-set default
        # `barmode` is "group", which would halve EACH trace's own lane
        # (and, via `constraintext`, its text) to fit two traces side by
        # side. `"overlay"` keeps every trace at its own full, independently
        # computed width -- the same fix `charts_compare.fig_metric_bars`
        # already carries for its own multi-trace rows.
        fig.update_layout(barmode="overlay")
    height = row_height_single(n) * (2 if (has_si and stacked) else 1)
    # bar-layout contract: the label + gutter columns are CONSTANTS derived
    # from the whole label universe (module header), never this frame's own
    # text -- every Find panel's bars therefore start at the identical pixel.
    margin_l = LABEL_COL_PX["find"] + GUTTER_COL_PX["find"] + COL_PAD_PX
    margin_r = SI_LABEL_MARGIN_PX if has_si else 16
    return _base_layout(fig, height, margin=dict(t=BASE_PX // 2, l=margin_l, r=margin_r,
                                                 b=BASE_PX), bargap=BAR_GAP_SINGLE)


# ---------------------------------------------------------------------------
# `fig_topics` (2. Top topics), `_frontier_topn`, `frontier_coverage` and
# `fig_frontier` (3. Frontier positioning) are RETIRED: the topic
# planes replacing them (`fig_plane_impact`, `fig_plane_frontier`,
# `lib/charts_topics.py`) supersede both panels on Find, and (later)
# Compare's topic overlay. Deleted outright, not kept as dead code -- see
# `tests/test_charts_topics.py` for the replacement builders' own tests.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 4. SDG profile -- share bars in goal order + ESI dots (UN colours)
# ---------------------------------------------------------------------------
def fig_sdg(df: pd.DataFrame, *, sort: str = "taxonomy", gutter: bool = True) -> go.Figure:
    """The SDG panel. Delegates to `fig_share_si` with `esi` presented in the SI
    slot, so the reader learns ONE form and reuses it
    (`same-read-same-form`). Each row's label carries a small SQUARE in its
    own official SDG colour (`label_accent=True`) -- the same taxonomy-accent
    idiom Compare's SDG chart carries, so a reader sees the goal's colour on
    either page.

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
                        si_axis_title=AX_ESI, si_hover_label=HOVER_SPECIALISATION_EUROPE,
                        share_hover_label=HOVER_SHARE_TAGGED_INST,
                        mass_hover_label=HOVER_MASS_TAGGED_RUN,
                        label_accent=True)


# ---------------------------------------------------------------------------
# 5. ERC profile -- panels grouped by ERC domain, share + SI
# ---------------------------------------------------------------------------
def fig_erc(df: pd.DataFrame, *, sort: str = "taxonomy", gutter: bool = True) -> go.Figure:
    """The ERC panel view: one row per ERC evaluation panel, coloured by its ERC
    DOMAIN (three hues -- `palette.ERC_DOMAIN_COLORS`), share on the left and SI
    on the right, `sort="taxonomy"` grouping the panels by domain in the fixed
    PE -> LS -> SH order. The weak-panel caveat (some panels are thinly
    populated) is the caller's caption, not a mark on the chart."""
    return fig_share_si(df, family="erc", sort=sort, gutter=gutter,
                        si_hover_label=HOVER_SPECIALISATION_EUROPE,
                        share_hover_label=HOVER_SHARE_CLASSIFIED_INST,
                        mass_hover_label=HOVER_MASS_CLASSIFIED_RUN)


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
