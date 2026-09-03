"""
app/lib/views_find.py -- render functions for the Find page.

COMPOSITION ONLY: every ranking, filter, badge, frame, figure, table shape,
string and number comes from lib/engine and lib/{profile_data,charts,tiles,
wordcloud_png,ranked,search,filters,badges,exports,links,countries,copy,state,
palette,app_config,data_cache}. Nothing here re-implements them and nothing
here types a value into a rendered string.

PAGE ORDER (top to bottom, the order the code below follows): title + one-line
promise (`_header`) -> the "Filtered by." strip slot right under it -> a
free-text institution search -> PROFILE section: row 1 in two halves (eight
KPI cards in a 2 x 4 grid, name first and all methodology in a `?` -- the six
original plus the two P5 KPIs (star papers, topics led)
adds | the identity block with the subfield wordcloud under it), row 2 full
width (a titled section, one segmented control and one chip legend above a
height-matched global + yearly breakdown pair whose bonus year is starred on
the axis), then six collapsed chart panels -> BENCHMARK section, headed by the
controls row (C1, L7, a post-filters expander -- D17 retires the depth radio:
the cut is the fixed `BENCHMARK_DEPTH` everywhere the page cuts) and the "How
to read the lenses" guide -> the lens tabs, labelled by the bare
`copy.LENS_DISPLAY_CODE` (L0.L9, renumbered in tab order; the full
`copy.LENS_DISPLAY_NAMES` sentence moved inside each tab body). The SIDEBAR
holds only counting & taxonomy (tree, basis) -- there is no shared sidebar
search or shared selection list any more: each page
owns its own search now, Find's own is `_seed_pick` below.

  Meta text: the verdict line and the data-from caption sit at the FOOT of
  the page (`_footer_meta`), after every section -- the promise a reader
  needs before scrolling is one line; the provenance a reader needs is not
  urgent enough to spend that line.

PERFORMANCE SHAPE: the engine context and ONE resident (tree, basis) scenario
are process-wide caches behind `lib.engine.scenario_cache` (`SC.bundle` /
`SC.get(tree, basis)`, ) -- switching scenario evicts the
previous one rather than accumulating a second, which is what keeps this app
under its RAM ceiling. `rank_all` is cheap and recomputed every rerun;
`build_rows` over a full ranking is not, so rows are built only for what is
actually shown -- the post-filtered depth cut, the tail-search matches, and
(lazily, through `st.download_button`'s callable `data`) the workbook.
`st.expander` bodies EXECUTE on every rerun even when collapsed -- only the
display folds -- so the six chart-panel frames are their own `@st.cache_data`,
keyed on the hashable (iid, tree, basis), fetching ctx/subs from the
scenario_cache internally (never passed as cache_data arguments, per E4).

STRINGS: every user-facing string lives in `lib/copy.py` under its own
digit-ban rule -- no digit outside a lens code / "top10"; every number is a
`{placeholder}` filled here from CFG or the live data
(`tests/test_narrative.py` enforces this over this file's `st.*` calls). The
two exceptions this stream adds are `KPI_STARS_LABEL` /
`KPI_LED_LABEL` below -- module constants rather than `copy.py` entries
because that file is another stream's this wave; moves them in.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from lib import baselines, charts, copy, countries, links, profile_data, state, tiles
from lib import palette as P
from lib.app_config import CFG
from lib.badges import badges_for, corrected_from
from lib.charts_compare import chart_note
from lib.data_cache import doctype_by_year, manifest
from lib.engine import (
    ALL_LENSES, CONCORDANCE_N, aspirational, aspirational_frontier, build_rows,
    concordance, cut_with_ties, family_overlap_scores, rank_all, seed_card,
)
from lib.engine import scenario_cache as SC
from lib.engine.evidence import rows_evidence
from lib.exports import data_date_label
from lib.exports_xlsx import XLSX_MIME, workbook_bytes
from lib.filters import active_controls_strip, apply_filters, explain_empty
from lib.palette import NA_MARK
from lib.ranked import (
    NAME_LINK_MODE, WORKS_LINK_FALLBACK_LABEL, _pct100, concordance_caption,
    format_concordance, format_rows, pct_progress_column, render_concordance_table,
    render_ranked_table, works_link_named,
)
from lib.search import normalize, search
from lib.wordcloud_png import render_wordcloud_png

# The C1 lens restricts L1 to the seed's top-N subfields; N is a bare literal
# inside lib/engine/lenses.py:build_c1_for_seed (`np.argsort(.)[:20]`), which
# is vendored file and gives it no name. Read here ONCE so no
# rendered string ever types it.
CORE_TOP_N = 20

# The displayed cut of the "top N" profile panels and of the frontier panel's
# default top-N. Module constants, never a digit inside a caption: the
# captions take them as `{n}` placeholders. SUBFIELDS_TOP_N is 30 under
# R2/L34 (the panel also lost its sort toggle: "top 30" is itself a
# volume-ordered concept, and a taxonomy re-sort of a volume-defined cut reads
# as an arbitrary 30 rows in ID order). TOPICS_TOP_N is 30 under (FB
# handoff, was 20; the topics panel lost its sort toggle for the same reason
# as subfields -- `charts.fig_topics`'s `sort` kwarg is accepted but ignored).
# FRONTIER_TOP_N is the frontier panel's own top-N slider default (:
# was a fixed two-hundred-topic volume-mode cut; now ONE slider drives BOTH
# modes, `_panel_frontier` below).
SUBFIELDS_TOP_N = 30
TOPICS_TOP_N = 30
FRONTIER_TOP_N = 200
FRONTIER_TOPN_MIN = 20
FRONTIER_TOPN_MAX = 200
FRONTIER_TOPN_STEP = 20

SEP = "·"   # middle dot -- the separator copy.STRIP_JOIN already uses
DASH = "–"  # en dash -- interval rendering

WINDOW_START, WINDOW_END = CFG["window"]

# D17: the 30/50 depth radio is retired -- the benchmark cut is always this
# constant (config.yaml pins depth.default == depth.max == 50, so this reads
# the same 50 `lib.engine.DEPTH` does). Every caption still names the cut.
BENCHMARK_DEPTH = CFG["depth"]["max"]

# D5: the two window labels the SDG/ERC panel basis
# captions name, built from CFG so no digit is ever typed into a string
#  -- CORPUS_WINDOW_LABEL is the five-year window this
# page states everywhere else; SDG_ERC_WINDOW_LABEL is the whole-run,
# six-year window `sdg.parquet`/`erc.parquet` are actually denominated on
# (window_conventions.sdg_mass_window, docs/data_contract.yaml) -- the bonus
# year IS included there, unlike every impact indicator on this page.
CORPUS_WINDOW_LABEL = f"{WINDOW_START}{DASH}{WINDOW_END}"
SDG_ERC_WINDOW_LABEL = f"{WINDOW_START}{DASH}{CFG['bonus_year']}"

# Layout constants (VIZ_SPEC S1.9 / S2.11 / S2.21). Streamlit collapses a
# horizontal block to a vertical stack below its own small breakpoint, which is
# what makes the cards wrap one-per-row at 390 px with no media query.
#
# The cards fill the LEFT half (columns 1-2) and the identity block with the
# wordcloud under it fills the right (columns 3-4). adds two
# more cards -- star papers, topics led (P5) -- to the original six, so the
# grid grows from 3 rows to 4; card width is unchanged (still half of half the
# content box).
N_CARDS = 8
CARD_GRID_COLS = 2                     # 4 rows x 2 cards (D9: +star papers, +topics led)
PROFILE_ROW1_WIDTHS = [1, 1]           # the eight cards | identity + wordcloud
PROFILE_ROW2_WIDTHS = [1, 1]           # global breakdown | yearly breakdown
CONTROLS_ROW_WIDTHS = [1, 1, 2]        # C1 | L7 | post-filters expander

# : the bonus year is marked ON the axis instead of banner-ed under the
# pair. The footnote itself moved into the section's `?` tooltip
# (copy.FIND["BREAKDOWN_SECTION_HELP"]).
BONUS_STAR = "*"

# : the two co-publication measures. landed these columns on
# `index.parquet`; `_identity_fact` still reads n/a for an institution whose
# value is null, and for the whole column should a rebuild ever drop it.
# -6 promotes both from identity facts to CARDS, so each is now measured
# against the index like every other card -- see `_extra_baselines`.
INTL_COLUMN = "intl_share"
COMPANY_COLUMN = "company_share"

# The one card whose small line is NOT the index baseline: it carries
# the same measure on the fractional basis instead. Named here so `_card_specs`
# and `_profile_cards` agree on which card that is without either of them
# counting positions in a list.
KPI_PUBS_KEY = "total_full_2020_2024"

# : the two P5 KPI tiles. Labels moved to `copy.FIND`
# ; both render MISSING_KPI_MARK, never NA_MARK (used everywhere
# else on this page), so "the P5 columns are not on this deployed index
# yet" reads distinctly from "this institution has no value here".
MISSING_KPI_MARK = "—"
KPI_STARS_LABEL = copy.FIND["KPI_STARS_LABEL"]
KPI_LED_LABEL = copy.FIND["KPI_LED_LABEL"]
_STARS_SUBLINE = "world top 1% by citations, 2020–2024"
_STARS_HELP = ("A star paper is one of the world's top 1% most-cited articles or reviews "
              "in its topic and publication year, 2020-2024 (ties beyond the cut are not "
              "counted). The share is star papers over this institution's own article and "
              "review output in the same window.")
_LED_SUBLINE_TEMPLATE = "world top-10 publisher, {pool}"
_LED_HELP_TEMPLATE = "World top-10 publisher in {n} topics ({pool} pool)."

SORT_VOLUME, SORT_TAXONOMY = "volume", "taxonomy"


# ------------------------------------------------- profile frames (cached)
# One @st.cache_data per S9.4 profile table, keyed on the HASHABLE scenario
# identity (iid, tree, basis) and fetching ctx/subs from
# `lib.engine.scenario_cache` internally -- ctx and subs are unhashable, so
# they are never cache_data arguments (E4). `st.expander` bodies execute on
# every rerun, so without these every collapsed panel would recompute its
# frame each time the user touched any control.

@st.cache_data(show_spinner=False, max_entries=24)
def _fields_frame(iid: str, tree: str, basis: str) -> pd.DataFrame:
    return profile_data.fields_table(SC.bundle()["ctx"], SC.get(tree, basis), iid)


@st.cache_data(show_spinner=False, max_entries=24)
def _subfields_frame(iid: str, tree: str, basis: str) -> pd.DataFrame:
    return profile_data.subfields_table(SC.bundle()["ctx"], SC.get(tree, basis), iid)


@st.cache_data(show_spinner=False, max_entries=12)
def _topics_frame(iid: str, tree: str, basis: str) -> pd.DataFrame:
    return profile_data.topics_table(SC.bundle()["ctx"], SC.get(tree, basis), iid)


@st.cache_data(show_spinner=False, max_entries=24)
def _yearly_domain_frame(iid: str, tree: str) -> pd.DataFrame:
    """Basis-independent in its KEY: the frame carries both `vol_full` and
    `vol_frac`, and the caller picks the column the active basis names."""
    return profile_data.yearly_by_domain(SC.bundle()["ctx"], iid, tree)


@st.cache_data(show_spinner=False, max_entries=24)
def _yearly_doctype_frame(iid: str) -> pd.DataFrame:
    """The R1 doc-type artefact, sliced to one institution. Neither tree- nor
    basis-scoped: a document type has no taxonomy tree, and the table ships
    both bases (progress/R1_S5.md S9). `doc_type` is a CATEGORY dtype in the
    parquet -- cast to str here, once, so no downstream `.map` ever meets a
    categorical (Assembly Line gotcha)."""
    df = doctype_by_year()
    out = df[df["institution_id"] == iid].copy()
    out["doc_type"] = out["doc_type"].astype(str)
    return out[["year", "doc_type", "vol_full", "vol_frac"]].reset_index(drop=True)


@st.cache_data(show_spinner=False, max_entries=24)
def _sdg_frame(iid: str) -> pd.DataFrame:
    return profile_data.sdg_table(SC.bundle()["ctx"], iid)


@st.cache_data(show_spinner=False, max_entries=24)
def _wordcloud_inputs(iid: str, tree: str, basis: str) -> tuple[dict, dict]:
    """`({subfield_name: weight}, {subfield_name: domain_id})` -- plain dicts,
    so `wordcloud_png.render_wordcloud_png` (itself cache_data) can hash them."""
    weights, domains = profile_data.wordcloud_weights(SC.bundle()["ctx"], SC.get(tree, basis), iid)
    return {str(k): float(v) for k, v in weights.items()}, {str(k): v for k, v in domains.items()}


def _vol_col(basis: str) -> str:
    """The volume column the active counting basis names -- the gutter number,
    the wordcloud weight, the bubble area and the breakdown bars all read it."""
    return "vol_frac" if basis == "frac" else "vol_full"


# ------------------------------------------------------------- sidebar ------

def _sidebar_scenario() -> dict:
    """L16: the sidebar holds ONLY what is app-wide -- the scenario (tree x
    basis), which re-derives every shape on the page, profile panels included.
    Depth, C1, L7 and the post-filters moved to the controls row at the head of
    the Benchmark section; their widget KEYS are unchanged by the move, so
    cross-page persistence and the Playwright selectors survive it."""
    sb = st.sidebar
    sb.header(copy.FIND["SCENARIO_HEADER"])
    trees = CFG["scenario"]["toggles"]["tree"]
    # R2/L29: the OPTION stays the internal value (every frame, every cache key
    # and every export reads it); only its rendering changes, through
    # `format_func`. A reader never meets "bestfit" or "frac" on the page again.
    tree = sb.selectbox(copy.FIND["TREE_LABEL"], trees,
                        index=trees.index(CFG["scenario"]["tree_default"]),
                        format_func=lambda v: copy.TREE_LABELS[v],
                        help=copy.FIND["TREE_HELP"], key="tree", **state.PERSIST)
    bases = CFG["scenario"]["toggles"]["basis"]
    basis = sb.selectbox(copy.FIND["BASIS_LABEL"], bases,
                         index=bases.index(CFG["scenario"]["basis_default"]),
                         format_func=lambda v: copy.BASIS_LABELS[v],
                         help=copy.FIND["BASIS_HELP"], key="basis", **state.PERSIST)
    return {"tree": tree, "basis": basis}


def _strip_tree(tree: str) -> str:
    """The value `filters.active_controls_strip` should receive for `tree`.

    That function uses its `tree` argument for TWO jobs at once: the off-default
    TEST (against `CFG["scenario"]["tree_default"]`, an internal value) and the
    strip's own DISPLAY text (`copy.STRIP_TREE`). Handing it the display label
    unconditionally would make the test never match and pin the strip open at
    the defaults; handing it the internal value keeps "bestfit" on screen, which
    L29 removed everywhere else. So the internal value goes in when it IS the
    default (the only case the test reads it) and the display label otherwise
    (the only case the text is rendered). Splitting that argument in two belongs
    in `lib/filters.py`, another stream's file this wave."""
    default = CFG["scenario"]["tree_default"]
    return default if tree == default else copy.TREE_LABELS[tree]


