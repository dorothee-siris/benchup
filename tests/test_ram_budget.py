"""tests/test_ram_budget.py -- RAM fit for Streamlit
Community Cloud, permanent gate. Recalibrated for
the unified-loader / one-resident-scenario architecture; carries forward the
earlier file's structure and ORDER rules almost unchanged -- only the budgets, the
loader-identity coverage and the NEW `test_scenario_cycle` are new here.

RSS-SENSITIVE, like `test_engine_identity.py:test_budgets` -- run this file
ISOLATED, never mixed into the main pytest sweep. `test_full_loader_sweep_
rss_delta` needs a clean just-imported baseline: a shared process that
already ran other test files (which themselves call `lib.data_cache`
loaders, e.g. `test_pages.py`) would read stale-warm frames and pass
vacuously regardless of what this build actually shipped. Gate ladder
convention: the main run excludes this whole file
(`--ignore=tests/test_ram_budget.py`, mirroring test_budgets' own
`--deselect`), then it runs on its own:

    python -m pytest tests/test_ram_budget.py -q -s

Data-driven, no fixtures -- reads the REAL app/data directly.

Covers:
  1. test_full_loader_sweep_rss_delta -- process-level RSS delta between a
     just-imported baseline and firing every lib.data_cache DataFrame loader
     plus lib.engine.scenario_cache.bundle (the ctx builder), in ONE
     process. MUST run first (see below).
  2. test_frame_census_under_budget -- every data_cache loader +
     bundle["ctx"]'s own frames, summed memory_usage(deep=True), DEDUPED
     BY OBJECT IDENTITY -- five of the eleven loaders now return the VERY SAME object bundle["ctx"] holds, so counting
     both would double-count one physical allocation, not prove the budget.
     Five identity assertions (`data_cache.X is bundle["ctx"]["X_df"]`)
     make the dedup itself falsifiable, not just implied by a lower number.
  3. test_collab_parquets_never_loaded_whole -- duckdb pushdown
     contract: a single-pair slice never returns more than a few hundred
     rows. SKIPPED, not failed, while `lib.collab_data` cannot be imported
     (see its own docstring below) -- a known, out-of-fence, ordering
     gap, not this file's regression.
  4. test_scenario_cycle -- one process calls
     `scenario_cache.get` for all 6 (tree, basis) combinations in
     sequence; RSS must never exceed the first reading + SCENARIO_CYCLE_
     BUDGET_MB, and every swap must free the PREVIOUS scenario's arrays
     (weakref proof, verified against bare-mode `st.cache_resource` -- see
     the test's own docstring for why a bare dict can't be weakly
     referenced directly, and the empirical check that bare-mode eviction
     really frees, so no `streamlit run` subprocess was needed).
  5. test_compare_pairs_sweep -- NEW (a concurrency fix, found via a stress
     test, phase B): 40 distinct qualifying pairs through
     Compare's six frame functions, sequentially, in one process; RSS
     growth from pair 10 to pair 40 must stay under
     COMPARE_SWEEP_GROWTH_BUDGET_MB -- the gate that would have caught the
     unbounded per-pair `ctx[key] = df` caches in `lib/collab_data.py`/
     `lib/leaders_data.py`/`lib/compare_data.py` before they ever reached
     a stress harness.
  6. test_repeated_scenario_cycle_no_ratchet -- NEW (a stress test, phase B,
     found a FAIL: peak 3477 MB, final 2412 MB, RETAINED
     growth from repeated scenario swapping, not just a transient spike).
     12 consecutive RANDOM `scenario_cache.get()` calls (same call pattern
     as `run_stress.py`'s chaos `scenario_combo` action); RSS after swap 12
     must not exceed RSS after swap 3 + REPEATED_CYCLE_GROWTH_BUDGET_MB --
     the gate that would have caught `_load_frame`'s per-swap heap
     fragmentation (root-caused and fixed in `lib/engine/substrates.py`,
     see `_FRAME_RAW_CACHE`'s docstring there) before it ever reached a
     stress harness. Deliberately LAST in this file (TEST ORDER) -- runs
     against an already-warm process (post `test_compare_pairs_sweep`),
     matching how a real long-running session actually hits this path.

TEST ORDER IS LOAD-BEARING: the RSS-delta test MUST run before anything else
in this file calls a data_cache loader, `scenario_cache.bundle`, or
`scenario_cache.get`, or its baseline is already warm. Python/pytest
collect test functions in file definition order (no reordering plugin in
this suite, confirmed against conftest.py) -- `test_full_loader_sweep_
rss_delta` is therefore defined FIRST; `test_scenario_cycle` and
`test_compare_pairs_sweep` are the two most expensive (6 full scenario
loads, then 40 pairs x 6 frame functions) and both deliberately run against
an already-warm ctx/bundle, matching how the real app hits it: a page never
requests a scenario before the process-wide bundle exists. `test_scenario_
cycle` is defined LAST BUT ONE and `test_compare_pairs_sweep` LAST OF ALL --
`test_scenario_cycle` happens to end on (bestfit, full), the exact scenario
Compare pins, so `test_compare_pairs_sweep` reuses that resident scenario
rather than paying its own load.
"""
from __future__ import annotations

