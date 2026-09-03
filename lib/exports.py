"""
app/lib/exports.py -- CSV export of a (filtered) lens ranking.
Pure functions, no Streamlit import: `ranked.py`/`views_find.py` call these to
get bytes for `st.download_button`.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from lib import countries

_COLUMNS = ["rank", "institution_id", "display_name", "country", "country_code", "type",
            "total_full_2020_2024", "total_frac_2020_2024", "lens_score", "evidence"]


def data_date_label(stamp, fallback: str) -> str:
    """An ISO timestamp -> the plain reading date the pages print.

    Lives here, in the one module that already owns "what vintage this file
    came from", because it has NO Streamlit import: `Menu.py` and
    `lib/views_find.py` both need the same string and neither should own a
    private copy of the formatting. No digit is typed -- the month name, the
    day and the year all come out of the parsed timestamp -- so the caption
    this feeds stays inside the digit-ban (this file is outside that test's
    scope anyway, `tests/test_narrative.py`'s own exclusion list).

    Returns `fallback` (the caller's `n/a` mark) for a missing or unparseable
    stamp rather than inventing a date. `datetime.fromisoformat` on this
    Python (3.12) accepts the `+00:00` offset the deploy manifest writes.
    """
    if not isinstance(stamp, str) or not stamp:
        return fallback
    try:
        dt = datetime.fromisoformat(stamp)
    except ValueError:
        return fallback
    return f"{dt:%B} {dt.day}, {dt.year}"


def _evidence_str(row: dict) -> str:
    """The lens-specific evidence text (`row["evidence_text"]`, R-B's
    `evidence.rows_evidence` --.4) when the row
    carries one; else the legacy top-3-fields text every row carries via
    `base_evidence` (kept as a fallback until every caller always sets
    `evidence_text`)."""
    text = row.get("evidence_text")
    if text:
        return text
    fields = row.get("shape_top3_fields") or []
    if fields:
        return "; ".join(f"{f['field_name']} ({f['share']:.1%})" for f in fields)
    return ""


def ranking_csv(rows, *, seed_id, lens, tree, basis, snapshot, filters_label) -> bytes:
    """Full (filtered) ranking as CSV bytes: original competition ranks
    preserved (gaps kept, never renumbered -- VIZ_SPEC S1.7), plus constant
    columns so the file is self-describing outside the app."""
    records = []
    for r in rows:
        code = str(r["country_code"])
        records.append({
            "rank": r["rank"],
            "institution_id": r["institution_id"],
            "display_name": r["display_name"],
            "country": countries.name(code),
            "country_code": code,
            "type": r["type"],
            "total_full_2020_2024": r.get("total_full_2020_2024"),
            "total_frac_2020_2024": r.get("total_frac_2020_2024"),
            "lens_score": r.get("lens_score"),
            "evidence": _evidence_str(r),
        })
    df = pd.DataFrame(records, columns=_COLUMNS)
    df["seed_id"] = seed_id
    df["lens"] = lens
    df["tree"] = tree
    df["basis"] = basis
    #  / A14: the export keeps FACTUAL provenance -- one plain column
    # holding the snapshot label -- and loses nothing else; the verbose
    # "generated <timestamp>" string the pages used to print was never in the
    # CSV. Renamed `snapshot` -> `data_snapshot` so the column says what it is
    # to someone reading the file outside the app.
    df["data_snapshot"] = snapshot
    df["filters"] = filters_label
    return df.to_csv(index=False).encode("utf-8")


def ranking_filename(seed_id: str, lens: str, tree: str, basis: str, filtered: bool) -> str:
    """`benchup_{seed}_{lens}_{tree}_{basis}[_filtered].csv` -- VIZ_SPEC S1.7."""
    suffix = "_filtered" if filtered else ""
    return f"benchup_{seed_id}_{lens}_{tree}_{basis}{suffix}.csv"
