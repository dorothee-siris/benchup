"""tests/test_contract.py -- Class-1 data-contract invariants over app/data/ (run with cwd=app/).

Covers: contract_check.check() clean (every declared file/column/dtype/key present, no
undeclared drop); fields/subfields shares sum to 1; erc.share sums <= 1; sdg.share per-row
bounds; topics_dim exclusion reason-code coverage; index PP confidence-interval ordering;
umbrella_supplement.csv shape. The type-override identity check moved with
overrides/type_overrides.csv to a private build tree, which the app no longer reads.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONTRACT_PATH = ROOT / "docs" / "data_contract.yaml"

sys.path.insert(0, str(ROOT / "ops"))
from contract_check import check  # noqa: E402


@pytest.fixture(scope="module")
def contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def _read(fname: str) -> pd.DataFrame:
    path = DATA_DIR / fname
    if path.suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_parquet(path)


def test_contract_check_clean(contract: dict) -> None:
    """Every declared file present, every declared column/dtype/key verified, no undeclared
    drop vs source_manifest.json's table_schemas. This single check covers 11 tables (9 parquet
    + 2 override csv) since R1's doctype_by_year.parquet addition (contract_version 1.1)."""
    violations = check(DATA_DIR, contract)
    assert violations == [], "\n".join(violations)


def test_fields_shares_sum_to_one() -> None:
    fields = _read("fields.parquet")
    for col in ("share_frac", "share_full"):
        s = fields.groupby("institution_id", observed=True)[col].sum().astype("float64")
        max_dev = float((s - 1).abs().max())
        print(f"fields.{col}: max|sum-1| over {len(s)} institutions = {max_dev:.3e}")
        assert max_dev <= 1e-6


def test_subfields_shares_sum_to_one() -> None:
    subfields = _read("subfields.parquet")
    for col in ("share_frac", "share_full"):
        s = subfields.groupby("institution_id", observed=True)[col].sum().astype("float64")
        max_dev = float((s - 1).abs().max())
        print(f"subfields.{col}: max|sum-1| over {len(s)} institutions = {max_dev:.3e}")
        assert max_dev <= 1e-6


def test_erc_share_sum_le_one() -> None:
    erc = _read("erc.parquet")
    s = erc.groupby("institution_id", observed=True)["share"].sum().astype("float64")
    print(f"erc.share sum per institution: max={s.max():.7f}, min={s.min():.7f}, n={len(s)}")
    assert s.max() <= 1 + 1e-6


def test_sdg_share_bounds_per_row() -> None:
    sdg = _read("sdg.parquet")
    lo, hi = float(sdg["share"].min()), float(sdg["share"].max())
    print(f"sdg.share per-row range over {len(sdg)} rows: [{lo}, {hi}]")
    assert lo >= 0 - 1e-6
    assert hi <= 1 + 1e-6
    per_inst_sum = sdg.groupby("institution_id", observed=True)["share"].sum().astype("float64")
    print(f"sdg.share sum per institution (multi-label, NOT bounded by 1): max={per_inst_sum.max():.4f}")


def test_topics_dim_exclusion_reason_codes() -> None:
    td = _read("topics_dim.parquet")
    excluded = td[td["is_excluded"] == True]  # noqa: E712
    non_excluded = td[td["is_excluded"] == False]  # noqa: E712
    print(f"topics_dim: {len(excluded)} excluded (811-list), {len(non_excluded)} not excluded")
    assert excluded["exclusion_reason_code"].notna().all()
    assert non_excluded["exclusion_reason_code"].isna().all()


def test_index_ci_ordering() -> None:
    idx = _read("index.parquet")
    mask = idx["pp_top10_frac"].notna()
    sub = idx.loc[mask]
    ok_low = (sub["pp_ci_low"] <= sub["pp_top10_frac"] + 1e-6).all()
    ok_high = (sub["pp_top10_frac"] <= sub["pp_ci_high"] + 1e-6).all()
    print(f"index CI ordering over {mask.sum()}/{len(idx)} non-null rows: low<=pp {ok_low}, pp<=high {ok_high}")
    assert ok_low and ok_high


def test_umbrella_supplement_shape() -> None:
    supp = _read("overrides/umbrella_supplement.csv")
    print(f"umbrella_supplement.csv: {len(supp)} rows, columns={list(supp.columns)}")
    assert list(supp.columns) == ["display_name", "institution_id", "note"]
    assert len(supp) >= 24


