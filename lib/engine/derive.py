"""
R2 S2 (REFINEMENT_PLAN.md S10.2, S2 row; R2.19/R2.20) -- the app's future data
layer: given the one topic-grain master (`topics_all` + `topics_dim`), derive
`subfields`/`fields` shapes for ANY tree x basis x 811-toggle scenario with
duckdb (in-process, $0, MIT), instead of shipping all 12 scenarios
precomputed. This module is copied verbatim into the Sprint-2 app.

`derive_shapes(topics_all_path, topics_dim_path, tree, basis, exclude_811,
index_institution_ids=None)` reproduces `pipeline/agg/trees_agg.py`'s
`build_subfields`/`build_fields` EXACTLY for basis='frac' (the only basis
trees_agg ever computes -- see "basis generalization" note below), on the
topic grain instead of the raw corpus grain: under `assignment='primary'`
(the shipped default, R2.18) a work's full weight lands on its primary topic
only, and trees_agg maps that SAME primary topic to a subfield -- so
GROUP BY (institution, tree_subfield(topic)) over `topics_all` and GROUP BY
(institution, tree_subfield(primary_topic)) over the raw corpus are the same
sum, just computed from a pre-aggregated intermediate table instead of every
work row.

Nesting is identical to trees_agg: subfield -> field is fixed (never
re-derived per tree, R4's own rule), shares sum to 1 per institution PER
SCENARIO (the denominator is the scenario's own total, i.e. excluded-topic
mass is dropped from BOTH numerator and denominator when exclude_811=True
R2.20's "excluded removes topics from shapes/SI/L3 ONLY"), and SI is
NaN below the G6 floor.

BASIS GENERALIZATION (a documented judgment call, not lifted from trees_agg
trees_agg has no `basis` toggle at all, it only ever computes ONE `si` column
from share_frac): when basis='full', `si` is computed from share_full ÷
mean(share_full) instead. The G6 FLOOR TEST STAYS ON vol_frac REGARDLESS of
`basis` -- REFINEMENT_PLAN.md's own registry entry (2026-08-27 07:40,
"Method B -> continuous fallback") states the ratified floor is a floor on
FRACTIONAL MASS ("vol_frac >= 30 ~ 100 full works"), not on whichever basis
happens to be displayed; trees_agg's own code hard-codes the vol_frac test
unconditionally, which is consistent with reading the floor as basis-
independent. This basis='full' path is NOT covered by the Tier-A identity
check against the shipped tables (trees_agg never ships a full-basis si to
compare against) -- flagged here and in the S2 report, not silently assumed.

MEAN-SHARE POPULATION (the second documented nuance, found reading trees_agg
line by line, not assumed from the plan's prose): "mean share across index
institutions" is NOT a mean over every institution in the index -- it is a
mean over every institution that has a NONZERO row for that subfield under
that tree (trees_agg's `overall.groupby("subfield_id")["share_frac"].mean`
runs on the already topic-mapped, already-filtered `overall` frame, which
only has a row where an institution's mass in that subfield is > 0).
`derive_shapes` reproduces this exactly: the mean is computed from
`subfields_raw` (already exclude_811-filtered and index_institution_ids-
filtered), which by construction only has rows for institutions with
nonzero mass in that (tree, subfield) cell in the given scenario.

BY-YEAR FORMAT DEVIATION (documented, not silently different): the shipped
`subfields.parquet` packs by-year volumes as pipe-strings
('YEAR:value|YEAR:value|.', `trees_agg._pack_year_columns`). `derive_shapes`
instead emits WIDE columns (`vol_full_<year>`/`vol_frac_<year>`, matching
`topics_all`'s own new per-year schema, R2 S2 item 1) whenever the source
`topics_all` parquet HAS those columns (detected live from its schema, not
assumed) -- a duckdb SUM per year is the natural, SQL-native shape for this
data layer and is what the app will actually plot (a trajectory needs
numeric columns, not a string to re-parse); when the source lacks them (the
CURRENT build, pre-S3), the output simply omits them, no fake NaNs.
`fields_df` never carries by-year columns, matching the shipped
`fields.parquet` exactly (trees_agg's `build_fields` has no by-year columns
at all -- field-level trajectories are not part of today's shipped schema).

Ponytail: no classes, no config object -- two small SQL strings (one per
output table) with duckdb's `?`/registered-table parameter binding, no
per-row pandas loops.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .trees_agg import G6_FLOOR, TREES as VALID_TREES

VALID_BASES = ("frac", "full")


def _posix(path: str | Path) -> str:
    """Windows backslashes inside a SQL string literal are ambiguous escape
    sequences -- duckdb's read_parquet takes forward-slash paths fine."""
    return Path(path).as_posix()


