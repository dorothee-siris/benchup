"""BenchUp -- pure Plotly figure builders for the Compare page.

Same house rules as `lib/charts.py`, enforced by the same kind of test
(`tests/test_charts_compare.py`): NO Streamlit import, NO `#RRGGBB` literal
anywhere in this file (every hue comes from `lib.palette`), NO digit inside a
STRING LITERAL other than a deployed parquet column name (`tests/
digit_allowlist.txt`, shared with the narrative digit-ban) -- a docstring is
exempt (prose for the reader of the source, never text the app renders).
`lib/views_compare.py` is the only place a figure built
here reaches a page; nothing in this module imports it.

WHAT V4 KEEPS FROM THE OLD COMPARE DESIGN, AND WHY
-------------------------------------------------------------------
's D2-D7 replace the old six-institution dot-mirror / metric-
selector / pooled-scatter Compare page with a fixed TWO-institution page
(D1: exactly two search slots) built from four sections: Thematic
shape (D3), SDG profile (D4), Shared frontier (D5), The relationship (D7).
Every one of those sections is now drawn with the SAME bar-family chrome
(`design-system/CHROME_CONTRACT.md` SS10 -- gutter column, solid institution-
coloured bars, red-dagger caution, diamond reference) already measured and
ratified as the one direction to converge the whole app on. `fig_metric_bars` -- that ratified primitive -- is KEPT, trimmed to the
two metrics D3/D4 actually need (`share`, `pp`; the old Dynamics/SDG-tagged/
Specialisation/Volume/FWCI metric-selector tabs are retired along with the
selector UI they served). `two_tab_bars` and `reciprocity_bars` below are
thin adapters onto it -- no new bar-drawing code, per the ponytail brief.

`legend_strip` / `map_legend_strip` / `chart_note` / `basis_caption` /
`best_value_dot` are also kept: page-level presentation primitives, not
builders, still exactly what needs for the fold-and-caption pattern
CHROME_CONTRACT.md SS0/SS6 name as the app's one convention to converge on.

WHAT IS DELETED, AND WHY
-----------------------------------------------------------------
The pooled frontier scatter and its "who holds the shared frontier" diverging
bar (`fig_frontier_map`, `fig_diverging_shared`) are gone -- D5 replaces both
with the mirror chart below. The dot-mirror family (`fig_mirror_dots`,
`fig_quadrant_mix`, the whole lane-dodge mechanism) is gone -- D3/D4 draw
bars, not dots, for shape/SDG. The frontier overlay/small-multiples scatters
(`fig_frontier_overlay`, `fig_frontier_small_multiples`) are gone -- ERC
panels and the pooled/per-institution frontier scatter are both out of scope
("Out of scope: ERC panels anywhere; pooled frontier scatter"). The impact
dot-interval builders (`fig_impact_intervals`, `fig_impact_subfields`) are
gone -- "Out of scope: Impact-by-subfield interval section"; D3's Impact tab
covers this ground as a `two_tab_bars` call instead. `fig_pulse` (joint
publications per year, one undifferentiated series) is gone -- D7 replaces it
with `yearly_domain_stack`, the same figure stacked by OpenAlex domain.
`RATIO_HATCH_METRICS`'s bar-pattern-fill remnants (`LOW_VOLUME_PATTERN_SHAPE`/
`LOW_VOLUME_PATTERN_SOLIDITY`) lost their one remaining caller (`fig_pulse`)
and are deleted with it -- the hatch-fill mechanism was already retired from
every OTHER bar in this module, so no hatch remnant survives anywhere in the
file now. Grep proof for every deletion above is pasted in `progress/C2.md`.

THE FOUR BUILDERS THIS STREAM ADDS
-----------------------------------
  1. `two_tab_bars` -- the Thematic-shape (D3) and SDG-profile (D4) charts.
                         A thin `fig_metric_bars` adapter: tab="profile" is
                         metric="share", tab="impact" is metric="pp".
  2. `mirror_frontier` -- the shared-frontier mirror (D5): A-only left of a
                         common centre, JOINT centred in `palette.
                         SHARED_FRONTIER` with the white halo, B-only right.
                         Genuinely new geometry (floating three-segment
                         `go.Bar`s via `base=`), not offered by any kept
                         primitive.
  3. `yearly_domain_stack` -- the relationship's yearly stack (D7): joint
                         publications 2020-2024 by OpenAlex domain.
  4. `reciprocity_bars` -- "strategic reciprocity by field" (D7), ADAPTED
                         from 's `views_collab._reciprocity_chart` +
                         `collab_data.reciprocity_frame` (credited in its own
                         docstring): the original was a bubble SCATTER (x =
                         field's share of B's own corpus, y = the same for A,
                         area = joint volume, colour = OA domain). V4 redraws
                         the same two numbers per field as INSTITUTION-
                         coloured `fig_metric_bars` bars (consistent with the
                         rest of this file's convergence onto the bar
                         family), keeping the domain as a label ACCENT glyph rather than the mark
                         colour, and the joint volume as the gutter column.

`colors`, everywhere in this module (`two_tab_bars`, `reciprocity_bars`,
`mirror_frontier`), is the institution SLOT mapping/sequence -- i.e. exactly
what the app's institution-slot map returns (`{institution_id: slot}` for
the two Mapping-shaped builders; `[slot_a, slot_b]` for `mirror_frontier`,
whose frame carries no `institution_id` column at all to key a Mapping by).
It is named `colors` rather than `slots` because that is ALL a slot ever is
in this module -- an index `palette.institution_color`/`institution_ink`
resolve to a hex -- and every one of the four builders' docstrings repeats
this so a caller never has to cross-reference this paragraph.
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lib import charts as C
from lib import palette as P

# ---------------------------------------------------------------------------
# Small pure helpers shared by every builder below
# ---------------------------------------------------------------------------
def _slot_of(slots: Mapping, iid) -> int:
    try:
        return int(slots[iid])
    except (KeyError, TypeError, ValueError):
        return len(P.INSTITUTION_COLORS)   # -> COMPARISON grey, never a cycle


def _name_of(names: Mapping | Sequence | None, iid, *, index: int | None = None) -> str:
    """`names` is usually a Mapping keyed by institution id; `mirror_frontier`
    also accepts a two-item Sequence (`[name_a, name_b]`, no id to key by)
    `index` picks the positional entry in that case."""
    if names is None:
        return str(iid)
    if isinstance(names, Mapping):
        return str(names[iid]) if iid in names else str(iid)
    if index is not None:
        try:
            return str(names[index])
        except (IndexError, TypeError):
            return str(iid)
    return str(iid)


def _ordered_ids(df: pd.DataFrame, slots: Mapping) -> list:
    """The compared institutions in SLOT order -- the one order every figure
    and legend in this module uses, so a colour always sits in the same
    position across a page."""
    ids = list(dict.fromkeys(df["institution_id"].tolist()))
    return sorted(ids, key=lambda i: (_slot_of(slots, i), str(i)))


def _first_col(df: pd.DataFrame, candidates: Sequence[str]) -> str | None:
    return C._first_col(df, candidates)


def _num(v) -> float:
    """Anything -> a PYTHON float (NaN when it will not convert). The
    formatters below test `isinstance(v, float)` for "missing", and
    `np.float32('nan')` is not an instance of `float` -- everything this
    module hands to a formatter goes through here first."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f


def _fmt_pct(v) -> str:
    return C._fmt_pct(_num(v))


def _fmt_si(v) -> str:
    return C._fmt_si(_num(v))


def _fmt_vol(v) -> str:
    return C._fmt_vol(_num(v))


def _fmt_frontier(v) -> str:
    return C._fmt_frontier(_num(v))


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _y_axis(fig: go.Figure, n_rows: int, ticktext: Sequence[str], **kw) -> None:
    fig.update_yaxes(tickmode="array", tickvals=list(range(n_rows)),
                     ticktext=list(ticktext), range=[n_rows - 0.5, -0.5],
                     showgrid=False, automargin=True, **kw)


def _row_rules(fig: go.Figure, n_rows: int, boundaries: Sequence[int] = ()) -> None:
    """A hairline BETWEEN two rows -- confirms the row order without a second
    ink family. `boundaries` names the row indices after which a
    taxonomy DOMAIN ends; those get one step heavier and darker (GRID/
    `DOMAIN_RULE_PX` rather than BORDER/`ROW_RULE_PX`)."""
    edges = set(int(b) for b in boundaries)
    for i in range(n_rows - 1):
        domain_edge = i in edges
        fig.add_shape(type="line", x0=0, x1=1, xref="x domain",
                      y0=i + 0.5, y1=i + 0.5,
                      line=dict(color=P.GRID if domain_edge else P.BORDER,
                                width=DOMAIN_RULE_PX if domain_edge else ROW_RULE_PX),
                      layer="below")


def _bold_axes(fig: go.Figure, *, x: float = C.FRONTIER_ORIGIN,
               y: float | None = C.FRONTIER_ORIGIN) -> None:
    """The bold black origin line(s) -- the figure's own frame of reference,
    the one line allowed to out-weigh the grid."""
    fig.add_vline(x=x, line=dict(color=P.INK, width=BOLD_AXIS_PX))
    if y is not None:
        fig.add_hline(y=y, line=dict(color=P.INK, width=BOLD_AXIS_PX))


# ---------------------------------------------------------------------------
# Geometry + vocabulary constants. Ints/floats only in code; every string
# below is either digit-free or a `{placeholder}`-carrying sentence (the
# digit-ban's own exemption).
# ---------------------------------------------------------------------------
ROW_RULE_PX = 1              # hairline between two category rows
DOMAIN_RULE_PX = 2            # the separator BETWEEN two taxonomy domains
BOLD_AXIS_PX = 2              # the bold black 0/0 axis rule
AXIS_PAD_FRAC = 0.20          # x-range headroom so an outer-end label never
                              # collides with the plot frame (measured need)
