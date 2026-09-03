"""
app/lib/compare_data.py -- Compare-view data frames over EXACTLY TWO
institutions.

Pure functions, no Streamlit import: every function takes the engine's `ctx`
(+ often `subs`, one scenario's substrates from `lib.engine.substrates.
load_substrates`) and the pair's two institution ids, and returns a plain
pandas DataFrame or dict. Compare is PINNED to tree="bestfit", basis="full" -- no function here takes a `tree`/`basis` argument: a
caller either passes `subs = lib.engine.substrates.load_substrates(ctx,
"bestfit", "full")` (or `lib.engine.scenario_cache.get("bestfit", "full")`
in the live app) itself, or -- for the two functions that do not need a
whole scenario dict (`cards`, `relationship`) -- this module loads that one
pin internally.

Every number this module ships is either (a) read straight off a shipped
table with no reinterpretation, or (b) IDENTICAL, cell for cell, to what
the reference version's `compare_data.py` computed for the same
(institution, taxon) pair -- verified against the reference figures for
three pairs in `tests/test_compare_data.py`. The file this module
descends from carried a much larger surface (an N-institution "Compare by"
metric-selector matrix, ERC panels, dynamics, a pooled frontier scatter,
grey-accounting coverage, bootstrap-CI impact-by-subfield): all of that is
DELETED and stays only in the archive -- no other file
outside this module's fence still imports a deleted name (aside from two
owned-elsewhere test files).

ONE function survives with its name and signature unchanged:
`fields_long(ctx, subs, ids)` -- `lib/collab_data.py:reciprocity_frame` imports and calls it directly,
so it cannot be renamed or dropped without touching a file outside this
module's fence.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from . import links
from . import leaders_data as LD
from . import profile_data as P
from .app_config import CFG
from .engine.substrates import load_substrates

# A concurrency fix, found via a stress test (phase B): same
# shared-connection + bounded-LRU idiom as `lib/collab_data.py`/
# `lib/leaders_data.py` (module-duplicated) -- `_topic_yearly_own`'s
# per-pair `ctx[key] = df` cache used to accumulate forever.
_DUCK_LOCK = threading.Lock()
_PAIR_CACHE_MAX = 32


def _duck(ctx: dict):
    """Cursor onto the ONE process-wide, memory-bounded duckdb connection
    (`SET memory_limit='512MB'` + `SET threads TO 2`), created lazily on
    `ctx` under `_DUCK_LOCK` -- identical helper to `lib/collab_data.py:
    _duck` (same shared `ctx` object in production, so truly one connection
    per process)."""
    with _DUCK_LOCK:
        con = ctx.get("_duck_con")
        if con is None:
            con = duckdb.connect()
            con.execute("SET memory_limit='512MB'")
            con.execute("SET threads TO 2")
            ctx["_duck_con"] = con
    return con.cursor()


def _lru_touch(ctx: dict, key: str, prefix: str) -> None:
    """Marks `key` (cache namespace `prefix`) most-recently-used, evicting
    the least-recently-used key in that namespace once more than
    `_PAIR_CACHE_MAX` are resident -- identical helper to
    `lib/collab_data.py:_lru_touch`."""
    with _DUCK_LOCK:
        order = ctx.setdefault(f"_lru::{prefix}", OrderedDict())
        order[key] = None
        order.move_to_end(key)
        while len(order) > _PAIR_CACHE_MAX:
            oldest, _ = order.popitem(last=False)
            ctx.pop(oldest, None)

# ---------------------------------------------------------------------------
# Windows & pin: every figure in this module is CORE-AR 2020-2024
# unless its own docstring says otherwise. `DYNAMICS_W1`/`DYNAMICS_W2` are
# the two sub-windows the one "change" figure this module computes (cards'
# `vol_change`) splits the core window into -- ported verbatim from the
# reference `compare_data.py` (same numbers, same helper functions, ANCHOR-tested).
# ---------------------------------------------------------------------------
CORE_WINDOW = tuple(CFG["window"])                  # (2020, 2024)
DYNAMICS_W1 = (2020, 2022)  # mean annual volume, window 1 (3 years)
DYNAMICS_W2 = (2023, 2024)  # mean annual volume, window 2 (2 years)

# `collab_topic_vols.parquet` (and
# `collab_pair_domain_year.parquet`) only carry rows for pairs with
# `core_total >= 5` (collab_data's own qualifying floor, `collab_data.
# PAIR_TOPICS_FLOOR`) -- kept here as a plain int (not imported from
# `collab_data`, which itself imports THIS module -- see the module
# docstring on the one-way `fields_long` dependency; importing back would
# be a circular import) so `shared_frontier`/`relationship` never have to
# guess the number.
PAIR_QUALIFYING_FLOOR = 5

ELITE_FRONTIER_PERCENTILE = 0.90  # global top-decile cut on frontier_score_latest (the "world top-decile" glyph)


def _num(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f


def _window_mean(vol_by_year: dict, window: tuple[int, int]) -> float:
    return float(np.mean([vol_by_year.get(y, 0.0) for y in range(window[0], window[1] + 1)]))


def _dynamics_value(vol_by_year: dict) -> float:
    """(mean annual volume, window 2) minus (window 1), over window 1 -- the
    reference implementation's own dynamics formula, ported verbatim (the
    Key-figure cards' 'change in mean annual volume 2020-22 -> 2023-24'
    reuses this exact helper, not a rewrite)."""
    w1 = _window_mean(vol_by_year, DYNAMICS_W1)
    w2 = _window_mean(vol_by_year, DYNAMICS_W2)
    if w1 <= 0:
        return np.nan
    return (w2 - w1) / w1


def _concat_sorted(frames: list[pd.DataFrame], sort_cols: list[str], cols: list[str]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=cols)
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(sort_cols).reset_index(drop=True).reindex(columns=cols)


# ---------------------------------------------------------------------------
# fields_long -- KEPT verbatim (collab_data.reciprocity_frame's own import,
# see module docstring). subfields_long/sdg_long are private helpers this
# module still needs internally for the shape/SDG frames below.
# ---------------------------------------------------------------------------

FIELDS_LONG_COLS = ["institution_id"] + P.FIELDS_COLS
SUBFIELDS_LONG_COLS = ["institution_id"] + P.SUBFIELDS_COLS
SDG_LONG_COLS = ["institution_id"] + P.SDG_COLS


def fields_long(ctx: dict, subs: dict, ids: list[str]) -> pd.DataFrame:
    """`profile_data.fields_table` per id, stacked, `institution_id` first.
    KEPT for `lib/collab_data.py:reciprocity_frame`, which imports this
    function by name (`from. import compare_data as CD; CD.fields_long(.)`)
    from outside this module's fence, so this signature and
    behaviour cannot change."""
    frames = []
    for iid in ids:
        df = P.fields_table(ctx, subs, iid)
        df.insert(0, "institution_id", iid)
        frames.append(df)
    return _concat_sorted(frames, ["institution_id", "field_id"], FIELDS_LONG_COLS)


def subfields_long(ctx: dict, subs: dict, ids: list[str]) -> pd.DataFrame:
    """`profile_data.subfields_table` per id (nonzero-mass subfields only,
    unfloored si), stacked, `institution_id` first."""
    frames = []
    for iid in ids:
        df = P.subfields_table(ctx, subs, iid)
        df.insert(0, "institution_id", iid)
        frames.append(df)
    return _concat_sorted(frames, ["institution_id", "subfield_id"], SUBFIELDS_LONG_COLS)


def sdg_long(ctx: dict, ids: list[str]) -> pd.DataFrame:
    """`profile_data.sdg_table` per id (DENSE 16 rows each), stacked,
    `institution_id` first."""
    frames = []
    for iid in ids:
        df = P.sdg_table(ctx, iid)
        df.insert(0, "institution_id", iid)
        frames.append(df)
    return _concat_sorted(frames, ["institution_id", "sdg_idx"], SDG_LONG_COLS)


# ---------------------------------------------------------------------------
# European-baseline / population-mean lookups (share_refs.parquet, impact_
# taxa.parquet's own population mean, fwci_taxa_ref.parquet) -- ported
# verbatim from 's `compare_data.py`, restricted to the two grains this
# module still offers (subfield, sdg). Field/ERC branches deleted (E12:
# stays the archive).
# ---------------------------------------------------------------------------

def _load_share_refs(ctx: dict) -> pd.DataFrame:
    """Lazy, ctx-cached: `share_refs.parquet` -- grain x taxon_id x basis,
    the unweighted mean-of-ratios European reference share."""
    if "share_refs_df" not in ctx:
        ctx["share_refs_df"] = pd.read_parquet(Path(ctx["data_dir"]) / "share_refs.parquet")
    return ctx["share_refs_df"]


def _share_ref_series(ctx: dict, grain: str, basis: str) -> pd.Series:
    """taxon_id -> eu_mean_share at (grain, basis), cached on ctx."""
    key = f"_share_ref_{grain}_{basis}"
    if key not in ctx:
        refs = _load_share_refs(ctx)
        sub = refs[(refs["grain"] == grain) & (refs["basis"] == basis)]
        ctx[key] = sub.set_index("taxon_id")["eu_mean_share"].astype("float64")
    return ctx[key]


def _load_impact_taxa(ctx: dict) -> pd.DataFrame:
    """Lazy, ctx-cached: `impact_taxa.parquet` -- institution x grain x
    taxon_id, PP10_WD (FULL/binary, BASIS- and BESTFIT-TREE-PINNED), floored
    at n_covered_pp>=1 only."""
    if "impact_taxa_df" not in ctx:
        ctx["impact_taxa_df"] = pd.read_parquet(Path(ctx["data_dir"]) / "impact_taxa.parquet")
    return ctx["impact_taxa_df"]


def _pp_ref_means(ctx: dict, level: str) -> pd.Series:
    """Population mean `pp10_wd` per taxon at this grain (NO floor
    re-applied -- the population is exactly 'institutions with a row'),
    cached per level on ctx."""
    key = f"_impact_taxa_mean_pp10_wd_{level}"
    if key not in ctx:
        taxa = _load_impact_taxa(ctx)
        sub = taxa[taxa["grain"] == level]
        ctx[key] = sub.groupby("taxon_id")["pp10_wd"].mean()
    return ctx[key]


def _pp_taxon(ctx: dict, ids: list[str], level: str) -> pd.DataFrame:
    """institution_id, taxon_id, pp10_wd, n_covered_pp, eu_mean_pp10_wd
    from `impact_taxa.parquet`. BASIS- and BESTFIT-TREE-PINNED: this never
    reads `subs` (decisions log 2026-09-02, ported from 's `_pp_frame`)."""
    taxa = _load_impact_taxa(ctx)
    sub = taxa[(taxa["grain"] == level) & (taxa["institution_id"].isin(ids))]
    ref = _pp_ref_means(ctx, level)
    out = pd.DataFrame({
        "institution_id": sub["institution_id"].to_numpy(),
        "taxon_id": sub["taxon_id"].astype(int).to_numpy(),
        "pp10_wd": sub["pp10_wd"].astype("float64").to_numpy(),
        "n_covered_pp": sub["n_covered_pp"].astype("float64").to_numpy(),
    })
    out["eu_mean_pp10_wd"] = out["taxon_id"].map(ref).astype("float64")
    return out


def _load_fwci_taxa(ctx: dict) -> pd.DataFrame:
    """Lazy, ctx-cached: `fwci_taxa.parquet` -- one row per (institution_id,
    grain, taxon_id), n_covered>=3 only (the source table's own floor)."""
    if "fwci_taxa_df" not in ctx:
        ctx["fwci_taxa_df"] = pd.read_parquet(Path(ctx["data_dir"]) / "fwci_taxa.parquet")
    return ctx["fwci_taxa_df"]


def _load_fwci_taxa_ref(ctx: dict) -> pd.DataFrame:
    """Lazy, ctx-cached: `fwci_taxa_ref.parquet` -- the European corpus-wide
    reference MEDIAN per (grain, taxon_id), not institution filtered, no
    floor (a real 0.0 -- a genuine humanities citation-practice fact
    flows through untouched, never truthiness-tested away)."""
    if "fwci_taxa_ref_df" not in ctx:
        ctx["fwci_taxa_ref_df"] = pd.read_parquet(Path(ctx["data_dir"]) / "fwci_taxa_ref.parquet")
    return ctx["fwci_taxa_ref_df"]


def _fwci_taxon(ctx: dict, ids: list[str], level: str) -> pd.DataFrame:
    """institution_id, taxon_id, fwci_median, fwci_mean, n_covered_fwci,
    eu_median_fwci -- from `fwci_taxa.parquet`/`fwci_taxa_ref.parquet`.
    BASIS- and BESTFIT-TREE-PINNED (never reads `subs`, decisions log
    2026-09-01, ported from 's `_fwci_frame`)."""
    taxa = _load_fwci_taxa(ctx)
    sub = taxa[(taxa["grain"] == level) & (taxa["institution_id"].isin(ids))]
    ref = _load_fwci_taxa_ref(ctx)
    ref = ref[ref["grain"] == level].set_index("taxon_id")["eu_median_work_fwci"].astype("float64")
    out = pd.DataFrame({
        "institution_id": sub["institution_id"].to_numpy(),
        "taxon_id": sub["taxon_id"].astype(int).to_numpy(),
        "fwci_median": sub["fwci_median"].astype("float64").to_numpy(),
        "fwci_mean": sub["fwci_mean"].astype("float64").to_numpy(),
        "n_covered_fwci": sub["n_covered"].astype("float64").to_numpy(),
    })
    out["eu_median_fwci"] = out["taxon_id"].map(ref).astype("float64")
    return out


def _taxon_si_from_share(share: pd.Series, taxon_id: pd.Series, ref: pd.Series) -> pd.Series:
    """`share / eu_mean_share`, joined by `taxon_id` -- the reference
    version's own SDG-grain SI formula (`_taxon_si_from_share`, ported
    verbatim): SDG has no stored
    `si` column at all (`profile_data.SDG_COLS` ships `esi`, a DIFFERENT
    figure `sdg_table` computes -- never read here), so SI is recomputed
    on the fly against the SAME `share_refs.parquet` mean the share metric's
    own `eu_mean_share` reads. 0-safe (a taxon with a zero population mean
    degrades to NaN, never inf/ZeroDivisionError)."""
    mean_share = taxon_id.map(ref).astype("float64")
    share = share.astype("float64")
    with np.errstate(invalid="ignore", divide="ignore"):
        return pd.Series(np.where(mean_share > 0, share / mean_share, np.nan), index=share.index)


def _share_and_si(ctx: dict, subs: dict, ids: list[str], level: str) -> pd.DataFrame:
    """institution_id, taxon_id, share_full, si, eu_mean_share -- the
    `share`/`si` values the reference version's own `_share_frame`/
    `_si_frame` computed at
    subfield/sdg grain (dropping the OLD per-field `field_id` filter: it
    only ever restricted which ROWS shipped, never the VALUE of any row --
    both `_share_denom_value` and `_taxon_si_from_share`'s population mean
    were always computed off the institution's WHOLE taxonomy regardless of
    that filter, per the anchor-test proof). `si` at SUBFIELD grain
    is the base frame's own (unfloored) `si` column; at SDG grain there is
    no such column (`profile_data.SDG_COLS` ships `esi`, unrelated) so it is
    RECOMPUTED as `share / eu_mean_share` (`_taxon_si_from_share`, the
    reference version's own SDG branch, ported verbatim)."""
    basis = subs["basis"]
    ref = _share_ref_series(ctx, level, basis)
    if level == "subfield":
        base = subfields_long(ctx, subs, ids)
        out = base[["institution_id", "subfield_id", "share", "si"]].rename(
            columns={"subfield_id": "taxon_id", "share": "share_full"})
    else:  # sdg
        base = sdg_long(ctx, ids)
        out = base[["institution_id", "sdg_idx", "share"]].rename(
            columns={"sdg_idx": "taxon_id", "share": "share_full"})
        out["si"] = _taxon_si_from_share(out["share_full"], out["taxon_id"], ref)
    out["eu_mean_share"] = out["taxon_id"].map(ref).astype("float64")
    return out


def _taxon_metrics(ctx: dict, subs: dict, ids: list[str], level: str) -> pd.DataFrame:
    """institution_id, taxon_id, share_full, si, eu_mean_share, pp10_wd,
    n_covered_pp, eu_mean_pp10_wd, fwci_median, fwci_mean, n_covered_fwci,
    eu_median_fwci -- ONE merged pass over the three independent sources
    (share/si are subs-aware and basis/tree-toggled with the page's pin;
    pp/fwci are basis- and bestfit-tree-PINNED regardless) restricted to
    `level in {"subfield", "sdg"}` -- ERC and field grain are deleted from
    this module."""
    assert level in ("subfield", "sdg"), f"unsupported level {level!r} (only subfield/sdg survive this trim)"
    out = _share_and_si(ctx, subs, ids, level)
    out = out.merge(_pp_taxon(ctx, ids, level), on=["institution_id", "taxon_id"], how="left")
    out = out.merge(_fwci_taxon(ctx, ids, level), on=["institution_id", "taxon_id"], how="left")
    return out


# ---------------------------------------------------------------------------
# cards -- Key-figure cards (no `subs`: every figure here is either an
# index.parquet column or derived from one, never subfield/topic-grain
# scenario data).
# ---------------------------------------------------------------------------

# The 7 legacy figures the reference version's `overview` shipped, kept
#   EQUAL to the golden `overview` figures -- window: `total_full_2020_2024` /
# `total_frac_2020_2024` are the 2020-2024 analytical window (config.yaml
# `window`), ALL FIVE harvested corpus types (article/review/book/
# book-chapter/letter, not narrowed to article+review) -- the SAME window
# `intl_share`/`company_share`/`sdg_tagged_share`/`frontier_top25_share`/
# `pp_top10_frac` are denominated on. `ci_low`/`ci_high` (the reference
# version's overview also carried these) are DROPPED here -- the card
# list has no confidence interval, point estimate only.
_CARD_INDEX_COLS = {
    "vol_full": "total_full_2020_2024", "vol_frac": "total_frac_2020_2024",
    "sdg_share": "sdg_tagged_share", "frontier_top25_share": "frontier_top25_share",
    "pp": "pp_top10_frac", "intl_share": "intl_share", "company_share": "company_share",
    "fwci_eu_median": "fwci_eu_median",  # added separately -- absent until it lands (NaN meanwhile)
    "star_share": "star_share", "n_stars": "n_stars", "n_topics_led_fair": "n_topics_led_fair",
}
CARDS_COLS = (["institution_id"] + list(_CARD_INDEX_COLS) + ["vol_change", "led_pool"]
             + [f"{c}_eu_median" for c in list(_CARD_INDEX_COLS) + ["vol_change"]])


def _eu_median_index(index_df: pd.DataFrame, col: str) -> float:
    """NaN-safe median of one `index.parquet` column over the WHOLE
    population."""
    if col not in index_df.columns:
        return float("nan")
    vals = pd.to_numeric(index_df[col], errors="coerce").dropna()
    return float(vals.median()) if len(vals) else float("nan")


def _all_vol_changes(ctx: dict) -> pd.Series:
    """`vol_change` for EVERY institution in the index, cached on ctx
    the one card figure with no ready-made index column, so its own
    population median needs one full pass parsing `vol_full_by_year_this_
    run` (cheap, ~7,557 short packed strings)."""
    key = "_all_vol_changes"
    if key not in ctx:
        idx = ctx["index_df"]
        vals = [_dynamics_value(P._parse_packed_years(p)) for p in idx["vol_full_by_year_this_run"]]
        ctx[key] = pd.Series(vals, index=idx["institution_id"].to_numpy(), dtype="float64")
    return ctx[key]


def cards(ctx: dict, ids: list[str]) -> pd.DataFrame:
    """Key-figure cards, one row per institution: the 7 legacy figures
    (EQUAL to the reference version's `overview`, see `_CARD_INDEX_COLS`'s
    own docstring for windows) plus `vol_change` (change in MEAN ANNUAL full
    volume, 2020-22 -> 2023-24, the reference version's own
    `_dynamics_value`/`_window_mean` reused verbatim),
    `fwci_eu_median`/`star_share`/`n_stars`/`n_topics_led_fair` and `led_pool` ('universities' when `type == "education"`,
    else 'all institutions', the fair-pool rule). EVERY numeric figure also
    ships a `<col>_eu_median` twin: the NaN-safe median of that SAME figure
    over the whole 7,557-row index, computed once
    per call, identical for both rows of a 2-institution pair by
    construction (a population statistic, not a per-institution one)."""
    idx = ctx["index_df"]
    idx_by_id = ctx["index_by_id"]
    all_changes = _all_vol_changes(ctx)

    rows = []
    for iid in ids:
        row = idx_by_id.loc[iid]

        def _v(col):
            if col not in row.index:
                return float("nan")
            v = row[col]
            return float("nan") if pd.isna(v) else float(v)

        rec = {"institution_id": iid}
        for out_col, src_col in _CARD_INDEX_COLS.items():
            rec[out_col] = _v(src_col)
        rec["vol_change"] = float(all_changes.get(iid, np.nan))
        rec["led_pool"] = "universities" if str(row["type"]) == "education" else "all institutions"
        rows.append(rec)
    out = pd.DataFrame(rows)

    for out_col, src_col in _CARD_INDEX_COLS.items():
        out[f"{out_col}_eu_median"] = _eu_median_index(idx, src_col)
    changes = all_changes.dropna()
    out["vol_change_eu_median"] = float(changes.median()) if len(changes) else float("nan")
    return out.reindex(columns=CARDS_COLS)


# ---------------------------------------------------------------------------
# top_subfields / all_subfields -- the Thematic-shape frame, in the
# two_tab_bars long-by-(row, institution) SHAPE (one row per subfield x
# institution) but carrying BOTH the Profile metric (share_full) and the
# Impact metric (pp10_wd) as separate named columns rather than a single
# `value` column picked by an active tab (`charts_compare.two_tab_bars`'s
# own contract).
# ---------------------------------------------------------------------------

SUBFIELD_WIDE_COLS = [
    "row_order", "subfield_id", "subfield_name", "field_id", "field_name",
    "domain_id", "domain_name", "domain_order", "field_rank", "institution_id",
    "share_full", "eu_mean_share", "si", "vol_full", "vol_frac", "combined_vol_full",
    "pp10_wd", "n_covered_pp", "eu_mean_pp10_wd",
    "fwci_median", "fwci_mean", "n_covered_fwci", "eu_median_fwci",
]

# The reference version's own `PAL.OA_DOMAIN_ORDER` display order (1=Life
# Sciences, 2=Health Sciences, 3=Physical Sciences, 4=Social Sciences) --
# copied here as a plain tuple (not imported from `lib.palette`, to avoid a
# needless cross-fence coupling for four ints) so field grouping has a
# stable, documented order without depending on chart-layer code.
_OA_DOMAIN_ORDER = (1, 2, 3, 4)
_OA_DOMAIN_ORDER_MAP = {d: i for i, d in enumerate(_OA_DOMAIN_ORDER)}


def _subfields_frame(ctx: dict, subs: dict, ids: list[str], n: int | None) -> pd.DataFrame:
    """Shared builder for `top_subfields`/`all_subfields`: a DENSE grid over
    every one of the 252 bestfit subfields x every id in `ids` ("All 252
    subfields in Excel" -- a subfield neither institution publishes in still
    gets a row, `share_full`/`vol_full`/`vol_frac` = 0.0, `si`/`pp10_wd`/
    `fwci_median` = NaN, absence not a fabricated number, same convention
    every metric frame in this module already follows), `combined_vol_full`
    = the SUM of `vol_full` across the two ids (0.0 for a subfield neither
    touches). `n=None` returns all 252; `n=20` (top_subfields' own default)
    keeps only the `n` subfields with the largest `combined_vol_full`.

    Row order ("fields grouped, subfields by combined volume within
    field"): fields ordered by (OpenAlex domain display order, then field_id
    ascending -- `field_rank`), subfields within a field ordered by
    `combined_vol_full` descending; the two institution-rows of one subfield
    are adjacent (same `combined_vol_full` by construction). `row_order` is
    the resulting 0-based position, for a caller that cannot trust its own
    frame handling to preserve row order untouched."""
    dim = P._subfield_field_domain_map(ctx)[["subfield_id", "subfield_name", "field_id", "field_name",
                                             "domain_id", "domain_name"]]
    metrics = _taxon_metrics(ctx, subs, ids, "subfield").rename(columns={"taxon_id": "subfield_id"})
    vol = subfields_long(ctx, subs, ids)[["institution_id", "subfield_id", "vol_full", "vol_frac"]]
    metrics = metrics.merge(vol, on=["institution_id", "subfield_id"], how="left")

    grid = pd.MultiIndex.from_product([dim["subfield_id"].to_numpy(), ids],
                                      names=["subfield_id", "institution_id"]).to_frame(index=False)
    out = grid.merge(dim, on="subfield_id", how="left").merge(metrics, on=["subfield_id", "institution_id"], how="left")
    for c in ("share_full", "vol_full", "vol_frac"):
        out[c] = out[c].fillna(0.0)

    combined = out.groupby("subfield_id")["vol_full"].sum().rename("combined_vol_full")
    out = out.drop(columns=["combined_vol_full"], errors="ignore").merge(combined, on="subfield_id", how="left")
    out["domain_order"] = out["domain_id"].map(_OA_DOMAIN_ORDER_MAP)

    field_key = dim[["field_id", "domain_id"]].drop_duplicates().copy()
    field_key["domain_order"] = field_key["domain_id"].map(_OA_DOMAIN_ORDER_MAP)
    field_key = field_key.sort_values(["domain_order", "field_id"]).reset_index(drop=True)
    field_key["field_rank"] = np.arange(len(field_key))
    out = out.merge(field_key[["field_id", "field_rank"]], on="field_id", how="left")

    if n is not None:
        top_ids = combined.sort_values(ascending=False).head(n).index
        out = out[out["subfield_id"].isin(top_ids)]

    out = out.sort_values(["field_rank", "combined_vol_full", "subfield_id", "institution_id"],
                          ascending=[True, False, True, True], kind="mergesort").reset_index(drop=True)
    out["row_order"] = out.index
    return out.reindex(columns=SUBFIELD_WIDE_COLS)


def top_subfields(ctx: dict, subs: dict, ids: list[str], n: int = 20) -> pd.DataFrame:
    """The Thematic-shape chart data: the `n` (default 20) subfields (bestfit
    taxonomy) with the largest COMBINED `vol_full` across the two `ids`, long
    by (subfield, institution). See `_subfields_frame` for the exact column
    contract, the density rule and the row-order rule."""
    return _subfields_frame(ctx, subs, ids, n)


def all_subfields(ctx: dict, subs: dict, ids: list[str]) -> pd.DataFrame:
    """The SAME contract as `top_subfields`, uncapped -- all 252 bestfit
    subfields ("All 252 subfields in Excel")."""
    return _subfields_frame(ctx, subs, ids, None)


# ---------------------------------------------------------------------------
# sdg_frame -- the SDG-profile frame, same contract at SDG grain (16 goals
# `profile_data.sdg_table`'s own dense convention; see the docstring
# below for the "17" vs "16" note).
# ---------------------------------------------------------------------------

SDG_WIDE_COLS = [
    "row_order", "sdg_idx", "sdg_number", "sdg_label", "institution_id",
    "share_full", "eu_mean_share", "si", "vol_full", "vol_frac",
    "pp10_wd", "n_covered_pp", "eu_mean_pp10_wd",
    "fwci_median", "fwci_mean", "n_covered_fwci", "eu_median_fwci",
]


def _load_sdg_year(ctx: dict) -> pd.DataFrame:
    """Lazy, ctx-cached: `sdg_year.parquet` -- institution x sdg x year
    (2020-2025 on disk), `mass_frac`/`mass_full`, tree-independent."""
    if "sdg_year_df" not in ctx:
        ctx["sdg_year_df"] = pd.read_parquet(Path(ctx["data_dir"]) / "sdg_year.parquet")
    return ctx["sdg_year_df"]


def _sdg_year_window_mass(ctx: dict, ids: list[str]) -> pd.DataFrame:
    """`sdg_year.parquet`, window-sliced to `CORE_WINDOW` (2020-2024),
    summed per (institution_id, sdg_idx), BOTH `mass_full`/`mass_frac`
    carried through -- the CORE-window, both-basis "volume tagged to this
    goal" figure `sdg_frame`'s own `vol_full`/`vol_frac` reads (a DIFFERENT
    number from `share_full`'s own denominator, which is `sdg_long`'s
    WHOLE-RUN 2020-2025 mass -- both are genuine, documented separately)."""
    df = _load_sdg_year(ctx)
    sub = df[df["institution_id"].isin(ids) & df["year"].between(CORE_WINDOW[0], CORE_WINDOW[1])]
    return sub.groupby(["institution_id", "sdg_idx"], as_index=False, observed=True)[["mass_frac", "mass_full"]].sum()


def sdg_frame(ctx: dict, subs: dict, ids: list[str]) -> pd.DataFrame:
    """The SDG-profile chart data, same contract as `top_subfields`/
    `all_subfields`, at SDG grain. 16 rows per institution (DENSE
    `profile_data.sdg_table`'s own convention: `sdg.parquet` ships all 16
    goals per institution, so "17" in some planning prose counts the
    'untagged' caption line as a pseudo-17th entry, not a 17th SDG row here).
    `vol_full`/`vol_frac` are `sdg_year.parquet`'s CORE-window (2020-2024)
    tagged mass on both bases -- NOT the same number as `share_full`'s own
    whole-run (2020-2025) denominator, both genuine and separately
    documented (`_sdg_year_window_mass`'s own docstring).

    `df.attrs["untagged_share"]` carries `{institution_id: 1
    index.sdg_tagged_share}` ("untagged share per institution, for the
    caption") -- NaN when the index cell itself is null, never a fabricated
    0."""
    out = _taxon_metrics(ctx, subs, ids, "sdg").rename(columns={"taxon_id": "sdg_idx"})
    win = _sdg_year_window_mass(ctx, ids).rename(columns={"mass_full": "vol_full", "mass_frac": "vol_frac"})
    out = out.merge(win, on=["institution_id", "sdg_idx"], how="left")
    out["vol_full"] = out["vol_full"].fillna(0.0)
    out["vol_frac"] = out["vol_frac"].fillna(0.0)

    labels = P._sdg_labels(ctx)[["sdg_idx", "sdg_number", "sdg_label"]]
    out = out.merge(labels, on="sdg_idx", how="left")
    out = out.sort_values(["sdg_number", "institution_id"], kind="mergesort").reset_index(drop=True)
    out["row_order"] = out.index
    out = out.reindex(columns=SDG_WIDE_COLS)

    idx_by_id = ctx["index_by_id"]
    untagged = {}
    for iid in ids:
        tagged = idx_by_id.loc[iid].get("sdg_tagged_share")
        untagged[iid] = (1.0 - float(tagged)) if pd.notna(tagged) else float("nan")
    out.attrs["untagged_share"] = untagged
    return out


# ---------------------------------------------------------------------------
# frontier_positioning -- the Frontier "positioning" figures, one row per
# institution.
# ---------------------------------------------------------------------------

FRONTIER_POSITIONING_COLS = [
    "institution_id", "share_top25", "n_top25_topics_published", "n_of_those_top_decile",
    "n_topics_led_fair", "n_stars_in_frontier_topics",
]


def _elite_frontier_topic_ids(ctx: dict) -> frozenset:
    """Global top-decile topic set: topic ids in the top-10% by
    `frontier_score_latest`, cut over every SCORED topic (never the compared
    institutions' own footprint) -- the "world top-decile" glyph. Cached on
    ctx (one `topics_dim.parquet` read + one quantile)."""
    if "_elite_frontier_topic_ids" not in ctx:
        extra = P._topics_dim_extra(ctx)
        scores = pd.to_numeric(extra["frontier_score_latest"], errors="coerce")
        scored = scores.dropna()
        cutoff = float(scored.quantile(ELITE_FRONTIER_PERCENTILE)) if len(scored) else np.inf
        ctx["_elite_frontier_topic_ids"] = frozenset(extra.loc[scores >= cutoff, "topic_id"])
    return ctx["_elite_frontier_topic_ids"]


def _top25_frontier_topic_ids(ctx: dict) -> frozenset:
    """Global top-quartile-frontier topic set (`topics_dim.top25pct_
    frontier == True`) -- the shared frontier's FIXED pool, tree-independent (the narrow
    `ctx['topics_dim_df']` already carries this column, no extra read)."""
    if "_top25_frontier_topic_ids" not in ctx:
        td = ctx["topics_dim_df"]
        ctx["_top25_frontier_topic_ids"] = frozenset(td.loc[td["top25pct_frontier"] == True, "topic_id"])  # noqa: E712
    return ctx["_top25_frontier_topic_ids"]


def frontier_positioning(ctx: dict, subs: dict, ids: list[str]) -> pd.DataFrame:
    """The Frontier "positioning" row per institution: `share_top25`
    (`index.frontier_top25_share`, verbatim), `n_top25_topics_published`
    (the count of the shared frontier's FIXED top-quartile-frontier topic
    pool where this institution's OWN volume, current basis, is >= 1),
    `n_of_those_top_decile` (the subset also in the GLOBAL top-decile-by-
    `frontier_score_latest` set, `_elite_frontier_topic_ids`),
    `n_topics_led_fair` (index column, the fair pool), `n_stars_in_frontier_topics` (this
    institution's own star-work count, summed over exactly the topics it
    was just counted as publishing in above).

    `df.attrs["n_shared"]` -- the count of top-quartile-frontier
    topics where BOTH `ids` hold >= 1 publication; `frozenset` when `ids`
    has fewer than 2 entries (defined as 0 shared, never a KeyError)."""
    top25 = _top25_frontier_topic_ids(ctx)
    elite = _elite_frontier_topic_ids(ctx)
    vol_col = "vol_full" if subs["basis"] == "full" else "vol_frac"

    rows = []
    own_topics: dict[str, set] = {}
    for iid in ids:
        df = P.topics_table(ctx, subs, iid)
        pub = df[(df[vol_col] >= 1) & df["topic_id"].isin(top25)]
        own_topics[iid] = set(pub["topic_id"])
        n_decile = int(pub["topic_id"].isin(elite).sum())

        stars = LD.stars_by_topic(ctx, [iid])
        n_stars = int(stars.loc[stars["topic_id"].astype(str).isin(own_topics[iid]), "n_stars"].sum())

        row = ctx["index_by_id"].loc[iid]
        share_top25 = row.get("frontier_top25_share")
        led_fair = row.get("n_topics_led_fair")
        rows.append({
            "institution_id": iid,
            "share_top25": float(share_top25) if pd.notna(share_top25) else float("nan"),
            "n_top25_topics_published": int(len(pub)),
            "n_of_those_top_decile": n_decile,
            "n_topics_led_fair": int(led_fair) if pd.notna(led_fair) else 0,
            "n_stars_in_frontier_topics": n_stars,
        })
    out = pd.DataFrame(rows, columns=FRONTIER_POSITIONING_COLS)
    shared = set.intersection(*own_topics.values()) if len(own_topics) >= 2 else set()
    out.attrs["n_shared"] = int(len(shared))
    return out


# ---------------------------------------------------------------------------
# shared_frontier -- the mirror-chart + table data. Topic set and A/B
# volumes are IDENTICAL to the reference version's own
# `shared_frontier(ctx, subs, ids, pool="volume")` (golden-anchor tested);
# every other column is a NEW per-topic addition.
# ---------------------------------------------------------------------------

SHARED_FRONTIER_COLS = [
    "topic_id", "topic_name", "keywords", "domain_id",
    "frontier_score", "expansion", "acceleration", "is_top_decile",
    "vol_a", "vol_b", "combined_vol", "vol_joint", "joint_known",
    "change_a", "change_b", "low_volume_a", "low_volume_b",
    "rank_a", "pool_a", "rank_b", "pool_b", "stars_a", "stars_b",
    "url_a", "url_b", "url_joint",
]

LOW_VOLUME_FLOOR = 10  # "own change A/B w1->w2 with dagger under 10 works"


def _shared_frontier_topics(ctx: dict, subs: dict, ids: list[str]) -> pd.DataFrame:
    """topic_id, topic_name, x (`expansion_latest`), y (`acceleration_
    latest`), combined_vol, vol_a, vol_b -- the topics BOTH `ids` (exactly
    two) hold nonzero volume in, restricted to the shared frontier's FIXED
    top-quartile-frontier pool (`topics_dim.top25pct_frontier == True`,
    scored topics only). Ported from the reference implementation's
    `frontier_points(mode="emerging")` +
    `_frontier_pool_frame(pool="volume")` + `shared_frontier`'s own
    `owner == "shared"` filter, COLLAPSED to this module's fixed 2-
    institution case (the OLD N-institution "owner" tri-state and the
    "elite" pool alternative are deleted: the pool is fixed, only two
    institutions are ever compared now) -- values are BIT-IDENTICAL to that
    path for the rows it would have called "shared" (anchor-tested
    against the reference figures' own `shared_frontier`)."""
    assert len(ids) == 2, "shared_frontier is defined for exactly two institutions (Compare's own cap)"
    vol_col = "vol_full" if subs["basis"] == "full" else "vol_frac"
    frames = []
    for iid in ids:
        df = P.topics_table(ctx, subs, iid)
        df = df[df["quadrant"].notna() & (df["top25pct_frontier"] == True)]  # noqa: E712
        df = df.copy()
        df.insert(0, "institution_id", iid)
        frames.append(df)
    pts = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    cols = ["topic_id", "name", "x", "y", "combined_vol", "vol_a", "vol_b"]
    if pts.empty:
        return pd.DataFrame(columns=cols)

    per_id = pts.pivot_table(index="topic_id", columns="institution_id", values=vol_col,
                             aggfunc="sum", fill_value=0.0).reindex(columns=ids, fill_value=0.0)
    n_holders = (per_id > 0).sum(axis=1)
    shared_topics = per_id.index[n_holders >= 2]
    if len(shared_topics) == 0:
        return pd.DataFrame(columns=cols)
    per_id = per_id.loc[shared_topics]
    meta = pts[pts["topic_id"].isin(shared_topics)].groupby("topic_id").agg(
        name=("topic_name", "first"), x=("expansion_latest", "first"), y=("acceleration_latest", "first"))
    out = meta.join(per_id)
    out["combined_vol"] = per_id.sum(axis=1)
    out = out.reset_index().rename(columns={ids[0]: "vol_a", ids[1]: "vol_b"})
    return out.sort_values("combined_vol", ascending=False).reset_index(drop=True).reindex(columns=cols)


def _topics_dim_keywords(ctx: dict) -> pd.Series:
    """Lazy, ctx-cached: `topics_dim.parquet`'s `keywords` column, indexed by
    `topic_id` -- the ONE column neither the narrow `ctx['topics_dim_df']`
    nor `profile_data._topics_dim_extra` carries (a second, narrow read of
    the same file, same idiom as `profile_data._topics_dim_extra`)."""
    if "_topics_dim_keywords" not in ctx:
        df = pd.read_parquet(Path(ctx["data_dir"]) / "topics_dim.parquet", columns=["topic_id", "keywords"])
        ctx["_topics_dim_keywords"] = df.set_index("topic_id")["keywords"]
    return ctx["_topics_dim_keywords"]


def _topic_yearly_own(ctx: dict, a: str, b: str) -> pd.DataFrame:
    """duckdb pushdown on `topics_all.parquet`, `institution_id IN (a, b)`:
    (institution_id, topic_id, vol_full_2020.vol_full_2024) -- ctx-cached
    per pair. Needed because neither `ctx`'s own topic-grain arrays
    (`load_context`, WHOLE-RUN totals only) nor `subs['subfields_df']`
    (subfield grain, not topic grain) carry a per-topic YEARLY breakdown
    `shared_frontier`'s own "change A/B" column is the one figure in this
    module that genuinely needs a fresh topic x year read."""
    key = f"_topic_yearly_own::{a}::{b}"
    if key not in ctx:
        path = Path(ctx["topics_all_path"]).as_posix()
        con = _duck(ctx)
        try:
            df = con.execute(
                "SELECT institution_id, topic_id, vol_full_2020, vol_full_2021, vol_full_2022, "
                "vol_full_2023, vol_full_2024 FROM read_parquet(?) WHERE institution_id IN (?, ?)",
                [path, a, b],
            ).df()
        finally:
            con.close()
        ctx[key] = df
    _lru_touch(ctx, key, "topic_yearly_own")
    return ctx[key]


def shared_frontier(ctx: dict, subs: dict, ids: list[str]) -> pd.DataFrame:
    """The shared-frontier mirror chart + table data (`mirror_frontier`'s
    own INPUT FRAME CONTRACT, `lib/charts_compare.py`: `topic_id`,
    `topic_name`, `url_joint`, `vol_a`, `vol_b`, `vol_joint`, `expansion`,
    `acceleration`, `is_top_decile` are all present under these exact
    names). Topic set and `vol_a`/`vol_b` are IDENTICAL to the reference
    version's own `shared_frontier` (`_shared_frontier_topics`'s own
    docstring; anchor-tested against the reference figures).

    Per topic, ADDED:
      keywords, domain_id, frontier_score -- `topics_dim.parquet`
      is_top_decile -- global top-10% by frontier_score_latest
      vol_joint, joint_known -- `collab_topic_vols.parquet`'s
                                                   per-topic joint volume, `joint_known=False`
                                                   (`vol_joint=NaN`) when the pair is below
                                                   the qualifying floor (`core_total >= 5`)
                                                   -- the floor is
                                                   checked on the PAIR, not the topic: a
                                                   qualifying pair's genuinely-zero topic
                                                   still ships `vol_joint=0.0`, `joint_known=True`
      change_a, change_b, low_volume_a/b -- mean annual `vol_full` 2023-24 minus
                                                   2020-22 (an ABSOLUTE delta, not a percent
                                                   distinct from `cards`' own `vol_change`),
                                                   `low_volume_*` when the institution's own
                                                   2020-2024 volume on the topic is < 10 works
      rank_a, pool_a, rank_b, pool_b -- `leaders_data.topic_ranks`, fair pool per
                                                   institution `type`, NaN when the
                                                   institution is not in the topic's top 200
      stars_a, stars_b -- `leaders_data.stars_by_topic`, 0 when absent
      url_a, url_b, url_joint -- `links.topic_url`/`links.joint_topic_url`
    """
    from . import collab_data as COL  # local import -- collab_data imports THIS module (fields_long)

    assert len(ids) == 2, "shared_frontier is defined for exactly two institutions (Compare's own cap)"
    a, b = ids
    base = _shared_frontier_topics(ctx, subs, ids)
    if base.empty:
        return pd.DataFrame(columns=SHARED_FRONTIER_COLS)

    extra = P._topics_dim_extra(ctx)[["topic_id", "frontier_score_latest"]].set_index("topic_id")
    keywords = _topics_dim_keywords(ctx)
    domain_by_topic = ctx["topics_dim_df"].set_index("topic_id")["domain_id"]
    elite = _elite_frontier_topic_ids(ctx)

    joint_slice = COL._collab_pair_slice(ctx, "collab_topic_vols", a, b)
    pair_row = COL._load_collab_pairs(ctx, a, b)
    core_total = float(pair_row.iloc[0]["core_total"]) if len(pair_row) else 0.0
    joint_known = core_total >= PAIR_QUALIFYING_FLOOR
    vol_joint_by_topic = (joint_slice.set_index("topic_id")["vol"].astype("float64")
                          if joint_known and len(joint_slice) else pd.Series(dtype="float64"))

    yearly = _topic_yearly_own(ctx, a, b)
    ya = yearly[yearly["institution_id"] == a].set_index("topic_id")
    yb = yearly[yearly["institution_id"] == b].set_index("topic_id")
    w1_cols = [f"vol_full_{y}" for y in range(DYNAMICS_W1[0], DYNAMICS_W1[1] + 1)]
    w2_cols = [f"vol_full_{y}" for y in range(DYNAMICS_W2[0], DYNAMICS_W2[1] + 1)]

    def _own_change(y_df: pd.DataFrame, topic_id: str) -> tuple[float, bool]:
        if topic_id not in y_df.index:
            return float("nan"), True
        r = y_df.loc[topic_id]
        w1 = float(np.mean([r[c] for c in w1_cols]))
        w2 = float(np.mean([r[c] for c in w2_cols]))
        core_vol = float(sum(r[c] for c in w1_cols + w2_cols))
        return (w2 - w1), (core_vol < LOW_VOLUME_FLOOR)

    topic_ids = list(base["topic_id"])
    ranks = LD.topic_ranks(ctx, topic_ids, [a, b])
    type_a = str(ctx["index_by_id"].loc[a, "type"])
    type_b = str(ctx["index_by_id"].loc[b, "type"])
    pool_a = "education" if type_a == "education" else "all"
    pool_b = "education" if type_b == "education" else "all"
    ranks_a = ranks[(ranks["institution_id"] == a) & (ranks["pool"] == pool_a)].set_index("topic_id")["rank"]
    ranks_b = ranks[(ranks["institution_id"] == b) & (ranks["pool"] == pool_b)].set_index("topic_id")["rank"]

    stars = LD.stars_by_topic(ctx, [a, b])
    stars_a = stars[stars["institution_id"] == a].set_index("topic_id")["n_stars"]
    stars_b = stars[stars["institution_id"] == b].set_index("topic_id")["n_stars"]

    rows = []
    for _, r in base.iterrows():
        tid = r["topic_id"]
        ca, low_a = _own_change(ya, tid)
        cb, low_b = _own_change(yb, tid)
        rows.append({
            "topic_id": tid, "topic_name": r["name"],
            "keywords": keywords.get(tid), "domain_id": domain_by_topic.get(tid),
            "frontier_score": float(extra.loc[tid, "frontier_score_latest"]) if tid in extra.index else np.nan,
            "expansion": float(r["x"]), "acceleration": float(r["y"]),
            "is_top_decile": bool(tid in elite),
            "vol_a": float(r["vol_a"]), "vol_b": float(r["vol_b"]), "combined_vol": float(r["combined_vol"]),
            "vol_joint": float(vol_joint_by_topic.get(tid, 0.0)) if joint_known else np.nan,
            "joint_known": joint_known,
            "change_a": ca, "change_b": cb, "low_volume_a": low_a, "low_volume_b": low_b,
            "rank_a": (int(ranks_a[tid]) if tid in ranks_a.index else np.nan), "pool_a": pool_a,
            "rank_b": (int(ranks_b[tid]) if tid in ranks_b.index else np.nan), "pool_b": pool_b,
            "stars_a": int(stars_a.get(tid, 0)), "stars_b": int(stars_b.get(tid, 0)),
            "url_a": links.topic_url(a, tid), "url_b": links.topic_url(b, tid),
            "url_joint": links.joint_topic_url(a, b, tid),
        })
    return pd.DataFrame(rows, columns=SHARED_FRONTIER_COLS)


# ---------------------------------------------------------------------------
# relationship -- the Relationship block: momentum + yearly-by-domain +
# reciprocity + joint stars, all read from `collab_data`/`leaders_data`
# (both frozen fences), reshaped to what `charts_compare.
# yearly_domain_stack`/`reciprocity_bars` need.
# ---------------------------------------------------------------------------

RECIPROCITY_WIDE_COLS = ["field_id", "field_name", "domain_id", "vol_joint", "share_a", "share_b"]
YEARLY_DOMAIN_COLS = ["year", "domain_id", "domain_name", "vol"]


def relationship(ctx: dict, ids: list[str], subs: dict | None = None) -> dict:
    """The Relationship block for the pair `ids` (exactly two). `subs`
    defaults to the Compare pin (`load_substrates(ctx, "bestfit", "full")`)
    when not given -- only `reciprocity` needs a scenario at all (via
    `collab_data.reciprocity_frame` -> `fields_long`), so a caller that
    already holds the pinned `subs` (the normal, single-scenario-resident
    live app) should pass it rather than pay for a second load.

    Returns:
      momentum -- `collab_data.pair_momentum(ctx, a, b)` verbatim
                           (EQUAL golden `pair_momentum`), or `None` (never
                           co-published).
      pulse -- `collab_data.pulse(ctx, a, b)` verbatim (EQUAL
                           golden `pulse`) -- its own `yearly` (2020-2025,
                           ALL doc types) is the relationship section's
                           "plain yearly totals" fallback for a pair below
                           the qualifying floor, or `None`.
      yearly -- DataFrame(year, domain_id, domain_name, vol):
                           `collab_data.pair_domain_year` (CORE-AR 2020-2024,
                           qualifying pairs only) joined to domain names;
                           EMPTY when the pair does not qualify.
      yearly_qualifies -- False when `yearly` is empty (core_total < 5,
                           the qualifying floor) -- the page falls back to
                           `pulse["yearly"]` for a plain bar in that case.
      core_total -- `collab_pairs.core_total` (CORE-AR joint volume,
                           2020-2024), NaN when the pair never co-published.
      topicless_note -- True when Sigma(`yearly`.vol) < `core_total`: a
                           handful of the pair's joint CORE-AR works carry no
                           primary topic and are therefore absent from the
                           domain breakdown (this chart's own
                           caption states this in words, never silently).
      reciprocity -- WIDE (`charts_compare.reciprocity_bars`'s own
                           contract): field_id, field_name, domain_id,
                           vol_joint, share_a, share_b (`collab_data.
                           reciprocity_frame`'s `y`/`x` respectively
                           EQUAL golden `reciprocity_frame` once relabelled).
                           No `rank_in_a`/`rank_in_b` column: the reference
                           version's own `reciprocity_frame` never carried
                           a per-field partner rank (only a per-PAIR one,
                           on `momentum`),
                           so this optional pair of columns is omitted
                           rather than fabricated (`reciprocity_bars`'
                           own docstring: an absent column simply drops
                           that hover clause).
      joint_stars -- `leaders_data.pair_stars(ctx, a, b)`, int, 0
                           when absent.
      joint_stars_url -- `links.joint_stars_url(a, b)` (joint filter
                           + `sort=cited_by_count:desc`)."""
    from . import collab_data as COL  # local import -- collab_data imports THIS module (fields_long)

    assert len(ids) == 2, "relationship is defined for exactly two institutions (Compare's own cap)"
    a, b = ids
    if subs is None:
        subs = load_substrates(ctx, "bestfit", "full")

    momentum = COL.pair_momentum(ctx, a, b)
    pulse = COL.pulse(ctx, a, b)

    pair_row = COL._load_collab_pairs(ctx, a, b)
    core_total = float(pair_row.iloc[0]["core_total"]) if len(pair_row) else float("nan")

    py = COL.pair_domain_year(ctx, a, b)
    domain_names = dict(zip(ctx["topics_dim_df"]["domain_id"], ctx["topics_dim_df"]["domain_name"]))
    if len(py):
        yearly = py.copy()
        yearly["domain_name"] = yearly["domain_id"].map(domain_names)
        yearly = yearly[YEARLY_DOMAIN_COLS].sort_values(["year", "domain_id"]).reset_index(drop=True)
        yearly_qualifies = True
        topicless_note = bool(np.isfinite(core_total) and yearly["vol"].sum() < core_total)
    else:
        yearly = pd.DataFrame(columns=YEARLY_DOMAIN_COLS)
        yearly_qualifies = False
        topicless_note = False

    recip = COL.reciprocity_frame(ctx, subs, a, b)
    if len(recip):
        reciprocity = pd.DataFrame({
            "field_id": recip["field_id"], "field_name": recip["field_name"], "domain_id": recip["domain_id"],
            "vol_joint": recip["joint_vol"], "share_a": recip["y"], "share_b": recip["x"],
        }).reset_index(drop=True)
    else:
        reciprocity = pd.DataFrame(columns=RECIPROCITY_WIDE_COLS)

    return {
        "a": a, "b": b,
        "momentum": momentum,
        "pulse": pulse,
        "yearly": yearly, "yearly_qualifies": yearly_qualifies,
        "core_total": core_total, "topicless_note": topicless_note,
        "reciprocity": reciprocity.reindex(columns=RECIPROCITY_WIDE_COLS),
        "joint_stars": LD.pair_stars(ctx, a, b),
        "joint_stars_url": links.joint_stars_url(a, b),
    }
