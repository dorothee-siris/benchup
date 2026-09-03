"""
app/lib/selection.py -- query-param parsing, deep-link helpers, and the
Compare page's two search slots.

Compare is now two independent search slots
(same matcher Find uses), not a shared, ordered, capped list read by three
pages. `render_slots` replaces the old shared-list sidebar and the
list-only slot pickers built on it; the `?pair=` deep link and its `pair_from`
helper are retired along with the earlier standalone pair-view page that used them. The
`?compare=A,B` deep link stays -- `deeplink`/`share_link_block` own both ends
of that round trip, `resolve_slot_hydration` owns turning the URL value into
slot contents on first load.

Every function below `render_slots` up to it is plain Python -- no Streamlit
import, no CFG read, no data-file read -- except `read_query`, the ONE thin
wrapper that actually touches `st.query_params`; its import is LOCAL to that
function so the rest of this module stays importable and unit-testable with
no Streamlit runtime.

An id that the caller's `known_ids` does not recognise (a stale link, a
retired institution, a typo) is DROPPED, never raised on and never kept: a
shared link that names one bad id still opens on the rest, and the dropped
id is reported back so a caller can disclose it rather than fail silently.
"""
from __future__ import annotations


def parse_ids(value, known_ids) -> tuple[list[str], list[str]]:
    """`value` is a comma-joined string or an iterable of ids. Returns
    `(kept, dropped)`: `kept` is de-duplicated, first-seen order, filtered
    to `known_ids`; `dropped` is every id that failed that filter, same
    order. `None` or an empty string yields `([], [])`."""
    if not value:
        return [], []
    if isinstance(value, str):
        raw = [v.strip() for v in value.split(",")]
    else:
        raw = [str(v).strip() for v in value]
    known = set(known_ids)
    seen: set[str] = set()
    kept: list[str] = []
    dropped: list[str] = []
    for iid in raw:
        if not iid or iid in seen:
            continue
        seen.add(iid)
        (kept if iid in known else dropped).append(iid)
    return kept, dropped


def deeplink(kind: str, ids) -> str:
    """The query-string half of a shareable link: `deeplink("compare", [I1,
    I2])` -> `"?compare=I1,I2"`. The exact shape `parse_query` (via
    `read_query`) reads back -- this module owns both ends of the round trip."""
    return f"?{kind}=" + ",".join(ids)


def share_link_block(kind: str, ids, *, caption: str | None = None) -> None:
    """The share-link UI element at the foot of a page. A caller passes its
    own resolved picks (`None` entries included -- dropped here) and `kind`
    (only "compare" is live now). `caption` is the caller's own copy string.
    Renders nothing when no id survives."""
    import streamlit as st  # function-local by this module's own convention

    filled = [i for i in ids if i]
    if not filled:
        return
    if caption:
        st.caption(caption)
    st.code(deeplink(kind, filled), language=None)


# ============================================================================
# The Compare page's two search slots.
# ============================================================================

SEARCH_TOP_N = 10  # a SHORT hit list/dropdown, never every match -- relevance
                    # over raw recall; `lib/search.py`'s own token-ranked
                    # engine already returns its results in that order.

SLOT_EMPTY = ""  # sentinel "no pick" value for a slot -- every real
                  # institution_id in this app is an OpenAlex "I." string,
                  # so an empty string can never collide with one.

COMPARE_PARAM = "compare"  # the one slotted-view deep-link param left


def hit_label(hit: dict) -> str:
    """name. country (by NAME). type. size -- the one result-row label a
    slot's own search results use. `hit` is one dict from `lib.search.search`'s
    own return shape."""
    from lib import countries
    from lib.palette import NA_MARK

    total = hit.get("total_full_2020_2024")
    size = NA_MARK if total is None or total != total else f"{total:,.0f}"  # NaN != NaN
    return (f"{hit['display_name']} · {countries.name(str(hit['country_code']))} · "
           f"{hit['type']} · {size}")