NOTE_MAX_CHARS = 160          # `chart_note`'s hard cap
DOT_HTML_PX = 10              # the KPI card's best-value dot
DOT_GAP_PX = 6
CAPTION_FONT_WEIGHT = 400      # D5 (CHROME_CONTRACT.md SS7): the basis caption
                              # is NEVER bold, in either colour state

ACCENT_GLYPH = "\N{BLACK VERTICAL RECTANGLE}"
# The row-label accent: a GLYPH in the taxonomy's OFFICIAL hue
# through plotly's tick pseudo-html, sitting left of a label that names the
# taxon in full -- colour is recognition, the text is the encoding. Never a
# mark; see `palette.py`'s LABEL ACCENTS section.
ACCENT_GAP = "\N{NO-BREAK SPACE}"

LABEL_SHARED = "shared"
NOTE_HELP_GLYPH = "?"

# --- the bar-family contract (SS10): gutter column + diamond reference -----
COMPARE_MAX_SERIES = 3        # headroom above D1's fixed pair (two search
                              # slots) -- `_series_ids` refuses a
                              # figure rather than truncate past this
BAR_PX = 13                   # target thickness of one institution's bar
BAR_GROUP_SPAN = C.DEFAULT_GROUP_SPAN     # single-sourced with charts.py's
BAR_GROUP_FILL = C.DEFAULT_GROUP_FILL     # own Find-panel geometry
GUTTER_NEG_AXIS_FRAC = 0.16
GUTTER_TIP_FRAC = 0.06
REF_MARKER_SYMBOL = "diamond-tall"
REF_MARKER_SIZE = 8
GUTTER_PHANTOM_FILL = "rgba({0},{0},{0},{0})".format(0)   # fully transparent

LOW_VOLUME_FLOOR = 10.0
# A cell whose mean annual FULL volume is below this is drawn cautioned
# equals `palette.RATIO_HATCH_FLOOR` (50) over the 5-year CORE-AR window, the
# same threshold in different units (the one-sentence user-facing rule stays
# true either way: "cautions under fifty works over the counted window").
RATIO_HATCH_METRICS = ("pp",)
# `pp` hatches on its own per-row `denom_value` (n_covered) against
# `palette.RATIO_HATCH_FLOOR` directly -- the impact tab's own caution rule
# ( brief: "caution on impact rows with n_covered <
# fifty"). `share` (the profile tab) keeps the generic `low_vol_col` rule,
# which two_tab_bars's frame does not carry -- so the profile tab never
# cautions, matching the brief exactly.
LOW_VOLUME_GLYPH = "\N{DAGGER}"
HOVER_LOW_VOLUME = "rests on fewer than {floor} works over the counted window, read with care"

METRICS = ("share", "pp")
LEVELS = ("field", "subfield", "sdg")
REF_METRICS = ("share", "pp")
# Both draw a per-row DIAMOND reference (`REF_MARKER_SYMBOL`) whenever the
# frame carries a `ref_value` -- the European-mean share, or the world PP10
# reference -- per.
SORT_MODES = ("taxonomy", "value")
# `taxonomy` (the default) keeps the frame's OWN row order, grouped under a
# domain separator when `domain_col` is present -- this is what "rows ordered
# as given, grouped under field headers" (the C2 brief) means concretely.
# `value` re-ranks by the value summed over the compared institutions.

AX_TOP_DECILE_SHARE = "Share of publications in the world top decile"
_METRIC_AXIS = {"share": C.AX_SHARE, "pp": AX_TOP_DECILE_SHARE}
_METRIC_KIND = {"share": "pct", "pp": "pct"}
_KEY_COLS = {"sdg": ("sdg_idx", "sdg_number")}
_ACCENT_COLS = {"sdg": ("sdg_number", "sdg_idx"), "field": ("domain_id",),
                "subfield": ("domain_id",)}
_LEVEL_ACCENT_FAMILY = {"sdg": "sdg", "field": "oa", "subfield": "oa"}

HOVER_REFERENCE = "index reference"
HOVER_DENOMINATOR = "denominator"
HOVER_FWCI_MEDIAN = "FWCI (median)"
HOVER_FIELD_PREFIX = "Field: "
# C2 follow-up 2 (manager, 2026-09-03): the literal string the manager
# asked for, verbatim -- deliberately NOT this module's usual
# lowercase-label + THIN_SPACE hover convention (every other line here
# reads "label + a thin space + value"), because this one names what the row's
# OWN label does not already say (which FIELD a subfield belongs to), and
# the manager's own wording is the more legible one for that one line.


def _fmt_metric(v, metric: str) -> str:
    kind = _METRIC_KIND.get(metric, "vol")
    return _fmt_pct(v) if kind == "pct" else _fmt_vol(v)


def metric_row_height(n_rows: int, n_series: int, n_wrapped: int = 0,
                      minimum: int = C.MIN_HEIGHT) -> int:
    """Figure height for `n_rows` grouped-bar rows, sized from `BAR_PX` so
    "no bar thinner than target" is an arithmetic property of the builder
    rather than a hope about the row count -- see `charts.row_height`, whose
    base estimate this extends with the wrapped-row-pitch correction folded
    into the fallback branch too."""
    n_rows = max(int(n_rows), 1)
    n_wrapped = min(max(int(n_wrapped), 0), n_rows)
    base = C.row_height(n_rows, minimum=minimum, n_wrapped=n_wrapped)
    chrome = C.BASE_PX + C.BASE_PX // 2
    need = BAR_PX * max(int(n_series), 1) / (BAR_GROUP_SPAN * BAR_GROUP_FILL)
    if n_wrapped > 0:
        need *= C.WRAP_ROW_FACTOR
    have = max(base - chrome, 0) / n_rows
    if have >= need:
        return base
    return int(round(need * n_rows)) + chrome


def _series_ids(d: pd.DataFrame, slots: Mapping, ids: Sequence | None) -> list:
    """The compared institutions, in SLOT order, capped at
    `COMPARE_MAX_SERIES`. Refusing rather than truncating is deliberate: a
    builder that silently drew fewer institutions than asked would produce a
    figure whose caption/legend/export all disagree with it."""
    out = list(ids) if ids is not None else _ordered_ids(d, slots)
    out = sorted(dict.fromkeys(out), key=lambda i: (_slot_of(slots, i), str(i)))
    if len(out) > COMPARE_MAX_SERIES:
        raise ValueError(f"at most {COMPARE_MAX_SERIES} institutions per compare "
                         f"figure, got {len(out)}")
    if not out:
        raise ValueError("no institutions to draw")
    return out


def _accent_ticktext(rows: pd.DataFrame, level: str, label_col: str,
                     accent_col: str | None) -> tuple[list[str], list[str]]:
    """`(plain, styled)` tick strings, with the taxonomy accent glyph.
    `plain` is what `charts._gutter_margin_px` measures; `styled` is what
    plotly draws. No accent is invented when the level has no official
    palette, or the frame carries no accent key."""
    family = _LEVEL_ACCENT_FAMILY.get(level)
    plain, styled = [], []
    for _, r in rows.iterrows():
        text_plain, text_styled = C._tick_display(str(r[label_col]), None)
        if family and accent_col and accent_col in rows.index.names + list(rows.columns):
            hexcol = P.label_accent_color(family, r[accent_col])
            text_plain = f"{ACCENT_GLYPH}{ACCENT_GAP}{text_plain}"
            text_styled = (f'<span style="color:{hexcol}">{ACCENT_GLYPH}</span>'
                           f"{ACCENT_GAP}{text_styled}")
        plain.append(text_plain)
        styled.append(text_styled)
    return plain, styled


def _metric_rows(d: pd.DataFrame, key_col: str, keep: Sequence[str], sort: str,
                 value_col: str, domain_col: str, domain_order_col: str,
                 ) -> tuple[pd.DataFrame, list[int]]:
    """One row per taxon, ordered, plus the domain BOUNDARIES.

    `taxonomy` keeps the frame's own arrival order INSIDE each domain and
    sorts domains by `domain_order_col` when the caller supplies one -- the
    producer owns the taxonomy order, this builder owns only the grouping.
    `value` re-ranks by the value summed over the compared institutions and
    returns NO boundaries (a grouping the rows no longer have). Both sorts
    are stable (`mergesort`)."""
    rows = d.drop_duplicates(subset=[key_col])[list(keep)].reset_index(drop=True)
    rows["_arrival"] = range(len(rows))
    if sort == "value":
        agg = (d.assign(_v=pd.to_numeric(d[value_col], errors="coerce").fillna(0.0))
                .groupby(key_col, sort=False)["_v"].sum())
        rows["_rank"] = [-float(agg.get(k, 0.0)) for k in rows[key_col]]
        rows = rows.sort_values(["_rank", "_arrival"], kind="mergesort")
        return rows.drop(columns=["_rank", "_arrival"]).reset_index(drop=True), []
    if domain_order_col in rows.columns:
        rows["_dom"] = pd.to_numeric(rows[domain_order_col], errors="coerce")
        rows["_dom"] = rows["_dom"].fillna(float(len(rows)))
        rows = rows.sort_values(["_dom", "_arrival"], kind="mergesort").drop(columns="_dom")
    rows = rows.drop(columns="_arrival").reset_index(drop=True)
    edge_col = domain_col if domain_col in rows.columns else domain_order_col
    if edge_col not in rows.columns:
        return rows, []
    marks = [str(v) for v in rows[edge_col].tolist()]
    return rows, [i for i in range(len(marks) - 1) if marks[i] != marks[i + 1]]


