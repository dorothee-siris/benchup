"""BenchUp -- pure Plotly figure builders for the Compare page.

Same house rules as `lib/charts.py`, enforced by the same kind of test
(`tests/test_charts_compare.py`): NO Streamlit import, NO `#RRGGBB` literal
anywhere in this file (every hue comes from `lib.palette`), NO digit inside a
STRING LITERAL other than a deployed parquet column name (`tests/
digit_allowlist.txt`, shared with the narrative digit-ban) -- a docstring is
exempt (prose for the reader of the source, never text the app renders).
`lib/views_compare.py` is the only place a figure built
here reaches a page; nothing in this module imports it.

WHAT THIS FILE KEEPS FROM THE OLD COMPARE DESIGN, AND WHY
-------------------------------------------------------------------
This redesign replaces the old six-institution dot-mirror / metric-
selector / pooled-scatter Compare page with a fixed TWO-institution page
(exactly two search slots) built from four sections: Thematic
shape, SDG profile, Shared frontier, The relationship.
Every one of those sections is now drawn with the SAME bar-family chrome
(`design-system/CHROME_CONTRACT.md` SS10 -- gutter column, solid institution-
coloured bars, red-dagger caution, diamond reference) already measured and
ratified as the one direction to converge the whole app on. `fig_metric_bars` -- that ratified primitive -- is KEPT, trimmed to the
two metrics the Thematic-shape and SDG-profile charts actually need (`share`,
`pp`; the old Dynamics/SDG-tagged/Specialisation/Volume/FWCI metric-selector
tabs are retired along with the selector UI they served). `two_tab_bars`
below is a thin adapter onto it -- no new bar-drawing code, reusing the
existing primitive instead. Strategic reciprocity by field is drawn by its
own `reciprocity_scatter`, a bubble scatter (below), not this primitive.

`legend_strip` / `map_legend_strip` / `chart_note` / `basis_caption` /
`best_value_dot` are also kept: page-level presentation primitives, not
builders, still exactly what needs for the fold-and-caption pattern
CHROME_CONTRACT.md SS0/SS6 name as the app's one convention to converge on.

WHAT IS DELETED, AND WHY
-----------------------------------------------------------------
The pooled frontier scatter and its "who holds the shared frontier" diverging
bar (`fig_frontier_map`, `fig_diverging_shared`) are gone -- the shared
frontier's mirror chart below replaces both. The dot-mirror family
(`fig_mirror_dots`, `fig_quadrant_mix`, the whole lane-dodge mechanism) is
gone -- the Thematic-shape and SDG-profile charts draw bars, not dots. The
frontier overlay/small-multiples scatters (`fig_frontier_overlay`,
`fig_frontier_small_multiples`) are gone -- ERC panels and the
pooled/per-institution frontier scatter are both excluded from this page.
The impact dot-interval builders (`fig_impact_intervals`,
`fig_impact_subfields`) are gone -- the impact-by-subfield interval section
is excluded from this page; the Thematic-shape chart's Impact tab covers
this ground as a `two_tab_bars` call instead. `fig_pulse` (joint
publications per year, one undifferentiated series) is gone -- the
relationship section replaces it with `yearly_domain_stack`, the same
figure stacked by OpenAlex domain.
`RATIO_HATCH_METRICS`'s bar-pattern-fill remnants (`LOW_VOLUME_PATTERN_SHAPE`/
`LOW_VOLUME_PATTERN_SOLIDITY`) lost their one remaining caller (`fig_pulse`)
and are deleted with it -- the hatch-fill mechanism was already retired from
every OTHER bar in this module, so no hatch remnant survives anywhere in the
file now.

THE BUILDERS IN THIS MODULE
----------------------------
  1. `two_tab_bars` -- the Thematic-shape and SDG-profile charts.
                         A thin `fig_metric_bars` adapter: tab="profile" is
                         metric="share", tab="impact" is metric="pp".
  2. `yearly_domain_stack` -- the relationship section's yearly stack: joint
                         publications 2020-2024 by OpenAlex domain.
  3. `reciprocity_scatter` -- "strategic reciprocity by field", a bubble
                         SCATTER: `y` = a field's share of A's own corpus,
                         `x` = the same for B, area = joint volume, colour =
                         the field's OpenAlex domain, one dotted equal-
                         weight diagonal, squared axes -- a port of an
                         earlier SIRIS Streamlit tool's own "Zoom partenaire"
                         view (credited in its own docstring), which this
                         page drew as institution-coloured bars in between
                         (`reciprocity_bars`, retired with its own
                         `_add_centred_gutter`/`_rewrite_reciprocity_hover`
                         helpers) before returning to the original reading.
  The topic-overlap scatter and balance bars draw from `lib.
  charts_topics` instead -- a separate module by design, so a Compare-side
  edit here can never collide with a concurrently-edited topic-plane change
  (see that module's own docstring).

`colors`, everywhere in this module (`two_tab_bars`,
`reciprocity_scatter`), is the institution SLOT mapping/sequence -- i.e.
exactly what the app's institution-slot map returns (`{institution_id:
slot}` for the Mapping-shaped builder; `[slot_a, slot_b]` for
`reciprocity_scatter`, whose frame carries no `institution_id` column at
all to key a Mapping by). It is named `colors` rather than `slots` because
that is ALL a slot ever is in this module -- an index `palette.
institution_color`/`institution_ink` resolve to a hex -- and every
builder's own docstring repeats this so a caller never has to
cross-reference this paragraph.
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
    """`names` is usually a Mapping keyed by institution id; `reciprocity_
    scatter` also accepts a two-item Sequence (`[name_a, name_b]`, no id to
    key by) -- `index` picks the positional entry in that case."""
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
                     showgrid=False, automargin=True,
                     tickfont=dict(size=C.TICK_FONT_PX), **kw)


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
CAPTION_FONT_WEIGHT = 400      # (CHROME_CONTRACT.md SS7): the basis caption
                              # is NEVER bold, in either colour state

# Row-label accent, gutter geometry and the bar-layout contract's other
# shared numbers are SINGLE-SOURCED in `lib/charts.py` now (`ACCENT_GLYPH`/
# `ACCENT_GAP`, `GUTTER_NEG_AXIS_FRAC`/`GUTTER_TIP_FRAC`/`GUTTER_PHANTOM_FILL`,
# `LABEL_COL_PX`/`GUTTER_COL_PX`/`COL_PAD_PX`/`WRAP_PX`, `TICK_FONT_PX`,
# `ROW_PITCH_PAIR`/`BAR_PX_PAIR`/`PAIR_GROUP_SPAN`/`PAIR_GROUP_FILL`) --
# referenced here as `C.<name>` rather than kept as a second copy.

LABEL_SHARED = "shared"
NOTE_HELP_GLYPH = "?"

# --- the bar-family contract (CHROME_CONTRACT.md SS10): gutter column + a
#     dashed red reference tick, never a diamond any more -----------------
COMPARE_MAX_SERIES = 3        # headroom above Compare's fixed pair (two search
                              # slots) -- `_series_ids` refuses a
                              # figure rather than truncate past this

LOW_VOLUME_FLOOR = 10.0
# A cell whose mean annual FULL volume is below this is drawn cautioned
# equals `palette.RATIO_HATCH_FLOOR` (50) over the 5-year CORE-AR window, the
# same threshold in different units (the one-sentence user-facing rule stays
# true either way: "cautions under fifty works over the counted window").
RATIO_HATCH_METRICS = ("pp",)
# `pp` hatches on its own per-row `denom_value` (n_covered) against
# `palette.RATIO_HATCH_FLOOR` directly -- the impact tab's own caution rule
# (the rule: "caution on impact rows with n_covered <
# fifty"). `share` (the profile tab) keeps the generic `low_vol_col` rule,
# which two_tab_bars's frame does not carry -- so the profile tab never
# cautions, matching the rule exactly.
LOW_VOLUME_GLYPH = "\N{DAGGER}"
HOVER_LOW_VOLUME = "rests on fewer than {floor} works over the counted window, read with care"

METRICS = ("share", "pp")
LEVELS = ("field", "subfield", "sdg")
REF_METRICS = ("share", "pp")
# Both draw a per-row dashed RED reference TICK (`_add_reference`) whenever the
# frame carries a `ref_value` -- the European-mean share, or the world PP10
# reference -- spanning that row's own band, x0 == x1 at the reference value.
SORT_MODES = ("taxonomy", "value")
# `taxonomy` (the default) keeps the frame's OWN row order, grouped under a
# domain separator when `domain_col` is present -- this is what "rows ordered
# as given, grouped under field headers" means concretely.
# `value` re-ranks by the value summed over the compared institutions.

AX_TOP_DECILE_SHARE = "Share of publications in the world top decile"
_METRIC_AXIS = {"share": C.AX_SHARE, "pp": AX_TOP_DECILE_SHARE}
# docs/tooltip_spec.yaml's own per-chart metric-value labels (`two_tab_bars`
# picks the right one by level/metric and passes it as `metric_label`,
# below the axis titles doubling as hover labels remains -- see
# `_metric_hover`'s own docstring): subfield/share, sdg/share, subfield/pp.
AX_SHARE_SUBFIELD = "share of publications"
AX_SHARE_SDG = "share of the institution's tagged output"
AX_PP_SUBFIELD = "world top-decile share, articles and reviews"
_METRIC_KIND = {"share": "pct", "pp": "pct"}
_KEY_COLS = {"sdg": ("sdg_idx", "sdg_number")}
_ACCENT_COLS = {"sdg": ("sdg_number", "sdg_idx"), "field": ("domain_id",),
                "subfield": ("domain_id",)}
_LEVEL_ACCENT_FAMILY = {"sdg": "sdg", "field": "oa", "subfield": "oa"}

HOVER_REF_SHARE = "European mean share"     # compare_thematic_profile / compare_sdg's own ref_value label
HOVER_REF_PP = "world reference"            # compare_thematic_impact's own ref_value label
HOVER_DENOMINATOR = "articles and reviews behind the share"
HOVER_FWCI_LABEL = "FWCI_EU, same window"
# docs/tooltip_spec.yaml's own label text for the SI line ("specialisation
# index") -- a LOCAL constant, not `charts.HOVER_SI` ("SI"): that shared
# constant lives in lib/charts.py, out of this stream's fence, so Compare's
# own spec-mandated wording is kept here instead of edited there.
HOVER_SI_LABEL = "specialisation index"
HOVER_FIELD_LABEL = "field"
# (`docs/tooltip_spec.yaml`'s `label_style: bold_colon`): every hover line
# past line 1 carries a label, including the two lines that used to have
# none at all -- the institution name (line 3 of `_metric_hover`, today's
# `label: ""`) and the low-volume caution line (today a bare dagger phrase).
HOVER_INSTITUTION_LABEL = "institution"
HOVER_CAUTION_LABEL = "caution"
HOVER_SHARE_OF_YEAR = "share of that year's joint output"
HOVER_LOW_VOLUME_SHARE = "rests on few publications a year, read with care"
HOVER_LOW_VOLUME_IMPACT = "fewer than {floor} articles and reviews behind the share, read with care"
# `subfields.parquet`'s own vol_full/vol_frac ARE the whole run already
# (find_subfields' own tooltip note); `sdg_frame`'s are the CORE window
# (its own documented, pre-existing choice, unchanged here) -- the two
# labels below name only WHAT differs (whole run vs a narrower one),
# never a digit year (this module's own digit-ban): the page's pin
# caption above every chart already states both windows in full.
HOVER_VOL_PAIR_SUBFIELD = "publications, whole run"
HOVER_VOL_PAIR_SDG = "tagged publications"


def _fmt_metric(v, metric: str) -> str:
    kind = _METRIC_KIND.get(metric, "vol")
    return _fmt_pct(v) if kind == "pct" else _fmt_vol(v)


def metric_row_height(n_rows: int, n_series: int, minimum: int = C.MIN_HEIGHT) -> int:
    """Figure height under the bar-layout contract: margins + `n_rows` at
    `ROW_PITCH_PAIR` (two-line labels are the norm that pitch already hosts,
    so there is no `n_wrapped` correction to fold in any more). `n_series`
    stays as a DEFENSIVE fallback only -- Compare's own fixed two-institution
    page never exceeds two series, and `PAIR_GROUP_FILL`/`PAIR_GROUP_SPAN`
    are solved so exactly two `BAR_PX_PAIR`-thick bars fit the pitch exactly
    -- but `COMPARE_MAX_SERIES` allows headroom to three, so a THIRD series
    (never exercised today) still gets a taller figure instead of a
    silently-squeezed bar."""
    n_rows = max(int(n_rows), 1)
    n_series = max(int(n_series), 1)
    base = C.row_height_pair(n_rows, minimum=minimum)
    if n_series <= 2:
        return base
    chrome = C.BASE_PX + C.BASE_PX // 2
    need = C.BAR_PX_PAIR * n_series / (C.PAIR_GROUP_SPAN * C.PAIR_GROUP_FILL)
    have = max(base - chrome, 0) / n_rows
    return base if have >= need else max(minimum, int(round(need * n_rows)) + chrome)


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
    """`(plain, styled)` tick strings, pixel-wrapped to <= two lines at
    `charts.WRAP_PX["compare"]` -- ONE wrap budget for the whole view, not
    one per taxonomy level (a per-level budget wrapped short labels far
    too early relative to the column they actually sit in; see `charts.
    WRAP_PX`'s own module-header note) -- with the taxonomy accent glyph,
    single-sourced now through `charts._tick_label` (Find's SDG panel uses
    the identical function for its own accent square). No accent is
    invented when the level has no official palette, or the frame carries
    no accent key."""
    family = _LEVEL_ACCENT_FAMILY.get(level)
    wrap_px = C.WRAP_PX["compare"]
    plain, styled = [], []
    for _, r in rows.iterrows():
        accent_hex = None
        if family and accent_col and accent_col in rows.index.names + list(rows.columns):
            accent_hex = P.label_accent_color(family, r[accent_col])
        text_plain, text_styled = C._tick_label(str(r[label_col]), wrap_px=wrap_px, accent_hex=accent_hex)
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


def _fmt_vol_pair(full, frac) -> str:
    """'vol_pair': the same measure on both counting bases, full first --
    '1 234 full - 512.4 fractional'. `charts._fmt_vol` already tells a
    whole count from a fractional one by its own value (no decimal unless
    the number itself has one), so the one formatter serves both slots."""
    return f"{_fmt_vol(full)} full - {_fmt_vol(frac)} fractional"


def _fmt_fwci_pair(mean, median, n) -> str | None:
    """'fwci_pair_2dp': 'mean 1.31 - median 0.98 on 54 works', both to two
    decimals (`charts._fmt_si`'s own two-decimal formatter -- never a raw
    f-string spec, which would plant a literal digit token this module's
    own digit-ban scans for); a dagger follows the work count under ten;
    the line is not drawn at all under three -- `None` tells the caller so."""
    n_val = _num(n)
    if not np.isfinite(n_val) or n_val < 3:
        return None
    dagger = LOW_VOLUME_GLYPH if n_val < 10 else ""
    return f"mean {_fmt_si(mean)} - median {_fmt_si(median)} on {_fmt_vol(n_val)}{dagger} works"


def _metric_hover(r, iid, names, label_col, value_col, metric, ref_col,
                  denom_value_col, metric_label, gutter_col: str | None = None,
                  low: bool = False, level: str | None = None,
                  y0: int | None = None, y1: int | None = None,
                  whole_y1: int | None = None) -> str:
    """`docs/tooltip_spec.yaml`'s `compare_thematic_profile` / `compare_
    thematic_impact` / `compare_sdg` entries, verbatim, in their own line
    order -- the ENTITY (the taxon's own row label) first, the field it
    belongs to second (when the frame carries one), the INSTITUTION third,
    then the metric's own reader lines.

    `level` ("subfield" or "sdg", `fig_metric_bars`'s own `level` local --
    threaded straight through, not re-derived) picks the few lines that
    genuinely differ between the two charts sharing this one builder:
      * the whole-run publications line's own LABEL (subfield: "publications,
        whole run {y0}-{whole_y1}" -- `subfields.parquet`'s own vol_full/
        vol_frac ARE whole-run already, so the exact window is stated; sdg:
        "tagged publications", no window stated -- `sdg_frame`'s own
        vol_full/vol_frac are a pre-existing CORE-window figure, unchanged
        here, so the label names only what the number IS rather than claim
        a whole-run window it is not);
      * the specialisation-index line (`compare_thematic_profile` alone --
        `compare_sdg`'s own spec carries no `si` line, even though the SDG
        frame still computes one for the untouched frontier/positioning
        code elsewhere -- this hover simply never asks for it on SDG rows).

    Metric alone decides the rest: `metric == "share"` (the Profile tab of
    either chart) draws the whole-run line and, on subfield rows only, the
    SI line, and its own reference is labelled "European mean share";
    `metric == "pp"` (the Impact tab, subfield only -- SDG has none) draws
    the covered-works denominator and the FWCI_EU line instead, and its own
    reference is labelled "world reference". The low-volume dagger's own
    explanatory sentence differs the same way (few publications a year, on
    Profile; fewer than the covered-works floor, on Impact)."""
    index = list(getattr(r, "index", []))
    parts = [C.hover_entity(str(r[label_col]))]                      # 1. the entity
    if "group_label" in index and pd.notna(r["group_label"]):
        parts.append(C.hover_line(HOVER_FIELD_LABEL, r["group_label"]))   # 2. its field
    parts.append(C.hover_line(HOVER_INSTITUTION_LABEL, _name_of(names, iid)))  # 3. the institution
    title = (metric_label or _METRIC_AXIS[metric]).lower()
    parts.append(C.hover_line(title, _fmt_metric(r[value_col], metric)))  # 4. the metric's own value

    if ref_col in index and metric in REF_METRICS and pd.notna(r.get(ref_col)):
        ref_label = HOVER_REF_PP if metric == "pp" else HOVER_REF_SHARE
        parts.append(C.hover_line(ref_label, _fmt_metric(r[ref_col], metric)))

    if metric == "share":
        if gutter_col and gutter_col in index and pd.notna(r.get(gutter_col)) and "vol_frac" in index:
            if level == "subfield" and y0 is not None and whole_y1 is not None:
                # whole-run: subfields.parquet's own vol_full/vol_frac ARE
                # the whole run already, so the whole-run window is stated.
                vol_label = f"{HOVER_VOL_PAIR_SUBFIELD} {y0}-{whole_y1}"   # a literal space WITHIN the label phrase
            elif level == "sdg" and y0 is not None and y1 is not None:
                # sdg_frame's own vol_full/vol_frac are the CORE window, not
                # whole-run (a pre-existing, documented choice, unchanged
                # here) -- the house rule ("a label states the perimeter
                # whenever it differs from the chart's own headline
                # perimeter") means this line must name THAT window, not
                # the whole-run one the share itself is denominated on.
                vol_label = f"{HOVER_VOL_PAIR_SDG}, {y0}-{y1}"
            else:
                vol_label = HOVER_VOL_PAIR_SUBFIELD if level == "subfield" else HOVER_VOL_PAIR_SDG
            parts.append(C.hover_line(vol_label, _fmt_vol_pair(r[gutter_col], r["vol_frac"])))
        if level == "subfield" and "si" in index and pd.notna(r["si"]):
            parts.append(C.hover_line(HOVER_SI_LABEL, _fmt_si(r["si"])))
    else:
        if denom_value_col in index and pd.notna(r.get(denom_value_col)):
            parts.append(C.hover_line(HOVER_DENOMINATOR, _fmt_vol(_num(r[denom_value_col]))))
        fwci_line = _fmt_fwci_pair(r.get("fwci_mean"), r.get("fwci_median"), r.get("n_covered_fwci"))
        if fwci_line:
            parts.append(C.hover_line(HOVER_FWCI_LABEL, fwci_line))

    if low:
        reason = (HOVER_LOW_VOLUME_IMPACT.format(floor=_fmt_vol(P.RATIO_HATCH_FLOOR)) if metric != "share"
                 else HOVER_LOW_VOLUME_SHARE)
        parts.append(C.hover_line(HOVER_CAUTION_LABEL, f"{LOW_VOLUME_GLYPH} {reason}"))
    return "<br>".join(p for p in parts if p is not None)


def _ref_line(fig: go.Figure, x: float) -> None:
    """ONE full-height dashed RED rule for a CONSTANT reference (a value the
    same in every row, e.g. SI/ESI = 1): a repeated tick on a value that
    never changes would be visual noise, not a benchmark, so the constant
    case stays a single rule spanning the whole panel (`add_vline`'s own
    default span)."""
    fig.add_vline(x=x, line=dict(color=P.WARNING_CAPTION_COLOR, width=C.LINE_PX, dash="dash"))


def _add_reference(fig: go.Figure, rows: pd.DataFrame, ref_col: str,
                   ref_value: float | None) -> None:
    """ONE full-height dashed RED rule for a CONSTANT reference (`_ref_line`),
    a dashed RED vertical TICK per row for a VARYING one -- `x0 == x1` at the
    reference value, spanning exactly that row's own band (`ri - 0.5` to
    `ri + 0.5`, the category-axis unit every row occupies): an index
    reference is a different number in every taxon, and drawing either a
    single line or a single row's worth of markers across the whole panel
    would assert a benchmark that does not exist for the other rows. A
    `go.Shape` line, not a marker trace -- no diamond, no hover of its own
    (the fact is already on the row's own hover line, `HOVER_REFERENCE`)."""
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
                for ri, v in enumerate(series.tolist()):
                    if not np.isfinite(v):
                        continue
                    fig.add_shape(type="line", x0=float(v), x1=float(v),
                                 y0=ri - 0.5, y1=ri + 0.5, xref="x", yref="y",
                                 line=dict(color=P.WARNING_CAPTION_COLOR,
                                           width=C.LINE_PX, dash="dash"))


# ---------------------------------------------------------------------------
# 1. The bar-family primitive (CHROME_CONTRACT.md SS10) -- kept unchanged,
#    trimmed to the two metrics the Thematic-shape and SDG-profile charts
#    need. `two_tab_bars` below is its only caller in this module now
#    (strategic reciprocity by field draws its own scatter, further down).
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
    low_vol_col: str = "vol_full_annual_mean",
    domain_col: str = "domain_id",
    domain_order_col: str = "domain_order",
    y0: int | None = None,
    y1: int | None = None,
    whole_y1: int | None = None,
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

    THE GUTTER COLUMN (bar-layout contract, CHROME_CONTRACT.md SS10.1).
    `gutter=True` (the default) draws a dedicated LEFT column: one phantom,
    zero-visible-fill `go.Bar` trace per institution, in the SAME lane as its
    real bar, at a small negative x (`charts.GUTTER_NEG_AXIS_FRAC` of the
    data span) with its own raw `gutter_col` value as text, pushed further
    left by `textposition="outside"`. **No header above the column any more**
    -- the earlier per-chart basis label ("Publications, full count") is
    retired; the basis is stated once, in the section's own caption, not
    repeated over every chart. Below roughly 600 px of plot width the column
    has nowhere to go (a wrapped first-row label alone can need most of a
    390 px figure); pass `gutter=False` and the raw value stays in hover
    alone -- never a horizontal scroll either way.

    THE CAUTION CHANNEL (CHROME_CONTRACT.md SS10.2). Every bar is SOLID,
    in the institution's own colour. A cell `_is_low_volume` flags switches
    its value text AND its gutter text to `palette.WARNING_CAPTION_COLOR`
    (never bold) and keeps `LOW_VOLUME_GLYPH` (a dagger) -- disclosure, never
    suppression: the bar is still drawn at full size, only the ink that
    prints its own number changes.

    ENCODING. Bar = institution (ascending
    `inst_key` via `slots`). Row label = the taxon; for SDG (and, generally,
    field/subfield) it carries a glyph in the taxonomy's official colour -- taxonomy colour on labels,
    institution colour on marks, never the reverse.

    REFERENCE (bar-layout contract, CHROME_CONTRACT.md SS10.3). Only
    `REF_METRICS` (`share`, `pp`) draw one, from the frame's OWN `ref_value`
    column. A reference that VARIES by row is a dashed RED vertical TICK per
    row (`x0 == x1` at the reference value, spanning that row's own band --
    replaces the earlier diamond marker); one that is the SAME for every row
    stays ONE full-height dashed red rule across the panel.

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
        neg_extent = basis * C.GUTTER_NEG_AXIS_FRAC
        gutter_x = -neg_extent * C.GUTTER_TIP_FRAC

    fig = go.Figure()
    _row_rules(fig, n, boundaries)
    if metric in REF_METRICS or ref_value is not None:
        _add_reference(fig, rows, ref_col, ref_value)

    for k, iid in enumerate(series):
        offset, bar_w = C._series_offset_width(len(series), k, C.PAIR_GROUP_SPAN,
                                               C.PAIR_GROUP_FILL)
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
                                        metric_label, gutter_col, low, level,
                                        y0=y0, y1=y1, whole_y1=whole_y1))
            if gutter_active and gutter_col in r.index:
                gy.append(ri)
                gtexts.append(_gutter_value(r[gutter_col]))
                ginks.append(caution)
        fig.add_trace(go.Bar(
            x=xs, y=ys, orientation="h", offset=offset, width=bar_w,
            marker=dict(color=[color] * len(xs), line=dict(color=color, width=C.HAIRLINE_PX)),
            text=texts, textposition="outside", cliponaxis=False,
            textfont=dict(size=C.GUTTER_FONT_PX, color=inks), constraintext="none",
            customdata=hovers, hovertemplate="%{customdata}<extra></extra>",
            showlegend=False))
        if gy:
            fig.add_trace(go.Bar(
                x=[gutter_x] * len(gy), y=gy, orientation="h", offset=offset, width=bar_w,
                marker=dict(color=[C.GUTTER_PHANTOM_FILL] * len(gy), line=dict(width=0)),
                text=gtexts, textposition="outside", cliponaxis=False,
                textfont=dict(size=C.GUTTER_FONT_PX, color=ginks), constraintext="none",
                customdata=[""] * len(gy), hoverinfo="skip", showlegend=False))

    fig.update_layout(barmode="overlay", bargap=0)
    # No header above the gutter column (bar-layout contract) -- the basis
    # is stated once in the section's own caption, never repeated per chart.

    plain, styled = _accent_ticktext(rows, level, label_col, accent_col)
    _y_axis(fig, n, styled)
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
    # bar-layout contract: a CONSTANT margin -- the whole label universe,
    # never this frame's own longest name -- so every Compare bar chart
    # starts its bars at the identical pixel (`fig_share_si`'s own note).
    margin_l = C.LABEL_COL_PX["compare"] + C.GUTTER_COL_PX["compare"] + C.COL_PAD_PX
    return C._base_layout(fig, metric_row_height(n, len(series)),
                          margin=dict(t=C.BASE_PX // 2, l=margin_l,
                                      r=C.BASE_PX, b=C.BASE_PX))


# ---------------------------------------------------------------------------
# 2. two_tab_bars -- the Thematic-shape and SDG-profile charts
# ---------------------------------------------------------------------------
TWO_TAB_TABS = ("profile", "impact")


def two_tab_bars(
    frame: pd.DataFrame,
    tab: str,
    names: Mapping,
    colors: Mapping,
    *,
    grouped_by_field: bool,
    gutter: bool = True,
    y0: int | None = None,
    y1: int | None = None,
    whole_y1: int | None = None,
) -> go.Figure:
    """The pair's Thematic-shape chart (`grouped_by_field=True`, top-20
    subfields by combined volume) and SDG-profile chart
    (`grouped_by_field=False`, all seventeen goals) -- one call site, one tab
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
      ref_value -- the reference: the European-mean share (profile) or the
                       world PP10 reference (impact), drawn as a dashed red
                       vertical tick spanning its row; omit the column, or
                       leave a row's cell null, for no reference on that row
      vol_full -- full-counted publication count, int -- drawn in the
                       LEFT gutter column (the pinned basis -- bestfit + full
                       counting -- is named once in the section's own
                       caption, not repeated as a per-chart header any more)
      n_covered -- covered-works denominator for the impact tab; a
                       row with `n_covered` under `palette.RATIO_HATCH_FLOOR`
                       (fifty) gets the red dagger caution -- ignored on the
                       profile tab (the Thematic-shape chart never cautions Share)
      si, fwci_median, vol_frac -- optional hover-only extras (`_metric_hover`)
      domain_id -- OPTIONAL, OpenAlex domain id of the taxon's FIELD.
                       When present, drives TWO things at once, both existing
                       mechanisms this builder does not invent: a small domain-coloured
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
    # docs/tooltip_spec.yaml: the metric's OWN value line carries a
    # chart-specific label, not the generic axis title `_METRIC_AXIS`
    # falls back to when none is given -- subfield/share ("share of
    # publications"), sdg/share ("share of the institution's tagged
    # output"), subfield/pp ("world top-decile share, articles and
    # reviews {y0}-{y1}", the ONE line that also states its own window
    # since it differs from the Profile tab's whole-run one).
    if level == "sdg":
        metric_label = AX_SHARE_SDG
    elif metric == "share":
        metric_label = AX_SHARE_SUBFIELD
    elif y0 is not None and y1 is not None:
        metric_label = f"{AX_PP_SUBFIELD} {y0}-{y1}"   # a literal space WITHIN the label phrase itself
    else:
        metric_label = AX_PP_SUBFIELD
    return fig_metric_bars(
        frame, metric,
        slots=colors, names=names, level=level, sort="taxonomy",
        value_col="value", label_col="row_label", key_col="row_id",
        ref_col="ref_value", denom_value_col="n_covered",
        gutter=gutter, gutter_col="vol_full", metric_label=metric_label,
        domain_col=domain_col, domain_order_col="__ungrouped_order__",
        y0=y0, y1=y1, whole_y1=whole_y1,
    )


# ---------------------------------------------------------------------------
# 4. yearly_domain_stack -- the relationship section's yearly stack
# ---------------------------------------------------------------------------
YEARLY_STACK_HEIGHT_PX = 500  # doubled (and a little) from the pre-trim 320 px
YEARLY_STACK_TOP_MARGIN_PX = C.BASE_PX * 2
# Room for the native horizontal legend ABOVE the plot area, on
# top of the year-total annotations that already sit just above each bar
# (unchanged, still inside the plot itself -- the legend sits in the MARGIN,
# a separate band).


def yearly_domain_stack(frame: pd.DataFrame) -> go.Figure:
    """Joint publications per year, stacked by the four OpenAlex domains
    (this module's replacement for the single-series `fig_pulse`, credited
    in this module's own docstring). Domain colours are `palette.OA_DOMAIN_COLORS`
    (`palette.domain_color`), in `palette.OA_DOMAIN_ORDER` -- no institution
    identity here, matching the relationship section's own "pooled" reading
    of a pair's joint corpus rather than either side's.

    INPUT FRAME CONTRACT (one row per year x domain):
      year -- the calendar year
      domain_id -- an OpenAlex domain id, 1-4
      domain_name -- the domain's display name
      vol -- joint publications in that domain that year (int)

    A year's TOTAL (summed across domains) is written as text ABOVE its bar.

    This is the ONE chart in this module
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
        year_totals = d.groupby("_year")["vol"].sum()
        shares = [(v / t) if (t := float(year_totals.get(y, 0.0))) > 0 else float("nan")
                 for y, v in zip(years, vals)]
        hovers = [f"{C.hover_entity(dname)}<br>{C.hover_line(C.AX_YEAR.lower(), y)}"
                 f"<br>{C.hover_line(C.AX_WORKS.lower(), _fmt_vol(v))}"
                 f"<br>{C.hover_line(HOVER_SHARE_OF_YEAR, _fmt_pct(s))}"
                 for y, v, s in zip(years, vals, shares)]
        fig.add_trace(go.Bar(
            x=years, y=vals, name=dname,
            marker=dict(color=P.domain_color(did), line=dict(color=P.SURFACE, width=C.HAIRLINE_PX)),
            customdata=hovers, hovertemplate="%{customdata}<extra></extra>"))
    fig.update_layout(barmode="stack")

    # The annotation's `x` is the category's INTEGER INDEX, never its string
    # label -- measured live: `add_annotation(x="2020",.)`
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
# 5. reciprocity_scatter -- "strategic reciprocity by field", a port of an
#    earlier SIRIS Streamlit tool's own "Zoom partenaire" bubble scatter
#    (credited in this module's own header docstring).
# ---------------------------------------------------------------------------
RECIP_AXIS_PAD_MULT = 1.1    # squared axes [0, max * 1.1] on both sides
RECIP_DIAGONAL_DASH = "dot"
RECIP_BUBBLE_OUTLINE_PX = 0.5
AX_RECIPROCITY_SHARE = "Share of {name}'s own publications"
AX_RECIPROCITY_SHARE_SUBFIELD = "Share of {name}'s own publications (subfield)"
HOVER_RECIP_SHARE = "share of {name}'s own publications"
HOVER_RECIP_JOINT = "joint publications"
HOVER_RECIP_PP10 = "joint papers in the world top decile"
HOVER_RECIP_STARS = "joint star papers in this field"
HOVER_RECIP_STARS_SUBFIELD = "joint star papers in this subfield"
HOVER_PARTNER_RANK_LABEL = "partner rank"    # the partner-rank sentence(s)
                                              # had no label at all before
HOVER_RECIP_FIELD_LABEL = "field"            # subfield grain only: the
                                              # subfield's parent field, one
                                              # bold-colon line right after
                                              # the bold subfield name
RECIPROCITY_GRAINS = ("fields", "subfields")


def reciprocity_scatter(frame: pd.DataFrame, names: Sequence, colors: Sequence,
                        grain: str = "fields") -> go.Figure:
    """"Strategic reciprocity", BACK to the bubble SCATTER an
    earlier SIRIS Streamlit tool's own "Zoom partenaire" view drew (this
    module's own header docstring): one bubble per field OR subfield
    (`grain`), `y` = that taxon's share of A's OWN output, `x` = the same
    taxon's share of B's OWN output, area = the pair's joint volume there
    (area-true: `sizemode="area"`, one `sizeref` shared by every bubble),
    colour = the taxon's OpenAlex domain, one dotted 45-degree "equal
    weight" diagonal, squared axes (`scaleanchor` locking the aspect ratio
    so the square is real, not just numerically equal ranges). Replaces the
    institution-coloured bar adaptation this page drew in between
    (`reciprocity_bars`, retired with its own `_add_centred_gutter`/
    `_rewrite_reciprocity_hover` helpers) -- there is no institution-
    coloured mark on this chart at all any more, matching the ORIGINAL
    reading exactly.

    `grain="fields"` (default) -- INPUT FRAME CONTRACT (one row per field),
    BYTE-IDENTICAL to every version of this function before the subfield
    grain existed:
      field_id, field_name, domain_id -- identity + the bubble's own colour
      share_a, share_b -- that field's share of A's / B's own output, 0-1
                      -- the vertical / horizontal axis respectively
      vol_joint -- the pair's joint CORE-AR volume in the field -- the
                      bubble's own area
      fwci_mean, fwci_median, n_fwci -- the joint papers' own FWCI_EU
                      (drawn from n_fwci >= 3, daggered under ten)
      n_top10, n_covered -- the joint papers' own world-top-decile count
                      and its covered-works denominator; PP10_WD is
                      `n_top10 / n_covered`, computed here, never stored
                      as a ratio (daggered under ten covered works, and
                      simply omitted when there are none at all)
      n_stars_field -- joint star papers in the field
      rank_in_a, rank_in_b -- OPTIONAL: the pair's own partner rank (a
                      PAIR-level fact, `collab_pairs.rank_in_a`/`rank_in_b`,
                      the same on every row) -- omit the columns, or leave
                      a row's cells null, to drop the clause entirely

    `grain="subfields"` -- the SAME contract, plus `subfield_name`
    (required) naming each bubble; `field_name` then names the subfield's
    PARENT field, printed as its own `<b>field</b>: {name}` hover line right
    after the bold subfield-name entity line. Axis titles say "subfield"
    instead of "field". The partner-rank clause (`rank_in_a`/`rank_in_b`) is
    DROPPED at this grain even when the columns are present -- a pair-level
    fact already shown on the field-grain chart, traded for the one extra
    line the field-name context costs, to hold the 8-line hover cap that
    holds everywhere else.

    `names`/`colors` are TWO-ITEM SEQUENCES `[a, b]` (this module's own
    fixed-pair convention, see the module docstring's `colors` paragraph)
    -- this frame carries no `institution_id` column to key a Mapping by.
    `colors` is accepted for that same signature
    parity but unused for the MARK colour here (the taxon's domain is the
    only colour channel this chart draws)."""
    if grain not in RECIPROCITY_GRAINS:
        raise ValueError(f"grain must be one of {RECIPROCITY_GRAINS}, got {grain!r}")
    subfield_grain = grain == "subfields"
    required = ["domain_id", "share_a", "share_b", "vol_joint"]
    required.append("subfield_name" if subfield_grain else "field_name")
    for col in required:
        if col not in frame.columns:
            raise ValueError(f"missing column {col!r}")
    if len(names) < 2 or len(colors) < 2:
        raise ValueError("reciprocity_scatter needs names=[a, b] and colors=[slot_a, slot_b]")

    d = frame.copy()
    name_a, name_b = _name_of(names, None, index=0), _name_of(names, None, index=1)
    x = pd.to_numeric(d["share_b"], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(d["share_a"], errors="coerce").to_numpy(dtype=float)
    vol = pd.to_numeric(d["vol_joint"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    n = len(d)
    marker_colors = [P.domain_color(v) for v in d["domain_id"]]
    vmax = float(vol.max()) if n and vol.max() > 0 else 1.0
    has_rank = (not subfield_grain) and ("rank_in_a" in d.columns or "rank_in_b" in d.columns)

    hovers = []
    for i in range(n):
        r = d.iloc[i]
        entity_name = str(r["subfield_name"]) if subfield_grain else str(r["field_name"])
        parts = [C.hover_entity(entity_name)]
        if subfield_grain:
            parts.append(C.hover_line(HOVER_RECIP_FIELD_LABEL, str(r["field_name"])))
        parts += [C.hover_line(HOVER_RECIP_SHARE.format(name=name_a), _fmt_pct(r["share_a"])),
                 C.hover_line(HOVER_RECIP_SHARE.format(name=name_b), _fmt_pct(r["share_b"])),
                 C.hover_line(HOVER_RECIP_JOINT, _fmt_vol(r["vol_joint"]))]
        fwci_line = _fmt_fwci_pair(r.get("fwci_mean"), r.get("fwci_median"), r.get("n_fwci"))
        if fwci_line:
            parts.append(C.hover_line(HOVER_FWCI_LABEL, fwci_line))
        n_cov, n_top = _num(r.get("n_covered")), _num(r.get("n_top10"))
        if np.isfinite(n_cov) and n_cov >= 1:
            pp10 = (n_top / n_cov) if n_cov > 0 else float("nan")
            dagger = LOW_VOLUME_GLYPH if n_cov < 10 else ""
            parts.append(C.hover_line(HOVER_RECIP_PP10, f"{_fmt_pct(pp10)}{dagger}"))
        n_stars = _num(r.get("n_stars_field"))
        if np.isfinite(n_stars):
            parts.append(C.hover_line(HOVER_RECIP_STARS_SUBFIELD if subfield_grain else HOVER_RECIP_STARS,
                                      _fmt_vol(n_stars)))
        if has_rank:
            rank_lines = []
            if pd.notna(r.get("rank_in_a")):
                rank_lines.append(f"{name_b} is {name_a}'s partner #{int(r['rank_in_a'])} here")
            if pd.notna(r.get("rank_in_b")):
                rank_lines.append(f"{name_a} is {name_b}'s partner #{int(r['rank_in_b'])} here")
            if rank_lines:
                parts.append(C.hover_line(HOVER_PARTNER_RANK_LABEL, ". ".join(rank_lines) + "."))
        hovers.append("<br>".join(p for p in parts if p is not None))

    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="markers",
        marker=dict(color=marker_colors, size=vol, sizemode="area",
                   sizeref=(2.0 * vmax / (C.BUBBLE_MAX_PX ** 2)),
                   sizemin=C.BUBBLE_MIN_PX,
                   line=dict(color=P.SURFACE, width=RECIP_BUBBLE_OUTLINE_PX)),
        customdata=hovers, hovertemplate="%{customdata}<extra></extra>", showlegend=False))

    finite_x = x[np.isfinite(x)]
    finite_y = y[np.isfinite(y)]
    axis_max = max(float(finite_x.max()) if len(finite_x) else 0.0,
                   float(finite_y.max()) if len(finite_y) else 0.0)
    axis_max = (axis_max or 1.0) * RECIP_AXIS_PAD_MULT
    fig.add_shape(type="line", x0=0, y0=0, x1=axis_max, y1=axis_max,
                 line=dict(color=P.INK_SECONDARY, width=C.HAIRLINE_PX, dash=RECIP_DIAGONAL_DASH))
    ax_share_tmpl = AX_RECIPROCITY_SHARE_SUBFIELD if subfield_grain else AX_RECIPROCITY_SHARE
    # Shares under 10 % (the subfield grain) need one decimal or the ticks
    # repeat the same rounded label twice.
    pct_fmt = C._AXIS_PCT_FMT_1DP if axis_max < C.RECIP_ONE_DECIMAL_BELOW else C._AXIS_PCT_FMT
    fig.update_xaxes(range=[0, axis_max], tickformat=pct_fmt,
                     title_text=ax_share_tmpl.format(name=name_b),
                     gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER,
                     constrain="domain")
    fig.update_yaxes(range=[0, axis_max], tickformat=pct_fmt,
                     title_text=ax_share_tmpl.format(name=name_a),
                     gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER,
                     # `constrain="domain"`, not the "range" default -- a
                     # plotly quirk: with `scaleanchor` set, the "range"
                     # default silently grows the SHORTER axis into a
                     # meaningless negative extent instead of shrinking its
                     # own plot area to match the square aspect ratio.
                     scaleanchor="x", scaleratio=1, constrain="domain")
    return C._base_layout(fig, C.SCATTER_HEIGHT,
                          margin=dict(t=C.BASE_PX // 2, l=C.BASE_PX, r=16, b=C.BASE_PX))


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

    `shared=True` appends the `palette.SHARED_TOPIC_MARK` chip -- Compare's
    topic-overlap legend, above its owner-coloured scatter and balance
    bars, is the caller (the MARK's own colour, not `SHARED_FRONTIER`, which
    stays a text/tick colour everywhere else -- see that constant's own
    docstring). `extra` takes further `(label, hex)` chips; the hex must
    still come from `lib.palette`."""
    order = sorted(dict.fromkeys(ids), key=lambda i: (_slot_of(slots, i), str(i)))
    items = [(_name_of(names, i), P.institution_color(_slot_of(slots, i)),
              P.institution_ink(_slot_of(slots, i))) for i in order]
    if shared:
        items.append((shared_label, P.SHARED_TOPIC_MARK, P.SHARED_TOPIC_MARK))
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
