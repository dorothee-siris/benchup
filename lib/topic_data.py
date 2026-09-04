"""
app/lib/topic_data.py -- per-institution topic-grain frame for the topic
planes (Find's "Topics: volume, impact and frontier" expander) and, later,
Compare's topic overlap.

`institution_topics(ctx, iid, tree)` is the ONE row-per-topic frame both
planes draw from: `inst_topic_impact.parquet` (articles+reviews 2020-2024,
full attribution, PRIMARY topic -- floored at n_ar>=3 by construction) joined
with the topic dimension (name, keywords, domain/field/subfield resolved
through the active tree, exclusion and frontier-score facts), the
institution's own star-paper and world-rank facts, its whole-run volumes on
both counting bases, and its own topic-level volume change between the two
windows. `select_topics` cuts that frame down to what one of the five
"Topics shown" modes actually draws, and `topic_set_caption` returns the
plain facts a caption composes into a sentence.

Perimeter (fixed, independent of Find's basis toggle): articles and
reviews, 2020-2024, full counting, primary topic. The two planes and the
"top by volume" selector all read this SAME perimeter; whole-run volumes on
both bases still ride along as a hover fact, never as the axis or the sort.

Data access follows the established per-institution idioms already shipped
in this package: a bounded duckdb pushdown (the SAME shared-connection +
LRU idiom `lib/leaders_data.py` and `lib/collab_data.py` already use,
module-duplicated here on purpose -- see `leaders_data.py`'s own docstring
for why one connection object is still shared: every copy keys the SAME
`ctx["_duck_con"]` slot) for the two per-institution reads
(`inst_topic_impact.parquet`, `topics_all.parquet`'s per-year columns), and
a plain frame cached once on `ctx` (the same idiom `profile_data.
_topics_dim_extra` already uses) for the topic dimension and the
institution-independent emergence threshold. Nothing here calls
`pd.read_parquet` on a per-call path -- every read is either a bounded,
parameterised pushdown or a load-once-per-ctx cache.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from lib import leaders_data as LD
from lib.profile_data import _subfield_field_domain_map

# Matches `lib/data_cache.py`'s own DATA_DIR construction exactly (both
# modules live in app/lib/) -- used ONLY by `emergence_threshold()` below,
# which is institution- and ctx-independent by definition (a topic's own
# frontier score never varies by institution or scenario) and therefore
# reads the one standing deployment rather than whatever `data_dir` a
# particular test ctx happens to point at.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# Shared-connection + bounded-LRU idiom, module-duplicated (see the module
# docstring above and `lib/leaders_data.py`'s own docstring for why this is
# duplicated rather than imported: each copy keys the SAME ctx slots, so the
# process still holds exactly one duckdb connection and one bounded LRU per
# cache namespace).
# ---------------------------------------------------------------------------
_DUCK_LOCK = threading.Lock()
_PAIR_CACHE_MAX = 32


def _posix(path) -> str:
    return Path(path).as_posix()


def _data_dir(ctx: dict) -> Path:
    return Path(ctx["data_dir"])


def _duck(ctx: dict):
    with _DUCK_LOCK:
        con = ctx.get("_duck_con")
        if con is None:
            con = duckdb.connect()
            con.execute("SET memory_limit='512MB'")
            con.execute("SET threads TO 2")
            ctx["_duck_con"] = con
    return con.cursor()


def _lru_touch(ctx: dict, key: str, prefix: str) -> None:
    with _DUCK_LOCK:
        order = ctx.setdefault(f"_lru::{prefix}", OrderedDict())
        order[key] = None
        order.move_to_end(key)
        while len(order) > _PAIR_CACHE_MAX:
            oldest, _ = order.popitem(last=False)
            ctx.pop(oldest, None)


# ---------------------------------------------------------------------------
# inst_topic_impact.parquet -- one institution's slice
# ---------------------------------------------------------------------------
_IMPACT_COLS = ("topic_id", "n_ar", "n_covered", "fwci_mean", "fwci_median",
                "n_pp", "n_top10_wd")


def _inst_topic_impact_slice(ctx: dict, iid: str) -> pd.DataFrame:
    """`inst_topic_impact.parquet` rows for ONE institution (n_ar>=3 by
    construction -- the file ships pre-floored). `topic_id` comes back as
    plain str (duckdb decodes the file's category column to VARCHAR)."""
    key = f"topic_data::inst_topic_impact::{iid}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "inst_topic_impact.parquet")
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT {', '.join(_IMPACT_COLS)} FROM read_parquet('{path}') "
                f"WHERE institution_id = ?",
                [iid],
            ).df()
        finally:
            con.close()
        df["topic_id"] = df["topic_id"].astype(str)
        ctx[key] = df.reset_index(drop=True)
    _lru_touch(ctx, key, "topic_data_inst_topic_impact")
    return ctx[key]


