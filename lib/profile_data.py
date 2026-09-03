"""
app/lib/profile_data.py -- per-institution profile tables for the R1 Profile
section (.2 L17, S9.3 R-B, S9.4 interface contracts).

Pure functions, no Streamlit import: every function takes the engine's `ctx`
(+ often `subs`, one scenario's substrates) and an `institution_id`, and
returns a plain pandas DataFrame with EXACTLY the S9.4 column contract
`lib/charts.py` and `lib/views_find.py` build on
these columns by name, so nothing here is free to rename or drop one.

Tree-awareness: `fields_table`/`subfields_table` read `subs["fields_df"]` /
`subs["subfields_df"]` -- the SAME scenario frames `lib/engine/substrates.py`
already computes for the L0/L1 lenses (`derive_shapes` output, or the shipped
`fields.parquet` on the default scenario) -- so `share` follows `subs["basis"]`.
`topics_table` resolves a topic's tree-aware subfield/field/domain from
`topics_dim.parquet`'s `{tree}_subfield_id` through the FIXED subfield->field
->domain map (subfield->field never changes per tree, `trees_agg.
subfield_to_field_map`).

R2 L34 (.2): `si` at subfield grain is now RECOMPUTED here
without the ratified G6 floor (`_unfloored_si`) -- `subs["subfields_df"]`'s own
`si` column is NaN below `vol_frac >= 30` (the ratified LENS floor, untouched),
but the profile display wants a value down to `vol_frac >= 10` ("thin" cells,
hollow mark) so it can distinguish "thin" from "none" instead of collapsing
both into a blank. `si_status` (`{"solid", "thin", "none"}`, thresholds
`SI_FLOOR_SOLID`/`SI_FLOOR_THIN`) is added to `subfields_table`/`erc_table`/
`sdg_table` (mass-based) and `fields_table` (no-floor-observed basis) so
`lib/charts.py` never has to re-derive a threshold from a typed number.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .engine.derive import _detect_year_cols

FIELDS_COLS = ["field_id", "field_name", "domain_id", "domain_name", "vol_full", "vol_frac", "share",
              "si", "si_status"]
SUBFIELDS_COLS = ["subfield_id", "subfield_name"] + FIELDS_COLS
TOPICS_COLS = ["topic_id", "topic_name", "subfield_id", "subfield_name", "field_id", "field_name",
              "domain_id", "domain_name", "vol_full", "vol_frac", "share", "is_excluded",
              "frontier_score_latest", "expansion_latest", "acceleration_latest", "quadrant",
              "top25pct_frontier", "rank_volume"]
YEARLY_COLS = ["year", "domain_id", "domain_name", "vol_full", "vol_frac"]
SDG_COLS = ["sdg_idx", "sdg_number", "sdg_label", "sdg_label_numbered", "share", "esi", "mass", "si_status"]
ERC_COLS = ["panel_idx", "panel_code", "panel_label", "erc_domain", "share", "si", "mass", "si_status"]

# R2 L34 (.2): harmonised display floors on FRACTIONAL mass
# (vol_frac for subfields, `mass` for ERC/SDG) -- solid = safe to plot as a
# filled mark, thin = hollow mark (small sample), none = no mark at all (this
# is the "no SI mark at zero volume" ERC fix, triage #9). These are a PROFILE
# DISPLAY rule only; the ratified lens floor (`trees_agg.G6_FLOOR` = 30, same
# number, different purpose) lives in `derive.py`'s own scenario-assembly
# step untouched.
SI_FLOOR_SOLID = 30.0
SI_FLOOR_THIN = 10.0


# --------------------------------------------------------- cached lookups ---

def _field_domain_map(ctx: dict) -> pd.DataFrame:
    """field_id -> field_name/domain_id/domain_name -- FIXED (tree-independent),
    26 rows, cached on ctx."""
    if "field_domain_map" not in ctx:
        td = ctx["topics_dim_df"]
        ctx["field_domain_map"] = (
            td[["field_id", "field_name", "domain_id", "domain_name"]].drop_duplicates()
        )
    return ctx["field_domain_map"]


def _subfield_field_domain_map(ctx: dict) -> pd.DataFrame:
    """subfield_id -> subfield_name/field_id/field_name/domain_id/domain_name
    FIXED (tree-independent, `trees_agg.subfield_to_field_map`'s own
    invariant), 252 rows, cached on ctx."""
    if "subfield_field_domain_map" not in ctx:
        td = ctx["topics_dim_df"]
        ctx["subfield_field_domain_map"] = (
            td[["subfield_id", "subfield_name", "field_id", "field_name", "domain_id", "domain_name"]]
            .drop_duplicates()
        )
    return ctx["subfield_field_domain_map"]


def _topics_dim_extra(ctx: dict) -> pd.DataFrame:
    """The columns `load_context`'s narrow `topics_dim_df` does NOT carry:
    `topic_name` and the ACCORD frontier score columns -- a second, narrow
    read of `topics_dim.parquet`, cached on ctx (S9.3 R-B: 'load lazily, cache
    on ctx')."""
    if "topics_dim_extra_df" not in ctx:
        ctx["topics_dim_extra_df"] = pd.read_parquet(
            Path(ctx["data_dir"]) / "topics_dim.parquet",
            columns=["topic_id", "topic_name", "frontier_score_latest", "expansion_latest",
                     "acceleration_latest", "quadrant"],
        )
    return ctx["topics_dim_extra_df"]


def _erc_panels(ctx: dict) -> pd.DataFrame:
    if "erc_panels_df" not in ctx:
        from .engine.evidence import RESOURCES
        ctx["erc_panels_df"] = pd.read_csv(RESOURCES / "erc_panels.csv")
    return ctx["erc_panels_df"]


def _sdg_labels(ctx: dict) -> pd.DataFrame:
    if "sdg_labels_df" not in ctx:
        from .engine.evidence import RESOURCES
        ctx["sdg_labels_df"] = pd.read_csv(RESOURCES / "sdg_labels.csv")
    return ctx["sdg_labels_df"]


def _year_cols(ctx: dict) -> list[int]:
    """Years present in `topics_all.parquet`'s schema (vol_full_<year> AND
    vol_frac_<year>), detected once and cached -- never a hardcoded year list
    ."""
    if "topics_all_year_cols" not in ctx:
        con = duckdb.connect()
        cols = con.sql(
            f"SELECT * FROM read_parquet('{Path(ctx['topics_all_path']).as_posix()}') LIMIT 0"
        ).columns
        con.close()
        ctx["topics_all_year_cols"] = _detect_year_cols(cols)
    return ctx["topics_all_year_cols"]


# -------------------------------------------------------- R2 L34 SI floors

def si_status_from_mass(mass) -> pd.Series:
    """Harmonised display-floor status (L34): >= `SI_FLOOR_SOLID` -> "solid",
    `SI_FLOOR_THIN` <= mass < `SI_FLOOR_SOLID` -> "thin", else (incl. zero and
    NaN) -> "none". `mass` is ALWAYS the fractional-mass column -- `vol_frac`
    for subfields, the `mass` column for ERC/SDG -- never a raw work count,
    never a share/si value. `np.select`'s comparisons are False on NaN, so a
    missing mass falls through to "none" without a separate branch."""
    m = pd.Series(mass).astype("float64")
    return pd.Series(
        np.select([m >= SI_FLOOR_SOLID, m >= SI_FLOOR_THIN], ["solid", "thin"], default="none"),
        index=m.index,
    )


def _unfloored_si(df: pd.DataFrame, group_col: str, share_col: str) -> pd.Series:
    """`share_col / mean(share_col over the rows PRESENT in df for that
    group_col value)` -- the exact population `derive.py`'s own
    `mean_share_v` averages over (only rows already present in the frame,
    i.e. institutions with nonzero mass in that cell -- derive.py's
    'MEAN-SHARE POPULATION' note), but WITHOUT derive.py's G6-floor gate on
    the numerator (`AND s.vol_frac >= g6_floor`). A display-only
    re-derivation (L34): the ratified lens floor is untouched in derive.py."""
    share = df[share_col].astype("float64")
    mean_share = share.groupby(df[group_col]).transform("mean")
    with np.errstate(invalid="ignore", divide="ignore"):
        si = np.where(mean_share > 0, share / mean_share, np.nan)
    return pd.Series(si, index=df.index)


def _subfields_si_unfloored(subs: dict, share_col: str) -> pd.Series:
    """Cached on `subs` (same idiom as ctx's `_field_domain_map` etc.): the
    groupby mean is a whole-population pass, so it runs once per (tree,
    basis, share_col) scenario, not once per institution/profile view."""
    cache_key = f"_si_unfloored_{share_col}"
    if cache_key not in subs:
        subs[cache_key] = _unfloored_si(subs["subfields_df"], "subfield_id", share_col)
    return subs[cache_key]


# ------------------------------------------------------------ fields/subs ---

def fields_table(ctx: dict, subs: dict, iid: str) -> pd.DataFrame:
    """One row per field this institution has nonzero mass in, scenario-aware
    (`subs['fields_df']`): share on `subs['basis']`, si with NO floor at
    field grain (data_contract.yaml). `si_status` (L34) is "solid" whenever
    vol_frac > 0 AND si is defined, else "none" -- fields.si carries no floor
    at all, so there is no "thin" state at this grain (contrast subfields)."""
    share_col = "share_frac" if subs["basis"] == "frac" else "share_full"
    df = subs["fields_df"]
    row = df[df["institution_id"] == iid].copy()
    row["si_status"] = np.where(
        (row["vol_frac"].astype("float64") > 0) & row["si"].notna(), "solid", "none")
    out = row.merge(_field_domain_map(ctx), on="field_id", how="left")
    out = out.rename(columns={share_col: "share"})
    return out.reindex(columns=FIELDS_COLS).reset_index(drop=True)


def subfields_table(ctx: dict, subs: dict, iid: str) -> pd.DataFrame:
    """Same as `fields_table` at the subfield grain. `si` is RECOMPUTED
    unfloored (`_unfloored_si`, L34) so "thin" cells (10 <= vol_frac < 30)
    carry a real value instead of the ratified-floor NaN; `si_status` flags
    solid/thin/none on `vol_frac` (`SI_FLOOR_SOLID`/`SI_FLOOR_THIN`). Where
    the frame's own (ratified-floor) si IS defined, this si is numerically
    identical to it (same formula, same population) -- see
    tests/test_profile_data.py's identity check."""
    share_col = "share_frac" if subs["basis"] == "frac" else "share_full"
    df = subs["subfields_df"]
    row = df[df["institution_id"] == iid].copy()
    row["si"] = _subfields_si_unfloored(subs, share_col).loc[row.index]
    row["si_status"] = si_status_from_mass(row["vol_frac"])
    fd = _subfield_field_domain_map(ctx)[["subfield_id", "subfield_name"]]
    out = row.merge(fd, on="subfield_id", how="left").merge(_field_domain_map(ctx), on="field_id", how="left")
    out = out.rename(columns={share_col: "share"})
    return out.reindex(columns=SUBFIELDS_COLS).reset_index(drop=True)


# ------------------------------------------------------------------ topics

_TOPICS_COLS_NO_RANK = [c for c in TOPICS_COLS if c != "rank_volume"]


def topics_table(ctx: dict, subs: dict, iid: str) -> pd.DataFrame:
    """One row per topic this institution has ANY mass in (`topics_all`),
    tree-aware subfield/field/domain (`subs['tree']`'s own `{tree}_subfield_id`
    resolved through the FIXED subfield->field->domain map), share on
    `subs['basis']` (frac = `topics_all.share_frac` verbatim; full = the
    vol_full-normalised share). moved the per-scenario ASSEMBLY of
    that share out of the app; the SAME values are already resident in
    `subs['l3']['share']` -- P1's dense (inst x topic) matrix for this basis,
    `cats == ctx['topic_ids']` -- so this reads them there by position
    instead: every row of this institution's slice has `ta_inst == idx` by
    construction (`mask`), so indexing the matrix at row `idx`, columns
    `topic_pos` reproduces exactly the per-row values the old (now removed)
    per-scenario share lookup used to hand back (proven identical to a direct
    recompute off `topics_all.parquet`, both bases, in
    tests/test_profile_data.py). `rank_volume` (L33) ranks topics by volume ON THE
    SAME BASIS (`vol_full` when basis='full', else `vol_frac`) -- 1 = largest,
    unique ints 1.n, ties broken by `topic_id` ascending (never a silent
    ambiguous tie) -- for the "top {n} topics by volume" frontier-panel mode."""
    idx = ctx["id_pos"][iid]
    mask = ctx["ta_inst"] == idx
    topic_pos = ctx["ta_topic"][mask]
    share_vals = subs["l3"]["share"][idx, topic_pos]
    topic_ids = np.asarray(ctx["topic_ids"], dtype=object)[topic_pos]

    df = pd.DataFrame({
        "topic_id": topic_ids,
        "vol_full": ctx["ta_vol_full"][mask],
        "vol_frac": ctx["ta_vol_frac"][mask],
        "share": share_vals,
    })

    tree_col = f"{subs['tree']}_subfield_id"
    dim = ctx["topics_dim_df"][["topic_id", tree_col, "is_excluded", "top25pct_frontier"]].rename(
        columns={tree_col: "subfield_id"})
    dim = dim.merge(_topics_dim_extra(ctx), on="topic_id", how="left")
    out = df.merge(dim, on="topic_id", how="left")
    out = out.merge(_subfield_field_domain_map(ctx), on="subfield_id", how="left")
    out = out.reindex(columns=_TOPICS_COLS_NO_RANK).reset_index(drop=True)

    vol_col = "vol_full" if subs["basis"] == "full" else "vol_frac"
    order = out.sort_values([vol_col, "topic_id"], ascending=[False, True]).index.to_numpy()
    ranks = np.empty(len(out), dtype="int64")
    ranks[order] = np.arange(1, len(out) + 1)
    out["rank_volume"] = ranks
    return out.reindex(columns=TOPICS_COLS)


# ------------------------------------------------------------ yearly trend

def yearly_by_domain(ctx: dict, iid: str, tree: str) -> pd.DataFrame:
    """(year, domain_id, domain_name, vol_full, vol_frac) via a single duckdb
    query over `topics_all.parquet`, filtered by this institution's `inst_key`
    (predicate pushdown -- warm target < 150 ms). `tree` picks which
    `{tree}_subfield_id` -> FIXED domain map resolves each topic's domain."""
    years = _year_cols(ctx)
    if not years:
        return pd.DataFrame(columns=YEARLY_COLS)

    inst_key = int(ctx["index_by_id"].loc[iid, "inst_key"])
    tree_col = f"{tree}_subfield_id"
    topic_domain = ctx["topics_dim_df"][["topic_id", tree_col]].rename(columns={tree_col: "subfield_id"})
    topic_domain = topic_domain.merge(
        _subfield_field_domain_map(ctx)[["subfield_id", "domain_id", "domain_name"]],
        on="subfield_id", how="left")[["topic_id", "domain_id", "domain_name"]]

    con = duckdb.connect()
    con.register("_topic_domain", topic_domain)
    ta_posix = Path(ctx["topics_all_path"]).as_posix()
    year_cols_sql = ", ".join(f"vol_full_{y}, vol_frac_{y}" for y in years)
    year_select = ", ".join(f"SUM(vol_full_{y}) AS vol_full_{y}, SUM(vol_frac_{y}) AS vol_frac_{y}"
                            for y in years)
    # Filter INSIDE the scanned CTE (not after the join) so duckdb's parquet
    # reader gets `inst_key = ?` as its own predicate -- row-group pruning on
    # this 533 MB file is what keeps this under the 150 ms warm budget.
    sql = f"""
        WITH ta_filtered AS (
            SELECT topic_id, {year_cols_sql}
            FROM read_parquet('{ta_posix}')
            WHERE inst_key = {inst_key}
        )
        SELECT td.domain_id, td.domain_name, {year_select}
        FROM ta_filtered ta
        JOIN _topic_domain td USING (topic_id)
        GROUP BY td.domain_id, td.domain_name
    """
    wide = con.sql(sql).df()
    con.close()

    rows = []
    for _, r in wide.iterrows():
        for y in years:
            rows.append({"year": y, "domain_id": r["domain_id"], "domain_name": r["domain_name"],
                        "vol_full": r[f"vol_full_{y}"], "vol_frac": r[f"vol_frac_{y}"]})
    out = pd.DataFrame(rows, columns=YEARLY_COLS)

    # topics_all only holds works that carry a
    # primary topic, so Sigma over domains runs a few works short of the index's
    # own by-year totals (measured up to 0.23 %). The yearly
    # breakdown is SWAPPABLE with the document-type view, whose totals ARE the
    # index totals -- so the residual is carried as an explicit
    # "Unclassified" domain (id 0, the shared UNCLASSIFIED_DOMAIN_ID convention)
    # and both views sum to the same number per year. Never negative: a
    # float32 rounding excess is clipped at 0.
    row = ctx["index_by_id"].loc[iid]
    tot_full = _parse_packed_years(row["vol_full_by_year_this_run"])
    tot_frac = _parse_packed_years(row["vol_frac_by_year_this_run"])
    resid = []
    for y in years:
        got_full = float(out.loc[out["year"] == y, "vol_full"].sum())
        got_frac = float(out.loc[out["year"] == y, "vol_frac"].sum())
        resid.append({"year": y, "domain_id": UNCLASSIFIED_DOMAIN_ID, "domain_name": UNCLASSIFIED_DOMAIN_NAME,
                      "vol_full": max(int(round(tot_full.get(y, got_full) - got_full)), 0),
                      "vol_frac": max(tot_frac.get(y, got_frac) - got_frac, 0.0)})
    return pd.concat([out, pd.DataFrame(resid, columns=YEARLY_COLS)], ignore_index=True)


UNCLASSIFIED_DOMAIN_ID = 0
UNCLASSIFIED_DOMAIN_NAME = "Unclassified"


def _parse_packed_years(packed) -> dict[int, float]:
    """'YEAR:value|YEAR:value|.' (index.vol_*_by_year_this_run) -> {year: value}."""
    if not isinstance(packed, str) or not packed:
        return {}
    out = {}
    for tok in packed.split("|"):
        y, v = tok.split(":")
        out[int(y)] = float(v)
    return out


# --------------------------------------------------------------- SDG / ERC

def sdg_table(ctx: dict, iid: str) -> pd.DataFrame:
    """DENSE 16-row SDG profile (`sdg.parquet` ships all 16 per institution,
    data_contract.yaml) joined to `resources/sdg_labels.csv` (carries both
    `sdg_label` and the numbered `sdg_label_numbered`, L36). `si_status`
    (L34) thresholds the fractional `mass` column -- `esi` itself has no
    floor observed (data_contract.yaml) and is kept as shipped."""
    row = ctx["sdg_df"][ctx["sdg_df"]["institution_id"] == iid]
    out = row.merge(_sdg_labels(ctx), on="sdg_idx", how="right")  # right join: 16 rows even if iid is thin
    out["institution_id"] = iid
    out["si_status"] = si_status_from_mass(out["mass"])
    return out.reindex(columns=SDG_COLS).reset_index(drop=True)


def erc_table(ctx: dict, iid: str) -> pd.DataFrame:
    """Sparse (nonzero-mass panels only, matching `erc.parquet`'s own
    convention) ERC profile joined to `resources/erc_panels.csv`. `si_status`
    (L34) thresholds the fractional `mass` column -- `si` itself has no floor
    observed (data_contract.yaml) and is kept as shipped."""
    row = ctx["erc_df"][ctx["erc_df"]["institution_id"] == iid].copy()
    row["si_status"] = si_status_from_mass(row["mass"])
    out = row.merge(_erc_panels(ctx), on="panel_idx", how="left")
    return out.reindex(columns=ERC_COLS).reset_index(drop=True)


# ---------------------------------------------------------------- wordcloud

def wordcloud_weights(ctx: dict, subs: dict, iid: str) -> tuple[dict, dict]:
    """`({subfield_name: vol on subs['basis']}, {subfield_name: domain_id})`
    over subfields with vol > 0 -- vol, not share (VIZ_SPEC wordcloud caption
    'size = works on the current basis')."""
    vol_col = "vol_frac" if subs["basis"] == "frac" else "vol_full"
    df = subs["subfields_df"]
    row = df[(df["institution_id"] == iid) & (df[vol_col] > 0)]
    fd = _subfield_field_domain_map(ctx)[["subfield_id", "subfield_name", "domain_id"]]
    row = row.merge(fd, on="subfield_id", how="left")
    weights = dict(zip(row["subfield_name"], row[vol_col].astype(float)))
    domains = dict(zip(row["subfield_name"], row["domain_id"]))
    return weights, domains
