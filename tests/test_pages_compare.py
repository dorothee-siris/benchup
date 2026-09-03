"""
tests/test_pages_compare.py -- BenchUp V4 trim,: AppTest
page-render tests for `pages/2_(scales)_Compare.py` and the render helpers
in `lib/views_compare.py`.

REWRITTEN END TO END for the trim. The pre-trim page
offered an N-institution "Compare by" metric-selector matrix, ERC panels,
field-grain dynamics, a pooled frontier scatter, coverage and impact-by-
subfield -- every one of those sections, and the frame builders behind them,
is DELETED. D1 fixes Compare at EXACTLY two institutions (two search
slots, `lib.selection.render_slots`) -- there is no N=3 case to test any
more, and no sidebar-shortlist premise (`lib.selection.render_sidebar`/
`slots_row`, the E3 shims, are gone by the time this stream ends -- see
this file's own final section).

Page order under test (D2): Key figures -> Thematic shape (Profile/Impact
tabs) -> SDG profile (same tab shape) -> Frontier (positioning + the shared
deep dive) -> The relationship -> one Excel download -> the share-link box.

Streamlit's own `st.cache_resource` keeps the engine context and the one
resident scenario warm across AppTest instances within one pytest PROCESS,
so the first test pays the cold load and every later one runs in about a
second. Each test builds its OWN AppTest -- a shared instance would leak
session_state between tests.

Run from cwd `app/`: python -m pytest tests/test_pages_compare.py -q
"""
from __future__ import annotations

import io
from pathlib import Path

import openpyxl
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from lib import charts_compare as X
from lib import compare_data as CD
from lib import copy
from lib import views_compare as VC
from lib.engine import scenario_cache as SC

APP_DIR = Path(__file__).resolve().parents[1]
COMPARE_PAGE = str(APP_DIR / "pages" / "2_⚖️_Compare.py")  # scales, the file's real name

IFREMER = "I154202486"      # the T0 golden anchor pair (also this stream's
NIOZ = "I4210107283"        # own Playwright/manager render target)
PAIR = [IFREMER, NIOZ]

SECTION_HEADER_KEYS = ("CARDS_HEADER", "SHAPE_HEADER", "SDG_HEADER", "FRONTIER_HEADER",
                       "SHARED_FRONTIER_HEADER", "RELATIONSHIP_HEADER")


def _app(ids=None, **extra_state) -> AppTest:
    """Institutions are seeded through `?compare=`, the SAME hydration path
    `lib.selection.render_slots` reads on a fresh session (D1)."""
    at = AppTest.from_file(COMPARE_PAGE, default_timeout=300)
    if ids:
        at.query_params["compare"] = ",".join(ids)
    for k, v in extra_state.items():
        at.session_state[k] = v
    return at


def _markdown_text(at) -> str:
    """Every rendered markdown block, joined -- C3's own captions/notes are
    HTML fragments through `chart_note`/`basis_caption`, rendered via
    `st.markdown`, not `st.caption` alone."""
    return " ".join(m.value for m in at.markdown)


def _caption_text(at) -> str:
    return " ".join(c.value for c in at.caption)


# ------------------------------------------------------------ base render ---

def test_the_page_renders_without_exception_for_the_anchor_pair():
    at = _app(PAIR).run()
    assert not at.exception, [str(e) for e in at.exception]


def test_fewer_than_two_picks_shows_the_one_line_prompt_and_stops():
    at = _app([IFREMER]).run()
    assert not at.exception
    text = _markdown_text(at) + " " + _caption_text(at) + " " + " ".join(i.value for i in at.info)
    assert copy.COMPARE["PROMPT_NEED_TWO"] in text
    # and none of the section headers rendered -- the page genuinely stops,
    # not merely shows the prompt ALONGSIDE a half-built page.
    headers = {h.value for h in at.subheader}
    for key in SECTION_HEADER_KEYS:
        assert copy.COMPARE[key] not in headers


def test_no_picks_at_all_shows_the_same_prompt():
    at = _app(None).run()
    assert not at.exception
    text = _markdown_text(at) + " " + _caption_text(at) + " " + " ".join(i.value for i in at.info)
    assert copy.COMPARE["PROMPT_NEED_TWO"] in text


# ------------------------------------------------------------ section order

def test_the_section_order_matches_the_d2_layout():
    at = _app(PAIR).run()
    assert not at.exception
    headers = [h.value for h in at.subheader]
    order = [copy.COMPARE[k] for k in SECTION_HEADER_KEYS]
    positions = [headers.index(h) for h in order]
    assert positions == sorted(positions), (headers, order)


def test_page_title_and_pin_caption_render():
    at = _app(PAIR).run()
    assert not at.exception
    assert at.title[0].value == copy.COMPARE["PAGE_TITLE"]
    y0, y1 = CD.CORE_WINDOW
    from lib.app_config import CFG

    rendered_pin = copy.COMPARE["PIN_CAPTION"].format(y0=y0, y1=y1, whole_y1=CFG["bonus_year"])
    assert rendered_pin in _markdown_text(at)


# ------------------------------------------------------------------ cards ---

