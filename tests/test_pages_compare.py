"""
tests/test_pages_compare.py -- AppTest
page-render tests for `pages/2_(scales)_Compare.py` and the render helpers
in `lib/views_compare.py`.

REWRITTEN END TO END. The earlier page
offered an N-institution "Compare by" metric-selector matrix, ERC panels,
field-grain dynamics, a pooled frontier scatter, coverage and impact-by-
subfield -- every one of those sections, and the frame builders behind them,
is DELETED. Compare is fixed at EXACTLY two institutions (two search
slots, `lib.selection.render_slots`) -- there is no N=3 case to test any
more, and no sidebar-shortlist premise (`lib.selection.render_sidebar`/
`slots_row` are gone -- see
this file's own final section).

Page order under test: Key figures -> Thematic shape (Profile/Impact
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
import re
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

IFREMER = "I154202486"      # the golden anchor pair (also the
NIOZ = "I4210107283"        # Playwright render target)
PAIR = [IFREMER, NIOZ]

SECTION_HEADER_KEYS = ("CARDS_HEADER", "SHAPE_HEADER", "SDG_HEADER", "FRONTIER_HEADER",
                       "SHARED_FRONTIER_HEADER", "RELATIONSHIP_HEADER")


def _app(ids=None, **extra_state) -> AppTest:
    """Institutions are seeded through `?compare=`, the SAME hydration path
    `lib.selection.render_slots` reads on a fresh session."""
    at = AppTest.from_file(COMPARE_PAGE, default_timeout=300)
    if ids:
        at.query_params["compare"] = ",".join(ids)
    for k, v in extra_state.items():
        at.session_state[k] = v
    return at


def _markdown_text(at) -> str:
    """Every rendered markdown block, joined -- captions/notes are
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

def test_key_figure_cards_render_nine_tiles_per_institution_plus_three_relationship_tiles():
    at = _app(PAIR).run()
    assert not at.exception
    html = _markdown_text(at)
    n_tiles = html.count('class="benchup-kpi"')
    # 8 single-value cards + 1 co-pub tile, x 2 institutions (18), plus D27's
    # three relationship tiles (Joint publications, Joint star papers,
    # Momentum) in their own row, one apiece.
    assert n_tiles == 21, n_tiles


def _tooltip_spec() -> dict:
    import yaml

    with open(APP_DIR / "docs" / "tooltip_spec.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("card_col,tip_key,tile_key", [
    ("vol_full", "CARD_PUBLICATIONS_TIP", "compare_card_publications"),
    ("vol_change", "CARD_VOL_CHANGE_TIP", "compare_card_vol_change"),
    ("fwci_eu_mean", "CARD_FWCI_TIP", "compare_card_fwci_eu"),
    ("pp", "CARD_PP10_TIP", "compare_card_pp10"),
    ("star_share", "CARD_STARS_TIP", "compare_card_stars"),
    ("n_topics_led_fair", "CARD_TOPICS_LED_TIP", "compare_card_topics_led"),
    ("frontier_top25_share", "CARD_FRONTIER_TIP", "compare_card_frontier_share"),
    ("sdg_share", "CARD_SDG_TIP", "compare_card_sdg_share"),
])
def test_card_tip_placeholders_match_the_tooltip_spec(card_col, tip_key, tile_key):
    """Every `compare_card_*` tile's help_lines name a set of `{placeholder}`
    tokens (`{eu_median}`, `{n}`, `{median}`, .); every one of those must
    appear, verbatim, in this card's OWN `copy.COMPARE` tip template -- the
    window itself is spelled `{y0}`/`{y1}`/`{whole_y1}` here rather than the
    spec's own literal digits, the one substitution every tip already made."""
    spec = _tooltip_spec()
    help_lines = " ".join(spec["tiles"][tile_key]["help_lines"])
    spec_placeholders = set(re.findall(r"\{(\w+)\}", help_lines))
    tip = copy.COMPARE[tip_key]
    tip_placeholders = set(re.findall(r"\{(\w+)\}", tip))
    assert spec_placeholders <= (tip_placeholders | {"y0", "y1", "whole_y1"}), (
        card_col, spec_placeholders - tip_placeholders)


def test_card_fwci_tip_carries_the_spec_distinctive_phrases():
    """`compare_card_fwci_eu`'s own reasoning sentences, copied verbatim
    (D23's four-line "?": n covered, median, PP10_WD, European median of
    the mean)."""
    tip = copy.COMPARE["CARD_FWCI_TIP"]
    assert "covered works" in tip
    assert "keeps the highly-cited tail the median discards" in tip
    assert "world-referenced reading of impact" in tip
    assert "European median of the mean" in tip


def test_card_topics_led_tip_states_the_world_top_twenty_all_institution_types():
    tip = copy.COMPARE["CARD_TOPICS_LED_TIP"]
    assert "world top twenty" in tip
    assert "publication volume" in tip
    assert "every institution type" in tip


def test_card_fwci_value_equals_index_fwci_eu_mean():
    """D23: the FWCI card's own displayed value moved to the mean."""
    at = _app(PAIR).run()
    assert not at.exception
    ctx = SC.bundle()["ctx"]
    row = ctx["index_by_id"].loc[IFREMER]
    from lib.charts_compare import _fmt_si

    want = _fmt_si(row["fwci_eu_mean"])
    html = _markdown_text(at)
    assert want in html, (want, "fwci_eu_mean not found on the rendered page")


def test_at_least_one_card_carries_the_leader_dot():
    at = _app(PAIR).run()
    assert not at.exception
    html = _markdown_text(at)
    assert X.best_value_dot(0) in html or X.best_value_dot(1) in html


