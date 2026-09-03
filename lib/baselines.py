"""
app/lib/baselines.py -- R2 L31 KPI baselines (.2 L31,
S10.4): median + percentile-rank of an institution's own KPI value against
the WHOLE index population, so every profile tile can carry a subline like
"index median {m} -- higher than {pct} of institutions" instead of a bare
number. Pure pandas, no Streamlit import -- the caller wraps `build` in `st.cache_resource`, exactly like every
other whole-population table in `lib/data_cache.py`.

`KPI_COLUMNS` names the eight L31 measures with a STABLE key (never renamed
downstream -- `stats`/`percentile` take this key, not a column name) mapped
to either an `index.parquet` column (str) or a one-argument callable
`(index_df) -> pd.Series` for a derived measure. Only `bonus_year_full` is
derived: `index.parquet` has no `vol_full_<bonus_year>` column of its own
(that lives on `topics_all`/`subfields`), so the bonus-year publication count
is parsed out of `vol_full_by_year_this_run`'s packed string for whichever
year `config.yaml`'s `bonus_year` names -- never a hardcoded year (L10).
"""
from __future__ import annotations

from typing import Callable, Union

import numpy as np
import pandas as pd

from .app_config import CFG

KpiSpec = Union[str, Callable[[pd.DataFrame], pd.Series]]


#  (2026-09-03): this used to be `from.profile_data import
# _parse_packed_years`. `lib/profile_data.py` (wave 3, not yet
# started) currently fails to import on its own -- it still does `from
# .engine.substrates import _topic_share_values`, a private helper Stream
# P1's substrates.py rewrite dropped (out of both P1's and E2's file fences
# for this worker). That import failure is transitive: it broke `import
# lib.baselines`, which blocks `scenario_cache.bundle` and every D11
# frame-aliasing test in this stream, though nothing here actually needs
# profile_data.py's OTHER logic. Rather than touch either stream's file,
# this eight-line pure string parser is copied verbatim (unrelated to the
# broken symbol) so baselines.py stays self-contained, exactly as its own
# module docstring already claims ("pure pandas, no Streamlit import").
# E2 may re-link to profile_data.py's copy (or delete this one) once that
# module imports cleanly again -- see progress/E1.md deviations.
def _parse_packed_years(packed) -> dict[int, float]:
    """'YEAR:value|YEAR:value|.' (index.vol_*_by_year_this_run) -> {year: value}."""
    if not isinstance(packed, str) or not packed:
        return {}
    out = {}
    for tok in packed.split("|"):
        y, v = tok.split(":")
        out[int(y)] = float(v)
    return out


def _bonus_year_full(index_df: pd.DataFrame) -> pd.Series:
    """The `CFG["bonus_year"]` (2025 as shipped) entry of each institution's
    `vol_full_by_year_this_run` -- NaN when that year is absent from the
    packed string (an institution with zero bonus-year publications still
    gets a defined 0 here IF the pipeline packs a 0 entry for it; a year
    genuinely missing from the string is a true unknown, not a 0)."""
    year = int(CFG["bonus_year"])
    return index_df["vol_full_by_year_this_run"].map(
        lambda packed: _parse_packed_years(packed).get(year, np.nan)
    )


# The eight L31 measures, in the tile order the profile page shows them.
KPI_COLUMNS: dict[str, KpiSpec] = {
    "total_full_2020_2024": "total_full_2020_2024",
    "total_frac_2020_2024": "total_frac_2020_2024",
    "hhi_subfield": "hhi_subfield",
    "breadth_subfields": "breadth_subfields",
    "sdg_tagged_share": "sdg_tagged_share",
    "frontier_top25_share": "frontier_top25_share",
    "pp_top10_frac": "pp_top10_frac",
    "bonus_year_full": _bonus_year_full,
}


def _kpi_values(index_df: pd.DataFrame, kpi: str) -> pd.Series:
    spec = KPI_COLUMNS[kpi]
    return spec(index_df) if callable(spec) else index_df[spec]


def build(index_df: pd.DataFrame) -> dict:
    """One pass over the index, per KPI: the SORTED non-null values (a plain
    `np.ndarray`, so `percentile` can binary-search it with
    `np.searchsorted`), the median (`pandas.Series.median`, which already
    skips NaN) and `n` (the non-null count -- the SAME population the median
    was computed over, never the full row count)."""
    bl: dict[str, dict] = {}
    for kpi in KPI_COLUMNS:
        non_null = _kpi_values(index_df, kpi).astype("float64").dropna()
        bl[kpi] = {
            "sorted": np.sort(non_null.to_numpy()),
            "median": float(non_null.median()) if len(non_null) else float("nan"),
            "n": int(len(non_null)),
        }
    return bl


def stats(bl: dict, kpi: str) -> dict:
    """`{"median": float, "n": int}` for one KPI -- the L31 tile subline's
    reference value and its coverage denominator."""
    entry = bl[kpi]
    return {"median": entry["median"], "n": entry["n"]}


def percentile(bl: dict, kpi: str, value) -> float | None:
    """Share of non-null index values STRICTLY BELOW `value` (0.1).
    `None` when `value` itself is null (L31: a missing KPI has no
    positioning to show -- never rendered as a false 0th percentile) or when
    the KPI has no non-null population at all (`n == 0`)."""
    if value is None or pd.isna(value):
        return None
    entry = bl[kpi]
    if entry["n"] == 0:
        return None
    below = int(np.searchsorted(entry["sorted"], float(value), side="left"))
    return below / entry["n"]
