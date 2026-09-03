"""
app/lib/badges.py -- umbrella/aggregate, type-corrected and catch-all badges. Pure functions over the institution index /
engine row dicts -- no Streamlit import.

The umbrella rule reads the PATCHED `type` column (config.yaml
umbrella_badge.basis_column), never `type_openalex`, specifically because the
`type_openalex` basis would flag Sciences Po, CentraleSupelec and EHESS -- all
three type-corrected TO education -- as umbrellas at the same time their own
correction says "this is really education".

-1a RETIRES the L7 "umbrella and type-corrected are mutually exclusive"
invariant, and with it the assertion that enforced it. The invariant held while
the two flags were drawn from disjoint populations; the / R2 type overrides
made ten institutions (Ifremer, TNO, CNR, SINTEF, DLR, Ikerbasque, DZHK, DZNE,
DZL, DZIF) legitimately BOTH -- an umbrella by volume against its country-type
median AND corrected away from the type OpenAlex records. Every one of them
crashed the profile on an AssertionError. The fix is not to suppress one flag
(that hides true information): the type correction is no longer a BADGE at all.
It renders INLINE in the identity line -- "government* (was: facility)"
built by `corrected_from` below and composed in `lib/views_find.py`; the
umbrella badge is the only badge this module still emits.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from lib import copy, palette
from lib.app_config import CFG
from lib.search import normalize

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UMBRELLA_SUPPLEMENT_PATH = DATA_DIR / "overrides" / "umbrella_supplement.csv"


def umbrella_flags(index_df: pd.DataFrame) -> pd.Series:
    """type in CFG umbrella_badge.types AND total_full_2020_2024 > multiplier x
    the (country_code, type) median -- both read on the PATCHED `type` column,
    median computed over the WHOLE index, not just the candidate rows (M5.7)
    OR named in overrides/umbrella_supplement.csv (matched on institution_id
    where present, else on normalised display_name). Returned indexed by
    institution_id."""
    cfg = CFG["umbrella_badge"]
    type_col = index_df[cfg["basis_column"]].astype(str)
    country_col = index_df["country_code"].astype(str)
    medians = index_df.groupby([country_col, type_col])["total_full_2020_2024"].transform("median")
    rule_flag = type_col.isin(cfg["types"]) & (index_df["total_full_2020_2024"] > cfg["multiplier"] * medians)

    supplement = pd.read_csv(UMBRELLA_SUPPLEMENT_PATH)
    by_id = set(supplement["institution_id"].dropna())
    by_name = {normalize(n) for n in supplement["display_name"].dropna()}
    name_hit = index_df["display_name"].map(normalize).isin(by_name)
    supplement_flag = index_df["institution_id"].isin(by_id) | name_hit

    flags = rule_flag | supplement_flag
    return pd.Series(flags.to_numpy(), index=index_df["institution_id"].to_numpy(), name="is_umbrella")


def umbrella_medians(index_df: pd.DataFrame) -> dict:
    """(country_code, type) -> median total_full_2020_2024 over the whole
    index -- what the umbrella tooltip compares a flagged row against."""
    cfg = CFG["umbrella_badge"]
    type_col = index_df[cfg["basis_column"]].astype(str)
    country_col = index_df["country_code"].astype(str)
    med = index_df.groupby([country_col, type_col])["total_full_2020_2024"].median()
    return {key: float(v) for key, v in med.items()}


def corrected_from(row) -> str | None:
    """The ORIGINAL (OpenAlex) type whenever the shipped `type` differs from it
    the "was:." half of the -1a inline identity form -- and `None`
    when the two agree. Works on either a raw index_df row (type_openalex always
    populated) or an engine evidence dict (type_openalex already None-clamped
    when equal to type).

    Returns the bare type, not a sentence: this module knows WHICH institutions
    were corrected, `lib/copy.py` knows how to say it and `lib/views_find.py`
    composes the two. Earlier, this function returned the whole badge string
    (`CFG type_overrides.ui_badge`), which is exactly the badge -1a
    removed."""
    type_oa = row["type_openalex"]
    if type_oa is None or pd.isna(type_oa):
        return None
    t, t_oa = str(row["type"]), str(type_oa)
    if t == t_oa:
        return None
    return t_oa


def badges_for(row, flags: pd.Series, medians: dict) -> list[str]:
    """Text labels for one row's badge cell -- since -1a, the umbrella
    badge and nothing else. The list shape is kept (rather than a bool) because
    every caller joins it, and because a second badge family may yet earn a
    place here; a type correction never will -- it renders inline in the
    identity line, off `corrected_from`."""
    if bool(flags.get(row["institution_id"], False)):
        return [copy.UMBRELLA_BADGE_LABEL]
    return []