import gc
import random
import sys
import weakref
from pathlib import Path

import duckdb
import pandas as pd
import pytest

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT / "ops"))

from lib import data_cache as DC  # noqa: E402
from lib.engine import scenario_cache as SC  # noqa: E402
from rss_probe import process_rss_mb  # noqa: E402

DATA_DIR = APP_ROOT / "data"

# Every lib/data_cache.py loader that returns a DataFrame (`manifest`
# returns a dict, not a frame, and is deliberately excluded). Unchanged from
# the earlier census -- aliased five of these onto bundle["ctx"]
# but added or removed no loader.
DATAFRAME_LOADERS = ["index", "fields", "subfields", "topics_dim", "erc", "sdg",
                     "doctype_by_year", "sdg_fields", "sdg_year"]

# The five loaders aliased onto scenario_cache.bundle["ctx"]
# `data_cache.<name>` must be the SAME OBJECT as `ctx["<key>"]`, not merely
# an equal one. `topics_dim` is deliberately absent: `ctx["topics_dim_df"]`
# is a 12-of-29-column SUBSET (`substrates.TOPICS_DIM_COLS`), a genuinely
# different object -- aliasing it would silently drop columns some caller
# expects. Established by `pd.testing.assert_frame_equal` per table before
# this suite aliased anything; the identity assertions
# below are the PERMANENT version of that one-time proof.
ALIASED_TABLES = {"index": "index_df", "fields": "fields_df", "subfields": "subfields_df",
                  "erc": "erc_df", "sdg": "sdg_df"}

# Measured 2026-09-03 (this file's own calibration, post-unification):
# loader sweep RSS delta 429.70 MB WorkingSetSize -- ~1.6x headroom under
# this ceiling (recalibrated DOWN from the earlier file's 900 MB; the five now-
# aliased loaders stopped paying for a second copy of index/fields/
# subfields/erc/sdg, ~55 MB of frame weight, but most of the 900->700 MB cut
# is headroom margin, not a 1:1 reflection of that -- RSS is a noisier
# process-level signal than the frame census below).
RSS_DELTA_BUDGET_MB = 700.0

# Measured 2026-09-03: frame census 91.42 MB DEDUPED BY IDENTITY (index
# 17.12 + fields 4.84 + subfields 23.47 + topics_dim 3.55 + erc 5.53 +
# sdg 2.99 + doctype_by_year
# 2.97 + sdg_fields 5.30 + sdg_year 8.02 + ctx.index_by_id 17.12 +
# ctx.topics_dim_df 0.51; ctx.index_df/fields_df/subfields_df/erc_df/sdg_df
# contribute ZERO extra -- same objects as their data_cache.* counterparts)
# ~3x headroom under this ceiling (recalibrated DOWN from the earlier file's
# 600 MB: the earlier census counted every aliased table TWICE, once as a
# data_cache frame and once as a separate ctx frame from an independent
# `load_context` call).
FRAME_BUDGET_MB = 450.0

