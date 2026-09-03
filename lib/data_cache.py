"""
Centralized data loading with Streamlit caching (adapted from Lorraine
Streamlit/lib/data_cache.py). Every path is __file__-relative, so the app runs
identically regardless of the launch cwd. `@st.cache_resource` loads each table once
and shares it across pages/reruns for the life of the process.

topics_all.parquet is 533 MB, mostly object-string columns not needed by the app's
substrate builders -- topics_all_slim reads only the four
columns the engine actually consumes, so the full frame is never materialized here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from lib.engine import scenario_cache as _SC

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# D11 "one copy of each table": the five loaders
# below used to each `pd.read_parquet` their own copy of a file
# `lib.engine.scenario_cache.bundle`'s `ctx` (via `load_context`) ALSO
# reads -- 206 MB of duplication per the 2E census. Each now returns the
# VERY SAME object held in `bundle["ctx"]`, proven byte-identical with
# `pd.testing.assert_frame_equal` in `tests/test_ram_budget.py` before this
# change (a perturbation test there proves the assertion is not vacuous).
# Import direction is one-way: this module imports `scenario_cache`, never
# the reverse (`lib.engine` imports nothing from `lib.data_cache`,
# anywhere -- grepped clean) -- so this is not a cycle. First call to ANY
# of these five now builds the WHOLE bundle (ctx + search index + baselines
# +.) rather than reading one small parquet, because `bundle` and
# `get` were always going to need the whole ctx together for a scenario
# swap; this just moves that one-time cost earlier for a caller that only
# wanted the index. `topics_dim` stays independent below: `ctx["topics_
# dim_df"]` is a COLUMN SUBSET (`TOPICS_DIM_COLS`, 12 of 29 columns), not
# the same object, so aliasing it would silently drop columns some caller
# expects (assert_frame_equal failed on this pair -- see the test).
def _ctx_frame(key: str) -> pd.DataFrame:
    return _SC.bundle()["ctx"][key]


@st.cache_resource
def index() -> pd.DataFrame:
    """Institution index: identity, type (patched), country, size, links. One row per institution.

    Aliased to `scenario_cache.bundle["ctx"]["index_df"]` (D11) -- same object as
    `load_context`'s own read of this file, never a second copy."""
    return _ctx_frame("index_df")


@st.cache_resource
def fields() -> pd.DataFrame:
    """Field-grain shape/SI per institution x tree (L0 substrate).

    Aliased to `scenario_cache.bundle["ctx"]["fields_df"]` (D11) -- same object as
    `load_context`'s own read of this file, never a second copy."""
    return _ctx_frame("fields_df")


@st.cache_resource
def subfields() -> pd.DataFrame:
    """Subfield-grain shape/SI per institution x tree (L1/L2f substrate).

    Aliased to `scenario_cache.bundle["ctx"]["subfields_df"]` (D11) -- same object as
    `load_context`'s own read of this file, never a second copy."""
    return _ctx_frame("subfields_df")


@st.cache_resource
def topics_dim() -> pd.DataFrame:
    """Topic taxonomy dimension: domain/field/subfield/topic names, frontier scores, is_excluded.

    NOT aliased (D11): `ctx["topics_dim_df"]` is a 12-of-29-column SUBSET
    (`substrates.TOPICS_DIM_COLS`) of this file, a genuinely different
    object, not a duplicate read -- `tests/test_ram_budget.py` proves the
    two are unequal so this stays an independent read."""
    return pd.read_parquet(DATA_DIR / "topics_dim.parquet")


@st.cache_resource
def erc() -> pd.DataFrame:
    """ERC panel shares/mass/SI per institution (L4/L5 substrate).

    Aliased to `scenario_cache.bundle["ctx"]["erc_df"]` (D11) -- same object as
    `load_context`'s own read of this file, never a second copy."""
    return _ctx_frame("erc_df")


@st.cache_resource
def sdg() -> pd.DataFrame:
    """SDG shares/ESI/mass per institution (L6/L7 substrate).

    Aliased to `scenario_cache.bundle["ctx"]["sdg_df"]` (D11) -- same object as
    `load_context`'s own read of this file, never a second copy."""
    return _ctx_frame("sdg_df")


@st.cache_resource
def doctype_by_year() -> pd.DataFrame:
    """Document-type volumes per institution x year.

    Columns: `inst_key int32, institution_id str, year int16, doc_type
    category{article,book,book-chapter,letter,review}, vol_full int32,
    vol_frac float32`.

    Grain: institution x year x doc_type and **SPARSE** -- 141,182 rows, NOT a
    dense 7,557 x 6 x 5 cube: a cell with zero works has NO row at all (four
    institutions even lack every year but 2020). Never assume presence; the
    yearly-breakdown consumer fills a missing (year, type) cell with zero
    itself, so a series absent for a seed still renders its empty group
    (VIZ_SPEC S2.14 "a missing year is data").

    `doc_type` is a CATEGORY dtype -- cast `.astype(str)` before any `.map`
    (Assembly Line gotcha: `.map(.).fillna(.)` raises on a categorical).
    """
    return pd.read_parquet(DATA_DIR / "doctype_by_year.parquet")


@st.cache_resource
def sdg_fields() -> pd.DataFrame:
    """Institution x sdg x field x tree, fractional SDG-tagged mass, full
    2020-2025 run window.
    `field_id == -1` is the explicit 'untopiced' residual row (a work with
    SDG-tagged mass but no primary topic, ~0.14% of the corpus) -- never
    silently folded into a real field. 1,736,925 rows, 5.9 MB."""
    return pd.read_parquet(DATA_DIR / "sdg_fields.parquet")


@st.cache_resource
def sdg_year() -> pd.DataFrame:
    """Institution x sdg x year (2020-2025), fractional SDG-tagged mass,
    tree-independent. SUM over all 6 years equals
    `sdg.parquet`'s own `mass` for the same (institution, sdg) -- confirming
    `sdg.parquet`'s basis is the full 6-year run window, not the 5-year
    2020-2024 core window. 427,687 rows, 1.7 MB."""
    return pd.read_parquet(DATA_DIR / "sdg_year.parquet")


@st.cache_resource
def manifest() -> dict:
    """Deploy-time MANIFEST.json if ops/deploy.py has run, else the pre-staged
    source_manifest.json ( Data flow: MANIFEST/source_manifest fallback)."""
    path = DATA_DIR / "MANIFEST.json"
    if not path.is_file():
        path = DATA_DIR / "source_manifest.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
