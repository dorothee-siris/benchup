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
-> Frontier (positioning figures, then the shared-frontier mirror chart
+ full table) -> The relationship (momentum, yearly-by-domain, strategic
reciprocity, joint star papers) -> one Excel download -> the share-link
box.

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

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import charts as C
from lib import compare_data as CD
from lib import copy
from lib import charts_compare as X
from lib import palette as P
from lib import selection, tiles
from lib.app_config import CFG
from lib.charts_compare import _esc, _fmt_frontier, _fmt_pct as _pct, _fmt_si, _fmt_vol as _count
from lib.engine import scenario_cache as SC
from lib.exports_xlsx import XLSX_MIME, workbook_bytes, workbook_filename
from lib.palette import NA_MARK
from lib.search import search as search_engine

CORE_Y0, CORE_Y1 = CFG["window"]
WHOLE_Y1 = CFG["bonus_year"]
COMPARE_SLOTS = int(CFG.get("compare_slots", 2))

TOP_N_SUBFIELDS = 20        # the pair's top-20 subfields by combined volume
MIRROR_TOP_N_DEFAULT = 20   # the mirror chart's own default cut, "show all N" past it
PVAL_FLOOR = 0.001          # below this, the significance line reads "< 0.001"

TAB_KEYS = {"profile": ("share_full", "eu_mean_share"), "impact": ("pp10_wd", "eu_mean_pp10_wd")}


# ---------------------------------------------------------------------------
# formatting / identity helpers -- reuses charts_compare's own formatters
# (`_fmt_pct`/`_fmt_vol`/`_fmt_si`/`_fmt_frontier`/`_esc`) rather than a
# second implementation of the same NA_MARK-safe rules.
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


