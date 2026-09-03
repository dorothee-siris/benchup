"""
 lib/baselines.py acceptance tests (.2 L31,
S10.4). Run: python -m pytest tests/test_baselines.py -q
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import baselines as B

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def index_df():
    return pd.read_parquet(DATA_DIR / "index.parquet")


@pytest.fixture(scope="module")
def bl(index_df):
    return B.build(index_df)


def test_every_kpi_resolves_on_the_real_index(index_df, bl):
    """Every KPI_COLUMNS entry resolves without error and yields at least
    one non-null value on the real deployed index."""
    for kpi in B.KPI_COLUMNS:
        assert kpi in bl
        assert bl[kpi]["n"] > 0, f"{kpi}: zero non-null values in the index"


@pytest.mark.parametrize("kpi", list(B.KPI_COLUMNS))
def test_n_equals_non_null_count(index_df, bl, kpi):
    values = B._kpi_values(index_df, kpi).astype("float64")
    assert bl[kpi]["n"] == int(values.notna().sum())


@pytest.mark.parametrize("kpi", list(B.KPI_COLUMNS))
def test_median_equals_pandas_series_median(index_df, bl, kpi):
    values = B._kpi_values(index_df, kpi).astype("float64")
    want = values.median()  # pandas skips NaN by default
    got = bl[kpi]["median"]
    if pd.isna(want):
        assert pd.isna(got)
    else:
        assert abs(got - float(want)) <= 1e-9


@pytest.mark.parametrize("kpi", list(B.KPI_COLUMNS))
def test_percentile_in_0_1(index_df, bl, kpi):
    values = B._kpi_values(index_df, kpi).astype("float64").dropna()
    n = len(values)
    assert n == bl[kpi]["n"]
    sample = values.sample(min(50, n), random_state=0)
    for v in sample:
        p = B.percentile(bl, kpi, v)
        assert p is not None
        assert 0.0 <= p <= 1.0


@pytest.mark.parametrize("kpi", list(B.KPI_COLUMNS))
def test_percentile_of_median_is_about_half(index_df, bl, kpi):
    """percentile counts values STRICTLY BELOW `value`, so
    percentile(median) sits within the EXACT bracket
    [rank_left/n, (rank_left + ties_at_median)/n] -- for a low-cardinality,
    heavily-tied KPI (e.g. breadth_subfields, a small integer with a huge
    point mass at 0/1) that bracket can be wide, so the tie count itself
    bounds the tolerance instead of a fixed +-1/n guess."""
    values = B._kpi_values(index_df, kpi).astype("float64").dropna()
    n = len(values)
    med = bl[kpi]["median"]
    p_med = B.percentile(bl, kpi, med)
    assert p_med is not None
    ties_at_median = int((values == med).sum())
    tol = max(1.0 / n, (ties_at_median + 1) / n)
    assert abs(p_med - 0.5) <= tol, \
        f"{kpi}: percentile(median)={p_med} too far from 0.5 (n={n}, ties={ties_at_median})"


def test_percentile_none_on_null_value(bl):
    assert B.percentile(bl, "hhi_subfield", None) is None
    assert B.percentile(bl, "hhi_subfield", float("nan")) is None


def test_stats_shape(bl):
    for kpi in B.KPI_COLUMNS:
        s = B.stats(bl, kpi)
        assert set(s) == {"median", "n"}
        assert isinstance(s["n"], int)


def test_bonus_year_full_matches_packed_string(index_df):
    """bonus_year_full is parsed from vol_full_by_year_this_run for
    CFG['bonus_year'] -- not a hardcoded year (L10)."""
    from lib.app_config import CFG
    from lib.profile_data import _parse_packed_years

    year = int(CFG["bonus_year"])
    got = B._bonus_year_full(index_df)
    sample = index_df.sample(min(30, len(index_df)), random_state=1)
    for i in sample.index:
        packed = index_df.loc[i, "vol_full_by_year_this_run"]
        want = _parse_packed_years(packed).get(year, np.nan)
        g = got.loc[i]
        if pd.isna(want):
            assert pd.isna(g)
        else:
            assert g == want


def test_ifpen_hhi_percentile_matches_manager_probe(index_df, bl):
    """Manager fact (2026-08-29): IFPEN (I265217849) hhi_subfield=507 sits at
    p40 of the index; median 602. A loose corridor -- this is a coherence
    cross-check on the real baselines, not a golden-file pin."""
    row = index_df.set_index("institution_id").loc["I265217849"]
    hhi = float(row["hhi_subfield"])
    p = B.percentile(bl, "hhi_subfield", hhi)
    assert p is not None
    assert 0.35 <= p <= 0.45, f"IFPEN hhi percentile {p} outside the expected p40 corridor"
