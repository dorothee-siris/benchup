"""
app/lib/engine/scenario_cache.py -- process-wide resident cache for the
engine context and ONE (tree, basis) scenario substrate dict.

`bundle` is `views_find.py:_bundle` moved verbatim in RESULT (same 11
keys, same values) -- the population-wide context plus the search index,
umbrella flags/medians, catch-all shares, normalised names for the tail
search, the domain-id -> name map, and the lightweight per-institution
`lite` dict `lib/filters.py:apply_filters` reads. `views_find.py` keeps its
own copy for now; this module is the ONE will import from at
merge, per 's file-ownership table and the manager's wave-2
dispatch note.

D11 "one copy of each table" -- the ONE deliberate deviation from a literal
line-for-line port: the original `_bundle` called `lib.data_cache.index`
and `lib.data_cache.topics_dim` as two SEPARATE reads of files `load_context`
below ALSO reads (`index.parquet` in full; `topics_dim.parquet` as the
`TOPICS_DIM_COLS` subset). Reading `index.parquet` twice was exactly the
kind of duplication D11 forbids, so this version takes `idx` and the two
`topics_dim` columns it needs (`domain_id`, `domain_name`, `field_id` -- both
present in `ctx["topics_dim_df"]`'s column subset) FROM `ctx` instead of
calling back into `lib.data_cache` -- proven value-identical to the old
`index`/`topics_dim` calls with `pd.testing.assert_frame_equal` in
`tests/test_ram_budget.py`. This also keeps the import graph one-directional:
`lib.data_cache` imports `lib.engine.scenario_cache` (to alias its own
loaders onto this module's `bundle["ctx"]`, D11 task 2) and NEVER the
other way -- `lib.engine` imports nothing from `lib.data_cache`, anywhere.

`get(tree, basis)` replaces `views_find.py:_subs` (which cached THREE
scenarios via `@st.cache_resource(max_entries=3)` around the whole-scenario
assembly function `load_substrates` now replaces): ONE scenario resident at a time
(`max_entries=int(os.environ.get("BENCHUP_SCENARIO_ENTRIES", "1"))`, so the
permanent stress harness can run its broken-control
at a higher entry count without a code change) around `load_substrates`. Streamlit's own
`cache_resource` already de-duplicates concurrent calls for the SAME
(tree, basis) key (one build, every waiting caller gets the result) -- the
module-level `_LOAD_LOCK` below is for the OTHER case D11 calls out: two
sessions requesting DIFFERENT scenarios at the same moment. Without the
lock both would build (and briefly hold) their own multi-hundred-MB
substrate dict concurrently; the lock serialises the two builds so only one
extra scenario is ever under construction at once, which is what keeps the
3-session worst case under D11's 1.8 GB ceiling.

Tree/basis-invariant blocks (D11 architecture note, "loaded once and
shared, not re-read per scenario"): nothing to do here -- `substrates.py`
already caches them at ITS OWN module level (`_TOPIC_SHARE_CACHE` keyed by
basis for l3/f1, `_COMMON_CACHE` unconditionally for l4-l7), independent of
whatever wraps `load_substrates`. Confirmed by reading `substrates.py`
before writing this module.
"""
from __future__ import annotations

import gc
import os
import threading
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from lib import baselines
from lib.badges import umbrella_flags, umbrella_medians
from lib.engine import catchall_811_share, load_context, load_substrates
from lib.search import build_search_index, normalize

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Same two co-publication columns `views_find.py` promotes to cards
#  copied here because `_extra_baselines` (below) is the
# function that builds their baseline entry, and it moved with `_bundle`.
INTL_COLUMN = "intl_share"
COMPANY_COLUMN = "company_share"

# D11: only ONE scenario dict resident at a time in normal operation. The
# stress harness's broken-control run overrides this via the environment
#  to reproduce the pre-fix crash path.
_SCENARIO_ENTRIES = int(os.environ.get("BENCHUP_SCENARIO_ENTRIES", "1"))

# Serialises scenario BUILDS across different (tree, basis) keys -- see the
# module docstring. `st.cache_resource` already handles the same-key case.
_LOAD_LOCK = threading.Lock()

# D12 concurrency fix: the last (tree, basis) `get()` actually built, guarded
# by `_LOAD_LOCK` -- lets `get()` tell "same scenario, cache hit" from
# "different scenario, about to swap" BEFORE calling through to the
# `st.cache_resource`-wrapped builder, so it can evict the old entry first.
_LAST_SCENARIO_KEY: tuple[str, str] | None = None


# ------------------------------------------------------------- bundle -----

def _extra_baselines(bl: dict, index_df: pd.DataFrame) -> dict:
    """Ported from `views_find.py:_extra_baselines` verbatim: the two
    promoted co-publication measures, given the SAME baseline
    entry shape `lib/baselines.py` builds for its own eight -- sorted
    non-null values, median, n -- so `baselines.stats`/`baselines.percentile`
    read them through their public interface without knowing they came from
    here."""
    for column in (INTL_COLUMN, COMPANY_COLUMN):
        values = (index_df[column].astype("float64").dropna()
                  if column in index_df.columns
                  else pd.Series(dtype="float64"))
        bl[column] = {"sorted": np.sort(values.to_numpy()),
                      "median": float(values.median()) if len(values) else float("nan"),
                      "n": int(len(values))}
    return bl