# ------------------------------------------------------- header + search ----
#  (BenchUp V4 trim) retired the shared sidebar search and the
# selection list it fed -- `_seed_pick` below now runs its own free-text
# search directly, over the same engine `lib.search.search` and this page's
# own tail search already use. `_header` is compacted to title + promise
# only; the verdict line and data-from caption it used to carry are
# `_footer_meta`, called once at the very end of `render`.


def _hit_label(hits: list[dict], iid: str) -> str:
    """name. country. type. size -- the candidate line `_seed_pick`'s own
    multi-hit picker uses, country by NAME."""
    h = next(x for x in hits if x["id"] == iid)
    total = h["total_full_2020_2024"]
    if total is None or pd.isna(total):
        size = NA_MARK
    else:
        size = f"{total:,.0f}"
    return (f"{h['display_name']} {SEP} {countries.name(h['country_code'])} {SEP} "
            f"{h['type']} {SEP} {size}")

def _header() -> None:
    """Title + the one-line promise. Everything this function used to also carry
    the standing verdict line, the data-from stamp -- is `_footer_meta` now."""
    st.title(copy.FIND["PAGE_TITLE"])
    st.caption(copy.FIND["PAGE_INTRO"])


def _footer_meta(bundle: dict, workbook_kwargs: dict | None = None) -> None:
    """The meta text SEL demotes to the FOOT of the page: the standing
    verdict line and the data stamp. Called once, at the very end
    of `render`, after every section.

    E7: `workbook_kwargs`, when given (a profile is on
    screen), renders the ONE end-of-page download button right after the data
    caption -- the same "index size, then the one download" order Compare's
    own footer uses. `None` on the seed-less early return: there is nothing
    to export yet."""
    st.markdown("---")
    st.markdown(f"**{copy.VERDICT_LINE}**")
    mf = manifest()
    # ops/deploy.py writes `source_manifest_generated_at` / `deployed_at`; the
    # pre-staged source_manifest.json writes `generated_at`. The SOURCE stamp is
    # preferred here (it dates the harvest, which is what "data from" claims);
    # `deployed_at` only dates the copy into app/data/.
    stamp = (mf.get("source_manifest_generated_at") or mf.get("generated_at")
             or mf.get("deployed_at"))
    st.caption(copy.FIND["DATA_CAPTION"].format(
        n_institutions=f"{len(bundle['index_df']):,}", sep=SEP,
        date=data_date_label(stamp, NA_MARK)))
    if workbook_kwargs is not None:
        _find_exports(**workbook_kwargs)


# A short hit list, never every match -- relevance over raw recall, the same
# convention `lib.selection`'s own Compare slots use.
SEED_SEARCH_TOP_N = 10


def _seed_pick(bundle: dict) -> str | None:
    """A free-text institution search: a text box over `lib.search.search`
    (the SAME engine the tail search on this page already uses) plus, when
    the query has more than one hit, a picker over the top ones. No query
    yet (and no prior pick this session) shows the empty-state prompt; ONE
    hit AUTO-SELECTS itself (no click needed); MORE than one still needs an
    explicit pick -- the "never load a match silently" guarantee the retired
    shared-selection dropdown used to give, now read off a live search instead.

    A pick already made (this session, or a page hop, or the `?seed=`
    hydration in `render`) survives an emptied or changed query -- `seed_id`
    is the SAME plain (non-widget) session key the rest of this file already
    reads. Picking (or auto-picking) an id also calls `state.set_find_seed`, so a Compare visit right after this one
    pre-fills its first slot with it."""
    query = st.text_input(copy.FIND["SEED_SEARCH_LABEL"], key="seed_query", **state.PERSIST)
    hits = search(query, bundle["search_idx"], k=SEED_SEARCH_TOP_N) if query else []
    if not hits:
        current = st.session_state.get("seed_id")
        if current:
            return current
        st.info(copy.FIND["SEED_PROMPT"])
        return None
    ids = [h["id"] for h in hits]
    if len(ids) == 1:
        pick = ids[0]
    else:
        names = {h["id"]: _hit_label(hits, h["id"]) for h in hits}
        # A query edit can leave the widget's OWN prior state pointing at an
        # id that is no longer an option, which would make st.selectbox raise
        # POP (never reassign) so `index=None` below is the only thing
        # setting this key this run.
        if st.session_state.get("seed_pick") not in ids:
            st.session_state.pop("seed_pick", None)
        pick = st.selectbox(copy.FIND["SEED_PICK_LABEL"], ids, index=None,
                            placeholder=copy.FIND["SEED_PICK_PLACEHOLDER"],
                            format_func=lambda i: names.get(i, i), key="seed_pick")
    if pick:
        st.session_state["seed_id"] = pick
        state.set_find_seed(pick)
    return st.session_state.get("seed_id")


# ------------------------------------------------------------ formatting ----

def _pct(value) -> str:
    """One precision level per measure; NA_MARK for missing, never 0."""
    if value is None or pd.isna(value):
        return NA_MARK
    return f"{float(value):.1%}"


def _count(value) -> str:
    """Thousands separator; NA_MARK for missing."""
    if value is None or pd.isna(value):
        return NA_MARK
    return f"{float(value):,.0f}"


def _esc(value) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _basis_caption(text: str, *, warning: bool = False) -> None:
    """D5: a one-line basis or
    coverage disclosure -- a fact about the DATA, read where the ratio it
    qualifies is, never folded into a chart's own `?` (which states how to
    READ the chart, a different job). Normal state matches every other
    caption's small ink; switches to PAL's frontier red -- never bold, no
    icon box -- when the fact is a warning (a floor bites, or a page-level
    setting silently does not apply here). Same recipe as
    `views_collab._basis_caption`, so the same kind of fact reads identically
    on every page; kept local rather than imported because this file owns no
    cross-page helper module this wave."""
    color = P.WARNING_CAPTION_COLOR if warning else P.INK_SECONDARY
    st.markdown(
        f'<div style="font-size:{charts.FONT_PX}px;color:{color};'
        f'margin:{charts.CHIP_GAP_PX}px {charts.NO_PX}px;">{_esc(text)}</div>',
        unsafe_allow_html=True)


def _identity_value(row, column: str):
    """ / -6: one of the two co-publication shares as a RAW value
    (the card formats it and positions it against the index), or `None` when
    the column is absent from the index altogether.

     landed `intl_share` / `company_share` on `index.parquet`, but the
    absent-column branch is kept and tested: a rebuilt index that drops one
    must render `n/a` -- never 0, which would claim the institution
    co-publishes with nobody abroad. `pandas.Series.get` returns None for a
    missing label, so the presence check and the null check are the same
    branch; the explicit `column not in row.index` test is kept so the intent
    survives a future pandas that starts raising instead."""
    if column not in row.index:
        return None
    return row.get(column)


# ------------------------------------------------------------- profile ------

def _identity_kind(card: dict, row) -> tuple[str, str | None]:
    """-1a: (the type as it renders, the tooltip that explains a star).

    A corrected type renders INLINE -- "government* (was: facility)" -- with
    the star, and only the star, in red. That is the whole of what used to be
    a second badge, and it is why the 2A "umbrella and type-corrected are
    mutually exclusive" assertion could be retired instead of being satisfied
    by hiding one of two true facts (ten institutions carry both).

    The red comes from Streamlit's own `:red[.]` markdown directive rather
    than from a hex: `lib/palette.py` owns every colour in this app and
    `tests/test_palette.py` fails the build on a hex written anywhere else
    under `lib/`, so a one-glyph accent that Streamlit already themes is the
    honest way to get it. An uncorrected type renders exactly as before."""
    kind = str(card["type"]) if card["type"] else NA_MARK
    was = corrected_from(row)
    if was is None:
        return kind, None
    return (copy.FIND["IDENTITY_TYPE_CORRECTED"].format(
        kind=kind, star=f":red[{BONUS_STAR}]", was=was),
        copy.FIND["IDENTITY_TYPE_HELP"])


