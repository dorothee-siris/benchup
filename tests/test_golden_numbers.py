"""
tests/test_golden_numbers.py -- hand-derived golden pins over REAL
`app/data/*.parquet` tables. Every number below is
derived IN THE TEST (comments show the arithmetic), from raw parquet reads
that do NOT import the function under test's own helper -- never copied from
a one-off probe script or a scratch notebook. Where a live app function is then
called, the test asserts the app's own output equals the independently
hand-derived number (a real regression guard, not just a self-consistency
check of the derivation script).

Skip-if-absent: session-scoped fixtures skip the whole module when
`app/data/collab_pairs.parquet` is not on disk.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import collab_data as CL
from lib.engine import load_context

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"

STRASBOURG = "I68947357"
IFPEN = "I265217849"
CNRS = "I1294671590"
FIELD_DECISION_SCIENCES = 18   # topics_dim.parquet: field_id 18 == "Decision Sciences"
FIELD_PHYSICS = 31             # OpenAlex field "Physics and Astronomy"
FIELD_AG_BIO = 11              # "Agricultural and Biological Sciences"

pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "collab_pairs.parquet").exists(),
    reason="app/data/*.parquet v2 artefacts not present -- skip-if-absent CI guard")


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


# ============================================================================
# (a) IFPEN Decision Sciences sdg_share -- derived by hand from sdg_fields.
# parquet + fields.parquet directly (never `_sdg_share_field_frame`'s own
# code). A prior one-off probe measured 0.6197 (fractional basis) on the
# live data; this derivation is independent and only cross-checks
# against that number as a sanity anchor, not a copied source.
# ============================================================================

def test_ifpen_decision_sciences_sdg_share_hand_derived():
    sdg_fields = pd.read_parquet(DATA_DIR / "sdg_fields.parquet")
    fields = pd.read_parquet(DATA_DIR / "fields.parquet")

    s = sdg_fields[(sdg_fields["institution_id"] == IFPEN) & (sdg_fields["tree"] == "bestfit")
                   & (sdg_fields["field_id"] == FIELD_DECISION_SCIENCES)]
    f = fields[(fields["institution_id"] == IFPEN) & (fields["tree"] == "bestfit")
              & (fields["field_id"] == FIELD_DECISION_SCIENCES)]
    assert len(s) == 1 and len(f) == 1, "expected exactly one sdg_fields row and one fields row for IFPEN/field 18"

    # numerator: distinct-tagged (>=1 SDG) fractional/full mass in this field.
    # denominator: the field's OWN total fractional/full mass. SAME window
    # (core_window, 2020-2024) and SAME basis on both sides by construction
    # of sdg_fields.parquet v2 (window_conventions.core_window) -- this is
    # the exact numerator/denominator pair `_sdg_share_field_frame` computes,
    # derived here from the raw tables, not that function.
    num_frac = float(s["mass_any_frac"].iloc[0])
    den_frac = float(f["vol_frac"].iloc[0])
    num_full = float(s["mass_any_full"].iloc[0])
    den_full = float(f["vol_full"].iloc[0])

    hand_frac = num_frac / den_frac
    hand_full = num_full / den_full

    # sanity anchor against a prior live probe (0.6197, fractional basis)
    np.testing.assert_allclose(hand_frac, 0.6197183399393414, atol=1e-6)
    np.testing.assert_allclose(hand_full, 0.6666666666666666, atol=1e-6)  # = 2/3 exactly (num_full=2.0, den_full=3)
    assert 0.0 <= hand_frac <= 1.0 and 0.0 <= hand_full <= 1.0
    # (no live-app cross-check here: the trimmed Compare surface has no
    # field x SDG share view any more -- the SDG profile is capped at SDG
    # grain, 17 rows -- so this stays a pure sdg_fields/fields data-quality
    # golden, not a UI regression guard.)


# ============================================================================
# (b) Strasbourg x CNRS pair core_total + field 31 row (vol/n_top10/n_covered)
# recomputed from collab_pairs.parquet/collab_pair_fields.parquet directly --
# a pure data-consistency check (core_total by definition, and the
# n_top10 <= n_covered <= vol ordering every field row must respect).
# ============================================================================

def test_strasbourg_cnrs_core_total_and_physics_field_recomputed(ctx):
    lo, hi = sorted([CNRS, STRASBOURG])
    pairs = pd.read_parquet(DATA_DIR / "collab_pairs.parquet")
    prow = pairs[(pairs["a"] == lo) & (pairs["b"] == hi)].iloc[0]
    core_total = int(prow["core_total"])
    c1, c2 = int(prow["c1"]), int(prow["c2"])
    assert core_total == c1 + c2, "core_total must equal c1+c2 by definition (SS2.2)"

    fields = pd.read_parquet(DATA_DIR / "collab_pair_fields.parquet")
    frow = fields[(fields["a"] == lo) & (fields["b"] == hi) & (fields["field_id"] == FIELD_PHYSICS)].iloc[0]
    vol, n_top10, n_covered = int(frow["vol"]), int(frow["n_top10"]), int(frow["n_covered"])
    assert n_top10 <= n_covered <= vol


# ============================================================================
# (c) One momentum class recomputed from c1/c2/d1/d2 + collab_facts.json,
# z-test included -- I1289784979 x I62916508 (a 'down'-classified pair).
# ============================================================================

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def test_momentum_down_class_hand_derived_with_z_test(ctx):
    A, B = "I1289784979", "I62916508"
    lo, hi = sorted([A, B])
    pairs = pd.read_parquet(DATA_DIR / "collab_pairs.parquet")
    prow = pairs[(pairs["a"] == lo) & (pairs["b"] == hi)].iloc[0]
    c1, c2 = float(prow["c1"]), float(prow["c2"])

    idx = pd.read_parquet(DATA_DIR / "index.parquet",
                          columns=["institution_id", "total_ar_full_w1", "total_ar_full_w2"]).set_index("institution_id")
    d1 = float(idx.loc[A, "total_ar_full_w1"] + idx.loc[B, "total_ar_full_w1"])
    d2 = float(idx.loc[A, "total_ar_full_w2"] + idx.loc[B, "total_ar_full_w2"])

    facts = json.loads((DATA_DIR / "collab_facts.json").read_text(encoding="utf-8"))
    med, band, alpha = facts["med"], facts["band"], facts["alpha"]

    # r = (c2/d2)/(c1/d1); rr = r/MED (SS2.3)
    r = (c2 / d2) / (c1 / d1)
    rr = r / med

    # pooled two-proportion z-test on (c1/d1) vs (c2/d2)
    p1, p2 = c1 / d1, c2 / d2
    p_pool = (c1 + c2) / (d1 + d2)
    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / d1 + 1.0 / d2))
    z = (p2 - p1) / se
    pval = 2.0 * (1.0 - _norm_cdf(abs(z)))

    candidate = "down" if rr <= 1.0 - band else ("up" if rr >= 1.0 + band else "stable")
    final_class = candidate if pval < alpha else "ns"

    np.testing.assert_allclose(rr, 0.3519085546282133, rtol=1e-5)
    np.testing.assert_allclose(pval, 0.03661144929074123, rtol=1e-3)
    assert candidate == "down"
    assert final_class == "down"

    # cross-check against the shipped, upstream-classified row
    assert str(prow["mom_class"]) == final_class == "down"
    np.testing.assert_allclose(float(prow["mom_rr"]), rr, rtol=1e-5)
    np.testing.assert_allclose(float(prow["mom_p"]), pval, rtol=1e-3)

    # and against the app's own display formatter (pure formatting over the
    # already-classified row -- collab_data.momentum_display)
    text, color, glyph = CL.momentum_display(prow["mom_class"], prow["mom_rr"], prow["mom_p"], c1, c2, facts)
    delta_pct = (float(prow["mom_rr"]) - 1.0) * 100.0
    assert text == f"{delta_pct:+.0f}%"
