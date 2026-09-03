"""
tests/test_countries.py -- lib/countries.py acceptance tests.
Run: python -m pytest tests/test_countries.py -q
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from lib import countries

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def index_codes():
    df = pd.read_parquet(DATA_DIR / "index.parquet")
    return sorted(df["country_code"].astype(str).unique())


def test_every_index_code_is_covered(index_codes):
    missing = [c for c in index_codes if c not in countries.NAMES]
    assert not missing, f"countries_en.csv is missing code(s): {missing}"


def test_no_empty_name_for_any_index_code(index_codes):
    for c in index_codes:
        nm = countries.name(c)
        assert nm and nm.strip(), f"{c} resolved to an empty name"


def test_unknown_code_falls_back_to_the_code_itself():
    assert countries.name("ZZ") == "ZZ"


def test_namibia_survives_the_na_string_trap():
    # Proves the keep_default_na=False guard: pandas' default NA-string
    # sniffing would otherwise silently turn the literal "NA" into a missing
    # value on CSV read -- the trap a real Namibia row would hit.
    assert countries.NAMES.get("NA") == "Namibia"
    assert countries.name("NA") == "Namibia"


def test_a_sample_of_real_names():
    assert countries.name("GB") == "United Kingdom"
    assert countries.name("CZ") == "Czechia"
    assert countries.name("GR") == "Greece"
    assert countries.name("NL") == "Netherlands"
    assert countries.name("CH") == "Switzerland"


def test_name_strips_and_uppercases_input():
    assert countries.name(" fr ") == "France"


def test_none_and_empty_input_return_empty_string():
    assert countries.name(None) == ""
    assert countries.name("") == ""