def test_doctype_by_year_keys_unique_and_typed() -> None:
    """Class-1 invariant: (institution_id, year, doc_type) unique; doc_type restricted to
    the harvest's 5 server-side-filtered types; year within the shipped 2020-2025 window."""
    dt = _read("doctype_by_year.parquet")
    n_dupes = int(dt.duplicated(subset=["institution_id", "year", "doc_type"]).sum())
    print(f"doctype_by_year.parquet: {len(dt):,} rows, {n_dupes} duplicate key(s)")
    assert n_dupes == 0
    allowed_types = {"article", "review", "book", "book-chapter", "letter"}
    other_types = set(dt["doc_type"].astype(str).unique()) - allowed_types
    print(f"doc_type values outside the 5-type allowlist: {other_types}")
    assert other_types == set()
    assert dt["year"].min() >= 2020 and dt["year"].max() <= 2025
    assert (dt["vol_full"] >= 0).all()
    assert (dt["vol_frac"] >= -1e-6).all()


def test_doctype_by_year_sum_matches_index_by_year() -> None:
    """Class-1 invariant, spot-checked on 3 institutions from the deployed app/data/ (the full
    7,557 x 6 = 45,342-cell check is run separately as part of the upstream build --
    this test is the CI-speed subset)."""
    dt = _read("doctype_by_year.parquet")
    idx = _read("index.parquet")

    def _parse_packed(s: str) -> dict[int, float]:
        return {int(y): float(v) for y, v in (p.split(":") for p in s.split("|"))} if s else {}

    sample_ids = idx["institution_id"].iloc[[0, len(idx) // 2, len(idx) - 1]].tolist()
    checked = 0
    for iid in sample_ids:
        row = idx.loc[idx["institution_id"] == iid].iloc[0]
        full_packed = _parse_packed(row["vol_full_by_year_this_run"])
        frac_packed = _parse_packed(row["vol_frac_by_year_this_run"])
        sub = dt[dt["institution_id"] == iid]
        for year, expected_full in full_packed.items():
            got_full = int(sub.loc[sub["year"] == year, "vol_full"].sum())
            assert got_full == int(round(expected_full)), (
                f"{iid} year={year}: doctype_by_year Sigma(vol_full)={got_full} != "
                f"index.vol_full_by_year_this_run={expected_full}"
            )
            expected_frac = frac_packed.get(year, 0.0)
            got_frac = float(sub.loc[sub["year"] == year, "vol_frac"].sum())
            rel = abs(got_frac - expected_frac) / max(abs(expected_frac), 1e-9)
            assert rel <= 1e-6 or abs(got_frac - expected_frac) <= 1e-3, (
                f"{iid} year={year}: doctype_by_year Sigma(vol_frac)={got_frac} != "
                f"index.vol_frac_by_year_this_run={expected_frac} (rel={rel:.2e})"
            )
            checked += 1
    print(f"doctype_by_year vs index by-year: {checked} (institution, year) cells matched exactly, "
          f"{len(sample_ids)} institutions")
    assert checked > 0


# ---------------------------------------------------------------------------
# After an "ERC-classified share
# 109 %" defect: every coverage ratio the profile shows is
# a ratio of two INDEX columns, so its 0..1 bound is a Class-1 invariant here,
# not a UI courtesy. A share above 1 is a defect (mixed time windows or
# populations), never a caveat.
# ---------------------------------------------------------------------------

def test_index_coverage_ratios_are_bounded():
    idx = pd.read_parquet(Path(__file__).resolve().parents[1] / "data" / "index.parquet")
    tol = 1e-6
    erc_over_total = idx["erc_classified_mass_frac"] / idx["total_frac"]
    assert erc_over_total.notna().all()
    assert (erc_over_total <= 1 + tol).all(), f"ERC-classified / total_frac max {erc_over_total.max()}"
    assert (idx["erc_classified_mass_frac"] <= idx["erc_eligible_mass_frac"] * (1 + tol)).all()
    assert (idx["total_frac_2020_2024"] <= idx["total_frac"] * (1 + tol)).all(), \
        "the analytical-window total must never exceed the whole-run total"
    for col in ("sdg_tagged_share", "frontier_top25_share", "frontier_excluded_share",
                "frontier_unscored_share", "pp_top10_frac", "pp_ci_low", "pp_ci_high"):
        s = idx[col].dropna()
        assert ((s >= -tol) & (s <= 1 + tol)).all(), f"{col} outside [0, 1]: min {s.min()} max {s.max()}"