def _gutter_value(v) -> str:
    """One gutter cell. A NUMBER formats as a volume (thin-space thousands,
    no decimals); anything else prints as the producer wrote it."""
    f = _num(v)
    if np.isfinite(f):
        return _fmt_vol(f)
    text = str(v).strip()
    return text if text and text.lower() != "nan" else P.NA_MARK


def _is_low_volume(r: pd.Series, metric: str, low_vol_col: str, denom_value_col: str) -> bool:
    """PP hatches on its own per-row `denom_value` (n_covered) against
    `palette.RATIO_HATCH_FLOOR`; every other metric hatches on `low_vol_col`
    against `LOW_VOLUME_FLOOR` -- the same threshold, different units. A
    frame missing the relevant column, or a cell with no value in it, is NOT
    low volume: an unmeasured thing is never flagged."""
    index = getattr(r, "index", [])
    if metric in RATIO_HATCH_METRICS:
        if denom_value_col not in index:
            return False
        v = _num(r[denom_value_col])
        return bool(np.isfinite(v) and v < P.RATIO_HATCH_FLOOR)
    if low_vol_col not in index:
        return False
    v = _num(r[low_vol_col])
    return bool(np.isfinite(v) and v < LOW_VOLUME_FLOOR)


def _metric_hover(r, iid, names, label_col, value_col, metric, ref_col,
                  denom_value_col, metric_label, gutter_col: str | None = None,
                  low: bool = False) -> str:
    """The fixed hover skeleton (CHROME_CONTRACT.md SS5), plus FOUR OPTIONAL
    reader-prose lines that a caller's frame may carry -- each drawn only
    when the row's OWN cell is present and not null, so a caller whose frame
    lacks them (e.g. `reciprocity_bars`, which overwrites this hover outright
    afterwards) gets the unchanged skeleton:
      * `si`, `fwci_median`, `vol_frac` (C2 brief: "hover extras");
      * `group_label` (C2 follow-up 2, `two_tab_bars`'s own `grouped_by_
        field=True` frame) -- "Field: {name}" as the literal FIRST hover
        line (ahead of even the institution name, exactly as asked), naming
        the FIELD a subfield row belongs to, alongside the same domain-
        coloured accent glyph already puts on the row's own LABEL
        (`_accent_ticktext`, auto-wired whenever the frame carries a
        `domain_id` column at `level="subfield"` -- no code change needed
        here, only the frame contract gaining the column).

    The `denominator` line prints `denom_value_col` -- a NUMBER, `_fmt_vol`'d
    and never a note-string: the bug that mixing the two once produced
    ("denominator: n/a" on a frame that had real data) stays fixed by
    construction, `denom_value` is a number by contract."""
    index = list(getattr(r, "index", []))
    parts = []
    if "group_label" in index and pd.notna(r["group_label"]):
        parts.append(f"{HOVER_FIELD_PREFIX}{r['group_label']}")
    title = (metric_label or _METRIC_AXIS[metric]).lower()
    parts += [_name_of(names, iid), str(r[label_col]),
             f"{title}{C.THIN_SPACE}{_fmt_metric(r[value_col], metric)}"]
    if "si" in index and pd.notna(r["si"]):
        parts.append(f"{C.HOVER_SI}{C.THIN_SPACE}{_fmt_si(r['si'])}")
    if "fwci_median" in index and pd.notna(r["fwci_median"]):
        parts.append(f"{HOVER_FWCI_MEDIAN}{C.THIN_SPACE}{_fmt_si(r['fwci_median'])}")
    if gutter_col and gutter_col in index:
        parts.append(f"{C.AX_WORKS.lower()}{C.THIN_SPACE}{_gutter_value(r[gutter_col])}")
    if "vol_frac" in index and pd.notna(r["vol_frac"]):
        parts.append(f"{C.HOVER_VOL_FRAC}{C.THIN_SPACE}{_fmt_vol(r['vol_frac'])}")
    if ref_col in index and metric in REF_METRICS:
        parts.append(f"{HOVER_REFERENCE}{C.THIN_SPACE}{_fmt_metric(r[ref_col], metric)}")
    if denom_value_col in index:
        parts.append(f"{HOVER_DENOMINATOR}{C.THIN_SPACE}{_fmt_vol(_num(r[denom_value_col]))}")
    if low:
        reason = HOVER_LOW_VOLUME.format(floor=_fmt_vol(P.RATIO_HATCH_FLOOR))
        parts.append(f"{LOW_VOLUME_GLYPH}{C.THIN_SPACE}{reason}")
    return "<br>".join(parts)


def _ref_line(fig: go.Figure, x: float) -> None:
    """The heavier/darker rule for a CONSTANT reference (a value the same in
    every row): a repeated marker on a value that never changes would be
    visual noise, not a benchmark, so the constant case stays a rule."""
    fig.add_vline(x=x, line=dict(color=P.INK, width=C.LINE_PX, dash="dash"))


def _add_reference(fig: go.Figure, rows: pd.DataFrame, ref_col: str,
                   ref_value: float | None) -> None:
    """ONE heavier/darker rule for a CONSTANT reference (`_ref_line`), a
    `REF_MARKER_SYMBOL` diamond MARKER per row for a VARYING one: an
    index reference is a different number in every taxon, and drawing either
    a single line or a single row's worth of markers across the whole panel
    would assert a benchmark that does not exist for the other rows."""
    if ref_value is not None:
        _ref_line(fig, float(ref_value))
        return
    if ref_col in rows.columns:
        series = pd.to_numeric(rows[ref_col], errors="coerce")
        finite = series[np.isfinite(series)]
        if len(finite):
            if float(finite.max()) - float(finite.min()) <= 1e-12:
                _ref_line(fig, float(finite.iloc[0]))
            else:
                xs = [float(v) for v in series.tolist() if np.isfinite(v)]
                ys = [ri for ri, v in enumerate(series.tolist()) if np.isfinite(v)]
                fig.add_trace(go.Scatter(
                    x=xs, y=ys, mode="markers",
                    marker=dict(symbol=REF_MARKER_SYMBOL, size=REF_MARKER_SIZE,
                               color=P.INK, line=dict(width=0)),
                    hoverinfo="skip", showlegend=False))


