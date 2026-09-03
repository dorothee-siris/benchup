"""
 lib/profile_data.py acceptance tests (.3/S9.4).
Run: python -m pytest tests/test_profile_data.py -q
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import profile_data as P
from lib.engine import load_context, load_substrates

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SEEDS = ["I40413290", "I265217849", "I39804081"]  # Gdansk, IFPEN, Sorbonne
YEARLY_SEEDS = ["I40413290", "I265217849", "I39804081", "I277688954", "I68947357"]


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def subs_bestfit(ctx):
    return load_substrates(ctx)  # default: bestfit / frac


@pytest.fixture(scope="module")
def subs_original(ctx):
    return load_substrates(ctx, tree="original", basis="frac")


@pytest.fixture(scope="module")
def subs_full(ctx):
    return load_substrates(ctx, tree="bestfit", basis="full")


def _parse_packed(s: str) -> dict:
    return {int(k): float(v) for k, v in (tok.split(":") for tok in s.split("|"))}


# ------------------------------------------------------------ fields/subs ---

@pytest.mark.parametrize("seed_id", SEEDS)
def test_fields_table_columns_and_share_sum(ctx, subs_bestfit, seed_id):
    df = P.fields_table(ctx, subs_bestfit, seed_id)
    assert list(df.columns) == P.FIELDS_COLS
    assert abs(df["share"].astype("float64").sum() - 1.0) <= 1e-6
    assert len(df) > 0


@pytest.mark.parametrize("seed_id", SEEDS)
def test_subfields_table_columns_and_share_sum(ctx, subs_bestfit, seed_id):
    df = P.subfields_table(ctx, subs_bestfit, seed_id)
    assert list(df.columns) == P.SUBFIELDS_COLS
    assert abs(df["share"].astype("float64").sum() - 1.0) <= 1e-6


@pytest.mark.parametrize("seed_id", SEEDS)
def test_subfields_table_si_status_thresholds_and_unfloored_si(ctx, subs_bestfit, seed_id):
    """si_status thresholds are exact on `vol_frac` (a direct
    recount from the frame), and si is now DEFINED (unfloored) for every
    solid/thin row -- only "none" rows may still be NaN. Where the frame's
    own ratified-floor si IS defined (vol_frac >= 30), our recomputed si is
    numerically identical to it (same formula, same population)."""
    df = P.subfields_table(ctx, subs_bestfit, seed_id)
    vol = df["vol_frac"].astype("float64")
    solid = vol >= P.SI_FLOOR_SOLID
    thin = (vol >= P.SI_FLOOR_THIN) & ~solid
    none_ = ~solid & ~thin
    assert solid.any(), f"{seed_id}: no solid subfield to test against"
    assert thin.any(), f"{seed_id}: no thin subfield to test against"
    assert (df.loc[solid, "si_status"] == "solid").all()
    assert (df.loc[thin, "si_status"] == "thin").all()
    assert (df.loc[none_, "si_status"] == "none").all()
    assert df.loc[solid | thin, "si"].notna().all(), \
        f"{seed_id}: a solid/thin subfield has a missing (unfloored) si"

    raw = subs_bestfit["subfields_df"]
    raw_row = raw[raw["institution_id"] == seed_id]
    merged = df.merge(raw_row[["subfield_id", "si"]], on="subfield_id", suffixes=("", "_floored"))
    have_floored = merged["si_floored"].notna()
    assert have_floored.any(), f"{seed_id}: no at/above-ratified-floor subfield to test the identity against"
    np.testing.assert_allclose(
        merged.loc[have_floored, "si"].astype("float64"),
        merged.loc[have_floored, "si_floored"].astype("float64"),
        rtol=1e-5,
    )


@pytest.mark.parametrize("seed_id", SEEDS)
def test_fields_table_si_status(ctx, subs_bestfit, seed_id):
    """Fields carry no floor at all (data_contract.yaml) -- solid
    whenever vol_frac > 0 and si is defined, "thin" never appears at this
    grain."""
    df = P.fields_table(ctx, subs_bestfit, seed_id)
    assert set(df["si_status"]) <= {"solid", "none"}
    want_solid = (df["vol_frac"].astype("float64") > 0) & df["si"].notna()
    assert (df["si_status"] == np.where(want_solid, "solid", "none")).all()


def test_fields_table_follows_the_tree(ctx, subs_bestfit, subs_original):
    """bug #5: fields_table under `original` differs from
    `bestfit` for at least one of 3 seeds."""
    any_diff = False
    for seed_id in SEEDS:
        bf = P.fields_table(ctx, subs_bestfit, seed_id).set_index("field_id")["share"]
        orig = P.fields_table(ctx, subs_original, seed_id).set_index("field_id")["share"]
        both = bf.index.union(orig.index)
        bf, orig = bf.reindex(both, fill_value=0.0), orig.reindex(both, fill_value=0.0)
        if (np.abs(bf.to_numpy(dtype="float64") - orig.to_numpy(dtype="float64")) > 1e-6).any():
            any_diff = True
    assert any_diff, "fields_table is identical under bestfit and original for all 3 seeds"


# ------------------------------------------------------------------ topics

@pytest.mark.parametrize("seed_id", SEEDS)
def test_topics_table_columns(ctx, subs_bestfit, seed_id):
    df = P.topics_table(ctx, subs_bestfit, seed_id)
    assert list(df.columns) == P.TOPICS_COLS
    assert len(df) > 0
    assert df["topic_name"].notna().all()
    assert df["subfield_id"].notna().all()  # every topic resolves through the fixed map


@pytest.mark.parametrize("seed_id", SEEDS)
def test_topics_table_rank_volume_unique_1_to_n(ctx, subs_bestfit, seed_id):
    """L33 top-200-by-volume mode: rank_volume is a unique permutation of
    1.n, 1 = largest volume on the CURRENT basis, ties broken by topic_id."""
    df = P.topics_table(ctx, subs_bestfit, seed_id)
    n = len(df)
    assert sorted(df["rank_volume"].tolist()) == list(range(1, n + 1))
    top = df.loc[df["rank_volume"] == 1].iloc[0]
    assert top["vol_frac"] == df["vol_frac"].max()


def test_topics_table_share_matches_topics_all_direct_recompute_both_bases(ctx, subs_bestfit, subs_full):
    """An earlier change removed `substrates._topic_share_values`; `topics_table` now reads
    the same values off `subs['l3']['share']` (its precomputed dense matrix)
    instead -- proven here against an INDEPENDENT recompute straight off
    `topics_all.parquet` (frac = `share_frac` verbatim; full = vol_full over
    this institution's own vol_full total), for one seed on both bases."""
    seed_id = "I40413290"
    ta = pd.read_parquet(DATA_DIR / "topics_all.parquet",
                         columns=["institution_id", "topic_id", "share_frac", "vol_full"])
    mine = ta[ta["institution_id"] == seed_id].set_index("topic_id")
    want_frac, want_full = mine["share_frac"], mine["vol_full"] / mine["vol_full"].sum()
    got_frac = P.topics_table(ctx, subs_bestfit, seed_id).set_index("topic_id")["share"]
    got_full = P.topics_table(ctx, subs_full, seed_id).set_index("topic_id")["share"]
    np.testing.assert_allclose(got_frac.reindex(want_frac.index).astype("float64"),
                               want_frac.astype("float64"), rtol=1e-5)
    np.testing.assert_allclose(got_full.reindex(want_full.index).astype("float64"),
                               want_full.astype("float64"), rtol=1e-5)


def test_topics_table_rank_volume_follows_basis(ctx, subs_full):
    """basis='full' ranks by vol_full, not vol_frac -- the two can disagree."""
    df = P.topics_table(ctx, subs_full, "I40413290")
    order = df.sort_values(["vol_full", "topic_id"], ascending=[False, True])["topic_id"].tolist()
    got = df.sort_values("rank_volume")["topic_id"].tolist()
    assert order == got


# ------------------------------------------------------------ yearly trend

@pytest.mark.parametrize("seed_id", YEARLY_SEEDS)
def test_yearly_by_domain_matches_index_by_year(ctx, subs_bestfit, seed_id):
    """Sigma over domains per year vs index.vol_full_by_year_this_run.
    MEASURED: `yearly_by_domain` reproduces topics_all's
    own per-topic vol_full/vol_frac columns EXACTLY (verified by a direct
    Sigma over topics_all with no domain join) but topics_all itself is
    systematically a FEW WORKS SHORT of the index's by-year bookkeeping
    total per (seed, year) -- up to 32 works / 0.23% relative on the worst
    seed measured (Sorbonne, 2020). This is a real, small, pre-existing
    artefact-level gap (topics_all's topic grain vs the run's raw by-year
    count), not a join bug here -- reported with a documented tolerance,
    never silently forced to equality ( spirit)."""
    # Update: the gap above is now carried explicitly as an
    # "Unclassified" domain row per year (P.UNCLASSIFIED_DOMAIN_ID), so the domain
    # view sums to the SAME per-year total as the document-type view (both = the
    # index's by-year bookkeeping) -- the swap between the two never changes a
    # total. Exact on full counts; float32-tolerant on fractional.
    row = ctx["index_by_id"].loc[seed_id]
    want_full = _parse_packed(row["vol_full_by_year_this_run"])
    want_frac = _parse_packed(row["vol_frac_by_year_this_run"])
    yb = P.yearly_by_domain(ctx, seed_id, subs_bestfit["tree"])
    got_full = yb.groupby("year")["vol_full"].sum()
    got_frac = yb.groupby("year")["vol_frac"].sum()
    uncl = yb[yb["domain_id"] == P.UNCLASSIFIED_DOMAIN_ID]
    assert len(uncl) == yb["year"].nunique(), f"{seed_id}: one Unclassified row per year expected"
    assert (uncl["vol_full"] >= 0).all() and (uncl["vol_frac"] >= 0).all(), f"{seed_id}: negative residual"
    for year, want in want_full.items():
        got = float(got_full.get(year, 0.0))
        print(f"[yearly] {seed_id}/{year}: got={got} want={want} unclassified={float(uncl.loc[uncl['year'] == year, 'vol_full'].sum())}")
        assert int(round(got)) == int(round(want)), f"{seed_id}/{year}: full total {got} != index {want}"
        gf, wf = float(got_frac.get(year, 0.0)), float(want_frac.get(year, 0.0))
        assert abs(gf - wf) <= max(1e-6 * wf, 1e-3), f"{seed_id}/{year}: frac total {gf} != index {wf}"


def test_yearly_by_domain_columns_and_empty_shape(ctx, subs_bestfit):
    df = P.yearly_by_domain(ctx, "I40413290", subs_bestfit["tree"])
    assert list(df.columns) == P.YEARLY_COLS
    assert len(df) > 0


# --------------------------------------------------------------- SDG / ERC

@pytest.mark.parametrize("seed_id", SEEDS)
def test_sdg_table_dense_16_rows(ctx, seed_id):
    df = P.sdg_table(ctx, seed_id)
    assert list(df.columns) == P.SDG_COLS
    assert len(df) == 16
    assert set(df["sdg_number"]) == set(range(1, 17))
    assert ((df["share"].isna()) | ((df["share"] >= 0) & (df["share"] <= 1))).all()


@pytest.mark.parametrize("seed_id", SEEDS)
def test_sdg_table_numbered_labels_and_si_status(ctx, seed_id):
    """L36: sdg_label_numbered is present for all 16 rows and its number/dot
    are exactly the row's own sdg_number/sdg_label (never a copy-typed
    string). L34: si_status thresholds the fractional `mass` column."""
    df = P.sdg_table(ctx, seed_id)
    assert df["sdg_label_numbered"].notna().all()
    want = "SDG " + df["sdg_number"].astype(str) + " · " + df["sdg_label"].astype(str)
    assert (df["sdg_label_numbered"] == want).all()
    mass = df["mass"].astype("float64")
    want_status = np.select([mass >= P.SI_FLOOR_SOLID, mass >= P.SI_FLOOR_THIN],
                             ["solid", "thin"], default="none")
    assert (df["si_status"] == want_status).all()


@pytest.mark.parametrize("seed_id", SEEDS)
def test_erc_table_columns_and_labels(ctx, seed_id):
    df = P.erc_table(ctx, seed_id)
    assert list(df.columns) == P.ERC_COLS
    if len(df):
        assert df["panel_code"].notna().all()
        assert set(df["erc_domain"].unique()) <= {"LS", "PE", "SH"}


def test_erc_table_si_status_thresholds(ctx):
    """si_status thresholds exact on `mass` -- direct recount against
    P.SI_FLOOR_SOLID/_THIN for a seed with enough ERC-classified mass to
    exercise all three buckets."""
    seed_id = "I40413290"  # Gdansk
    df = P.erc_table(ctx, seed_id)
    mass = df["mass"].astype("float64")
    want = np.select([mass >= P.SI_FLOOR_SOLID, mass >= P.SI_FLOOR_THIN],
                      ["solid", "thin"], default="none")
    assert (df["si_status"] == want).all()
    counts = df["si_status"].value_counts().to_dict()
    print(f"[erc si_status] {seed_id}: {counts}")


# ---------------------------------------------------------------- wordcloud

@pytest.mark.parametrize("seed_id", SEEDS)
def test_wordcloud_weights_shape(ctx, subs_bestfit, seed_id):
    weights, domains = P.wordcloud_weights(ctx, subs_bestfit, seed_id)
    assert set(weights) == set(domains)
    assert weights, f"{seed_id}: empty wordcloud"
    assert all(v > 0 for v in weights.values())