def _detect_year_cols(columns: list[str]) -> list[int]:
    """Years present in BOTH vol_full_<year> and vol_frac_<year> (topics_all's
    R2 S2 schema) -- sorted ascending. Empty on the pre-S2 schema (no by-year
    columns at all), never guessed from a hardcoded year list."""
    full_years = {int(m.group(1)) for c in columns if (m := re.fullmatch(r"vol_full_(\d{4})", c))}
    frac_years = {int(m.group(1)) for c in columns if (m := re.fullmatch(r"vol_frac_(\d{4})", c))}
    return sorted(full_years & frac_years)


def _cast_output(df: pd.DataFrame, id_col: str, year_cols: list[int]) -> pd.DataFrame:
    df["inst_key"] = df["inst_key"].astype("int32")
    df[id_col] = df[id_col].astype("int16")
    if "field_id" in df.columns:
        df["field_id"] = df["field_id"].astype("int16")
    df["vol_full"] = df["vol_full"].round().astype("int32")
    for c in ("vol_frac", "share_frac", "share_full", "si"):
        df[c] = df[c].astype("float32")
    for y in year_cols:
        df[f"vol_full_{y}"] = df[f"vol_full_{y}"].round().astype("int32")
        df[f"vol_frac_{y}"] = df[f"vol_frac_{y}"].astype("float32")
    return df