def _card_facts(ctx: dict, iid: str, row: pd.Series) -> list[tuple[str, str, str, str]]:
    """`[(column, label, value, tooltip)]`, this card's own nine-figure order. The
    ninth figure (international + company co-publication) is a two-value
    tile, rendered separately (`_copub_tile`) -- it carries no single
    "higher" reading, so it stays out of the leader-dot family.

    D23: the FWCI card's own DISPLAYED value moved from the median to the
    mean (`row["fwci_eu_mean"]`, `compare_data.cards`'s own column now --
    no side lookup on `ctx["index_by_id"]` needed any more); its "?" states
    the median, the world-referenced PP10_WD share and the population's own
    median-of-the-mean, per `docs/tooltip_spec.yaml`'s `compare_card_fwci_eu`
    tile verbatim."""
    Cw = copy.COMPARE
    return [
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
    value = f'{_pct(row["intl_share"])} · {_pct(row["company_share"])}'
    html = _card_html(Cw["CARD_COPUB"], value, "")
    return html, tip


def _render_cards(ctx: dict, ids: list[str], names: dict, slots: dict) -> pd.DataFrame:
    st.subheader(copy.COMPARE["CARDS_HEADER"])
    df = CD.cards(ctx, ids)
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

    if not tabs:
        # the SDG section (its own frame's vol_full/vol_frac are the CORE
        # window, not whole-run -- see _metric_hover's own docstring)
        fig = X.two_tab_bars(_frame("profile"), "profile", names, slots, grouped_by_field=grouped,
                             y0=CORE_Y0, y1=CORE_Y1)
        st.plotly_chart(fig, width="stretch", key=f"fig_{key_prefix}_profile")
        st.markdown(X.chart_note(note_profile), unsafe_allow_html=True)
        return

    tab_profile, tab_impact = st.tabs([copy.COMPARE["TAB_PROFILE"], copy.COMPARE["TAB_IMPACT"]])
    with tab_profile:
        fig = X.two_tab_bars(_frame("profile"), "profile", names, slots, grouped_by_field=grouped,
                             y0=CORE_Y0, whole_y1=WHOLE_Y1)
        st.plotly_chart(fig, width="stretch", key=f"fig_{key_prefix}_profile")
        st.markdown(X.chart_note(note_profile), unsafe_allow_html=True)
    with tab_impact:
        fig = X.two_tab_bars(_frame("impact"), "impact", names, slots, grouped_by_field=grouped)
        st.plotly_chart(fig, width="stretch", key=f"fig_{key_prefix}_impact")
        st.markdown(X.chart_note(note_impact.format(floor=int(P.RATIO_HATCH_FLOOR))), unsafe_allow_html=True)


def _render_shape(ctx: dict, subs: dict, ids: list[str], names: dict, slots: dict) -> pd.DataFrame:
    df = CD.top_subfields(ctx, subs, ids, n=TOP_N_SUBFIELDS)
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
    df = CD.sdg_frame(ctx, subs, ids)
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
# 4. Frontier -- positioning figures, then the shared-frontier deep dive.
# ---------------------------------------------------------------------------

def _render_frontier_positioning(ctx: dict, subs: dict, ids: list[str], names: dict, slots: dict) -> pd.DataFrame:
    Cw = copy.COMPARE
    st.subheader(Cw["FRONTIER_HEADER"])
    pos = CD.frontier_positioning(ctx, subs, ids)
    cells = pos.set_index("institution_id")
    cols = st.columns(len(ids))
    for col, iid in zip(cols, ids):
        row = cells.loc[iid]
        with col:
            colour = P.institution_color(slots[iid])
            st.markdown(f'<span style="color:{colour}">●</span> **{_esc(names[iid])}**',
                        unsafe_allow_html=True)
            st.metric(Cw["FRONTIER_POSITIONING_SHARE"], _pct(row["share_top25"]))
            st.metric(Cw["FRONTIER_POSITIONING_PUBLISHED"], _count(row["n_top25_topics_published"]))
            st.metric(Cw["FRONTIER_POSITIONING_TOP_DECILE"], _count(row["n_of_those_top_decile"]))
            st.metric(Cw["FRONTIER_POSITIONING_LED"], _count(row["n_topics_led_fair"]))
            st.metric(Cw["FRONTIER_POSITIONING_STARS"], _count(row["n_stars_in_frontier_topics"]))
    st.caption(Cw["FRONTIER_SHARED_LINE"].format(n=_count(pos.attrs.get("n_shared", 0))))
    st.markdown(X.basis_caption(Cw["FRONTIER_POSITIONING_TIP"].format(y0=CORE_Y0, y1=CORE_Y1)),
               unsafe_allow_html=True)
    return pos


def _toggle_frontier_show_all() -> None:
    """on_click target -- a plain session_state flip, with no manual rerun
    call after it (known lesson: stacking one on top of a widget's own rerun
    poisons every `st.download_button` for the session)."""
    st.session_state["compare_frontier_show_all"] = True


def _rank_label(rank, pool) -> str:
    if pd.isna(rank):
        return NA_MARK
    pool_label = (copy.COMPARE["RANK_POOL_UNIVERSITIES"] if pool == "education"
                 else copy.COMPARE["RANK_POOL_ALL"])
    return f"#{int(rank)} · {pool_label}"


def _change_label(change, low) -> str:
    if pd.isna(change):
        return NA_MARK
    dagger = X.LOW_VOLUME_GLYPH if low else ""
    return f"{change:+.1f}{dagger}"


def _join_keywords(raw) -> str:
    """`topics_dim.parquet`'s own `keywords` column ships '|'-joined (the
    same convention `topic_name`/other taxonomy fields use internally),
    but a reader-facing column reads that
    delimiter as a literal pipe character, not a list separator. Reused for
    BOTH the on-page table and the workbook's "Shared frontier" sheet --
    one keywords convention throughout beats a table that reads differently
    from its own downloaded twin."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return NA_MARK
    return ", ".join(str(raw).split("|"))


def _render_shared_frontier_table(frame: pd.DataFrame, ids: list[str], names: dict) -> None:
    Cw = copy.COMPARE
    a, b = ids
    name_a, name_b = names[a], names[b]
    disp = pd.DataFrame({
        "topic": [f"{t}{' ' + X.TOP_DECILE_GLYPH if d else ''}"
                 for t, d in zip(frame["topic_name"], frame["is_top_decile"])],
        "keywords": [_join_keywords(v) for v in frame["keywords"]],
        "frontierness": [_fmt_frontier(v) for v in frame["frontier_score"]],
        "expansion": [_fmt_frontier(v) for v in frame["expansion"]],
        "acceleration": [_fmt_frontier(v) for v in frame["acceleration"]],
        "vol_a": frame["vol_a"],
        "vol_b": frame["vol_b"],
        "vol_joint": [NA_MARK if not k else _count(v)
                     for k, v in zip(frame["joint_known"], frame["vol_joint"])],
        "change_a": [_change_label(c, low) for c, low in zip(frame["change_a"], frame["low_volume_a"])],
        "change_b": [_change_label(c, low) for c, low in zip(frame["change_b"], frame["low_volume_b"])],
        "rank_a": [_rank_label(r, p) for r, p in zip(frame["rank_a"], frame["pool_a"])],
        "rank_b": [_rank_label(r, p) for r, p in zip(frame["rank_b"], frame["pool_b"])],
        "stars_a": frame["stars_a"],
        "stars_b": frame["stars_b"],
        "url_a": frame["url_a"],
        "url_b": frame["url_b"],
        "url_joint": frame["url_joint"],
    })
    st.dataframe(
        disp, hide_index=True, width="stretch", key="tbl_shared_frontier",
        column_config={
            "topic": st.column_config.TextColumn(Cw["COL_TOPIC"]),
            "keywords": st.column_config.TextColumn(Cw["COL_KEYWORDS"]),
            "frontierness": st.column_config.TextColumn(Cw["COL_FRONTIERNESS"]),
            "expansion": st.column_config.TextColumn(Cw["COL_EXPANSION"]),
            "acceleration": st.column_config.TextColumn(Cw["COL_ACCELERATION"]),
            "vol_a": st.column_config.NumberColumn(Cw["COL_VOL"].format(name=name_a)),
            "vol_b": st.column_config.NumberColumn(Cw["COL_VOL"].format(name=name_b)),
            "vol_joint": st.column_config.TextColumn(Cw["COL_VOL_JOINT"]),
            "change_a": st.column_config.TextColumn(Cw["COL_CHANGE"].format(name=name_a)),
            "change_b": st.column_config.TextColumn(Cw["COL_CHANGE"].format(name=name_b)),
            "rank_a": st.column_config.TextColumn(Cw["COL_RANK"].format(name=name_a)),
            "rank_b": st.column_config.TextColumn(Cw["COL_RANK"].format(name=name_b)),
            "stars_a": st.column_config.NumberColumn(Cw["COL_STARS"].format(name=name_a)),
            "stars_b": st.column_config.NumberColumn(Cw["COL_STARS"].format(name=name_b)),
            "url_a": st.column_config.LinkColumn(Cw["COL_LINK"].format(name=name_a), display_text=name_a),
            "url_b": st.column_config.LinkColumn(Cw["COL_LINK"].format(name=name_b), display_text=name_b),
            "url_joint": st.column_config.LinkColumn(Cw["COL_LINK_JOINT"], display_text=Cw["COL_LINK_JOINT"]),
        },
    )
    st.caption(Cw["SHARED_FRONTIER_TABLE_CAPTION"].format(
        w1=_window(CD.DYNAMICS_W1), w2=_window(CD.DYNAMICS_W2), floor=int(CD.LOW_VOLUME_FLOOR)))


def _render_shared_frontier(ctx: dict, subs: dict, ids: list[str], names: dict, slots: dict) -> pd.DataFrame:
    Cw = copy.COMPARE
    st.subheader(Cw["SHARED_FRONTIER_HEADER"])
    frame = CD.shared_frontier(ctx, subs, ids)
    if frame.empty:
        st.caption(Cw["SHARED_FRONTIER_TIP"].format(floor=int(X.JOINT_FLOOR)))
        return frame
    st.markdown(X.legend_strip(ids, slots=slots, names=names, shared=True), unsafe_allow_html=True)
    st.markdown(X.basis_caption(Cw["SHARED_FRONTIER_BASIS_CAPTION"]), unsafe_allow_html=True)
    show_all = bool(st.session_state.get("compare_frontier_show_all", False))
    top_n = None if show_all else MIRROR_TOP_N_DEFAULT
    fig = X.mirror_frontier(frame, [names[ids[0]], names[ids[1]]], [slots[ids[0]], slots[ids[1]]],
                            top_n=top_n)
    st.plotly_chart(fig, width="stretch", key="fig_mirror_frontier")
    if not show_all and len(frame) > MIRROR_TOP_N_DEFAULT:
        st.button(Cw["SHOW_ALL"].format(n=len(frame)), key="btn_frontier_show_all",
                 on_click=_toggle_frontier_show_all)
    st.markdown(X.chart_note(Cw["SHARED_FRONTIER_NOTE"],
                             Cw["SHARED_FRONTIER_TIP"].format(floor=int(X.JOINT_FLOOR))),
               unsafe_allow_html=True)
    _render_shared_frontier_table(frame, ids, names)
    return frame


# ---------------------------------------------------------------------------
# 5. The relationship -- momentum, yearly-by-domain, reciprocity, stars.
# ---------------------------------------------------------------------------

def _momentum_evidence_line(mom: dict, facts: dict) -> str:
    """D27's always-visible evidence sentence, filled from the pair's own
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
    """The relationship block's three tiles, one row (D27) -- the SAME
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
    rel = CD.relationship(ctx, ids, subs)
    if rel["momentum"] is None:
        st.caption(Cw["RELATIONSHIP_NEVER"])
        return rel

    _render_relationship_tiles(ctx, rel)

    if rel["yearly_qualifies"] and len(rel["yearly"]):
        fig = X.yearly_domain_stack(rel["yearly"])
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

    recip = rel["reciprocity"]
    if len(recip):
        st.markdown(f"##### {Cw['RECIPROCITY_HEADER']}")
        fig = X.reciprocity_scatter(recip, [names[ids[0]], names[ids[1]]], [slots[ids[0]], slots[ids[1]]])
        st.plotly_chart(fig, width="stretch", key="fig_reciprocity")
        st.caption(Cw["RECIPROCITY_CAPTION"])

    return rel


# ---------------------------------------------------------------------------
# 6. One Excel at the end, then the share-link box.
# ---------------------------------------------------------------------------

def _workbook_sheets(ctx: dict, subs: dict, ids: list[str]) -> list[tuple[str, pd.DataFrame]]:
    """The SEVEN sheets `copy.COMPARE` names, in that order -- pure function (no
    Streamlit), so it is directly unit-testable and directly what
    `_workbook_bytes` (the cached wrapper) calls."""
    Cw = copy.COMPARE
    cards_df = CD.cards(ctx, ids)
    subfields_df = CD.all_subfields(ctx, subs, ids)
    sdg_df = CD.sdg_frame(ctx, subs, ids)
    pos_df = CD.frontier_positioning(ctx, subs, ids)
    shared_df = CD.shared_frontier(ctx, subs, ids)
    rel = CD.relationship(ctx, ids, subs)
    if rel["yearly_qualifies"] and len(rel["yearly"]):
        yearly_df = rel["yearly"].copy()
    elif rel["pulse"] is not None:
        yearly_df = rel["pulse"]["yearly"].copy()
    else:
        yearly_df = pd.DataFrame(columns=["year", "copubs"])
    # D27: the three relationship tiles' own values ride along on this sheet
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
        (Cw["XLSX_SHEET_POSITIONING"], pos_df),
        (Cw["XLSX_SHEET_SHARED_FRONTIER"], shared_df),
        (Cw["XLSX_SHEET_RELATIONSHIP_YEARLY"], yearly_df),
        (Cw["XLSX_SHEET_RECIPROCITY"], recip_df),
    ]


@st.cache_data(show_spinner=False, max_entries=8, ttl=1800)
def _workbook_bytes(ids: tuple[str, str]) -> bytes:
    """Keyed on the hashable id pair ALONE -- ctx/subs are fetched
    inside, from the process-wide scenario cache, never passed in as
    arguments."""
    ctx = SC.bundle()["ctx"]
    subs = SC.get("bestfit", "full")
    return workbook_bytes(_workbook_sheets(ctx, subs, list(ids)))


def _render_export(ids: list[str]) -> None:
    Cw = copy.COMPARE
    st.download_button(
        Cw["EXPORT_BUTTON"], lambda: _workbook_bytes(tuple(ids)),
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
    _render_frontier_positioning(ctx, subs, ids, names, slots)
    _render_shared_frontier(ctx, subs, ids, names, slots)
    _render_relationship(ctx, subs, ids, names, slots)

    st.divider()
    _render_export(ids)
    selection.share_link_block("compare", ids, caption=copy.COMPARE["DEEPLINK_LABEL"])
