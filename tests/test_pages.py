"""
tests/test_pages.py --: Streamlit AppTest page-render tests for
Menu.py and pages/1_(magnifying-glass)_Find.py.

Streamlit's own `st.cache_resource` keeps lib/views_find.py's engine bundle
warm across AppTest instances within one pytest PROCESS (measured on this
build: the first Find-page AppTest.run pays the ~9 s cold load; every
later AppTest instance in the same process -- a fresh seed, a fresh page
runs in ~0.1-0.4 s), so each test below builds its OWN AppTest rather than
mutating one shared instance: session_state on a shared instance would leak
selections between tests, and the shared cost is the process-wide Streamlit
cache, not a pytest fixture.

`AppTest.tabs` returns one entry per rendered `st.tabs(.)` label with a
`.label` attribute -- confirmed against this Streamlit build (1.61.1)
interactively before writing this file; that is the "verify the AppTest
attribute for tabs" step asks for.

Run from cwd `app/`: python -m pytest tests/test_pages.py -q
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from lib import copy, tiles, views_find

APP_DIR = Path(__file__).resolve().parents[1]
# AppTest.from_file resolves a RELATIVE path against the file that CALLS it
# (this test module, under tests/), not the pytest run cwd -- so both page
# paths are made absolute here.
MENU_PAGE = str(APP_DIR / "Menu.py")
FIND_PAGE = str(APP_DIR / "pages" / "1_\U0001F50E_Find.py")  # magnifying-glass-tilted-left, the file's real name

GDANSK = "I40413290"           # University of Gdansk -- seed with all default lenses defined
EMPTY_SIZE_RANGE = (100_000, 100_001)  # verified empty for Gdansk/L1 (see test below), inside the
                                        # slider's real bounds [200, 238_978] on this deployed index


def _find_app(seed_id: str = GDANSK, **extra_state) -> AppTest:
    at = AppTest.from_file(FIND_PAGE, default_timeout=120)
    at.session_state["seed_id"] = seed_id
    for k, v in extra_state.items():
        at.session_state[k] = v
    return at


def _template_literal_segment(template: str) -> str:
    """The template's fixed part for a substring check against rendered
    text: the first NON-EMPTY literal segment once every `{placeholder}` is
    cut out. A plain "text before the first {" reading is empty for a
    template that OPENS on a placeholder (copy.UNDEFINED_LENS_TEMPLATE =
    "{lens} is undefined for this seed: {reason}." starts with "{lens}"),
    which would make that check vacuously true -- this generalises it to
    the first segment that actually carries fixed text, covering both
    template shapes the same way."""
    import re

    segments = [s for s in re.split(r"\{[^{}]*\}", template) if s]
    assert segments, f"template has no fixed text at all: {template!r}"
    return segments[0]


# ---------------------------------------------------------------- Menu -----

def test_menu_renders_without_exception():
    at = AppTest.from_file(MENU_PAGE, default_timeout=60).run()
    assert not at.exception, [str(e) for e in at.exception]


def test_menu_has_at_least_three_nav_cards():
    at = AppTest.from_file(MENU_PAGE, default_timeout=60).run()
    assert not at.exception
    # Menu.py lays out st.columns(len(DIMENSIONS)) with one bordered
    # container per dimension (Find/Compare/Methods) -- st.columns is
    # the cheapest locale-independent proxy AppTest exposes for "N nav
    # cards rendered" (this AppTest build has no dedicated container
    # element type to inspect directly, confirmed interactively: at.get
    # ("container") returns 0 even though 3 bordered st.containers render).
    assert len(at.columns) >= 3
    all_markdown = " ".join(m.value for m in at.markdown)
    # This retired the earlier standalone pair-view page and its
    # own nav card -- Menu now reads "Find peers", "Compare", "How it is
    # built" (three cards, no version word). "Find"/"Compare" are still
    # substrings of the current wording, so only the third card's own check
    # changes here.
    for word in ("Find", "Compare"):
        assert word in all_markdown, all_markdown
    assert "Collaborate" not in all_markdown, all_markdown


def test_menu_data_caption_names_the_index_size_and_the_harvest_date():
    """:
    the menu no longer prints "Snapshot: <label> (generated <timestamp>)". It
    prints the two facts that stamp was standing in for -- how many
    institutions the index holds and what date the data was harvested -- both
    computed at run time. The old assertions are inverted rather than deleted:
    the snapshot LABEL must now be ABSENT, and the caption must still carry no
    n/a mark (a manifest with no parsable stamp would produce one)."""
    at = AppTest.from_file(MENU_PAGE, default_timeout=60).run()
    from lib.app_config import CFG
    from lib.data_cache import index, manifest
    from lib.exports import data_date_label

    mf = manifest()
    snapshot_label = mf.get("snapshot") or CFG.get("snapshot", "n/a")
    captions = [c.value for c in at.caption]
    expected_date = data_date_label(
        mf.get("source_manifest_generated_at") or mf.get("generated_at")
        or mf.get("deployed_at"), "n/a")
    data_caption = next((c for c in captions if expected_date in c), None)
    assert data_caption is not None, captions
    assert f"{len(index()):,}" in data_caption, data_caption
    assert "n/a" not in data_caption, data_caption
    # .and the retired stamp is gone from the whole page, not just moved.
    page_text = " ".join([*captions, *(m.value for m in at.markdown)])
    assert snapshot_label not in page_text, page_text
    assert "Snapshot:" not in page_text, page_text


# ---------------------------------------------------------------- Find -----

def test_find_default_seed_renders_ten_tabs_no_c1_l7():
    at = _find_app().run()
    assert not at.exception, [str(e) for e in at.exception]
    labels = [t.label for t in at.tabs]
    assert len(at.tabs) >= 10, labels
    assert "Overview" in labels
    # /A11: the tab now carries the bare DISPLAY code, and the
    # Aspirational tab carries its star.
    assert copy.FIND["TAB_ASPIRATIONAL"] in labels, labels
    assert copy.LENS_DISPLAY_CODE["C1"] not in labels, \
        "C1 must be OFF by default"
    assert copy.LENS_DISPLAY_CODE["L7"] not in labels, \
        "L7 must be OFF by default"


def test_find_c1_and_l7_toggles_add_two_tabs():
    at = _find_app().run()
    assert not at.exception
    # keys read from lib/views_find.py:_sidebar_scenario (sb.checkbox(., key="c1_on"/"l7_on")),
    # never guessed from label text (state-driven, locale-independent selector).
    at.session_state["c1_on"] = True
    at.session_state["l7_on"] = True
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    labels = [t.label for t in at.tabs]
    assert len(at.tabs) == 12, labels
    # : a tab carries the bare DISPLAY code (C1 -> L8, L7 -> L9); the
    # full name moved inside the tab body and the lens guide.
    assert copy.LENS_DISPLAY_CODE["C1"] in labels and copy.LENS_DISPLAY_CODE["L7"] in labels, labels


def test_undefined_lens_shows_template(undefined_l2f_seed):
    at = _find_app(seed_id=undefined_l2f_seed).run()
    assert not at.exception, [str(e) for e in at.exception]
    labels = [t.label for t in at.tabs]
    disp = copy.LENS_DISPLAY_CODE["L2f"]
    assert disp in labels, labels
    tab = at.tabs[labels.index(disp)]
    text = " ".join(x.value for x in (*tab.info, *tab.caption, *tab.markdown))
    fixed = _template_literal_segment(copy.UNDEFINED_LENS_TEMPLATE)
    assert fixed in text, text
    # The reader gets the lens's own plain-language precondition, never
    # the engine's debugging string (which names internal structures).
    assert copy.LENS_UNDEFINED_REASON["L2f"] in text, text
    assert "excess-SI" not in text, text


def test_type_filter_empties_a_lens_list():
    """DEVIATION from the literal wording ("set a type filter to a
    type absent from the seed's L1 top-50"): measured directly --
    for I40413290/L1, EVERY institution type has at
    least 76 candidates somewhere in the full positive-score ranking (not
    just the top 50), so no single-type filter empties the list. A narrow
    total-works size_range does reliably empty it (apply_filters(.,
    size_range=(100_000, 100_001)) -> 0 kept, verified against this
    deployed index whose max total_full_2020_2024 is 238,978) and exercises
    the same "post-filter empties the ranking" code path the intent
    is really after (lib/filters.py's own predicates are independent per
    )."""
    at = _find_app().run()
    assert not at.exception
    at.session_state["f_size"] = EMPTY_SIZE_RANGE
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    labels = [t.label for t in at.tabs]
    tab = at.tabs[labels.index(copy.LENS_DISPLAY_CODE["L1"])]
    text = " ".join(x.value for x in tab.info)
    fixed = _template_literal_segment(copy.EMPTY_STATE_TEMPLATE)
    assert fixed in text, text


# --------------------------------------------------------- fixtures --------

@pytest.fixture(scope="module")
def engine_ctx():
    """Module-scope: cold load (~7 s) paid ONCE for this file's undefined-
    seed discovery, independent of the process-wide Streamlit cache the
    AppTest-based tests above ride on."""
    from lib.engine import load_substrates, load_context

    ctx = load_context(APP_DIR / "data")
    subs = load_substrates(ctx)  # default scenario: bestfit / frac
    return ctx, subs


@pytest.fixture(scope="module")
def undefined_l2f_seed(engine_ctx) -> str:
    """A seed whose L2f ranking is undefined, found via the engine over the
    20 smallest-total_full_2020_2024 institutions -- I24568809 on this deployed snapshot, reason:
    "seed's excess-SI vector is empty under candidate (f), papers>=30
    (n_eligible_cells=0)"."""
    from lib.engine import rank_all

    ctx, subs = engine_ctx
    idx = ctx["index_df"].nsmallest(20, "total_full_2020_2024")
    for iid in idx["institution_id"]:
        if rank_all(ctx, subs, iid, ["L2f"])["L2f"]["undefined"]:
            return iid
    pytest.skip("no undefined-L2f seed found among the 20 smallest institutions on this snapshot")


# ------------------------------------------------ Find: the profile section -----
# The seed card
# became a PROFILE section (header, 7 KPI tiles, coverage caption, wordcloud +
# yearly breakdown pair, six collapsed chart panels) and the benchmark controls
# moved out of the sidebar into a controls row at the head of the Benchmark
# section. Every selector below is state- or copy-driven, never a typed label.

STRASBOURG = "I68947357"   # the drive seed; the reference seed

# Widget keys L16 froze: the controls MOVED but were NOT renamed, which is the
# whole reason the move was cheap (the smoke suite's selectors survive it).
# "Depth" is dropped -- the radio it named is retired, the cut is fixed.
CONTROLS_ROW_KEYS = ("c1_on", "l7_on")
POST_FILTER_KEYS = ("f_types", "f_countries", "f_excl_own", "f_size", "f_guard", "f_family")


def test_find_profile_section_renders_header_and_eight_cards():
    """ takes the six original cards to eight (adds star
    papers and topics led): the profile section holds the seed's name and
    exactly EIGHT KPI cards, each carrying ONE small line. AppTest exposes no
    container element type
    (see test_menu_has_at_least_three_nav_cards), so the cards are counted by
    lib/tiles.py's own stable class hooks, never by a user-facing string.

    The four dropped measures are asserted ABSENT rather than simply not
    asserted present: "the tiles are gone" is the decision, and a test that
    only stopped naming them would pass with all eight still on screen."""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    headers = [h.value for h in at.header]
    assert copy.FIND["PROFILE_HEADER"] in headers, headers
    assert copy.FIND["BENCHMARK_HEADER"] in headers, headers
    rendered = [m.value for m in at.markdown if tiles.TILE_CLASS in m.value]
    assert len(rendered) == views_find.N_CARDS == 8, len(rendered)
    for html in rendered:
        assert html.count(tiles.SUBLINE_CLASS) == 1, html
    for label_key in ("KPI_PUBS_LABEL", "KPI_SDG_LABEL", "KPI_FRONTIER_LABEL", "KPI_PP_LABEL",
                      "KPI_INTL_LABEL", "KPI_COMPANY_LABEL"):
        assert any(copy.FIND[label_key] in html for html in rendered), label_key
    for label in (views_find.KPI_STARS_LABEL, views_find.KPI_LED_LABEL):
        assert any(label in html for html in rendered), label
    from lib.app_config import CFG
    # the retired tile design's own labels (Concentration, Breadth, the bonus-year tile)
    dropped = ["Concentration", "Breadth",
               f"Publications in {CFG['bonus_year']} (bonus year)"]
    for label in dropped:
        assert not any(label in html for html in rendered), label
    # .and every one of the SIX ORIGINAL cards' small line is the index
    # baseline itself, EXCEPT the publications card, whose small line is the
    # same measure on the fractional basis -- asserted here rather
    # than skipped, so a card that quietly lost its reference line still
    # fails. The two new KPIs carry their OWN small line (pool name / citation
    # window), never the index-baseline template, so they are excluded from
    # this count on purpose.
    baseline_fixed = _template_literal_segment(copy.FIND["TILE_BASELINE_SUB"])
    with_baseline = [h for h in rendered if baseline_fixed in h]
    assert len(with_baseline) == 5, len(with_baseline)
    pubs = [h for h in rendered if copy.FIND["KPI_PUBS_LABEL"] in h]
    assert len(pubs) == 1 and tiles.VALUE2_CLASS in pubs[0], pubs


def test_kpi_builders_render_from_a_tiny_fixture_index_with_the_five_new_columns():
    """ acceptance step 4: a tiny, hand-built index frame
    carrying the five new columns, run through the tile-BUILDER functions
    directly (no Streamlit) -- proves the two new KPI strings render once the
    columns exist, independent of whether the real deployed index has them
    yet (the absent-column path is the test right after this one).

    v1.7: one ranking pool -- the Topics-led subline/help are now FIXED text
    ("world top 20, all institutions") regardless of the institution's own
    `type`, so I_EDU and I_RTO (education vs facility) must render the
    IDENTICAL subline, not a type-conditional one."""
    fixture = pd.DataFrame([
        {"institution_id": "I_EDU", "type": "education", "n_stars": 16, "star_share": 0.021,
         "n_topics_led_all": 39},
        {"institution_id": "I_RTO", "type": "facility", "n_stars": 0, "star_share": 0.0,
         "n_topics_led_all": 0},
    ]).set_index("institution_id")

    row = fixture.loc["I_EDU"]
    stars_value, stars_sub, stars_help = views_find._stars_kpi(row)
    led_value, led_sub, led_help = views_find._led_kpi(row)
    #  shortening: "N (x.x% of output)" wrapped mid-word at the tile's
    # own width; the middle-dot join (copy.STRIP_JOIN, the same separator
    # every other strip/caption in the app uses) replaces the parentheses.
    assert stars_value == "16 · 2.1% of output", stars_value
    assert led_value == "39", led_value
    assert led_sub == "world top 20, all institutions", led_sub
    assert "all institutions" in led_help, led_help
    assert views_find.MISSING_KPI_MARK not in stars_value
    assert views_find.MISSING_KPI_MARK not in led_value

    row_rto = fixture.loc["I_RTO"]
    rto_value, rto_sub, rto_help = views_find._led_kpi(row_rto)
    assert rto_value == "0", rto_value
    assert rto_sub == led_sub, (rto_sub, led_sub)  # fixed text, same for every type
    assert "all institutions" in rto_help, rto_help


def test_kpi_builders_render_missing_mark_when_the_p5_columns_are_absent():
    """The other half: an index row from a build that has not landed the new columns yet
    (the columns simply are not there) renders MISSING_KPI_MARK -- never
    NA_MARK (used everywhere else on this page) and never a crash -- and the
    same for a present-but-null cell."""
    row = pd.Series({"institution_id": "I_OLD", "type": "education"})
    stars_value, _, _ = views_find._stars_kpi(row)
    led_value, _, _ = views_find._led_kpi(row)
    assert stars_value == views_find.MISSING_KPI_MARK, stars_value
    assert led_value == views_find.MISSING_KPI_MARK, led_value

    row_null = pd.Series({"n_stars": float("nan"), "star_share": float("nan"),
                          "type": "education", "n_topics_led_all": float("nan")})
    stars_value2, _, _ = views_find._stars_kpi(row_null)
    led_value2, _, _ = views_find._led_kpi(row_null)
    assert stars_value2 == views_find.MISSING_KPI_MARK, stars_value2
    assert led_value2 == views_find.MISSING_KPI_MARK, led_value2


def test_find_profile_has_no_coverage_line():
    """VIZ_SPEC S2.12, retired: the coverage caption is REMOVED from the
    page, not shortened -- its four items now live in the panel, tile or tab
    that each one qualifies."""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    page_text = " ".join(x.value for x in (*at.caption, *at.markdown, *at.info))
    # the retired coverage caption's own fixed opening segment, now gone from copy.py too
    fixed = "ERC-classified share "
    assert fixed not in page_text, fixed
    # ...and the relocated items ARE on the page, where they were moved to.
    erc_fixed = _template_literal_segment(copy.FIND["CAPTION_ERC"])
    catchall_fixed = _template_literal_segment(copy.FIND["CAPTION_TOPIC_PLANE_A"])
    assert erc_fixed in page_text
    assert catchall_fixed in page_text


def test_find_sidebar_selectboxes_show_display_labels():
    """L29: the sidebar renders a LABEL for every internal value; the option
    values themselves are untouched (every frame, cache key and export reads
    them), which is why only the rendered options are asserted here."""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    boxes = {s.key: s for s in at.sidebar.selectbox}
    assert set(copy.TREE_LABELS.values()) == set(boxes["tree"].options), boxes["tree"].options
    assert set(copy.BASIS_LABELS.values()) == set(boxes["basis"].options), boxes["basis"].options
    for internal in copy.TREE_LABELS:
        assert internal not in boxes["tree"].options, internal


def test_find_lens_tabs_carry_the_lens_names_and_the_guide_is_present():
    """ (A11): every lens TAB now carries only the bare DISPLAY code; the
    full name + one-line intro is the first thing INSIDE the tab body
    instead (`_lens_intro`), and the "How to read the lenses" expander at the
    head of the Benchmark section describes each SHOWN lens in one plain
    sentence under its own new code."""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    labels = [t.label for t in at.tabs]
    from lib.app_config import CFG
    shown = list(CFG["lenses"]["default"])
    for lens in shown:
        disp = copy.LENS_DISPLAY_CODE[lens]
        assert disp in labels, (lens, disp, labels)
        tab = at.tabs[labels.index(disp)]
        body_text = " ".join(x.value for x in tab.markdown)
        assert copy.LENS_DISPLAY_NAMES[lens] in body_text, (lens, body_text)
    # expander title carries the same `:red[.]` markdown-lite wrapper
    # `_lens_guide` applies (A11's red title, the one colour a widget label
    # can take on this pinned Streamlit build -- see that function's own
    # docstring) around the plain header text.
    expander_labels = [e.label for e in at.expander]
    red_header = f":red[{copy.FIND['LENS_INTRO_HEADER']}]"
    assert red_header in expander_labels, expander_labels
    guide = at.expander[expander_labels.index(red_header)]
    text = " ".join(x.value for x in (*guide.markdown, *guide.caption))
    assert copy.FIND["LENS_INTRO_LEAD"] in text
    for lens in shown:
        assert copy.LENS_INTRO[lens] in text, lens
        assert copy.LENS_DISPLAY_NAMES[lens] in text, lens


def test_topic_mode_swap_changes_the_selected_topic_set_and_its_caption():
    """Rewrite of the old L33/frontier-mode claim: the "Topics shown"
    segmented control changes WHICH topics both planes draw -- recomputed
    off `TopicData` directly (not circular against the page's own
    rendering), then cross-checked against the live page's own
    plane-A caption facts (`n_shown`/`n_catchall`), which must always match
    `TopicData.topic_set_caption`'s numbers for whichever mode is active."""
    from lib import topic_data as TD
    from lib.engine import load_context

    ctx = load_context(APP_DIR / "data")
    df = TD.institution_topics(ctx, STRASBOURG, "bestfit")
    vol_set = set(TD.select_topics(df, "volume", 50)["topic_id"])
    led_set = set(TD.select_topics(df, "led", 50)["topic_id"])
    assert vol_set != led_set, "volume and led modes must select different topic sets on this seed"

    row = ctx["index_by_id"].loc[STRASBOURG]
    total_ar = float(row["total_ar_full_w1"]) + float(row["total_ar_full_w2"])
    facts_vol = TD.topic_set_caption(TD.select_topics(df, "volume", 50), total_ar)

    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    controls = {c.key: c.value for c in at.segmented_control}
    assert controls.get("topic_mode") == copy.FIND["TOPIC_MODE_VOLUME"], controls
    caption_text = " ".join(c.value for c in at.caption)
    assert f"{facts_vol['n_shown']:,}" in caption_text, (facts_vol, caption_text)
    assert f"{facts_vol['n_catchall']:,}" in caption_text

    at.session_state["topic_mode"] = copy.FIND["TOPIC_MODE_LED"]
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    facts_led = TD.topic_set_caption(TD.select_topics(df, "led", 50), total_ar)
    caption_text2 = " ".join(c.value for c in at.caption)
    assert f"{facts_led['n_shown']:,}" in caption_text2, (facts_led, caption_text2)


def test_topic_planes_captions_have_no_unfilled_placeholder():
    """A `.format(...)` call that forgets a kwarg leaves a literal '{y0}' on
    the page -- caught here by asserting the ACTUAL substituted window
    ('2020-2024', real digits) appears, not just a fixed prose fragment that
    would still be present either way. (Found live on a manager render-read:
    the perimeter caption's own `.format()` call was missing entirely.)"""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    caption_text = " ".join(c.value for c in at.caption)
    assert "{y0}" not in caption_text and "{y1}" not in caption_text, caption_text
    window = f"{views_find.WINDOW_START}-{views_find.WINDOW_END}"
    assert window in caption_text, (window, caption_text)
    assert "{" not in copy.FIND["CAPTION_TOPIC_PERIMETER"].format(
        y0=views_find.WINDOW_START, y1=views_find.WINDOW_END)


def test_top_subfields_panel_has_no_sort_control_and_cuts_at_thirty():
    """L34: the top-subfields panel is a volume-ordered cut of
    SUBFIELDS_TOP_N rows with NO sort toggle (the other bar panels keep
    theirs), and the cut is stated parametrically in its own title."""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    radio_keys = {r.key for r in at.radio}
    assert "sort_subfields" not in radio_keys, radio_keys
    # the topics panel loses its sort control too --
    # `fig_topics` is always volume-ordered now, so the toggle was dead UI.
    assert "sort_topics" not in radio_keys, radio_keys
    assert {"sort_fields", "sort_erc"} <= radio_keys, radio_keys
    assert views_find.SUBFIELDS_TOP_N == 30
    expected = copy.FIND["PANEL_SUBFIELDS"].format(n=views_find.SUBFIELDS_TOP_N)
    assert expected in [e.label for e in at.expander], [e.label for e in at.expander]

    from lib import profile_data
    from lib.engine import load_substrates, load_context

    ctx = load_context(APP_DIR / "data")
    subs = load_substrates(ctx, "bestfit", "frac")
    df = profile_data.subfields_table(ctx, subs, STRASBOURG)
    assert len(df) > views_find.SUBFIELDS_TOP_N, len(df)
    assert len(df.nlargest(views_find.SUBFIELDS_TOP_N, "vol_frac")) == 30


def test_strip_shows_a_display_label_for_a_non_default_tree():
    """L29: the "Filtered by." strip names the taxonomy the reader chose in
    the words the sidebar used, never the internal value."""
    at = _find_app(seed_id=STRASBOURG)
    at.session_state["tree"] = "original"
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    text = " ".join(m.value for m in at.markdown)
    assert copy.STRIP_TREE.format(tree=copy.TREE_LABELS["original"]) in text, text
    assert copy.STRIP_TREE.format(tree="original") not in text, text


def test_find_profile_has_wordcloud_image_and_breakdown_control():
    """L17 block 4: the wordcloud raster, and the ONE segmented control that
    swaps both breakdown figures between the domain and doc-type family."""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    assert len(at.get("image")) >= 1, "the subfield wordcloud PNG did not render"
    controls = {s.key: s.value for s in at.segmented_control}
    assert "breakdown_dim" in controls, controls
    assert controls["breakdown_dim"] == copy.FIND["BREAKDOWN_DOMAIN"], controls


def test_find_five_chart_panels_are_expanders_in_the_ruled_order():
    """L17 block 5 / VIZ_SPEC S1.9: Fields, Top subfields, Topics
    (volume/impact/frontier -- the retired "Top topics" and "Frontier
    positioning" panels fold into this ONE expander), SDG profile, ERC
    profile -- in that order -- plus the post-filters expander that heads
    the Benchmark section."""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    labels = [e.label for e in at.expander]
    expected = [copy.FIND[k].format(**views_find.PANEL_LABEL_ARGS.get(name, {}))
                for name, k in (("fields", "PANEL_FIELDS"), ("subfields", "PANEL_SUBFIELDS"),
                                ("topic_planes", "PANEL_TOPIC_PLANES"),
                                ("sdg", "PANEL_SDG"), ("erc", "PANEL_ERC"))]
    assert labels[:len(expected)] == expected, labels
    assert copy.FIND["POSTFILTERS_EXPANDER"] in labels, labels


def test_find_sidebar_holds_scenario_controls_only():
    """L16: depth, C1, L7 and every post-filter LEFT the sidebar. Asserted by
    element TYPE, so a copy edit cannot make it vacuous: depth was the sidebar's
    only radio and the post-filters its only multiselects and its only slider."""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    assert len(at.sidebar.radio) == 0, [r.key for r in at.sidebar.radio]
    assert len(at.sidebar.multiselect) == 0, [m.key for m in at.sidebar.multiselect]
    assert len(at.sidebar.slider) == 0, [s.key for s in at.sidebar.slider]
    # .and what DOES stay: the two scenario selectboxes (tree, basis).
    assert {s.key for s in at.sidebar.selectbox} >= {"tree", "basis"}, \
        [s.key for s in at.sidebar.selectbox]


def test_find_controls_row_keeps_the_same_widget_keys_in_the_main_area():
    """L16's cheapness claim, made falsifiable: the controls moved into the main
    area but every widget key is unchanged, so persist_state and the Playwright
    st-key-* selectors survive the move."""
    at = _find_app(seed_id=STRASBOURG).run()
    assert not at.exception, [str(e) for e in at.exception]
    main_keys = {w.key for w in (*at.radio, *at.checkbox, *at.multiselect, *at.slider)}
    for key in (*CONTROLS_ROW_KEYS, *POST_FILTER_KEYS):
        assert key in main_keys, (key, sorted(k for k in main_keys if k))


def test_find_renders_under_every_tree_and_the_fields_frame_follows_the_tree():
    """Toggle coherence: the page renders under a non-default tree, AND the
    Fields panel's own frame (profile_data.fields_table over that tree's
    substrates -- exactly what views_find._fields_frame caches) actually changes
    with the tree. Computed through the engine rather than scraped off the page,
    because the panel is a Plotly canvas."""
    at = _find_app(seed_id=STRASBOURG)
    at.session_state["tree"] = "original"
    at.run()
    assert not at.exception, [str(e) for e in at.exception]

    from lib import profile_data
    from lib.engine import load_substrates, load_context

    ctx = load_context(APP_DIR / "data")
    frames = {}
    for tree in ("original", "bestfit"):
        subs = load_substrates(ctx, tree, "frac")
        frames[tree] = profile_data.fields_table(ctx, subs, STRASBOURG).set_index("field_id")
    common = frames["original"].index.intersection(frames["bestfit"].index)
    assert len(common) > 0
    diff = (frames["original"].loc[common, "share"] - frames["bestfit"].loc[common, "share"]).abs()
    assert float(diff.max()) > 0, "the Fields frame is identical under original and bestfit"


def test_breakdown_pair_series_agree_on_every_year_total():
    """The invariant that makes ONE segmented control legitimate over TWO data
    sources (.7, the "Unclassified" residual decision): the
    domain view and the document-type view must sum to the SAME volume per year,
    or the swap would read as a bug. Recomputed from the two sources the page
    reads, not from the page."""
    from lib import profile_data
    from lib.data_cache import doctype_by_year
    from lib.engine import load_context

    ctx = load_context(APP_DIR / "data")
    domain = profile_data.yearly_by_domain(ctx, STRASBOURG, "bestfit")
    dt = doctype_by_year()
    dt = dt[dt["institution_id"] == STRASBOURG]
    assert not domain.empty and not dt.empty

    dom_full = domain.groupby("year")["vol_full"].sum()
    dt_full = dt.groupby("year", observed=True)["vol_full"].sum()
    assert sorted(dom_full.index) == sorted(dt_full.index), (list(dom_full.index),
                                                             list(dt_full.index))
    for year in dom_full.index:
        assert abs(float(dom_full[year]) - float(dt_full[year])) < 1.0, (
            year, float(dom_full[year]), float(dt_full[year]))
        dom_frac = float(domain.loc[domain["year"] == year, "vol_frac"].sum())
        dt_frac = float(dt.loc[dt["year"] == year, "vol_frac"].sum())
        assert abs(dom_frac - dt_frac) <= 1e-3 * max(dom_frac, 1.0), (year, dom_frac, dt_frac)


def test_find_workbook_has_fifteen_sheets():
    """Acceptance step 4/6: the Find workbook always has 15 sheets -- the
    original 13 (profile numbers, overview, ten lenses, aspirational) plus
    sheet 14, "Topics led & star papers" (whether or not `lib.leaders_data`
    has landed: unavailable, it is still written as a single explanatory
    row, never omitted), plus sheet 15, "Topics" (every topic with
    n_ar>=3, uncapped -- `TopicData.institution_topics` verbatim). Built
    through the page's own pure frame functions, no Streamlit runtime
    needed."""
    import io

    import openpyxl
    from lib.engine import rank_all

    bundle = views_find.SC.bundle()
    ctx = bundle["ctx"]
    subs = views_find.SC.get("bestfit", "frac")
    seed_id = STRASBOURG
    rankings = rank_all(ctx, subs, seed_id)
    seed_row = ctx["index_by_id"].loc[seed_id]
    card = views_find.seed_card(ctx, seed_id, subs, bundle["catchall"])
    ctl = {"tree": "bestfit", "basis": "frac", "depth": views_find.BENCHMARK_DEPTH,
           "c1_on": False, "l7_on": False}
    filters = {"types": None, "countries": None, "exclude_own_country": False,
              "size_range": None, "scale_guard": False, "family_min": None}
    bits = views_find._ctx_bits(ctl, filters, seed_id, rankings, None, None, card)
    xlsx_bytes = views_find._find_workbook(bundle, subs, ctl, filters, seed_row, card,
                                           rankings, bits, seed_id)
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    assert len(wb.sheetnames) == 15, wb.sheetnames
    assert wb.sheetnames[-1] == views_find._TOPICS_SHEET_TITLE, wb.sheetnames
    topics_ws = wb[views_find._TOPICS_SHEET_TITLE]
    from lib import topic_data as TD
    assert [c.value for c in topics_ws[1]] == TD.TOPIC_COLS
    assert topics_ws.max_row - 1 == len(
        TD.institution_topics(ctx, seed_id, "bestfit")), "the Topics sheet is uncapped"
    assert views_find._find_workbook_filename(seed_id, "bestfit", "frac") == \
        f"BenchUp_find_{seed_id}_bestfit_frac.xlsx"


def test_ranked_frame_carries_two_sizes_and_no_badge_column():
    """L22 on the frame the page actually renders: both counting bases as their
    own columns, the lens-specific evidence cell filled, and no badge column."""
    from lib.engine import build_rows, load_substrates, load_context, rank_all
    from lib.engine.evidence import rows_evidence
    from lib.ranked import format_rows

    ctx = load_context(APP_DIR / "data")
    subs = load_substrates(ctx, "bestfit", "frac")
    rankings = rank_all(ctx, subs, STRASBOURG)
    l1 = rankings["L1"]
    rows = build_rows(l1, ctx, 5, rankings, subs)
    texts = rows_evidence(ctx, subs, "L1", STRASBOURG, [r["institution_id"] for r in rows])
    for r in rows:
        r["evidence_text"] = texts.get(r["institution_id"])
    df = format_rows(rows, lens="L1", depth=5)
    assert {"size_full", "size_frac", "evidence"} <= set(df.columns), list(df.columns)
    assert "badge" not in df.columns, list(df.columns)
    assert (df["evidence"] != "n/a").any(), df["evidence"].tolist()
