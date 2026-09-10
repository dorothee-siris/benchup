"""
app/lib/views_compare.py -- the Compare page.

COMPOSITION ONLY, same house rule `lib/views_find.py`'s own docstring states:
every frame comes from `lib.compare_data`, every chart from
`lib.charts_compare`, every string from `lib.copy` (the
app's own COMPARE section). Nothing here recomputes a number and nothing
types a value into a rendered string.

PAGE ORDER (top to bottom): title + the pin caption -> two search slots
(`lib.selection.render_slots`) -> Key figures (nine cards per pair)
-> Thematic shape (Profile/Impact tabs) -> SDG profile (same tab shape)
-> Topic overlap (the shared selector, the owner-coloured plane, the
balance bars -- five per-mode encodings, a right-margin OpenAlex link
column, no on-page table any more) -> The relationship (momentum,
yearly-by-domain, strategic reciprocity, joint star papers) -> one Excel
download -> the share-link box.

PIN: Compare never offers a taxonomy/basis toggle -- every figure is
best-fit + full counting, named once in the caption under the title, with
the CORE window ({y0}-{y1}) and the whole-run window ({whole_y1}, the "share
of own output" denominator) both stated.

PERFORMANCE: the engine context and the ONE resident scenario come from
`lib.engine.scenario_cache` (`SC.bundle` / `SC.get("bestfit", "full")`)
-- never re-read here. The one export workbook is built once per
(a, b) pair behind `@st.cache_data(max_entries=8, ttl=1800)`, keyed on the
hashable id pair alone -- ctx/subs are fetched inside the cached
function, never passed as arguments.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts as C
from lib import compare_data as CD
from lib import copy
from lib import charts_compare as X
from lib import charts_topics as XT
from lib import fig_cache
from lib import how_to_read
from lib import palette as P
from lib import selection, state, tiles
from lib import topic_data as TD
from lib.app_config import CFG
from lib.charts_compare import _esc, _fmt_pct as _pct, _fmt_si, _fmt_vol as _count
from lib.engine import scenario_cache as SC
from lib.exports_xlsx import XLSX_MIME, workbook_bytes, workbook_filename
from lib.palette import NA_MARK
from lib.search import search as search_engine

CORE_Y0, CORE_Y1 = CFG["window"]
WHOLE_Y1 = CFG["bonus_year"]
COMPARE_SLOTS = int(CFG.get("compare_slots", 2))

TOP_N_SUBFIELDS = 20        # the pair's top-20 subfields by combined volume
PVAL_FLOOR = 0.001          # below this, the significance line reads "< 0.001"

TOPIC_N_DEFAULT = 50        # the "Topics per institution" slider's own default
TOPIC_N_STEP = 10

TAB_KEYS = {"profile": ("share_full", "eu_mean_share"), "impact": ("pp10_wd", "eu_mean_pp10_wd")}


# ---------------------------------------------------------------------------
# formatting / identity helpers -- reuses charts_compare's own formatters
# (`_fmt_pct`/`_fmt_vol`/`_fmt_si`/`_esc`) rather than a second
# implementation of the same NA_MARK-safe rules.
# ---------------------------------------------------------------------------

def _window(bounds: tuple[int, int]) -> str:
    return f"{bounds[0]}–{bounds[1]}"


def _pval(p) -> str:
    if p is None or pd.isna(p):
        return NA_MARK
    p = float(p)
    return f"< {PVAL_FLOOR}" if p < PVAL_FLOOR else f"{p:.3f}"


def _names_and_slots(ctx: dict, ids: list[str]) -> tuple[dict, dict]:
    """Slot 0 = A, slot 1 = B -- the
    reader's own slot layout IS the colour key ('s own `_slots`/`_names`
    idiom, `/app/lib/views_compare.py`), not the institution-slot map's
    ascending-id rule (that rule serves a caller with no natural pick
    order; here the picker order itself is the order)."""
    idx_by_id = ctx["index_by_id"]
    names = {iid: str(idx_by_id.loc[iid, "display_name"]) for iid in ids}
    slots = {ids[0]: 0, ids[1]: 1}
    return names, slots


def _search(query: str) -> list[dict]:
    bundle = SC.bundle()
    return search_engine(query, bundle["search_idx"], k=selection.SEARCH_TOP_N)


# ---------------------------------------------------------------------------
# 1. Key figures -- nine cards per institution, the card component
#    (`tiles.py`'s own type scale, a leader dot from `charts_compare.
#    best_value_dot`), ported from `/app/lib/views_compare.py:_card_html`/
#    `_card_facts`/`_leaders` (tiles.kpi_tile itself has no room for a dot).
# ---------------------------------------------------------------------------

CARD_COLUMNS = ("vol_full", "vol_change", "fwci_eu_mean", "pp", "star_share",
                "n_topics_led_fair", "frontier_top25_share", "sdg_share")

# the nine card tips (`copy.COMPARE`'s own `CARD_*_TIP`/`CARD_COPUB_TIP`
# templates, out of this stream's fence) already state several of their own
# facts as a "Label: value" clause with a literal colon -- this call site
# upgrades each one to the house `**label**: value` form (`tiles.
# bold_label_clauses`) without touching that prose. Longest-first ordering
# lives inside the helper itself.
_CARD_TIP_LABELS = (
    "European median of the mean", "European median", "Median of the same works",
    "World top-decile share of the same output", "Count",
    "In fractional counting", "International co-publication", "Company co-publication",
)


def _card_facts(ctx: dict, iid: str, row: pd.Series) -> list[tuple[str, str, str, str]]:
    """`[(column, label, value, tooltip)]`, this card's own nine-figure order. The
    ninth figure (international + company co-publication) is a two-value
    tile, rendered separately (`_copub_tile`) -- it carries no single
    "higher" reading, so it stays out of the leader-dot family.

    the FWCI card's own DISPLAYED value moved from the median to the
    mean (`row["fwci_eu_mean"]`, `compare_data.cards`'s own column now --
    no side lookup on `ctx["index_by_id"]` needed any more); its "?" states
    the median, the world-referenced PP10_WD share and the population's own
    median-of-the-mean, per `docs/tooltip_spec.yaml`'s `compare_card_fwci_eu`
    tile verbatim."""
    Cw = copy.COMPARE
    facts = [
        ("vol_full", Cw["CARD_PUBLICATIONS"], _count(row["vol_full"]),
         Cw["CARD_PUBLICATIONS_TIP"].format(y0=CORE_Y0, y1=CORE_Y1, frac=_count(row["vol_frac"]),
                                            eu_median=_count(row["vol_full_eu_median"]))),
        ("vol_change", Cw["CARD_VOL_CHANGE"], _pct(row["vol_change"]),
         Cw["CARD_VOL_CHANGE_TIP"].format(w1=_window(CD.DYNAMICS_W1), w2=_window(CD.DYNAMICS_W2),
                                          eu_median=_pct(row["vol_change_eu_median"]))),
        ("fwci_eu_mean", Cw["CARD_FWCI"], _fmt_si(row["fwci_eu_mean"]),
         Cw["CARD_FWCI_TIP"].format(y0=CORE_Y0, y1=CORE_Y1, n=_count(row["fwci_eu_n"]),
                                    median=_fmt_si(row["fwci_eu_median"]), pp10=_pct(row["pp"]),
                                    eu_median=_fmt_si(row["fwci_eu_mean_eu_median"]))),
        ("pp", Cw["CARD_PP10"], _pct(row["pp"]),
         Cw["CARD_PP10_TIP"].format(y0=CORE_Y0, y1=CORE_Y1, eu_median=_pct(row["pp_eu_median"]))),
        ("star_share", Cw["CARD_STARS"], _pct(row["star_share"]),
         Cw["CARD_STARS_TIP"].format(y0=CORE_Y0, y1=CORE_Y1, count=_count(row["n_stars"]),
                                     eu_median=_pct(row["star_share_eu_median"]))),
        ("n_topics_led_fair", Cw["CARD_TOPICS_LED"], _count(row["n_topics_led_fair"]),
         Cw["CARD_TOPICS_LED_TIP"].format(y0=CORE_Y0, y1=CORE_Y1,
                                          eu_median=_count(row["n_topics_led_fair_eu_median"]))),
        ("frontier_top25_share", Cw["CARD_FRONTIER"], _pct(row["frontier_top25_share"]),
         Cw["CARD_FRONTIER_TIP"].format(y0=CORE_Y0, y1=CORE_Y1,
                                        eu_median=_pct(row["frontier_top25_share_eu_median"]))),
        ("sdg_share", Cw["CARD_SDG"], _pct(row["sdg_share"]),
         Cw["CARD_SDG_TIP"].format(y0=CORE_Y0, y1=WHOLE_Y1, eu_median=_pct(row["sdg_share_eu_median"]))),
    ]
    # (see
    # `_CARD_TIP_LABELS`'s own comment above): bold each tip's own
    # already-colon-labelled clause(s), the tuple's own shape unchanged.
    return [(col, label, value, tiles.bold_label_clauses(tip, _CARD_TIP_LABELS))
           for col, label, value, tip in facts]


def _leaders(df: pd.DataFrame) -> dict:
    """`{card column: institution_id}` of the higher value -- no entry on a
    tie or when neither institution carries a finite value ('s own
    `_leaders`, ported verbatim: a tied dot claims nothing a plain read
    would not already show)."""
    cells = df.set_index("institution_id")
    out = {}
    for col in CARD_COLUMNS:
        series = pd.to_numeric(cells[col], errors="coerce").dropna()
        if series.empty:
            continue
        winners = series[series == series.max()]
        if len(winners) == 1:
            out[col] = str(winners.index[0])
    return out


def _card_html(label: str, value: str, dot: str, *, raw_value: bool = False) -> str:
    """ONE card: measure name, then value with the leader dot beside it
    `tiles.py`'s own type scale (LABEL_PX/VALUE_PX/.), ported from 's
    `_card_html` (`tiles.kpi_tile` itself has no slot for a dot).
    `raw_value=True` (the Relationship section's three tiles, below) skips
    the escape on `value` -- the ONLY caller that needs it is the Momentum
    tile, whose "value" is already-safe HTML built from `mom["color"]`/
    `mom["glyph"]`/`mom["text"]`, none of it reader-supplied text."""
    value_html = value if raw_value else _esc(value)
    return (f'<div class="{tiles.TILE_CLASS}">'
            f'<div style="font-size:{tiles.LABEL_PX}px;font-weight:{tiles.LABEL_WEIGHT};'
            f'line-height:{tiles.LABEL_LINE_HEIGHT};color:{P.INK};">{_esc(label)}</div>'
            f'<div style="display:flex;align-items:center;gap:{X.DOT_GAP_PX}px;'
            f'font-size:{tiles.VALUE_PX}px;font-weight:{tiles.VALUE_WEIGHT};'
            f'line-height:{tiles.VALUE_LINE_HEIGHT};color:{P.INK};">'
            f'<span>{value_html}</span>{dot}</div></div>')


def _copub_tile(row: pd.Series) -> str:
    Cw = copy.COMPARE
    tip = Cw["CARD_COPUB_TIP"].format(intl=_pct(row["intl_share"]), intl_eu=_pct(row["intl_share_eu_median"]),
                                      company=_pct(row["company_share"]),
                                      company_eu=_pct(row["company_share_eu_median"]),
                                      y0=CORE_Y0, y1=CORE_Y1)
    tip = tiles.bold_label_clauses(tip, _CARD_TIP_LABELS)   # see _CARD_TIP_LABELS
    value = f'{_pct(row["intl_share"])} · {_pct(row["company_share"])}'
    html = _card_html(Cw["CARD_COPUB"], value, "")
    return html, tip


def _render_cards(ctx: dict, ids: list[str], names: dict, slots: dict) -> pd.DataFrame:
    st.subheader(copy.COMPARE["CARDS_HEADER"])
    df = _cards_frame(ids[0], ids[1])
    cells = df.set_index("institution_id")
    leaders = _leaders(df)
    cols = st.columns(len(ids))
    for col, iid in zip(cols, ids):
        slot = slots[iid]
        colour = P.institution_color(slot)
        with col:
            st.markdown(f'<span style="color:{colour}">●</span> **{_esc(names[iid])}**',
                        unsafe_allow_html=True)
            row = cells.loc[iid]
            for column, label, value, tip in _card_facts(ctx, iid, row):
                dot = X.best_value_dot(slot) if leaders.get(column) == iid else ""
                with st.container(border=True):
                    st.markdown(_card_html(label, value, dot), unsafe_allow_html=True, help=tip)
            html, tip = _copub_tile(row)
            with st.container(border=True):
                st.markdown(html, unsafe_allow_html=True, help=tip)
    st.markdown(X.chart_note(copy.COMPARE["CARDS_NOTE"], copy.COMPARE["CARDS_NOTE_TIP"]),
               unsafe_allow_html=True)
    return df


# ---------------------------------------------------------------------------
# 2/3. Thematic shape and SDG profile -- the SAME two_tab_bars
#    call, differing only in the source frame and `grouped_by_field`.
# ---------------------------------------------------------------------------

def _shape_long(df: pd.DataFrame, tab: str, *, grouped: bool, id_col: str, label_col: str) -> pd.DataFrame:
    value_col, ref_col = TAB_KEYS[tab]
    out = pd.DataFrame({
        "row_id": df[id_col], "row_label": df[label_col], "institution_id": df["institution_id"],
        "value": df[value_col], "ref_value": df[ref_col], "vol_full": df["vol_full"],
        "n_covered": df["n_covered_pp"], "si": df["si"], "fwci_median": df["fwci_median"],
        # fwci_mean/n_covered_fwci ride along unconditionally (one frame
        # serves both tabs) so the Impact tab's hover can join the FWCI_EU
        # line (mean AND median together, floored on the FWCI population's
        # OWN n -- a different, slightly wider count than n_covered_pp, the
        # PP10_WD population); the Profile tab's hover simply never asks
        # for them. Both columns already ship on `df` (compare_data's
        # subfield/SDG frames already carry fwci_mean via fwci_taxa).
        "fwci_mean": df["fwci_mean"], "n_covered_fwci": df["n_covered_fwci"],
        "vol_frac": df["vol_frac"],
    })
    if grouped:
        out["group_label"] = df["field_name"]
        out["domain_id"] = df["domain_id"]
    return out


def _render_two_tab_section(header: str, basis_caption: str, note_profile: str, note_impact: str,
                            df: pd.DataFrame, ids: list[str], names: dict, slots: dict, *,
                            grouped: bool, id_col: str, label_col: str, key_prefix: str,
                            tabs: bool = True, accent_key_col: str | None = None) -> None:
    """`tabs=False` (the SDG section, below) renders the profile chart alone,
    no `st.tabs()` at all -- the thematic-shape section (unedited call site,
    `_render_shape`) keeps the default and therefore keeps both tabs.
    `accent_key_col` copies one extra column from the caller's own `df`
    straight through onto the frame `two_tab_bars` draws, unchanged by
    `_shape_long` (row order is untouched, a positional copy aligns): the
    SDG section passes its own `sdg_number` so the chart's accent-square
    mechanism (already wired for subfields via `domain_id`) has an SDG
    colour key to find -- `_shape_long`'s `grouped=False` branch otherwise
    carries no such column at all, which is why the square was missing."""
    st.subheader(header)
    st.markdown(X.legend_strip(ids, slots=slots, names=names), unsafe_allow_html=True)
    st.markdown(X.basis_caption(basis_caption), unsafe_allow_html=True)

    def _frame(tab: str) -> pd.DataFrame:
        frame = _shape_long(df, tab, grouped=grouped, id_col=id_col, label_col=label_col)
        if accent_key_col and accent_key_col in df.columns:
            frame[accent_key_col] = df[accent_key_col].to_numpy()
        return frame

    # (pair, key_prefix, tab) is a complete figure-cache identity --
    # `df` itself is already the caller's own cached per-pair frame (`_top_
    # subfields_frame`/`_sdg_pair_frame`), and neither section exposes any
    # further control that could change `_frame(tab)`'s own content.
    def _cached(tab: str, **kwargs) -> None:
        fig = fig_cache.cached_figure(
            f"two_tab_bars_{key_prefix}", (ids[0], ids[1], tab),
            lambda: X.two_tab_bars(_frame(tab), tab, names, slots, grouped_by_field=grouped, **kwargs))
        st.plotly_chart(fig, width="stretch", key=f"fig_{key_prefix}_{tab}")

    if not tabs:
        # the SDG section (its own frame's vol_full/vol_frac are the CORE
        # window, not whole-run -- see _metric_hover's own docstring)
        _cached("profile", y0=CORE_Y0, y1=CORE_Y1)
        st.markdown(X.chart_note(note_profile), unsafe_allow_html=True)
        return

    tab_profile, tab_impact = st.tabs([copy.COMPARE["TAB_PROFILE"], copy.COMPARE["TAB_IMPACT"]])
    with tab_profile:
        _cached("profile", y0=CORE_Y0, whole_y1=WHOLE_Y1)
        st.markdown(X.chart_note(note_profile), unsafe_allow_html=True)
    with tab_impact:
        _cached("impact")
        st.markdown(X.chart_note(note_impact.format(floor=int(P.RATIO_HATCH_FLOOR))), unsafe_allow_html=True)


def _render_shape(ctx: dict, subs: dict, ids: list[str], names: dict, slots: dict) -> pd.DataFrame:
    df = _top_subfields_frame(ids[0], ids[1])
    n = df["subfield_id"].nunique()
    _render_two_tab_section(
        copy.COMPARE["SHAPE_HEADER"], copy.COMPARE["SHAPE_BASIS_CAPTION"].format(n=n),
        copy.COMPARE["SHAPE_NOTE_PROFILE"], copy.COMPARE["SHAPE_NOTE_IMPACT"],
        df, ids, names, slots, grouped=True, id_col="subfield_id", label_col="subfield_name",
        key_prefix="shape")
    return df


def _render_sdg(ctx: dict, subs: dict, ids: list[str], names: dict, slots: dict) -> pd.DataFrame:
    """SDG profile -- PROFILE ONLY, no Impact tab and no tab UI at all: the
    section states one shape (each institution's own SDG-tagged mass), the
    world top-decile read the Impact tab would otherwise carry stays out of
    scope here, matching the thematic section's own reasoning for keeping
    two tabs in reverse (that section actively wants both views; this one
    does not). `accent_key_col="sdg_number"` is the fix for the missing
    colour square: `sdg_frame` already carries the goal's own 1-based number,
    this just lets it reach the chart."""
    df = _sdg_pair_frame(ids[0], ids[1])
    _render_two_tab_section(
        copy.COMPARE["SDG_HEADER"], copy.COMPARE["SDG_BASIS_CAPTION"],
        copy.COMPARE["SDG_NOTE_PROFILE"], copy.COMPARE["SDG_NOTE_IMPACT"],
        df, ids, names, slots, grouped=False, id_col="sdg_idx", label_col="sdg_label",
        key_prefix="sdg", tabs=False, accent_key_col="sdg_number")
    untagged = df.attrs.get("untagged_share", {})
    lines = [copy.COMPARE["SDG_UNTAGGED"].format(name=names[iid], share=_pct(untagged.get(iid)))
            for iid in ids]
    st.caption(" ".join(lines))
    return df


# ---------------------------------------------------------------------------
# 4. Topic overlap -- the shared selector, the owner-coloured plane, the
#    balance bars (five per-mode encodings + a right-margin OpenAlex link
#    column; the on-page recap table this section once carried is gone,
#    its columns live on in the workbook sheet only).
# ---------------------------------------------------------------------------

_PAIR_TOPIC_MODE_BY_LABEL: dict[str, str] = {}   # filled just below, once copy.FIND exists


def _pair_topic_mode_options() -> list[str]:
    """The five "Topics shown" mode labels, in the fixed order the
    segmented control shows them -- SAME labels Find's own topic planes
    use (`copy.FIND`, never duplicated into `copy.COMPARE`), reverse-mapped
    into a module-level dict OF THIS FILE'S OWN (never `lib.views_find`'s:
    no view module in this app imports another view module, and a shared
    mutable global would let the two pages silently race on it)."""
    order = [
        (copy.FIND["TOPIC_MODE_VOLUME"], TD.MODE_VOLUME),
        (copy.FIND["TOPIC_MODE_FWCI"], TD.MODE_FWCI),
        (copy.FIND["TOPIC_MODE_LED"], TD.MODE_LED),
        (copy.FIND["TOPIC_MODE_STARS"], TD.MODE_STARS),
        (copy.FIND["TOPIC_MODE_EMERGENCE"], TD.MODE_EMERGENCE),
    ]
    _PAIR_TOPIC_MODE_BY_LABEL.clear()
    _PAIR_TOPIC_MODE_BY_LABEL.update(dict(order))
    return [label for label, _ in order]


@st.cache_data(show_spinner=False, max_entries=8, ttl=1800)
def _pair_topics_frame(a: str, b: str, mode: str, n: int, fwci_stat: str) -> pd.DataFrame:
    """Bounded per-(pair, mode, n, fwci_stat) cache -- `ctx` is read
    from the process-wide scenario cache inside, never passed as an
    argument, so the cache key stays a small hashable tuple."""
    return TD.pair_topics(SC.bundle()["ctx"], a, b, mode, n, fwci_stat)


# ---------------------------------------------------------------------------
# The OTHER per-pair Compare frames, bounded the SAME way as
# `_pair_topics_frame` above (`max_entries=8, ttl=1800`, ctx/subs fetched
# inside from the process-wide scenario cache -- never a cache_data argument,
# matching `views_find.py`'s own house pattern, `_fields_frame`). Compare is
# PINNED to bestfit/full (never a user control), so the pair id alone is a
# complete, correct cache key: `subs` never varies while these are resident.
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, max_entries=8, ttl=1800)
def _cards_frame(a: str, b: str) -> pd.DataFrame:
    return CD.cards(SC.bundle()["ctx"], [a, b])


@st.cache_data(show_spinner=False, max_entries=8, ttl=1800)
def _top_subfields_frame(a: str, b: str) -> pd.DataFrame:
    return CD.top_subfields(SC.bundle()["ctx"], SC.get("bestfit", "full"), [a, b], n=TOP_N_SUBFIELDS)


@st.cache_data(show_spinner=False, max_entries=8, ttl=1800)
def _sdg_pair_frame(a: str, b: str) -> pd.DataFrame:
    return CD.sdg_frame(SC.bundle()["ctx"], SC.get("bestfit", "full"), [a, b])


@st.cache_data(show_spinner=False, max_entries=8, ttl=1800)
def _relationship_frame(a: str, b: str) -> dict:
    """The relationship BUNDLE (momentum + pulse + yearly stack + reciprocity
    + joint stars), cached as one dict -- `compare_data.relationship` already
    computes all four together in one call, so one cache entry covers all of
    JOB 1's 'relationship frames: momentum, yearly stack, reciprocity'."""
    return CD.relationship(SC.bundle()["ctx"], [a, b], SC.get("bestfit", "full"))


@st.cache_data(show_spinner=False, max_entries=8, ttl=1800)
def _reciprocity_subfields_frame(a: str, b: str) -> pd.DataFrame:
    """The subfield-grain sibling of `_relationship_frame`'s own `reciprocity`
    block: renames `collab_data.reciprocity_frame(..., grain="subfields")`'s
    raw x/y/joint_vol columns into the SAME share_a/share_b/vol_joint wide
    contract `compare_data.relationship` already builds for the field grain
    (mirrors that rename verbatim, minus rank_in_a/rank_in_b -- a pair-level
    fact the chart already drops at this grain), so `charts_compare.
    reciprocity_scatter` reads either grain through one shape. Cached
    separately, keyed on (a, b) alone -- the grain is fixed to "subfields" by
    construction, so this can never collide with `_relationship_frame`'s own
    (a, b)-only key for the field grain."""
    from lib import collab_data as COL  # local import, same reasoning as compare_data's own

    ctx = SC.bundle()["ctx"]
    subs = SC.get("bestfit", "full")
    recip = COL.reciprocity_frame(ctx, subs, a, b, grain="subfields")
    cols = ["subfield_id", "subfield_name", "field_id", "field_name", "domain_id",
           "vol_joint", "share_a", "share_b", "fwci_mean", "fwci_median", "n_fwci",
           "n_top10", "n_covered", "n_stars_field"]
    if not len(recip):
        return pd.DataFrame(columns=cols)
    return pd.DataFrame({
        "subfield_id": recip["subfield_id"], "subfield_name": recip["subfield_name"],
        "field_id": recip["field_id"], "field_name": recip["field_name"], "domain_id": recip["domain_id"],
        "vol_joint": recip["joint_vol"], "share_a": recip["y"], "share_b": recip["x"],
        "fwci_mean": recip["fwci_mean"], "fwci_median": recip["fwci_median"], "n_fwci": recip["n_fwci"],
        "n_top10": recip["n_top10"], "n_covered": recip["n_covered"],
        "n_stars_field": recip["n_stars_field"],
    }).reset_index(drop=True)


# ---------------------------------------------------------------------------
# The topic-overlap table's own per-institution column headers -- a SHORT
# name per slot (`index.display_name_acronyms`' first entry when present,
# else `display_name` cut at `SHORT_NAME_CUT` characters with an ellipsis),
# so a header reads "Publications, CNRS" rather than the bare letter
# "Publications, A". `docs/tooltip_spec.yaml`'s own `compare_topic_table`
# entry documents the SAME five templates verbatim (with `{A}`/`{B}`
# placeholders); mirrored here as plain Python constants, a deliberate,
# narrow exception to this module's own "every string from `lib.copy`"
# convention, scoped to exactly these five short-name templates.
# ---------------------------------------------------------------------------
SHORT_NAME_CUT = 24   # characters, before the ellipsis

_COL_PUBLICATIONS_TMPL = "Publications, {name}"
_COL_CHANGE_TMPL = "Change, {name}"
_COL_WORLD_RANK_TMPL = "World rank, {name}"
_COL_STAR_PAPERS_TMPL = "Star papers, {name}"
_COL_ON_OPENALEX_TMPL = "{name} on OpenAlex"


def _short_institution_name(ctx: dict, iid: str) -> str:
    """`index.display_name_acronyms`'s own first pipe-delimited entry when
    the institution carries one (e.g. "CNRS", never the empty string this
    column ships for an institution with no recorded acronym); otherwise
    `display_name` cut at `SHORT_NAME_CUT` characters with a single
    ellipsis character appended -- never a mid-word hard cut with no
    indication anything was removed."""
    row = ctx["index_by_id"].loc[iid]
    acronyms = row.get("display_name_acronyms")
    if isinstance(acronyms, str) and acronyms.strip():
        return acronyms.split("|")[0].strip()
    name = str(row.get("display_name") or iid)
    if len(name) > SHORT_NAME_CUT:
        return name[:SHORT_NAME_CUT] + "\N{HORIZONTAL ELLIPSIS}"
    return name


def _render_topic_overlap(ctx: dict, ids: list[str], names: dict, slots: dict) -> tuple[str, int, str]:
    """Returns `(mode, n, fwci_stat)` -- the resolved control state, so
    `render()` can thread the SAME selection into the workbook download
    (JOB 3: the "Topic overlap" sheet reflects the CURRENT mode, not a
    fixed default).

    The recap table this section used to render below the charts is GONE:
    it was a strict subset of the workbook's own uncapped "Topic overlap"
    sheet, and the right-margin link column the balance bars now carry
    restores the one thing the table alone offered on-page -- an OpenAlex
    link per row. `_workbook_sheets` below is untouched: the export keeps
    its own 33-column `PAIR_COLS` shape regardless."""
    Cw, Fw = copy.COMPARE, copy.FIND
    st.subheader(Cw["TOPIC_OVERLAP_HEADER"])

    mode_label = st.segmented_control(Fw["TOPIC_MODE_LABEL"], _pair_topic_mode_options(),
                                      default=Fw["TOPIC_MODE_VOLUME"], required=True,
                                      key="compare_topic_mode", **state.PERSIST)
    mode = _PAIR_TOPIC_MODE_BY_LABEL.get(mode_label or Fw["TOPIC_MODE_VOLUME"], TD.MODE_VOLUME)
    c_n, c_stat = st.columns([3, 2])
    with c_n:
        n = st.slider(Cw["TOPIC_N_LABEL"], TD.PAIR_N_MIN, TD.PAIR_N_MAX,
                      TOPIC_N_DEFAULT, step=TOPIC_N_STEP, key="compare_topic_n", **state.PERSIST)
    with c_stat:
        stat_label = st.radio(Fw["TOPIC_FWCI_STAT_LABEL"],
                              [Fw["TOPIC_FWCI_STAT_MEAN"], Fw["TOPIC_FWCI_STAT_MEDIAN"]],
                              index=0, horizontal=True, key="compare_topic_fwci_stat", **state.PERSIST)
    fwci_stat = (TD.FWCI_STAT_MEAN if stat_label != Fw["TOPIC_FWCI_STAT_MEDIAN"]
                else TD.FWCI_STAT_MEDIAN)

    a, b = ids
    pairs = _pair_topics_frame(a, b, mode, n, fwci_stat)
    if pairs.empty:
        st.caption(Cw["TOPIC_OVERLAP_EMPTY"])
        return mode, n, fwci_stat

    name_a, name_b = names[a], names[b]
    short_a, short_b = _short_institution_name(ctx, a), _short_institution_name(ctx, b)
    st.markdown(X.legend_strip(ids, slots=slots, names=names, shared=True,
                               extra=[(Cw["LEGEND_JOINT"], P.JOINT_TOPIC_COLOR)]),
               unsafe_allow_html=True)

    facts = TD.pair_topic_set_caption(pairs)
    st.markdown(X.basis_caption(Cw["CAPTION_TOPIC_OVERLAP_PERIMETER"].format(
        y0=CORE_Y0, y1=CORE_Y1, name_a=name_a, name_b=name_b,
        n_shared=_count(facts["n_shared"]), n_a_only=_count(facts["n_a_only"]),
        n_b_only=_count(facts["n_b_only"]), n_catchall=_count(facts["n_catchall"]),
        n_no_frontier=_count(facts["n_no_frontier"]))), unsafe_allow_html=True)

    # One figure-cache identity for both the plane and the bars --
    # both are built from this SAME `pairs` frame (itself already
    # `_pair_topics_frame`'s own cache hit on a repeat visit), so both
    # figures skip their own rebuild on an unrelated rerun of this page.
    # `mode` is already part of the key (a mode change picks a different
    # `pairs` set AND a different bar encoding).
    overlap_key = (a, b, mode, n, fwci_stat)

    st.caption(how_to_read.text("compare_topic_overlay", mode, a=short_a, b=short_b))

    scored = pairs[np.isfinite(pd.to_numeric(pairs["expansion_latest"], errors="coerce"))
                  & np.isfinite(pd.to_numeric(pairs["acceleration_latest"], errors="coerce"))]
    if scored.empty:
        st.caption(Cw["TOPIC_OVERLAP_PLANE_EMPTY"])
    else:
        fig = fig_cache.cached_figure(
            "fig_topic_overlap_plane", overlap_key,
            lambda: XT.fig_plane_frontier(pairs, color_by="owner", slots=slots, names=names, ids=ids))
        st.plotly_chart(fig, width="stretch", key="fig_topic_overlap_plane")
    st.caption(Fw["AXIS_DEF_TOPIC_PLANES"])

    st.caption(how_to_read.text("compare_balance_bars", mode, a=short_a, b=short_b))
    fig = fig_cache.cached_figure(
        "fig_topic_overlap_bars", overlap_key,
        lambda: XT.balance_bars(pairs, ids, slots=slots, names=names, mode=mode))
    st.plotly_chart(fig, width="stretch", key="fig_topic_overlap_bars")
    # The bars' own two housekeeping notes: the catch-all flag (every mode --
    # a catch-all row's tick carries a cross glyph and its segments draw in a
    # lighter tint) and, on the two modes whose tip labels can carry a
    # dagger, what that dagger means.
    st.markdown(X.chart_note(XT.NOTE_CATCHALL_FLAG), unsafe_allow_html=True)
    if mode == TD.MODE_FWCI:
        st.markdown(X.chart_note(XT.NOTE_FWCI_DAGGER), unsafe_allow_html=True)
    elif mode == TD.MODE_EMERGENCE:
        st.markdown(X.chart_note(XT.NOTE_EMERGENCE_DAGGER), unsafe_allow_html=True)

    return mode, n, fwci_stat


# ---------------------------------------------------------------------------
# 5. The relationship -- momentum, yearly-by-domain, reciprocity, stars.
# ---------------------------------------------------------------------------

# The reciprocity scatter's own field/subfield grain toggle -- persisted like
# the topic-overlap controls above, but its own strings live here rather than
# in `lib.copy` (a deliberate narrow exception, same reasoning `SHORT_NAME_
# CUT`'s block already states for this module: this control belongs to the
# relationship section alone, not the page-wide COMPARE copy set).
RECIPROCITY_GRAIN_LABEL = "Grain"
RECIPROCITY_GRAIN_FIELDS = "Fields"
RECIPROCITY_GRAIN_SUBFIELDS = "Top 30 subfields (by joint volume)"
RECIPROCITY_GRAIN_OPTIONS = [RECIPROCITY_GRAIN_FIELDS, RECIPROCITY_GRAIN_SUBFIELDS]
_RECIPROCITY_GRAIN_BY_LABEL = {RECIPROCITY_GRAIN_FIELDS: "fields", RECIPROCITY_GRAIN_SUBFIELDS: "subfields"}
_RECIPROCITY_SUBFIELD_CAPTION_NOTE = (
    " This view shows the pair's 30 subfields with the most joint publications.")
_RECIPROCITY_SUBFIELD_EMPTY_CAPTION = (
    "This pair has no shared subfields with joint publications to show at this grain.")


def _momentum_evidence_line(mom: dict, facts: dict) -> str:
    """the always-visible evidence sentence, filled from the pair's own
    figures -- `collab_data.momentum_evidence`'s value-driven state (never
    `mom_class`) picked straight into ONE of `copy.COMPARE`'s
    `MOMENTUM_LINE_*` templates, per `docs/tooltip_spec.yaml`'s
    `compare_momentum_line` verbatim. `facts` is `collab_facts.json`
    verbatim, threaded straight through to `momentum_evidence` (every
    threshold it uses -- band, alpha, the three classification floors --
    comes from there, never a typed digit)."""
    from lib import collab_data as COL  # local import, same reasoning as compare_data's own

    Cw = copy.COMPARE
    alpha = facts.get("alpha")
    ev = COL.momentum_evidence(mom, facts)
    w1, w2 = _window(CD.DYNAMICS_W1), _window(CD.DYNAMICS_W2)
    if ev["state"] == "new":
        return Cw["MOMENTUM_LINE_NEW"].format(w1=w1, c2=_count(ev["c2_mean"]))
    if ev["state"] == "thin_ns":
        return Cw["MOMENTUM_LINE_NS_THIN"]
    if ev["state"] == "dormant":
        return Cw["MOMENTUM_LINE_DORMANT"].format(w1=w1, c1=_count(ev["c1_mean"]))
    if ev["state"] == "thin":
        return Cw["MOMENTUM_LINE_THIN"].format(w1=w1, floor=int(CD.PAIR_QUALIFYING_FLOOR))
    if ev["sig"] == "stable_band":
        significance = Cw["MOMENTUM_LINE_SIG_STABLE"].format(band=ev["band_pct"])
    elif ev["sig"] == "no_test":
        significance = Cw["MOMENTUM_LINE_SIG_NO_TEST"]
    else:
        sig_key = ("MOMENTUM_LINE_SIG_SIGNIFICANT" if ev["sig"] == "significant"
                  else "MOMENTUM_LINE_SIG_NOT_SIGNIFICANT")
        significance = Cw[sig_key].format(alpha=_pct(alpha), p=_pval(ev["p"]))
    return Cw["MOMENTUM_LINE_NUMERIC"].format(c1=_count(ev["c1_mean"]), c2=_count(ev["c2_mean"]),
                                              w1=w1, w2=w2, pct=ev["pct"], significance=significance)


def _render_relationship_tiles(ctx: dict, rel: dict) -> None:
    """The relationship block's three tiles, one row -- the SAME
    bordered-card visual the Key-figure cards above already use (`_card_html`,
    `lib.tiles`'s own type scale), just with no leader dot (there is no
    "higher is better" reading across three unrelated measures). "Joint star
    papers" carries the OpenAlex link directly under its own tile, in the
    same column -- the sentence that used to carry it, at the very bottom of
    this section, is retired."""
    from lib import collab_data as COL  # local import, same reasoning as compare_data's own

    Cw = copy.COMPARE
    mom = rel["momentum"]
    pulse = rel["pulse"]
    facts = COL._load_collab_facts(ctx)
    alpha = facts.get("alpha")

    col_pub, col_stars, col_mom = st.columns(3)
    with col_pub:
        with st.container(border=True):
            tip = Cw["TILE_JOINT_PUBLICATIONS_TIP"].format(
                y0=CORE_Y0, y1=CORE_Y1, whole_y1=WHOLE_Y1,
                copubs_total=_count(pulse["copubs_total"]), floor=int(CD.PAIR_QUALIFYING_FLOOR))
            st.markdown(_card_html(Cw["TILE_JOINT_PUBLICATIONS"], _count(rel["core_total"]), ""),
                       unsafe_allow_html=True, help=tip)
    with col_stars:
        with st.container(border=True):
            tip = Cw["TILE_JOINT_STARS_TIP"].format(y0=CORE_Y0, y1=CORE_Y1)
            st.markdown(_card_html(Cw["TILE_JOINT_STARS"], _count(rel.get("joint_stars") or 0), ""),
                       unsafe_allow_html=True, help=tip)
        st.markdown(f'[{Cw["JOINT_STARS_LINK_LABEL"]}]({rel["joint_stars_url"]})')
    with col_mom:
        with st.container(border=True):
            tip = Cw["TILE_MOMENTUM_TIP"].format(
                w1=_window(CD.DYNAMICS_W1), w2=_window(CD.DYNAMICS_W2),
                alpha=_pct(alpha) if alpha is not None else NA_MARK,
                floor=int(CD.PAIR_QUALIFYING_FLOOR))
            value_html = f'<span style="color:{mom["color"]};">{_esc(mom["glyph"])} {_esc(mom["text"])}</span>'
            st.markdown(_card_html(Cw["TILE_MOMENTUM"], value_html, "", raw_value=True),
                       unsafe_allow_html=True, help=tip)

    st.markdown(_momentum_evidence_line(mom, facts))


def _fallback_yearly_bar(pulse_yearly: pd.DataFrame) -> go.Figure:
    """The relationship section's "plain yearly totals" fallback for a pair
    below the qualifying floor: the earlier single-series `fig_pulse`
    builder is gone, so this reuses the SAME house
    chrome (`charts._base_layout`, the shared axis titles/grid/border
    tokens) rather than a second bar-drawing primitive for one rare case."""
    years = [str(y) for y in pulse_yearly["year"]]
    vals = [float(v) for v in pulse_yearly["copubs"]]
    fig = go.Figure(go.Bar(
        x=years, y=vals, marker=dict(color=P.SHARED_FRONTIER, line=dict(color=P.SURFACE, width=C.HAIRLINE_PX)),
        text=[_count(v) for v in vals], textposition="outside", cliponaxis=False))
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=years,
                     title_text=C.AX_YEAR, gridcolor=P.GRID, linecolor=P.BORDER)
    fig.update_yaxes(title_text=C.AX_WORKS, rangemode="tozero",
                     gridcolor=P.GRID, zerolinecolor=P.GRID, linecolor=P.BORDER)
    return C._base_layout(fig, X.YEARLY_STACK_HEIGHT_PX,
                          margin=dict(t=C.BASE_PX, l=8, r=16, b=C.BASE_PX))


