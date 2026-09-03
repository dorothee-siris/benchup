"""
app/lib/countries.py -- ISO2 -> English country name (
Refinement R1, S9.2 L22 / S9.4 `countries.name(code) -> str`).

Pattern copied from Lorraine's own
`countries_fr.py` (frozen CSV, `keep_default_na=False`), English names instead
of French: this app's UI is English throughout (
decisions log, "UI language = English").

`data/countries_en.csv` is a curated, frozen mapping covering every
`country_code` value in `data/index.parquet` -- 31 codes on this snapshot
(AT BE BG CH CY CZ DE DK EE ES FI FR GB GR HR HU IE IS IT LT LU LV MT NL NO
PL PT RO SE SI SK; see `tests/test_countries.py` for the 100% coverage
assertion against the live index) -- plus one extra `NA` (Namibia) row that
exists ONLY to prove the `keep_default_na=False` guard below: pandas' default
NA-string sniffing would otherwise silently turn the literal string "NA" into
a missing value on CSV read, which is exactly the trap a real Namibia row
would hit in a wider (non-EU27) snapshot. That row never shows up in this
app's live data; it is a standing regression test fixture, not live coverage.

`name(code)` never raises and never returns an empty string for a non-empty
input: an unrecognised code falls back to the code itself (.3 R-F2 brief), logged once per code per process -- never a wall of
repeated warnings for a wide table.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "countries_en.csv"
_logger = logging.getLogger(__name__)

# Codes already warned about this process -- "logged once", not once per row
# of a table that repeats the same unknown code hundreds of times.
_warned_codes: set[str] = set()


def _load_names() -> dict[str, str]:
    # keep_default_na=False + na_values=[]: "NA" IS Namibia, never a null
    # (see module docstring's Namibia paragraph). dtype=str so a numeric-
    # looking code is never silently coerced.
    df = pd.read_csv(_CSV_PATH, dtype=str, keep_default_na=False, na_values=[])
    return dict(zip(df["iso2"].str.strip(), df["name_en"].str.strip()))


NAMES: dict[str, str] = _load_names()


def name(code) -> str:
    """English display name for an ISO2 code (stripped, upper-cased before
    lookup). Unknown or missing input -> the code itself (or "" for a
    genuinely null/empty input); never raises. Unknown codes are logged once
    per code via the `logging` module, not printed."""
    if code is None:
        return ""
    try:
        if pd.isna(code):
            return ""
    except (TypeError, ValueError):
        pass
    c = str(code).strip().upper()
    if not c:
        return ""
    nm = NAMES.get(c)
    if nm:
        return nm
    if c not in _warned_codes:
        _logger.warning(
            "countries.name: no English name for ISO2 code %r -- showing the code itself", c)
        _warned_codes.add(c)
    return c
