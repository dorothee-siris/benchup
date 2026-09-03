"""
tests/test_selection.py -- (BenchUp trim): unit tests for
lib/state.py's cross-page seed handoff and lib/selection.py's query-param,
deep-link and slot helpers.

Run from cwd `app/`: python -m pytest tests/test_selection.py -q
"""
from __future__ import annotations

from lib import selection, state
from lib.selection import resolve_seed0, resolve_slot_hydration

KNOWN = {"A", "B", "C", "D", "E", "F", "G", "H"}


# ------------------------------------------------------------- state.py -----

def test_compare_cap_kept():
    """The old Compare hard cap survives (still config-backed) even though
    the shortlist it used to cap alongside is gone."""
    assert state.COMPARE_CAP == 3


def _fresh_state():
    """Resets the live st.session_state singleton. Works outside a running
    Streamlit script ("bare mode" -- a stderr warning, not an error,
    confirmed against this Streamlit build): state.py's own functions
    read/write nothing but this same singleton, so no mock is needed to
    unit-test them directly."""
    import streamlit as st

    st.session_state.clear()


def test_ensure_sets_defaults():
    _fresh_state()
    state.ensure()
    import streamlit as st

    assert st.session_state["find_seed"] is None
    assert st.session_state["slot_cleared"] is False


def test_set_and_get_find_seed():
    _fresh_state()
    assert state.get_find_seed() is None  # ensure's own default, lazily
    state.set_find_seed("I154202486")
    assert state.get_find_seed() == "I154202486"
    state.set_find_seed(None)
    assert state.get_find_seed() is None


# --------------------------------------------------------- selection.py -----

def test_parse_ids_comma_string():
    kept, dropped = selection.parse_ids("A,B,C", KNOWN)
    assert kept == ["A", "B", "C"]
    assert dropped == []


def test_parse_ids_list_input():
    kept, dropped = selection.parse_ids(["A", "B"], KNOWN)
    assert kept == ["A", "B"]


def test_parse_ids_deduplicates_first_seen_order():
    kept, _ = selection.parse_ids("A,B,A,C,B", KNOWN)
    assert kept == ["A", "B", "C"]


def test_parse_ids_drops_unknown_and_reports_them():
    kept, dropped = selection.parse_ids("A,X,B,Y", KNOWN)
    assert kept == ["A", "B"]
    assert dropped == ["X", "Y"]


def test_parse_ids_empty_and_none():
    assert selection.parse_ids(None, KNOWN) == ([], [])
    assert selection.parse_ids("", KNOWN) == ([], [])


def test_parse_query_compare_only_pair_is_gone():
    """`?pair=` is retired along with the page that used it -- parse_query's
    return shape no longer carries a "pair" key at all."""
    out = selection.parse_query({"compare": "A,B,C"}, KNOWN)
    assert out == {"compare": ["A", "B", "C"], "dropped": []}
    assert "pair" not in out


def test_parse_query_drops_and_reports_unknown():
    out = selection.parse_query({"compare": "A,X,B,Y"}, KNOWN)
    assert out["compare"] == ["A", "B"]
    assert out["dropped"] == ["X", "Y"]


def test_parse_query_missing_key_is_empty():
    out = selection.parse_query({}, KNOWN)
    assert out == {"compare": [], "dropped": []}


def test_compare_ids_query_wins_then_shortlist_fills_capped():
    shortlist = ["D", "E", "F", "G"]
    query = "A,B"
    out = selection.compare_ids(shortlist, query, KNOWN, cap=3)
    assert out == ["A", "B", "D"]  # query first, shortlist fills the remaining slot, capped


def test_compare_ids_dedupes_across_query_and_shortlist():
    out = selection.compare_ids(["A", "B"], "B,C", KNOWN, cap=6)
    assert out == ["B", "C", "A"]


def test_compare_ids_drops_unknown_from_either_side():
    out = selection.compare_ids(["A", "ZZZ"], "YYY,B", KNOWN, cap=6)
    assert out == ["B", "A"]


# --------------------------------------------------- compare_ids_capped -----

def test_compare_ids_capped_query_wins_then_shortlist_fills_and_reports_cut():
    """4 candidates (A,B from query; D,E,F,G from the shortlist) = 6
    combined, capped at 3 -- 3 are cut (E, F, G)."""
    shortlist = ["D", "E", "F", "G"]
    query = "A,B"
    out, n_truncated = selection.compare_ids_capped(shortlist, query, KNOWN, cap=3)
    assert out == ["A", "B", "D"]
    assert n_truncated == 3