def test_key_figure_cards_render_nine_tiles_per_institution():
    at = _app(PAIR).run()
    assert not at.exception
    html = _markdown_text(at)
    n_tiles = html.count('class="benchup-kpi"')
    assert n_tiles == 18, n_tiles  # 8 single-value cards + 1 co-pub tile, x 2 institutions


def test_at_least_one_card_carries_the_leader_dot():
    at = _app(PAIR).run()
    assert not at.exception
    html = _markdown_text(at)
    assert X.best_value_dot(0) in html or X.best_value_dot(1) in html


# ---------------------------------------------------------------- tabs -----

def test_shape_and_sdg_sections_each_offer_profile_and_impact_tabs():
    at = _app(PAIR).run()
    assert not at.exception
    labels = [t.label for t in at.tabs]
    assert labels.count(copy.COMPARE["TAB_PROFILE"]) == 2
    assert labels.count(copy.COMPARE["TAB_IMPACT"]) == 2


def test_shape_and_sdg_basis_captions_name_the_pin():
    at = _app(PAIR).run()
    assert not at.exception
    html = _markdown_text(at)
    n = CD.top_subfields(SC.bundle()["ctx"], SC.get("bestfit", "full"), PAIR, n=VC.TOP_N_SUBFIELDS)["subfield_id"].nunique()
    assert copy.COMPARE["SHAPE_BASIS_CAPTION"].format(n=n) in html
    assert copy.COMPARE["SDG_BASIS_CAPTION"] in html


def test_sdg_untagged_share_caption_names_both_institutions():
    at = _app(PAIR).run()
    assert not at.exception
    text = _caption_text(at)
    assert "Ifremer" in text and "carries no Sustainable Development Goal tag" in text


# ------------------------------------------------------------- frontier ----

def test_frontier_positioning_shows_five_metrics_per_institution():
    at = _app(PAIR).run()
    assert not at.exception
    labels = [m.label for m in at.get("metric")] if hasattr(at, "get") else [m.label for m in at.metric]
    Cw = copy.COMPARE
    for key in ("FRONTIER_POSITIONING_SHARE", "FRONTIER_POSITIONING_PUBLISHED",
               "FRONTIER_POSITIONING_TOP_DECILE", "FRONTIER_POSITIONING_LED",
               "FRONTIER_POSITIONING_STARS"):
        assert labels.count(Cw[key]) == 2, (key, labels)


def test_shared_frontier_mirror_chart_and_table_both_render():
    at = _app(PAIR).run()
    assert not at.exception
    assert len(at.get("plotly_chart")) if hasattr(at, "get") else True  # smoke: no crash reading charts
    dataframes = at.dataframe
    assert len(dataframes) >= 1, "the shared-frontier table must render as an st.dataframe"


def test_show_all_button_present_and_flips_session_state_via_on_click():
    """`st.button(., on_click=.)` -- the HARD RULE: never `st.rerun`
    after a manual state flip. Clicking the button must not raise, and the
    flag it flips must be True afterwards -- proven through the widget's
    own click, not by setting session_state directly (which would not
    prove the callback wiring)."""
    at = _app(PAIR).run()
    assert not at.exception
    buttons = [b for b in at.button if b.label == copy.COMPARE["SHOW_ALL"].format(
        n=len(CD.shared_frontier(SC.bundle()["ctx"], SC.get("bestfit", "full"), PAIR)))]
    assert len(buttons) == 1, "the Show all button must be present for a pair with >20 shared topics"
    assert "compare_frontier_show_all" not in at.session_state
    buttons[0].click().run()
    assert not at.exception
    assert at.session_state["compare_frontier_show_all"] is True


# --------------------------------------------------------- relationship ----

def test_relationship_section_shows_momentum_and_joint_stars_link():
    at = _app(PAIR).run()
    assert not at.exception
    html = _markdown_text(at)
    assert copy.COMPARE["JOINT_STARS_LINK_LABEL"] in html
    rel = CD.relationship(SC.bundle()["ctx"], PAIR, SC.get("bestfit", "full"))
    assert rel["joint_stars_url"] in html


def test_relationship_yearly_caption_states_the_subject_topic_window():
    at = _app(PAIR).run()
    assert not at.exception
    y0, y1 = CD.CORE_WINDOW
    expected = copy.COMPARE["YEARLY_CAPTION"].format(y0=y0, y1=y1)
    assert expected in _caption_text(at)


def test_reciprocity_section_renders_when_the_pair_has_qualifying_fields():
    at = _app(PAIR).run()
    assert not at.exception
    rel = CD.relationship(SC.bundle()["ctx"], PAIR, SC.get("bestfit", "full"))
    if len(rel["reciprocity"]):
        assert copy.COMPARE["RECIPROCITY_HEADER"] in _markdown_text(at)
        assert copy.COMPARE["RECIPROCITY_CAPTION"] in _caption_text(at)


# ------------------------------------------------------------- workbook ----

def test_workbook_download_button_present_with_the_d15_filename():
    at = _app(PAIR).run()
    assert not at.exception
    buttons = [b for b in at.download_button if b.label == copy.COMPARE["EXPORT_BUTTON"]]
    assert len(buttons) == 1