# ---------------------------------------------------------------------------
# 1. The bar-family primitive (CHROME_CONTRACT.md SS10) -- kept unchanged,
#    trimmed to the two metrics D3/D4 need. `two_tab_bars` and
#    `reciprocity_bars` below are its only callers in this module.
# ---------------------------------------------------------------------------
def fig_metric_bars(
    frame: pd.DataFrame,
    metric: str,
    ids: Sequence | None = None,
    *,
    slots: Mapping,
    names: Mapping | None = None,
    level: str = "field",
    sort: str = "taxonomy",
    value_col: str = "value",
    label_col: str | None = None,
    key_col: str | None = None,
    ref_col: str = "ref_value",
    ref_value: float | None = None,
    denom_value_col: str = "denom_value",
    accent_col: str | None = None,
    metric_label: str | None = None,
    gutter: bool = True,
    gutter_col: str = "vol_display",
    gutter_header: str | None = None,
    low_vol_col: str = "vol_full_annual_mean",
    domain_col: str = "domain_id",
    domain_order_col: str = "domain_order",
) -> go.Figure:
    """ONE metric, one taxonomy level, up to `COMPARE_MAX_SERIES` institutions:
    horizontal grouped bars, one row per taxon, the value written on the mark.

    ROW ORDER. `sort="taxonomy"` (the default) keeps the frame's OWN arrival
    order, grouped under `domain_col` with a heavier separator where one
    domain ends (`_row_rules`'s boundaries) -- this is what "rows ordered as
    given, grouped under field headers"
    means: the CALLER decides the order (already ranked how it wants,
    e.g. by combined volume) and this builder never re-sorts it, only marks
    where a `domain_col` value changes. `sort="value"` re-ranks by the value
    summed over the compared institutions.

    THE GUTTER COLUMN (E6, CHROME_CONTRACT.md SS10.1). `gutter=True` (the
    default) draws a dedicated LEFT column: one phantom, zero-visible-fill
    `go.Bar` trace per institution, in the SAME lane as its real bar, at a
    small negative x (`GUTTER_NEG_AXIS_FRAC` of the data span) with its own
    raw `gutter_col` value as text, pushed further left by
    `textposition="outside"`. `gutter_header` names the basis (the caller's
    word, this module never invents one). Below roughly 600 px of plot width
    the column has nowhere to go (a wrapped first-row label alone can need
    most of a 390 px figure); pass `gutter=False` and the raw value stays in
    hover alone -- never a horizontal scroll either way.

    THE CAUTION CHANNEL (E5, CHROME_CONTRACT.md SS10.2). Every bar is SOLID,
    in the institution's own colour. A cell `_is_low_volume` flags switches
    its value text AND its gutter text to `palette.WARNING_CAPTION_COLOR`
    (never bold) and keeps `LOW_VOLUME_GLYPH` (a dagger) -- disclosure, never
    suppression: the bar is still drawn at full size, only the ink that
    prints its own number changes.

    ENCODING. Bar = institution (ascending
    `inst_key` via `slots`). Row label = the taxon; for SDG (and, generally,
    field/subfield) it carries a glyph in the taxonomy's official colour -- taxonomy colour on labels,
    institution colour on marks, never the reverse.

    REFERENCE (E8, CHROME_CONTRACT.md SS10.3). Only `REF_METRICS` (`share`,
    `pp`) draw one, from the frame's OWN `ref_value` column. A reference that
    VARIES by row is a dark `REF_MARKER_SYMBOL` diamond MARKER per row; one
    that is the SAME for every row stays ONE rule across the panel.

    EMPTY STATE (n/a never zero). An institution with no row for a taxon gets
    NO bar and NO label. A genuine zero gets no visible bar either (a
    zero-length bar cannot be drawn) but does get its value label at the
    origin, so "measured, and it is zero" and "not measured" look different.
    """
    if metric not in METRICS:
        raise ValueError(f"metric must be one of {METRICS}, got {metric!r}")
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}, got {level!r}")
    if sort not in SORT_MODES:
        raise ValueError(f"sort must be one of {SORT_MODES}, got {sort!r}")
    if "institution_id" not in frame.columns or value_col not in frame.columns:
        raise ValueError(f"frame needs institution_id and {value_col!r}")

    d = frame.copy()
    label_col = label_col or _first_col(d, ("taxon_label",) + C._LABEL_COLS)
    if label_col is None:
        raise ValueError("no label column found; pass label_col=")
    key_col = key_col or _first_col(d, ("taxon_id",) + _KEY_COLS.get(level, ())) or label_col
    accent_col = accent_col or _first_col(d, _ACCENT_COLS.get(level, ()))
    series = _series_ids(d, slots, ids)

    keep = list(dict.fromkeys(c for c in (key_col, label_col, ref_col, accent_col,
                                          domain_col, domain_order_col)
                              if c and c in d.columns))
    rows, boundaries = _metric_rows(d, key_col, keep, sort, value_col,
                                    domain_col, domain_order_col)
    n = len(rows)
    if n == 0:
        raise ValueError("no rows to draw")

    cells = {(r[key_col], r["institution_id"]): r for _, r in d.iterrows()}
    vals = pd.to_numeric(d[value_col], errors="coerce")
    vmax = float(vals.max()) if len(vals) and np.isfinite(vals.max()) else 0.0
    vmin = float(vals.min()) if len(vals) and np.isfinite(vals.min()) else 0.0
    signed = vmin < 0

    keys = rows[key_col].tolist()

    gutter_active = bool(gutter and gutter_col in d.columns
                         and pd.notna(d[gutter_col]).any())
    neg_extent = 0.0
    gutter_x = 0.0
    if gutter_active:
        basis = vmax if vmax > 0 else (abs(vmin) if vmin < 0 else 1.0)
        neg_extent = basis * GUTTER_NEG_AXIS_FRAC
        gutter_x = -neg_extent * GUTTER_TIP_FRAC

    fig = go.Figure()
    _row_rules(fig, n, boundaries)
    if metric in REF_METRICS or ref_value is not None:
        _add_reference(fig, rows, ref_col, ref_value)

    for k, iid in enumerate(series):
        offset, bar_w = C._series_offset_width(len(series), k, BAR_GROUP_SPAN,
                                               BAR_GROUP_FILL)
        slot = _slot_of(slots, iid)
        color = P.institution_color(slot)
        ink = P.institution_ink(slot)
        xs, ys, texts, hovers, inks = [], [], [], [], []
        gy, gtexts, ginks = [], [], []
        for ri, key in enumerate(keys):
            r = cells.get((key, iid))
            if r is None:
                continue
            v = _num(r[value_col])
            if not np.isfinite(v):
                continue
            low = _is_low_volume(r, metric, low_vol_col, denom_value_col)
            caution = P.WARNING_CAPTION_COLOR if low else ink
            xs.append(v)
            ys.append(ri)
            texts.append(_fmt_metric(v, metric) + (LOW_VOLUME_GLYPH if low else ""))
            inks.append(caution)
            hovers.append(_metric_hover(r, iid, names, label_col, value_col,
                                        metric, ref_col, denom_value_col,
                                        metric_label, gutter_col, low))
            if gutter_active and gutter_col in r.index:
                gy.append(ri)
                gtexts.append(_gutter_value(r[gutter_col]))
                ginks.append(caution)
        fig.add_trace(go.Bar(
            x=xs, y=ys, orientation="h", offset=offset, width=bar_w,
            marker=dict(color=[color] * len(xs), line=dict(color=color, width=C.HAIRLINE_PX)),
            text=texts, textposition="outside", cliponaxis=False,
            textfont=dict(size=C.GUTTER_FONT_PX, color=inks),
            customdata=hovers, hovertemplate="%{customdata}<extra></extra>",
            showlegend=False))
        if gy:
            fig.add_trace(go.Bar(
                x=[gutter_x] * len(gy), y=gy, orientation="h", offset=offset, width=bar_w,
                marker=dict(color=[GUTTER_PHANTOM_FILL] * len(gy), line=dict(width=0)),
                text=gtexts, textposition="outside", cliponaxis=False,
                textfont=dict(size=C.GUTTER_FONT_PX, color=ginks),
                customdata=[""] * len(gy), hoverinfo="skip", showlegend=False))

    fig.update_layout(barmode="overlay", bargap=0)

    if gutter_active and gutter_header:
        fig.add_annotation(x=gutter_x, xref="x", y=1.0, yref="y domain",
                           xanchor="right", yanchor="bottom",
                           text=gutter_header, showarrow=False,
                           font=dict(size=C.GUTTER_FONT_PX, color=P.INK_SECONDARY))

    plain, styled = _accent_ticktext(rows, level, label_col, accent_col)
    _y_axis(fig, n, styled)
    n_wrapped = sum(1 for s in styled if "<br>" in s)
    lo = min(vmin, 0.0)
    hi = max(vmax, 0.0)
    span = (hi - lo) or (abs(hi) or 1.0)
    pad = span * AXIS_PAD_FRAC
    fig.update_xaxes(range=[lo - (pad if signed else 0.0) - neg_extent, hi + pad],
                     title_text=metric_label or _METRIC_AXIS[metric],
                     gridcolor=P.GRID, zerolinecolor=P.GRID, zeroline=True,
                     zerolinewidth=C.HAIRLINE_PX, linecolor=P.BORDER)
    if _METRIC_KIND[metric] == "pct":
        fig.update_xaxes(tickformat=C._AXIS_PCT_FMT)
    if gutter_active and not signed:
        fig.update_xaxes(tickmode="array", tickvals=C._nice_ticks(hi))
    if signed:
        _bold_axes(fig, y=None)
    plain_lines = [s.replace("<br>", "\n") for s in plain]
    return C._base_layout(fig, metric_row_height(n, len(series), n_wrapped=n_wrapped),
                          margin=dict(t=C.BASE_PX // 2,
                                      l=C._gutter_margin_px(plain_lines),
                                      r=C.BASE_PX, b=C.BASE_PX))


# ---------------------------------------------------------------------------
# 2. two_tab_bars -- the Thematic-shape (D3) and SDG-profile (D4) charts
# ---------------------------------------------------------------------------
TWO_TAB_TABS = ("profile", "impact")
GUTTER_HEADER_FULL = "Publications, full count"


def two_tab_bars(
    frame: pd.DataFrame,
    tab: str,
    names: Mapping,
    colors: Mapping,
    *,
    grouped_by_field: bool,
    gutter: bool = True,
) -> go.Figure:
    """The pair's Thematic-shape chart (D3, `grouped_by_field=True`, top-20
    subfields by combined volume) and SDG-profile chart (D4,
    `grouped_by_field=False`, all seventeen goals) -- one call site, one tab
    switch, both a thin `fig_metric_bars` adapter (no new bar-drawing code).

    INPUT FRAME CONTRACT (long: one row per institution x taxon):
      row_id -- stable key for one taxon row (a subfield id, or an
                       SDG number/idx) -- REPEATS across the two institution
                       rows of the same taxon
      row_label -- the taxon's display name
      group_label -- the taxon's FIELD name, for `grouped_by_field=True`
                       (bestfit); omitted or null for SDG rows -- draws a
                       heavier separator between two different field names,
                       never a re-sort (rows stay in the order given)
      institution_id -- one of the two compared institutions
      value -- the row's SHARE OF OWN OUTPUT, 0-1 (`tab="profile"`)
                       or its PP10_WD -- share of publications in the world
                       top decile, 0-1 (`tab="impact"`)
      ref_value -- the diamond reference: the European-mean share
                       (profile) or the world PP10 reference (impact);
                       omit the column, or leave a row's cell null, for no
                       diamond on that row
      vol_full -- full-counted publication count, int -- drawn in the
                       LEFT gutter column (header names the pinned basis,
                       D10: bestfit + full counting)
      n_covered -- covered-works denominator for the impact tab; a
                       row with `n_covered` under `palette.RATIO_HATCH_FLOOR`
                       (fifty) gets the red dagger caution -- ignored on the
                       profile tab (D3 never cautions Share)
      si, fwci_median, vol_frac -- optional hover-only extras (`_metric_hover`)
      domain_id -- OPTIONAL, OpenAlex domain id of the taxon's FIELD
                       C2 follow-up 2 (manager, 2026-09-03): when present,
                       drives TWO things at once, both existing mechanisms
                       this builder does not invent: a small domain-coloured
                       square accent in front of the row's own label and, when `group_label` is ALSO
                       present and not null, "Field: {group_label}" as the
                       literal FIRST hover line (`_metric_hover`). Meaningful
                       for `grouped_by_field=True` (the shape chart); has no
                       effect for SDG rows, which carry no field/domain
                       concept.

    `colors` is the institution SLOT mapping (`institution_id -> int`, as
    returned by the institution-slot map), resolved to a hex fill via
    `palette.institution_color`/`institution_ink` inside `fig_metric_bars`.
    `gutter=False` below the ~600 px plot-width breakpoint (CHROME_CONTRACT.md
    SS10.7) drops the LEFT column; the raw volume stays in hover regardless.
    """
    if tab not in TWO_TAB_TABS:
        raise ValueError(f"tab must be one of {TWO_TAB_TABS}, got {tab!r}")
    metric = "share" if tab == "profile" else "pp"
    level = "subfield" if grouped_by_field else "sdg"
    domain_col = "group_label" if grouped_by_field else "__ungrouped__"
    return fig_metric_bars(
        frame, metric,
        slots=colors, names=names, level=level, sort="taxonomy",
        value_col="value", label_col="row_label", key_col="row_id",
        ref_col="ref_value", denom_value_col="n_covered",
        gutter=gutter, gutter_col="vol_full", gutter_header=GUTTER_HEADER_FULL,
        domain_col=domain_col, domain_order_col="__ungrouped_order__",
    )


