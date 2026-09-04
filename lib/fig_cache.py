"""
app/lib/fig_cache.py -- a small, bounded cache for built Plotly figures.

The heavy figures on Find (the two topic planes) and Compare (the
topic-overlap plane, the balance bars, the thematic/SDG bars, the
reciprocity scatter, the yearly domain stack) are rebuilt on EVERY
Streamlit rerun -- including a rerun triggered by an unrelated widget
elsewhere on the same page, and a page switch back to a view whose own
controls have not changed at all. This module caches each figure's own
JSON (`go.Figure.to_json()`) behind `st.cache_data`, keyed on (builder
name, every value that shapes that figure) -- NEVER on the DataFrame
itself: the caller's own zero-argument `build` closure re-derives whatever
it needs, itself already cheap because it closes over an already-fetched,
small frame (`topic_data`/`compare_data`'s own per-pair/per-institution
frame caches, `lib/views_find.py`'s `_topic_planes_frame`/`lib/
views_compare.py`'s `_pair_topics_frame` and siblings).

Why cache a JSON STRING, not the `go.Figure` object itself: `st.cache_data`
returns a stored value on a hit without re-running the decorated function's
body, but still copies the return value through its own serialisation path
on every call (hit or miss) so one caller can never mutate what another
caller reads back. A `go.Figure` is a heavier, more deeply-nested object to
copy that way; its own `.to_json()` string is a small, flat, trivially
copyable value, and `plotly.io.from_json` rebuilds an equivalent `go.Figure`
from it cheaply (a dict-to-object walk, not a redraw) on every call, hit or
miss.

`build` is a zero-argument callable (a small lambda closing over the
already-fetched frame and any names/slots the builder needs) -- its own
leading underscore in `_figure_json`'s signature is Streamlit's own
convention for a parameter EXCLUDED from hashing (the same mechanism this
app would use to pass an unhashable database connection into a cached
function): on a cache HIT `build` is never called at all, so its identity
never matters; on a MISS it runs once and its return value is discarded
right after `.to_json()`.
"""
from __future__ import annotations

from typing import Callable

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# <10 MB across the worst-case 16 entries (measured directly against the
# heaviest figures this app builds), 30 minutes.
FIG_CACHE_MAX_ENTRIES = 16
FIG_CACHE_TTL_S = 1800


@st.cache_data(show_spinner=False, max_entries=FIG_CACHE_MAX_ENTRIES, ttl=FIG_CACHE_TTL_S)
def _figure_json(name: str, key: tuple, _build: Callable[[], go.Figure]) -> str:
    """`name` + `key` are the cache identity: a short tag naming the
    builder (e.g. "fig_plane_impact", "reciprocity_scatter") plus every
    hashable control value that shapes the figure (ids, tree, mode, n,
    fwci_stat, tab, ...) -- never a DataFrame or a ctx dict. `_build` is
    excluded from hashing by its leading underscore (Streamlit's own
    convention) and called ONLY on a miss."""
    return _build().to_json()


def cached_figure(name: str, key: tuple, build: Callable[[], go.Figure]) -> go.Figure:
    """Returns the figure `build()` would construct: from the bounded JSON
    cache when (`name`, `key`) was already built within the last
    `FIG_CACHE_TTL_S` seconds (and is still among the `FIG_CACHE_MAX_
    ENTRIES` most recently used keys), otherwise builds it fresh via
    `build()` and caches the result. `key` must be a hashable tuple of
    plain values -- ids, tree, basis, mode, n, fwci_stat, tab, and the
    like -- the same "small hashable identity, ctx/frame fetched inside"
    convention this app's own `@st.cache_data` frame wrappers already use
    (`lib/views_find.py:_fields_frame`)."""
    return pio.from_json(_figure_json(name, key, build))