def _render_relationship(ctx: dict, subs: dict, ids: list[str], names: dict, slots: dict) -> dict:
    Cw = copy.COMPARE
    st.subheader(Cw["RELATIONSHIP_HEADER"])
    rel = _relationship_frame(ids[0], ids[1])
    if rel["momentum"] is None:
        st.caption(Cw["RELATIONSHIP_NEVER"])
        return rel

    _render_relationship_tiles(ctx, rel)

    # Neither figure below has any control of its own -- `rel` is
    # already the caller's own cached per-pair bundle (`_relationship_
    # frame`), so `(a, b)` alone is a complete figure-cache identity.
    pair_key = (ids[0], ids[1])

    if rel["yearly_qualifies"] and len(rel["yearly"]):
        fig = fig_cache.cached_figure("yearly_domain_stack", pair_key,
                                      lambda: X.yearly_domain_stack(rel["yearly"]))
        st.plotly_chart(fig, width="stretch", key="fig_relationship_yearly")
        caption = Cw["YEARLY_CAPTION"].format(y0=CORE_Y0, y1=CORE_Y1)
        if rel["topicless_note"]:
            caption += Cw["YEARLY_TOPICLESS_NOTE"]
        st.caption(caption)
    elif rel["pulse"] is not None:
        fig = _fallback_yearly_bar(rel["pulse"]["yearly"])
        st.plotly_chart(fig, width="stretch", key="fig_relationship_yearly_fallback")
        st.caption(Cw["YEARLY_FALLBACK_CAPTION"].format(floor=int(CD.PAIR_QUALIFYING_FLOOR),
                                                        y0=CD.CORE_WINDOW[0], y1=WHOLE_Y1))

    recip_fields = rel["reciprocity"]
    if len(recip_fields):
        st.markdown(f"##### {Cw['RECIPROCITY_HEADER']}")
        grain_label = st.segmented_control(
            RECIPROCITY_GRAIN_LABEL, RECIPROCITY_GRAIN_OPTIONS,
            default=RECIPROCITY_GRAIN_FIELDS, required=True,
            key="compare_recip_grain", **state.PERSIST)
        grain = _RECIPROCITY_GRAIN_BY_LABEL.get(grain_label or RECIPROCITY_GRAIN_FIELDS, "fields")

        short_a = _short_institution_name(ctx, ids[0])
        short_b = _short_institution_name(ctx, ids[1])
        st.caption(how_to_read.text("compare_reciprocity", grain, a=short_a, b=short_b))

        recip = recip_fields if grain == "fields" else _reciprocity_subfields_frame(ids[0], ids[1])
        if len(recip):
            recip_key = (ids[0], ids[1], grain)
            fig = fig_cache.cached_figure(
                "reciprocity_scatter", recip_key,
                lambda: X.reciprocity_scatter(recip, [names[ids[0]], names[ids[1]]],
                                              [slots[ids[0]], slots[ids[1]]], grain=grain))
            st.plotly_chart(fig, width="stretch", key="fig_reciprocity")
            caption = Cw["RECIPROCITY_CAPTION"]
            if grain == "subfields":
                caption += _RECIPROCITY_SUBFIELD_CAPTION_NOTE
            st.caption(caption)
        else:
            st.caption(_RECIPROCITY_SUBFIELD_EMPTY_CAPTION)

    return rel