# ---------------------------------------------------------------------------
# 3. mirror_frontier -- the shared-frontier mirror (D5)
# ---------------------------------------------------------------------------
JOINT_FLOOR = 5
# The P7 qualifying floor (`core_total >= 5`, 's own decisions
# log 2026-09-03): below it `collab_topic_vols` carries no row for the pair
# and `vol_joint` arrives NaN.
HOVER_JOINT = "joint"
HOVER_JOINT_UNAVAILABLE = "joint count not available under {floor} joint publications"
TOP_DECILE_GLYPH = "\N{BLACK DIAMOND}"
MIRROR_LINK_TARGET = "_blank"

MIRROR_LABEL_WRAP_WIDTH = 20
# C2 follow-up (manager, 2026-09-03): Streamlit gives Python no viewport
# width, so this chart cannot offer a caller-decided `gutter=False`-style
# narrow-width switch the way `fig_metric_bars` does (CHROME_CONTRACT.md
# SS10.7) -- a topic name has to fit SOME fixed budget at every width.
# **Measured, not estimated** (`yaxis.automargin=True` GROWS the configured
# margin to fit whatever text arrives, so it -- not a character-count
# formula -- is the real ceiling that decides the plot area's width): a
# character-length sweep against the live Playwright render
# (`progress/C2_renders/render_c2.py`'s own harness) found the plot area
# collapses toward zero above ~26 chars/line at 390 px and plateaus at its
# `MIRROR_MARGIN_CAP_PX`-bound maximum at 22 chars/line and below. Twenty
# keeps comfortable headroom under that knee for glyphs wider than the
# probe's own monospaced test characters -- UNCHANGED by the C2 follow-up-2
# three-line widening below, because automargin cares about the WIDEST
# LINE, not how many lines a label has.
MIRROR_LABEL_MAX_LINES = 3
# C2 follow-up 2 (manager, 2026-09-03): raised from two -- real OpenAlex
# topic names run 25-60 chars ("Geological and Geochemical Analysis") and
# were losing their meaning cut to two 20-char lines. Verified this does
# NOT reopen the 390 px fix above: `MIRROR_LABEL_WRAP_WIDTH` (the widest any
# ONE line can be) is unchanged, and automargin's left-margin need is driven
# by line WIDTH, not line COUNT -- re-measured on the live render after this
# change, `progress/C2.md`.
MIRROR_LABEL_CHAR_BUDGET = 60
# C2 follow-up 2: the ellipsis decision is keyed on the ORIGINAL name's own
# character count, never on how many lines greedy word-wrap happens to need
# a <= 60 char name that still does not fit `MIRROR_LABEL_MAX_LINES`
# lines under strict word-boundary wrapping (word lengths tile imperfectly)
# gets its overflow MERGED into the last line instead (never a lost
# character, `charts.wrap_label`'s own "two lines, not truncation" rule);
# only a name that is ACTUALLY longer than the budget is cut, with
# `ELLIPSIS` marking the cut.
MIRROR_MARGIN_CAP_PX = 180
# The CONFIGURED left margin -- NOT a hard ceiling on the RENDERED one:
# `yaxis.automargin=True` (`_y_axis`, unchanged) GROWS the actual margin
# past this value whenever the tick text still needs more room, so this
# number only binds once `MIRROR_LABEL_WRAP_WIDTH` has already kept the
# text short enough that it does not need to (measured together on the live
# render -- `progress/C2_renders/render_c2.py` -- as one system, not two
# independent settings). At 390 px total viewport width, minus the render
# harness's own 16 px page padding on both sides and the chart's `r`/`b`
# margins, 180 px of left margin leaves > 120 px for the bars -- the C2
# follow-up's own acceptance floor. Re-confirmed unchanged after follow-up 2
# (three lines, still 20 chars wide each): `progress/C2.md`.
ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"

MIRROR_THREE_LINE_FACTOR = 3.0
# Manager follow-up 2026-09-03: a genuine, real-topic-name overlap survived
# to the live page ("Ocean Acidification / Effects and / Responses" running
# into the next row) at both 1280 and 390 px -- found on the REAL render,
# not the synthetic harness. Measured directly (Playwright, `.ytick`
# bounding boxes against the real Compare page, T0 anchor pair, "Show all"):
# a 3-line row's own rendered text is 47.2 px tall; `_mirror_row_height`'s
# OLD formula (linearly extrapolating `charts.WRAP_ROW_FACTOR`'s 2-line
# increment, +0.7x ROW_PX per additional line) gave a pitch of ~42.2 px
# a 5.0 px deficit. Plotly CENTRES each row's text in its uniform slot, so
# two ADJACENT 3-line rows each overflow 2.5 px toward the other -- exactly
# the measured 5.0 px overlap, at every 3-line-then-3-line boundary in the
# real 44-topic render (16 such rows, T0 anchor pair). The 2-line case is
# UNCHANGED and was never the problem (measured 31.6 px text against a
# ~30.6 px pitch, comfortably positive gaps throughout) -- this constant
# governs ONLY the 3-line pitch, calibrated to the SAME live measurement
# with real headroom (18 px x 3.0 = 54 px pitch against a measured 47.2 px
# need, ~6.8 px margin) rather than a formula extrapolated from a different
# case's own increment.


def _wrap_topic_label(text, width: int = MIRROR_LABEL_WRAP_WIDTH,
                      max_lines: int = MIRROR_LABEL_MAX_LINES,
                      char_budget: int = MIRROR_LABEL_CHAR_BUDGET) -> list[str]:
    """Greedy word-wrap (never splits a word), up to `max_lines` (three)
    the ONE place in this module that can shorten a label, and even then
    ONLY past `char_budget` (sixty) characters of the ORIGINAL name (C2
    follow-up 2: real OpenAlex topic names run 25-60 chars and must survive
    whole). There is no Streamlit-side viewport width to condition a
    per-width switch on here (`mirror_frontier`'s own docstring) -- see
    `CHROME_CONTRACT.md` SS13.8. Returns a LIST of raw (unescaped) lines, so
    the caller can HTML-escape each line before joining with `<br>` (escaping
    the whole wrapped string first risks splitting an entity mid-way).

    Two distinct "too long" cases, handled differently on purpose:
      * the name is <= `char_budget` chars but strict word-boundary
        wrapping still needs MORE than `max_lines` lines (word lengths tile
        imperfectly against `width`) -- the overflow is MERGED into the
        last line instead of cut, so no character is ever lost under the
        budget (`charts.wrap_label`'s own "cap is the line count, not the
        text" rule, applied here at three lines instead of two);
      * the name is actually longer than `char_budget` -- cut to `max_lines`
        lines and the last one gets `ELLIPSIS`."""
    words = str(text).split()
    if not words:
        return [str(text)]
    lines = [words[0]]
    for w in words[1:]:
        candidate = f"{lines[-1]} {w}"
        if len(candidate) <= width:
            lines[-1] = candidate
        else:
            lines.append(w)
    if len(lines) <= max_lines:
        return lines
    if len(str(text)) <= char_budget:
        return lines[: max_lines - 1] + [" ".join(lines[max_lines - 1:])]
    kept = lines[:max_lines]
    trimmed = kept[-1][: max(width - len(ELLIPSIS), 1)].rstrip()
    kept[-1] = f"{trimmed}{ELLIPSIS}"
    return kept


def _mirror_row_height(n_rows: int, max_lines_used: int, minimum: int = C.MIN_HEIGHT) -> int:
    """mirror_frontier's own row-pitch formula -- generalises `charts.
    row_height`'s BINARY `n_wrapped` (its own one-vs-two-line case only) to
    however many lines (one to `MIRROR_LABEL_MAX_LINES`) a row's label
    actually wrapped onto: plotly spaces a categorical axis UNIFORMLY, so
    once ANY row needs `max_lines_used` lines, EVERY row gets that pitch.

    The two-line case reproduces `charts.WRAP_ROW_FACTOR` exactly (the
    identical number every other wrapped chart in the app already uses)
    UNCHANGED, and never the problem (measured live at 31.6 px of text
    against a ~30.6 px pitch, comfortably positive row-to-row gaps
    throughout the real page). The three-line case does NOT linearly
    extrapolate from the two-line increment any more (manager follow-up
    2026-09-03: that extrapolation undershot a REAL measurement by 5 px,
    see `MIRROR_THREE_LINE_FACTOR`'s own comment) -- it uses that directly
    calibrated constant instead."""
    n_rows = max(int(n_rows), 1)
    max_lines_used = min(max(int(max_lines_used), 1), MIRROR_LABEL_MAX_LINES)
    if max_lines_used <= 1:
        factor = 1.0
    elif max_lines_used == 2:
        factor = C.WRAP_ROW_FACTOR
    else:
        factor = MIRROR_THREE_LINE_FACTOR
    pitch = C.ROW_PX * factor
    return max(minimum, int(round(pitch * n_rows)) + C.BASE_PX)


