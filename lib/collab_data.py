"""
app/lib/collab_data.py -- Collaborate-view data frames for exactly ONE pair
of institutions, A -> B directional.

Pure functions, no Streamlit import.

The "topics-together" table
(`joint_profile`, `collab_pair_topics.parquet`) and "Untapped potential"
(`untapped`, `shared_topics`, `collab_topic_vols.parquet`) sections are
DELETED from the app -- the Relationship block's new joint-publications-by-
domain-and-year chart (`pair_domain_year`, `collab_pair_domain_year.parquet`)
replaces them. Their builders are deleted from this module too (grep -rn for
untapped, shared_topics and joint_profile over app/lib app/pages app/Menu.py
showed zero importers outside this file before deletion, `views_collab.py`
already gone, `views_compare.py` imports nothing from `collab_data` yet).

This module's parquets
(`collab_pairs`, `collab_pair_fields`, `collab_pair_domain_year`) are NEVER
read whole into pandas here -- every consumer wants exactly one (a, b)
pair's rows, so `_collab_pair_slice` below runs a duckdb `WHERE a = ? AND
b = ?` pushdown query per table per pair (same in-process duckdb idiom as
`lib/engine/derive.py`/`lib/compare_data.py`/`lib/profile_data.py`:
`duckdb.connect`, a posix path inside `read_parquet('.')`, `.df`,
`con.close`) and caches the resulting SLICE (a handful to a few hundred
rows, never the multi-million-row whole table) on `ctx` under
`collab_slice:<table>:<lo>:<hi>` -- a rerun on the same pair pays
nothing. All tables are (a, b)-pair grain (a<b lexicographic, one row per
pair per extra key).

duckdb's `.df` decodes a parquet dictionary/category column to plain
VARCHAR (Python `str`), not pandas `category` -- `_collab_pair_slice` casts
the known category columns (`a`, `b`, `topic_id`, `mom_class`,
`erc_top_panel`) back to `category` on the returned slice so every
downstream comparison, `.map` and `groupby(observed=)` sees the exact
dtype a whole-table `pd.read_parquet` used to hand it.
"""
from __future__ import annotations

import json
import threading
from collections import OrderedDict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from . import compare_data as CD
from . import leaders_data as LD
from . import links
from . import palette as PAL
from . import profile_data as P

_COLLAB_CATEGORY_COLS = ("a", "b", "topic_id", "mom_class", "erc_top_panel")

# A concurrency fix, found via a stress test (phase B): three
# concurrent sessions browsing many distinct pairs each call this module's
# duckdb pushdowns, and the ctx-cached slice used to accumulate forever --
# one entry per (table, pair) ever requested, never evicted. `_DUCK_LOCK`
# guards both the lazy shared-connection creation below and the bounded-LRU
# bookkeeping in `_lru_touch` (same idiom, module-duplicated like `_posix`,
# in `lib/leaders_data.py`/`lib/compare_data.py`).
_DUCK_LOCK = threading.Lock()
_PAIR_CACHE_MAX = 32  # LRU cap per cache namespace -- a handful of open Compare tabs' worth of pairs


def _posix(path) -> str:
    """Windows backslashes inside a SQL string literal are ambiguous escape
    sequences -- duckdb's read_parquet takes forward-slash paths fine
    (same helper as `lib/engine/derive.py:_posix`)."""
    return Path(path).as_posix()