# ---------------------------------------------------------------------------
# 6. One Excel at the end, then the share-link box.
# ---------------------------------------------------------------------------

def _workbook_sheets(ctx: dict, subs: dict, ids: list[str], mode: str, n: int,
                     fwci_stat: str) -> list[tuple[str, pd.DataFrame]]:
    """The SIX sheets `copy.COMPARE` names, in that order -- pure function
    (no Streamlit), so it is directly unit-testable and directly what
    `_workbook_bytes` (the cached wrapper) calls. `mode`/`n`/`fwci_stat`
    (JOB 3): the "Topic overlap" sheet is `topic_data.pair_topics` for the
    CURRENT selector state, uncapped -- every row, every column of
    `TD.PAIR_COLS` (the 33-column export contract, UNCHANGED by the
    balance bars' own new per-mode fields: `PAIR_EXTRA_COLS` -- `stars_joint`,
    `star_ids_joint`, `url_stars_joint`, `n_covered_a`/`n_covered_b` -- are
    chart-layer-only and never reach this sheet)."""
    Cw = copy.COMPARE
    cards_df = _cards_frame(ids[0], ids[1])
    subfields_df = CD.all_subfields(ctx, subs, ids)  # uncapped (all 252) -- NOT _top_subfields_frame's top-20
    sdg_df = _sdg_pair_frame(ids[0], ids[1])
    overlap_df = _pair_topics_frame(ids[0], ids[1], mode, n, fwci_stat)[TD.PAIR_COLS]
    rel = _relationship_frame(ids[0], ids[1])
    if rel["yearly_qualifies"] and len(rel["yearly"]):
        yearly_df = rel["yearly"].copy()
    elif rel["pulse"] is not None:
        yearly_df = rel["pulse"]["yearly"].copy()
    else:
        yearly_df = pd.DataFrame(columns=["year", "copubs"])
    # the three relationship tiles' own values ride along on this sheet
    # too (repeated on every row -- a pair-level fact, the same flat-table
    # convention `reciprocity_frame`'s own rank_in_a/rank_in_b already use),
    # since the workbook has no separate "tiles" sheet of its own.
    if rel["momentum"] is not None and len(yearly_df):
        yearly_df["joint_publications_core_total"] = rel["core_total"]
        yearly_df["joint_star_papers"] = rel.get("joint_stars") or 0
        yearly_df["momentum"] = rel["momentum"]["text"]
    recip_df = rel["reciprocity"]
    return [
        (Cw["XLSX_SHEET_CARDS"], cards_df),
        (Cw["XLSX_SHEET_SUBFIELDS"], subfields_df),
        (Cw["XLSX_SHEET_SDG"], sdg_df),
        (Cw["XLSX_SHEET_TOPIC_OVERLAP"], overlap_df),
        (Cw["XLSX_SHEET_RELATIONSHIP_YEARLY"], yearly_df),
        (Cw["XLSX_SHEET_RECIPROCITY"], recip_df),
    ]