def _profile_identity(card: dict, row, bundle: dict) -> None:
    """VIZ_SPEC S2.10 / -6: the institution NAME as the link to its own
    publications in OpenAlex, then "type. city, COUNTRY NAME" with a
    correction rendered inline, then the umbrella badge if it applies, then the
    two links that point somewhere else. A missing city / ROR / homepage drops
    silently; a missing type renders NA_MARK, never a blank or a guess.

    -6 removes the "What counts as a publication" link: it pointed at the
    same URL the name now carries, and its tooltip -- the corpus definition
    moved onto the publications card, where the figure it qualifies is. What
    remains here is a row of two links, not a row of one link and one
    explanation.

    `ranked.works_link_named` is the SAME builder the benchmark tables use for
    their institution-name links (its `#<name>` fragment is inert for OpenAlex
    and is what `LinkColumn` reads back per cell); reusing it keeps one
    definition of "the works URL for an institution" in the app instead of two
    that can drift."""
    name = str(card["display_name"])
    st.markdown(f"### [{name}]({works_link_named(card['institution_id'], name)})",
                help=copy.FIND["IDENTITY_NAME_HELP"])
    country = countries.name(str(card["country_code"]))
    city = row.get("city")
    if isinstance(city, str) and city:
        place = f"{city}, {country}"
    else:
        place = country
    kind, kind_help = _identity_kind(card, row)
    # `st.caption` renders markdown, which is what carries the `:red[.]`
    # star; a plain type has no directive in it and reads exactly as before.
    st.caption(f"{kind} {SEP} {place}", help=kind_help)

    labels = badges_for(card, bundle["flags"], bundle["medians"])
    if labels:
        med = bundle["medians"].get((str(card["country_code"]), str(card["type"])))
        if med is None:
            tip = copy.UMBRELLA_TOOLTIP.format(median=NA_MARK)
        else:
            tip = copy.UMBRELLA_TOOLTIP.format(median=f"{med:,.0f}")
        st.markdown(f" {SEP} ".join(labels), help=tip)

    parts = []
    ror = row.get("ror_id")
    if isinstance(ror, str) and ror:
        parts.append(f"[{copy.FIND['LINK_ROR']}]({links.ror_url(ror)})")
    home = row.get("homepage_url")
    if isinstance(home, str) and home:
        parts.append(f"[{copy.FIND['LINK_HOMEPAGE']}]({home})")
    if parts:
        st.markdown(f" {SEP} ".join(parts))


def _baseline_sub(bundle: dict, kpi: str, value, fmt) -> str:
    """R2/L31: the tile's SECOND subline, positioning the value in the index
    "index median {m}. higher than {pct} of institutions". The median is
    formatted by the tile's OWN formatter, so a share reads as a share and a
    count as a count; a null value keeps the median visible and marks its own
    position NA_MARK (`baselines.percentile` returns None there), because a
    missing measure has no percentile but the reference still exists."""
    ref = baselines.stats(bundle["baselines"], kpi)
    pct = baselines.percentile(bundle["baselines"], kpi, value)
    if pct is None:
        pct_text = NA_MARK
    else:
        pct_text = f"{pct:.0%}"
    return copy.FIND["TILE_BASELINE_SUB"].format(median=fmt(ref["median"]), pct=pct_text, sep=SEP)


def _card_specs(card: dict, row) -> list[tuple]:
    """(baseline key, label, value, formatter, tooltip) x 6 -- the -6
    cards, in the ruled order: publications, SDG-tagged share, frontier
    top-quartile share, PP(top10%), international co-publications, industrial
    co-publications. The last two are PROMOTED here from the identity column.

    The publications card is the one card with no index line: its small line
    carries the SAME measure on the fractional basis instead, which
    is a companion figure rather than a second card. `_profile_cards` reads
    `KPI_PUBS_KEY` to tell the two forms apart, so the special case is named
    once and never inferred from a position in this list.

    What is GONE and why:
      * concentration (HHI) and breadth -- R2 had already stripped the
        concentration tile's class word because `hhi_class` called 86 % of the
        index "generalist"; the gate found the bare index equally unreadable,
        and breadth is the same statistic seen from the other side. Both are
        still in `index.parquet` and still exported;
      * the two size tiles, MERGED here: full and fractional counting are one
        measure under two conventions, and reading them as two neighbouring
        "sizes" invited exactly the subtraction they do not support;
      * the bonus-year tile -- a single year's volume next to a five-year
        window is a category error at the same visual weight; the bonus year is
        now marked where it is actually read, on the breakdown's year axis.

    Every definition that used to print as a subline under its tile is in the
    card's `?` tooltip: the card surface carries the name, the value and the
    index position, and nothing else. The publications card's tooltip also
    absorbed the corpus definition that used to hang off the retired "What
    counts as a publication" link -- it is read where the figure it
    qualifies is, not a column away.

    The PP card lost its bootstrap-interval companion line: an
    interval printed under a value on a card competed with the value at the
    same visual weight for a caveat that only ever changes a reading at the
    margin. The caveat itself is not dropped -- it is the last sentence of the
    card's own tooltip.

    `frontier_top25_share_index` (not `frontier_top25_share`) is the card's
    value: `seed_card` names the index-basis column that way, while the
    baseline key stays the `index.parquet` column name `baselines.KPI_COLUMNS`
    knows -- the same pairing R2's tile spec used."""
    window = {"y0": WINDOW_START, "y1": WINDOW_END}
    return [
        (KPI_PUBS_KEY, copy.FIND["KPI_PUBS_LABEL"],
         card["total_full_2020_2024"], _count,
         f"{copy.FIND['PUBLICATIONS_TOOLTIP'].format(bonus_year=CFG['bonus_year'], **window)} "
         f"{copy.FIND['KPI_PUBS_HELP_FULL']}"),
        ("sdg_tagged_share", copy.FIND["KPI_SDG_LABEL"],
         card["sdg_tagged_share"], _pct, copy.FIND["KPI_SDG_HELP"]),
        ("frontier_top25_share", copy.FIND["KPI_FRONTIER_LABEL"],
         card["frontier_top25_share_index"], _pct, copy.FIND["KPI_FRONTIER_HELP"]),
        ("pp_top10_frac", copy.FIND["KPI_PP_LABEL"],
         row["pp_top10_frac"], _pct, copy.FIND["KPI_PP_HELP_R2"]),
        (INTL_COLUMN, copy.FIND["KPI_INTL_LABEL"],
         _identity_value(row, INTL_COLUMN), _pct,
         copy.FIND["KPI_INTL_HELP"].format(**window)),
        (COMPANY_COLUMN, copy.FIND["KPI_COMPANY_LABEL"],
         _identity_value(row, COMPANY_COLUMN), _pct,
         copy.FIND["KPI_COMPANY_HELP"].format(**window)),
    ]


def _stars_kpi(row) -> tuple[str, str, str]:
    """(value, subline, help) for the Star-papers tile:
    'N · x.x% of output' from index.n_stars / index.star_share. MISSING_KPI_MARK for either
    half when P5 has not landed the columns on this deployed index yet, or
    the cell is null."""
    n = row.get("n_stars")
    if n is None or pd.isna(n):
        return MISSING_KPI_MARK, _STARS_SUBLINE, _STARS_HELP
    share = row.get("star_share")
    share_txt = _pct(share) if share is not None and not pd.isna(share) else NA_MARK
    return f"{_count(n)}{copy.STRIP_JOIN}{share_txt} of output", _STARS_SUBLINE, _STARS_HELP


def _led_kpi(row) -> tuple[str, str, str]:
    """(value, subline, help) for the Topics-led tile: index.n_topics_led_fair
    (P5's own fair-pool pick -- universities for `type == education`, all
    institutions otherwise, D6), MISSING_KPI_MARK when the column is absent
    or null. The pool NAME (never the raw `type` value) is stated in both the
    subline and the help text."""
    pool = "universities" if str(row.get("type")) == "education" else "all institutions"
    n = row.get("n_topics_led_fair")
    value = MISSING_KPI_MARK if n is None or pd.isna(n) else _count(n)
    return value, _LED_SUBLINE_TEMPLATE.format(pool=pool), _LED_HELP_TEMPLATE.format(n=value, pool=pool)


