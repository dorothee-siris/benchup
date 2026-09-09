"""
tests/test_pages_methods.py -- (BenchUp V4 trim): the Methods page
and the 3-card Menu.

Run from cwd `app/`: python -m pytest tests/test_pages_methods.py -q
"""
from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lib import copy
from lib.data_cache import manifest

APP_DIR = Path(__file__).resolve().parents[1]
MENU_PAGE = str(APP_DIR / "Menu.py")
# open-book-tilted-left, the file's real name (AppTest.from_file resolves a
# relative path against THIS module, under tests/, so both paths are made
# absolute here -- same reason pages/1_(magnifying-glass)_Find.py is absolute
# in tests/test_pages.py).
METHODS_PAGE = str(APP_DIR / "pages" / "3_\U0001F4D6_Methods.py")

# `{[a-z_]+}` -- a real unfilled template placeholder ("{n_seeds}") never
# contains anything but lowercase letters and underscores; this deliberately
# will NOT flag a markdown/CSS brace pair with other content, so the test
# stays specific to the failure mode it exists to catch.
PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}")

EXPECTED_SECTION_KEYS = [
    "what_it_is", "data_windows", "counting_bases", "taxonomy", "two_baselines",
    "frontier_scores", "world_leaders", "star_papers", "topic_planes", "topic_overlap",
    "relationship", "reading_momentum", "matching", "scale_guard", "limits",
]


def _methods_app() -> AppTest:
    return AppTest.from_file(METHODS_PAGE, default_timeout=120)


def _page_text(at: AppTest) -> str:
    """Every rendered string AppTest exposes for this page. `at.markdown`
    and `at.caption` are FLAT collectors across the whole element tree, so
    this does not need to walk `at.expander[i].markdown` itself."""
    parts = [t.value for t in at.title]
    parts += [c.value for c in at.caption]
    parts += [m.value for m in at.markdown]
    parts += [e.label for e in at.expander]
    return "\n".join(p for p in parts if p)


# ------------------------------------------------------------- Methods -----

def test_methods_page_renders_without_exception():
    at = _methods_app().run()
    assert not at.exception, [str(e) for e in at.exception]


def test_methods_page_title_and_lead_from_nav():
    at = _methods_app().run()
    assert not at.exception
    assert copy.NAV["METHODS_LABEL"] in [t.value for t in at.title]
    assert copy.NAV["METHODS_LEAD"] in [c.value for c in at.caption]


def test_methods_page_verdict_line_present():
    at = _methods_app().run()
    assert not at.exception
    assert copy.VERDICT_LINE in _page_text(at)


def test_methods_page_has_exactly_fifteen_sections_in_order():
    """One section per objection a reader is entitled to raise about the app
    as it stands, fifteen total: the earlier trim's own eight unaffected
    sections, plus the four sections added or split out for the topic
    planes, topic overlap, reading momentum and scale guard content -- no
    survivor of the pre-trim page (the aspirational view's old detail,
    ERC/SDG classifier detail, impact bootstrap intervals, gated overrides,
    the old standalone pair-view floors block, the two-pool topics-led
    reading, the pooled frontier-positioning KPIs, the shared-frontier
    mirror chart as its own section)."""
    assert list(copy.METHODS.keys()) == EXPECTED_SECTION_KEYS, list(copy.METHODS.keys())

    at = _methods_app().run()
    assert not at.exception
    labels = [e.label for e in at.expander]
    assert len(labels) == 15, (len(labels), labels)
    for key, section in copy.METHODS.items():
        assert section["title"] in labels, (key, section["title"], labels)


def test_methods_page_carries_a_reading_momentum_section():
    """The relationship's momentum tile points readers at a shortened,
    restored 'Reading momentum' section, pinned by name on its own, since it
    is the one section a tile '?' cross-references by title."""
    assert copy.METHODS["reading_momentum"]["title"] == "Reading momentum"
    at = _methods_app().run()
    assert not at.exception
    assert "Reading momentum" in [e.label for e in at.expander]


def test_methods_page_carries_topic_planes_and_topic_overlap_sections():
    """Find's two topic planes and Compare's topic overlap (absorbing the
    earlier frontier-positioning and shared-frontier reading) each get
    their own section, not folded into an older one."""
    assert copy.METHODS["topic_planes"]["title"] == "Topic planes"
    assert copy.METHODS["topic_overlap"]["title"] == "Topic overlap"


def test_methods_page_carries_a_scale_guard_section():
    """The flat-ratio scale guard, previously undocumented on this page,
    gets a section of its own."""
    assert copy.METHODS["scale_guard"]["title"] == "Scale guard"
    assert "aspirational" in copy.METHODS["scale_guard"]["body"].lower()


def test_methods_page_has_no_unfilled_placeholder():
    """Every `{placeholder}` copy.METHODS carries must be gone from the
    rendered page: methods_values fills every name METHODS_SOURCES
    documents (test_methods_note.py already proves the two dicts agree)."""
    at = _methods_app().run()
    assert not at.exception
    leftover = PLACEHOLDER_RE.findall(_page_text(at))
    assert not leftover, leftover


