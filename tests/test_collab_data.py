"""
lib/collab_data.py acceptance tests (Tier A). Anchors are concrete values
recomputed from app/data/*.parquet (env-app, bestfit/frac
default scenario).

`shared_topics`/`joint_profile`/`untapped` and their test suites
are DELETED (the builders themselves are gone from lib/collab_data.py --
see that module's own docstring) and replaced by `pair_domain_year`'s tests
at the bottom of this file.

Run: python -m pytest tests/test_collab_data.py -q
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import collab_data as CL
from lib.engine import load_substrates, load_context

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

STRASBOURG, IFPEN, GDANSK, ISCTE, SORBONNE, ETH = (
    "I68947357", "I265217849", "I40413290", "I110026055", "I39804081", "I35440088")


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def subs_bestfit(ctx):
    return load_substrates(ctx)  # default: bestfit / frac


CNRS = "I1294671590"


# ============================================================================
# Anchors recomputed via an INDEPENDENT code path (plain pandas
# over app/data/collab_pairs.parquet, no import of lib.collab_data).
# ============================================================================

def test_pulse_pinned_anchor_cnrs_strasbourg_table_order(ctx):
    """Pinned fact: copubs_total 12694,
    rank_in_b 1 -- called in the TABLE's own a<b order (CNRS < Strasbourg
    lexicographically)."""
    got = CL.pulse(ctx, CNRS, STRASBOURG)
    assert got["copubs_total"] == 12694
    assert got["rank_in_a"] == 16
    assert got["rank_in_b"] == 1
    want_years = {2020: 2284, 2021: 2357, 2022: 2190, 2023: 2123, 2024: 2034, 2025: 1706}
    for y, v in want_years.items():
        row = got["yearly"].loc[got["yearly"]["year"] == y, "copubs"].iloc[0]
        assert int(row) == v
    assert got["yearly"]["copubs"].sum() == 12694


def test_pulse_swapped_call_order_reorients_ranks(ctx):
    """Calling pulse(Strasbourg, CNRS) -- the OPPOSITE of the table's own
    a<b order -- must swap rank_in_a/rank_in_b to stay CALLER-relative:
    rank_in_a (rank of CNRS among Strasbourg's partners) == 1, rank_in_b
    (rank of Strasbourg among CNRS's partners) == 16."""
    got = CL.pulse(ctx, STRASBOURG, CNRS)
    assert got["copubs_total"] == 12694
    assert got["rank_in_a"] == 1
    assert got["rank_in_b"] == 16


def test_pulse_denominators_and_share_anchor(ctx):
    """Independently summed off index.vol_full_by_year_this_run (2020-2025):
    Strasbourg 22865, CNRS 281939 (raw pandas over index.parquet, not
    lib.collab_data's own _parse_packed_years call site)."""
    got = CL.pulse(ctx, STRASBOURG, CNRS)
    np.testing.assert_allclose(got["denominator_a"], 22865.0, rtol=1e-9)
    np.testing.assert_allclose(got["denominator_b"], 281939.0, rtol=1e-9)
    np.testing.assert_allclose(got["share_of_a"], 12694 / 22865.0, rtol=1e-9)
    np.testing.assert_allclose(got["share_of_b"], 12694 / 281939.0, rtol=1e-9)


def test_pulse_none_for_a_pair_that_never_co_published(ctx):
    """Two small, unrelated institutions with NO row in collab_pairs at all."""
    a, b = "I1305429183", "I1308570094"
    pairs = _load_pairs_raw(ctx)
    lo, hi = sorted([a, b])
    assert pairs[(pairs["a"] == lo) & (pairs["b"] == hi)].empty  # precondition, independently checked
    assert CL.pulse(ctx, a, b) is None


def _load_pairs_raw(ctx):
    return pd.read_parquet(Path(ctx["data_dir"]) / "collab_pairs.parquet")


def _load_raw_pair_fields():
    return pd.read_parquet(Path(__file__).resolve().parents[1] / "data" / "collab_pair_fields.parquet")


def test_field_breakdown_matches_collab_pair_fields_anchor(ctx):
    """RE-DERIVED: `vol_total`
    -> `vol` (rebased all-types/2020-2025 -> CORE-AR articles+reviews/2020-
    2024) and `mean_citations` DROPPED entirely, superseded by `fwci_median`
    (SS2.2 dropped_column note). Independent anchor, re-read RAW off
    `collab_pair_fields.parquet` (also cross-referenced against
    an OpenAlex-diagnostic-verified `computed_vol`/
    `computed_n_top10`/`computed_n_covered` for this exact pair/field, see
    `test_golden_numbers.py`): CNRS x Strasbourg's largest joint field
    (field_id 31, Physics and Astronomy) -- vol 1643 (was 1882 under the
    wider all-types/2020-2025 basis -- the exact
    'joint 1,882 vs covered 1,642' mismatch class, now resolved: vol and
    n_covered are on the SAME basis), n_top10 383 (UNCHANGED -- impact
    eligibility was already articles+reviews-restricted upstream), n_covered
    1642 (UNCHANGED), fwci_median 0.7711243033409119."""
    raw = _load_raw_pair_fields()
    lo, hi = sorted([CNRS, STRASBOURG])
    raw_row = raw[(raw["a"] == lo) & (raw["b"] == hi) & (raw["field_id"] == 31)].iloc[0]
    assert int(raw_row["vol"]) == 1643
    assert int(raw_row["n_top10"]) == 383
    assert int(raw_row["n_covered"]) == 1642
    assert "mean_citations" not in raw.columns  # dropped entirely, not renamed (SS2.2)
    np.testing.assert_allclose(float(raw_row["fwci_median"]), 0.7711243033409119, rtol=1e-6)

    df = CL.field_breakdown(ctx, CNRS, STRASBOURG)
    assert list(df.columns) == CL.FIELD_BREAKDOWN_COLS
    assert "mean_citations" not in df.columns
    row = df[df["field_id"] == 31].iloc[0]
    assert int(row["vol"]) == 1643
    assert int(row["n_top10"]) == 383
    assert int(row["n_covered"]) == 1642
    np.testing.assert_allclose(float(row["fwci_median"]), 0.7711243033409119, rtol=1e-6)
    assert row["field_name"] == "Physics and Astronomy"
    assert df.attrs["note"] == CL.FIELD_BREAKDOWN_NOTE
    assert df.attrs["floor"] == CL.PAIR_TOPICS_FLOOR
    assert (df["n_top10"] <= df["n_covered"]).all()
    assert (df["n_covered"] <= df["vol"]).all()
    assert df["vol"].is_monotonic_decreasing


def test_field_breakdown_carries_fwci_mean_and_n_fwci(ctx):
    """`collab_pair_fields.parquet`'s two newest columns survive
    `field_breakdown` untouched: n_fwci >= n_covered on every row (the FWCI
    population is a superset of the top-decile-eligible one), and field
    31's own anchor value matches a raw read."""
    raw = _load_raw_pair_fields()
    lo, hi = sorted([CNRS, STRASBOURG])
    raw_row = raw[(raw["a"] == lo) & (raw["b"] == hi) & (raw["field_id"] == 31)].iloc[0]

    df = CL.field_breakdown(ctx, CNRS, STRASBOURG)
    assert "fwci_mean" in df.columns and "n_fwci" in df.columns
    row = df[df["field_id"] == 31].iloc[0]
    np.testing.assert_allclose(float(row["fwci_mean"]), float(raw_row["fwci_mean"]), rtol=1e-6)
    assert int(row["n_fwci"]) == int(raw_row["n_fwci"])
    assert (df["n_fwci"] >= df["n_covered"]).all()


def test_field_breakdown_empty_below_floor(ctx):
    """A pair below PAIR_TOPICS_FLOOR (or that never co-published) gets an
    empty, correctly-columned frame -- never raises."""
    df = CL.field_breakdown(ctx, "I1305429183", "I1308570094")
    assert list(df.columns) == CL.FIELD_BREAKDOWN_COLS
    assert len(df) == 0


def test_field_breakdown_arrows_and_urls(ctx):
    """Every row carries an arrow in the fixed vocabulary and a live
    OpenAlex url that names both institutions and this field."""
    df = CL.field_breakdown(ctx, CNRS, STRASBOURG)
    assert len(df)
    assert set(df["arrow"]) <= {CL.ARROW_UP, CL.ARROW_DOWN, CL.ARROW_FLAT}
    row31 = df[df["field_id"] == 31].iloc[0]
    from urllib.parse import unquote
    decoded = unquote(row31["url"])
    assert f"authorships.institutions.id:{CNRS}" in decoded
    assert f"authorships.institutions.id:{STRASBOURG}" in decoded
    assert "primary_topic.field.id:31" in decoded


def test_arrow_deadband_hand_recomputed():
    """Independent recompute of `_arrow`'s own formula: mean-annual w2 vs w1
    (windows of 2 and 3 years respectively), deadband 0.5 works/year."""
    assert CL._arrow(30, 20) == CL.ARROW_FLAT   # w1=10.0/yr, w2=10.0/yr -> delta 0.0
    assert CL._arrow(30, 30) == CL.ARROW_UP     # w1=10.0/yr, w2=15.0/yr -> delta +5.0
    assert CL._arrow(60, 20) == CL.ARROW_DOWN   # w1=20.0/yr, w2=10.0/yr -> delta -10.0
    assert CL._arrow(3, 1) == CL.ARROW_DOWN     # w1=1.0/yr, w2=0.5/yr -> delta -0.5, AT the deadband (not <, so it counts)


def test_gaps_and_top10_subfield_ids_are_gone():
    """-11(f): the deleted footprint-gap table leaves no trace."""
    assert not hasattr(CL, "gaps")
    assert not hasattr(CL, "GAPS_COLS")
    assert not hasattr(CL, "_top10_subfield_ids")


def test_topics_together_and_untapped_builders_are_gone():
    """The "topics-together" (`joint_profile`)
    and "Untapped potential" (`untapped`/`shared_topics`) sections and every
    symbol that solely backed them leave no trace."""
    for name in ("joint_profile", "untapped", "shared_topics",
                 "JOINT_TOPICS_COLS", "JOINT_ROLLUP_VALUE_COLS", "MEAN_CITATIONS_NOTE",
                 "UNTAPPED_COLS", "SHARED_TOPICS_COLS",
                 "_joint_vol_by_topic", "_load_collab_pair_topics", "_load_collab_topic_vols",
                 "_topic_subfield_map", "_topic_keywords_map", "_label_topics"):
        assert not hasattr(CL, name), f"{name} should have been deleted"


# ============================================================================
# `pair_domain_year` -- the
# Relationship block's joint-publications-by-domain-and-year chart data,
# read off the NEW `collab_pair_domain_year.parquet`. Anchors independently
# recomputed straight off `collab_pairs.parquet`.
# ============================================================================

IFREMER, NIOZ = "I154202486", "I4210107283"


def test_pair_domain_year_dtypes_and_sort(ctx):
    df = CL.pair_domain_year(ctx, IFREMER, NIOZ)
    assert list(df.columns) == ["a", "b", "domain_id", "year", "vol"]
    assert not df.empty
    assert df["a"].dtype.name == "category" and df["b"].dtype.name == "category"
    assert df["domain_id"].dtype == np.int8
    assert df["year"].dtype == np.int16
    assert df["vol"].dtype == np.int32
    assert list(df.sort_values(["year", "domain_id"]).index) == list(df.index)  # already sorted a,b,year,domain


def test_pair_domain_year_sum_equals_core_total_ifremer_nioz(ctx):
    """Sigma(vol) over ALL domain x year rows for this
    qualifying pair equals `collab_pairs.core_total` exactly -- the
    upstream rollup's own invariant, re-verified here through the module's
    public accessor."""
    df = CL.pair_domain_year(ctx, IFREMER, NIOZ)
    pairs = _load_pairs_raw(ctx)
    lo, hi = sorted([IFREMER, NIOZ])
    core_total = int(pairs[(pairs["a"] == lo) & (pairs["b"] == hi)].iloc[0]["core_total"])
    assert int(df["vol"].sum()) == core_total


def test_pair_domain_year_order_invariant(ctx):
    """Same re-orientation contract as every other table in this module:
    calling with (a, b) swapped returns the identical rows (up to the a/b
    column labels themselves following the CALLER's order internally, since
    the table has no per-side asymmetric column)."""
    fwd = CL.pair_domain_year(ctx, IFREMER, NIOZ)
    bwd = CL.pair_domain_year(ctx, NIOZ, IFREMER)
    assert int(fwd["vol"].sum()) == int(bwd["vol"].sum())
    assert len(fwd) == len(bwd)


def test_pair_domain_year_empty_for_non_qualifying_pair(ctx):
    """Two small, unrelated institutions with no collab_pairs row at all
    (same precondition as `test_pulse_none_for_a_pair_that_never_co_published`)
    get an empty, correctly-columned frame -- never raise."""
    df = CL.pair_domain_year(ctx, "I1305429183", "I1308570094")
    assert list(df.columns) == ["a", "b", "domain_id", "year", "vol"]
    assert len(df) == 0


# ============================================================================
# reciprocity_frame -- D27's new per-field columns (x/y/joint_vol are the
# pre-existing, byte-identical invariant -- see tests/test_compare_data.py's
# own golden-equal test).
# ============================================================================

def test_reciprocity_frame_new_columns_present_and_consistent(ctx, subs_bestfit):
    df = CL.reciprocity_frame(ctx, subs_bestfit, STRASBOURG, CNRS)
    assert list(df.columns) == CL.RECIPROCITY_COLS
    assert len(df) > 0
    assert (df["n_fwci"] >= df["n_covered"]).all()
    # a pair-level fact -- the SAME rank on every field row
    assert df["rank_in_a"].nunique() == 1
    assert df["rank_in_b"].nunique() == 1
    # re-oriented exactly like pulse's own rank_in_a/rank_in_b
    pulse = CL.pulse(ctx, STRASBOURG, CNRS)
    assert int(df["rank_in_a"].iloc[0]) == pulse["rank_in_a"]
    assert int(df["rank_in_b"].iloc[0]) == pulse["rank_in_b"]


def test_reciprocity_frame_sum_of_stars_over_all_fields_within_two_of_pair_stars(ctx, subs_bestfit):
    """`leaders_data.pair_stars_by_field`'s own total, summed over every
    field `reciprocity_frame` actually carries, matches `leaders_data.
    pair_stars` up to the small cross-table vintage drift `tests/
    test_compare_golden_anchors.py`'s own hand-recompute already documents
    for the Ifremer x NIOZ anchor pair (a joint star work's field, off the
    CURRENT topics_dim, absent from `collab_pair_fields`'s own -- older --
    field set)."""
    from lib import leaders_data as LD

    df = CL.reciprocity_frame(ctx, subs_bestfit, STRASBOURG, CNRS)
    total_pair_stars = LD.pair_stars(ctx, STRASBOURG, CNRS)
    diff = total_pair_stars - int(df["n_stars_field"].sum())
    assert 0 <= diff <= 5, diff


def test_reciprocity_frame_empty_below_floor(ctx, subs_bestfit):
    df = CL.reciprocity_frame(ctx, subs_bestfit, "I1305429183", "I1308570094")
    assert list(df.columns) == CL.RECIPROCITY_COLS
    assert len(df) == 0


# ============================================================================
# momentum_evidence -- the always-visible evidence line's value-driven
# classification (D27), independent of `mom_class`. `FACTS` mirrors
# `collab_facts.json`'s own shape (the real file's values, so a test here
# reads exactly like the production call) -- every threshold `momentum_
# evidence` uses comes from this dict, never a literal in the function body.
# ============================================================================

FACTS = {"band": 0.25, "alpha": 0.05, "new_min_c2": 5, "dormant_min_c1": 5, "weak_base_max": 4}


def test_momentum_evidence_new_state_c2_at_or_above_new_min_c2():
    ev = CL.momentum_evidence({"c1": 0.0, "c2": 7.0}, FACTS)
    assert ev == {"state": "new", "c2_mean": 4}   # round(7/2=3.5) -> 4 (round-half-to-even)


def test_momentum_evidence_thin_ns_when_c1_zero_and_c2_below_new_min_c2():
    """An 'ns' row with NEITHER a rate nor a p-value (c1==0, but too little
    since for "new" either) -- its own state and sentence, distinct from
    "new" (live-verified: ~1.13M of the 1,450,358 'ns' rows on `app/data/
    collab_pairs.parquet` are exactly this shape)."""
    assert CL.momentum_evidence({"c1": 0.0, "c2": 3.0}, FACTS) == {"state": "thin_ns"}
    assert CL.momentum_evidence({"c1": 0.0, "c2": 1.0}, FACTS) == {"state": "thin_ns"}


def test_momentum_evidence_dormant_requires_c1_at_or_above_dormant_min_c1():
    """A c1 BELOW the floor with c2==0 is "thin" ("weak"), not "dormant" --
    matching the upstream ladder's OWN `dormant = c2==0 AND
    c1>=dormant_min_c1` definition, not merely "checked before weak"."""
    assert CL.momentum_evidence({"c1": 1.0, "c2": 0.0}, FACTS) == {"state": "thin"}
    assert CL.momentum_evidence({"c1": 6.0, "c2": 0.0}, FACTS) == {"state": "dormant", "c1_mean": 2}


def test_momentum_evidence_thin_base_at_or_below_weak_base_max():
    ev = CL.momentum_evidence({"c1": 2.0, "c2": 5.0}, FACTS)
    assert ev == {"state": "thin"}


def test_momentum_evidence_stable_band_reads_its_own_sentence_state_not_significance():
    """A rate INSIDE the +-band (here: 0.9706 for band=0.25, so the band is
    (0.8, 1.25)) reads sig="stable_band" regardless of mom_p (always null
    for real 'stable' rows, but the band check itself never looks at p)."""
    ev = CL.momentum_evidence({"c1": 30.0, "c2": 30.0, "mom_rr": 0.9706419110298157, "mom_p": None}, FACTS)
    assert ev["state"] == "numeric" and ev["sig"] == "stable_band" and ev["band_pct"] == "25"
    assert ev["pct"] == "\N{MINUS SIGN}3 %"


def test_momentum_evidence_numeric_significant_and_not_significant():
    sig = CL.momentum_evidence({"c1": 30.0, "c2": 30.0, "mom_rr": 1.5, "mom_p": 0.01}, FACTS)
    assert sig["state"] == "numeric" and sig["sig"] == "significant" and sig["pct"] == "+50 %"
    not_sig = CL.momentum_evidence({"c1": 30.0, "c2": 30.0, "mom_rr": 1.5, "mom_p": 0.40}, FACTS)
    assert not_sig["sig"] == "not_significant"


def test_momentum_evidence_numeric_no_test_when_outside_the_band_with_no_p():
    """A directional rate (outside the +-band) with no p-value at all --
    unreached in the live data (every such row always carries one), kept as
    a defensive, never-crashing fallback."""
    ev = CL.momentum_evidence({"c1": 30.0, "c2": 30.0, "mom_rr": 1.5, "mom_p": None}, FACTS)
    assert ev["state"] == "numeric" and ev["sig"] == "no_test"


def test_momentum_evidence_clamps_extreme_ratios():
    ev = CL.momentum_evidence({"c1": 10.0, "c2": 10.0, "mom_rr": 12.0, "mom_p": 0.01}, FACTS)
    assert ev["pct"] == "> +999 %"


def test_momentum_evidence_pct_uses_a_true_minus_sign_never_a_hyphen():
    ev = CL.momentum_evidence({"c1": 30.0, "c2": 30.0, "mom_rr": 0.5, "mom_p": 0.01}, FACTS)
    assert ev["pct"].startswith("\N{MINUS SIGN}")
    assert "-" not in ev["pct"]   # no ASCII hyphen-minus anywhere in the signed text


def test_momentum_evidence_matches_live_ns_and_stable_populations(ctx):
    """Live cross-check (`app/data/collab_pairs.parquet`): an 'ns' row that
    carries a real mom_rr/mom_p (a demoted up/down candidate) reads
    "numeric" with a real significance verdict (never "stable_band", since a
    demoted candidate was an up/down CANDIDATE precisely because its rr sat
    OUTSIDE the band); a 'stable' row (mom_p always null upstream) reads
    "numeric, stable_band"."""
    facts = CL._load_collab_facts(ctx)
    pairs = _load_pairs_raw(ctx)
    ns_with_rr = pairs[(pairs["mom_class"] == "ns") & pairs["mom_p"].notna()].iloc[0]
    ev = CL.momentum_evidence(ns_with_rr.to_dict(), facts)
    assert ev["state"] == "numeric" and ev["sig"] in ("significant", "not_significant")

    stable = pairs[pairs["mom_class"] == "stable"].iloc[0]
    assert pd.isna(stable["mom_p"])
    ev2 = CL.momentum_evidence(stable.to_dict(), facts)
    assert ev2["state"] == "numeric" and ev2["sig"] == "stable_band"