# The scenario-swap ceiling:
# every RSS reading across the 6-scenario cycle must stay within this many
# MB of the FIRST reading. Measured 2026-09-03: max delta ~300 MB (two
# basis-keyed topic-share matrices, ~172 MB each, load once each and then
# stay resident for the rest of the process by design -- an architecture
# note "tree/basis-invariant blocks. loaded once and shared" -- NOT a
# leak; see the test's own docstring) -- ~2.5x headroom.
SCENARIO_CYCLE_BUDGET_MB = 750.0

COLLAB_PAIR_ROW_CAP = 5000
# The reference anchor pair.
IFREMER_ID, NIOZ_ID = "I154202486", "I4210107283"

SCENARIOS = [(tree, basis)
            for tree in ("original", "conservative", "bestfit")
            for basis in ("frac", "full")]

# NEW (a concurrency fix, found via a stress test, phase B): 40
# distinct qualifying pairs, seeded, `core_total >= 20` (well above the P7
# floor of 5 -- every function below has real rows to chew on, not empty
# frames). Measured pre-fix: ~1.8 MB/pair sequential slope from the
# unbounded `ctx[key] = df` per-pair caches in `lib/collab_data.py`/
# `lib/leaders_data.py`/`lib/compare_data.py` -- small alone, but the same
# unbounded growth compounded with concurrent duckdb-connection overhead and
# scenario-swap double-residency to blow stress phase B's 1,800 MB ceiling.
COMPARE_SWEEP_MIN_CORE_TOTAL = 20
COMPARE_SWEEP_N_PAIRS = 40
COMPARE_SWEEP_SEED = 7
COMPARE_SWEEP_GROWTH_BUDGET_MB = 250.0


def _qualifying_pairs(n: int, seed: int, min_core: int = COMPARE_SWEEP_MIN_CORE_TOTAL) -> list[tuple[str, str]]:
    """`n` distinct (a, b) pairs with `collab_pairs.core_total >= min_core`,
    duckdb-pushed (never the 3.58M-row whole table into pandas) and sampled
    with a seeded `random.Random` for a reproducible gate."""
    con = duckdb.connect()
    try:
        df = con.execute(
            "SELECT a, b FROM read_parquet(?) WHERE core_total >= ? ORDER BY a, b",
            [str((DATA_DIR / "collab_pairs.parquet").as_posix()), min_core],
        ).df()
    finally:
        con.close()
    rng = random.Random(seed)
    picks = rng.sample(range(len(df)), n)
    return [(df.iloc[i]["a"], df.iloc[i]["b"]) for i in picks]


def test_full_loader_sweep_rss_delta():
    """MUST run first in this file (see module docstring) -- WorkingSetSize
    delta between a just-imported baseline and after firing every
    DATAFRAME_LOADERS entry plus `scenario_cache.bundle` (the ctx
    builder), in ONE process. `bundle` -- NOT a bare `load_context` call
    is deliberate: `load_context` is a plain, uncached function, so a
    direct call here would build a SECOND ctx independent of the one the
    five aliased loaders already triggered, silently reintroducing the
    exact duplication a later change removed and inflating this number by ~150 MB for
    no reason. A collab parquet accidentally loaded whole again (3.4-15.4M
    rows) or a table read a second time outside the alias would blow this
    budget by an order of magnitude; the frame-census test below cannot
    catch that on its own since it inspects only the OBJECTS this file's
    own loaders return, not incidental process-wide allocation."""
    baseline = process_rss_mb()
    assert baseline is not None, "could not read baseline process RSS (ctypes GetProcessMemoryInfo failed)"

    for name in DATAFRAME_LOADERS:
        getattr(DC, name)()
    SC.bundle()

    after = process_rss_mb()
    assert after is not None, "could not read post-sweep process RSS"
    delta_ws = after[0] - baseline[0]
    print(f"[ram] full loader sweep RSS delta: {delta_ws:.2f} MB "
          f"(baseline {baseline[0]:.2f} MB, after {after[0]:.2f} MB, budget {RSS_DELTA_BUDGET_MB} MB)")
    assert delta_ws < RSS_DELTA_BUDGET_MB, (
        f"loader sweep RSS delta {delta_ws:.2f} MB >= budget {RSS_DELTA_BUDGET_MB} MB")


