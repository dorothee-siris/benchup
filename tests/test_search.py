"""
 search.py acceptance tests.
Run: python -m pytest tests/test_search.py -q
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from lib.search import build_search_index, search

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def idx():
    index_df = pd.read_parquet(DATA_DIR / "index.parquet")
    return build_search_index(index_df)


def _top_id(query, idx_, k=10):
    hits = search(query, idx_, k=k)
    assert hits, f"no hits for {query!r}"
    return hits[0]["id"]


def test_gdansk_ascii_top1(idx):
    assert _top_id("gdansk", idx) == "I40413290"


def test_gdansk_accented_top1(idx):
    assert _top_id("Gdańsk", idx) == "I40413290"


def test_gdansk_seven_institutions_match(idx):
    # k=7 exactly meets the primary-tier hit count, so the fuzzy fallback
    # (triggered whenever fewer than k hits are found) never kicks in here.
    hits = search("gdansk", idx, k=7)
    assert len({h["id"] for h in hits}) == 7, [h["id"] for h in hits]


def test_ifpen_top1(idx):
    assert _top_id("IFPEN", idx) == "I265217849"


def test_sorbone_typo_within_top3(idx):
    hits = search("sorbone", idx, k=10)
    top3 = [h["id"] for h in hits[:3]]
    assert "I39804081" in top3, top3


def test_one_institution_id_appears_once(idx):
    hits = search("gdansk", idx, k=50)
    ids = [h["id"] for h in hits]
    assert len(ids) == len(set(ids))


def test_empty_query_returns_nothing(idx):
    assert search("", idx) == []
