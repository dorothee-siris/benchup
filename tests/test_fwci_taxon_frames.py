"""tests/test_fwci_taxon_frames.py -- (BenchUp V4 trim),: a SECOND, independent witness for `lib.compare_data._fwci_taxon`, real
data (`app/data/fwci_taxa.parquet` / `fwci_taxa_ref.parquet`), separate from
`tests/test_compare_data.py`'s own golden-anchor equality tests -- it
re-derives the same facts a different way (a parquet-level sweep, not a
fixed institution list; a GENERIC search for a zero-reference taxon rather
than a hardcoded one) so a regression that slipped past the anchor tests
would still be caught here.

, (2026-09-03): ERC and field grain are DELETED from
this codebase (the code stays only in the archive) -- this file is rewritten to sweep
only the two surviving grains, `subfield` and `sdg`. The file's own
"bar=MEDIAN, hover=MEAN+n_covered / reference is the European
CORPUS-MEDIAN work-FWCI, a real 0.0 must survive untouched" invariants are
kept verbatim -- they are facts about the shipped `fwci_taxa*.parquet`
tables, not about which grains `compare_data.py` still exposes.

Invariants checked:
  1. n_covered >= 3 on EVERY row of the raw `fwci_taxa.parquet` file (its
     own floor), for both surviving grains.
  2. `_fwci_taxon`'s `fwci_mean` is populated (non-null) on every row.
  3. a real `eu_median_work_fwci == 0.0` taxon (found by SEARCHING
     `fwci_taxa_ref.parquet` at a surviving grain, not assumed) survives the
     ref-value join into a real institution's frame as an actual 0.0.
  4. BASIS-PINNING: `_fwci_taxon` takes no `subs`/`basis` argument at all
     checked by signature, not just by value (a stronger guarantee than
     "two calls happened to agree").

Run: python -m pytest tests/test_fwci_taxon_frames.py -q
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
FWCI_TAXA = DATA_DIR / "fwci_taxa.parquet"
FWCI_TAXA_REF = DATA_DIR / "fwci_taxa_ref.parquet"

SURVIVING_LEVELS = ("subfield", "sdg")
IFREMER = "I154202486"


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def raw_fwci_taxa():
    return pd.read_parquet(FWCI_TAXA)


@pytest.fixture(scope="module")
def raw_fwci_taxa_ref():
    return pd.read_parquet(FWCI_TAXA_REF)


# --------------------------------------------------------- 1. n_covered>=3

def test_raw_fwci_taxa_n_covered_floor_holds_on_surviving_grains(raw_fwci_taxa):
    sub = raw_fwci_taxa[raw_fwci_taxa["grain"].isin(SURVIVING_LEVELS)]
    assert len(sub) > 0
    assert (sub["n_covered"] >= 3).all(), "fwci_taxa.parquet's own floor (n_covered>=3) is violated"


@pytest.mark.parametrize("level", SURVIVING_LEVELS)
def test_fwci_taxon_n_covered_floor_holds(ctx, level):
    ids = [IFREMER]
    out = CD._fwci_taxon(ctx, ids, level)
    assert len(out) > 0
    assert (out["n_covered_fwci"] >= 3).all()


def test_taxon_metrics_unknown_level_raises_not_silently_empty(ctx):
    """VACUITY for the level assertion `_taxon_metrics` (the merged
    share/si/pp/fwci builder `sdg_frame`/`all_subfields` both call) applies:
    an unsupported grain -- `field`/`erc`, deleted here
    must raise, never quietly return zero rows (which would let a caller
    believe "no data" instead of "wrong/retired grain name")."""
    with pytest.raises(AssertionError):
        CD._taxon_metrics(ctx, {"basis": "full"}, [IFREMER], "field")
    with pytest.raises(AssertionError):
        CD._taxon_metrics(ctx, {"basis": "full"}, [IFREMER], "erc")


# ------------------------------------------------------- 2. fwci_mean rule

@pytest.mark.parametrize("level", SURVIVING_LEVELS)
def test_fwci_taxon_mean_populated_on_every_row(ctx, level):
    out = CD._fwci_taxon(ctx, [IFREMER], level)
    assert len(out) > 0
    assert out["fwci_mean"].notna().all(), f"{level}: fwci_mean must be populated on every row"


# -------------------------------------------------- 3. real 0.0 reference

def _find_zero_ref_taxon(raw_ref: pd.DataFrame, level: str):
    sub = raw_ref[(raw_ref["grain"] == level) & (raw_ref["eu_median_work_fwci"] == 0.0)]
    return None if sub.empty else int(sub.iloc[0]["taxon_id"])


def _find_institution_covered_in(raw_taxa: pd.DataFrame, level: str, taxon_id: int):
    sub = raw_taxa[(raw_taxa["grain"] == level) & (raw_taxa["taxon_id"] == taxon_id)]
    return None if sub.empty else str(sub.iloc[0]["institution_id"])


def test_a_real_zero_reference_taxon_survives_untouched(ctx, raw_fwci_taxa, raw_fwci_taxa_ref):
    """WT_2C.md claim 1: a genuine `eu_median_work_fwci == 0.0` (a real
    humanities citation-practice fact) must reach the merged frame as an
    ACTUAL 0.0, never dropped or truthiness-tested into NaN/None. Searched
    generically over BOTH surviving grains -- skips (does not fabricate a
    pass) if the current data has no such taxon at all."""
    for level in SURVIVING_LEVELS:
        tid = _find_zero_ref_taxon(raw_fwci_taxa_ref, level)
        if tid is None:
            continue
        iid = _find_institution_covered_in(raw_fwci_taxa, level, tid)
        if iid is None:
            continue
        out = CD._fwci_taxon(ctx, [iid], level).set_index("taxon_id")
        assert tid in out.index
        got = out.loc[tid, "eu_median_fwci"]
        assert got == 0.0, f"level={level} taxon={tid}: expected literal 0.0, got {got!r}"
        return
    pytest.skip("no zero-reference taxon with a covered institution found at subfield/sdg grain in this snapshot")


# ------------------------------------------------------------ 4. pinning ---

def test_fwci_taxon_signature_carries_no_subs_or_basis_argument():
    """BASIS-PINNED (decisions log 2026-09-01): `_fwci_taxon` must not even
    ACCEPT a `subs`/`basis` argument -- a stronger guarantee than "the
    output happens not to change", since a caller literally cannot pass one
    in by accident."""
    params = set(inspect.signature(CD._fwci_taxon).parameters)
    assert "subs" not in params
    assert "basis" not in params
    assert params == {"ctx", "ids", "level"}


@pytest.mark.parametrize("level", SURVIVING_LEVELS)
def test_fwci_taxon_two_institution_call_matches_two_single_calls(ctx, level):
    """A basic non-interference proof: calling with [a, b] together yields
    exactly the union of calling with [a] and [b] separately -- no row leaks
    between institutions, no row is silently dropped."""
    a, b = "I154202486", "I4210107283"
    together = CD._fwci_taxon(ctx, [a, b], level)
    solo_a = CD._fwci_taxon(ctx, [a], level)
    solo_b = CD._fwci_taxon(ctx, [b], level)
    assert len(together) == len(solo_a) + len(solo_b)
    merged = pd.concat([solo_a, solo_b], ignore_index=True).sort_values(
        ["institution_id", "taxon_id"]).reset_index(drop=True)
    together_sorted = together.sort_values(["institution_id", "taxon_id"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(merged, together_sorted, check_dtype=False)
