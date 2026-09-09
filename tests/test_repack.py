"""tests/test_repack.py -- dtype contract gate for the deployed app data.

Pins the RAM-fit repack (an offline build step) as a standing contract on
every deployed `app/data/*.parquet`: ID/label columns load as `category`, no `float64`
column survives anywhere, and `impact_fields.parquet` stays gone. Data-driven, no
fixtures -- reads app/data/ directly, so it
automatically covers every new table the upstream build adds at the top level of app/data/
(no per-table edit needed here when a table is added, only the count pin below).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

ID_COLUMNS = ("institution_id", "a", "b", "topic_id")

PARQUET_FILES = sorted(p.name for p in DATA_DIR.glob("*.parquet"))

# topics_dim's three list<double> period-array columns, and star_works.parquet's
# work_id/topic_id/inst_ids (v1.7: shipped as a straight byte copy of its own source
# table, never round-tripped through the repack's dtype-normalising pass), are the
# sanctioned object-dtype holdouts (topics_dim's for unhashable numpy-array values --
# category cast would fail; star_works.parquet's per its own contract entry).
KNOWN_OBJECT_HOLDOUTS = {
    ("topics_dim.parquet", "expansion_by_period"),
    ("topics_dim.parquet", "acceleration_by_period"),
    ("topics_dim.parquet", "frontier_score_by_period"),
    ("star_works.parquet", "work_id"),
    ("star_works.parquet", "topic_id"),
    ("star_works.parquet", "inst_ids"),
}


def test_impact_fields_deleted() -> None:
    assert not (DATA_DIR / "impact_fields.parquet").exists(), (
        "impact_fields.parquet is dead (no code path reads it) and must stay deleted from app/data"
    )


def test_deployed_table_count_is_25() -> None:
    assert len(PARQUET_FILES) == 24, sorted(PARQUET_FILES)  # 24 parquet + 1 override csv = 25 (contract v1.8)


@pytest.mark.parametrize("fname", PARQUET_FILES)
def test_id_columns_are_category(fname: str) -> None:
    df = pd.read_parquet(DATA_DIR / fname, columns=None)
    for col in ID_COLUMNS:
        if col in df.columns and (fname, col) not in KNOWN_OBJECT_HOLDOUTS:
            assert str(df[col].dtype) == "category", (
                f"{fname}.{col}: expected category, got {df[col].dtype}"
            )


@pytest.mark.parametrize("fname", PARQUET_FILES)
def test_no_float64_columns(fname: str) -> None:
    df = pd.read_parquet(DATA_DIR / fname)
    float64_cols = [c for c in df.columns if str(df[c].dtype) == "float64"]
    assert float64_cols == [], f"{fname}: float64 columns survived repack: {float64_cols}"


@pytest.mark.parametrize("fname", PARQUET_FILES)
def test_object_columns_are_only_known_holdouts(fname: str) -> None:
    df = pd.read_parquet(DATA_DIR / fname)
    object_cols = [c for c in df.columns if str(df[c].dtype) == "object"]
    unexpected = [c for c in object_cols if (fname, c) not in KNOWN_OBJECT_HOLDOUTS]
    assert unexpected == [], f"{fname}: unexpected object-dtype column(s) after repack: {unexpected}"