def test_compare_ids_capped_dedupes_no_truncation():
    out, n_truncated = selection.compare_ids_capped(["A", "B"], "B,C", KNOWN, cap=6)
    assert out == ["B", "C", "A"]
    assert n_truncated == 0


def test_compare_ids_capped_drops_unknown_from_either_side():
    out, n_truncated = selection.compare_ids_capped(["A", "ZZZ"], "YYY,B", KNOWN, cap=6)
    assert out == ["B", "A"]
    assert n_truncated == 0


def test_compare_ids_capped_truncation_count_at_the_hard_cap():
    """5 known candidates capped at state.COMPARE_CAP (3) reports
    n_truncated == 2, surviving ids in query-then-shortlist order."""
    out, n_truncated = selection.compare_ids_capped(["C", "D", "E"], "A,B", KNOWN, cap=state.COMPARE_CAP)
    assert out == ["A", "B", "C"]
    assert n_truncated == 2


def test_compare_ids_capped_matches_compare_ids_ids_half():
    """compare_ids_capped's `ids` half is byte-identical to compare_ids on
    the same inputs -- one function is not quietly a different resolution
    order from the other."""
    shortlist, query = ["D", "E", "F"], "A,B"
    plain = selection.compare_ids(shortlist, query, KNOWN, cap=3)
    capped_ids, _ = selection.compare_ids_capped(shortlist, query, KNOWN, cap=3)
    assert plain == capped_ids


def test_pair_from_is_gone():
    """Retired with the `?pair=` deep link and the page that used it."""
    assert not hasattr(selection, "pair_from")


def test_render_sidebar_and_slots_row_are_gone():
    """The deprecated `render_sidebar`/`slots_row` shims (kept only so
    lib/views_find.py / lib/views_compare.py could import during their own
    waves) are DELETED now that both streams call `render_slots` directly."""
    assert not hasattr(selection, "render_sidebar")
    assert not hasattr(selection, "slots_row")


def test_deeplink_round_trips_through_parse_query():
    link = selection.deeplink("compare", ["A", "B", "C"])
    assert link == "?compare=A,B,C"
    qs = link.lstrip("?")
    key, value = qs.split("=", 1)
    out = selection.parse_query({key: value}, KNOWN)
    assert out["compare"] == ["A", "B", "C"]


# ------------------------------------------------- slot hydration (pure) ----

def test_resolve_slot_hydration_parses_and_pads():
    out = resolve_slot_hydration("A,B", KNOWN, 3)
    assert out == ["A", "B", selection.SLOT_EMPTY]


def test_resolve_slot_hydration_truncates_to_n():
    out = resolve_slot_hydration("A,B,C,D", KNOWN, 2)
    assert out == ["A", "B"]


def test_resolve_slot_hydration_drops_unknown_ids():
    out = resolve_slot_hydration("A,ZZZ,B", KNOWN, 3)
    assert out == ["A", "B", selection.SLOT_EMPTY]


def test_resolve_slot_hydration_none_value_is_all_empty():
    assert resolve_slot_hydration(None, KNOWN, 2) == [selection.SLOT_EMPTY] * 2


# --------------------------------------------------- slot-0 seeding (pure)
# The rule render_slots applies to its first slot only, factored out as a
# plain function of (hydrated slot-0 value, slot_cleared flag, find_seed) so
# it is testable with no session_state or Streamlit runtime at all.

def test_resolve_seed0_url_wins_over_find_seed():
    assert resolve_seed0("A", False, "Z") == "A"  # URL already filled slot 0


def test_resolve_seed0_fills_from_find_seed_when_empty_and_not_cleared():
    assert resolve_seed0(selection.SLOT_EMPTY, False, "Z") == "Z"


def test_resolve_seed0_stays_empty_when_cleared_even_with_a_find_seed():
    assert resolve_seed0(selection.SLOT_EMPTY, True, "Z") == selection.SLOT_EMPTY


def test_resolve_seed0_stays_empty_with_no_find_seed():
    assert resolve_seed0(selection.SLOT_EMPTY, False, None) == selection.SLOT_EMPTY


# ------------------------------------------------- render_slots end to end
# AppTest.from_function execs the function body in an isolated temp script
# module-level names in THIS file are not visible inside it, so every helper
# a test app needs (a fake `search`, a hit dict) is defined INSIDE `_app`.