def _duck(ctx: dict):
    """Cursor onto the ONE process-wide, memory-bounded duckdb connection
    (`SET memory_limit='512MB'` + `SET threads TO 2`), created lazily on
    `ctx` under `_DUCK_LOCK` -- every per-pair pushdown in this module
    shares it instead of paying a fresh `duckdb.connect()`'s own buffer-pool
    overhead per call (three concurrent sessions hitting many distinct pairs
    used to open/close hundreds of separate connections, part of stress
    phase B's spike). `ctx` is the SAME object every page shares
    (`scenario_cache.bundle()["ctx"]`), so in production this really is one
    connection per process; a bare test ctx gets its own small one.
    `.cursor()` is duckdb's own documented pattern for one connection shared
    by many threads -- callers `.close()` the cursor they get back, never
    the parent connection."""
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
    the least-recently-used key in that namespace from `ctx` once more than
    `_PAIR_CACHE_MAX` are resident. Bounds every per-pair/per-args cache in
    this module to a small, fixed footprint no matter how many distinct
    pairs a run of sessions hops across -- the fix for the unbounded
    `ctx[key] = df` growth stress phase B exposed. One `OrderedDict` per
    namespace, itself stored on `ctx` so it travels with the same shared
    ctx object every caller uses."""
    with _DUCK_LOCK:
        order = ctx.setdefault(f"_lru::{prefix}", OrderedDict())
        order[key] = None
        order.move_to_end(key)
        while len(order) > _PAIR_CACHE_MAX:
            oldest, _ = order.popitem(last=False)
            ctx.pop(oldest, None)


def _collab_pair_slice(ctx: dict, table: str, a: str, b: str) -> pd.DataFrame:
    """The rows of `<table>.parquet` (one of the four Collaborate parquets)
    for the (a, b) pair, re-oriented to the table's own a<b convention and
    cached on `ctx` per (table, lo, hi), bounded to the `_PAIR_CACHE_MAX`
    most recently used pairs per table so a repeat call for a
    STILL-RESIDENT pair (any of this module's six public functions, in any
    order) never re-scans the parquet file, while a session that keeps
    hopping to new pairs never accumulates an unbounded number of slices.
    Returns an EMPTY frame (right columns, from the file's own schema) when
    the pair has no row in this table, exactly like the old
    `whole_df[(whole_df.a==lo)&(whole_df.b==hi)]` boolean mask did."""
    lo, hi = (a, b) if a < b else (b, a)
    key = f"collab_slice::{table}::{lo}::{hi}"
    if key not in ctx:
        path = _posix(Path(ctx["data_dir"]) / f"{table}.parquet")
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT * FROM read_parquet('{path}') WHERE a = ? AND b = ?", [lo, hi]
            ).df()
        finally:
            con.close()
        for c in _COLLAB_CATEGORY_COLS:
            if c in df.columns:
                df[c] = df[c].astype("category")
        ctx[key] = df
    _lru_touch(ctx, key, f"collab_slice::{table}")  # one LRU per TABLE (4 tables x 32 pairs, not 32 shared)
    return ctx[key]


# ============================================================================
# The Collaborate sections over ONE pair (a, b), from the `collab_pairs.
# parquet` / `collab_pair_fields.parquet` / `collab_pair_domain_year.parquet`
# pair files. Every table keys on (a, b) with `a` the LEXICOGRAPHICALLY
# SMALLER institution_id (the tables' OWN convention) -- every function below
# accepts (a, b) in the CALLER's own order and re-orients whatever it reads
# back, so a caller never has to know or care which of its two ids happens to
# sort first.
# ============================================================================

def _load_collab_pairs(ctx: dict, a: str, b: str) -> pd.DataFrame:
    """Reads `collab_pairs.parquet`'s row for this ONE
    pair only, duckdb-pushed and ctx-cached per pair by
    `_collab_pair_slice` -- never the 3.58M-row whole table. Columns:
    ALL a<b indexed-institution pairs with >=1 co-published work 2020-2025,
    `copubs_2020.copubs_2025` (all-types, pulse's own window, naming kept
    per WT_2BR3.md SS0 -- NOT a typo), `core_total`/`c1`/`c2` (CORE-AR,
    articles+reviews 2020-2024), `n_top10`/`n_covered`/`n_sdg`/`fwci_median`
    (CORE-AR), `rank_in_a`/`rank_in_b` (recomputed on CORE-AR, ranks computed
    before any floor), `mom_class`/`mom_rr`/`mom_p` (SS2.3, already
    classified), plus `erc_top_panel`/`erc_top_panel_n`/`erc_labelled_n`
    carried forward on their CURRENT basis (WT_2BR3.md SS0 gap g: moved here
    from collab_pair_topics v1, the pair-level ERC header now has a schema
    home)."""
    return _collab_pair_slice(ctx, "collab_pairs", a, b)


def pair_domain_year(ctx: dict, a: str, b: str) -> pd.DataFrame:
    """Reads `collab_pair_domain_year.parquet`'s rows
    for this ONE pair only, duckdb-pushed and ctx-cached like every table
    above -- never the whole file. Columns: (a, b, domain_id, year, vol),
    CORE-AR 2020-2024, qualifying pairs only (core_total >= 5, same floor
    as `collab_pairs`; the offline build's own rollup of
    the qualifying pair x field x year tables via `topics_dim`'s bestfit field ->
    domain map). Powers the Relationship block's joint-publications-by-
    domain stacked chart. Empty (right columns, from the file's own schema)
    when the pair never qualified -- Sigma(vol) over all rows for a
    qualifying pair equals that pair's `collab_pairs.core_total` exactly
    (verified per pair in `tests/test_collab_data.py` and the
    build step's own acceptance script)."""
    return _collab_pair_slice(ctx, "collab_pair_domain_year", a, b)


def _load_collab_facts(ctx: dict) -> dict:
    """Lazy, ctx-cached (`collab_facts.json` NEW, SS2.2): the momentum
    constants (med/w1/w2/band/alpha/elig_min/weak_base_max/new_min_c2/
    dormant_min_c1/basis) `momentum_display` may need for its message text."""
    if "collab_facts" not in ctx:
        with open(Path(ctx["data_dir"]) / "collab_facts.json") as f:
            ctx["collab_facts"] = json.load(f)
    return ctx["collab_facts"]


PULSE_YEARS = list(range(2020, 2026))  # collab_pairs' own window (2020-2025 incl. the 2025 bonus year)
PULSE_YEARLY_COLS = ["year", "copubs"]


def _num(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f


ARROW_UP, ARROW_DOWN, ARROW_FLAT = "up", "down", "flat"
ARROW_DEADBAND = 0.5
# -11(d): per-row direction arrows compare the MEAN ANNUAL volume of
# window 1 (2020-2022, /3) against window 2 (2023-2024, /2) -- never the raw
# window sums, which cover different numbers of years and are not
# comparable as-is. A change smaller than this deadband (half a joint
# publication per year) reads "flat" rather than flipping direction on
# noise -- the windows themselves are named in the caller's tooltip, not
# here (this module returns the arrow only, never composes the sentence).


def _arrow(vol_w1, vol_w2) -> str:
    w1_annual, w2_annual = _num(vol_w1) / 3.0, _num(vol_w2) / 2.0
    if not (np.isfinite(w1_annual) and np.isfinite(w2_annual)):
        return ARROW_FLAT
    delta = w2_annual - w1_annual
    if abs(delta) < ARROW_DEADBAND:
        return ARROW_FLAT
    return ARROW_UP if delta > 0 else ARROW_DOWN


def _taxon_url(a: str, b: str, level: str, taxon_id) -> str:
    # types default = links.CORE_AR_TYPES (articles+reviews), matching every
    # table count this module serves (plan §2.1; inspection I-2 fix).
    return links.copubs_taxon_url(a, b, level, taxon_id)


def pulse(ctx: dict, a: str, b: str) -> dict | None:
    """ S1 (Relationship pulse). Reads ONE row of `collab_pairs.
    parquet` (regardless of the table's own a<b ordering) and returns it in
    the CALLER's (a, b) orientation:

      yearly -- DataFrame[year, copubs], 2020-2025 (2025 labelled
                            the bonus year by the caller/page, same
                            convention as topics_all/doctype_by_year).
      copubs_total -- SUM over 2020-2025, full counting.
      share_of_a/b -- copubs_total / that side's own total FULL-counted
                            works over the SAME 2020-2025 window (index.
                            vol_full_by_year_this_run summed over all 6
                            years) -- NOT total_full_2020_2024's 5-year core
                            window; see `denominator_note`.
      rank_in_a -- dense rank (1=highest) of `b` among ALL of `a`'s
                            partners by copubs_total, computed BEFORE any
                            floor -- re-oriented from the table's
                            own rank_in_a/rank_in_b when the caller's (a, b)
                            is the table's (b, a).
      rank_in_b -- dense rank of `a` among ALL of `b`'s partners.

    Returns `None` when the pair has never co-published at all.
    Pinned anchor: `pulse(ctx, "I1294671590", "I68947357")` (CNRS, Strasbourg
    the table's own a<b order) -> copubs_total 12694, rank_in_a 16,
    rank_in_b 1 (verified against the underlying table)."""
    lo, hi = (a, b) if a < b else (b, a)
    row = _load_collab_pairs(ctx, a, b)  # already pushed down to this ONE pair
    if row.empty:
        return None
    row = row.iloc[0]
    swapped = a != lo  # caller's `a` is the table's `b`

    yearly = pd.DataFrame({"year": PULSE_YEARS, "copubs": [int(row[f"copubs_{y}"]) for y in PULSE_YEARS]},
                          columns=PULSE_YEARLY_COLS)
    rank_in_a = int(row["rank_in_b"] if swapped else row["rank_in_a"])
    rank_in_b = int(row["rank_in_a"] if swapped else row["rank_in_b"])

    idx = ctx["index_by_id"]
    denom_a = sum(P._parse_packed_years(idx.loc[a, "vol_full_by_year_this_run"]).get(y, 0.0) for y in PULSE_YEARS)
    denom_b = sum(P._parse_packed_years(idx.loc[b, "vol_full_by_year_this_run"]).get(y, 0.0) for y in PULSE_YEARS)
    total = int(row["copubs_total"])

    return {
        "a": a, "b": b, "yearly": yearly, "copubs_total": total,
        "share_of_a": (total / denom_a) if denom_a > 0 else np.nan,
        "share_of_b": (total / denom_b) if denom_b > 0 else np.nan,
        "denominator_a": denom_a, "denominator_b": denom_b,
        "denominator_note": ("Each side's share of co-publications is out of its OWN total full-counted "
                             "publications, 2020-2025 (the same 6-year window as the co-publication count "
                             "itself) -- not the shorter 2020-2024 window used for some other Compare figures."),
        "rank_in_a": rank_in_a, "rank_in_b": rank_in_b,
    }


PAIR_TOPICS_FLOOR = 5    # -12: collab_pair_topics/collab_pair_fields ship only for pairs with copubs_total >= this

FIELD_BREAKDOWN_COLS = ["field_id", "field_name", "domain_id", "domain_name", "vol_w1", "vol_w2",
                        "vol", "n_covered", "n_top10", "n_sdg", "fwci_median", "fwci_mean", "n_fwci",
                        "mom_class", "arrow", "url"]
FIELD_BREAKDOWN_NOTE = (
    "Field mix uses the repaired (best-fit) taxonomy only and does not change with the tree toggle."
)


def _load_collab_pair_fields(ctx: dict, a: str, b: str) -> pd.DataFrame:
    """Reads `collab_pair_fields.parquet`'s rows for this
    ONE pair only, duckdb-pushed and ctx-cached -- never the 3.57M-row whole
    table. Pair x field, UNCAPPED (every field the pair has any joint mass
    in), bestfit tree only, same a<b/floor-5 qualifying-pair convention as
    `collab_pair_topics`. The ONE source `field_breakdown` reads -- the
    AUTHORITATIVE, uncapped per-field total. `mean_citations` is GONE
    (SS2.2: "DROPPED, superseded by FWCI") -- `fwci_median` is the only
    per-field impact figure now."""
    return _collab_pair_slice(ctx, "collab_pair_fields", a, b)


def field_breakdown(ctx: dict, a: str, b: str) -> pd.DataFrame:
    """The field breakdown of the joint corpus -- one row per field the pair
    has any joint CORE-AR mass in, from `collab_pair_fields.parquet`
    (UNCAPPED, bestfit-tree-only -- `.attrs['note']` carries that caveat for
    the caller's caption, and `.attrs['floor']` the qualifying-pair floor).
    Sorted by `vol` (CORE-AR) descending; empty (with the right columns) when
    the pair never co-published or falls below `PAIR_TOPICS_FLOOR`. Each row
    carries `fwci_median`/`mom_class`, an `arrow` (`_arrow`) and a live
    OpenAlex `url` restricted to this field. The DATA function survives
    unchanged in shape (only its column contract moves) -- only the TABLE
    RENDERER that used to sit on top of it is retired (WT_2BR3.md SS0
    ratification, CD4 acceptance: 'field_breakdown the DATA function
    SURVIVES. only VL's table renderer dies')."""
    rows = _load_collab_pair_fields(ctx, a, b)  # already pushed down to this ONE pair
    name_map = P._field_domain_map(ctx)[["field_id", "field_name", "domain_id", "domain_name"]]
    out = rows.merge(name_map, on="field_id", how="left")
    if len(out):
        out["arrow"] = [_arrow(w1, w2) for w1, w2 in zip(out["vol_w1"], out["vol_w2"])]
        out["url"] = [_taxon_url(a, b, "field", int(fid)) for fid in out["field_id"]]
    else:
        out["arrow"], out["url"] = pd.Series(dtype=object), pd.Series(dtype=object)
    out = out.sort_values("vol", ascending=False).reset_index(drop=True).reindex(columns=FIELD_BREAKDOWN_COLS)
    out.attrs["note"] = FIELD_BREAKDOWN_NOTE
    out.attrs["floor"] = PAIR_TOPICS_FLOOR
    return out


# ============================================================================
#  CD4 items 5/6 ( SS2.3 momentum, SS1.6 reciprocity)
# ============================================================================

# Merged: palette.py is the ONE source of momentum
# hexes/glyphs; this module keeps only its ladder's "neutral" bucket alias
# (ns/new/dormant/weak all share palette's ns entry).
MOMENTUM_COLORS = {"up": PAL.MOMENTUM_COLORS["up"], "down": PAL.MOMENTUM_COLORS["down"],
                   "stable": PAL.MOMENTUM_COLORS["stable"], "neutral": PAL.MOMENTUM_COLORS["ns"]}
MOMENTUM_GLYPH = {"up": PAL.MOMENTUM_GLYPHS["up"], "down": PAL.MOMENTUM_GLYPHS["down"],
                  "stable": PAL.MOMENTUM_GLYPHS["stable"], "neutral": PAL.MOMENTUM_GLYPHS["ns"]}
MOMENTUM_CLAMP_PCT = 999.0  # SS2.3: delta_pct display-clamped at "> +999 %" (one-sided -- rr>=0 bounds delta at -100%)
MOMENTUM_NULL_TEXT = "—"


def _mom_num(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f


def momentum_display(mom_class, mom_rr, mom_p, c1, c2, facts: dict) -> tuple[str, str, str]:
    """SS2.3's 9-case momentum display ladder -- a PURE formatting
    function over an ALREADY-CLASSIFIED pair/field/topic row (`mom_class`/
    `mom_rr`/`mom_p` are upstream outputs from `collab_pairs`/
    `collab_pair_fields`/`collab_pair_topics`; this function never
    reclassifies, and `c1`/`c2`/`facts` are accepted for signature parity
    with future message-text branches but are not needed by
    today's 9 cases -- classification already happened upstream). Returns
    `(text, hex_colour, glyph)`; colour is NEVER the only signal -- text and
    glyph always accompany it (a mandatory rule, the sharpest finding from
    a hostile-verifier pass).

    The 9 cases: null/unclassified -> '—' neutral; 'weak' (0<c1<5, no
    %) -> 'weak base'; 'new' -> 'new'; 'dormant' -> 'dormant'; 'ns' (demoted
    by the two-proportion z-test) -> 'n.s.'; 'up' normal -> signed no-decimal
    '+NN%'; 'up' beyond the clamp -> '> +999%'; 'down' -> signed no-decimal
    '-NN%'; 'stable' -> signed no-decimal '+NN%' (a real number inside the
    +-25% band, unlike the four label-only neutral states above)."""
    if mom_class is None or (isinstance(mom_class, float) and np.isnan(mom_class)):
        return MOMENTUM_NULL_TEXT, MOMENTUM_COLORS["neutral"], MOMENTUM_GLYPH["neutral"]
    mc = str(mom_class)
    if mc == "weak":
        return "weak base", MOMENTUM_COLORS["neutral"], MOMENTUM_GLYPH["neutral"]
    if mc == "new":
        return "new", MOMENTUM_COLORS["neutral"], MOMENTUM_GLYPH["neutral"]
    if mc == "dormant":
        return "dormant", MOMENTUM_COLORS["neutral"], MOMENTUM_GLYPH["neutral"]
    if mc == "ns":
        return "n.s.", MOMENTUM_COLORS["neutral"], MOMENTUM_GLYPH["neutral"]
    if mc not in ("up", "down", "stable"):
        raise AssertionError(f"unknown mom_class {mom_class!r}")
    rr = _mom_num(mom_rr)
    if not np.isfinite(rr):
        return MOMENTUM_NULL_TEXT, MOMENTUM_COLORS["neutral"], MOMENTUM_GLYPH["neutral"]
    delta_pct = (rr - 1.0) * 100.0
    if mc == "up" and delta_pct > MOMENTUM_CLAMP_PCT:
        return "> +999%", MOMENTUM_COLORS["up"], MOMENTUM_GLYPH["up"]
    return f"{delta_pct:+.0f}%", MOMENTUM_COLORS[mc], MOMENTUM_GLYPH[mc]


def pair_momentum(ctx: dict, a: str, b: str) -> dict | None:
    """Pair-header momentum verdict (SS2.3): reads `collab_pairs.parquet`'s
    own `mom_class`/`mom_rr`/`mom_p`/`c1`/`c2` (already classified
    upstream -- ONE drift correction per run, per SS2.3) plus each side's own
    CORE-AR window totals (`index.total_ar_full_w1/w2`, SS2.2) for the
    evidence block's d1/d2, re-oriented to the CALLER's (a, b) like every
    other pair-table read in this module. Returns `None` when the pair has
    no `collab_pairs` row at all (never co-published)."""
    row = _load_collab_pairs(ctx, a, b)  # already pushed down to this ONE pair
    if row.empty:
        return None
    row = row.iloc[0]
    idx = ctx["index_by_id"]
    d1 = float(idx.loc[a, "total_ar_full_w1"]) + float(idx.loc[b, "total_ar_full_w1"])
    d2 = float(idx.loc[a, "total_ar_full_w2"]) + float(idx.loc[b, "total_ar_full_w2"])
    c1, c2 = float(row["c1"]), float(row["c2"])
    facts = _load_collab_facts(ctx)
    text, color, glyph = momentum_display(row.get("mom_class"), row.get("mom_rr"), row.get("mom_p"), c1, c2, facts)
    return {
        "a": a, "b": b, "mom_class": row.get("mom_class"), "mom_rr": _mom_num(row.get("mom_rr")),
        "mom_p": _mom_num(row.get("mom_p")), "c1": c1, "c2": c2, "d1": d1, "d2": d2,
        "text": text, "color": color, "glyph": glyph,
    }


MOMENTUM_EVIDENCE_STATES = ("numeric", "new", "dormant", "thin")
MOMENTUM_EVIDENCE_SIG_STATES = ("significant", "not_significant", "no_test")


def momentum_evidence(mom: dict, facts: dict) -> dict:
    """The Relationship section's always-visible momentum EVIDENCE LINE (
    `compare_momentum_line`) -- a PURE classification over the pair's own
    RAW figures (`mom["c1"]`/`c2`/`mom_rr`/`mom_p`), never over `mom_class`.
    `facts` is `collab_facts.json` verbatim (`_load_collab_facts`'s own
    return) -- every threshold below is READ from it, never a typed digit,
    per the house rule this function's own review asked for: `band` (the
    +-25% recentred-ratio width, `stable`'s own definition), `alpha` (the
    significance level), `new_min_c2`/`dormant_min_c1`/`weak_base_max` (the
    SAME three ints the upstream classifier itself uses for new/dormant/weak
    -- reused here so this function can never silently drift from
    `mom_class`'s own ladder even though it never reads that column).

    Six states, in this priority:
      1. c1==0 and c2 >= new_min_c2      -> "new" (a genuine emergence)
      2. c1==0 and 0 < c2 < new_min_c2   -> "thin_ns" (an 'ns' row with
                                            NEITHER mom_rr nor mom_p at all --
                                            too little in EITHER window for
                                            any rate, let alone a test)
      3. 0 < c1 < weak_base_max + 1      -> "thin" ("weak": a real base-
                                            window count, still too small
                                            for a rate)
      4. c2==0 (c1 already >= the floor) -> "dormant"
      5. mom_rr within the stable band   -> "numeric", sig="stable_band"
      6. otherwise (a real up/down       -> "numeric", sig="significant" |
         direction, in or out of the        "not_significant" | "no_test"
         upstream table's own "ns")         (the last only if mom_p itself
                                             is somehow absent -- unreached
                                             in the live data: every row
                                             outside the stable band always
                                             carries a p-value)

    Live-verified on the shipped `app/data/collab_pairs.parquet`: of
    1,450,358 'ns' rows, 316,171 carry BOTH mom_rr and mom_p (the demoted
    up/down candidates -- state 6 above, "not_significant" by construction,
    since a row that had cleared alpha would never have been demoted to
    'ns' in the first place); the remaining 1,134,187 carry NEITHER (state
    1 or 2 above, split on `new_min_c2`). 'stable'/'weak'/'dormant' rows
    ALWAYS carry mom_rr but NEVER mom_p (no z-test is ever run for them
    upstream) -- 'dormant'/'weak' need no test to begin with (states 3/4),
    and 'stable' reads its own fixed sentence (state 5) rather than
    "too little... for a test", which would be a category error for a row
    that HAS a real, defined rate.

    Returns exactly one of:
      {"state": "new", "c2_mean": int}
      {"state": "thin_ns"}
      {"state": "thin"}
      {"state": "dormant", "c1_mean": int}
      {"state": "numeric", "c1_mean": int, "c2_mean": int, "pct": str,
       "sig": "stable_band" | "significant" | "not_significant" | "no_test",
       "p": float, "band_pct": str}

    `c1_mean`/`c2_mean` are ROUNDED to whole works (the house convention for
    this figure -- `charts._fmt_vol` already prints a whole int with the
    thousands separator and no decimal once given one). `pct` is the signed,
    space-before-percent, true-minus-sign text (`_delta_pct_text`) -- the
    SAME formula `momentum_display`'s up/down/stable branches compute
    (kept as its own small copy there, per that function's own "unchanged
    ladder" contract), just reached here without going through `mom_class`
    at all. `band_pct` (only on the "stable_band" sig) is `facts["band"]`
    as a bare NUMBER string (e.g. "25", no percent sign -- the template
    itself supplies " %", matching `pct`'s own space-before-percent
    convention), for the evidence line's own "+-{band_pct} %" clause. Never
    raises: a floor-cleared row with a
    somehow-non-finite ratio (should not occur; defensive only) degrades to
    "thin_ns" rather than printing a NaN percentage."""
    c1, c2 = _mom_num(mom.get("c1")), _mom_num(mom.get("c2"))
    n1 = CD.DYNAMICS_W1[1] - CD.DYNAMICS_W1[0] + 1
    n2 = CD.DYNAMICS_W2[1] - CD.DYNAMICS_W2[0] + 1
    new_min_c2 = facts["new_min_c2"]
    dormant_min_c1 = facts["dormant_min_c1"]
    weak_base_max = facts["weak_base_max"]
    band = facts["band"]
    alpha = facts.get("alpha")

    if c1 == 0:
        if c2 >= new_min_c2:
            return {"state": "new", "c2_mean": round(c2 / n2)}
        return {"state": "thin_ns"}
    if c1 <= weak_base_max:
        # matches the upstream ladder's OWN "weak" condition exactly
        # (0 < c1 <= weak_base_max) -- checked BEFORE dormant, since
        # "dormant" upstream is itself defined as c2==0 AND c1 >=
        # dormant_min_c1, never a thin-base row that merely went quiet too.
        return {"state": "thin"}
    if c2 == 0:
        return {"state": "dormant", "c1_mean": round(c1 / n1)}
    rr = _mom_num(mom.get("mom_rr"))
    if not np.isfinite(rr):
        return {"state": "thin_ns"}
    c1_mean, c2_mean = round(c1 / n1), round(c2 / n2)
    pct = _delta_pct_text(rr)
    lo, hi = 1.0 / (1.0 + band), 1.0 + band
    if lo < rr < hi:
        return {"state": "numeric", "c1_mean": c1_mean, "c2_mean": c2_mean,
                "pct": pct, "sig": "stable_band", "p": float("nan"),
                "band_pct": f"{band * 100:.0f}"}
    p = _mom_num(mom.get("mom_p"))
    if np.isfinite(p) and alpha is not None:
        sig = "significant" if p <= alpha else "not_significant"
    else:
        sig = "no_test"
    return {"state": "numeric", "c1_mean": c1_mean, "c2_mean": c2_mean,
            "pct": pct, "sig": sig, "p": p}


def _delta_pct_text(rr: float) -> str:
    """Signed, no-decimal, SPACE-before-percent '{+/MINUS}NN %' from a
    recentred ratio, clamped at `MOMENTUM_CLAMP_PCT` -- kept as its OWN small
    formula (not factored out of `momentum_display`, whose own up-only
    clamp condition and "+NN%" tile-facing text stay untouched per its
    "unchanged ladder" contract) so `momentum_evidence` never risks
    perturbing that function's existing, tested output.

    A TRUE minus sign (U+2212), never a hyphen-minus, on a negative value --
    the evidence SENTENCE sits a signed number directly after a colon
    ("2023-2024: {pct} once.."), where a hyphen-minus would print as a
    second dash immediately before the sign; the tile's own bare glyph
    ("-> -3%", `momentum_display`) has no such neighbour and is unaffected."""
    delta_pct = (rr - 1.0) * 100.0
    if delta_pct > MOMENTUM_CLAMP_PCT:
        return "> +999 %"
    sign = "\N{MINUS SIGN}" if delta_pct < 0 else "+"
    return f"{sign}{abs(delta_pct):.0f} %"


RECIPROCITY_COLS = ["field_id", "field_name", "domain_id", "domain_name", "x", "y", "joint_vol",
                    "fwci_mean", "fwci_median", "n_fwci", "n_top10", "n_covered",
                    "n_stars_field", "rank_in_a", "rank_in_b"]


def reciprocity_frame(ctx: dict, subs: dict, a: str, b: str) -> pd.DataFrame:
    """"Strategic reciprocity by field" (SS1.6, ported from an earlier SIRIS
    Streamlit tool, HONEST both-sides variant -- that tool's own
    x-axis builder divides pair co-works by the PARTNER's total, which is in
    tension with its own copy; BenchUp implements the version that matches
    what the chart actually claims to show): per field with joint CORE-AR
    volume > 0, `x` = that field's share of B's OWN corpus, `y` = that
    field's share of A's OWN corpus (both `fields.parquet`, current tree/
    basis-aware via `subs` -- `compare_data.fields_long`, never recomputed
    here), `joint_vol` = the pair's CORE-AR joint volume in that field
    (`field_breakdown`'s own `vol`, the authoritative uncapped source, never
    the topic-rollup lower bound). `x`/`y`/`joint_vol` are UNCHANGED by the
    the scatter-return (byte-identical formula, still the bubble's position
    and area) -- everything below is a NEW per-field addition:

      fwci_mean, fwci_median, n_fwci -- `collab_pair_fields.parquet`'s own
                       per-field FWCI of the pair's JOINT works (n_fwci is
                       the FWCI population's own count, a slightly WIDER set
                       than n_covered -- both genuine, both surfaced so a
                       reader never confuses the two denominators, per the
                       upstream reconciliation note on that column).
      n_top10, n_covered -- the same table's joint top-decile count and its
                       OWN (narrower) covered-works denominator; PP10_WD for
                       the field is `n_top10 / n_covered`, computed by the
                       caller at render time, never stored here as a ratio.
      n_stars_field -- `leaders_data.pair_stars_by_field`, 0 when absent.
      rank_in_a, rank_in_b -- the PAIR's own partner rank (`collab_pairs.
                       rank_in_a`/`rank_in_b`, re-oriented to the caller's
                       (a, b) exactly like `pulse`'s own reorientation),
                       repeated on every field row -- a pair-level fact, not
                       a per-field one; NaN when the pair has no
                       `collab_pairs` row (never co-published).

    One row per qualifying field; SYMMETRIC by construction -- swapping
    (a, b) swaps (x, y) and leaves `joint_vol`/the field-level additions
    unchanged (`field_breakdown` is itself a<b-orientation-invariant; the
    pair-level rank_in_a/rank_in_b swap with (a, b), matching `pulse`)."""
    fb = field_breakdown(ctx, a, b)
    fb = fb[fb["vol"] > 0]
    if fb.empty:
        return pd.DataFrame(columns=RECIPROCITY_COLS)
    fl = CD.fields_long(ctx, subs, [a, b])
    a_share = fl[fl["institution_id"] == a].set_index("field_id")["share"]
    b_share = fl[fl["institution_id"] == b].set_index("field_id")["share"]
    out = fb[["field_id", "field_name", "domain_id", "domain_name", "vol",
             "fwci_mean", "fwci_median", "n_fwci", "n_top10", "n_covered"]].rename(columns={"vol": "joint_vol"})
    out["x"] = out["field_id"].map(b_share).fillna(0.0)  # field's share of B's OWN corpus
    out["y"] = out["field_id"].map(a_share).fillna(0.0)  # field's share of A's OWN corpus

    stars_by_field = LD.pair_stars_by_field(ctx, a, b)
    out["n_stars_field"] = out["field_id"].map(stars_by_field).fillna(0).astype(int)

    lo, hi = (a, b) if a < b else (b, a)
    pair_row = _load_collab_pairs(ctx, a, b)
    if len(pair_row):
        swapped = a != lo  # caller's `a` is the table's `b` -- reorient like `pulse`
        r = pair_row.iloc[0]
        out["rank_in_a"] = float(r["rank_in_b"]) if swapped else float(r["rank_in_a"])
        out["rank_in_b"] = float(r["rank_in_a"]) if swapped else float(r["rank_in_b"])
    else:
        out["rank_in_a"] = np.nan
        out["rank_in_b"] = np.nan

    return out.reindex(columns=RECIPROCITY_COLS).sort_values("joint_vol", ascending=False).reset_index(drop=True)
