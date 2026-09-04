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
original plus the two star-papers/topics-led KPIs
adds | the identity block with the subfield wordcloud under it), row 2 full
width (a titled section, one segmented control and one chip legend above a
height-matched global + yearly breakdown pair whose bonus year is starred on
the axis), then five collapsed chart panels (Fields, Top subfields, Topics:
volume/impact/frontier, SDG profile, ERC profile) -> BENCHMARK section, headed by the
controls row (C1, L7, a post-filters expander -- the depth radio is retired:
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
`SC.get(tree, basis)`) -- switching scenario evicts the
previous one rather than accumulating a second, which is what keeps this app
under its RAM ceiling. `rank_all` is cheap and recomputed every rerun;
`build_rows` over a full ranking is not, so rows are built only for what is
actually shown -- the post-filtered depth cut, the tail-search matches, and
(lazily, through `st.download_button`'s callable `data`) the workbook.
`st.expander` bodies EXECUTE on every rerun even when collapsed -- only the
display folds -- so the six chart-panel frames are their own `@st.cache_data`,
keyed on the hashable (iid, tree, basis), fetching ctx/subs from the
scenario_cache internally (never passed as cache_data arguments).

STRINGS: every user-facing string lives in `lib/copy.py` under its own
digit-ban rule -- no digit outside a lens code / "top10"; every number is a
`{placeholder}` filled here from CFG or the live data
(`tests/test_narrative.py` enforces this over this file's `st.*` calls). The
two exceptions are `KPI_STARS_LABEL` /
`KPI_LED_LABEL` below -- module constants rather than `copy.py` entries
because `copy.py` is owned by other work in progress; moved in here instead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from lib import baselines, charts, charts_topics, copy, countries, links, profile_data, state, tiles
from lib import palette as P
from lib import topic_data as TopicData
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
# is a ported file and gives it no name. Read here ONCE so no
# rendered string ever types it.
CORE_TOP_N = 20

# The displayed cut of the "top N" subfields panel. A module constant,
# never a digit inside a caption: the caption takes it as an `{n}`
# placeholder. SUBFIELDS_TOP_N is 30 (the panel also lost its sort toggle:
# "top 30" is itself a volume-ordered concept, and a taxonomy re-sort of a
# volume-defined cut reads as an arbitrary 30 rows in ID order).
SUBFIELDS_TOP_N = 30

# The topic planes' shared "Topics shown" slider -- 10..100 step 10
# (`TopicData.N_MIN`/`N_MAX` own the clamp band this slider's own min/max
# mirror), default 50.
TOPIC_N_DEFAULT = 50
TOPIC_N_STEP = 10

SEP = "·"   # middle dot -- the separator copy.STRIP_JOIN already uses
DASH = "–"  # en dash -- interval rendering

WINDOW_START, WINDOW_END = CFG["window"]

# The 30/50 depth radio is retired -- the benchmark cut is always this
# constant (config.yaml pins depth.default == depth.max == 50, so this reads
# the same 50 `lib.engine.DEPTH` does). Every caption still names the cut.
BENCHMARK_DEPTH = CFG["depth"]["max"]

# The two window labels the SDG/ERC panel basis
# captions name, built from CFG so no digit is ever typed into a string
# -- CORPUS_WINDOW_LABEL is the five-year window this
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
# wordcloud under it fills the right (columns 3-4). This adds two
# more cards -- star papers, topics led -- to the original six, so the
# grid grows from 3 rows to 4; card width is unchanged (still half of half the
# content box).
N_CARDS = 8
CARD_GRID_COLS = 2                     # 4 rows x 2 cards (+star papers, +topics led)
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

# The two star-papers/topics-led KPI tiles. Labels moved to `copy.FIND`;
# both render MISSING_KPI_MARK, never NA_MARK (used everywhere
# else on this page), so "these columns are not on this deployed index
# yet" reads distinctly from "this institution has no value here".
MISSING_KPI_MARK = "—"
KPI_STARS_LABEL = copy.FIND["KPI_STARS_LABEL"]
KPI_LED_LABEL = copy.FIND["KPI_LED_LABEL"]
_STARS_SUBLINE = "world top 1% by citations, 2020–2024"
_STARS_HELP = ("A star paper is one of the world's top 1% most-cited articles or reviews "
              "in its topic and publication year, 2020-2024 (ties beyond the cut are not "
              "counted). The share is star papers over this institution's own article and "
              "review output in the same window.")
_LED_SUBLINE = "world top 20, all institutions"
_LED_HELP_TEMPLATE = "World top-20 publisher (all institutions) in {n} topics."

SORT_VOLUME, SORT_TAXONOMY = "volume", "taxonomy"


# ------------------------------------------------- profile frames (cached)
# One @st.cache_data per S9.4 profile table, keyed on the HASHABLE scenario
# identity (iid, tree, basis) and fetching ctx/subs from
# `lib.engine.scenario_cache` internally -- ctx and subs are unhashable, so
# they are never cache_data arguments. `st.expander` bodies execute on
# every rerun, so without these every collapsed panel would recompute its
# frame each time the user touched any control.

@st.cache_data(show_spinner=False, max_entries=24)
def _fields_frame(iid: str, tree: str, basis: str) -> pd.DataFrame:
    return profile_data.fields_table(SC.bundle()["ctx"], SC.get(tree, basis), iid)


@st.cache_data(show_spinner=False, max_entries=24)
def _subfields_frame(iid: str, tree: str, basis: str) -> pd.DataFrame:
    return profile_data.subfields_table(SC.bundle()["ctx"], SC.get(tree, basis), iid)


@st.cache_data(show_spinner=False, max_entries=24)
def _yearly_domain_frame(iid: str, tree: str) -> pd.DataFrame:
    """Basis-independent in its KEY: the frame carries both `vol_full` and
    `vol_frac`, and the caller picks the column the active basis names."""
    return profile_data.yearly_by_domain(SC.bundle()["ctx"], iid, tree)


@st.cache_data(show_spinner=False, max_entries=24)
def _yearly_doctype_frame(iid: str) -> pd.DataFrame:
    """The document-type table, sliced to one institution. Neither tree- nor
    basis-scoped: a document type has no taxonomy tree, and the table ships
    both bases. `doc_type` is a CATEGORY dtype in the
    parquet -- cast to str here, once, so no downstream `.map` ever meets a
    categorical (Assembly Line gotcha)."""
    df = doctype_by_year()
    out = df[df["institution_id"] == iid].copy()
    out["doc_type"] = out["doc_type"].astype(str)
    return out[["year", "doc_type", "vol_full", "vol_frac"]].reset_index(drop=True)


@st.cache_data(show_spinner=False, max_entries=24)
def _sdg_frame(iid: str, tree: str) -> pd.DataFrame:
    """`tree` gates the FWCI_EU/PP10_WD hover join (a tooltip-spec ruling: applied
    uniformly across all four profile panels) -- SDG's own share/mass/si
    columns are tree-independent and unaffected."""
    return profile_data.sdg_table(SC.bundle()["ctx"], iid, tree)


@st.cache_data(show_spinner=False, max_entries=24)
def _erc_frame(iid: str, tree: str) -> pd.DataFrame:
    """Same `tree` gate as `_sdg_frame`."""
    return profile_data.erc_table(SC.bundle()["ctx"], iid, tree)


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
    # The OPTION stays the internal value (every frame, every cache key
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
    the rest of the page removed. So the internal value goes in when it IS the
    default (the only case the test reads it) and the display label otherwise
    (the only case the text is rendered). Splitting that argument in two belongs
    in `lib/filters.py`, a file outside this module's fence."""
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
    """The meta text this page demotes to the FOOT of the page: the standing
    verdict line and the data stamp. Called once, at the very end
    of `render`, after every section.

    `workbook_kwargs`, when given (a profile is on
    screen), renders the ONE end-of-page download button right after the data
    caption -- the same "index size, then the one download" order Compare's
    own footer uses. `None` on the seed-less early return: there is nothing
    to export yet."""
    st.markdown("---")
    st.markdown(f"**{copy.VERDICT_LINE}**")
    mf = manifest()
    # The deploy step writes `source_manifest_generated_at` / `deployed_at`; the
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
    """A one-line basis or
    coverage disclosure -- a fact about the DATA, read where the ratio it
    qualifies is, never folded into a chart's own `?` (which states how to
    READ the chart, a different job). Normal state matches every other
    caption's small ink; switches to PAL's frontier red -- never bold, no
    icon box -- when the fact is a warning (a floor bites, or a page-level
    setting silently does not apply here). Same recipe as
    `views_collab._basis_caption`, so the same kind of fact reads identically
    on every page; kept local rather than imported because this file owns no
    cross-page helper module."""
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
    a second badge, and it is why the "umbrella and type-corrected are
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
    """The tile's SECOND subline, positioning the value in the index
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
      * concentration (HHI) and breadth -- an earlier pass had already stripped the
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
    knows -- the same pairing the original tile spec used."""
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
    half when these columns have not landed on this deployed index yet, or
    the cell is null."""
    n = row.get("n_stars")
    if n is None or pd.isna(n):
        return MISSING_KPI_MARK, _STARS_SUBLINE, _STARS_HELP
    share = row.get("star_share")
    share_txt = _pct(share) if share is not None and not pd.isna(share) else NA_MARK
    return f"{_count(n)}{copy.STRIP_JOIN}{share_txt} of output", _STARS_SUBLINE, _STARS_HELP


def _led_kpi(row) -> tuple[str, str, str]:
    """(value, subline, help) for the Topics-led tile: index.n_topics_led_all
    (rank<=20 among ALL institution types, one ranking pool -- the Methods
    page states the resulting skew toward large, multi-site organisations),
    MISSING_KPI_MARK when the column is absent or null."""
    n = row.get("n_topics_led_all")
    value = MISSING_KPI_MARK if n is None or pd.isna(n) else _count(n)
    return value, _LED_SUBLINE, _LED_HELP_TEMPLATE.format(n=value)


def _profile_cards(card: dict, row, bundle: dict) -> None:
    """Eight cards in a 2 x 4 grid filling the LEFT half of the profile row
    (cards left, identity and its wordcloud right), each `name + value + one
    small line`, with all methodology behind the card's own `?`. `n/a` (or,
    for the two star-papers/topics-led KPIs, MISSING_KPI_MARK) for anything the data cannot
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
    # The two star-papers/topics-led KPIs read the index ROW directly (their
    # own columns, not the engine's seed_card) and extend the same grid by one
    # more row -- `specs` has 6 entries, so `cols[6]`/`cols[7]` are the two
    # slots `zip` above never consumed.
    stars_value, stars_sub, stars_help = _stars_kpi(row)
    tiles.kpi_tile(cols[len(specs)], KPI_STARS_LABEL, stars_value, stars_sub, help=stars_help)
    led_value, led_sub, led_help = _led_kpi(row)
    tiles.kpi_tile(cols[len(specs) + 1], KPI_LED_LABEL, led_value, led_sub, help=led_help)


def _erc_share(card: dict, row) -> float | None:
    """The ERC-classified share the ERC panel caption reports. A RATIO of two
    card fields, computed once so the caption reads a value rather than an
    expression.

    The numerator is on the WHOLE-RUN mass basis (2020-2025), so its
    denominator must be the whole-run `total_frac`, not the 2020-2024 window
    (which printed 109.1 % for Strasbourg). `data_contract.yaml`
    index.erc_classified_mass_frac carries the corrected formula."""
    erc, tot = card["erc_classified_mass_frac"], row.get("total_frac")
    if erc is None or tot is None or pd.isna(tot) or float(tot) <= 0:
        return None
    return erc / float(tot)


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
    """Same shape for the DOCUMENT-TYPE view, from the shipped table. Returns
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
    # The section gets a TITLE carrying the bonus-year footnote in its
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
    # This reverses the two figures' earlier stacking, which put them one above
    # the other because this pair shared its row with the wordcloud, which left each
    # sub-column ~260 px of plot at 1280 px -- a width at which category labels
    # clip and value ticks rotate to vertical. The wordcloud has moved up into
    # row 1, so the pair now owns the FULL section width and each panel gets
    # ~600 px, comfortably past that failure point; side by side is what an
    # earlier SIRIS Streamlit tool's lab card does and what makes the two
    # reads comparable at a
    # glance. Streamlit stacks the two columns anyway below its own small
    # breakpoint, so the 390 px behaviour is exactly as before.
    #
    #  adds the height MATCH. The two builders size themselves from
    # different rules -- the global one from its row count (six domains ->
    # 260 px), the yearly one from a fixed scatter budget (400 px) -- so the
    # pair rendered as two panels of visibly different height sitting side by
    # side, which reads as two unrelated figures rather than one split total.
    # The yearly figure is COMPRESSED onto the global one's height here, in the
    # composing view, rather than in `lib/charts.py`: the constraint is a fact
    # about this LAYOUT (these two figures, this row), not about either builder,
    # and charts.py is a file outside this module's fence. Reading the height off
    # the built figure keeps the two in step if that file retunes either rule.
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
    """VIZ_SPEC S2.16: the top SUBFIELDS_TOP_N subfields by volume on
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


_TOPIC_MODE_BY_LABEL: dict[str, str] = {}   # filled just below, once copy.FIND exists


def _topic_mode_options() -> list[str]:
    """The five "Topics shown" mode labels, in the fixed order the
    segmented control shows them -- built from `copy.py` so the label text
    lives in exactly one place, and reverse-mapped once into
    `_TOPIC_MODE_BY_LABEL` (display label -> `topic_data` mode id)."""
    order = [
        (copy.FIND["TOPIC_MODE_VOLUME"], TopicData.MODE_VOLUME),
        (copy.FIND["TOPIC_MODE_FWCI"], TopicData.MODE_FWCI),
        (copy.FIND["TOPIC_MODE_LED"], TopicData.MODE_LED),
        (copy.FIND["TOPIC_MODE_STARS"], TopicData.MODE_STARS),
        (copy.FIND["TOPIC_MODE_EMERGENCE"], TopicData.MODE_EMERGENCE),
    ]
    _TOPIC_MODE_BY_LABEL.clear()
    _TOPIC_MODE_BY_LABEL.update(dict(order))
    return [label for label, _ in order]


@st.cache_data(show_spinner=False, max_entries=12)
def _topic_planes_frame(iid: str, tree: str) -> pd.DataFrame:
    """The topic-plane perimeter (articles+reviews 2020-2024, full
    counting, primary topic) is basis-INDEPENDENT -- this cache key
    deliberately carries no `basis`, unlike every other profile frame in
    this file."""
    return TopicData.institution_topics(SC.bundle()["ctx"], iid, tree)


def _panel_topic_planes(iid: str, ctl: dict, card: dict) -> None:
    """The two topic planes (Volume and impact | Frontier) live in ONE
    expander, sharing a single controls row and therefore always the
    IDENTICAL topic set (`TopicData.select_topics` is called once; both
    figures are built from its one return value) -- a Streamlit widget key
    cannot be rendered twice in one run, and the planes are defined to share
    their set by construction (a Streamlit widget key cannot render twice
    in one run, and the two planes are defined to share their selection)."""
    df = _topic_planes_frame(iid, ctl["tree"])
    if df.empty:
        st.caption(copy.FIND["PANEL_EMPTY"])
        return

    mode_label = st.segmented_control(copy.FIND["TOPIC_MODE_LABEL"], _topic_mode_options(),
                                      default=copy.FIND["TOPIC_MODE_VOLUME"], required=True,
                                      key="topic_mode", **state.PERSIST)
    mode = _TOPIC_MODE_BY_LABEL.get(mode_label or copy.FIND["TOPIC_MODE_VOLUME"], TopicData.MODE_VOLUME)
    c_n, c_stat = st.columns([3, 2])
    with c_n:
        n = st.slider(copy.FIND["TOPIC_N_LABEL"], TopicData.N_MIN, TopicData.N_MAX,
                      TOPIC_N_DEFAULT, step=TOPIC_N_STEP, key="topic_n", **state.PERSIST)
    with c_stat:
        stat_label = st.radio(copy.FIND["TOPIC_FWCI_STAT_LABEL"],
                              [copy.FIND["TOPIC_FWCI_STAT_MEAN"], copy.FIND["TOPIC_FWCI_STAT_MEDIAN"]],
                              index=0, horizontal=True, key="topic_fwci_stat", **state.PERSIST)
    fwci_stat = (TopicData.FWCI_STAT_MEAN if stat_label != copy.FIND["TOPIC_FWCI_STAT_MEDIAN"]
                else TopicData.FWCI_STAT_MEDIAN)

    st.caption(copy.FIND["CAPTION_TOPIC_PERIMETER"].format(y0=WINDOW_START, y1=WINDOW_END))

    shown = TopicData.select_topics(df, mode, n, fwci_stat=fwci_stat)
    if shown.empty:
        st.caption(copy.FIND["TOPIC_PLANES_EMPTY"])
        return

    seed_row = SC.bundle()["ctx"]["index_by_id"].loc[iid]
    w1 = seed_row.get("total_ar_full_w1")
    w2 = seed_row.get("total_ar_full_w2")
    total_ar = None if (pd.isna(w1) or pd.isna(w2)) else float(w1) + float(w2)
    facts = TopicData.topic_set_caption(shown, total_ar)
    share_text = NA_MARK if facts["share_of_ar"] is None else _pct(facts["share_of_ar"])

    st.markdown(f"**{copy.FIND['TOPIC_PLANE_A_TITLE']}**")
    st.plotly_chart(charts_topics.fig_plane_impact(shown, fwci_stat=fwci_stat),
                    width="stretch", key="fig_plane_impact")
    st.caption(copy.FIND["CAPTION_TOPIC_PLANE_A"].format(
        n_shown=f"{facts['n_shown']:,}", n_not_placed=f"{facts['n_not_placed_a']:,}",
        n_catchall=f"{facts['n_catchall']:,}", share=share_text,
        y0=WINDOW_START, y1=WINDOW_END))

    st.caption(copy.FIND["AXIS_DEF_TOPIC_PLANES"])

    st.markdown(f"**{copy.FIND['TOPIC_PLANE_B_TITLE']}**")
    scored = shown[np.isfinite(pd.to_numeric(shown["expansion_latest"], errors="coerce"))
                   & np.isfinite(pd.to_numeric(shown["acceleration_latest"], errors="coerce"))]
    if scored.empty:
        st.caption(copy.FIND["FRONTIER_EMPTY"])
    else:
        st.plotly_chart(charts_topics.fig_plane_frontier(shown, color_by="domain"),
                        width="stretch", key="fig_plane_frontier")
    st.caption(copy.FIND["CAPTION_TOPIC_PLANE_B"].format(
        n_no_frontier=f"{facts['n_no_frontier']:,}", n_shown=f"{facts['n_shown']:,}"))


def _panel_sdg(iid: str, ctl: dict, card: dict) -> None:
    """VIZ_SPEC S2.19: sixteen bars in FIXED goal order (the one panel with no
    sort toggle -- the SDG numbers are a canonical sequence a reader navigates
    by position), official UN colours, ESI in the SI slot."""
    df = _sdg_frame(iid, ctl["tree"])
    if df.empty:
        st.caption(copy.FIND["PANEL_EMPTY"])
        return
    st.plotly_chart(charts.fig_sdg(df), width="stretch", key="fig_sdg")
    st.caption(copy.FIND["CAPTION_SDG"].format(
        n_missing=", ".join(str(n) for n in P.SDG_UNCOVERED)))
    # This ratio surface states its OWN
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


def _panel_erc(iid: str, ctl: dict, card: dict) -> None:
    """VIZ_SPEC S2.20: one row per ERC evaluation panel, coloured by its ERC
    DOMAIN (three hues that share nothing with the OpenAlex four -- a different
    taxonomy of the same output), grouped PE -> LS -> SH under the taxonomy
    sort, which is this panel's default."""
    df = _erc_frame(iid, ctl["tree"])
    if df.empty:
        st.caption(copy.FIND["PANEL_EMPTY"])
        return
    sort = _sort_control("erc", default=SORT_TAXONOMY)
    st.plotly_chart(charts.fig_erc(df, sort=sort), width="stretch", key="fig_erc")
    # The ERC-classified share sits in this caption, where the panel it
    # qualifies is on screen; the SI reading note is folded into its `?`.
    st.caption(copy.FIND["CAPTION_ERC"].format(n_panels=f"{len(df):,}",
                                               erc_share=_pct(card.get("_erc_share"))),
               help=copy.FIND["CAPTION_SI"])
    # Same whole-run, six-year basis as the SDG panel above (`erc.parquet`
    # carries no year filter either -- data_contract.yaml erc.parquet.mass /
    # index.erc_classified_mass_frac). Disclosure only, basis unchanged.
    _basis_caption(copy.FIND["RATIO_WHOLE_RUN_BASIS"].format(
        window=SDG_ERC_WINDOW_LABEL, corpus=CORPUS_WINDOW_LABEL))
    if ctl["basis"] == "full":
        _basis_caption(copy.FIND["FRACTIONAL_ONLY_PANEL"], warning=True)


# The six panels of VIZ_SPEC S1.9 block 5, in their fixed order. The key is
# BOTH the expander's session-state key and the widget key suffix.
#
# A panel whose TITLE states its own cut takes its arguments from here rather
# than typing the number into copy.py: "Top {n} subfields" is the
# only such title today.
PANEL_LABEL_ARGS = {"subfields": {"n": SUBFIELDS_TOP_N}}

# "Top topics" and "Frontier positioning" are ONE expander now
# ("Topics: volume, impact and frontier") -- the profile therefore has FIVE
# collapsed panels, not six.
PANELS = (
    ("fields", "PANEL_FIELDS", _panel_fields),
    ("subfields", "PANEL_SUBFIELDS", _panel_subfields),
    ("topic_planes", "PANEL_TOPIC_PLANES", _panel_topic_planes),
    ("sdg", "PANEL_SDG", _panel_sdg),
    ("erc", "PANEL_ERC", _panel_erc),
)


def _profile_panels(iid: str, ctl: dict, card: dict) -> None:
    """The five panels are COLLAPSED by default (VIZ_SPEC S1.9) but their
    bodies run every rerun -- `st.expander` folds the display, never the
    execution.

    A lazy gate was built and REJECTED on a measurement (a
    verify-before-building check): Streamlit 1.61.1's `st.expander` does take
    a `key=` and does publish its open/closed state into `st.session_state`,
    but that state RESETS to the coded `expanded=` on the very next rerun, so
    a body gated on it would blank itself the moment the reader touched any
    other control. Rendering all panels unconditionally costs a measured
    0.88 s warm on the largest seed tested (six panels; five now cost no
    more), inside the 1.5 s budget, so the panels are always built and the
    `key=` is kept only as a stable DOM hook (`.st-key-panel_<name>`) for
    the probe."""
    for name, copy_key, body in PANELS:
        label = copy.FIND[copy_key].format(**PANEL_LABEL_ARGS.get(name, {}))
        with st.expander(label, expanded=False, key=f"panel_{name}"):
            body(iid, ctl, card)


def _render_profile(bundle: dict, subs: dict, seed_id: str, ctl: dict) -> dict:
    """VIZ_SPEC S1.9 / -6 -- the profile as a 2 + 2 split. Row 1 in two
    halves (the SIX KPI cards as a 2 x 3 grid | identity with the wordcloud
    UNDER it), row 2 full width (a titled section holding one control, one chip
    legend and the height-matched breakdown pair), then the five collapsed
    panels (Find folds "Top topics" and "Frontier positioning" into one).
    Returns the seed card, which the L2f tab intro and the export path
    both read after the profile has rendered."""
    ctx = bundle["ctx"]
    card = seed_card(ctx, seed_id, subs, bundle["catchall"])
    row = ctx["index_by_id"].loc[seed_id]
    card["_erc_share"] = _erc_share(card, row)
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


def _scale_guard_removed_count(bundle: dict, rankings: dict, seed_row) -> int:
    """How many candidates the scale guard alone drops from the default
    lens's full ranking, independent of every other post-filter -- the
    number the "Filtered by..." strip names once the guard is switched on
    (D25)."""
    ranking = rankings.get(CFG["lenses"]["default"][0])
    if ranking is None or ranking["undefined"]:
        return 0
    lite = bundle["lite"]
    rows = [lite[i] for i in ranking["sorted_ids"] if i in lite]
    kept = apply_filters(rows, seed_row=seed_row, scale_guard=True)
    return len(rows) - len(kept)


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
    # and ordered by their English name.
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
    ratio_disp = f"{CFG['scale_guard']['ratio']:g}"
    guard = st.checkbox(copy.FIND["SCALE_GUARD_LABEL"].format(ratio=ratio_disp), value=False,
                        help=copy.FIND["SCALE_GUARD_HELP"].format(ratio=ratio_disp),
                        key="f_guard", **state.PERSIST)
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
    the option DOES. Depth is no longer a control here at all -- the
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
    tree x basis."""
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
    basis disclosure, above the table. Adds the L2f-eligible cell count
    here, on the L2f tab and nowhere else: it is a precondition for THAT
    lens's ranking, so a reader meets it on the tab whose list it explains
    rather than in the profile's retired coverage line.

    The tab itself now carries only the bare display code, so
    the FULL lens name is the first line rendered INSIDE the tab -- this
    function's own opening line, `copy.LENS_DISPLAY_NAMES[lens]` (the renumbered
    code + the same name `copy.LENS_NAMES` always carried).

    The gloss used to stay bold-visible with the CAVEAT stacked
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
    before -- they are what this lens SAYS about the seed, which the fold
    pattern keeps on screen everywhere else too.

    A later fix: the gloss+caveat pair above was ALREADY hidden behind Streamlit's
    native `help=`, but that is a different visual component
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
    # The per-lens coverage lines the
    # spec asks for -- ERC-classified share on the ERC lenses, SDG-tagged
    # share on the SDG lenses, frontier share on F1, catch-all share on L3 -- were
    # authored in copy.py (EV_ERC/EV_SDG/EV_FRONTIER/EV_CATCHALL) but never wired
    # once the profile coverage line was retired. Each is a statement about the
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
        # A page-level setting the reader just touched silently
        # not applying to THIS tab is exactly the kind of fact a warning
        # colour exists for -- kept VISIBLE (never folded into a `?` nobody
        # hovers) but recoloured, never bold, no icon box.
        _basis_caption(copy.FIND["BASIS_DISCLOSURE"], warning=True)


def _tail_search(lens: str, ranking: dict, bundle: dict, subs: dict, kept,
                 ctx_bits: dict) -> None:
    """VIZ_SPEC S2.7: search scoped to the FULL filtered ranking.

    This used to also carry the
    per-lens CSV download (`_csv` + `st.download_button`) right below the
    tail search; that button is GONE -- every lens now downloads together in
    the ONE end-of-page workbook (`_find_exports`), a measured, cheap
    "compute every lens at export time" approach. The
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
        # The engine's own `reason` is a debugging string (it names
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
    # The old `ranked.depth_caption`
    # pointed at the per-lens CSV button just removed (".or download the
    # full ranking"); this page now renders its OWN depth line, built from
    # `copy.DEPTH_CAPTION_TEMPLATE` (the exact rewritten string), which
    # points at the one end-of-page workbook instead. `ranked.depth_caption`
    # is unchanged and still exercised by its own tests -- it is simply no
    # longer this page's caller (flagged for a future dead-code sweep, out
    # of this module's fence).
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
    # The chips are lens CODES, which are stable identifiers rather than
    # self-explaining names -- so the table says what a chip means and points at
    # the guide that names every lens in full.
    st.caption(copy.FIND["LENS_LEGEND_CAPTION"].format(N=CONCORDANCE_N))


# ---------------------------------------------------------- aspirational ----

def _aspirational_frame(rows: list[dict], *, score_key: str = "lens_score_L1_overlap",
                        score_label_key: str = "COL_L1") -> pd.DataFrame:
    """VIZ_SPEC S2.5, revised: the interval column is GONE
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
            # A locale fix: pre-scaled 0-100, the SAME transform `lib/ranked.py:format_rows`
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
            # A locale fix: was the banned locale-sensitive ProgressColumn
            # `format=` keyword, which renders
            # through the HOST BROWSER LOCALE
            # confirmed comma-decimal live. The
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

    Mode B: when the base aspirational ranking returns NO row for this seed --
    a seed near the impact ceiling of its own look-alike pool, ETH Zurich is
    one such case -- the same
    L1 pool is shown instead, reordered by frontier alignment
    (`engine.aspirational_frontier`, ported from the earlier A-frontier
    definition), labelled explicitly so a reader never mistakes it for the
    base ranking's impact-qualified list. The PP sort toggle stays base-ranking-only: the fallback is
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
    # D25: the aspirational tab is EXEMPT from the scale guard -- every
    # other post-filter still applies.
    asp_filters = {**filters, "scale_guard": False}
    kept = apply_filters(rows, seed_row=seed_row, family_scores=None, **asp_filters)
    if not kept:
        if rows:
            st.info(explain_empty(asp_filters, seed_row))
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
    # The per-tab CSV this used to end on
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
    """"How to read the lenses", a collapsed expander at the head of the
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
    `st.expander`). `lib/palette.py` is out of scope here and ships
    no reusable "alert" token for a widget label; adding one would be a new
    hex under a different name, which the plan forbids as surely as a raw
    literal would be -- left for a future pass to reconcile
    against a true `palette.py` token when unsafe HTML is allowed
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
# ONE workbook at the very end of
# the page replaces every per-lens/per-tab CSV this page used to offer. Built
# from ALL_LENSES (every lens the engine defines), never only the tabs this
# scenario happens to show -- a measured inventory found this
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
    """The eight KPI cards' own numbers: metric name, formatted
    value, and the same small line the card itself carries -- an index
    position for the original five, the fractional-count note for the
    publications card, the pool/citation-window sentence for the two
    star-papers/topics-led KPIs.
    Nowhere else on the page offers these eight figures together as a table
    (the workbook's own "profile numbers" sheet)."""
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
    the retired per-lens CSV carried, built here (at workbook-click time)
    rather than at every tab's own click, so an unopened tab still costs
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
    Overview sheet."""
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
    built into a plain sheet for the workbook -- kept in the DEFAULT
    L1-overlap order regardless of the on-screen sort checkbox, since this
    button is computed 'regardless of open tab', not a copy
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
    # D25: the aspirational tab (and this, its workbook-sheet twin) is
    # EXEMPT from the scale guard -- every other post-filter still applies.
    kept = apply_filters(rows, seed_row=seed_row, family_scores=None,
                         **{**filters, "scale_guard": False})
    if not kept:
        return pd.DataFrame(columns=_ASPIRATIONAL_SHEET_COLUMNS)
    if fallback:
        frame = _aspirational_frame(kept, score_key="lens_score_F1_overlap",
                                    score_label_key="COL_F1")
    else:
        frame = _aspirational_frame(kept)
    return frame[_ASPIRATIONAL_SHEET_COLUMNS]


_LEADERS_SHEET_TITLE = "Topics led & star papers"
_LEADERS_SHEET_COLUMNS = ["topic_id", "topic_name", "world_rank", "n_stars"]
_LEADERS_SHEET_NOT_AVAILABLE = pd.DataFrame([{"note": "not available in this build"}])


def _leaders_sheet_frame(seed_id: str) -> pd.DataFrame:
    """Sheet 14, "Topics led & star papers": every
    topic this institution leads (world top 20, all institutions -- `topics_led.
    parquet` via `leaders_data.led_topics`, which already carries
    `topic_name`) merged with its star-paper count in that topic
    (`inst_stars.parquet` via `leaders_data.stars_by_topic`), sorted by rank
    then stars descending. `lib.leaders_data` is a newer module, which may
    not exist yet in every checkout -- guarded (import AND shape) so the
    workbook still builds either way: one explanatory row before it lands,
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
        # ImportError (the module has not landed) or any shape mismatch against the
        # contract this was written against
        # either way the workbook still ships its 14th sheet, honestly labelled.
        return _LEADERS_SHEET_NOT_AVAILABLE


