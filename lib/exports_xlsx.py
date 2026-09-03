"""
app/lib/exports_xlsx.py -- the mechanics behind the ONE end-of-page workbook
each of Find/Compare offers.

Pure functions, no Streamlit import and no copy import: the caller owns every
string (sheet titles, the Methods rows) and this module owns only the mechanics
sheet-name legality, sheet order, and the bytes. That split is what lets
`lib/copy.py` stay the single source of rendered text while a workbook still
carries the same words the page does.

`openpyxl==3.1.5` (pinned in requirements.txt, installed into envs/env-app) is
reached through pandas' own `ExcelWriter`; nothing here imports it directly, so
a future engine swap is a one-word change.
"""
from __future__ import annotations

import io

import pandas as pd

# Excel's own sheet-name rules: at most 31 characters, none of []:*?/\, not
# empty, unique inside one workbook. A name that breaks them raises deep inside
# openpyxl at write time, i.e. after the download button has already been
# clicked -- so they are enforced here, once, on the way in.
SHEET_NAME_MAX = 31
ILLEGAL_CHARS = set(chr(c) for c in (0x5B, 0x5D, 0x3A, 0x2A, 0x3F, 0x2F, 0x5C))
FALLBACK_SHEET = "Sheet"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def sheet_name(label: str, taken: set | None = None) -> str:
    """A legal, unique Excel sheet name for `label`. Illegal characters are
    dropped, the name is trimmed to the length Excel allows, and a collision
    with anything in `taken` gets a numeric suffix (the ONE place a digit may
    enter a workbook name -- it is a disambiguator, not copy)."""
    clean = "".join(c for c in str(label) if c not in ILLEGAL_CHARS)
    base = clean.strip()[:SHEET_NAME_MAX] or FALLBACK_SHEET
    if taken is None or base not in taken:
        return base
    for n in range(2, 100):
        suffix = f" ({n})"
        candidate = base[:SHEET_NAME_MAX - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
    return base[:SHEET_NAME_MAX - 1] + "~"


def workbook_bytes(sheets) -> bytes:
    """`sheets` is an ordered mapping (or a sequence of pairs) of
    `label -> DataFrame`; returns the.xlsx bytes.

    An empty frame still gets its sheet: a reader who sees a named, empty sheet
    learns that the view had nothing to show, while a MISSING sheet is
    indistinguishable from a workbook built by an older version of the app.
    """
    items = list(sheets.items() if hasattr(sheets, "items") else sheets)
    buffer = io.BytesIO()
    taken: set = set()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for label, frame in items:
            name = sheet_name(label, taken)
            taken.add(name)
            df = frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame)
            df.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


def workbook_filename(ids) -> str:
    """"BenchUp_compare_<A>_<B>.xlsx". No tree/basis suffix
    any more: Compare is PINNED to the best-fit taxonomy and full counting,
    so a scenario suffix would name a setting that never varies."""
    return "BenchUp_compare_" + "_".join(str(i) for i in ids) + ".xlsx"