# ---------------------------------------------------------------------------
# topics_all.parquet -- one institution's own per-year vol_full, reduced to
# the two-window change (change_w1_w2 / low_base). A separate, small pushdown
# from the whole-run totals below (those come off ctx's already-resident
# arrays, no file read at all).
# ---------------------------------------------------------------------------
CHANGE_W1_YEARS = (2020, 2021, 2022)
CHANGE_W2_YEARS = (2023, 2024)
LOW_BASE_FLOOR = 10.0   # w1 TOTAL (not mean) under this -> low_base (dagger)


def _topic_yearly_change_df(ctx: dict, iid: str) -> pd.DataFrame:
    """(topic_id, change_w1_w2, low_base) for one institution: OWN volume
    change, mean annual `vol_full` over 2023-2024 against 2020-2022, from
    `topics_all.parquet`'s per-year columns -- NaN when the w1 mean is 0
    (never a division by zero), `low_base` when the w1 TOTAL (three years
    summed, not the mean) is under `LOW_BASE_FLOOR` works."""
    key = f"topic_data::yearly_change::{iid}"
    if key not in ctx:
        inst_key = int(ctx["index_by_id"].loc[iid, "inst_key"])
        path = _posix(Path(ctx["topics_all_path"]))
        w1_sum = " + ".join(f"vol_full_{y}" for y in CHANGE_W1_YEARS)
        w2_sum = " + ".join(f"vol_full_{y}" for y in CHANGE_W2_YEARS)
        con = _duck(ctx)
        try:
            df = con.execute(
                f"""
                SELECT topic_id, ({w1_sum}) AS w1_total, ({w2_sum}) AS w2_total
                FROM read_parquet('{path}')
                WHERE inst_key = ?
                """,
                [inst_key],
            ).df()
        finally:
            con.close()
        w1_total = pd.to_numeric(df["w1_total"], errors="coerce").astype("float64")
        w2_total = pd.to_numeric(df["w2_total"], errors="coerce").astype("float64")
        w1_mean = w1_total / float(len(CHANGE_W1_YEARS))
        w2_mean = w2_total / float(len(CHANGE_W2_YEARS))
        with np.errstate(invalid="ignore", divide="ignore"):
            change = np.where(w1_mean > 0, w2_mean / w1_mean - 1.0, np.nan)
        out = pd.DataFrame({
            "topic_id": df["topic_id"].astype(str),
            "change_w1_w2": change,
            "low_base": (w1_total < LOW_BASE_FLOOR).to_numpy(),
        })
        ctx[key] = out
    _lru_touch(ctx, key, "topic_data_yearly_change")
    return ctx[key]


# ---------------------------------------------------------------------------
# topic_leaders.parquet -- rank-1 display_name for a LIST of topics, one
# batched query. `leaders_data.topic_leader_name` only takes one topic at a
# time (its own bounded LRU caps at 32 resident keys); calling it once per
# topic across an institution's whole topic set (hundreds to low thousands
# for a large multi-site organisation) would be that many separate queries.
# This mirrors `leaders_data.topic_rank`'s own IN-list batching instead, over
# the SAME file, without editing that module.
# ---------------------------------------------------------------------------