def test_render_slots_hydrates_from_url_and_persists_across_rerun():
    """render_slots end to end (AppTest.from_function, no real page needed):
    first run with `?compare=A,B` hydrates both slots; a second.run with
    no query params must NOT re-hydrate (the session flag guards it) -- the
    slots stay exactly where the reader last left them."""
    from streamlit.testing.v1 import AppTest

    def _app():
        import streamlit as st

        from lib import selection, state

        state.ensure()
        picks = selection.render_slots(3, lambda q: [])
        st.session_state["_picks_seen"] = picks

    at = AppTest.from_function(_app, default_timeout=60)
    # Patch lib.data_cache.index for known_ids without a real data file.
    import pandas as pd

    from lib import data_cache

    original_index = data_cache.index
    data_cache.index = lambda: pd.DataFrame({"institution_id": ["A", "B", "C"]})
    try:
        at.query_params["compare"] = "A,B"
        at.run()
        assert not at.exception, [str(e) for e in at.exception]
        assert at.session_state["_picks_seen"] == ["A", "B", None]
        assert at.query_params["compare"] == ["A,B"]

        at.run()  # second run, no new query params -- must not re-hydrate
        assert not at.exception, [str(e) for e in at.exception]
        assert at.session_state["_picks_seen"] == ["A", "B", None]
    finally:
        data_cache.index = original_index


def test_render_slots_clear_empties_the_slot_with_no_rerun_crash():
    from streamlit.testing.v1 import AppTest

    def _app():
        import streamlit as st

        from lib import selection, state

        state.ensure()
        picks = selection.render_slots(2, lambda q: [])
        st.session_state["_picks_seen"] = picks

    at = AppTest.from_function(_app, default_timeout=60)
    import pandas as pd

    from lib import data_cache

    original_index = data_cache.index
    data_cache.index = lambda: pd.DataFrame({"institution_id": ["A", "B"]})
    try:
        at.query_params["compare"] = "A,B"
        at.run()
        assert not at.exception, [str(e) for e in at.exception]
        assert at.session_state["_picks_seen"] == ["A", "B"]

        clear0 = next(b for b in at.button if b.key == "compare_slot_clear_0")
        clear0.click().run()
        assert not at.exception, [str(e) for e in at.exception]
        assert at.session_state["_picks_seen"][0] is None
        assert at.session_state["slot_cleared"] is True
        # the other slot is untouched by clearing slot 0
        assert at.session_state["_picks_seen"][1] == "B"
    finally:
        data_cache.index = original_index


def test_render_slots_seeds_slot0_from_find_seed_when_url_empty():
    from streamlit.testing.v1 import AppTest

    def _app():
        import streamlit as st

        from lib import selection, state

        state.ensure()
        state.set_find_seed("A")
        picks = selection.render_slots(2, lambda q: [])
        st.session_state["_picks_seen"] = picks

    at = AppTest.from_function(_app, default_timeout=60)
    import pandas as pd

    from lib import data_cache

    original_index = data_cache.index
    data_cache.index = lambda: pd.DataFrame({"institution_id": ["A", "B"]})
    try:
        at.run()  # no ?compare= at all
        assert not at.exception, [str(e) for e in at.exception]
        assert at.session_state["_picks_seen"] == ["A", None]
    finally:
        data_cache.index = original_index


def test_render_slots_pick_from_search_hits():
    """A query that matches feeds real hits into the pick control; selecting
    one becomes that slot's returned pick -- proves the `search` callable
    contract end to end, not just the hydration/clear paths above."""
    from streamlit.testing.v1 import AppTest

    def _app():
        import streamlit as st

        from lib import selection, state

        def _search(query: str):
            if query != "IFP":
                return []
            return [{"id": "Z", "display_name": "IFPEN", "country_code": "fr",
                     "type": "education", "total_full_2020_2024": 100.0}]

        state.ensure()
        picks = selection.render_slots(2, _search)
        st.session_state["_picks_seen"] = picks

    at = AppTest.from_function(_app, default_timeout=60)
    import pandas as pd

    from lib import data_cache

    original_index = data_cache.index
    data_cache.index = lambda: pd.DataFrame({"institution_id": ["A", "B", "Z"]})
    try:
        at.run()
        assert not at.exception, [str(e) for e in at.exception]
        assert at.session_state["_picks_seen"] == [None, None]

        at.text_input(key="compare_slot_query_1").set_value("IFP").run()
        assert not at.exception, [str(e) for e in at.exception]
        slot1 = at.selectbox(key="compare_slot_1")
        # .options carries FORMATTED labels (format_func applied), not raw ids
        assert any(o.startswith("IFPEN") for o in slot1.options), slot1.options

        hit_index = next(i for i, o in enumerate(slot1.options) if o.startswith("IFPEN"))
        slot1.select_index(hit_index).run()
        assert not at.exception, [str(e) for e in at.exception]
        assert at.session_state["_picks_seen"] == [None, "Z"]
    finally:
        data_cache.index = original_index