def mirror_frontier(
    frame: pd.DataFrame,
    names: Sequence,
    colors: Sequence,
    top_n: int | None = None,
) -> go.Figure:
    """The shared-frontier mirror (D5): one row per topic, A-only publications
    drawn LEFT of a common centre in A's colour, JOINT publications centred
    (`-joint/2` to `+joint/2`) in `palette.SHARED_FRONTIER` red with the
    `palette.FRONTIER_SHARED_HALO` white ring, B-only RIGHT in B's colour.
    Total row width = A-only + joint + B-only. New geometry (floating
    three-segment `go.Bar`s via `base=`) -- no kept primitive draws this.

    INPUT FRAME CONTRACT (one row per topic):
      topic_id, topic_name -- identity + display name
      url_joint -- the OpenAlex link for the pair's joint publications on
                       this topic (E6's `authorships.institutions.id:{A},
                       authorships.institutions.id:{B}` filter) -- becomes the
                       y tick's `<a href>`
      vol_a, vol_b -- each institution's OWN publication count on the topic
      vol_joint -- the pair's JOINT count on the topic; NaN when the pair
                       is below the P7 floor (`JOINT_FLOOR`) -- no red segment
                       is drawn for that row and its hover explains why
      expansion, acceleration -- the topic's frontier scores (hover only)
      is_top_decile -- world top-decile flag; appends `TOP_DECILE_GLYPH` (an
                       ink diamond, never a colour) to the row's label

    `names`/`colors` are TWO-ITEM SEQUENCES, `[a, b]`, matching `vol_a`/
    `vol_b`'s own order -- this frame carries no `institution_id` column to
    key a Mapping by. `colors` holds SLOT ints (the institution-slot map
    order), resolved via `palette.institution_color`, matching every other
    builder in this module. `top_n` keeps the `top_n` rows with the largest
    `vol_a + vol_b` ("combined volume", D5); `None` draws every row given.

    y-axis ticks carry `<a href="{url_joint}" target="_blank">{topic_name}
    {glyph}</a>` via plotly's own pseudo-html tick text (already exploited
    elsewhere in this file for `<span style>`; verified here by rendering and
    clicking in `progress/C2_renders/render_c2.py`). A long name wraps onto
    at most two lines (`_wrap_topic_label`, ellipsis beyond); **measured
    fact:** plotly renders each WRAPPED LINE as its own SVG `<tspan>`, and
    re-wraps this module's ONE `<a>.</a>` source markup into ONE anchor
    PER LINE at draw time (both carrying the identical `href` this module
    wrote) -- so either line is independently clickable and both open the
    same URL, even though the SOURCE string here is a single tag spanning
    both lines. Confirmed in `progress/C2_renders/render_c2.py`'s own click
    check, which clicks whichever line the anchor locator resolves to."""
    required = ("topic_id", "topic_name", "url_joint", "vol_a", "vol_b",
               "vol_joint", "expansion", "acceleration")
    for col in required:
        if col not in frame.columns:
            raise ValueError(f"missing column {col!r}")
    if len(names) < 2 or len(colors) < 2:
        raise ValueError("mirror_frontier needs names=[a, b] and colors=[slot_a, slot_b]")

    d = frame.copy()
    va = pd.to_numeric(d["vol_a"], errors="coerce").fillna(0.0)
    vb = pd.to_numeric(d["vol_b"], errors="coerce").fillna(0.0)
    d["_combined"] = va + vb
    d = d.sort_values("_combined", ascending=False, kind="mergesort").reset_index(drop=True)
    if top_n is not None and top_n > 0:
        d = d.head(int(top_n)).reset_index(drop=True)
    n = len(d)
    if n == 0:
        raise ValueError("no topics to draw")

    color_a = P.institution_color(int(colors[0]))
    color_b = P.institution_color(int(colors[1]))
    name_a, name_b = _name_of(names, None, index=0), _name_of(names, None, index=1)
    top = (d["is_top_decile"].fillna(False).to_numpy(dtype=bool)
          if "is_top_decile" in d.columns else np.zeros(n, dtype=bool))

    a_only = np.zeros(n); b_only = np.zeros(n); half = np.zeros(n)
    joint_valid = np.zeros(n, dtype=bool)
    left_extent = np.zeros(n); right_extent = np.zeros(n)
    for i in range(n):
        va_i = _num(d.at[i, "vol_a"])
        vb_i = _num(d.at[i, "vol_b"])
        vj_i = _num(d.at[i, "vol_joint"])
        valid = np.isfinite(vj_i)
        veff = vj_i if valid else 0.0
        joint_valid[i] = valid and veff > 0
        half[i] = veff / 2.0
        a_only[i] = max(0.0, (va_i if np.isfinite(va_i) else 0.0) - veff)
        b_only[i] = max(0.0, (vb_i if np.isfinite(vb_i) else 0.0) - veff)
        left_extent[i] = half[i] + a_only[i]
        right_extent[i] = half[i] + b_only[i]

    hovers = []
    for i in range(n):
        vj_i = _num(d.at[i, "vol_joint"])
        joint_line = (f"{HOVER_JOINT}{C.THIN_SPACE}{_fmt_vol(vj_i)}" if joint_valid[i]
                     else HOVER_JOINT_UNAVAILABLE.format(floor=_fmt_vol(JOINT_FLOOR)))
        hovers.append("<br>".join([
            str(d.at[i, "topic_name"]),
            f"{name_a}{C.THIN_SPACE}{_fmt_vol(d.at[i, 'vol_a'])}",
            f"{name_b}{C.THIN_SPACE}{_fmt_vol(d.at[i, 'vol_b'])}",
            joint_line,
            f"{C.HOVER_EXPANSION}{C.THIN_SPACE}{_fmt_frontier(d.at[i, 'expansion'])}",
            f"{C.HOVER_ACCELERATION}{C.THIN_SPACE}{_fmt_frontier(d.at[i, 'acceleration'])}",
        ]))

    fig = go.Figure()
    _row_rules(fig, n)
    fig.add_trace(go.Bar(
        x=list(a_only), y=list(range(n)), base=list(-left_extent), orientation="h",
        marker=dict(color=color_a, line=dict(color=color_a, width=C.HAIRLINE_PX)),
        customdata=hovers, hovertemplate="%{customdata}<extra></extra>", showlegend=False))
    joint_idx = [i for i in range(n) if joint_valid[i]]
    fig.add_trace(go.Bar(
        x=[2.0 * half[i] for i in joint_idx], y=joint_idx,
        base=[-half[i] for i in joint_idx], orientation="h",
        marker=dict(color=P.SHARED_FRONTIER,
                   line=dict(color=P.FRONTIER_SHARED_HALO["color"],
                             width=P.FRONTIER_SHARED_HALO["width"])),
        customdata=[hovers[i] for i in joint_idx],
        hovertemplate="%{customdata}<extra></extra>", showlegend=False))
    fig.add_trace(go.Bar(
        x=list(b_only), y=list(range(n)), base=[half[i] for i in range(n)], orientation="h",
        marker=dict(color=color_b, line=dict(color=color_b, width=C.HAIRLINE_PX)),
        customdata=hovers, hovertemplate="%{customdata}<extra></extra>", showlegend=False))
    fig.update_layout(barmode="overlay", bargap=0)

    plain, styled = [], []
    for i in range(n):
        glyph = f" {TOP_DECILE_GLYPH}" if top[i] else ""
        lines = _wrap_topic_label(str(d.at[i, "topic_name"]))
        plain.append("\n".join(lines) + glyph)
        styled_lines = "<br>".join(_esc(ln) for ln in lines)
        # ONE <a>.</a> wraps the whole (possibly two-line) label in THIS
        # source string -- plotly re-splits it into one anchor per rendered
        # line at draw time (both keep the same href; see the docstring's
        # own "measured fact" above). Glyph lands on the last line by
        # construction (appended after the join, no separate placement).
        styled.append(f'<a href="{_esc(d.at[i, "url_joint"])}" target="{MIRROR_LINK_TARGET}">'
                      f"{styled_lines}{glyph}</a>")
    _y_axis(fig, n, styled)

    vmax = float(max(left_extent.max(), right_extent.max())) if n else 1.0
    vmax = vmax if vmax > 0 else 1.0
    pad = vmax * AXIS_PAD_FRAC
    ticks = [t for t in C._nice_ticks(vmax) if t > 0]
    fig.update_xaxes(
        range=[-vmax - pad, vmax + pad], tickmode="array",
        tickvals=[-t for t in reversed(ticks)] + [0.0] + ticks,
        ticktext=([_fmt_vol(t) for t in reversed(ticks)] + [_fmt_vol(0.0)]
                  + [_fmt_vol(t) for t in ticks]),
        title_text=C.AX_WORKS, gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)
    _bold_axes(fig, y=None)
    # `plain` already holds the WRAPPED (<= two-line) text, so
    # `_gutter_margin_px` measures the longest WRAPPED line, not the whole
    # un-wrapped name -- `MIRROR_MARGIN_CAP_PX` is a belt-and-braces ceiling
    # on top of that (C2 follow-up: mirror_frontier@390px was unusable
    # before this fix, `progress/C2.md`).
    margin_l = min(C._gutter_margin_px(plain), MIRROR_MARGIN_CAP_PX)
    # A SECOND part of that same fix, found while reading the FIXED render:
    # a wrapped row needs MORE than one row's worth of vertical space, same
    # reasoning every other builder's `n_wrapped` term already carries
    # (`charts.row_height`'s own rule) -- omitting it here left every
    # wrapped row's later lines overlapping the row below it, still visibly
    # broken even after the margin/wrap-width fix alone. C2 follow-up 2:
    # `_mirror_row_height` (this module) replaces the plain `metric_row_
    # height(n, 1, n_wrapped=.)` call from follow-up 1 -- that binary
    # term could not tell a two-line row from THREE, and under-allocated
    # height once three-line wrapping existed (found on this fix's own
    # first render, same discovery pattern as follow-up 1's own two bugs).
    max_lines_used = max((s.count("\n") + 1 for s in plain), default=1)
    return C._base_layout(fig, _mirror_row_height(n, max_lines_used),
                          margin=dict(t=C.BASE_PX // 2, l=margin_l,
                                      r=C.BASE_PX, b=C.BASE_PX))