def _leader_names_for_topics(ctx: dict, topic_ids) -> dict:
    topic_key = tuple(sorted(set(topic_ids)))
    if not topic_key:
        return {}
    key = f"topic_data::leader_names::{topic_key}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "topic_leaders.parquet")
        t_ph = ",".join(["?"] * len(topic_key))
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT topic_id, institution_id, display_name FROM read_parquet('{path}') "
                f"WHERE rank = 1 AND topic_id IN ({t_ph})",
                list(topic_key),
            ).df()
        finally:
            con.close()
        names = {}
        for t, rank1_iid, name in zip(df["topic_id"], df["institution_id"], df["display_name"]):
            names[str(t)] = str(name) if pd.notna(name) else str(rank1_iid)
        ctx[key] = {t: names.get(t) for t in topic_key}
    _lru_touch(ctx, key, "topic_data_leader_names")
    return ctx[key]


# ---------------------------------------------------------------------------
# topics_dim.parquet -- the full 29-column frame, cached once per ctx
# (`profile_data._topics_dim_extra` reads only 5 columns for a different
# purpose; this is a separate, wider cache under its own key).
# ---------------------------------------------------------------------------
_DIM_COLS = ("topic_id", "topic_name", "keywords", "is_excluded",
            "exclusion_reason_label", "expansion_latest", "acceleration_latest",
            "frontier_score_latest", "quadrant", "top25pct_frontier",
            "is_frontier_scored", "original_subfield_id",
            "conservative_subfield_id", "bestfit_subfield_id")


def _topics_dim_full(ctx: dict) -> pd.DataFrame:
    if "topic_data_dim_df" not in ctx:
        df = pd.read_parquet(_data_dir(ctx) / "topics_dim.parquet", columns=list(_DIM_COLS))
        df["topic_id"] = df["topic_id"].astype(str)
        ctx["topic_data_dim_df"] = df
    return ctx["topic_data_dim_df"]


def _topic_dimension(ctx: dict, tree: str) -> pd.DataFrame:
    """The topic dimension resolved through ONE tree: topic_id, topic_name,
    keywords, is_excluded, exclusion_reason_label, expansion_latest,
    acceleration_latest, frontier_score_latest, quadrant, top25pct_frontier,
    is_frontier_scored, domain_id, domain_name, field_name, subfield_name --
    subfield/field/domain resolved via `{tree}_subfield_id` through the
    FIXED (tree-independent) subfield->field->domain map, the SAME idiom
    `profile_data.topics_table` already uses."""
    tree_col = f"{tree}_subfield_id"
    dim = _topics_dim_full(ctx)
    slim = dim.drop(columns=[c for c in ("original_subfield_id", "conservative_subfield_id",
                                         "bestfit_subfield_id") if c != tree_col])
    slim = slim.rename(columns={tree_col: "subfield_id"})
    sfd = _subfield_field_domain_map(ctx)[
        ["subfield_id", "subfield_name", "field_id", "field_name", "domain_id", "domain_name"]]
    out = slim.merge(sfd, on="subfield_id", how="left")
    return out.drop(columns=["subfield_id", "field_id"])


# ---------------------------------------------------------------------------
# institution_topics -- the one row-per-topic frame both planes draw from
# ---------------------------------------------------------------------------
TOPIC_COLS = [
    "topic_id", "topic_name", "keywords", "domain_id", "domain_name",
    "field_name", "subfield_name", "is_excluded", "exclusion_reason_label",
    "expansion_latest", "acceleration_latest", "frontier_score_latest",
    "quadrant", "top25pct_frontier", "is_frontier_scored",
    "n_ar", "n_covered", "fwci_mean", "fwci_median", "n_pp", "n_top10_wd",
    "pp10_wd", "n_stars", "world_rank", "is_led", "leader_name",
    "vol_full_run", "vol_frac_run", "change_w1_w2", "low_base",
]

WORLD_LEADERBOARD_RANK_FLOOR = 20   # a topic is "led" at or above this rank