def test_methods_page_snapshot_stamp_matches_manifest():
    at = _methods_app().run()
    assert not at.exception
    mf = manifest()
    snapshot = mf.get("snapshot") or "n/a"
    assert snapshot != "n/a", "manifest() carries no snapshot to compare against"
    assert snapshot in _page_text(at)


def test_methods_page_offers_the_note_download():
    at = _methods_app().run()
    assert not at.exception
    buttons = at.get("download_button")
    assert len(buttons) >= 1, "no st.download_button on the Methods page"


def test_methods_values_match_documented_sources():
    """Cross-check against copy.METHODS_SOURCES: every documented
    placeholder name has an entry in methods_values, and every filled
    (non-NA) value is a plain int/float/str, never a stray NaN or a pandas
    scalar type that would render oddly."""
    from lib.palette import NA_MARK
    from lib.views_methods import methods_values

    values = methods_values()
    documented = set(copy.METHODS_SOURCES)
    assert documented <= set(values), documented - set(values)
    for name, v in values.items():
        if v == NA_MARK:
            continue
        assert isinstance(v, (int, float, str)), (name, type(v), v)


def test_methods_values_match_sources_on_the_surviving_numbers():
    """A handful of the live-measured figures pinned against a direct,
    independent read of the same shipped tables, so a future data refresh
    that shifts them is caught here rather than only inside views_methods.py
    itself."""
    import duckdb
    import pandas as pd

    from lib.compare_data import ELITE_FRONTIER_PERCENTILE, PAIR_QUALIFYING_FLOOR
    from lib.data_cache import DATA_DIR, topics_dim
    from lib.views_methods import methods_values

    values = methods_values()
    td = topics_dim()

    assert values["n_topics"] == f"{len(td):,}"
    assert values["n_excluded"] == f"{int(td['is_excluded'].fillna(False).sum()):,}"
    assert values["pair_qualifying_floor"] == PAIR_QUALIFYING_FLOOR
    assert values["top_decile_pct"] == f"{(1 - ELITE_FRONTIER_PERCENTILE) * 100:.0f}%"

    leaders_max = pd.read_parquet(DATA_DIR / "topic_leaders.parquet", columns=["rank"])["rank"].max()
    assert values["leader_depth"] == int(leaders_max)

    con = duckdb.connect()
    try:
        row = con.execute(
            "SELECT display_name, star_share FROM read_parquet(?) "
            "WHERE star_share IS NOT NULL ORDER BY star_share DESC LIMIT 1",
            [str(DATA_DIR / "index.parquet")],
        ).df().iloc[0]
    finally:
        con.close()
    assert values["top_star_name"] == str(row["display_name"])
    assert values["top_star_share"] == f"{float(row['star_share']) * 100:.1f}%"


def test_methods_values_carry_the_new_figures_pinned_independently():
    """The topic-planes / topic-overlap / scale-guard figures added to
    methods_values, each checked against an independent read of the same
    shipped constant or table -- not merely 'the function returned
    something'."""
    from lib.app_config import CFG
    from lib.data_cache import topics_dim
    from lib.topic_data import (
        FWCI_MODE_FLOOR, N_MAX, N_MIN, PAIR_N_MAX, PLANE_A_MIN_COVERED, emergence_threshold,
    )
    from lib.views_find import TOPIC_N_DEFAULT
    from lib.views_methods import methods_values

    values = methods_values()

    assert values["plane_a_min_covered"] == PLANE_A_MIN_COVERED
    assert values["fwci_mode_floor"] == FWCI_MODE_FLOOR
    assert values["n_topic_min"] == N_MIN
    assert values["n_topic_max"] == N_MAX
    assert values["topic_n_default"] == TOPIC_N_DEFAULT
    assert values["pair_n_max"] == PAIR_N_MAX
    # topic_table_cap is retired: the on-page topic-overlap recap table it
    # capped is gone, and the workbook sheet it left uncapped needs no
    # figure stated on this page any more.
    assert "topic_table_cap" not in values
    assert values["scale_guard_ratio"] == f"{CFG['scale_guard']['ratio']:g}"

    threshold = emergence_threshold()
    assert values["emergence_threshold"] == f"{threshold:.3f}"
    td = topics_dim()
    scored = td["frontier_score_latest"].notna()
    assert values["n_scored_topics"] == f"{int(scored.sum()):,}"
    n_at_or_above = int((td.loc[scored, "frontier_score_latest"] >= threshold).sum())
    assert values["n_emergence_topics"] == f"{n_at_or_above:,}"

    # VACUITY: the emergence share the two live counts imply lands in the
    # world top decile's own neighbourhood (a `quantile(0.9)` cut), not at
    # some unrelated share a broken wiring could still pass silently.
    share = n_at_or_above / int(scored.sum())
    assert 0.08 <= share <= 0.12, (n_at_or_above, int(scored.sum()), share)


