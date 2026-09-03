"""
Tier-A identity + budget test for `lib/engine`.

`derive_shapes` is the app's only shape source, so it must reproduce the
shipped `subfields.parquet` / `fields.parquet` that the upstream `trees_agg.py`
built from the raw corpus -- for all three trees -- and its shares must sum to
1 per institution on every (tree, basis) scenario the UI can select.

Run from `app/`: python -m pytest tests/test_engine_identity.py -q -s
"""
from __future__ import annotations

import ctypes
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib.engine import derive as derive_mod
from lib.engine import derive_shapes, load_context, load_substrates, rank_all
from lib.engine.trees_agg import G6_FLOOR, TREES

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RTOL = 1e-6
GOLDEN_SEED = "I40413290"  # University of Gdansk

BUDGET_COLD_LOAD_S = 30.0
BUDGET_WARM_RANK_S = 1.0
# Before this budget was tightened, it stood at 2.5 GB against a measured
# 1.67 GB baseline (see the runtime print below, unchanged). The dtype
# repack (category/float32, impact_fields.parquet deleted) together with the
# collab_* duckdb pushdown (never materialized whole) measure 1.42 GB peak
# RSS for this exact cold-load+load_context+load_substrates+rank_all
# sequence, so the budget is now tightened to measured + ~30% headroom
# (1.42 * 1.3 = 1.846, rounded to 1.85) -- a future regression that eats
# back those savings still trips this gate well before Cloud's 2.7 GB hard
# cap. Cold/warm time budgets untouched: both stayed comfortably inside
# their existing budgets (6.88s/30s, 0.122s/1.0s).
BUDGET_PEAK_RSS_GB = 1.85


def peak_rss_gb() -> float | None:
    """PeakWorkingSetSize via GetProcessMemoryInfo -- stdlib ctypes only
    (copied from the ranking reference implementation's get_peak_rss_gb)."""
    try:
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
        psapi.GetProcessMemoryInfo.restype = wt.BOOL
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        if psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return c.PeakWorkingSetSize / (1024 ** 3)
    except Exception as e:  # pragma: no cover -- diagnostic only
        print(f"[budget] could not read peak RSS: {e}")
    return None


def _derive(tree: str, basis: str):
    return derive_shapes(DATA_DIR / "topics_all.parquet", DATA_DIR / "topics_dim.parquet",
                         tree=tree, basis=basis, exclude_811=False, index_institution_ids=None)


def _align(ref: pd.DataFrame, der: pd.DataFrame, id_col: str, tree: str):
    ref = ref[ref["tree"].astype(str) == tree].sort_values(["inst_key", id_col]).reset_index(drop=True)
    der = der[der["tree"].astype(str) == tree].sort_values(["inst_key", id_col]).reset_index(drop=True)
    ref_keys = set(zip(ref["inst_key"], ref[id_col]))
    der_keys = set(zip(der["inst_key"], der[id_col]))
    assert not (ref_keys - der_keys), f"{len(ref_keys - der_keys)} (institution, {id_col}) keys missing from derived"
    assert not (der_keys - ref_keys), f"{len(der_keys - ref_keys)} extra (institution, {id_col}) keys in derived"
    return ref, der


def _compare(ref: pd.DataFrame, der: pd.DataFrame, label: str, allow_floor_boundary: bool = False) -> int:
    """vol_full exact; the float32 columns within a SYMMETRIC relative
    tolerance (`|a-b| <= rtol * max(|a|,|b|)` -- np.allclose's asymmetric
    `rtol*|b|` would divide by a derived 0); si NaN pattern exact.

    `allow_floor_boundary` tolerates si cells sitting exactly ON the G6 floor
    (vol_frac == 30): trees_agg sums the raw corpus in float64 pandas while
    derive.py sums the topic grain in duckdb, so a cell whose fractional mass
    lands on 30.0 to within a float32 ulp can fall either side of
    `vol_frac >= 30`. Measured: 1 such cell in 756,484 for tree=original,
    0 for conservative, 0 for the shipped bestfit tables. Reported, never
    silently absorbed.

    Returns the number of cells that differ AT ALL (any column, any bit)."""
    assert np.array_equal(ref["vol_full"].to_numpy(), der["vol_full"].to_numpy()), f"{label}: vol_full differs"
    na = np.isnan(ref["si"].to_numpy())
    nb = np.isnan(der["si"].to_numpy())
    boundary = np.zeros(len(ref), dtype=bool)
    if (na != nb).any():
        boundary = (na != nb)
        vf = np.maximum(ref["vol_frac"].to_numpy(dtype=np.float64),
                        der["vol_frac"].to_numpy(dtype=np.float64))
        on_floor = np.abs(vf - G6_FLOOR) <= 1e-4
        assert allow_floor_boundary and bool((boundary <= on_floor).all()), (
            f"{label}: si NaN pattern differs on {int(boundary.sum())} cell(s), "
            f"{int((boundary & ~on_floor).sum())} of them NOT on the G6 floor")
        print(f"[identity] {label}: {int(boundary.sum())} si cell(s) straddle the G6 floor "
              f"(vol_frac == {G6_FLOOR}); excluded from the si comparison")
    ndiff = int((ref["vol_full"].to_numpy() != der["vol_full"].to_numpy()).sum())
    for col in ("vol_frac", "share_frac", "share_full", "si"):
        a = ref[col].to_numpy(dtype=np.float64)
        b = der[col].to_numpy(dtype=np.float64)
        both_nan = np.isnan(a) & np.isnan(b)
        ndiff += int((~(both_nan | (a == b))).sum())
        keep = ~both_nan & ~boundary
        rel = np.abs(a[keep] - b[keep]) / np.maximum(np.maximum(np.abs(a[keep]), np.abs(b[keep])), 1e-300)
        worst = float(rel.max()) if rel.size else 0.0
        assert worst <= RTOL, (f"{label}: {col} outside rtol={RTOL} "
                               f"(max symmetric relative deviation {worst:.3e})")
    return ndiff