def _slot_key(i: int) -> str:
    return f"compare_slot_{i}"


def _query_key(i: int) -> str:
    return f"compare_slot_query_{i}"


def _labels_key(i: int) -> str:
    return f"compare_slot_labels_{i}"


SLOT_HELP_TEMPLATE = "OpenAlex id: {iid}"  # kept inline rather than moved to
# copy.py (the widget's own `?` help,
# never a per-option one (Streamlit's selectbox carries one help string for
# the whole widget, not per row) -- the raw id stays available on request,
# never as the ON-SCREEN option text (see `_display_name` below).


def _display_name(iid: str) -> str:
    """Best-effort display name for an id a slot's own CURRENT search hits
    do not cover -- a slot hydrated from `?compare=` or seeded from Find's
    `state.set_find_seed` never ran a query, so it was never added to
    `labels` (`hit_label`'s own dict, built only from `hits` below), and
    `_fmt`'s old fallback (`_labels.get(iid, iid)`) printed the raw
    OpenAlex id verbatim.

    `lib.data_cache.index` is the single `@st.cache_resource`-backed
    institution table already aliased to the engine ctx's own `index_df`
    -- calling it here costs nothing beyond one boolean-mask row
    lookup, never a second file read. Falls back to the raw id only if it
    is somehow absent from the index (should not happen: every id a slot
    can hold was validated against `known_ids` before it got there)."""
    from lib.data_cache import index

    idx = index()
    if "display_name" not in idx.columns:  # a caller's own reduced/fake index
        return iid                          # (test fixtures included) -- degrade, never crash
    row = idx.loc[idx["institution_id"] == iid, "display_name"]
    return str(row.iloc[0]) if len(row) else iid


def resolve_slot_hydration(param_value, known_ids, n: int) -> list[str]:
    """The pure rule behind `render_slots`'s first-load hydration:
    `param_value` (a raw `?compare=` query value, or None) parsed and
    filtered against `known_ids` exactly like `parse_ids`, kept to the first
    `n`, and padded with SLOT_EMPTY -- exactly the list `render_slots` seeds
    each slot's session state to on a fresh session. An id `parse_ids` drops
    is dropped silently here too (no reader-facing report exists for that
    today); split out from `render_slots` so the hydration RULE is
    unit-testable with no Streamlit runtime."""
    kept, _ = parse_ids(param_value, known_ids)
    kept = kept[:n]
    return kept + [SLOT_EMPTY] * (n - len(kept))


def resolve_seed0(slot0: str, slot_cleared: bool, find_seed: str | None) -> str:
    """The slot-0 seeding rule (pure): given the just-hydrated value of slot
    0 (SLOT_EMPTY when `?compare=` named nothing there), whether the reader
    has cleared slot 0 already this session, and the current find_seed,
    returns what slot 0 should hold. A URL-supplied id always wins (a
    non-empty `slot0` is returned unchanged, `find_seed` is never consulted);
    otherwise `find_seed` fills the slot only when `slot_cleared` is False.
    Split out from `render_slots` so this one rule is unit-testable with
    plain values, no session_state or Streamlit runtime involved."""
    if slot0 != SLOT_EMPTY:
        return slot0
    if slot_cleared:
        return SLOT_EMPTY
    return find_seed if find_seed else SLOT_EMPTY


def _clear_slot(i: int) -> None:
    """on_click target for slot i's Clear button: empties that slot's pick
    (and, for slot 0 only, sets session_state["slot_cleared"] so
    `render_slots`'s own seeding rule never re-fills it again this session)
    with no `st.rerun` call -- a widget callback already triggers
    Streamlit's own rerun, and stacking a manual one on top of a
    session_state write is exactly what breaks a later widget on the same
    run (memory: streamlit-rerun-breaks-download-button)."""
    import streamlit as st

    st.session_state[_slot_key(i)] = SLOT_EMPTY
    if i == 0:
        st.session_state["slot_cleared"] = True