@st.cache_data(show_spinner=False, max_entries=8, ttl=1800)
def _workbook_bytes(ids: tuple[str, str], mode: str, n: int, fwci_stat: str) -> bytes:
    """Keyed on the hashable id pair PLUS the topic-overlap selector state
    -- ctx/subs are fetched inside, from the process-wide scenario cache,
    never passed in as arguments. The selector state must be part of the
    key: two different selections must not silently share one cached
    workbook."""
    ctx = SC.bundle()["ctx"]
    subs = SC.get("bestfit", "full")
    return workbook_bytes(_workbook_sheets(ctx, subs, list(ids), mode, n, fwci_stat))


def _render_export(ids: list[str], mode: str, n: int, fwci_stat: str) -> None:
    Cw = copy.COMPARE
    st.download_button(
        Cw["EXPORT_BUTTON"], lambda: _workbook_bytes(tuple(ids), mode, n, fwci_stat),
        file_name=workbook_filename(ids), mime=XLSX_MIME,
        help=Cw["EXPORT_HELP"], key="dl_compare_workbook")


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def render() -> None:
    st.title(copy.COMPARE["PAGE_TITLE"])
    st.caption(copy.COMPARE["PAGE_INTRO"])

    bundle = SC.bundle()
    ctx = bundle["ctx"]

    picks = selection.render_slots(COMPARE_SLOTS, search=_search)
    ids = [p for p in picks if p][:2]
    if len(ids) < 2:
        st.info(copy.COMPARE["PROMPT_NEED_TWO"])
        return

    names, slots = _names_and_slots(ctx, ids)
    st.markdown(X.basis_caption(copy.COMPARE["PIN_CAPTION"].format(
        y0=CORE_Y0, y1=CORE_Y1, whole_y1=WHOLE_Y1)), unsafe_allow_html=True)

    subs = SC.get("bestfit", "full")

    _render_cards(ctx, ids, names, slots)
    _render_shape(ctx, subs, ids, names, slots)
    _render_sdg(ctx, subs, ids, names, slots)
    topic_mode, topic_n, topic_fwci_stat = _render_topic_overlap(ctx, ids, names, slots)
    _render_relationship(ctx, subs, ids, names, slots)

    st.divider()
    _render_export(ids, topic_mode, topic_n, topic_fwci_stat)
    selection.share_link_block("compare", ids, caption=copy.COMPARE["DEEPLINK_LABEL"])