@pytest.fixture(scope="module")
def default_derived():
    return _derive("bestfit", "frac")


def test_cast_output_is_float32_storage(default_derived):
    """The identity comparison is only meaningful on the SHIPPED storage
    dtypes -- `derive_shapes` applies `derive._cast_output` itself (derive.py
    lines 209 / 249); re-applying it here must be a no-op."""
    sub, fld = default_derived
    recast = derive_mod._cast_output(sub.copy(), "subfield_id", [])
    for c in ("vol_frac", "share_frac", "share_full", "si"):
        assert sub[c].dtype == np.float32, c
        assert fld[c].dtype == np.float32, c
        assert recast[c].dtype == np.float32
    assert sub["vol_full"].dtype == np.int32 and fld["vol_full"].dtype == np.int32


def test_identity_bestfit_frac_vs_shipped(default_derived):
    der_sub, der_fld = default_derived
    total = 0
    for table, id_col, der in (("subfields", "subfield_id", der_sub), ("fields", "field_id", der_fld)):
        shipped = pd.read_parquet(DATA_DIR / f"{table}.parquet")
        ref, d = _align(shipped, der, id_col, "bestfit")
        n = _compare(ref, d, f"bestfit/frac {table}")
        print(f"[identity] bestfit/frac {table}: {len(ref)} cells, {n} differ at all "
              f"({n / max(len(ref) * 5, 1):.4%} of compared values)")
        total += n
    print(f"[identity] TOTAL differing cells (bestfit/frac, shipped tables): {total}")


@pytest.mark.parametrize("tree", list(TREES))
@pytest.mark.parametrize("basis", ["frac", "full"])
def test_shares_sum_to_one(tree, basis):
    sub, fld = _derive(tree, basis)
    for label, df in (("subfields", sub), ("fields", fld)):
        for col in ("share_frac", "share_full"):
            s = df.groupby("inst_key", observed=True)[col].sum().to_numpy(dtype=np.float64)
            assert np.allclose(s, 1.0, atol=1e-6), (
                f"{tree}/{basis} {label}.{col} does not sum to 1 per institution "
                f"(max deviation {np.max(np.abs(s - 1.0)):.3e})")


def test_budgets():
    """`build_substrates` (in-app, per-scenario
    rebucketing) was replaced by `load_substrates` (reads
    the offline build's precomputed `app/data/scenarios/`)
    this budget now covers `load_context` + `load_substrates`, not a live
    rebuild. Assertions unchanged (brief: "keep their assertions")."""
    t0 = time.time()
    ctx = load_context(DATA_DIR)
    subs = load_substrates(ctx)
    cold = time.time() - t0

    rank_all(ctx, subs, GOLDEN_SEED)          # warm-up (first call touches lazy pages)
    t1 = time.time()
    rank_all(ctx, subs, GOLDEN_SEED)
    warm = time.time() - t1

    rss = peak_rss_gb()
    print(f"[budget] cold load_context+load_substrates: {cold:.2f}s (budget {BUDGET_COLD_LOAD_S}s)")
    print(f"[budget] warm rank_all(1 seed, 10 lenses): {warm:.3f}s (budget {BUDGET_WARM_RANK_S}s)")
    print(f"[budget] peak RSS: {rss:.2f} GB (budget {BUDGET_PEAK_RSS_GB} GB, WT baseline 1.67 GB)")
    assert cold <= BUDGET_COLD_LOAD_S, f"cold load {cold:.2f}s > {BUDGET_COLD_LOAD_S}s"
    assert warm <= BUDGET_WARM_RANK_S, f"warm rank_all {warm:.3f}s > {BUDGET_WARM_RANK_S}s"
    assert rss is not None and rss <= BUDGET_PEAK_RSS_GB, f"peak RSS {rss} GB > {BUDGET_PEAK_RSS_GB} GB"