def _profile_cards(card: dict, row, bundle: dict) -> None:
    """Eight cards in a 2 x 4 grid filling the LEFT half of the profile row
    (cards left, identity and its wordcloud right), each `name + value + one
    small line`, with all methodology behind the card's own `?`. `n/a` (or,
    for the two P5 KPIs, MISSING_KPI_MARK) for anything the data cannot
    support -- never 0, never a hidden card.

    Streamlit stacks every row one-card-per-line below its own small
    breakpoint, so 390 px needs no media query."""
    st.markdown(f"**{copy.FIND['TILES_HEADER']}**", help=copy.FIND["BASELINE_HELP"])
    cols = []
    for _ in range(N_CARDS // CARD_GRID_COLS):
        cols.extend(st.columns(CARD_GRID_COLS))
    specs = _card_specs(card, row)
    for col, (kpi, label, value, fmt, tip) in zip(cols, specs):
        if kpi == KPI_PUBS_KEY:
            tiles.kpi_tile(col, label, fmt(value), help=tip,
                           note_template=copy.FIND["KPI_PUBS_FRAC_NOTE"],
                           note_value=_count(card["total_frac_2020_2024"]))
        else:
            tiles.kpi_tile(col, label, fmt(value),
                           _baseline_sub(bundle, kpi, value, fmt), help=tip)
    # : the two P5 KPIs read the index ROW directly (P5's own
    # columns, not the engine's seed_card) and extend the same grid by one
    # more row -- `specs` has 6 entries, so `cols[6]`/`cols[7]` are the two
    # slots `zip` above never consumed.
    stars_value, stars_sub, stars_help = _stars_kpi(row)
    tiles.kpi_tile(cols[len(specs)], KPI_STARS_LABEL, stars_value, stars_sub, help=stars_help)
    led_value, led_sub, led_help = _led_kpi(row)
    tiles.kpi_tile(cols[len(specs) + 1], KPI_LED_LABEL, led_value, led_sub, help=led_help)


def _profile_wordcloud(iid: str, ctl: dict) -> None:
    """VIZ_SPEC S2.13 /: a raster UNDER the identity block, in the left
    half of the profile row -- it illustrates what the institution works on, so
    it belongs with its name rather than in a third column competing with the
    cards. Size = publications on the current basis, colour = domain -- both
    stated in the caption, because a wordcloud whose size channel is unstated is
    a decoration.

     / A15 adds the one caveat a reader needs before comparing two
    renders: the caption's `?` says that fractional counting up-weights
    few-author (SSH) subfields and that the two bases therefore render at
    different scales. The font cap that made the cloud readable at all lives in
    `wordcloud_png.MAX_FONT_SIZE`, not here."""
    weights, domains = _wordcloud_inputs(iid, ctl["tree"], ctl["basis"])
    png = render_wordcloud_png(weights, domains)
    if png is None:
        st.caption(copy.FIND["WORDCLOUD_EMPTY"])
        return
    st.image(png, width="stretch")
    st.caption(copy.FIND["WORDCLOUD_CAPTION"].format(sep=SEP),
               help=copy.FIND["WORDCLOUD_HELP"])


def _domain_series(iid: str, ctl: dict, bundle: dict, years: list[int]):
    """(series keys, labels, colours, per-year totals) for the DOMAIN view.
    Fixed family order (`palette.OA_DOMAIN_ORDER`) plus the explicit
    "Unclassified" residual (`profile_data.UNCLASSIFIED_DOMAIN_ID`, the works
    that carry no primary topic) so this view and the document-type view sum to
    the same yearly totals -- the whole point of putting them on one control."""
    df = _yearly_domain_frame(iid, ctl["tree"])
    col = _vol_col(ctl["basis"])
    keys = [*P.OA_DOMAIN_ORDER, profile_data.UNCLASSIFIED_DOMAIN_ID]
    labels, colors, totals = {}, {}, {}
    by_key = {int(k): g for k, g in df.groupby("domain_id")}
    for k in keys:
        g = by_key.get(int(k))
        if k == profile_data.UNCLASSIFIED_DOMAIN_ID:
            labels[k] = copy.FIND["UNCLASSIFIED_LABEL"]
        else:
            labels[k] = str(bundle["domain_names"].get(k, k))
        colors[k] = P.domain_color(k)
        per_year = {} if g is None else dict(zip(g["year"], g[col]))
        totals[k] = [float(per_year.get(y, 0.0)) for y in years]
    return keys, labels, colors, totals


def _doctype_series(iid: str, ctl: dict, years: list[int]):
    """Same shape for the DOCUMENT-TYPE view, from the R1 artefact. Returns
    `None` when the institution has no doc-type rows at all, so the caller can
    disclose the fallback to the domain view instead of showing an empty pair
    (VIZ_SPEC S2.14 empty state)."""
    df = _yearly_doctype_frame(iid)
    if df.empty:
        return None
    col = _vol_col(ctl["basis"])
    keys = list(P.DOCTYPE_ORDER)
    labels = {k: P.DOCTYPE_LABELS.get(k, k) for k in keys}
    colors = {k: P.doctype_color(k) for k in keys}
    by_key = {str(k): g for k, g in df.groupby("doc_type")}
    totals = {}
    for k in keys:
        g = by_key.get(str(k))
        per_year = {} if g is None else dict(zip(g["year"], g[col]))
        totals[k] = [float(per_year.get(y, 0.0)) for y in years]
    return keys, labels, colors, totals


def _year_label(year) -> str:
    """The year as an axis tick, with the bonus year starred.

    `charts.fig_breakdown_yearly` requires STRING years (a numeric axis
    autoranges and ticks differently from every other chart in the app), so the
    star costs nothing structurally -- it rides on a label that was already
    text. The star's meaning is stated once, in the section's `?` tooltip, and
    never repeated under the figure."""
    if int(year) == int(CFG["bonus_year"]):
        return f"{int(year)}{BONUS_STAR}"
    return str(int(year))


def _profile_breakdown(iid: str, ctl: dict, bundle: dict) -> None:
    """VIZ_SPEC S2.14: ONE segmented control swapping the identity family for
    BOTH figures, ONE shared chip legend, grouped bars (never stacked), years
    as strings. The two figures can never disagree because one control drives
    them both."""
    # : the section gets a TITLE carrying the bonus-year footnote in its
    # `?`, and the control loses its "Break down by" label -- two options
    # reading "Domain" and "Document type" state their own question, so the
    # label was a line of chrome above every render. The label ARGUMENT stays
    # (Streamlit requires one, and it is what a screen reader announces); only
    # its visual rendering is collapsed.
    st.markdown(f"**{copy.FIND['BREAKDOWN_SECTION_TITLE']}**",
                help=copy.FIND["BREAKDOWN_SECTION_HELP"].format(
                    year=CFG["bonus_year"], star=BONUS_STAR))
    st.segmented_control(
        copy.FIND["BREAKDOWN_CONTROL_LABEL"],
        [copy.FIND["BREAKDOWN_DOMAIN"], copy.FIND["BREAKDOWN_DOCTYPE"]],
        default=copy.FIND["BREAKDOWN_DOMAIN"], required=True,
        key="breakdown_dim", label_visibility="collapsed", **state.PERSIST)
    pick = st.session_state.get("breakdown_dim") or copy.FIND["BREAKDOWN_DOMAIN"]

    years = sorted(int(y) for y in _yearly_domain_frame(iid, ctl["tree"])["year"].unique())
    if not years:
        st.caption(copy.FIND["PANEL_EMPTY"])
        return
    built = None
    if pick == copy.FIND["BREAKDOWN_DOCTYPE"]:
        built = _doctype_series(iid, ctl, years)
        if built is None:
            st.caption(copy.FIND["BREAKDOWN_DOCTYPE_MISSING"])
    if built is None:
        built = _domain_series(iid, ctl, bundle, years)
    keys, labels, colors, totals = built

    legend = [(labels[k], colors[k]) for k in keys]
    st.markdown(charts.chip_legend_html(legend), unsafe_allow_html=True)
    # R2/L30 reverses R1's stacking. R1 put the two figures one above the other
    # because this pair shared its row with the wordcloud, which left each
    # sub-column ~260 px of plot at 1280 px -- a width at which category labels
    # clip and value ticks rotate to vertical. The wordcloud has moved up into
    # row 1, so the pair now owns the FULL section width and each panel gets
    # ~600 px, comfortably past that failure point; side by side is what the
    # Lorraine lab card does and what makes the two reads comparable at a
    # glance. Streamlit stacks the two columns anyway below its own small
    # breakpoint, so the 390 px behaviour is exactly R1's.
    #
    #  adds the height MATCH. The two builders size themselves from
    # different rules -- the global one from its row count (six domains ->
    # 260 px), the yearly one from a fixed scatter budget (400 px) -- so the
    # pair rendered as two panels of visibly different height sitting side by
    # side, which reads as two unrelated figures rather than one split total.
    # The yearly figure is COMPRESSED onto the global one's height here, in the
    # composing view, rather than in `lib/charts.py`: the constraint is a fact
    # about this LAYOUT (these two figures, this row), not about either builder,
    # and charts.py is another stream's file this wave. Reading the height off
    # the built figure keeps the two in step if that stream retunes either rule.
    global_fig = charts.fig_breakdown_global([labels[k] for k in keys],
                                             [sum(totals[k]) for k in keys],
                                             [colors[k] for k in keys])
    # The bonus year is marked ON the axis: the banner that used to sit
    # under the pair is gone and its footnote moved into the section tooltip, so
    # the mark has to travel with the tick it qualifies.
    yearly_fig = charts.fig_breakdown_yearly([_year_label(y) for y in years],
                                             keys, labels, colors, totals)
    yearly_fig.update_layout(height=global_fig.layout.height)
    left, right = st.columns(PROFILE_ROW2_WIDTHS)
    with left:
        st.markdown(f"**{copy.FIND['BREAKDOWN_GLOBAL_TITLE']}**")
        st.plotly_chart(global_fig, width="stretch", key="fig_breakdown_global")
    with right:
        st.markdown(f"**{copy.FIND['BREAKDOWN_YEARLY_TITLE']}**")
        st.plotly_chart(yearly_fig, width="stretch", key="fig_breakdown_yearly")


# ---------------------------------------------------------- chart panels ----

def _sort_control(panel: str, default: str = SORT_VOLUME) -> str:
    """The shared sort toggle (L20). Colour follows the entity, never the rank,
    so the toggle never repaints anything -- `tests/test_charts.py` pins that."""
    options = [copy.FIND["SORT_VOLUME"], copy.FIND["SORT_TAXONOMY"]]
    idx = 0 if default == SORT_VOLUME else 1
    picked = st.radio(copy.FIND["SORT_LABEL"], options, index=idx, horizontal=True,
                      key=f"sort_{panel}", **state.PERSIST)
    return SORT_VOLUME if picked == copy.FIND["SORT_VOLUME"] else SORT_TAXONOMY


def _panel_fields(iid: str, ctl: dict, card: dict) -> None:
    """VIZ_SPEC S2.15: one row per field, coloured by its DOMAIN, share bars +
    SI lollipops. No SI floor at field grain (the G6 floor is a subfield rule
    the data contract says so on both rows)."""
    df = _fields_frame(iid, ctl["tree"], ctl["basis"])
    if df.empty:
        st.caption(copy.FIND["PANEL_EMPTY"])
        return
    sort = _sort_control("fields")
    st.plotly_chart(charts.fig_share_si(df, family="oa", sort=sort, label_col="field_name",
                                        volume_col=_vol_col(ctl["basis"])),
                    width="stretch", key="fig_fields")
    st.caption(copy.FIND["CAPTION_SI"])


def _panel_subfields(iid: str, ctl: dict, card: dict) -> None:
    """VIZ_SPEC S2.16 / R2 L34: the top SUBFIELDS_TOP_N subfields by volume on
    the current basis, and NO sort toggle -- "top 30" is itself a volume-ordered
    concept, so a taxonomy re-sort of it would read as an arbitrary 30 rows in
    ID order. The SI mark is solid at or above the solid floor, hollow between
    the two floors and absent below the thin one; `charts.fig_share_si` reads
    that off the frame's own `si_status` column, and the floors are printed from
    `profile_data`'s constants, the ONE place those numbers are typed."""
    df = _subfields_frame(iid, ctl["tree"], ctl["basis"])
    if df.empty:
        st.caption(copy.FIND["PANEL_EMPTY"])
        return
    vol = _vol_col(ctl["basis"])
    top = df.nlargest(SUBFIELDS_TOP_N, vol)
    st.plotly_chart(charts.fig_share_si(top, family="oa", sort=SORT_VOLUME,
                                        label_col="subfield_name", volume_col=vol),
                    width="stretch", key="fig_subfields")
    # -8: ONE reading line under the figure; how to read the SI mark and
    # what the two floors are move -- verbatim -- into that line's own `?`.
    floors = copy.FIND["CAPTION_SI_FLOOR"].format(
        floor_solid=int(profile_data.SI_FLOOR_SOLID),
        floor_thin=int(profile_data.SI_FLOOR_THIN))
    st.caption(copy.FIND["CAPTION_TOP_N_VOLUME"].format(n=f"{len(top):,}"),
               help=f"{copy.FIND['CAPTION_SI']} {floors}")


def _panel_topics(iid: str, ctl: dict, card: dict) -> None:
    """VIZ_SPEC S2.17: the top topics by share. A catch-all (out-of-scope, 811)
    topic is FLAGGED and COUNTED, never dropped -- its presence is exactly what
    a reader needs in order to discount every other number in the section.

     (FB handoff): no sort control -- `charts.fig_topics` is always
    volume-ordered now (the toggle would be dead UI, same reasoning as the
    subfields panel losing its own toggle under R2/L34)."""
    df = _topics_frame(iid, ctl["tree"], ctl["basis"])
    if df.empty:
        st.caption(copy.FIND["PANEL_EMPTY"])
        return
    top = df.nlargest(TOPICS_TOP_N, "share")
    st.plotly_chart(charts.fig_topics(top, volume_col=_vol_col(ctl["basis"])),
                    width="stretch", key="fig_topics")
    # R2/L30: the seed's catch-all SHARE moved off the retired coverage line
    # into this caption, which already counted the flagged rows from the data
    # a caveat is read where the rows it qualifies are on screen. -8 keeps
    # THAT as the panel's one visible line (it qualifies every number in the
    # figure) and moves the depth-of-cut line into its `?`.
    st.caption(copy.FIND["CAPTION_TOPICS_CATCHALL"].format(
        n=f"{int(top['is_excluded'].fillna(False).sum()):,}", glyph=charts.EXCLUDED_GLYPH,
        catchall=_pct(card["catchall_811_share"])),
        help=copy.FIND["CAPTION_TOP_N_SHARE"].format(n=f"{len(top):,}"))


def _frontier_modes() -> tuple[str, str]:
    """The two L33 mode labels, built once so the control, the default and the
    comparison below all read the same strings.

     (FB handoff): the volume mode's label no longer bakes in a fixed
    N -- the panel's own top-N slider (below) states it instead, and the same
    slider now governs BOTH modes."""
    return (copy.FIND["FRONTIER_MODE_TOP"], copy.FIND["FRONTIER_MODE_EMERGING"])


def _panel_frontier(iid: str, ctl: dict, card: dict) -> None:
    """VIZ_SPEC S2.18 / R2 L33, rewired by the FB handoff
    (`progress/2BR_FB.md`): Expansion x Acceleration, bubble area = volume on
    the current basis, colour = domain, an INK outline on a top-quartile
    topic. TWO modes behind one segmented control -- the seed's topics by
    volume, or every topic in the global top quartile of emergence (NOT a
    subset of the first: a topic can be small and highly emergent, or large
    and static) -- ONE top-N slider shared by both, handed to
    `charts.fig_frontier` as `top_n` so the chart does the mass-based cut
    itself (`charts._frontier_topn`) instead of a hand-rolled rank mask.

    Catch-all topics are no longer pre-excluded before this cut (FB handoff:
    "catch-all must enter the top_n count") -- `fig_frontier` already mutes
    and hover-flags them exactly like `fig_topics` does, so they are shown and
    counted like any other topic, never invisibly dropped ahead of the
    selection the caption describes. Placeability (both axes scored) is left
    for `fig_frontier`/`charts.frontier_coverage` to determine THEMSELVES,
    internally, off whichever base this function hands them -- `df` itself for
    the volume mode (so `n_excluded` states how many of the SEED's topics
    carry no frontier score at all), the top-quartile subset for the emerging
    mode (so `n_excluded` states how many of THOSE carry none) -- rather than
    this function pre-filtering to placeable rows itself, which would make
    every base 100% placeable by construction and the caption vacuous.
    `charts.frontier_coverage` runs the IDENTICAL selection on the SAME frame
    handed to `fig_frontier`, so the chart and the caption's numbers can never
    drift apart."""
    df = _topics_frame(iid, ctl["tree"], ctl["basis"])
    if df.empty:
        st.caption(copy.FIND["PANEL_EMPTY"])
        return
    mode_top, mode_emerging = _frontier_modes()
    st.segmented_control(copy.FIND["FRONTIER_MODE_LABEL"], [mode_top, mode_emerging],
                         default=mode_top, required=True, key="frontier_mode", **state.PERSIST)
    pick = st.session_state.get("frontier_mode") or mode_top
    base = df[df["top25pct_frontier"].fillna(False)] if pick == mode_emerging else df

    top_n = st.slider(copy.FIND["FRONTIER_TOPN_LABEL"], FRONTIER_TOPN_MIN, FRONTIER_TOPN_MAX,
                      FRONTIER_TOP_N, step=FRONTIER_TOPN_STEP, key=f"frontier_topn_{pick}",
                      **state.PERSIST)
    vol_col = _vol_col(ctl["basis"])
    cov = charts.frontier_coverage(base, size_col=vol_col, top_n=top_n)
    if cov["n_shown"] == 0:
        st.caption(copy.FIND["FRONTIER_EMPTY"])
    else:
        st.plotly_chart(charts.fig_frontier(base, size_col=vol_col, top_n=top_n),
                        width="stretch", key="fig_frontier")
    n_not_placeable = int(len(base) - cov["n_placeable"])
    min_mass = NA_MARK if cov["min_mass_shown"] is None else f"{cov['min_mass_shown']:,.0f}"
    # -8: what is plotted stays visible; how much mass the cut leaves out
    # and how catch-all topics are treated move into the same line's `?`.
    st.caption(copy.FIND["CAPTION_FRONTIER"].format(
        n_shown=f"{cov['n_shown']:,}", n_excluded=f"{n_not_placeable:,}"),
        help=copy.FIND["CAPTION_FRONTIER_COVERAGE"].format(
            n_catchall=f"{cov['n_catchall_shown']:,}", glyph=charts.EXCLUDED_GLYPH,
            pct_not_shown=_pct(cov["pct_mass_not_shown"]), min_mass=min_mass))


def _panel_sdg(iid: str, ctl: dict, card: dict) -> None:
    """VIZ_SPEC S2.19: sixteen bars in FIXED goal order (the one panel with no
    sort toggle -- the SDG numbers are a canonical sequence a reader navigates
    by position), official UN colours, ESI in the SI slot."""
    df = _sdg_frame(iid)
    if df.empty:
        st.caption(copy.FIND["PANEL_EMPTY"])
        return
    st.plotly_chart(charts.fig_sdg(df), width="stretch", key="fig_sdg")
    st.caption(copy.FIND["CAPTION_SDG"].format(
        n_missing=", ".join(str(n) for n in P.SDG_UNCOVERED)))
    # D5: this ratio surface states its OWN
    # basis -- `sdg.parquet` is denominated on the whole-run, six-year window,
    # not the five-year corpus window this page states everywhere else
    # (window_conventions.sdg_mass_window, docs/data_contract.yaml). Disclosure
    # only: the basis is unchanged, deliberately different from Compare's own
    # SDG basis, and stays that way. The fractional-only disclosure moves from
    # a silent `?` to its own visible warning line -- a page-level
    # setting silently not applying here is exactly the fact a reader needs to
    # SEE, not discover by hovering.
    _basis_caption(copy.FIND["RATIO_WHOLE_RUN_BASIS"].format(
        window=SDG_ERC_WINDOW_LABEL, corpus=CORPUS_WINDOW_LABEL))
    if ctl["basis"] == "full":
        _basis_caption(copy.FIND["FRACTIONAL_ONLY_PANEL"], warning=True)


# The five panels of VIZ_SPEC S1.9 block 5, in their fixed order. The key is
# BOTH the expander's session-state key and the widget key suffix.
#
# The ERC panel is GONE ( "Out of scope: ERC panels
# anywhere" -- `lib/charts.py:fig_erc`, C2's file, is retired along with
# it; the L4/L5 ERC-based ranking LENSES in the Benchmark section below are
# untouched, a different feature the scope note does not name).
#
# A panel whose TITLE states its own cut takes its arguments from here rather
# than typing the number into copy.py (L10): R2/L34's "Top {n} subfields" is the
# only such title today.
PANEL_LABEL_ARGS = {"subfields": {"n": SUBFIELDS_TOP_N}}

PANELS = (
    ("fields", "PANEL_FIELDS", _panel_fields),
    ("subfields", "PANEL_SUBFIELDS", _panel_subfields),
    ("topics", "PANEL_TOPICS", _panel_topics),
    ("frontier", "PANEL_FRONTIER", _panel_frontier),
    ("sdg", "PANEL_SDG", _panel_sdg),
)


def _profile_panels(iid: str, ctl: dict, card: dict) -> None:
    """The six panels are COLLAPSED by default (VIZ_SPEC S1.9) but their bodies
    run every rerun -- `st.expander` folds the display, never the execution.

    A lazy gate was built and REJECTED on a measurement (progress/R1_E2.md,
    verify-before-building item b): Streamlit 1.61.1's `st.expander` does take
    a `key=` and does publish its open/closed state into `st.session_state`,
    but that state RESETS to the coded `expanded=` on the very next rerun, so
    a body gated on it would blank itself the moment the reader touched any
    other control. Rendering all six unconditionally costs a measured 0.88 s
    warm on the largest seed tested, inside the 1.5 s budget, so the panels are
    always built and the `key=` is kept only as a stable DOM hook
    (`.st-key-panel_<name>`) for the probe."""
    for name, copy_key, body in PANELS:
        label = copy.FIND[copy_key].format(**PANEL_LABEL_ARGS.get(name, {}))
        with st.expander(label, expanded=False, key=f"panel_{name}"):
            body(iid, ctl, card)


def _render_profile(bundle: dict, subs: dict, seed_id: str, ctl: dict) -> dict:
    """VIZ_SPEC S1.9 / -6 -- the profile as a 2 + 2 split. Row 1 in two
    halves (the SIX KPI cards as a 2 x 3 grid | identity with the wordcloud
    UNDER it), row 2 full width (a titled section holding one control, one chip
    legend and the height-matched breakdown pair), then the five collapsed
    panels. Returns the seed card, which the L2f tab intro and the export path
    both read after the profile has rendered."""
    ctx = bundle["ctx"]
    card = seed_card(ctx, seed_id, subs, bundle["catchall"])
    row = ctx["index_by_id"].loc[seed_id]
    st.header(copy.FIND["PROFILE_HEADER"])
    with st.container(border=True, key="profile"):
        c_cards, c_identity = st.columns(PROFILE_ROW1_WIDTHS)
        with c_cards:
            _profile_cards(card, row, bundle)
        with c_identity:
            _profile_identity(card, row, bundle)
            _profile_wordcloud(seed_id, ctl)
        _profile_breakdown(seed_id, ctl, bundle)
        _profile_panels(seed_id, ctl, card)
    return card


# --------------------------------------------------------- controls row -----

def _same_country_share(rankings: dict, ctx: dict, seed_row, depth: int) -> str:
    """The live figure copy.L3_COUNTRY_TOOLTIP asks for: the share of L3's own
    visible candidates sitting in the seed's country. NA_MARK when L3 is
    undefined -- never a typed number, never 0."""
    r = rankings.get("L3")
    if r is None or r["undefined"] or not r["sorted_ids"]:
        return NA_MARK
    ids, _ = cut_with_ties(r["sorted_ids"], r["sorted_scores"], depth)
    own = str(seed_row["country_code"])
    same = sum(1 for i in ids if str(ctx["index_by_id"].loc[i, "country_code"]) == own)
    return f"{same / len(ids):.0%}"


def _post_filters(bundle: dict, rankings: dict, seed_row, depth: int) -> dict:
    """L16/L6: every post-filter opt-in and off by default, moved out of the
    sidebar into the controls row's expander with its widget KEYS unchanged.
    Rendered after the rankings exist so the same-country tooltip carries a
    computed share. Returns exactly `filters.apply_filters`' keyword set."""
    idx = bundle["index_df"]
    st.caption(copy.FIND["FILTERS_HELP"])
    types = st.multiselect(copy.FIND["TYPE_LABEL"], sorted(idx["type"].astype(str).unique()),
                           default=[], key="f_types", **state.PERSIST)
    # Options stay the CODES (the value `apply_filters` matches on), displayed
    # and ordered by their English name -- R1/L22.
    codes = sorted(idx["country_code"].astype(str).unique(), key=countries.name)
    picked = st.multiselect(copy.FIND["COUNTRY_LABEL"], codes, default=[],
                            format_func=countries.name, key="f_countries", **state.PERSIST)
    excl = st.checkbox(copy.FIND["EXCLUDE_OWN_LABEL"], value=False,
                       help=copy.L3_COUNTRY_TOOLTIP.format(
                           share=_same_country_share(rankings, bundle["ctx"], seed_row, depth)),
                       key="f_excl_own", **state.PERSIST)
    lo_all = int(np.floor(idx["total_full_2020_2024"].min()))
    hi_all = int(np.ceil(idx["total_full_2020_2024"].max()))
    lo, hi = st.slider(copy.FIND["SIZE_LABEL"], lo_all, hi_all, (lo_all, hi_all),
                       key="f_size", **state.PERSIST)
    guard = st.checkbox(copy.FIND["SCALE_GUARD_LABEL"], value=False,
                        help=copy.FIND["SCALE_GUARD_HELP"], key="f_guard", **state.PERSIST)
    thr = CFG["family_filter_threshold"]
    fam = st.checkbox(copy.FIND["FAMILY_LABEL"], value=False,
                      help=copy.FIND["FAMILY_HELP"].format(threshold=thr),
                      key="f_family", **state.PERSIST)
    narrowed = (lo, hi) != (lo_all, hi_all)
    return {"types": types or None, "countries": picked or None, "exclude_own_country": excl,
            "size_range": (lo, hi) if narrowed else None, "scale_guard": guard,
            "family_min": thr if fam else None}


def _controls_row(bundle: dict, rankings: dict, seed_row) -> tuple[dict, dict]:
    """L16 / VIZ_SPEC S2.21: the head of the Benchmark section. C1 and L7 are
    ORDINARY controls a reader touches on a first visit, so they sit in the
    open; the six post-filters are the advanced ones and live one click down,
    in a collapsed expander whose body still EXECUTES every rerun (its
    widgets must register). Each control carries a `help=` that explains what
    the option DOES. D17: depth is no longer a control here at all -- the
    benchmark always cuts at `BENCHMARK_DEPTH`."""
    st.header(copy.FIND["BENCHMARK_HEADER"])
    st.caption(copy.FIND["BENCHMARK_INTRO"])
    c_c1, c_l7, c_filters = st.columns(CONTROLS_ROW_WIDTHS)
    with c_c1:
        c1_on = st.checkbox(copy.C1_TOGGLE_LABEL, value=False,
                            help=copy.FIND["C1_HELP"].format(core_top_n=CORE_TOP_N),
                            key="c1_on", **state.PERSIST)
    with c_l7:
        l7_on = st.checkbox(copy.L7_TOGGLE_LABEL, value=False, help=copy.FIND["L7_HELP"],
                            key="l7_on", **state.PERSIST)
    with c_filters:
        with st.expander(copy.FIND["POSTFILTERS_EXPANDER"], expanded=False, key="postfilters"):
            filters = _post_filters(bundle, rankings, seed_row, BENCHMARK_DEPTH)
    return {"depth": BENCHMARK_DEPTH, "c1_on": c1_on, "l7_on": l7_on}, filters


# --------------------------------------------------- rows, filters, rank ----

def _rows_for_ids(ranking: dict, ctx: dict, ids: list, scores, rankings: dict | None,
                  subs: dict | None = None) -> list[dict]:
    """`engine.build_rows` over an explicit id subset, with the ORIGINAL
    competition rank restored from the unfiltered ranking's `rmap` (post-filters
    remove rows, they never renumber -- /VIZ_SPEC S1.7).
    `subs` is forwarded so every row's `shape_top3_fields` follows the active
    tree x basis (R1 bug #5)."""
    if not ids:
        return []
    sub = dict(ranking)
    sub["sorted_ids"] = list(ids)
    sub["sorted_scores"] = np.asarray(scores)
    rows = build_rows(sub, ctx, len(ids), rankings, subs)
    for r in rows:
        r["rank"] = ranking["rmap"][r["institution_id"]]
    return rows


def _with_evidence(rows: list[dict], ctx: dict, subs: dict, lens: str, seed_id: str) -> list[dict]:
    """L21: the lens-specific evidence cell -- the top shared cell for THAT
    lens, labelled in that lens's own namespace -- attached to the rows the
    table is about to render. Computed for the VISIBLE ids only, never over the
    whole population (S9.4 contract); `ranked.format_rows` and
    `exports.ranking_csv` both read `row["evidence_text"]`."""
    if not rows:
        return rows
    texts = rows_evidence(ctx, subs, lens, seed_id, [r["institution_id"] for r in rows])
    for r in rows:
        r["evidence_text"] = texts.get(r["institution_id"])
    return rows


def _cross_lens(rankings: dict) -> dict | None:
    """`build_rows`' optional L1/L3 cross-reference, only when both are defined
    (an undefined ranking carries `scores=None`, which that path would crash on)."""
    ok = all(ln in rankings and not rankings[ln]["undefined"] for ln in ("L1", "L3"))
    if ok:
        return rankings
    return None


def _filtered(ranking: dict, bundle: dict, filters: dict, seed_row, family_scores):
    """Post-filters on the FULL ranking, evaluated over the lightweight row
    dicts (`lite`) so nothing pays `build_rows` for rows nobody will see."""
    lite = bundle["lite"]
    rows = [lite[i] for i in ranking["sorted_ids"] if i in lite]
    kept = apply_filters(rows, seed_row=seed_row, family_scores=family_scores, **filters)
    kept_ids = [r["institution_id"] for r in kept]
    by_id = dict(zip(ranking["sorted_ids"], ranking["sorted_scores"]))
    return kept_ids, [by_id[i] for i in kept_ids]


def _family_scores(bundle: dict, subs: dict, seed_id: str, filters: dict) -> dict | None:
    """L0 field-grain scores, computed only when the opt-in family filter asks."""
    if filters["family_min"] is None:
        return None
    ctx = bundle["ctx"]
    return dict(zip(ctx["inst_ids"], family_overlap_scores(ctx, subs, seed_id)))


# ------------------------------------------------------------- lens tab -----

def _gloss_values(bundle: dict) -> dict:
    """Every placeholder copy.LENS_GLOSS/LENS_CAVEAT can ask for, filled from
    CFG, the engine's own constants and the live data -- never typed."""
    return {"n_fields": bundle["n_fields"], "n_named_lenses": len(ALL_LENSES),
            "n_default_lenses": len(CFG["lenses"]["default"]),
            "floor_papers": CFG["l2f_floor"]["value"], "core_top_n": CORE_TOP_N,
            "depth_max": CFG["depth"]["max"]}


def _lens_intro(lens: str, ranking: dict, subs: dict, basis: str, bundle: dict,
                card: dict) -> None:
    """Gloss (visible) + caveat (its `?`) + this seed's evidence line(s) + the
    basis disclosure, above the table. R2/L30 adds the L2f-eligible cell count
    here, on the L2f tab and nowhere else: it is a precondition for THAT
    lens's ranking, so a reader meets it on the tab whose list it explains
    rather than in the profile's retired coverage line.

    A11: the tab itself now carries only the bare display code, so
    the FULL lens name is the first line rendered INSIDE the tab -- this
    function's own opening line, `copy.LENS_DISPLAY_NAMES[lens]` (the renumbered
    code + the same name `copy.LENS_NAMES` always carried).

    D10 fix: the gloss used to stay bold-visible with the CAVEAT stacked
    under it as a second, always-visible `st.caption` line and no `?` at
    all -- the one place on this page with no fold, right after six profile
    panels two scrolls up that all DO fold their own methodology behind a
    `?` (VIZ_SPEC S2.4's "never tooltip-only" instruction pre-dates that fold
    pattern's own existence, CHROME_CONTRACT.md S6). The caveat is
    methodology (how to read the lens), not a fact about this seed's data, so
    it now travels in the gloss line's own `help=` -- the SAME
    `st.markdown(text, help=tooltip)` idiom this file already uses for the
    identity name (`_profile_identity`) and every profile-panel caption,
    rather than a new cross-file dependency on `charts_compare.chart_note`.
    The seed-specific evidence lines below (L2f eligibility, ERC/SDG/frontier/
    catch-all share, the generic evidence line) stay visible exactly as
    before -- they are what this lens SAYS about the seed, -8's other
    half, which the fold pattern keeps on screen everywhere else too.

    PRESS-A F12/F14 fix: the gloss+caveat pair above was ALREADY hidden behind Streamlit's
    native `help=` (the D10 fix), but that is a different visual component
    from the `?`-glyph reading-line convention every OTHER chart/section on
    this page and on Compare uses (CHROME_CONTRACT.md S6) -- a bold,
    always-visible headline is not the same affordance as a small ink
    reading line with its own tooltip circle. This now goes through the
    SAME `charts_compare.chart_note` primitive Compare's own `_note` calls,
    so the one place on this page that had not adopted the shared fold
    pattern now reads identically to every other one. No new prose: the
    reading text and the tooltip are still exactly `LENS_GLOSS`/
    `LENS_CAVEAT`, unchanged."""
    st.markdown(f"**{copy.LENS_DISPLAY_NAMES[lens]}**")
    vals = _gloss_values(bundle)
    st.markdown(chart_note(copy.LENS_GLOSS[lens].format(**vals),
                           copy.LENS_CAVEAT[lens].format(**vals)),
                unsafe_allow_html=True)
    if lens == "L2f":
        st.caption(copy.FIND["EV_L2F"].format(
            value=f"{card['n_eligible_subfields_L2f']:,}"))
    # Manager fix 2026-08-29 (inspection R2, I-2): the per-lens coverage lines the
    # spec asks for (L8) -- ERC-classified share on the ERC lenses, SDG-tagged
    # share on the SDG lenses, frontier share on F1, catch-all share on L3 -- were
    # authored in copy.py (EV_ERC/EV_SDG/EV_FRONTIER/EV_CATCHALL) but never wired
    # once R2 retired the profile coverage line. Each is a statement about the
    # SEED's data, never a gate.
    shown_specific = False
    if lens in ("L4", "L5"):
        erc, tot = card.get("erc_classified_mass_frac"), bundle["ctx"]["index_by_id"].loc[card["institution_id"], "total_frac"]
        if erc is None or pd.isna(tot) or float(tot) <= 0:
            erc_txt = NA_MARK
        else:
            erc_txt = _pct(erc / float(tot))
        st.caption(copy.FIND["EV_ERC"].format(value=erc_txt))
        shown_specific = True
    elif lens in ("L6", "L7"):
        st.caption(copy.FIND["EV_SDG"].format(value=_pct(card.get("sdg_tagged_share"))))
        shown_specific = True
    elif lens == "F1":
        st.caption(copy.FIND["EV_FRONTIER"].format(value=_pct(card.get("frontier_top25_share_index"))))
        shown_specific = True
    elif lens == "L3":
        st.caption(copy.FIND["EV_CATCHALL"].format(value=_pct(card.get("catchall_811_share"))))
        shown_specific = True
    ev = {k: v for k, v in (ranking.get("evidence") or {}).items() if isinstance(v, (int, float))}
    if ev:
        text = "; ".join(f"{k.replace('_', ' ')}: {v:,.3f}" for k, v in ev.items())
        st.caption(copy.FIND["EVIDENCE_LABEL"].format(text=text, sep=SEP))
    elif not shown_specific and lens != "L2f":
        st.caption(copy.FIND["EV_NONE"])
    if basis == "full" and not subs["basis_applies"][lens]:
        # D5: a page-level setting the reader just touched silently
        # not applying to THIS tab is exactly the kind of fact a warning
        # colour exists for -- kept VISIBLE (never folded into a `?` nobody
        # hovers) but recoloured, never bold, no icon box.
        _basis_caption(copy.FIND["BASIS_DISCLOSURE"], warning=True)


def _tail_search(lens: str, ranking: dict, bundle: dict, subs: dict, kept,
                 ctx_bits: dict) -> None:
    """VIZ_SPEC S2.7: search scoped to the FULL filtered ranking.

    E7: this used to also carry the
    per-lens CSV download (`_csv` + `st.download_button`) right below the
    tail search; that button is GONE -- every lens now downloads together in
    the ONE end-of-page workbook (`_find_exports`), per WT_2D claim 6's
    own measured, cheap "compute every lens at export time" approach. The
    function keeps its old name minus "_export" (nothing here builds an
    export any more)."""
    kept_ids, kept_scores = kept
    ctx, norm = bundle["ctx"], bundle["norm_names"]
    seed_id = ranking["seed_id"]
    query = st.text_input(copy.FIND["TAIL_SEARCH_LABEL"], key=f"tail_{lens}", **state.PERSIST)
    if query:
        q = normalize(query)
        hits = [(i, s) for i, s in zip(kept_ids, kept_scores) if q in norm.get(i, "")]
        if not hits:
            st.caption(copy.TAIL_SEARCH_EMPTY_TEMPLATE.format(query=query))
        else:
            rows = _rows_for_ids(ranking, ctx, [h[0] for h in hits], [h[1] for h in hits],
                                 ctx_bits["cross"], subs)
            _with_evidence(rows, ctx, subs, lens, seed_id)
            st.caption(copy.FIND["TAIL_CAPTION"])
            render_ranked_table(format_rows(rows, lens=lens, depth=len(rows)),
                                key=f"tailtbl_{lens}")


def _render_lens_tab(lens: str, ranking: dict, bundle: dict, subs: dict, filters: dict,
                     seed_row, ctx_bits: dict) -> None:
    """VIZ_SPEC S2.4 / S2.22, the one shared form every lens renders through."""
    _lens_intro(lens, ranking, subs, ctx_bits["basis"], bundle, ctx_bits["card"])
    if ranking["undefined"]:
        # R2/L29: the engine's own `reason` is a debugging string (it names
        # internal structures and types digits this app bans in copy), so the
        # reader gets the lens's plain-language precondition instead. The
        # engine's version stays in its own log, unchanged.
        st.info(copy.UNDEFINED_LENS_TEMPLATE.format(
            lens=copy.LENS_DISPLAY_NAMES[lens], reason=copy.LENS_UNDEFINED_REASON[lens]))
        return
    ctx, depth = bundle["ctx"], ctx_bits["depth"]
    kept_ids, kept_scores = _filtered(ranking, bundle, filters, seed_row, ctx_bits["family"])
    if not kept_ids:
        st.info(explain_empty(filters, seed_row))
        return
    vis_ids, vis_scores = cut_with_ties(kept_ids, np.asarray(kept_scores), depth)
    rows = _rows_for_ids(ranking, ctx, vis_ids, vis_scores, ctx_bits["cross"], subs)
    _with_evidence(rows, ctx, subs, lens, ranking["seed_id"])
    render_ranked_table(format_rows(rows, lens=lens, depth=depth), key=f"tbl_{lens}")
    # U4 / PRESS-A: the old `ranked.depth_caption`
    # pointed at the per-lens CSV button E7 just removed (".or download the
    # full ranking"); this page now renders its OWN depth line, built from
    # `copy.DEPTH_CAPTION_TEMPLATE` (E10's exact rewritten string), which
    # points at the one end-of-page workbook instead. `ranked.depth_caption`
    # is unchanged and still exercised by its own tests -- it is simply no
    # longer this page's caller (flagged for a future dead-code sweep, out
    # of this stream's fence).
    st.caption(copy.DEPTH_CAPTION_TEMPLATE.format(n=f"{len(rows):,}", m=f"{len(kept_ids):,}"))
    st.caption(copy.FIND["POP_CAPTION"].format(n_pop=f"{len(ranking['sorted_ids']):,}"))
    _tail_search(lens, ranking, bundle, subs, (kept_ids, kept_scores), ctx_bits)


# ------------------------------------------------------------- overview -----

def _render_overview(bundle: dict, rankings: dict, lenses: list, filters: dict, seed_row) -> None:
    """VIZ_SPEC S2.3: k of n over the UNFILTERED rankings; post-filters remove
    rows and never recompute k."""
    st.caption(copy.FIND["OVERVIEW_INTRO"])
    rows = concordance(bundle["ctx"], rankings, lenses, CONCORDANCE_N)
    if not rows:
        st.info(copy.FIND["CONCORDANCE_EMPTY"])
        return
    n_defined = rows[0]["n"]
    kept = apply_filters(rows, seed_row=seed_row, family_scores=None, **filters)
    if not kept:
        st.info(explain_empty(filters, seed_row))
        return
    render_concordance_table(
        format_concordance(kept, lenses=lenses, N=CONCORDANCE_N), key="tbl_concordance")
    st.caption(concordance_caption(n_defined, CONCORDANCE_N, len(kept)))
    # R2/L29: the chips are lens CODES, which are stable identifiers rather than
    # self-explaining names -- so the table says what a chip means and points at
    # the guide that names every lens in full.
    st.caption(copy.FIND["LENS_LEGEND_CAPTION"].format(N=CONCORDANCE_N))


# ---------------------------------------------------------- aspirational ----

def _aspirational_frame(rows: list[dict], *, score_key: str = "lens_score_L1_overlap",
                        score_label_key: str = "COL_L1") -> pd.DataFrame:
    """VIZ_SPEC S2.5 + R1/L22, revised by: the interval column is GONE
    (the point estimate is what a reader compares row to row here; the full
    interval already sits in the profile's own PP card, VIZ_SPEC S9.6's rule
    lives there now), both size bases, country by NAME, no badge column, and
    the institution NAME is the OpenAlex-works link (A10, same
    `works_link_named` mechanism `lib/ranked.py`'s tables use).

    `score_key`/`score_label_key` let this ONE frame serve both aspirational
    modes: V0's L1-overlap score (default) or the A-frontier fallback's F1
    score."""
    out = []
    for r in rows:
        iid = r["institution_id"]
        out.append({
            "rank": r["rank"], "institution": works_link_named(iid, str(r["display_name"])),
            "institution_name": r["display_name"],
            "country": countries.name(str(r["country_code"])), "type": str(r["type"]),
            "size_full": _count(r.get("total_full_2020_2024")),
            "size_frac": _count(r.get("total_frac_2020_2024")),
            "pp": _pct(r.get("pp_top10_frac")),
            # D9 (locale fix, CHROME-F recipe in progress/2C_CHROME-F.md
            # S1): pre-scaled 0-100, the SAME transform `lib/ranked.py:format_rows`
            # applies to its own `score` column -- `_render_aspirational_table`'s
            # ProgressColumn reads this already-scaled value.
            "score": _pct100(r[score_key]), "institution_id": iid})
    df = pd.DataFrame(out)
    df.attrs["score_label_key"] = score_label_key
    return df


def _render_aspirational_table(df: pd.DataFrame) -> list:
    """Own column set (not the shared lens form).: no "Interval"
    column (either aspirational mode); the institution name is the works
    link, gated by the SAME `NAME_LINK_MODE` `lib/ranked.py` uses so a single
    fallback decision covers every table on this page."""
    score_label = copy.FIND[df.attrs.get("score_label_key", "COL_L1")]
    if NAME_LINK_MODE == "fragment":
        order = ["rank", "institution", "country", "type", "size_full", "size_frac", "pp", "score"]
        institution_cfg = st.column_config.LinkColumn(copy.FIND["COL_INSTITUTION"],
                                                       display_text=r"#(.*)$")
    else:
        order = ["rank", "institution_name", "country", "type", "size_full", "size_frac",
                 "pp", "score", "institution"]
        institution_cfg = st.column_config.LinkColumn(WORKS_LINK_FALLBACK_LABEL,
                                                       display_text=WORKS_LINK_FALLBACK_LABEL)
    event = st.dataframe(
        df, hide_index=True, width="stretch", on_select="rerun",
        selection_mode="multi-row", key="tbl_aspirational",
        column_order=order,
        column_config={
            "rank": st.column_config.NumberColumn(copy.FIND["COL_RANK"]),
            "institution": institution_cfg,
            "institution_name": st.column_config.TextColumn(copy.FIND["COL_INSTITUTION"]),
            "institution_id": None,
            "country": st.column_config.TextColumn(copy.FIND["COL_COUNTRY"]),
            "type": st.column_config.TextColumn(copy.FIND["COL_TYPE"]),
            "size_full": st.column_config.TextColumn(copy.FIND["COL_SIZE_FULL"]),
            "size_frac": st.column_config.TextColumn(copy.FIND["COL_SIZE_FRAC"]),
            "pp": st.column_config.TextColumn(copy.FIND["COL_PP"]),
            # D9 fix: was the banned locale-sensitive ProgressColumn
            # `format=` keyword (see CHROME_CONTRACT.md S9), which renders
            # through the HOST BROWSER LOCALE
            # confirmed comma-decimal live (progress/2C_CHROME-F.md S1). The
            # shared `ranked.pct_progress_column` builder is printf-style
            # ("%.1f%%"), period-decimal regardless of locale; its column
            # expects the value pre-scaled 0-100, which `_aspirational_frame`
            # now does via `ranked._pct100` (the SAME transform
            # `lib/ranked.py:format_rows` applies to the lens tables' own
            # Score column, so both tables of this page share one convention).
            "score": pct_progress_column(score_label)})
    rows_sel = event.selection.rows if event and event.selection else []
    return [df.iloc[i]["institution_id"] for i in rows_sel]


def _render_aspirational(bundle: dict, rankings: dict, filters: dict, seed_row,
                         ctx_bits: dict) -> None:
    """VIZ_SPEC S2.5, kept in L1-overlap order unless the analyst asks for a PP
    sort -- which is a control, never the default.

     mode B: when V0 (`aspirational`) returns NO row for this seed
    a seed near the impact ceiling of its own look-alike pool, ETH Zurich in
    the R2 campaign (`evals/aspirational_R2/REPORT.md` S2/S3.1) -- the same
    L1 pool is shown instead, reordered by frontier alignment
    (`engine.aspirational_frontier`, ported from that REPORT's A-frontier
    definition), labelled explicitly so a reader never mistakes it for V0's
    impact-qualified list. The PP sort toggle stays V0-only: the fallback is
    already sorted by the ONE score it exists to show."""
    st.caption(copy.FIND["ASP_FRAME_INTRO"])
    st.caption(copy.FIND["ASP_INTRO"])
    l1 = rankings.get("L1")
    if l1 is None or l1["undefined"] or pd.isna(seed_row["pp_top10_frac"]) \
            or pd.isna(seed_row["pp_ci_high"]):
        st.info(copy.FIND["ASP_UNDEFINED"])
        return
    rows = aspirational(bundle["ctx"], l1)
    pool = len(cut_with_ties(l1["sorted_ids"], l1["sorted_scores"], CFG["depth"]["max"])[0])
    fallback = False
    if not rows:
        fallback_rows = aspirational_frontier(bundle["ctx"], l1, rankings.get("F1"))
        if fallback_rows:
            fallback = True
            rows = fallback_rows
    kept = apply_filters(rows, seed_row=seed_row, family_scores=None, **filters)
    if not kept:
        if rows:
            st.info(explain_empty(filters, seed_row))
        else:
            st.info(copy.FIND["ASP_EMPTY"].format(seed=seed_row["display_name"]))
        return
    if fallback:
        st.caption(copy.FIND["ASP_FRONTIER_FALLBACK"])
        frame = _aspirational_frame(kept, score_key="lens_score_F1_overlap",
                                    score_label_key="COL_F1")
    else:
        if st.checkbox(copy.FIND["ASP_SORT_LABEL"], value=False, key="asp_sort", **state.PERSIST):
            kept = sorted(kept, key=lambda r: -r["pp_top10_frac"])
        frame = _aspirational_frame(kept)
    _render_aspirational_table(frame)
    st.caption(copy.FIND["ASP_CAPTION"].format(n_rows=f"{len(kept):,}", n_pool=f"{pool:,}"))
    # E7: the per-tab CSV this used to end on
    # (`_aspirational_export`) is GONE -- the aspirational list is one more
    # sheet in the end-of-page workbook now (`_aspirational_sheet_frame`),
    # built at click time regardless of which tab is open.


# ---------------------------------------------------------------- render ----

def _lenses_shown(ctl: dict) -> list:
    """CFG's eight defaults in their ruled order, plus each optional lens whose
    own toggle is on."""
    shown = list(CFG["lenses"]["default"])
    if ctl["c1_on"]:
        shown.append("C1")
    if ctl["l7_on"]:
        shown.append("L7")
    return shown


def _lens_guide(lenses: list) -> None:
    """R2/L29: "How to read the lenses", a collapsed expander at the head of the
    Benchmark section. One plain sentence per SHOWN lens (the guide never
    describes a tab that is not on screen), each headed by the same DISPLAY
    label its tab now carries, so the code in the Overview chips, the evidence
    column and the CSV can stay a bare identifier without being unexplained.

    A11: the expander's own title renders in the house palette's alert/
    attention hue via Streamlit's `:red[.]` markdown-lite directive -- the
    ONE colour token a widget LABEL can carry on this pinned Streamlit build
    (verified against the installed package's own
    `.agents/skills/developing-with-streamlit/references/markdown.md`: eight
    named colours plus `primary`, no arbitrary hex, no `unsafe_allow_html` on
    `st.expander`). `lib/palette.py` is file this wave and ships
    no reusable "alert" token for a widget label; adding one would be a new
    hex under a different name, which the plan forbids as surely as a raw
    literal would be -- flagged in `progress/2BR_FC.md` for VS/G to reconcile
    against a true `palette.py` token when a future wave allows unsafe HTML
    here (e.g. rendering the title via `st.markdown` above a keyless
    container instead of the native expander label)."""
    with st.expander(f":red[{copy.FIND['LENS_INTRO_HEADER']}]", expanded=False, key="lens_guide"):
        st.caption(copy.FIND["LENS_INTRO_LEAD"])
        for lens in lenses:
            st.markdown(f"**{copy.LENS_DISPLAY_NAMES[lens]}** {DASH} {copy.LENS_INTRO[lens]}")


def _ctx_bits(ctl: dict, filters: dict, seed_id: str, rankings: dict, strip: str | None,
              family, card: dict) -> dict:
    """The per-render constants every tab needs, assembled once."""
    filtered = any(v not in (None, False, []) for v in filters.values())
    if strip:
        label = strip
    else:
        label = ""
    return {"tree": ctl["tree"], "basis": ctl["basis"], "depth": ctl["depth"],
            "snapshot": manifest().get("snapshot") or CFG["snapshot"], "seed_id": seed_id,
            "filters_label": label, "filtered": filtered, "family": family,
            "card": card, "cross": _cross_lens(rankings)}


# --------------------------------------------------------------- workbook ---
# E7: ONE workbook at the very end of
# the page replaces every per-lens/per-tab CSV this page used to offer. Built
# from ALL_LENSES (every lens the engine defines), never only the tabs this
# scenario happens to show -- WT_2D.md claim 6's own inventory measured this
# at ~0.95s/lens, ~8-12s total, which is exactly the shape the OLD per-lens
# CSV button already accepted: a lazy `data=` callable that only runs when
# someone actually clicks (nothing here runs on a bare rerun).

_LENS_SHEET_COLUMNS = ["rank", "institution_name", "institution_id", "country", "type",
                       "size_full", "size_frac", "score", "evidence"]
_CONCORDANCE_SHEET_COLUMNS = ["institution_name", "institution_id", "country", "type",
                             "k_of_n", "hit_lenses", "size_full", "size_frac"]
_ASPIRATIONAL_SHEET_COLUMNS = ["rank", "institution_name", "institution_id", "country", "type",
                               "size_full", "size_frac", "pp", "score"]


def _profile_numbers_frame(card: dict, row, bundle: dict) -> pd.DataFrame:
    """The eight KPI cards' own numbers (E7 + D9): metric name, formatted
    value, and the same small line the card itself carries -- an index
    position for the original five, the fractional-count note for the
    publications card, the pool/citation-window sentence for the two P5 KPIs.
    Nowhere else on the page offers these eight figures together as a table
    (WT_2D claim 6's own "profile numbers" sheet)."""
    out = []
    for kpi, label, value, fmt, _tip in _card_specs(card, row):
        if kpi == KPI_PUBS_KEY:
            sub = copy.FIND["KPI_PUBS_FRAC_NOTE"].format(n=_count(card["total_frac_2020_2024"]))
        else:
            sub = _baseline_sub(bundle, kpi, value, fmt)
        out.append({"metric": label, "value": fmt(value), "index_position": sub})
    stars_value, stars_sub, _ = _stars_kpi(row)
    out.append({"metric": KPI_STARS_LABEL, "value": stars_value, "index_position": stars_sub})
    led_value, led_sub, _ = _led_kpi(row)
    out.append({"metric": KPI_LED_LABEL, "value": led_value, "index_position": led_sub})
    return pd.DataFrame(out)


def _lens_sheet_frame(lens: str, ranking: dict, bundle: dict, subs: dict, filters: dict,
                      seed_row, bits: dict) -> pd.DataFrame:
    """One lens's full (filtered) ranking as a plain sheet -- the SAME rows
    the retired per-lens CSV carried, built here (at workbook-click time,
    E7) rather than at every tab's own click, so an unopened tab still costs
    nothing until the workbook itself is downloaded."""
    if ranking["undefined"]:
        return pd.DataFrame([{"note": copy.LENS_UNDEFINED_REASON[lens]}])
    ctx = bundle["ctx"]
    kept_ids, kept_scores = _filtered(ranking, bundle, filters, seed_row, bits["family"])
    if not kept_ids:
        return pd.DataFrame(columns=_LENS_SHEET_COLUMNS)
    rows = _rows_for_ids(ranking, ctx, kept_ids, kept_scores, bits["cross"], subs)
    _with_evidence(rows, ctx, subs, lens, ranking["seed_id"])
    df = format_rows(rows, lens=lens, depth=len(rows))
    return df[_LENS_SHEET_COLUMNS]


def _overview_sheet_frame(bundle: dict, rankings: dict, filters: dict, seed_row) -> pd.DataFrame:
    """The concordance ("k of n lenses") table over EVERY lens (`ALL_LENSES`),
    not only the tabs this scenario happens to show -- the workbook's own
    Overview sheet (E7)."""
    rows = concordance(bundle["ctx"], rankings, ALL_LENSES, CONCORDANCE_N)
    if not rows:
        return pd.DataFrame(columns=_CONCORDANCE_SHEET_COLUMNS)
    kept = apply_filters(rows, seed_row=seed_row, family_scores=None, **filters)
    if not kept:
        return pd.DataFrame(columns=_CONCORDANCE_SHEET_COLUMNS)
    df = format_concordance(kept, lenses=ALL_LENSES, N=CONCORDANCE_N)
    return df[_CONCORDANCE_SHEET_COLUMNS]


def _aspirational_sheet_frame(bundle: dict, rankings: dict, filters: dict, seed_row) -> pd.DataFrame:
    """The same V0 / frontier-fallback logic `_render_aspirational` renders,
    built into a plain sheet for the workbook (E7) -- kept in the DEFAULT
    L1-overlap order regardless of the on-screen sort checkbox, since this
    button is computed 'regardless of open tab' (WT_2D claim 6), not a copy
    of whatever one session happened to toggle."""
    l1 = rankings.get("L1")
    if l1 is None or l1["undefined"] or pd.isna(seed_row["pp_top10_frac"]) \
            or pd.isna(seed_row["pp_ci_high"]):
        return pd.DataFrame(columns=_ASPIRATIONAL_SHEET_COLUMNS)
    rows = aspirational(bundle["ctx"], l1)
    fallback = False
    if not rows:
        fallback_rows = aspirational_frontier(bundle["ctx"], l1, rankings.get("F1"))
        if fallback_rows:
            fallback = True
            rows = fallback_rows
    kept = apply_filters(rows, seed_row=seed_row, family_scores=None, **filters)
    if not kept:
        return pd.DataFrame(columns=_ASPIRATIONAL_SHEET_COLUMNS)
    if fallback:
        frame = _aspirational_frame(kept, score_key="lens_score_F1_overlap",
                                    score_label_key="COL_F1")
    else:
        frame = _aspirational_frame(kept)
    return frame[_ASPIRATIONAL_SHEET_COLUMNS]


_LEADERS_SHEET_TITLE = "Topics led & star papers"
_LEADERS_SHEET_COLUMNS = ["topic_id", "topic_name", "pool", "world_rank", "n_stars"]
_LEADERS_SHEET_NOT_AVAILABLE = pd.DataFrame([{"note": "not available in this build"}])


def _leaders_sheet_frame(seed_id: str) -> pd.DataFrame:
    """Sheet 14, "Topics led & star papers": every
    topic this institution leads (world top-10, either pool -- `topics_led.
    parquet` via `leaders_data.led_topics`, which already carries
    `topic_name`) merged with its star-paper count in that topic
    (`inst_stars.parquet` via `leaders_data.stars_by_topic`), sorted by rank
    then stars descending. `lib.leaders_data` is file, which may
    not exist yet when this stream runs -- guarded (import AND shape) so the
    workbook still builds either way: one explanatory row before P5 lands,
    the real merge once it has."""
    try:
        from lib import leaders_data

        ctx = SC.bundle()["ctx"]
        led = leaders_data.led_topics(ctx, seed_id)
        if led is None or len(led) == 0:
            return pd.DataFrame(columns=_LEADERS_SHEET_COLUMNS)
        stars = leaders_data.stars_by_topic(ctx, [seed_id])
        merged = led.rename(columns={"rank": "world_rank"})
        if stars is not None and len(stars):
            merged = merged.merge(stars[["topic_id", "n_stars"]], on="topic_id", how="left")
        else:
            merged["n_stars"] = 0
        merged["n_stars"] = merged["n_stars"].fillna(0).astype(int)
        merged = merged.sort_values(["world_rank", "n_stars"], ascending=[True, False])
        return merged.reindex(columns=_LEADERS_SHEET_COLUMNS).reset_index(drop=True)
    except Exception:
        # ImportError (P5 has not landed) or any shape mismatch against the
        # contract this was written against
        # either way the workbook still ships its 14th sheet, honestly labelled.
        return _LEADERS_SHEET_NOT_AVAILABLE


def _find_workbook(bundle: dict, subs: dict, ctl: dict, filters: dict, seed_row, card: dict,
                   rankings: dict, bits: dict, seed_id: str) -> bytes:
    """Every lens (`ALL_LENSES`) + the concordance overview + the aspirational
    list + the profile's own KPI numbers + the topics-led/star-papers sheet
    (D9), one sheet each, fourteen total, in that order (E7).
    `exports_xlsx.workbook_bytes` legalises and de-duplicates every sheet
    name on the way in, so a lens whose display name runs past Excel's
    31-character cap (e.g. L9's) is truncated there, not here."""
    sheets = [(copy.FIND["XLSX_SHEET_PROFILE"], _profile_numbers_frame(card, seed_row, bundle)),
              (copy.FIND["XLSX_SHEET_OVERVIEW"],
               _overview_sheet_frame(bundle, rankings, filters, seed_row))]
    for lens in ALL_LENSES:
        sheets.append((copy.LENS_DISPLAY_NAMES[lens],
                       _lens_sheet_frame(lens, rankings[lens], bundle, subs, filters, seed_row,
                                        bits)))
    sheets.append((copy.FIND["XLSX_SHEET_ASPIRATIONAL"],
                   _aspirational_sheet_frame(bundle, rankings, filters, seed_row)))
    sheets.append((_LEADERS_SHEET_TITLE, _leaders_sheet_frame(seed_id)))
    return workbook_bytes(sheets)


def _find_workbook_filename(seed_id: str, tree: str, basis: str) -> str:
    """"BenchUp_find_<institution>_<tree>_<basis>.xlsx" -- D15's plain
    "BenchUp" capitalisation, built locally."""
    return f"BenchUp_find_{seed_id}_{tree}_{basis}.xlsx"


def _find_exports(bundle: dict, subs: dict, seed_id: str, ctl: dict, filters: dict, seed_row,
                  card: dict, rankings: dict, bits: dict) -> None:
    """ONE download button (E7), replacing every per-lens/per-tab CSV this
    page used to offer. `data` is a zero-arg callable, so the whole all-lenses
    workbook is only ever built when someone actually clicks."""
    def _book() -> bytes:
        return _find_workbook(bundle, subs, ctl, filters, seed_row, card, rankings, bits, seed_id)

    st.download_button(copy.FIND["EXPORT_XLSX_BUTTON"], _book,
                       file_name=_find_workbook_filename(seed_id, ctl["tree"], ctl["basis"]),
                       mime=XLSX_MIME, help=copy.FIND["EXPORT_XLSX_HELP"],
                       key="dl_find_workbook")


def render() -> None:
    """The whole Find page, in the argument order VIZ_SPEC S1.3/S1.9/S2 fixes.

    Computation order: sidebar counting & taxonomy only -> compact header (title + promise)
    -> the free-text seed pick (`_seed_pick`) -> the resident scenario
    (`SC.get`) -> rank_all -> PROFILE (which returns the seed card the L2f
    tab intro reads) -> controls row (which needs the rankings for the
    same-country tooltip) -> the lens guide -> the strip, rendered back into
    the slot reserved under the title -> tabs -> the meta text at the foot of
    the page (`_footer_meta`), always rendered last, seed or no seed."""
    bundle = SC.bundle()
    qp_seed = st.query_params.get("seed")
    if qp_seed and "seed_id" not in st.session_state and qp_seed in bundle["ctx"]["id_pos"]:
        # ops/_probe_find.py + tests/ui/smoke.py jump straight to a profile
        # this way; `state.set_find_seed` is the same call `_seed_pick` makes
        # on a reader's own pick, so a Compare visit right after this one
        # pre-fills its first slot from a deep-linked seed too.
        st.session_state["seed_id"] = qp_seed
        state.set_find_seed(qp_seed)
    scenario = _sidebar_scenario()
    _header()
    strip_slot = st.empty()
    seed_id = _seed_pick(bundle)
    if not seed_id:
        _footer_meta(bundle)
        return
    subs = SC.get(scenario["tree"], scenario["basis"])
    ctx = bundle["ctx"]
    rankings = rank_all(ctx, subs, seed_id)
    seed_row = ctx["index_by_id"].loc[seed_id]
    card = _render_profile(bundle, subs, seed_id, scenario)
    benchmark, filters = _controls_row(bundle, rankings, seed_row)
    ctl = {**scenario, **benchmark}
    lenses = _lenses_shown(ctl)
    _lens_guide(lenses)
    strip = active_controls_strip(tree=_strip_tree(ctl["tree"]), basis=ctl["basis"],
                                  depth=ctl["depth"], c1_on=ctl["c1_on"], l7_on=ctl["l7_on"],
                                  filters=filters)
    if strip:
        with strip_slot.container(key="strip"):
            st.markdown(strip)
    bits = _ctx_bits(ctl, filters, seed_id, rankings, strip,
                     _family_scores(bundle, subs, seed_id, filters), card)
    # A11: the tab now carries ONLY the bare DISPLAY code (so all
    # twelve tabs -- Overview + L0.L9 + Aspirational, both optional lenses
    # on -- fit at 1280 px with no silent scroll); the full name moved inside
    # the tab body (`_lens_intro`'s own first line) and into the lens guide.
    tabs = st.tabs([copy.FIND["TAB_OVERVIEW"], *[copy.LENS_DISPLAY_CODE[ln] for ln in lenses],
                    copy.FIND["TAB_ASPIRATIONAL"]])
    with tabs[0]:
        _render_overview(bundle, rankings, lenses, filters, seed_row)
    for tab, lens in zip(tabs[1:-1], lenses):
        with tab:
            _render_lens_tab(lens, rankings[lens], bundle, subs, filters, seed_row, bits)
    with tabs[-1]:
        _render_aspirational(bundle, rankings, filters, seed_row, bits)
    _footer_meta(bundle, workbook_kwargs={
        "bundle": bundle, "subs": subs, "seed_id": seed_id, "ctl": ctl, "filters": filters,
        "seed_row": seed_row, "card": card, "rankings": rankings, "bits": bits})