def institution_topics(ctx: dict, iid: str, tree: str) -> pd.DataFrame:
    """One row per topic of `inst_topic_impact.parquet` for `iid` (n_ar>=3
    by construction), with every column the two topic planes and their
    workbook sheet need -- see `TOPIC_COLS` for the exact order. Empty
    (right columns) when the institution has no topic clearing the floor."""
    impact = _inst_topic_impact_slice(ctx, iid)
    if impact.empty:
        return pd.DataFrame(columns=TOPIC_COLS)
    topic_ids = impact["topic_id"].tolist()

    dim = _topic_dimension(ctx, tree)
    out = impact.merge(dim, on="topic_id", how="left")

    n_pp = out["n_pp"].to_numpy(dtype="float64")
    n_top10 = out["n_top10_wd"].to_numpy(dtype="float64")
    with np.errstate(invalid="ignore", divide="ignore"):
        out["pp10_wd"] = np.where(n_pp > 0, n_top10 / n_pp, np.nan)

    stars_map = LD.stars_for_topics(ctx, iid, topic_ids)
    out["n_stars"] = out["topic_id"].map(stars_map).fillna(0).astype(int)

    rank_map = LD.topic_rank(ctx, iid, topic_ids)
    out["world_rank"] = pd.array([rank_map.get(t) for t in out["topic_id"]], dtype="Int64")
    out["is_led"] = (out["world_rank"] <= WORLD_LEADERBOARD_RANK_FLOOR).fillna(False).astype(bool)

    leader_map = _leader_names_for_topics(ctx, topic_ids)
    out["leader_name"] = out["topic_id"].map(leader_map)

    idx_pos = ctx["id_pos"][iid]
    mask = ctx["ta_inst"] == idx_pos
    topic_pos = ctx["ta_topic"][mask]
    run_topic_ids = np.asarray(ctx["topic_ids"], dtype=object)[topic_pos]
    vol_full_run = pd.Series(ctx["ta_vol_full"][mask], index=run_topic_ids)
    vol_frac_run = pd.Series(ctx["ta_vol_frac"][mask], index=run_topic_ids)
    out["vol_full_run"] = out["topic_id"].map(vol_full_run)
    out["vol_frac_run"] = out["topic_id"].map(vol_frac_run)

    change = _topic_yearly_change_df(ctx, iid)
    out = out.merge(change, on="topic_id", how="left")

    return out.reindex(columns=TOPIC_COLS).reset_index(drop=True)


# ---------------------------------------------------------------------------
# emergence_threshold -- the world top-decile of frontier_score_latest,
# computed ONCE over the whole taxonomy (institution- and tree-independent:
# a topic's own frontier score never varies by who is asking).
# ---------------------------------------------------------------------------
_EMERGENCE_THRESHOLD: float | None = None


def emergence_threshold() -> float:
    """The `frontier_score_latest` value at the world top decile, computed
    ONCE (module-level, process-wide, lazily on first use) over every scored
    topic of `topics_dim.parquet` (3,706 of 4,516 topics carry a score; the
    810 catch-all/unscored topics are excluded from the population before
    the quantile is taken, never treated as a zero). Both topic planes'
    "Top decile of emergence" mode reads this SAME fixed number, whatever
    institution or tree is on screen -- it is never recomputed per
    institution."""
    global _EMERGENCE_THRESHOLD
    if _EMERGENCE_THRESHOLD is None:
        dim = pd.read_parquet(DATA_DIR / "topics_dim.parquet", columns=["frontier_score_latest"])
        scored = pd.to_numeric(dim["frontier_score_latest"], errors="coerce").dropna()
        _EMERGENCE_THRESHOLD = float(scored.quantile(0.9))
    return _EMERGENCE_THRESHOLD


# ---------------------------------------------------------------------------
# select_topics -- the shared "Topics shown" selector, both planes
# ---------------------------------------------------------------------------
MODE_VOLUME = "volume"
MODE_FWCI = "fwci"
MODE_LED = "led"
MODE_STARS = "stars"
MODE_EMERGENCE = "emergence"
MODES = (MODE_VOLUME, MODE_FWCI, MODE_LED, MODE_STARS, MODE_EMERGENCE)

FWCI_STAT_MEAN = "mean"
FWCI_STAT_MEDIAN = "median"