def render_slots(n: int, search) -> list[str | None]:
    """Renders `n` side-by-side search slots (`st.columns`) and returns the
    picked institution id per slot (`None` for an empty one). Each slot is a
    text input (keyed, `state.PERSIST`) feeding `search(query) -> list[hit]`
    a callable the CALLING PAGE passes, built the same way Find's own
    matcher is (`lib.search.build_search_index` + `lib.search.search`), kept
    as a parameter so this module stays free of that data-loading dependency
    a selectbox over the top hits as the pick control, and a Clear button.

    Deep-link hydration runs ONCE per session, on the first call: `?compare=`
    is parsed against the full institution index (`resolve_slot_hydration`)
    and becomes that first run's slot picks; every later run reads session
    state only, so a reader's own later edit is never fought by the URL.
    Slot 0 is then seeded from `state.get_find_seed` per `resolve_seed0`
    when the URL named nothing there. After every render, the resolved
    (non-empty) picks are written back to `?compare=`; an all-empty set of
    slots removes the param rather than writing an empty one.

    STREAMLIT TOUCHPOINT: session_state for a slot's own key is set directly,
    then that slot's selectbox is instantiated with `key=` alone (no
    `index=`) -- setting session_state for a key AND passing `index=`/`value=`
    on the SAME widget call is a Streamlit conflict; never add either kwarg
    to the selectbox call below without re-reading this note."""
    import streamlit as st

    from lib import copy, state

    hydrated_key = "_slots_hydrated_compare"
    if not st.session_state.get(hydrated_key):
        from lib.data_cache import index

        known_ids = set(index()["institution_id"])
        seeded = resolve_slot_hydration(st.query_params.get(COMPARE_PARAM), known_ids, n)
        if seeded:
            seeded[0] = resolve_seed0(seeded[0], st.session_state.get("slot_cleared", False),
                                      state.get_find_seed())
        for i in range(n):
            st.session_state[_slot_key(i)] = seeded[i]
        st.session_state[hydrated_key] = True

    cols = st.columns(n)
    picks: list[str | None] = []
    for i, col in enumerate(cols):
        labels = st.session_state.setdefault(_labels_key(i), {})
        with col:
            query = st.text_input(copy.FIND["SEED_SEARCH_LABEL"], key=_query_key(i), **state.PERSIST)
            hits = search(query)[:SEARCH_TOP_N] if query else []
            for hit in hits:
                labels[hit["id"]] = hit_label(hit)
            current = st.session_state.get(_slot_key(i), SLOT_EMPTY)
            options = [SLOT_EMPTY]
            for iid in (*([current] if current != SLOT_EMPTY else []), *[h["id"] for h in hits]):
                if iid not in options:
                    options.append(iid)
            if st.session_state.get(_slot_key(i)) not in options:
                st.session_state[_slot_key(i)] = SLOT_EMPTY

            def _fmt(iid: str, _labels=labels) -> str:
                if iid == SLOT_EMPTY:
                    return copy.FIND["SLOT_EMPTY_LABEL"]
                if iid not in _labels:
                    _labels[iid] = _display_name(iid)
                return _labels[iid]

            help_text = SLOT_HELP_TEMPLATE.format(iid=current) if current != SLOT_EMPTY else None
            pick = st.selectbox(copy.FIND["SLOT_LABEL"].format(n=i + 1), options,
                                format_func=_fmt, key=_slot_key(i), help=help_text)
            st.button("Clear", key=f"compare_slot_clear_{i}", on_click=_clear_slot, args=(i,))
        picks.append(None if pick == SLOT_EMPTY else pick)

    filled = [p for p in picks if p]
    if filled:
        st.query_params[COMPARE_PARAM] = ",".join(filled)
    elif COMPARE_PARAM in st.query_params:
        del st.query_params[COMPARE_PARAM]

    return picks
