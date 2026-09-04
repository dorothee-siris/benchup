"""tests/test_contract_collab_tables.py -- collaboration-table additions to the data contract.

Covers what test_contract.py's existing test_contract_check_clean does NOT pin explicitly:
the collaboration tables' exact column sets, the new index columns' bounds, pool_excluded's
count, collab_pairs' a<b uniqueness, and the ratio-window rule -- the two window strings must
appear verbatim in the contract text, guarding against a future edit silently dropping which
window a share divides by (the generalised form of a real defect once found this way: an
"ERC-classified share" reading 109%).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONTRACT_PATH = ROOT / "docs" / "data_contract.yaml"

NEW_TABLES = [
    "collab_pairs.parquet",
    "collab_pair_fields.parquet",   # pair x field, uncapped, bestfit-only
    "sdg_fields.parquet",
    "sdg_year.parquet",
    # impact_fields.parquet REMOVED: dead,
    # deleted from app/data + contract.
]


@pytest.fixture(scope="module")
def contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def contract_text() -> str:
    return CONTRACT_PATH.read_text(encoding="utf-8")


def _read(fname: str) -> pd.DataFrame:
    path = DATA_DIR / fname
    return pd.read_csv(path) if path.suffix == ".csv" else pd.read_parquet(path)


# ---------------------------------------------------------------------------
# 1. every contracted table (new + the new overrides file) exists in app/data
#    with EXACTLY the contracted columns
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fname", NEW_TABLES)
def test_new_table_exists_with_exact_columns(contract: dict, fname: str) -> None:
    assert fname in contract["files"], f"{fname} is not declared in data_contract.yaml"
    path = DATA_DIR / fname
    assert path.is_file(), f"{fname} missing from app/data/ -- deploy not run since PC's edits?"
    df = _read(fname)
    declared = {c["name"] for c in contract["files"][fname]["columns"]}
    actual = set(df.columns)
    assert actual == declared, (
        f"{fname}: column mismatch -- declared-only {declared - actual}, "
        f"file-only {actual - declared}"
    )


def test_contract_declares_25_files(contract: dict) -> None:
    # History of this count (each step live-verified against the deploy
    # step's own printed total, not typed in twice): ... -> 23 ->
    # 22 (impact_fields.parquet deleted, dead, superseded by impact_taxa.parquet)
    # -> 27 (contract v1.5): five new tables -- collab_pair_domain_year.parquet,
    # topic_leaders.parquet, topics_led.parquet, inst_stars.parquet,
    # pair_stars.parquet (world leaders, star papers, the yearly pair x domain
    # rollup) -> 23 (contract v1.6): impact_cells.parquet and
    # collab_pair_topics.parquet deleted (dead, no code path read either);
    # type_overrides.csv and pool_exclusions.csv moved to a private build
    # tree (the app never read them at run time either) -> 25 (contract v1.7):
    # two new tables -- inst_topic_impact.parquet (institution x primary-topic
    # impact) and star_works.parquet (the per-work star-paper table); none
    # dropped. `collab_facts.json` (momentum constants) and the build-internal
    # `fwci_ref.parquet`/`fwci_work.parquet` do NOT join this count -- all are
    # DELIBERATELY excluded from `contract["files"]` by the contract's own
    # documented design (not a parquet table this app/data/ directory ships
    # with a column schema to check). `data/scenarios/` (the ranking engine's
    # precomputed substrates) is ALSO not counted here -- it is validated
    # separately via `contract["scenario_files"]`, since its members are not
    # one-row-per-key tables.
    assert len(contract["files"]) == 25, sorted(contract["files"])


# ---------------------------------------------------------------------------
# 2. intl_share / company_share in app/data/index.parquet: [0,1], 0 nulls
# ---------------------------------------------------------------------------

def test_intl_company_share_bounds() -> None:
    idx = _read("index.parquet")
    for col in ("intl_share", "company_share"):
        s = idx[col]
        n_null = int(s.isna().sum())
        print(f"index.{col}: nulls={n_null}, range=[{s.min():.6f}, {s.max():.6f}]")
        assert n_null == 0, f"index.{col} has {n_null} null(s)"
        assert s.min() >= -1e-9, f"index.{col} min {s.min()} < 0"
        assert s.max() <= 1 + 1e-9, f"index.{col} max {s.max()} > 1"


# ---------------------------------------------------------------------------
# 3. pool_excluded: exactly 3 True (the exclusion list itself is a private
#    build-tree input, not shipped with the app -- see docs/data_contract.yaml)
# ---------------------------------------------------------------------------

def test_pool_excluded_exactly_three() -> None:
    idx = _read("index.parquet")
    flagged = set(idx.loc[idx["pool_excluded"] == True, "institution_id"])  # noqa: E712
    print(f"index.pool_excluded True: {len(flagged)} -- {sorted(flagged)}")
    assert len(flagged) == 3


# ---------------------------------------------------------------------------
# 4. collab_pairs: a<b, unique (sampled -- full check would be 3.58M string
#    comparisons, fine at this size but sampled to keep this file fast)
# ---------------------------------------------------------------------------

def test_collab_pairs_a_lt_b_and_unique() -> None:
    pairs = _read("collab_pairs.parquet")
    n_dupes = int(pairs.duplicated(subset=["a", "b"]).sum())
    print(f"collab_pairs.parquet: {len(pairs):,} rows, {n_dupes} duplicate (a,b) key(s)")
    assert n_dupes == 0

    sample = pairs.sample(n=min(50_000, len(pairs)), random_state=42)
    # 2E: a/b are unordered category dtype (repack) -- string comparison for
    # the ordering check, same values, no dtype-driven behaviour change.
    n_violations = int((sample["a"].astype(str) >= sample["b"].astype(str)).sum())
    print(f"a<b sample check: {n_violations} violation(s) of {len(sample):,} sampled rows")
    assert n_violations == 0


def test_collab_pair_fields_uncapped_and_within_floor() -> None:
    """`collab_pair_fields.parquet` carries NO per-pair cap (every field the
    pair has any joint mass in ships) -- a pair spans a mean of ~4 fields
    (WT #13), so uncapped never approaches a 100-row order of magnitude; this
    is a structural guard against that ratio drifting, not a hardcoded
    row-count pin."""
    pairs = _read("collab_pairs.parquet").set_index(["a", "b"])
    fields = _read("collab_pair_fields.parquet")
    per_pair_n = fields.groupby(["a", "b"], observed=True).size()
    print(f"collab_pair_fields: {len(per_pair_n):,} distinct pairs, "
          f"mean fields/pair={per_pair_n.mean():.2f}, max={per_pair_n.max()}")
    # Uncapped, but a "field" is a coarse taxon -- OA has 26 -- so it can
    # never exceed that no matter how large the pair's joint corpus is.
    assert per_pair_n.max() <= 26, "collab_pair_fields must never exceed the field taxonomy's own size"

    sample_pairs = per_pair_n.sample(n=min(2_000, len(per_pair_n)), random_state=42).index
    below_floor = sum(1 for a, b in sample_pairs if pairs.loc[(a, b), "copubs_total"] < 5)
    print(f"floor-5 sample check (fields): {below_floor} of {len(sample_pairs)} sampled pairs below floor")
    assert below_floor == 0


# ---------------------------------------------------------------------------
# 5. the ratio-window rule: the two SDG/core window strings appear verbatim
#    in the contract text, both in window_conventions AND on the columns that
#    actually use them -- guards against a future edit dropping the window name.
# ---------------------------------------------------------------------------

CORE_WINDOW = "2020-2024 (core window)"
SDG_MASS_WINDOW = "2020-2025 (SDG mass basis, six-year)"


def test_window_conventions_declared(contract: dict) -> None:
    wc = contract.get("window_conventions")
    assert wc is not None, "data_contract.yaml is missing the window_conventions block"
    assert wc["core_window"] == CORE_WINDOW
    assert wc["sdg_mass_window"] == SDG_MASS_WINDOW
    assert "dynamics_window_1" in wc and "dynamics_window_2" in wc


def test_window_strings_appear_verbatim_on_the_columns_that_use_them(contract_text: str) -> None:
    # core_window: intl_share and company_share
    assert contract_text.count(CORE_WINDOW) >= 3, (
        "CORE_WINDOW string must appear on window_conventions + intl_share + company_share "
        "at minimum -- a drop here silently un-names a denominator's window"
    )
    # sdg_mass_window: sdg.parquet.share, sdg.parquet.mass, sdg_fields.mass, sdg_year.mass
    assert contract_text.count(SDG_MASS_WINDOW) >= 5, (
        "SDG_MASS_WINDOW string must appear on window_conventions + sdg.share + sdg.mass + "
        "sdg_fields.mass + sdg_year.mass at minimum"
    )


def test_type_overrides_count_is_41_not_stale(contract: dict) -> None:
    """A prior pass flagged the contract's own '34 rows' text as stale (41 after the
    7 gated-type resolutions); this pins the fix. The identity check against the
    shipped CSV moved with overrides/type_overrides.csv to a private build tree,
    which the app no longer reads."""
    spec = contract["files"]["index.parquet"]["type_overrides"]
    assert spec["n_ids"] == 41
    assert len(spec["institution_ids"]) == 41
    # NOTE: a raw substring search for the stale "34" was tried and dropped, it also matches
    # this file's own v1.2 changelog prose explaining the fix (e.g. "34 + 7 gated-type
    # resolutions"), which is correct narration, not a live spec value, and would make this
    # test permanently red for the wrong reason.
