"""tests/test_repack.py -- dtype contract gate for the deployed app data.

Pins the RAM-fit repack (`pipeline/20_repack_app_data.py`) as a standing contract on
every deployed `app/data/*.parquet`: ID/label columns load as `category`, no `float64`
column survives anywhere, and `impact_fields.parquet` stays gone. Data-driven, no
fixtures -- reads app/data/ directly, so it
automatically covers every new table the pipeline adds at the top level of app/data/
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

# topics_dim's three list<double> period-array columns are the sole sanctioned
# object-dtype holdout (unhashable numpy-array values -- category cast would fail).
KNOWN_OBJECT_HOLDOUTS = {
    ("topics_dim.parquet", "expansion_by_period"),
    ("topics_dim.parquet", "acceleration_by_period"),
    ("topics_dim.parquet", "frontier_score_by_period"),
}


def test_impact_fields_deleted() -> None:
    assert not (DATA_DIR / "impact_fields.parquet").exists(), (
        "impact_fields.parquet is dead (no code path reads it) and must stay deleted from app/data"
    )


def test_deployed_table_count_is_23() -> None:
    assert len(PARQUET_FILES) == 22, sorted(PARQUET_FILES)  # 22 parquet + 1 override csv = 23


@pytest.mark.parametrize("fname", PARQUET_FILES)
def test_id_columns_are_category(fname: str) -> None:
    df = pd.read_parquet(DATA_DIR / fname, columns=None)
    for col in ID_COLUMNS:
        if col in df.columns:
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