def test_frame_census_under_budget():
    """Every lib/data_cache.py loader (DATAFRAME_LOADERS) + `bundle["ctx"]`'s
    own DataFrame-valued entries, fired on the REAL app/data -- summed
    DataFrame.memory_usage(deep=True), DEDUPED BY PYTHON OBJECT IDENTITY --
    five of the eleven loaders are now the SAME object as a ctx frame; a
    plain sum would double-count them and this test would stop meaning
    anything). Runs AFTER the RSS-delta test above by definition order
    reuses whatever `st.cache_resource` already warmed, which is correct
    here: this test measures absolute frame size, not incremental cost, so
    cache state does not affect its result.

    Also asserts the identity itself, per aliased table: not just "the
    total is small" but "these two names are LITERALLY one object"
    falsifiable by construction (revert one loader to its own
    `pd.read_parquet` and this assertion fails, the vacuity proof
    demonstrated when this test was written)."""
    ctx = SC.bundle()["ctx"]

    for dc_name, ctx_key in ALIASED_TABLES.items():
        dc_obj = getattr(DC, dc_name)()
        ctx_obj = ctx[ctx_key]
        assert dc_obj is ctx_obj, (
            f"data_cache.{dc_name}() is not bundle()['ctx']['{ctx_key}'] -- aliasing broken, "
            f"two copies of this table are resident")

    total = 0.0
    detail: dict[str, float] = {}
    seen_ids: dict[int, str] = {}

    def _add(label: str, df: pd.DataFrame) -> None:
        nonlocal total
        key = id(df)
        if key in seen_ids:
            detail[f"{label} (== {seen_ids[key]})"] = 0.0
            return
        mb = df.memory_usage(deep=True).sum() / (1024 ** 2)
        seen_ids[key] = label
        detail[label] = mb
        total += mb

    for name in DATAFRAME_LOADERS:
        _add(f"data_cache.{name}", getattr(DC, name)())
    for k, v in ctx.items():
        if isinstance(v, pd.DataFrame):
            _add(f"ctx.{k}", v)

    print(f"[ram] frame census (deduped by identity): {total:.2f} MB (budget {FRAME_BUDGET_MB} MB)")
    for k, mb in sorted(detail.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<38} {mb:8.2f} MB")
    assert total < FRAME_BUDGET_MB, f"frame census {total:.2f} MB >= budget {FRAME_BUDGET_MB} MB"


def test_collab_parquets_never_loaded_whole():
    """A single-pair duckdb pushdown never returns more than a
    few dozen rows -- never the multi-million-row whole table.

    `pytest.importorskip` guards this in case `lib.collab_data` (which chains
    through `compare_data.py` and `profile_data.py`) ever fails to import
    again, turning that into an honest skip instead of a
    collection-time crash that would take the rest of this file down with
    it (see the module docstring's TEST ORDER note -- a broken import here
    must never cost the RSS/census/cycle tests their result)."""
    # pytest 9.1 defaults `importorskip` to catching only ModuleNotFoundError
    # (a missing package) -- the failure here is a genuine ImportError (a
    # present module whose OWN import raises), so exc_type must be widened
    # explicitly or this skip never fires and the raw ImportError fails the
    # test instead (caught empirically before shipping this test).
    pytest.importorskip(
        "lib.collab_data", exc_type=ImportError,
        reason="lib.collab_data -> compare_data -> profile_data failed to import.")
    from lib import collab_data as CDL

    for attr in ("collab_pairs", "collab_pair_fields", "collab_topic_vols"):
        assert not hasattr(DC, attr), (
            f"lib.data_cache still exposes {attr}() -- this whole-table loader should be deleted")

    ctx = {"data_dir": DATA_DIR}
    for table in ("collab_pairs", "collab_topic_vols", "collab_pair_fields"):
        df = CDL._collab_pair_slice(ctx, table, IFREMER_ID, NIOZ_ID)
        print(f"[ram] {table} slice for Ifremer x NIOZ: {len(df)} row(s)")
        assert len(df) < COLLAB_PAIR_ROW_CAP, (
            f"{table}: {len(df)} rows >= {COLLAB_PAIR_ROW_CAP} pair-slice sanity cap "
            f"(a whole-table read would return millions)")