@st.cache_resource(show_spinner=False)
def bundle() -> dict:
    """Everything computed once per process: the engine context plus the
    search index, umbrella flags/medians, catch-all shares, normalised
    names for the tail search, the domain-id -> name map the yearly
    breakdown needs, and the lightweight per-institution dict the
    post-filters run over (`lite` -- four keys, exactly what
    `filters.apply_filters` reads). See the module docstring for the one
    value-identical deviation from the original `views_find._bundle`."""
    ctx = load_context(str(DATA_DIR))
    idx = ctx["index_df"]
    td = ctx["topics_dim_df"]
    lite = {r.institution_id: {"institution_id": r.institution_id, "type": str(r.type),
                               "country_code": str(r.country_code),
                               "total_full_2020_2024": (None if pd.isna(r.total_full_2020_2024)
                                                        else float(r.total_full_2020_2024))}
            for r in idx.itertuples(index=False)}
    # R2/L31: the KPI baselines are one pass over the whole index, so they are
    # built HERE (inside the process-wide cache_resource) rather than per rerun.
    # `bonus_year_full` is the one DERIVED KPI -- `baselines.KPI_COLUMNS` holds
    # its parser, so the per-institution bonus-year count is read through the
    # same public spec the median is computed from, never re-parsed here.
    bonus_spec = baselines.KPI_COLUMNS["bonus_year_full"]
    bonus = bonus_spec(idx) if callable(bonus_spec) else idx[bonus_spec]
    return {"ctx": ctx, "index_df": idx, "lite": lite,
            "baselines": _extra_baselines(baselines.build(idx), idx),
            "bonus_year_full": dict(zip(idx["institution_id"], bonus)),
            "search_idx": build_search_index(idx),
            "flags": umbrella_flags(idx), "medians": umbrella_medians(idx),
            "catchall": catchall_811_share(ctx),
            "norm_names": {i: normalize(n)
                           for i, n in zip(idx["institution_id"], idx["display_name"])},
            "domain_names": dict(zip(td["domain_id"], td["domain_name"])),
            "n_fields": int(td["field_id"].nunique())}


# --------------------------------------------------------------- get ------

@st.cache_resource(max_entries=_SCENARIO_ENTRIES, show_spinner=False)
def _get_cached(tree: str, basis: str) -> dict:
    return load_substrates(bundle()["ctx"], tree, basis)


def get(tree: str, basis: str) -> dict:
    """The ONE resident (tree, basis) scenario's substrates (D11). Bounded
    by `BENCHUP_SCENARIO_ENTRIES` (default 1): switching scenario evicts the
    previous dict from Streamlit's cache (LRU) rather than accumulating a
    second one, which is what `tests/test_scenario_cycle` proves end to end.

    EVICT-BEFORE-BUILD (D12 concurrency fix, stress phase B,
    STRESS_2026-09-03_1302.md): `st.cache_resource`'s own LRU eviction only
    fires AFTER the decorated function returns a NEW entry -- a plain
    `@st.cache_resource(max_entries=1)` wrapped straight around
    `load_substrates` therefore builds the NEW multi-hundred-MB scenario
    dict while the OLD one is still cached and reachable, briefly holding
    BOTH resident at once. Measured in a bare-process 3-thread reproduction
    of phase B's random Find-page tree/basis toggling: this roughly doubled
    the concurrent RSS delta over the same run without scenario swaps
    (~484 MB -> ~988 MB above baseline). When the requested key differs from
    the last one this process actually built (`_LAST_SCENARIO_KEY`, only
    meaningful while `BENCHUP_SCENARIO_ENTRIES` is left at its default 1 --
    the stress harness's own broken-control override deliberately keeps the
    old, unfixed double-residency behavior for comparison runs),
    `_get_cached.clear()` evicts the old entry and `gc.collect()`s BEFORE
    calling through to the cache-wrapped builder, so only one scenario dict
    is ever resident at a time -- never two. Everything here runs under
    `_LOAD_LOCK` (see module docstring: also the lock that keeps two
    DIFFERENT concurrent scenario requests from building at once), so a
    concurrent request for the SAME key already resident simply blocks and
    then gets the cache hit, paying no clear/collect. ponytail: no argument
    validation here -- `load_substrates` already raises a clear
    `FileNotFoundError` for an unknown (tree, basis) pair via its own
    `_scenarios_dir` lookup; duplicating that check would just be a second
    place for the two to drift."""
    global _LAST_SCENARIO_KEY
    key = (tree, basis)
    with _LOAD_LOCK:
        if _SCENARIO_ENTRIES == 1 and _LAST_SCENARIO_KEY is not None and _LAST_SCENARIO_KEY != key:
            _get_cached.clear()
            gc.collect()
        _LAST_SCENARIO_KEY = key
        return _get_cached(tree, basis)