def derive_shapes(
    topics_all_path: str | Path,
    topics_dim_path: str | Path,
    tree: str = "bestfit",
    basis: str = "frac",
    exclude_811: bool = False,
    index_institution_ids: list[str] | None = None,
    g6_floor: float = G6_FLOOR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (subfields_df, fields_df) for the given tree x basis x
    exclude_811 scenario, computed from `topics_all` + `topics_dim` alone
    (no raw corpus, no attribution_long -- the whole point of the one-master
    design, R2.19). See module docstring for the exact rules reproduced."""
    if tree not in VALID_TREES:
        raise ValueError(f"tree must be one of {VALID_TREES}, got {tree!r}")
    if basis not in VALID_BASES:
        raise ValueError(f"basis must be one of {VALID_BASES}, got {basis!r}")

    ta_posix = _posix(topics_all_path)
    td_posix = _posix(topics_dim_path)
    share_col = "share_frac" if basis == "frac" else "share_full"

    con = duckdb.connect()
    ta_cols = con.sql(f"SELECT * FROM read_parquet('{ta_posix}') LIMIT 0").columns
    year_cols = _detect_year_cols(ta_cols)
    year_sum_sql = "".join(
        f", SUM(vol_full_{y}) AS vol_full_{y}, SUM(vol_frac_{y}) AS vol_frac_{y}" for y in year_cols
    )
    year_select_sql = "".join(f", vol_full_{y}, vol_frac_{y}" for y in year_cols)

    id_filter_sql = ""
    if index_institution_ids is not None:
        con.register("_idlist", pd.DataFrame({"institution_id": list(index_institution_ids)}))
        id_filter_sql = "AND institution_id IN (SELECT institution_id FROM _idlist)"
    excl_filter_sql = "AND NOT is_excluded" if exclude_811 else ""

    # 1:1 sanity on the tree-independent subfield->field map (trees_agg's own
    # assertion, reproduced here rather than trusted blind).
    dup = con.sql(
        f"SELECT subfield_id, COUNT(*) c FROM "
        f"(SELECT DISTINCT subfield_id, field_id FROM read_parquet('{td_posix}')) "
        f"GROUP BY subfield_id HAVING COUNT(*) > 1"
    ).df()
    if len(dup):
        raise AssertionError(f"subfield_id -> field_id is not 1:1 in topics_dim: {dup.to_dict('records')}")

    subfields_sql = f"""
    WITH topics_dim_v AS (
        SELECT topic_id, {tree}_subfield_id AS subfield_id, is_excluded
        FROM read_parquet('{td_posix}')
    ),
    ta_joined AS (
        SELECT ta.institution_id, ta.inst_key, td.subfield_id,
               ta.vol_frac, ta.vol_full {year_select_sql}
        FROM read_parquet('{ta_posix}') ta
        JOIN topics_dim_v td USING (topic_id)
        WHERE 1=1 {excl_filter_sql} {id_filter_sql}
    ),
    subfields_raw AS (
        SELECT institution_id, inst_key, subfield_id,
               SUM(vol_frac) AS vol_frac, SUM(vol_full) AS vol_full
               {year_sum_sql}
        FROM ta_joined
        GROUP BY institution_id, inst_key, subfield_id
    ),
    inst_totals AS (
        SELECT institution_id, SUM(vol_frac) AS _tot_frac, SUM(vol_full) AS _tot_full
        FROM subfields_raw GROUP BY institution_id
    ),
    shares AS (
        SELECT r.*,
               CASE WHEN t._tot_frac > 0 THEN r.vol_frac / t._tot_frac ELSE 0 END AS share_frac,
               CASE WHEN t._tot_full > 0 THEN r.vol_full / t._tot_full ELSE 0 END AS share_full
        FROM subfields_raw r JOIN inst_totals t USING (institution_id)
    ),
    mean_share_v AS (
        SELECT subfield_id, AVG({share_col}) AS _mean_share FROM shares GROUP BY subfield_id
    )
    SELECT s.institution_id, s.inst_key, s.subfield_id, sf.field_id,
           s.vol_frac, s.vol_full, s.share_frac, s.share_full,
           CASE WHEN m._mean_share > 0 AND s.vol_frac >= {g6_floor}
                THEN s.{share_col} / m._mean_share ELSE NULL END AS si
           {year_select_sql}
    FROM shares s
    JOIN mean_share_v m USING (subfield_id)
    JOIN (SELECT DISTINCT subfield_id, field_id FROM read_parquet('{td_posix}')) sf USING (subfield_id)
    ORDER BY inst_key, subfield_id
    """
    subfields_df = con.sql(subfields_sql).df()
    subfields_df["tree"] = tree
    subfields_df = subfields_df[
        ["inst_key", "institution_id", "subfield_id", "field_id", "tree", "vol_frac", "vol_full",
         "share_frac", "share_full", "si"] + [c for y in year_cols for c in (f"vol_full_{y}", f"vol_frac_{y}")]
    ]
    subfields_df = _cast_output(subfields_df, "subfield_id", year_cols)
    subfields_df["tree"] = subfields_df["tree"].astype("category")

    # ---- fields: pure re-aggregation of subfields_df (subfield->field is fixed,
    # so no second pass over topics_all -- matches trees_agg.build_fields exactly,
    # including "no G6 floor at field grain, ever"). ----
    con.register("_subfields_v", subfields_df)
    year_sum_sql2 = "".join(f", SUM(vol_full_{y}) AS vol_full_{y}, SUM(vol_frac_{y}) AS vol_frac_{y}" for y in year_cols)
    fields_sql = f"""
    WITH fields_raw AS (
        SELECT institution_id, inst_key, field_id,
               SUM(vol_frac) AS vol_frac, SUM(vol_full) AS vol_full
               {year_sum_sql2}
        FROM _subfields_v
        GROUP BY institution_id, inst_key, field_id
    ),
    inst_totals AS (
        SELECT institution_id, SUM(vol_frac) AS _tot_frac, SUM(vol_full) AS _tot_full
        FROM fields_raw GROUP BY institution_id
    ),
    shares AS (
        SELECT r.*,
               CASE WHEN t._tot_frac > 0 THEN r.vol_frac / t._tot_frac ELSE 0 END AS share_frac,
               CASE WHEN t._tot_full > 0 THEN r.vol_full / t._tot_full ELSE 0 END AS share_full
        FROM fields_raw r JOIN inst_totals t USING (institution_id)
    ),
    mean_share_v AS (
        SELECT field_id, AVG({share_col}) AS _mean_share FROM shares GROUP BY field_id
    )
    SELECT s.institution_id, s.inst_key, s.field_id,
           s.vol_frac, s.vol_full, s.share_frac, s.share_full,
           CASE WHEN m._mean_share > 0 THEN s.{share_col} / m._mean_share ELSE NULL END AS si
    FROM shares s JOIN mean_share_v m USING (field_id)
    ORDER BY inst_key, field_id
    """
    fields_df = con.sql(fields_sql).df()
    fields_df["tree"] = tree
    fields_df = fields_df[
        ["inst_key", "institution_id", "field_id", "tree", "vol_frac", "vol_full", "share_frac", "share_full", "si"]
    ]
    fields_df = _cast_output(fields_df, "field_id", [])
    fields_df["tree"] = fields_df["tree"].astype("category")
    con.close()
    return subfields_df, fields_df
