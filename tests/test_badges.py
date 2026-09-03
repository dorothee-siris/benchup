"""
 badges.py acceptance tests, plus the CSV export round-trip and
the copy.py digit-ban self-check. Run: python -m pytest tests/test_badges.py -q
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

from lib import badges, copy, exports

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SUPPLEMENT_PATH = DATA_DIR / "overrides" / "umbrella_supplement.csv"


@pytest.fixture(scope="module")
def index_df():
    return pd.read_parquet(DATA_DIR / "index.parquet")


def test_umbrella_flags_zero_education_and_covers_most_supplement(index_df):
    flags = badges.umbrella_flags(index_df)
    flagged = int(flags.sum())

    edu_ids = index_df.loc[index_df["type"].astype(str) == "education", "institution_id"]
    education_flagged = int(flags.reindex(edu_ids.to_numpy()).fillna(False).sum())

    supplement = pd.read_csv(SUPPLEMENT_PATH)
    hits, misses = [], []
    for _, row in supplement.iterrows():
        (hits if bool(flags.get(row["institution_id"], False)) else misses).append(row["display_name"])

    print(f"umbrella flagged (total): {flagged}")
    print(f"umbrella flagged among education rows (must be 0): {education_flagged}")
    print(f"supplement hits: {len(hits)}/{len(supplement)}")
    if misses:
        print("supplement misses:", "; ".join(m.encode('ascii', 'replace').decode() for m in misses))

    assert education_flagged == 0
    assert len(hits) >= 20, f"only {len(hits)}/{len(supplement)} supplement names flagged"


def test_corrected_from_returns_the_original_type_sciences_po(index_df):
    """-1a: the function returns the BARE original type -- the "was:" half
    of the inline identity form -- not a badge sentence."""
    row = index_df.loc[index_df["institution_id"] == "I205092303"].iloc[0]
    assert badges.corrected_from(row) == "facility"


def test_corrected_from_none_when_types_match(index_df):
    row = index_df.loc[index_df["institution_id"] == "I39804081"].iloc[0]  # Sorbonne: type == type_openalex
    assert badges.corrected_from(row) is None


def test_an_umbrella_that_is_also_type_corrected_renders_one_badge_not_a_crash():
    """-1a, the crash class itself: earlier this row raised an
    AssertionError ("mutually exclusive"), which is what took the Ifremer
    profile down. The row is legitimate -- ten real institutions are both
    so it now yields the umbrella badge and nothing else, the type correction
    having moved into the identity line."""
    row = {"institution_id": "SYN1", "type": "government", "type_openalex": "facility"}
    flags = pd.Series([True], index=["SYN1"])
    assert badges.badges_for(row, flags, {}) == [copy.UMBRELLA_BADGE_LABEL]
    assert badges.corrected_from(row) == "facility"


def test_no_badge_at_all_when_only_the_type_was_corrected():
    """The other half: a correction on its own puts NOTHING in the badge row."""
    row = {"institution_id": "SYN3", "type": "education", "type_openalex": "facility"}
    assert badges.badges_for(row, pd.Series(dtype=bool), {}) == []


def test_badges_for_single_badge_ok():
    umbrella_row = {"institution_id": "SYN2", "type": "government", "type_openalex": "government"}
    flags = pd.Series([True], index=["SYN2"])
    assert badges.badges_for(umbrella_row, flags, {}) == [copy.UMBRELLA_BADGE_LABEL]


# --------------------------------------------------------------- exports ----

def _synthetic_rows():
    return [
        {"rank": 1, "institution_id": "I1", "display_name": "Alpha U", "country_code": "FR",
         "type": "education", "total_full_2020_2024": 500.0, "lens_score": 0.9,
         "shape_top3_fields": [{"field_name": "Physics", "share": 0.4}]},
        {"rank": 1, "institution_id": "I2", "display_name": "Beta U", "country_code": "DE",
         "type": "education", "total_full_2020_2024": 480.0, "lens_score": 0.9,
         "shape_top3_fields": []},
        {"rank": 3, "institution_id": "I3", "display_name": "Gamma Inst", "country_code": "IT",
         "type": "facility", "total_full_2020_2024": 300.0, "lens_score": 0.7,
         "shape_top3_fields": []},
    ]


# ------------------------------------------------------------ copy.py -------

def test_copy_digit_scan_passes():
    violations = copy.scan_for_digit_violations()
    assert violations == [], violations