# ---------------------------------------------------------------------------
# 4. yearly_domain_stack -- the relationship's yearly stack (D7)
# ---------------------------------------------------------------------------
YEARLY_STACK_HEIGHT_PX = 320
YEARLY_STACK_TOP_MARGIN_PX = C.BASE_PX * 2
# C2 follow-up: room for the native horizontal legend ABOVE the plot area, on
# top of the year-total annotations that already sit just above each bar
# (unchanged, still inside the plot itself -- the legend sits in the MARGIN,
# a separate band).


def yearly_domain_stack(frame: pd.DataFrame) -> go.Figure:
    """Joint publications per year, stacked by the four OpenAlex domains
    (D7's replacement for 's single-series `fig_pulse`, credited in this
    module's own docstring). Domain colours are `palette.OA_DOMAIN_COLORS`
    (`palette.domain_color`), in `palette.OA_DOMAIN_ORDER` -- no institution
    identity here, matching D7's own "pooled" reading of a pair's joint
    corpus rather than either side's.

    INPUT FRAME CONTRACT (one row per year x domain):
      year -- the calendar year
      domain_id -- an OpenAlex domain id, 1-4
      domain_name -- the domain's display name
      vol -- joint publications in that domain that year (int)

    A year's TOTAL (summed across domains) is written as text ABOVE its bar.

    C2 follow-up (manager, 2026-09-03): this is the ONE chart in this module
    with its OWN native Plotly legend (`showlegend=True`, `legend.orientation
    ="h"`, anchored just above the plot) rather than the app-wide HTML chip
    strip every other builder here defers to (CHROME_CONTRACT.md SS4)
    four unlabelled bar colours with no institution axis to anchor a caption
    against were unreadable on their own. `map_legend_strip(color_by=
    "domain",.)` is still available for a caller (e.g. a workbook export
    caption) that wants the same chip-strip form, but the CHART itself no
    longer depends on it to be legible."""
    for col in ("year", "domain_id", "domain_name", "vol"):
        if col not in frame.columns:
            raise ValueError(f"missing column {col!r}")
    d = frame.copy()
    years = sorted({str(y) for y in d["year"]}, key=lambda y: (len(y), y))
    if not years:
        raise ValueError("no years to draw")
    d["_year"] = d["year"].astype(str)

    fig = go.Figure()
    for did in P.OA_DOMAIN_ORDER:
        mine = d[d["domain_id"] == did]
        if mine.empty:
            continue
        by_year = mine.set_index("_year")["vol"]
        dname = str(mine["domain_name"].iloc[0])
        vals = [float(by_year.get(y, 0.0)) for y in years]
        hovers = [f"{dname}<br>{C.AX_YEAR.lower()}{C.THIN_SPACE}{y}"
                 f"<br>{C.AX_WORKS.lower()}{C.THIN_SPACE}{_fmt_vol(v)}"
                 for y, v in zip(years, vals)]
        fig.add_trace(go.Bar(
            x=years, y=vals, name=dname,
            marker=dict(color=P.domain_color(did), line=dict(color=P.SURFACE, width=C.HAIRLINE_PX)),
            customdata=hovers, hovertemplate="%{customdata}<extra></extra>"))
    fig.update_layout(barmode="stack")

    # The annotation's `x` is the category's INTEGER INDEX, never its string
    # label -- measured live (progress/C2.md): `add_annotation(x="2020",.)`
    # against a `type="category"` axis collapses every category to one slot
    # and strands the annotation off past the plot's right edge on this
    # pinned plotly (5.24.1), the same class of annotation-positioning quirk
    # `_tick_display`'s own fix note (charts.py) already warns about for
    # `xref="paper"`. The index addresses the SAME category slot the bar
    # traces (given as label strings) already occupy.
    totals = d.groupby("_year")["vol"].sum()
    for idx, y in enumerate(years):
        fig.add_annotation(x=idx, y=float(totals.get(y, 0.0)), text=_fmt_vol(totals.get(y, 0.0)),
                           showarrow=False, yanchor="bottom", yshift=4,
                           font=dict(size=C.GUTTER_FONT_PX, color=P.INK_SECONDARY))

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=years,
                     title_text=C.AX_YEAR, gridcolor=P.GRID, linecolor=P.BORDER)
    fig.update_yaxes(title_text=C.AX_WORKS, rangemode="tozero",
                     gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER,
                     automargin=True, title_standoff=6)
    fig = C._base_layout(fig, YEARLY_STACK_HEIGHT_PX,
                         margin=dict(t=YEARLY_STACK_TOP_MARGIN_PX, l=8, r=16, b=C.BASE_PX))
    # `_base_layout` sets `showlegend=False` for every OTHER builder in this
    # module (the shared chip-strip convention) -- re-enabled here, AFTER
    # that shared call, for this one chart only (see the docstring above).
    fig.update_layout(showlegend=True, legend=dict(
        orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0.0,
        font=dict(size=C.GUTTER_FONT_PX, color=P.INK_SECONDARY)))
    return fig


# ---------------------------------------------------------------------------
# 5. reciprocity_bars -- "strategic reciprocity by field" (D7), adapted from
#    's views_collab._reciprocity_chart + collab_data.reciprocity_frame
# ---------------------------------------------------------------------------
GUTTER_HEADER_JOINT = "Joint publications"
AX_RECIPROCITY = "Share of each institution's own output in the field"
RECIPROCITY_HOVER_BASE = ("{field}: {share_a} of {name_a}'s output, {share_b} of {name_b}'s; "
                          "{joint} joint publications")
RECIPROCITY_HOVER_RANK = "{other_name} is {this_name}'s partner #{rank} here"


def reciprocity_bars(frame: pd.DataFrame, names: Sequence, colors: Sequence) -> go.Figure:
    """"Strategic reciprocity by field" (D7). ADAPTED from 's
    `views_collab._reciprocity_chart` + `collab_data.reciprocity_frame`
    (BenchUp, itself a Lorraine "Zoom partenaire" port): the ORIGINAL drew
    one bubble per field on a `x` = field's share of B's own corpus, `y` =
    the same for A, area = joint volume, colour = OA domain SCATTER, with a
    dotted equal-weight diagonal.

    V4 keeps the same two numbers per field -- "how much of my OWN portfolio
    sits in this field" for A and for B -- but draws them as institution-
    coloured `fig_metric_bars` bars instead of a scatter, matching the rest
    of this file's convergence onto the bar-family chrome
    (CHROME_CONTRACT.md SS10) rather than adding a second chart grammar for
    one section. The field's OpenAlex domain, formerly the bubble's colour,
    survives as the row-label ACCENT GLYPH instead of a mark colour. Fields are drawn in
    DESCENDING joint-volume order (matching the original's own ranking),
    computed here rather than assumed of the caller.

    INPUT FRAME CONTRACT for C1 (wide: ONE ROW PER FIELD, not per
    institution -- revised in the C2 follow-up, 2026-09-03):
      field_id -- the field's id
      field_name -- the field's display name
      domain_id -- the field's OpenAlex domain (label accent only, never
                      a mark colour)
      vol_joint -- the pair's joint CORE-AR volume in that field -- drawn
                      ONCE per row in the LEFT gutter column (header "Joint
                      publications"), centred between the two institution
                      bars rather than repeated on each of them
      share_a -- that field's share of institution A's OWN corpus, 0-1
      share_b -- that field's share of institution B's OWN corpus, 0-1
      rank_in_a -- OPTIONAL: B's dense rank among ALL of A's OWN partners
                      by joint volume (1 = A's single largest partner)
                      feeds the "…is partner #N" clause on A's bar only;
                      omit the column (or leave a row's cell null) to drop
                      that clause for that row
      rank_in_b -- OPTIONAL: A's dense rank among ALL of B's OWN partners
                      feeds the "…is partner #N" clause on B's bar only

    `names`/`colors` are TWO-ITEM SEQUENCES `[a, b]`, the SAME convention
    `mirror_frontier` uses -- this frame carries no `institution_id` column
    to key a Mapping by. `colors` holds SLOT ints, resolved via
    `palette.institution_color`. No reference diamond is drawn (there is no
    natural European-mean benchmark for a pair-specific reciprocity read)."""
    required = ("field_id", "field_name", "domain_id", "vol_joint", "share_a", "share_b")
    for col in required:
        if col not in frame.columns:
            raise ValueError(f"missing column {col!r}")
    if len(names) < 2 or len(colors) < 2:
        raise ValueError("reciprocity_bars needs names=[a, b] and colors=[slot_a, slot_b]")

    d = frame.copy()
    d = d.sort_values("vol_joint", ascending=False, kind="mergesort").reset_index(drop=True)
    has_rank = "rank_in_a" in d.columns and "rank_in_b" in d.columns

    id_a, id_b = "__reciprocity_a__", "__reciprocity_b__"
    slots = {id_a: int(colors[0]), id_b: int(colors[1])}
    name_a, name_b = _name_of(names, None, index=0), _name_of(names, None, index=1)
    disp_names = {id_a: name_a, id_b: name_b}

    long_rows = []
    for _, r in d.iterrows():
        for iid, share_col in ((id_a, "share_a"), (id_b, "share_b")):
            long_rows.append(dict(row_id=r["field_id"], row_label=r["field_name"],
                                  domain_id=r["domain_id"], institution_id=iid,
                                  value=r[share_col]))
    long_df = pd.DataFrame(long_rows)

    fig = fig_metric_bars(
        long_df, "share",
        slots=slots, names=disp_names, level="field", sort="taxonomy",
        value_col="value", label_col="row_label", key_col="row_id",
        gutter=False, metric_label=AX_RECIPROCITY,
    )
    _add_centred_gutter(fig, d, GUTTER_HEADER_JOINT)
    _rewrite_reciprocity_hover(fig, d, name_a, name_b, colors, has_rank)
    return fig