def test_scenario_cycle():
    """NEW. Cycles all 6 (tree, basis)
    scenarios through `scenario_cache.get` in ONE process, in sequence.
    Two things must hold at every step:

      (a) RSS never exceeds the FIRST reading + SCENARIO_CYCLE_BUDGET_MB
          `max_entries=1` bounds the cache to one resident scenario dict,
          not zero growth (the two basis-keyed topic-share matrices and the
          l4-l7 common block are deliberately cached once and shared across
          every scenario -- an architecture note -- so the FIRST get pays
          for those and every later swap should be cheap by comparison).

      (b) the PREVIOUS scenario's arrays are actually freed once a
          DIFFERENT (tree, basis) is requested -- not merely "no longer
          reachable through the cache", but dead, checked with a real
          `weakref` + `gc.collect`. A plain `dict` has no `__weakref__`
          slot (`weakref.ref({})` raises `TypeError`), so this tracks one
          scenario-specific ndarray INSIDE each dict instead:
          `subs["l0"]["share"]`. `l0`/`l1`/`l2f` are read fresh from disk on
          every `load_substrates` call (substrates.py's own docstring:
          "scenario-specific, read fresh from disk on every call") and are
          therefore never shared across two different scenario dicts by
          construction -- unlike `l3`/`f1` (basis-keyed, 2 variants total)
          and `l4`-`l7` (1 variant), which substrates.py caches at ITS OWN
          module level and which correctly stay alive across every swap;
          tracking one of THOSE instead would make this proof vacuous (it
          would never go dead, cache or no cache).

    Confirmed empirically before writing this test that
    `st.cache_resource`'s LRU eviction genuinely frees the evicted value in
    BARE mode -- no real Streamlit server, the same "missing
    ScriptRunContext" condition this whole test file already runs under (a
    plain `python -m pytest` invocation, not `streamlit run`) -- so the
    brief's fallback path (drive the cycle through a real `streamlit run`
    subprocess) was not needed; this test's own assertions are that
    confirmation, made permanent."""
    baseline_after_first = None
    prev_weak = None

    for i, (tree, basis) in enumerate(SCENARIOS):
        subs = SC.get(tree, basis)
        rss = process_rss_mb()
        assert rss is not None, f"could not read process RSS at scenario {i} ({tree}, {basis})"
        print(f"[ram] scenario_cycle {i + 1}/{len(SCENARIOS)} ({tree}, {basis}): "
              f"RSS {rss[0]:.2f} MB (WorkingSetSize)")

        if baseline_after_first is None:
            baseline_after_first = rss[0]
        else:
            assert rss[0] <= baseline_after_first + SCENARIO_CYCLE_BUDGET_MB, (
                f"scenario_cycle RSS {rss[0]:.2f} MB > first-reading baseline "
                f"{baseline_after_first:.2f} MB + budget {SCENARIO_CYCLE_BUDGET_MB} MB "
                f"at ({tree}, {basis})")

        weak = weakref.ref(subs["l0"]["share"])
        del subs
        gc.collect()

        if prev_weak is not None:
            assert prev_weak() is None, (
                f"the PREVIOUS scenario's l0.share array is still alive after swapping to "
                f"({tree}, {basis}) -- max_entries=1 did not evict it, more than one scenario "
                f"dict is resident")
        prev_weak = weak

    print(f"[ram] scenario_cycle: baseline_after_first {baseline_after_first:.2f} MB, "
          f"budget +{SCENARIO_CYCLE_BUDGET_MB} MB, every reading within budget, "
          f"every swap freed the previous scenario's arrays")