N_MIN, N_MAX = 10, 100          # the slider's own clamp band
FWCI_MODE_FLOOR = 10            # "Top by FWCI_EU" mode's own citation-eligible floor


def select_topics(df: pd.DataFrame, mode: str, n: int, fwci_stat: str = FWCI_STAT_MEAN) -> pd.DataFrame:
    """One of the five "Topics shown" cuts of `df` (`institution_topics`'
    own shape), sorted for display, `n` clamped to [10, 100]. A stable tie-
    break on `topic_id` (ascending) so a re-render of the identical frame
    never reorders which rows land on the cut line.

      volume    -- sort n_ar desc (the default; the plane's own perimeter)
      fwci      -- rows with n_covered >= FWCI_MODE_FLOOR, sort by the
                   chosen stat (`fwci_stat`: "mean" or "median") desc
      led       -- is_led rows only, sort n_ar desc
      stars     -- n_stars >= 1 rows only, sort n_stars desc
      emergence -- frontier_score_latest at or above `emergence_threshold()`,
                   sort score desc -- the SAME set feeds both planes, so
                   plane A shows the identical topics plane B does under
                   this mode, by construction (one call, one frame, drawn
                   twice)."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    n_clamped = int(min(max(int(n), N_MIN), N_MAX))

    if mode == MODE_VOLUME:
        d = df
        sort_col = "n_ar"
    elif mode == MODE_FWCI:
        d = df[pd.to_numeric(df["n_covered"], errors="coerce").fillna(0) >= FWCI_MODE_FLOOR]
        sort_col = "fwci_mean" if fwci_stat != FWCI_STAT_MEDIAN else "fwci_median"
    elif mode == MODE_LED:
        d = df[df["is_led"].fillna(False)]
        sort_col = "n_ar"
    elif mode == MODE_STARS:
        d = df[pd.to_numeric(df["n_stars"], errors="coerce").fillna(0) >= 1]
        sort_col = "n_stars"
    else:  # MODE_EMERGENCE
        threshold = emergence_threshold()
        d = df[pd.to_numeric(df["frontier_score_latest"], errors="coerce") >= threshold]
        sort_col = "frontier_score_latest"

    ordered = d.sort_values([sort_col, "topic_id"], ascending=[False, True], kind="mergesort")
    return ordered.head(n_clamped).reset_index(drop=True)


# ---------------------------------------------------------------------------
# topic_set_caption -- the plain facts the two plane captions compose
# ---------------------------------------------------------------------------
PLANE_A_MIN_COVERED = 3   # plane A places no topic under this many covered works


def topic_set_caption(shown: pd.DataFrame, total_ar: float | None) -> dict:
    """Facts about the SHOWN set (`select_topics`'s own output), never the
    institution's full topic frame: how many are catch-all, how many plane A
    cannot place (n_covered < `PLANE_A_MIN_COVERED`), how many carry no
    frontier score at all (plane B), and the shown set's combined `n_ar` as
    a share of the institution's own articles-and-reviews total (`total_ar`,
    e.g. `index.total_ar_full_w1 + total_ar_full_w2`) -- `None`/NaN when
    that total is unknown or zero, never a division by zero."""
    n = len(shown)
    n_catchall = int(shown["is_excluded"].fillna(False).sum()) if n else 0
    n_not_placed_a = (int((pd.to_numeric(shown["n_covered"], errors="coerce").fillna(0)
                          < PLANE_A_MIN_COVERED).sum()) if n else 0)
    n_no_frontier = (int(pd.to_numeric(shown["frontier_score_latest"], errors="coerce").isna().sum())
                    if n else 0)
    shown_ar = float(pd.to_numeric(shown["n_ar"], errors="coerce").fillna(0).sum()) if n else 0.0
    share_of_ar = None
    if total_ar is not None and not pd.isna(total_ar) and float(total_ar) > 0:
        share_of_ar = shown_ar / float(total_ar)
    return {
        "n_shown": n,
        "n_catchall": n_catchall,
        "n_not_placed_a": n_not_placed_a,
        "n_no_frontier": n_no_frontier,
        "share_of_ar": share_of_ar,
    }
