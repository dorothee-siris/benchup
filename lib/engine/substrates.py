"""
app/lib/engine/substrates.py -- population context + per-scenario substrate
loader.

Ports the recall reference implementation's `load_everything` and its
`build_*_substrate` family, plus the ranking reference implementation's L0
substrate and `build_catchall_811_share`. Arithmetic is copied, not rewritten;
every deviation is documented inline. The two that matter here:

  * `topics_all` is read with FIVE columns only (`inst_key, topic_id,
    share_frac, vol_frac, vol_full`) -- the full
    frame is 533 MB deep, 366 MB of it object strings. `institution_id` is
    therefore NOT available, so the L3/F1 dense matrices are filled by integer
    position (inst_key -> row, topic_id -> column) instead of
    `lens_lib.build_dense_matrix`'s `pivot_table(index="institution_id")`.
    (institution_id, topic_id) is the primary key of that table, so a pivot
    with `aggfunc="sum"` and a positional scatter produce the SAME matrix;
    uniqueness is asserted at load, not assumed. Column order is
    `sorted(topic_id)` -- byte-identical to `lens_lib.topic_matrices`' own
    `cats`.

  * `basis` is threaded through every shape-grain lens (L0/L1/C1 pick
    share_frac vs share_full; L3/F1 use share_frac vs a vol_full-normalised
    share). ERC/SDG outputs (L4-L7) are fractional-only and carry
    `basis_applies=False`.

Population order is `index.parquet` row order (= `inst_key` ascending =
`institution_id` ascending), asserted at load. Every matrix is reindexed
to it, so the stable argsort tie-break in `lenses.py` is reproducible.

`build_substrates` -- the per-scenario dense
matrix ASSEMBLY that used to live here -- moved to
an offline build that now writes every (tree, basis)
scenario to `app/data/scenarios/` before deployment. This module keeps `load_context`
(population + topic-grain arrays, cheap, still built live) and gains
`load_substrates(ctx, tree, basis)`, which returns the IDENTICAL dict
`build_substrates` used to (same keys, dtypes, shapes, memory order --
`tests/test_scenarios.py` proves it against the offline build's own
in-process build) by reading the precomputed files instead. `derive_shapes`
(`.derive`) is kept in the app package even though nothing on the live pages
calls it any more -- `tests/test_engine_identity.py` tests it directly as the
reference build the shipped scenario substrates must reproduce exactly.

Tree/basis-invariant blocks are cached at module
level, lazily, keyed by basis (topic-share matrix) or unconditionally (the
ERC/SDG common blocks) -- loaded once per process, shared across every
scenario switch, never re-read from disk per (tree, basis) call.

A data-contract size pass (`app/data/scenarios`
measured 544.9 MB against a 400 MB whole-`app/data` contract cap) prompted
three on-disk format changes, all detailed at their call sites (`_load_topic_share`,
`_load_frame`) and in the offline build's own module
docstring, which is the authoritative writer-side rationale:
  1. l3's topic-share matrix moved from a dense (split, mmap'd) `.npy` pair
     to a sparse (rows, cols, vals) triplet -- **DEVIATION**: the
     original hard rule ("load with mmap_mode='r' for the two topic
     matrices") no longer applies, there is nothing dense on disk to map;
     the reconstructed in-RAM array is still bit-identical in dtype/shape/
     F-order/values (proven by `tests/test_scenarios.py`), and resident RAM
     is unchanged (the matrix was always fully touched by L3/F1 scoring).
  2. l0/l1/l2f moved from `np.savez` to `np.savez_compressed` -- transparent
     to every reader here, `np.load` handles both identically.
  3. `fields_df`/`subfields_df` are consolidated once per TREE when the
     offline build's own empirical check proves the two bases differ ONLY
     in `si` (true for `subfields_df` on every tree, and for `fields_df` on
     `original`/`conservative` but NOT `bestfit`, whose `frac` build reads
     the shipped table while `full` reads a `derive_shapes` build)
     `_load_frame` reconstructs the exact original frame either way.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import lens_lib as L  # load_context still calls L.load_subfield_codebook / L.load_field_name_map below

DEFAULT_TREE = "bestfit"
DEFAULT_BASIS = "frac"

TOPICS_ALL_COLS = ["inst_key", "topic_id", "share_frac", "vol_frac", "vol_full"]
TOPICS_DIM_COLS = ["topic_id", "subfield_id", "subfield_name", "field_id", "field_name",
                   "domain_id", "domain_name", "is_excluded", "top25pct_frontier",
                   "original_subfield_id", "conservative_subfield_id", "bestfit_subfield_id"]

# L4-L7 read ERC/SDG outputs, which the upstream build only ever ships on the
# fractional basis -- the basis toggle does not apply to them.
BASIS_APPLIES = {"L0": True, "L1": True, "C1": True, "L3": True, "F1": True, "L2f": True,
                 "L4": False, "L5": False, "L6": False, "L7": False}


# --------------------------------------------------------------- context ----

def load_context(data_dir) -> dict:
    """Loads every table the engine needs from a deployed `app/data/` folder."""
    data_dir = Path(data_dir)
    index_df = pd.read_parquet(data_dir / "index.parquet")

    # ---- L14: population order = index.parquet row order = inst_key ascending
    # = institution_id ascending. Asserted, never assumed: every matrix below is
    # reindexed to this order and every tie-break is stable by that position.
    assert index_df["inst_key"].is_monotonic_increasing, \
        "index.parquet is not in ascending inst_key order (L14)"
    assert index_df["institution_id"].is_monotonic_increasing, \
        "index.parquet is not in ascending institution_id order (L14)"

    inst_ids = index_df["institution_id"].tolist()
    id_pos = {iid: i for i, iid in enumerate(inst_ids)}

    # Institutions flagged `pool_excluded` (a funder
    # surfacing as a performer, or a duplicate-institution row a canonical id
    # already covers) are never removed from the population -- their own data,
    # SI denominators and baselines stay exactly as they are (re-aggregation
    # is forbidden) -- but they must never come back as a CANDIDATE in a
    # lens ranking, the concordance or the aspirational views. Rather than a
    # per-lens filter, every lens (`lenses.rank_all`'s shared `_emit`) and
    # `rank_map` read this ONE position set. `pool_excluded` lands on
    # index.parquet once the upstream build ships it -- until then the
    # column is simply absent and every position set is empty, a no-op.
    if "pool_excluded" in index_df.columns:
        pool_excluded_positions = frozenset(
            np.flatnonzero(index_df["pool_excluded"].fillna(False).to_numpy(dtype=bool)).tolist())
    else:
        pool_excluded_positions = frozenset()

    inst_keys = index_df["inst_key"].to_numpy(dtype=np.int64)
    key_pos = np.full(int(inst_keys.max()) + 1, -1, dtype=np.int32)
    key_pos[inst_keys] = np.arange(len(inst_ids), dtype=np.int32)

    topics_dim_df = pd.read_parquet(data_dir / "topics_dim.parquet", columns=TOPICS_DIM_COLS)
    erc_df = pd.read_parquet(data_dir / "erc.parquet")
    sdg_df = pd.read_parquet(data_dir / "sdg.parquet")
    fields_df = pd.read_parquet(data_dir / "fields.parquet")
    subfields_df = pd.read_parquet(data_dir / "subfields.parquet")

    # ---- topics_all: five columns, topic_id mapped to an int position once ----
    ta = pd.read_parquet(data_dir / "topics_all.parquet", columns=TOPICS_ALL_COLS)
    topic_ids = sorted(ta["topic_id"].unique().tolist())  # == lens_lib.topic_matrices' cats
    topic_pos = {t: i for i, t in enumerate(topic_ids)}
    ta_inst = key_pos[ta["inst_key"].to_numpy(dtype=np.int64)]
    ta_topic = ta["topic_id"].map(topic_pos).to_numpy(dtype=np.int32)
    ta_share = ta["share_frac"].to_numpy()
    ta_vol_frac = ta["vol_frac"].to_numpy()
    ta_vol_full = ta["vol_full"].to_numpy()
    del ta
    assert (ta_inst >= 0).all(), "topics_all carries an inst_key absent from index.parquet"
    combo = ta_inst.astype(np.int64) * len(topic_ids) + ta_topic
    assert len(np.unique(combo)) == len(combo), \
        "(institution, topic) is not unique in topics_all -- positional scatter would drop mass"
    del combo

    subfield_name_by_id, _ = L.load_subfield_codebook()
    field_name_by_id = L.load_field_name_map(topics_dim_df)

    return {
        "data_dir": data_dir,
        "topics_all_path": data_dir / "topics_all.parquet",
        "topics_dim_path": data_dir / "topics_dim.parquet",
        "index_df": index_df, "index_by_id": index_df.set_index("institution_id"),
        "inst_ids": inst_ids, "id_pos": id_pos, "n": len(inst_ids), "key_pos": key_pos,
        "pool_excluded_positions": pool_excluded_positions,
        "erc_df": erc_df, "sdg_df": sdg_df, "fields_df": fields_df, "subfields_df": subfields_df,
        "topics_dim_df": topics_dim_df,
        "topic_ids": topic_ids, "topic_pos": topic_pos,
        "ta_inst": ta_inst, "ta_topic": ta_topic, "ta_share": ta_share,
        "ta_vol_frac": ta_vol_frac, "ta_vol_full": ta_vol_full,
        "subfield_name_by_id": subfield_name_by_id, "field_name_by_id": field_name_by_id,
    }


# -------------------------------------------------- precomputed scenarios
# Everything below reads the offline build's output from
# `<data_dir>/scenarios/`. Tree/basis-invariant blocks are cached at module
# level ("loaded once and shared, not re-read per scenario") -- this is
# a plain per-process cache, not an LRU: there are only 2 bases and 1 common
# block, so nothing needs eviction. `load_substrates` itself is NOT cached
# here (that whole-dict cache, `max_entries=1` behind a lock, is
# `lib/engine/scenario_cache.py`).

_TOPIC_SHARE_CACHE: dict[str, np.ndarray] = {}
_COMMON_CACHE: dict | None = None

# A stress test surfaced a RAM ratchet under repeated scenario swapping
# (final RSS 2412 MB, peak 3477 MB, growing with additional scenario swaps
# even when revisiting already-seen combos): a bare-process measurement
# proved the ratchet is native heap fragmentation from repeatedly re-reading and
# re-deserialising `fields_df`/`subfields_df` inside `_load_frame` below --
# NOT a reference leak (a per-object weakref proof over every array/frame in
# `subs` showed every piece IS correctly freed by Python each swap) and NOT
# pyarrow's own memory pool (`default_memory_pool().bytes_allocated()` stays
# FLAT across repeated identical reads). Isolating each read kind confirmed
# it: 20 repeated fresh reads of ONLY `l0`/`l1`/`l2f` (`np.load` on the small
# npz files) cost +0.0 MB once warm, while 20 repeated fresh calls to ONLY
# `_load_frame` (the fields_df/subfields_df parquet/pickle deserialize)
# cost +78.6 MB and kept climbing -- `_load_frame` is the fix target, not
# the npz blocks (left exactly as they were, "read fresh from disk on every
# call", per `_load_scenario_block`'s own docstring below).
#
# Fix: `_load_frame`'s RAW read (before the shared-mode rename/drop) is
# cached forever, per PHYSICAL FILE PATH, in `_FRAME_RAW_CACHE` -- there are
# only 7 such files across all 6 (tree, basis) scenarios (`mode=="shared"`:
# `frac`/`full` for `original` and `conservative` share ONE file each --
# size-pass item 3 -- so 2 trees x 1 file + `bestfit`'s own frac/full x
# 2 tables = 2+4=... measured 7 distinct paths), the
# SAME closed, fixed universe the module-level caching note above already
# reasons about for l3/l4-l7. A 3-thread bare-process simulation of a
# concurrent-session workload (144 total `SC.get()` calls, random (tree,basis)
# each, matching the app's actual per-run volume) grew RSS 448->1235 MB
# with the OLD always-re-read design; this fix measured a FLAT 1100.9 MB
# plateau after the first full 6-scenario cycle, zero further growth over
# 24 additional swaps. A whole-block cache (also caching
# l0/l1/l2f and the POST-rename/drop frame, not just the raw read) was
# tried first and ALSO fully killed the ratchet, but plateaued 433 MB
# higher (1533.8 MB) for no further benefit -- the npz blocks and the
# lightweight rename/drop/reindex step were never the problem, so caching
# them too only pays extra resident RAM. Deliberately not reintroducing
# `scenario_cache.py`'s own `_get_cached`/`max_entries` knob here: bumping
# THAT to 3 (one slot per concurrent session) was tried too and made things
# WORSE (1462 MB peak) -- `st.cache_resource`'s own post-build LRU re-admits
# the earlier double-residency window once `_SCENARIO_ENTRIES != 1`.
# This cache is a plain dict with no eviction (not `st.cache_resource`), so
# it carries none of that risk -- `_get_cached`'s own `max_entries=1`/
# evict-before-build logic is completely unchanged and still governs which
# ONE full `subs` dict is reachable through `scenario_cache.get()`; this
# cache only stops the REBUILD half of a swap from re-touching disk for the
# frame tables, it does not change how many scenarios are resident.
_FRAME_RAW_CACHE: dict[str, pd.DataFrame] = {}


def _scenarios_dir(ctx: dict) -> Path:
    return Path(ctx["data_dir"]) / "scenarios"


def _restore_order(arr: np.ndarray, order: str) -> np.ndarray:
    """`np.load`/`np.savez` round-trip the recorded fortran_order flag
    correctly by construction (the.npy format stores it in the header), so
    this is a belt-and-braces check, not the primary mechanism -- if a future
    numpy/format change ever broke that, this repairs it rather than
    silently shipping a wrong-order array (E2)."""
    if order == "F" and not arr.flags["F_CONTIGUOUS"]:
        return np.asfortranarray(arr)
    if order == "C" and not arr.flags["C_CONTIGUOUS"]:
        return np.ascontiguousarray(arr)
    return arr


def _load_topic_share(ctx: dict, basis: str) -> np.ndarray:
    """L3's dense (n_inst x n_topics) matrix for `basis` -- basis-dependent,
    tree-INVARIANT (confirmed against the pre-move `build_substrates`: the
    computation never touches `tree`).

    A data-contract size pass: stored as a
    sparse (rows, cols, vals) int16/int16/float32 triplet on disk (~27 MB/
    basis, down from ~136.5 MB dense) -- the offline build's own
    module docstring, size-pass item 1, has the full rationale and the
    mmap-rule deviation this required. Reconstructed here with the EXACT
    same allocate-then-scatter recipe the old dense build used
    (`np.zeros(shape, dtype=np.float32, order="F"); m[rows, cols] = vals`),
    so dtype/shape/F-order/values are bit-identical to the pre-size-pass
    design -- `tests/test_scenarios.py` proves it. No `mmap_mode` any more:
    there is no dense file to map, and the resident array must be fully
    materialised either way (L3/F1 scoring touches every cell)."""
    if basis in _TOPIC_SHARE_CACHE:
        return _TOPIC_SHARE_CACHE[basis]
    t0 = time.time()
    d = _scenarios_dir(ctx)
    meta = json.loads((d / f"topic_share_{basis}_meta.json").read_text(encoding="utf-8"))
    n, ncols = meta["shape"]
    npz = np.load(d / meta["npz"])
    rows, cols, vals = npz["rows"], npz["cols"], npz["vals"]
    share = np.zeros((n, ncols), dtype=np.float32, order="F")
    share[rows, cols] = vals
    assert share.flags["F_CONTIGUOUS"], "reconstructed topic-share matrix lost F order"
    _TOPIC_SHARE_CACHE[basis] = share
    print(f"[substrates] _load_topic_share({basis}): {len(rows)} nonzeros -> "
         f"({n}, {ncols}) in {time.time() - t0:.3f}s", flush=True)
    return share


def _load_common(ctx: dict) -> dict:
    """L4-L7 (ERC/SDG) -- tree- AND basis-invariant (`BASIS_APPLIES` False),
    loaded once per process."""
    global _COMMON_CACHE
    if _COMMON_CACHE is not None:
        return _COMMON_CACHE
    d = _scenarios_dir(ctx) / "common"
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    blocks = {}
    for key, block_meta in meta["blocks"].items():
        npz = np.load(d / f"{key}.npz")
        block = {}
        for arr_key in block_meta["array_keys"]:
            block[arr_key] = _restore_order(npz[arr_key], block_meta["order"][arr_key])
        block["cats"] = list(block_meta["cats"])
        blocks[key] = block
    _COMMON_CACHE = blocks
    return blocks


def _load_frame(scenarios_dir: Path, info: dict) -> pd.DataFrame:
    """Reconstructs one `fields_df`/`subfields_df` from `info` (this
    scenario's `meta.json["frames"][table]`), per size-pass item 3:

    `mode == "own"`: the file already IS the exact frame (per-scenario
    storage, e.g. `bestfit`'s `fields_df` -- frac reads the shipped table,
    full reads a derive_shapes build, so the two are not merely an
    `si`-only diff and are never consolidated).

    `mode == "shared"`: the file is `frames_common/<tree>/<table>.parquet`,
    written ONCE per tree with `si` split into `si_frac`/`si_full` (the two
    bases were proven cell-for-cell identical on every OTHER column at
    persist time -- verified by the offline build's own `_frame_diff_ignoring`).
    Reconstruction: rename `info["si_col"]` back to `si`, drop the other
    variant, reorder columns to `info["column_order"]` (recorded verbatim
    from the original in-process frame) -- byte-identical to the
    un-consolidated frame, `check_dtype=True`/`check_categorical=True` safe.

    The RAW read (before the shared-mode rename/drop) is cached forever
    in `_FRAME_RAW_CACHE`, keyed by the physical path string -- `mode ==
    "shared"` info dicts for `frac` and `full` carry the IDENTICAL `path`
    (one file backs both bases), so this collapses what used to be two full
    parquet/pickle deserializations into one. `.rename`/`.drop`/`[cols]`
    below all return NEW frames (never mutate their input in place), so
    handing the same cached raw object to every caller is safe -- the same
    precedent `_TOPIC_SHARE_CACHE`/`_COMMON_CACHE` above already set."""
    path = scenarios_dir / info["path"]
    path_key = str(path)
    df = _FRAME_RAW_CACHE.get(path_key)
    if df is None:
        df = pd.read_parquet(path) if info["ext"] == "parquet" else pd.read_pickle(path)
        _FRAME_RAW_CACHE[path_key] = df
    if info["mode"] == "shared":
        other = "si_full" if info["si_col"] == "si_frac" else "si_frac"
        df = df.rename(columns={info["si_col"]: "si"}).drop(columns=[other])
    return df[info["column_order"]]


def _load_scenario_block(ctx: dict, tree: str, basis: str) -> dict:
    """l0, l1, l2f -- scenario-specific, read fresh from disk on every call
    (unchanged: measured to cost zero incremental fragmentation once warm,
    see `_FRAME_RAW_CACHE`'s module-level docstring above). fields_df/
    subfields_df go through `_load_frame`, which caches the expensive raw
    read (not this function)."""
    scenarios_dir = _scenarios_dir(ctx)
    d = scenarios_dir / f"{tree}_{basis}"
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))

    def _npz_block(name: str) -> dict:
        npz = np.load(d / f"{name}.npz")
        block_meta = meta["arrays"][name]
        block = {k: _restore_order(npz[k], block_meta["order"][k]) for k in block_meta["order"]}
        block["cats"] = npz["cats"].tolist()
        return block

    l0 = _npz_block("l0")
    l1 = _npz_block("l1")
    l2f = _npz_block("l2f")

    fields_df = _load_frame(scenarios_dir, meta["frames"]["fields_df"])
    subfields_df = _load_frame(scenarios_dir, meta["frames"]["subfields_df"])
    return {"l0": l0, "l1": l1, "l2f": l2f, "fields_df": fields_df, "subfields_df": subfields_df}


def load_substrates(ctx: dict, tree: str = DEFAULT_TREE, basis: str = DEFAULT_BASIS) -> dict:
    """Loader replacement for the old `build_substrates(ctx, tree, basis)`:
    SAME return shape (same 10 lens keys, `tree`/`basis`/`basis_applies`),
    same dtypes, shapes, memory order (`tests/test_scenarios.py` proves it
    cell-for-cell against the offline build's own in-process build). Reads
    the offline build's precomputed
    `<data_dir>/scenarios/` tree instead of rebuilding from `topics_all` --
    the app never rebuckets that table again."""
    scenario = _load_scenario_block(ctx, tree, basis)
    topic_share = _load_topic_share(ctx, basis)
    common = _load_common(ctx)

    td = ctx["topics_dim_df"]
    frontier_ids = set(td.loc[td["top25pct_frontier"] == True, "topic_id"])  # noqa: E712
    excluded_ids = set(td.loc[td["is_excluded"] == True, "topic_id"])  # noqa: E712
    f1_cats = sorted(frontier_ids)
    keep_cols = np.array([ctx["topic_pos"][t] for t in f1_cats], dtype=np.int32)

    subs = {"tree": tree, "basis": basis, "basis_applies": dict(BASIS_APPLIES)}
    subs["l0"] = {"share": scenario["l0"]["share"], "cats": scenario["l0"]["cats"]}
    subs["l1"] = {"share": scenario["l1"]["share"], "cats": scenario["l1"]["cats"]}
    subs["fields_df"] = scenario["fields_df"]
    subs["subfields_df"] = scenario["subfields_df"]
    subs["l3"] = {"share": topic_share, "cats": ctx["topic_ids"]}
    subs["f1"] = {"share": topic_share[:, keep_cols], "cats": f1_cats,
                  "n_frontier_topics": len(frontier_ids),
                  "excluded_and_frontier_topic_ids": sorted(frontier_ids & excluded_ids)}
    subs["l2f"] = {"excess": scenario["l2f"]["excess"], "eligible": scenario["l2f"]["eligible"],
                   "cats": scenario["l2f"]["cats"]}
    subs["l4"] = {"share": common["l4"]["share"], "cats": common["l4"]["cats"]}
    subs["l5"] = {"excess": common["l5"]["excess"], "si": common["l5"]["si"], "cats": common["l5"]["cats"]}
    subs["l6"] = {"profile": common["l6"]["profile"], "raw_share": common["l6"]["raw_share"],
                  "cats": common["l6"]["cats"]}
    subs["l7"] = {"excess": common["l7"]["excess"], "esi": common["l7"]["esi"], "cats": common["l7"]["cats"]}
    return subs