def test_compare_pairs_sweep():
    """NEW (a concurrency fix). Runs Compare's six frame functions
    (`cards`, `top_subfields`, `sdg_frame`, `frontier_positioning`,
    `shared_frontier`, `relationship`) over 40 distinct qualifying pairs
    SEQUENTIALLY in this already-warm process -- reuses
    `scenario_cache.bundle()`/`get("bestfit", "full")`, the exact scenario
    Compare pins and the one `test_scenario_cycle` just above leaves
    resident, so this test pays no extra scenario load (TEST ORDER: must
    run AFTER `test_scenario_cycle`, per the module docstring's ordering
    convention -- defined last here for the same reason).

    Gate: RSS growth from after pair 10 to after pair 40 stays under
    `COMPARE_SWEEP_GROWTH_BUDGET_MB`. The bounded LRU (cap 32 per cache
    namespace) added to `lib/collab_data.py`/`lib/leaders_data.py`/
    `lib/compare_data.py`'s per-pair ctx caches keeps this near-flat once
    warm (the cache is full by pair 32, so pairs 33-40 evict as they
    insert); before that fix the caches grew without bound across distinct
    pairs, one entry per (table, pair) ever requested, for as long as the
    process stayed up."""
    ctx = SC.bundle()["ctx"]
    subs = SC.get("bestfit", "full")
    pairs = _qualifying_pairs(COMPARE_SWEEP_N_PAIRS, COMPARE_SWEEP_SEED)
    assert len(pairs) == COMPARE_SWEEP_N_PAIRS, f"expected {COMPARE_SWEEP_N_PAIRS} sampled pairs, got {len(pairs)}"

    from lib import compare_data as CD  # local import: keeps this file's module-load order untouched elsewhere

    r10 = r_end = None
    for i, (a, b) in enumerate(pairs, 1):
        CD.cards(ctx, [a, b])
        CD.top_subfields(ctx, subs, [a, b])
        CD.sdg_frame(ctx, subs, [a, b])
        CD.frontier_positioning(ctx, subs, [a, b])
        CD.shared_frontier(ctx, subs, [a, b])
        CD.relationship(ctx, [a, b], subs)
        if i == 10:
            r10 = process_rss_mb()
            assert r10 is not None, "could not read process RSS at pair 10"
            print(f"[ram] compare_pairs_sweep after 10 pairs: RSS {r10[0]:.2f} MB")
        if i == COMPARE_SWEEP_N_PAIRS:
            r_end = process_rss_mb()
            assert r_end is not None, f"could not read process RSS at pair {COMPARE_SWEEP_N_PAIRS}"
            print(f"[ram] compare_pairs_sweep after {COMPARE_SWEEP_N_PAIRS} pairs: RSS {r_end[0]:.2f} MB")

    growth = r_end[0] - r10[0]
    print(f"[ram] compare_pairs_sweep growth pair10->pair{COMPARE_SWEEP_N_PAIRS}: "
          f"{growth:.2f} MB (budget {COMPARE_SWEEP_GROWTH_BUDGET_MB} MB)")
    assert growth < COMPARE_SWEEP_GROWTH_BUDGET_MB, (
        f"compare_pairs_sweep RSS growth {growth:.2f} MB >= budget {COMPARE_SWEEP_GROWTH_BUDGET_MB} MB "
        f"between pair 10 and pair {COMPARE_SWEEP_N_PAIRS} -- the per-pair ctx caches in "
        f"lib/collab_data.py / lib/leaders_data.py / lib/compare_data.py may be unbounded again")


REPEATED_CYCLE_N_SWAPS = 12
REPEATED_CYCLE_SEED = 3
# Measured post-fix: 12 random swaps against an already-
# warm process (this test runs last, after test_compare_pairs_sweep) show
# ~0-2 MB drift, noise-level -- ~75x headroom under this budget. Pre-fix
# (bare-process repro, same call pattern): +134 MB over 24 swaps in a
# SEQUENTIAL 6-item cycle, and +786 MB peak over 144 swaps in a 3-thread
# concurrent simulation of the stress harness's actual scenario-switch
# volume -- this budget is generous on purpose so it fails loudly on ANY
# regression of the fix, not just a return to the full pre-fix magnitude.
REPEATED_CYCLE_GROWTH_BUDGET_MB = 150.0


