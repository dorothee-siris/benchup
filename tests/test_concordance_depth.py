"""
tests/test_concordance_depth.py -- the concordance top-N cut follows
`CONCORDANCE_N` (derived from config.yaml, the single source), now 50 --
same depth as every ranked list, no separate 30-deep cut left anywhere.

Note on what "widening N" actually guarantees. `concordance()`'s own output
is a SEPARATE tie-inclusive top-50 cut over a competitive ranking key
(-k, mean_rank, id) -- not a plain pass-through of the per-lens pools. Each
candidate's own k (lenses that hit it) is monotone non-decreasing as N grows
(cut_with_ties widens every per-lens pool, never shrinks it), but the
OUTPUT window is a fixed-size competitive cut: widening N also admits new,
often stronger competitors, which can and does push previously-included
low-k members of the N=30 output out of the N=50 output window (verified:
happens for every probed seed, not an edge case). So "the N=30 list is a
subset of the N=50 list" does not hold and is not asserted here; what is
guaranteed by construction, and tested below, is (a) per-lens pool
monotonicity, and (b) that k never decreases for any candidate that DOES
survive in both output windows.

Run from `app/`: python -m pytest tests/test_concordance_depth.py -q
"""
from __future__ import annotations

from pathlib import Path

import pytest

from lib.app_config import CFG
from lib.engine import (
    CONCORDANCE_N, DEFAULT_LENSES, concordance, cut_with_ties, load_context, load_substrates, rank_all,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SEEDS = ["I40413290", "I103320735", "I76903346"]  # PROBE_SEEDS, test_find_benchmark_section.py


def test_concordance_n_is_50_and_matches_config():
    assert CONCORDANCE_N == CFG["concordance_N"] == 50


@pytest.fixture(scope="module")
def engine():
    ctx = load_context(DATA_DIR)
    subs = load_substrates(ctx)
    return ctx, subs


def test_per_lens_pool_at_30_is_a_subset_of_the_pool_at_50(engine):
    """Pure-function guarantee (`cut_with_ties`): widening N can only ADD
    candidates to a single lens's tie-aware top-N pool, never drop one."""
    ctx, subs = engine
    for seed in SEEDS:
        r = rank_all(ctx, subs, seed)
        for lens in DEFAULT_LENSES:
            if r[lens]["undefined"]:
                continue
            ids30, _ = cut_with_ties(r[lens]["sorted_ids"], r[lens]["sorted_scores"], 30)
            ids50, _ = cut_with_ties(r[lens]["sorted_ids"], r[lens]["sorted_scores"], 50)
            assert set(ids30) <= set(ids50), f"{seed}/{lens}: top-30 pool not a subset of top-50 pool"


def test_concordance_k_never_decreases_for_candidates_common_to_both_windows(engine):
    """For a candidate present in BOTH the N=30 and N=50 concordance output
    windows, its k (lenses that hit it) is never lower at N=50 -- and at
    least one seed's output window must differ in composition, otherwise
    the depth change would be vacuous for real data."""
    ctx, subs = engine
    any_diff = []
    for seed in SEEDS:
        r = rank_all(ctx, subs, seed)
        rows30 = concordance(ctx, r, DEFAULT_LENSES, 30)
        rows50 = concordance(ctx, r, DEFAULT_LENSES, 50)
        by30 = {row["institution_id"]: row for row in rows30}
        by50 = {row["institution_id"]: row for row in rows50}
        common = set(by30) & set(by50)
        for iid in common:
            assert by50[iid]["k"] >= by30[iid]["k"], (
                f"{seed}: {iid} k dropped from {by30[iid]['k']} (N=30) to {by50[iid]['k']} (N=50)")
        any_diff.append((seed, set(by30) != set(by50)))

    assert any(differs for _, differs in any_diff), (
        f"N=50 concordance output is identical in composition to N=30 for all of {SEEDS} "
        f"-- pick different seeds; results were {any_diff}")
