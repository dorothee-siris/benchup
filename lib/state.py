"""
app/lib/state.py -- cross-page session state: PERSIST (the persistence kwarg
every keyed widget in this app must carry to survive a page switch) and the
seed handed from Find to Compare's first slot.

Lorraine lib/controls.py lines 184-222 (read verbatim before touching
this file): a widget's value resets to its coded default on every page switch
unless the widget itself is given `persist_state="session"` -- Streamlit's
per-page widget-id hashing means a plain session_state write-through does not
reliably reattach across more than one page hop.

 (BenchUp trim): the shortlist/compare-picker selection surface that
lived here (add/remove/items/clear/move/reorder/is_full behind a shared cap)
is retired along with the page it served -- Compare now reads two independent
search slots directly (`lib/selection.py:render_slots`), so there is nothing
left to hold a shared, ordered, capped list across pages. What remains is the
one thing Find still hands forward: which institution to pre-fill Compare's
first slot with.
"""
from __future__ import annotations

import streamlit as st

from lib.app_config import CFG

# Every keyed widget other streams build (tree, basis, depth, C1, L7,
# post-filters) must pass this as **PERSIST to survive a page switch:
# st.selectbox(., key="tree", **state.PERSIST).
PERSIST = dict(persist_state="session")

# Compare's own slot count is config-backed the same
# way as every other ruled number in this app (`config.yaml`'s `compare_cap`
# key); a config snapshot that predates that key falls back to this module
# constant instead of raising.
COMPARE_CAP: int = int(CFG.get("compare_cap", 3))


def ensure() -> None:
    """setdefault the two pieces of cross-page state this module owns. Call
    at the top of every page, before reading either one."""
    st.session_state.setdefault("find_seed", None)
    st.session_state.setdefault("slot_cleared", False)


def set_find_seed(iid: str | None) -> None:
    """Called by Find when a reader picks an institution to profile: the next
    Compare visit pre-fills its first slot with `iid`, unless that slot was
    explicitly cleared already this session (`lib/selection.py:render_slots`
    reads both this value and the `slot_cleared` flag)."""
    ensure()
    st.session_state["find_seed"] = iid


def get_find_seed() -> str | None:
    ensure()
    return st.session_state.get("find_seed")