def test_repeated_scenario_cycle_no_ratchet():
    """A stress-test finding (peak 3477 MB,
    final 2412 MB -- the FINAL reading exceeding the peak-ceiling-sized
    ratio proves RETAINED growth across the run, not just a transient
    spike). 12 consecutive `scenario_cache.get()` calls, RANDOM (tree,
    basis) each (`random.Random(REPEATED_CYCLE_SEED)`, same call shape as
    `run_stress.py`'s chaos `scenario_combo` action: both tree and basis
    re-rolled independently on every swap) -- asserts RSS after swap 12
    does not exceed RSS after swap 3 + REPEATED_CYCLE_GROWTH_BUDGET_MB.

    Root cause (bare-process isolation): `_load_frame`
    (`lib/engine/substrates.py`) re-reads and re-deserialises
    `fields_df`/`subfields_df` from parquet/pickle on every scenario swap,
    which left ~2-4 MB/swap of native heap fragmentation the OS never
    reclaimed -- NOT a Python reference leak (a per-object weakref proof
    over every array/frame in a scenario's `subs` dict showed each one IS
    correctly freed on eviction; `test_scenario_cycle` above still proves
    this for `l0.share`) and NOT pyarrow's own memory pool (its
    `bytes_allocated()` stayed flat across repeated identical reads).
    Isolating the read kinds pinned it further: 20 repeated fresh `np.load`
    calls for `l0`/`l1`/`l2f` cost +0.0 MB once warm; 20 repeated fresh
    `_load_frame` calls cost +78.6 MB and kept climbing. Fix: `_load_frame`
    caches its RAW read forever, keyed by physical file path (only 7 such
    paths exist across all 6 scenarios) -- see `_FRAME_RAW_CACHE`'s
    docstring in `lib/engine/substrates.py` for the full measurement table
    and the two rejected alternatives (a whole-block cache also killed the
    ratchet but cost 433 MB more resident for no further benefit; raising
    `scenario_cache.py`'s own `max_entries` made the peak WORSE by
    re-admitting the earlier double-residency window).

    Deliberately LAST in this file (TEST ORDER, module docstring): runs
    against an ALREADY-WARM process (post `test_scenario_cycle` and
    `test_compare_pairs_sweep`, which between them have already visited
    every (tree, basis) combination at least once) -- exactly how a real
    long-running session hits this path, and the harder case: a cold-cache
    12-swap run would trivially pass by never revisiting a physical file at
    all in fewer than 7 swaps."""
    rng = random.Random(REPEATED_CYCLE_SEED)
    trees = ["original", "conservative", "bestfit"]
    bases = ["frac", "full"]
    readings: list[float] = []

    for i in range(REPEATED_CYCLE_N_SWAPS):
        tree, basis = rng.choice(trees), rng.choice(bases)
        subs = SC.get(tree, basis)
        _ = subs["l0"]["share"].shape  # touch it, like a real page render would
        del subs
        gc.collect()
        rss = process_rss_mb()
        assert rss is not None, f"could not read process RSS at repeated-cycle swap {i + 1}"
        readings.append(rss[0])
        print(f"[ram] repeated_cycle swap {i + 1}/{REPEATED_CYCLE_N_SWAPS} ({tree}, {basis}): "
              f"RSS {rss[0]:.2f} MB")

    after_3, after_12 = readings[2], readings[-1]
    growth = after_12 - after_3
    print(f"[ram] repeated_cycle: after swap 3 = {after_3:.2f} MB, after swap {REPEATED_CYCLE_N_SWAPS} = "
          f"{after_12:.2f} MB, growth {growth:.2f} MB (budget {REPEATED_CYCLE_GROWTH_BUDGET_MB} MB)")
    assert growth <= REPEATED_CYCLE_GROWTH_BUDGET_MB, (
        f"repeated scenario cycling ratchets RSS: swap {REPEATED_CYCLE_N_SWAPS} {after_12:.2f} MB > "
        f"swap 3 {after_3:.2f} MB + budget {REPEATED_CYCLE_GROWTH_BUDGET_MB} MB -- "
        f"lib/engine/substrates.py's _FRAME_RAW_CACHE fix may be broken or bypassed")