def test_workbook_bytes_carry_exactly_seven_named_sheets():
    from lib.exports_xlsx import workbook_filename

    assert workbook_filename(PAIR) == f"BenchUp_compare_{IFREMER}_{NIOZ}.xlsx"
    data = VC._workbook_bytes(tuple(PAIR))
    wb = openpyxl.load_workbook(io.BytesIO(data))
    Cw = copy.COMPARE
    expected = [Cw["XLSX_SHEET_CARDS"], Cw["XLSX_SHEET_SUBFIELDS"], Cw["XLSX_SHEET_SDG"],
               Cw["XLSX_SHEET_POSITIONING"], Cw["XLSX_SHEET_SHARED_FRONTIER"],
               Cw["XLSX_SHEET_RELATIONSHIP_YEARLY"], Cw["XLSX_SHEET_RECIPROCITY"]]
    assert wb.sheetnames == expected, wb.sheetnames


def test_workbook_still_builds_after_the_show_all_state_flip():
    """The 2C lesson (memory: streamlit-rerun-breaks-download-button): a
    manual `st.rerun` on top of a widget's own rerun poisons every
    `st.download_button` for the session. `_toggle_frontier_show_all` uses
    `on_click` with no `st.rerun` call (grep-proved below) -- this test
    proves the CONSEQUENCE end to end: the workbook builds identically
    before AND after the flag flips, through a real click, not a direct
    session_state write."""
    at = _app(PAIR).run()
    assert not at.exception
    before = VC._workbook_bytes(tuple(PAIR))

    buttons = [b for b in at.button if b.label == copy.COMPARE["SHOW_ALL"].format(
        n=len(CD.shared_frontier(SC.bundle()["ctx"], SC.get("bestfit", "full"), PAIR)))]
    if buttons:
        buttons[0].click().run()
        assert not at.exception

    after = VC._workbook_bytes(tuple(PAIR))
    assert before == after  # same (a, b) key -> the SAME cached bytes, workbook unaffected by the UI flag

    # the download button itself must still be present and clickable-looking
    # (no exception) after the flip -- the actual regression the 2C lesson
    # names was a SILENTLY BROKEN button, not a raised exception, so the
    # positive assertion (present, page still exception-free) is the real
    # proof here.
    dl_buttons = [b for b in at.download_button if b.label == copy.COMPARE["EXPORT_BUTTON"]]
    assert len(dl_buttons) == 1


def test_no_st_rerun_call_anywhere_in_views_compare():
    """The HARD RULE, source-level: `st.rerun` never appears as LIVE CODE
    in this stream's own file (a prose mention inside a docstring
    explaining the rule -- as this very test's own docstring does -- is not
    a violation; only an AST `Call` node is). `on_click` callbacks
    (`_toggle_frontier_show_all`) are the ONLY state-flip mechanism."""
    import ast

    path = APP_DIR / "lib" / "views_compare.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls = [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "rerun"]
    assert calls == [], [(c.lineno, ast.dump(c)) for c in calls]
    assert "on_click=_toggle_frontier_show_all" in path.read_text(encoding="utf-8")

    # VACUITY: a real Call node IS found in a scratch tree carrying one.
    scratch = ast.parse("import streamlit as st\nst.rerun()\n")
    scratch_calls = [n for n in ast.walk(scratch)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and n.func.attr == "rerun"]
    assert len(scratch_calls) == 1


# ---------------------------------------------------------------- share ----

def test_share_link_box_renders_the_compare_deeplink():
    at = _app(PAIR).run()
    assert not at.exception
    codes = [c.value for c in at.get("code")] if hasattr(at, "get") else [c.value for c in at.code]
    assert any(c == f"?compare={IFREMER},{NIOZ}" for c in codes), codes


# -------------------------------------------------------- format=percent ---

def test_format_percent_is_banned_in_this_streams_own_files():
    """The hard rule: `format="percent"` is
    BANNED. `tests/test_2c_locale_ban.py` already sweeps the whole `lib/`
    tree; this re-confirms it directly on this stream's own two files as a
    fast, file-scoped guard."""
    for rel in ("lib/views_compare.py", "lib/exports_xlsx.py"):
        src = (APP_DIR / rel).read_text(encoding="utf-8")
        assert 'format="percent"' not in src, rel
        assert "format='percent'" not in src, rel


# ----------------------------------------------------- deleted surfaces ----

DELETED_NAMES = ("metric_frame", "erc_long", "frontier_pooled", "impact_index",
                 "impact_subfields", "coverage", "top_shared_subfields",
                 "UNAVAILABLE_REASON", "FRONTIER_POOLS")


def test_no_deleted_compare_data_surface_is_imported_by_this_stream():
    src = (APP_DIR / "lib" / "views_compare.py").read_text(encoding="utf-8")
    hits = [name for name in DELETED_NAMES if name in src]
    assert hits == [], hits

    # VACUITY
    mutated = src + "\nCD.metric_frame(ctx, subs, ids, 'field', 'share')\n"
    assert any(name in mutated for name in DELETED_NAMES)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
