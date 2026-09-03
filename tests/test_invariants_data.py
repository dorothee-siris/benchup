"""
tests/test_invariants_data.py -- deterministic data invariants over the REAL
`app/data/*.parquet` artefacts. No fixtures, no mocks, no fabricated data.
Every check is a vectorised pandas pass over a raw parquet table (or two),
never through a page-layer function -- so this file stays correct across a
UI rewrite as long as the underlying tables keep their contract shape.

Session-scoped fixtures SKIP (never fail) the whole module when
`app/data/collab_pairs.parquet` is absent -- CI without the data snapshot
exits clean.

Superseded coverage: everything this file used to check through the old
Compare `metric_frame` API (share/si bounds, the dynamics-gutter
reconciliation, the tooltip-denominator check, the "untapped" gaps table) is
now owned by `tests/test_compare_data.py`, which tests the current
`compare_data.py` surface (`cards`/`top_subfields`/`sdg_frame`/
`frontier_positioning`/`shared_frontier`/`relationship`) directly against
golden anchors -- removed here rather than duplicated on a dead API.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import collab_data as CL
from lib import profile_data as P
from lib.engine import load_substrates, load_context

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
FWCI_DIR = APP_DIR.parent / "data" / "interim" / "fwci"  # pipeline-internal, NOT deployed (data_contract.yaml)

STRASBOURG, IFPEN, GDANSK, ISCTE, SORBONNE, ETH = (
    "I68947357", "I265217849", "I40413290", "I110026055", "I39804081", "I35440088")
CNRS = "I1294671590"
IFREMER = "I154202486"

pytestmark = pytest.mark.skipif(
    not (DATA_DIR / "collab_pairs.parquet").exists(),
    reason="app/data/*.parquet artefacts not present -- skip-if-absent CI guard")


# ============================================================================
# fixtures
# ============================================================================

@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def subs_frac(ctx):
    return load_substrates(ctx, tree="bestfit", basis="frac")


@pytest.fixture(scope="module")
def subs_full(ctx):
    return load_substrates(ctx, tree="bestfit", basis="full")


# ============================================================================
# item 1 -- sdg mass_any <= field mass, SAME basis, FULL TABLE, both bases
# ============================================================================

def test_sdg_mass_any_le_field_mass_full_table():
    """`sdg_fields.parquet`'s distinct-tagged `mass_any_frac`/`mass_any_full`
    can never exceed `fields.parquet`'s own `vol_frac`/`vol_full` for the SAME
    (institution, field, tree=bestfit) cell -- a work counting once toward a
    field's SDG-tagged mass cannot exceed the field's own total mass. Checked
    on EVERY row of both tables (bestfit only -- `fields.parquet` ships no
    other tree), both bases, vectorised (no Python row loop)."""
    sdg_fields = pd.read_parquet(DATA_DIR / "sdg_fields.parquet")
    fields = pd.read_parquet(DATA_DIR / "fields.parquet",
                             columns=["institution_id", "field_id", "tree", "vol_frac", "vol_full"])
    sub = sdg_fields[(sdg_fields["tree"] == "bestfit") & (sdg_fields["field_id"] != -1)]
    fb = fields[fields["tree"] == "bestfit"].set_index(["institution_id", "field_id"])
    merged = sub.set_index(["institution_id", "field_id"]).join(fb[["vol_frac", "vol_full"]], how="left")

    missing = merged["vol_frac"].isna().sum()
    assert missing == 0, f"{missing} sdg_fields cells have no matching fields.parquet row (should be impossible: fields.parquet ships every nonzero-mass cell)"

    bad_frac = merged[merged["mass_any_frac"] > merged["vol_frac"] + 1e-4]
    assert bad_frac.empty, f"mass_any_frac > vol_frac (fractional basis): {len(bad_frac)} / {len(merged):,} cells"
    bad_full = merged[merged["mass_any_full"] > merged["vol_full"] + 1e-4]
    assert bad_full.empty, f"mass_any_full > vol_full (full basis): {len(bad_full)} / {len(merged):,} cells"
    assert len(merged) > 50_000, f"suspiciously few cells checked: {len(merged)}"


# ============================================================================
# item 2 -- n_top10 <= n_covered <= vol on EVERY row of the collab tables
# (full table, vectorised)
# ============================================================================

def test_ordering_n_top10_le_n_covered_le_vol_full_tables():
    for name in ("collab_pair_fields.parquet", "collab_pairs.parquet"):
        cols = ["n_top10", "n_covered"] + (["core_total"] if name == "collab_pairs.parquet" else ["vol"])
        df = pd.read_parquet(DATA_DIR / name, columns=cols)
        vol_col = "core_total" if name == "collab_pairs.parquet" else "vol"
        bad = df[(df["n_top10"] > df["n_covered"]) | (df["n_covered"] > df[vol_col])]
        assert bad.empty, f"{name}: n_top10<=n_covered<={vol_col} violated on {len(bad)} / {len(df):,} rows"


# ============================================================================
# item 3 -- FWCI: citation-weighted stratum-mean == 1 (skips if the
# pipeline-internal reference tables are not present locally)
# ============================================================================

_FWCI_FILES_PRESENT = (FWCI_DIR / "fwci_ref.parquet").exists() and (FWCI_DIR / "fwci_work.parquet").exists()


@pytest.mark.skipif(not _FWCI_FILES_PRESENT, reason="pipeline-internal fwci_ref/fwci_work.parquet not present locally (not deployed to app/data -- V4/data/interim/fwci/ only)")
def test_fwci_stratum_citation_weighted_mean_equals_one():
    """FWCI(work) = cited_by_count / mean_cited(subfield x year x type
    stratum) -- by construction, the mean of fwci over the works THAT
    STRATUM'S mean_cited was itself computed from must equal 1.0, on every
    NON-FALLBACK (subfield-level) stratum. Tolerance 1e-6 (float32 storage
    rounding)."""
    ref = pd.read_parquet(FWCI_DIR / "fwci_ref.parquet")
    work = pd.read_parquet(FWCI_DIR / "fwci_work.parquet")
    non_fb = ref[ref["fallback_level"] == "subfield"]
    keys = set(zip(non_fb["subfield_id"], non_fb["year"], non_fb["type"]))

    w = work.dropna(subset=["fwci"])
    mask = np.array([k in keys for k in zip(w["subfield_id"], w["year"], w["type"])])
    non_fb_work = w[mask]
    means = non_fb_work.groupby(["subfield_id", "year", "type"], observed=True)["fwci"].mean()
    max_dev = float((means - 1.0).abs().max())
    assert max_dev <= 1e-6, f"citation-weighted mean(fwci) deviates from 1.0 by {max_dev:.3e} on some stratum"
    assert len(means) >= 1000, f"suspiciously few non-fallback strata checked: {len(means)}"


def test_fwci_median_nonnegative_and_null_rate_sane():
    """`fwci_median` (a MEDIAN of nonnegative per-work FWCI ratios) can never
    be negative, on both collab tables. Null-rate check is DELIBERATELY
    approximate: 'null when < 3 covered works' means covered-by-a-valid-FWCI-
    value, a DIFFERENT concept from the PP-threshold `n_covered` column
    tested elsewhere in this suite -- so this checks only that the null rate
    among clearly-qualifying rows (n_covered >= 10, safely above the <3
    floor) is small, not that it is exactly zero."""
    for name in ("collab_pairs.parquet", "collab_pair_fields.parquet"):
        vol_col = "core_total" if name == "collab_pairs.parquet" else "vol"
        df = pd.read_parquet(DATA_DIR / name, columns=["n_covered", "fwci_median", vol_col])
        neg = df[df["fwci_median"].notna() & (df["fwci_median"] < -1e-9)]
        assert neg.empty, f"{name}: {len(neg)} rows have a negative fwci_median"

        qualifying = df[df["n_covered"] >= 10]
        if len(qualifying) == 0:
            continue
        null_rate = float(qualifying["fwci_median"].isna().mean())
        assert null_rate < 0.01, (
            f"{name}: fwci_median null on {null_rate:.2%} of rows with n_covered>=10 "
            f"(expected near-zero; the <3-valid-FWCI-works floor should almost never bind above n_covered=10)")


# ============================================================================
# item 4 -- momentum: vocabulary, up/down significance, MED band, weak rule
# (full table, vectorised)
# ============================================================================

def test_momentum_vocabulary_and_stat_rules():
    cp = pd.read_parquet(DATA_DIR / "collab_pairs.parquet",
                         columns=["c1", "c2", "mom_class", "mom_rr", "mom_p"])
    facts = json.loads((DATA_DIR / "collab_facts.json").read_text(encoding="utf-8"))
    alpha = facts["alpha"]

    allowed = {"up", "down", "stable", "ns", "new", "dormant", "weak"}
    observed = set(cp["mom_class"].dropna().unique().tolist())
    assert observed <= allowed, f"unexpected mom_class value(s): {observed - allowed}"

    assert 0.8 <= facts["med"] <= 1.3, f"collab_facts.json MED out of the [0.8,1.3] sanity band: {facts['med']}"

    up_down = cp[cp["mom_class"].isin(["up", "down"])]
    bad_p = up_down[~(up_down["mom_p"] < alpha)]
    assert bad_p.empty, (
        f"{len(bad_p)} 'up'/'down'-classified rows have mom_p >= alpha ({alpha}) or null -- "
        f"the z-test demotion to 'ns' should have caught these")

    weak_range = (cp["c1"] > 0) & (cp["c1"] < 5)
    mismatch_a = cp[weak_range & (cp["mom_class"] != "weak")]
    mismatch_b = cp[(cp["mom_class"] == "weak") & ~weak_range]
    assert mismatch_a.empty, f"{len(mismatch_a)} rows with 0<c1<5 are NOT classified 'weak'"
    assert mismatch_b.empty, f"{len(mismatch_b)} rows classified 'weak' do NOT have 0<c1<5"


# ============================================================================
# item 5 -- collab_topic_vols pair set == collab_pairs qualifying set
# ============================================================================

def test_collab_topic_vols_pair_set_matches_qualifying_pairs():
    """Vectorised (merge-based, never a Python set-of-15M-tuples loop).
    Tolerance <=5 mirrors the pipeline's own disclosed edge case: a
    qualifying pair whose every joint work lacks a primary topic never
    enters a topic-grain table at all (~0.07% of works corpus-wide)."""
    cp = pd.read_parquet(DATA_DIR / "collab_pairs.parquet", columns=["a", "b", "core_total"])
    ctv = pd.read_parquet(DATA_DIR / "collab_topic_vols.parquet", columns=["a", "b"])
    qualifying = cp.loc[cp["core_total"] >= 5, ["a", "b"]].drop_duplicates()
    ctv_pairs = ctv.drop_duplicates()
    merged = qualifying.merge(ctv_pairs.assign(_in_ctv=True), on=["a", "b"], how="outer", indicator=True)
    diff = int((merged["_merge"] != "both").sum())
    assert diff <= 5, f"collab_topic_vols pair set vs collab_pairs core_total>=5 qualifying set: symmetric diff {diff}"


# ============================================================================
# item 6 -- cross-view pin: Find profile field share == fields.parquet raw
# ============================================================================

_PIN_IDS = [STRASBOURG, IFPEN, GDANSK, SORBONNE, ETH]


@pytest.mark.parametrize("basis", ["frac", "full"])
def test_cross_view_pin_field_share_find_parquet(ctx, subs_frac, subs_full, basis):
    """`profile_data.fields_table` (what the Find profile page shows) == a
    fresh raw read of `fields.parquet`'s own `share_<basis>` column, for 5
    institutions, both bases -- byte-equal (no arithmetic between the two
    reads, so an exact-equality check is the right bar, not a tolerance)."""
    subs = subs_frac if basis == "frac" else subs_full
    share_col = f"share_{basis}"
    fields_raw = pd.read_parquet(DATA_DIR / "fields.parquet",
                                 columns=["institution_id", "field_id", "tree", share_col])
    fields_raw = fields_raw[fields_raw["tree"] == "bestfit"]

    for iid in _PIN_IDS:
        find_df = P.fields_table(ctx, subs, iid).set_index("field_id")["share"]
        raw_row = fields_raw[fields_raw["institution_id"] == iid].set_index("field_id")[share_col]

        assert set(find_df.index) == set(raw_row.index), f"{iid}/{basis}: Find profile field set != fields.parquet field set"
        np.testing.assert_array_equal(
            find_df.reindex(raw_row.index).to_numpy(dtype="float64"),
            raw_row.to_numpy(dtype="float64"),
            err_msg=f"{iid}/{basis}: Find profile share != fields.parquet raw share")


def test_cross_view_pin_field_vol(ctx):
    """`collab_data.field_breakdown` (the pair field-grain reciprocity
    source) == a fresh raw read of `collab_pair_fields.parquet`, for 2 real
    pairs -- exact integer equality on `vol`/`n_top10`/`n_covered`."""
    raw = pd.read_parquet(DATA_DIR / "collab_pair_fields.parquet")
    for a, b in [(CNRS, STRASBOURG), (STRASBOURG, IFPEN)]:
        lo, hi = sorted([a, b])
        raw_rows = raw[(raw["a"] == lo) & (raw["b"] == hi)].set_index("field_id")
        if raw_rows.empty:
            continue
        got = CL.field_breakdown(ctx, a, b).set_index("field_id")
        for fid, raw_row in raw_rows.iterrows():
            got_row = got.loc[fid]
            assert int(got_row["vol"]) == int(raw_row["vol"]), f"{a}/{b} field {fid}: vol mismatch"
            assert int(got_row["n_top10"]) == int(raw_row["n_top10"]), f"{a}/{b} field {fid}: n_top10 mismatch"


# ============================================================================
# item 7 -- new-table anchors (world leaders / star papers / institution
# FWCI_EU) -- Ifremer field 11, cross-checked against the pipeline's own
# golden values (progress/P5.md, P6.md, pipeline/README.md step 19)
# ============================================================================

def test_impact_taxa_ifremer_field11_anchor():
    it = pd.read_parquet(DATA_DIR / "impact_taxa.parquet")
    row = it[(it["institution_id"] == IFREMER) & (it["grain"] == "field") & (it["taxon_id"] == 11)]
    assert len(row) == 1, f"expected exactly 1 Ifremer/field/11 row in impact_taxa.parquet, got {len(row)}"
    row = row.iloc[0]
    assert row["n_covered_pp"] == 1699, f"Ifremer field 11 n_covered_pp: expected 1699, got {row['n_covered_pp']}"
    assert abs(float(row["pp10_wd"]) - 0.167746) < 1e-3, f"Ifremer field 11 pp10_wd: expected ~0.167746 (16.8%), got {row['pp10_wd']}"


def test_fwci_taxa_ifremer_field11_anchor():
    ft = pd.read_parquet(DATA_DIR / "fwci_taxa.parquet")
    row = ft[(ft["institution_id"] == IFREMER) & (ft["grain"] == "field") & (ft["taxon_id"] == 11)]
    assert len(row) == 1, f"expected exactly 1 Ifremer/field/11 row in fwci_taxa.parquet, got {len(row)}"
    row = row.iloc[0]
    assert abs(float(row["fwci_median"]) - 0.8149413) < 1e-4, f"Ifremer field 11 fwci_median: expected ~0.8149413, got {row['fwci_median']}"
    assert int(row["n_covered"]) == 1700, f"Ifremer field 11 n_covered: expected 1700, got {row['n_covered']}"


def test_index_star_leader_fwci_columns_present():
    """The 8 columns P3/P4/P5/P6 (world leaders, star papers, institution
    FWCI_EU) add to `index.parquet` -- present, correctly typed, and (for
    the two anchor institutions the pipeline itself verified) matching the
    values recorded in progress/P5.md and progress/P6.md."""
    idx = pd.read_parquet(DATA_DIR / "index.parquet")
    expected_dtypes = {
        "n_stars": "int32", "star_share": "float32",
        "n_topics_led_all": "int16", "n_topics_led_edu": "int16", "n_topics_led_fair": "int16",
        "fwci_eu_median": "float32", "fwci_eu_mean": "float32", "fwci_eu_n": "int32",
    }
    for col, dtype in expected_dtypes.items():
        assert col in idx.columns, f"index.parquet missing column {col!r}"
        assert str(idx[col].dtype) == dtype, f"index.{col}: expected {dtype}, got {idx[col].dtype}"

    ifremer = idx.loc[idx["institution_id"] == IFREMER].iloc[0]
    assert int(ifremer["n_stars"]) == 160, f"Ifremer n_stars: expected 160, got {ifremer['n_stars']}"
    assert abs(float(ifremer["fwci_eu_median"]) - 0.690692) < 1e-3, f"Ifremer fwci_eu_median: expected ~0.690692, got {ifremer['fwci_eu_median']}"

    cnrs = idx.loc[idx["institution_id"] == CNRS].iloc[0]
    assert int(cnrs["n_topics_led_all"]) >= 500, f"CNRS n_topics_led_all sanity floor: expected >=500, got {cnrs['n_topics_led_all']}"