_TOPICS_SHEET_TITLE = "Topics"


def _topics_sheet_frame(seed_id: str, tree: str) -> pd.DataFrame:
    """Sheet 15, "Topics": `TopicData.institution_topics` verbatim -- every
    topic with n_ar>=3, every `TopicData.TOPIC_COLS` column, NO cap --
    every workbook gets the uncapped topic data, the same frame the
    profile's topic-plane expander selects its shown set from, before that
    selection ever cuts it down."""
    return TopicData.institution_topics(SC.bundle()["ctx"], seed_id, tree)


def _find_workbook(bundle: dict, subs: dict, ctl: dict, filters: dict, seed_row, card: dict,
                   rankings: dict, bits: dict, seed_id: str) -> bytes:
    """Every lens (`ALL_LENSES`) + the concordance overview + the aspirational
    list + the profile's own KPI numbers + the topics-led/star-papers sheet +
    the uncapped topics sheet, one sheet each, fifteen total, in that order.
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
    sheets.append((_TOPICS_SHEET_TITLE, _topics_sheet_frame(seed_id, ctl["tree"])))
    return workbook_bytes(sheets)


def _find_workbook_filename(seed_id: str, tree: str, basis: str) -> str:
    """"BenchUp_find_<institution>_<tree>_<basis>.xlsx" -- plain
    "BenchUp" capitalisation, built locally."""
    return f"BenchUp_find_{seed_id}_{tree}_{basis}.xlsx"


def _find_exports(bundle: dict, subs: dict, seed_id: str, ctl: dict, filters: dict, seed_row,
                  card: dict, rankings: dict, bits: dict) -> None:
    """ONE download button, replacing every per-lens/per-tab CSV this
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
    guard_removed = (_scale_guard_removed_count(bundle, rankings, seed_row)
                     if filters.get("scale_guard") else None)
    strip = active_controls_strip(tree=_strip_tree(ctl["tree"]), basis=ctl["basis"],
                                  depth=ctl["depth"], c1_on=ctl["c1_on"], l7_on=ctl["l7_on"],
                                  filters=filters, scale_guard_removed=guard_removed)
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