def test_two_baselines_states_the_mean_as_the_headline_and_no_world_fwci():
    """FWCI_EU's mean is the headline, the median sits beside it, and the
    page states plainly that no world-referenced FWCI exists here."""
    body = copy.METHODS["two_baselines"]["body"]
    assert "the mean, across an institution's own" in body
    assert "the median of the same distribution sits" in body
    assert "no world-referenced version of FWCI" in body
    assert "FWCI_WD" not in body

    # VACUITY: the old median-headline phrasing is genuinely absent, not
    # merely un-searched-for.
    assert "the median, across an institution's own" not in body


# ------------------------------------------------------------------ Menu ---

def test_menu_renders_three_cards_in_narrative_order():
    at = AppTest.from_file(MENU_PAGE, default_timeout=60).run()
    assert not at.exception, [str(e) for e in at.exception]
    assert len(at.columns) == 3, len(at.columns)
    text = " ".join(m.value for m in at.markdown)
    for key in ("FIND_LABEL", "COMPARE_LABEL", "METHODS_LABEL"):
        assert copy.NAV[key] in text, (key, text)
    assert "COLLAB_LABEL" not in copy.NAV, "the Collaborate card must not survive the trim"


def test_menu_intro_from_nav():
    at = AppTest.from_file(MENU_PAGE, default_timeout=60).run()
    assert not at.exception
    assert copy.NAV["MENU_INTRO"] in [c.value for c in at.caption]
    assert "Four pages" not in copy.NAV["MENU_INTRO"], "the intro must count three pages, not four"
    assert "Three pages" in copy.NAV["MENU_INTRO"]


def test_menu_find_card_is_live():
    at = AppTest.from_file(MENU_PAGE, default_timeout=60).run()
    assert not at.exception
    links = at.get("page_link")
    assert len(links) >= 1, "the Find card should be a live st.page_link"
    assert any("Find" in (lk.label or "") for lk in links), [lk.label for lk in links]


# ---------------------------------------------------------------- lenses ---

def test_lens_concordance_table_names_every_display_code_and_internal_id():
    """copy._lens_concordance_table must name every display code AND every
    internal id exactly once each, built from FC's own LENS_DISPLAY_CODE/
    LENS_DISPLAY_NAMES rather than a second hand-typed list that could drift.
    The Matching section splices this table straight into its own body."""
    table = copy._lens_concordance_table()
    for internal, display in copy.LENS_DISPLAY_CODE.items():
        assert f"**{display}**" in table, (internal, display, table)
        assert f"({internal})" in table, (internal, table)
    assert table in copy.METHODS["matching"]["body"]


def test_matching_section_states_depth_and_concordance():
    """The benchmark depth is fixed at 50 (the 30/50 radio is retired);
    the concordance counts each lens's top-50, the same depth as the ranked lists."""
    from lib.app_config import CFG
    from lib.views_methods import methods_values

    assert CFG["depth"]["max"] == 50
    assert CFG["concordance_N"] == 50
    values = methods_values()
    assert values["depth_max"] == 50
    assert values["concordance_n"] == 50


# ------------------------------------------------ corrected frontier wording

def test_frontier_and_topic_planes_sections_carry_the_corrected_wording():
    """The corrected reading (three-year bins through 2019-21 plus the
    2022-23 latest bin, the 0.7/0.3 weighting) must reach the rendered page
    through `frontier_scores_intro` -- filled from `lib.how_to_read.methods`,
    the one source `docs/how_to_read.yaml` also feeds to the topic planes'
    own caption and Compare's overlay how-to-read line."""
    from lib.views_methods import methods_values

    values = methods_values()
    for token in ("2019-21", "2022-23", "0.7"):
        assert token in values["frontier_scores_intro"], (token, values["frontier_scores_intro"])

    at = _methods_app().run()
    assert not at.exception
    text = _page_text(at)
    for token in ("2019-21", "2022-23", "0.7"):
        assert token in text, token


def test_old_frontier_wording_is_gone_everywhere():
    """'grew over the latest period' (and 'over the latest period' on its
    own) named the retired reading; neither survives on the rendered Methods
    page, in copy.py's own two sections, nor in the source note."""
    from lib.views_methods import methods_values

    banned = ("over the latest period", "grew over")
    values = methods_values()
    for key in ("frontier_scores", "topic_planes"):
        section = copy.METHODS[key]
        rendered = section["body"].format(**values)
        for phrase in banned:
            assert phrase not in rendered, (key, phrase)

    at = _methods_app().run()
    assert not at.exception
    text = _page_text(at)
    for phrase in banned:
        assert phrase not in text, phrase

    note = (Path(__file__).resolve().parents[1] / "docs" / "METHODS_NOTE.md").read_text(
        encoding="utf-8")
    for phrase in banned:
        assert phrase not in note, phrase