# ---------------------------------------------------------------- tabs -----

def test_shape_and_sdg_sections_each_offer_profile_and_impact_tabs():
    """Bar-layout contract (D28/C3): the SDG section is now PROFILE ONLY --
    no tab strip at all -- so only the Thematic-shape section's own pair of
    tabs remains; both label counts drop from 2 to 1."""
    at = _app(PAIR).run()
    assert not at.exception
    labels = [t.label for t in at.tabs]
    assert labels.count(copy.COMPARE["TAB_PROFILE"]) == 1
    assert labels.count(copy.COMPARE["TAB_IMPACT"]) == 1


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


def test_relationship_three_tiles_render_with_their_own_values():
    """D27: Joint publications == core_total, Joint star papers == pair_stars
    (0 when absent), Momentum == momentum_display's own text -- all three in
    one row, none of them carrying a leader dot (there is no "higher wins"
    reading across three unrelated measures)."""
    at = _app(PAIR).run()
    assert not at.exception
    html = _markdown_text(at)
    Cw = copy.COMPARE
    for label in (Cw["TILE_JOINT_PUBLICATIONS"], Cw["TILE_JOINT_STARS"], Cw["TILE_MOMENTUM"]):
        assert label in html

    from lib.charts_compare import _fmt_vol as _cnt

    rel = CD.relationship(SC.bundle()["ctx"], PAIR, SC.get("bestfit", "full"))
    assert _cnt(rel["core_total"]) in html
    assert _cnt(rel.get("joint_stars") or 0) in html
    assert rel["momentum"]["text"] in html
    assert rel["momentum"]["glyph"] in html


def test_momentum_evidence_line_renders_for_the_anchor_pair():
    """D27's always-visible evidence sentence -- filled from the SAME pair
    the momentum tile itself reads, present on the page regardless of
    which state the anchor pair happens to land in."""
    at = _app(PAIR).run()
    assert not at.exception
    from lib import collab_data as COL
    from lib.views_compare import _momentum_evidence_line

    ctx = SC.bundle()["ctx"]
    rel = CD.relationship(ctx, PAIR, SC.get("bestfit", "full"))
    facts = COL._load_collab_facts(ctx)
    line = _momentum_evidence_line(rel["momentum"], facts)
    assert line in _markdown_text(at)
    assert "joint article" in line  # this anchor pair is "stable" -- its own sentence names the figures


FACTS = {"band": 0.25, "alpha": 0.05, "new_min_c2": 5, "dormant_min_c1": 5, "weak_base_max": 4}


@pytest.mark.parametrize("mom,expected_state,expected_sig", [
    ({"c1": 0.0, "c2": 7.0}, "new", None),
    ({"c1": 0.0, "c2": 3.0}, "thin_ns", None),
    ({"c1": 6.0, "c2": 0.0}, "dormant", None),
    ({"c1": 2.0, "c2": 5.0}, "thin", None),
    ({"c1": 30.0, "c2": 30.0, "mom_rr": 0.9706419110298157, "mom_p": None}, "numeric", "stable_band"),
    ({"c1": 30.0, "c2": 30.0, "mom_rr": 1.5, "mom_p": 0.01}, "numeric", "significant"),
    ({"c1": 30.0, "c2": 30.0, "mom_rr": 0.5, "mom_p": 0.40}, "numeric", "not_significant"),
])
def test_momentum_evidence_line_covers_every_state(mom, expected_state, expected_sig):
    """One example per state `collab_data.momentum_evidence` can return
    (the never-co-published case is handled entirely separately, by
    `_render_relationship`'s own early return on `rel["momentum"] is None`,
    and is covered by `test_relationship_no_collaboration_pair_returns_
    none_momentum_and_pulse` in tests/test_compare_data.py)."""
    from lib import collab_data as COL
    from lib.views_compare import _momentum_evidence_line

    ev = COL.momentum_evidence(mom, FACTS)
    assert ev["state"] == expected_state
    if expected_sig:
        assert ev["sig"] == expected_sig
    line = _momentum_evidence_line(mom, FACTS)
    assert line and isinstance(line, str)
    if expected_state == "new":
        assert "No joint articles or reviews" in line
    elif expected_state == "thin_ns":
        assert line == "The base is too thin for a significance test."
    elif expected_state == "dormant":
        assert "none since" in line
    elif expected_state == "thin":
        assert "too thin a base for a rate" in line
    elif expected_sig == "stable_band":
        assert "\N{PLUS-MINUS SIGN}25 % band" in line and "no direction is called" in line
        assert ": \N{MINUS SIGN}3 % once" in line
    else:
        assert "once both institutions' own growth is taken out" in line
        assert ": " in line and " - " not in line  # the colon separator, never the old dash


def test_yearly_stack_height_is_500px():
    from lib.charts_compare import YEARLY_STACK_HEIGHT_PX

    assert YEARLY_STACK_HEIGHT_PX == 500


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
    """A known lesson (memory: streamlit-rerun-breaks-download-button): a
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
    # (no exception) after the flip -- the actual regression named above
    # was a SILENTLY BROKEN button, not a raised exception, so the
    # positive assertion (present, page still exception-free) is the real
    # proof here.
    dl_buttons = [b for b in at.download_button if b.label == copy.COMPARE["EXPORT_BUTTON"]]
    assert len(dl_buttons) == 1


def test_no_st_rerun_call_anywhere_in_views_compare():
    """The HARD RULE, source-level: `st.rerun` never appears as LIVE CODE
    in this file (a prose mention inside a docstring
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
    tree; this re-confirms it directly on these two files as a
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