def _add_centred_gutter(fig: go.Figure, rows: pd.DataFrame, gutter_header: str) -> None:
    """ONE phantom gutter column, centred on each row (not one per
    institution lane): `reciprocity_bars`'s own `vol_joint` is a FIELD fact,
    the SAME number on both of a row's bars, so C2's follow-up asks for it
    drawn once rather than `fig_metric_bars`'s per-series repeat -- built
    here, on `fig_metric_bars(gutter=False,.)`'s own output, rather than
    inside that shared primitive (`two_tab_bars` still needs the per-series
    form unchanged)."""
    vmax = float(pd.concat([rows["share_a"], rows["share_b"]]).max())
    vmax = vmax if np.isfinite(vmax) and vmax > 0 else 1.0
    neg_extent = vmax * GUTTER_NEG_AXIS_FRAC
    gutter_x = -neg_extent * GUTTER_TIP_FRAC
    pad = vmax * AXIS_PAD_FRAC
    n = len(rows)
    fig.add_trace(go.Bar(
        x=[gutter_x] * n, y=list(range(n)), orientation="h",
        marker=dict(color=[GUTTER_PHANTOM_FILL] * n, line=dict(width=0)),
        text=[_gutter_value(v) for v in rows["vol_joint"]],
        textposition="outside", cliponaxis=False,
        textfont=dict(size=C.GUTTER_FONT_PX, color=P.INK_SECONDARY),
        customdata=[""] * n, hoverinfo="skip", showlegend=False))
    fig.update_xaxes(range=[-neg_extent, vmax + pad], tickmode="array",
                     tickvals=C._nice_ticks(vmax))
    fig.add_annotation(x=gutter_x, xref="x", y=1.0, yref="y domain",
                       xanchor="right", yanchor="bottom", text=gutter_header,
                       showarrow=False, font=dict(size=C.GUTTER_FONT_PX, color=P.INK_SECONDARY))


def _rewrite_reciprocity_hover(fig: go.Figure, rows: pd.DataFrame, name_a: str, name_b: str,
                               colors: Sequence, has_rank: bool) -> None:
    """Replaces `fig_metric_bars`'s generic hover skeleton on the two REAL
    bar traces with one plain-English sentence naming the field's share of
    EACH institution's own output plus the pair's joint count in that field
    -- the same full fact on both of a row's bars, so the words never depend
    on which of the two the reader happens to be pointing at. A trailing
    partner-rank clause is still appended per bar (A's bar reads
    `rank_in_a`, B's reads `rank_in_b`) since that fact IS bar-specific.
    Traces are matched by their OWN fill colour (deterministic:
    `palette.institution_color(colors[0])`/`[1]`) rather than by add-order,
    since `fig_metric_bars` orders traces by ascending SLOT, not by A/B
    position."""
    color_a = P.institution_color(int(colors[0]))
    color_b = P.institution_color(int(colors[1]))
    for tr in fig.data:
        if not isinstance(tr, go.Bar) or not tr.marker or not tr.marker.color:
            continue
        mcolor = tr.marker.color[0] if isinstance(tr.marker.color, (list, tuple)) else tr.marker.color
        if mcolor == color_a:
            rank_col, this_name, other_name = "rank_in_a", name_a, name_b
        elif mcolor == color_b:
            rank_col, this_name, other_name = "rank_in_b", name_b, name_a
        else:
            continue
        hovers = []
        for ri in tr.y:
            r = rows.iloc[int(ri)]
            sentence = RECIPROCITY_HOVER_BASE.format(
                field=r["field_name"], share_a=_fmt_pct(r["share_a"]), name_a=name_a,
                share_b=_fmt_pct(r["share_b"]), name_b=name_b, joint=_gutter_value(r["vol_joint"]))
            if has_rank and pd.notna(r.get(rank_col)):
                sentence += "; " + RECIPROCITY_HOVER_RANK.format(
                    other_name=other_name, this_name=this_name, rank=int(r[rank_col]))
            hovers.append(sentence)
        tr.customdata = hovers


# ---------------------------------------------------------------------------
# 6. Presentation primitives -- the chip legend, the reading line, the
#    best-value dot. Page-level helpers, not builders; kept unchanged.
# ---------------------------------------------------------------------------
def legend_strip(ids: Sequence, *, slots: Mapping, names: Mapping | None = None,
                 shared: bool = False, shared_label: str = LABEL_SHARED,
                 extra: Sequence | None = None) -> str:
    """The institution chip strip, in slot order, for the ids actually drawn
    mandatory ABOVE EVERY Compare chart (CHROME_CONTRACT.md SS4): it is
    the secondary encoding the palette's own accessibility validation obliges.

    `shared=True` appends the `palette.SHARED_FRONTIER` chip -- the caller
    for `mirror_frontier`'s own legend. `extra` takes further `(label, hex)`
    chips; the hex must still come from `lib.palette`."""
    order = sorted(dict.fromkeys(ids), key=lambda i: (_slot_of(slots, i), str(i)))
    items = [(_name_of(names, i), P.institution_color(_slot_of(slots, i)),
              P.institution_ink(_slot_of(slots, i))) for i in order]
    if shared:
        items.append((shared_label, P.SHARED_FRONTIER, P.SHARED_FRONTIER))
    items.extend([(str(a), str(b), P.INK_SECONDARY) for a, b in (extra or [])])
    return _chip_strip(items)


def _chip_strip(items: Sequence[tuple[str, str, str]]) -> str:
    """`charts.chip_legend_html` with a THIRD column: the ink each label is
    written in -- the institution fills sit at low contrast on white, so the
    NAME is written in that institution's dark twin instead of the shared
    secondary ink, making the chip and its label read as one object."""
    chips = "".join(
        f'<span style="display:inline-flex;align-items:center;'
        f'margin-right:{C.CHIP_MARGIN_PX}px;">'
        f'<span style="width:{C.CHIP_PX}px;height:{C.CHIP_PX}px;background:{_esc(hexcol)};'
        f'border-radius:{C.CHIP_RADIUS_PX}px;margin-right:{C.CHIP_GAP_PX}px;"></span>'
        f'<span style="font-size:{C.FONT_PX}px;color:{_esc(ink)};">{_esc(label)}</span>'
        f'</span>'
        for label, hexcol, ink in items
    )
    return (f'<div style="display:flex;flex-wrap:wrap;gap:{C.HAIRLINE_PX}px;'
            f'margin:{C.CHIP_GAP_PX}px {C.NO_PX}px;">{chips}</div>')


def chart_note(reading: str, tooltip: str | None = None) -> str:
    """ONE short reading line under a chart, with the methodology folded into
    a `?` the reader can hover (CHROME_CONTRACT.md SS6). A `reading` longer
    than `NOTE_MAX_CHARS`, or one containing a line break, raises
    `ValueError` -- no wall-of-prose fallback. The tooltip has no cap."""
    text = " ".join(str(reading).split())
    if not text:
        raise ValueError("a chart note needs a reading line")
    if "\n" in str(reading).strip() or len(text) > NOTE_MAX_CHARS:
        raise ValueError(f"a chart note is ONE short line of at most "
                         f"{NOTE_MAX_CHARS} characters; put the rest in the "
                         f"tooltip (got {len(text)})")
    help_span = ""
    if tooltip:
        payload = " ".join(str(tooltip).split())
        help_span = (
            f'<span title="{_esc(payload)}" role="note" '
            f'style="display:inline-flex;align-items:center;justify-content:center;'
            f'width:{C.FONT_PX}px;height:{C.FONT_PX}px;margin-left:{DOT_GAP_PX}px;'
            f'border:{C.HAIRLINE_PX}px solid {P.BORDER};border-radius:{C.FONT_PX}px;'
            f'font-size:{C.GUTTER_FONT_PX}px;color:{P.INK_SECONDARY};'
            f'cursor:help;">{NOTE_HELP_GLYPH}</span>')
    return (f'<div style="display:flex;align-items:center;'
            f'font-size:{C.FONT_PX}px;color:{P.INK_SECONDARY};'
            f'margin:{C.CHIP_GAP_PX}px {C.NO_PX}px;">'
            f'<span>{_esc(text)}</span>{help_span}</div>')


def basis_caption(text: str, *, warn: bool = False) -> str:
    """The ratio-chart basis/floor/coverage line -- ONE per chart, directly
    under the section title, above the legend and the chart
    (CHROME_CONTRACT.md SS7). `warn=True` (a floor bites, or a taxon is
    unscored) switches the colour to `palette.WARNING_CAPTION_COLOR` -- red,
    NEVER bold, never a `st.warning`/`st.error` banner."""
    color = P.WARNING_CAPTION_COLOR if warn else P.INK_SECONDARY
    return (f'<div style="font-size:{C.FONT_PX}px;font-weight:{CAPTION_FONT_WEIGHT};'
            f'color:{color};margin:{C.CHIP_GAP_PX}px {C.NO_PX}px;">{_esc(text)}</div>')


def best_value_dot(slot, label: str | None = None) -> str:
    """The Compare overview card's leader mark: a small dot in the LEADING
    institution's colour, optionally followed by that institution's name in
    its dark twin. `slot` is the zero-based institution slot,
    so the dot on a card and the bar in the chart below it cannot disagree."""
    dot = (f'<span style="display:inline-block;width:{DOT_HTML_PX}px;'
           f'height:{DOT_HTML_PX}px;border-radius:{DOT_HTML_PX}px;'
           f'background:{P.institution_color(slot)};'
           f'border:{P.OUTLINE_WIDTH}px solid {P.SURFACE};"></span>')
    if not label:
        return dot
    return (f'<span style="display:inline-flex;align-items:center;'
            f'gap:{DOT_GAP_PX}px;font-size:{C.GUTTER_FONT_PX}px;'
            f'color:{P.institution_ink(slot)};">{dot}'
            f'<span>{_esc(label)}</span></span>')
