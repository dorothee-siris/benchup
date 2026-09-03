"""
app/lib/exports.py -- CSV export of a (filtered) lens ranking.
Pure functions, no Streamlit import: `ranked.py`/`views_find.py` call these to
get bytes for `st.download_button`.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from lib import countries


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


