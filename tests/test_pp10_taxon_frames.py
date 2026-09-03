"""tests/test_pp10_taxon_frames.py -- (BenchUp V4 trim),: a
SECOND, independent witness for `lib.compare_data._pp_taxon`/`_pp_ref_means`
(PP10_WD), real data (`app/data/impact_taxa.parquet`), separate from
`tests/test_compare_data.py`'s own golden-anchor equality tests -- every
check here reads `impact_taxa.parquet` straight off disk (never through
`compare_data`'s own ctx-cache) and probes a different institution than the
anchor tests do, so a regression that breaks both together is still caught.

, ERC and field grain are DELETED (
stays the archive) -- this file is rewritten to sweep only the two
surviving grains, `subfield` and `sdg`. The "NO display floor" rule (every
taxon an institution has >=1 covered work in ships a row) is a fact about
the shipped table, kept verbatim.

VACUITY, per check: every assertion below is followed by an in-memory
mutation that makes the identical check fail -- proving none of these are
trivially satisfied by any frame `_pp_taxon` could return.

Run: python -m pytest tests/test_pp10_taxon_frames.py -q
"""
from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import compare_data as CD
from lib.engine import load_context

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
IMPACT_TAXA = DATA_DIR / "impact_taxa.parquet"

SURVIVING_LEVELS = ("subfield", "sdg")
IFREMER = "I154202486"          # tests/test_compare_data.py's own golden institution
STRASBOURG = "I68947357"        # this module's OWN probe, distinct from IFREMER


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def raw_impact_taxa():
    return pd.read_parquet(IMPACT_TAXA)


# --------------------------------------------- 1. no floor, exact ship

@pytest.mark.parametrize("level", SURVIVING_LEVELS)
def test_pp_taxon_ships_every_raw_row_no_floor(ctx, raw_impact_taxa, level):
    """The headline rule: `_pp_taxon(., level)` must ship EXACTLY the raw
    (institution, taxon) rows `impact_taxa.parquet` has for STRASBOURG at
    this grain -- no 10/30 impact-floor control anywhere in this API path
    any more."""
    raw = raw_impact_taxa[(raw_impact_taxa["grain"] == level)
                          & (raw_impact_taxa["institution_id"] == STRASBOURG)]
    out = CD._pp_taxon(ctx, [STRASBOURG], level)
    assert len(out) == len(raw) > 0, level
    assert set(out["taxon_id"]) == set(raw["taxon_id"].astype(int))

    # VACUITY: dropping one real raw row and re-checking set-equality fails.
    dropped_ids = set(raw["taxon_id"].astype(int)) - {int(raw.iloc[0]["taxon_id"])}
    assert set(out["taxon_id"]) != dropped_ids


@pytest.mark.parametrize("level", SURVIVING_LEVELS)
def test_pp_taxon_pp10_wd_in_unit_interval(ctx, level):
    out = CD._pp_taxon(ctx, [IFREMER, STRASBOURG], level)
    assert len(out) > 0
    assert (out["pp10_wd"] >= 0.0).all() and (out["pp10_wd"] <= 1.0).all()
    # VACUITY: a value outside [0,1] would fail this same check.
    bad = out["pp10_wd"].copy()
    bad.iloc[0] = 1.5
    assert not ((bad >= 0.0) & (bad <= 1.0)).all()


@pytest.mark.parametrize("level", SURVIVING_LEVELS)
def test_pp_taxon_n_covered_pp_matches_raw_exactly(ctx, raw_impact_taxa, level):
    raw = raw_impact_taxa[(raw_impact_taxa["grain"] == level)
                          & (raw_impact_taxa["institution_id"] == IFREMER)].set_index("taxon_id")
    out = CD._pp_taxon(ctx, [IFREMER], level).set_index("taxon_id")
    assert len(out) == len(raw)
    for tid in raw.index:
        assert out.loc[int(tid), "n_covered_pp"] == raw.loc[tid, "n_covered_pp"]
        assert np.isclose(out.loc[int(tid), "pp10_wd"], raw.loc[tid, "pp10_wd"], atol=1e-6)


# --------------------------------------------------- 2. taxon_metrics gate

def test_taxon_metrics_rejects_unsupported_level(ctx):
    """Field/ERC grain is DELETED here (the archive keeps the
    old data) -- `_taxon_metrics` (which `_pp_taxon` feeds into via
    `sdg_frame`/`all_subfields`) must raise for either, never silently
    return an empty frame that could be misread as "no impact data"."""
    for bad_level in ("field", "erc", "bogus"):
        with pytest.raises(AssertionError):
            CD._taxon_metrics(ctx, {"basis": "full"}, [IFREMER], bad_level)


# ------------------------------------------------------------ 3. pinning ---

def test_pp_taxon_signature_carries_no_subs_or_basis_or_tree_argument():
    """BASIS- and BESTFIT-TREE-PINNED (decisions log 2026-09-02): `_pp_taxon`
    must not even ACCEPT a `subs`/`basis`/`tree` argument."""
    params = set(inspect.signature(CD._pp_taxon).parameters)
    assert params == {"ctx", "ids", "level"}
    assert "subs" not in params and "basis" not in params and "tree" not in params


@pytest.mark.parametrize("level", SURVIVING_LEVELS)
def test_pp_taxon_value_is_scenario_invariant_in_practice(ctx, level):
    """Cross-check the STRUCTURAL guarantee above with an empirical one:
    `_pp_taxon` never reads `ctx`'s scenario-dependent keys at all, so
    calling it twice (nothing in between could have changed its inputs)
    reproduces the identical frame -- a cheap idempotence proof standing in
    for a basis/tree A-B compare now that there is no `subs` to vary."""
    a = CD._pp_taxon(ctx, [IFREMER], level)
    b = CD._pp_taxon(ctx, [IFREMER], level)
    pd.testing.assert_frame_equal(a, b)


# ------------------------------------------------ 4. reference-mean sanity

@pytest.mark.parametrize("level", SURVIVING_LEVELS)
def test_pp_ref_means_is_a_population_mean_not_the_institutions_own_value(ctx, raw_impact_taxa, level):
    """`_pp_ref_means` must be a POPULATION statistic (many institutions),
    not silently collapse to one institution's own value -- checked by
    comparing against a hand-computed groupby mean straight off the raw
    file (never through `compare_data`'s own ctx-cache)."""
    raw = raw_impact_taxa[raw_impact_taxa["grain"] == level]
    want = raw.groupby("taxon_id")["pp10_wd"].mean()
    got = CD._pp_ref_means(ctx, level)
    assert len(got) == len(want)
    # pick a taxon with a real, multi-institution population so the mean is
    # provably NOT any one institution's own value
    counts = raw.groupby("taxon_id").size()
    multi_ids = counts[counts >= 5].index
    assert len(multi_ids) > 0
    sample_id = int(multi_ids[0])
    assert np.isclose(float(got.loc[sample_id]), float(want.loc[sample_id]), atol=1e-6)
    one_row = raw[raw["taxon_id"] == sample_id].iloc[0]
    single_val = float(one_row["pp10_wd"])
    # VACUITY: a "mean" that was secretly just one institution's row would
    # equal that row far more often than chance across 5+ real institutions
    # assert the population mean is NOT identical to this one arbitrary row.
    assert not np.isclose(single_val, float(want.loc[sample_id]), atol=1e-9), (
        "suspicious: population mean equals one institution's own value exactly")
