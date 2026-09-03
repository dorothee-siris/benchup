"""
app/lib/leaders_data.py.

Pure-function duckdb-pushdown slice loaders over the four tables the
upstream build writes -- `topic_leaders.parquet`,
`inst_stars.parquet`, `pair_stars.parquet`, `topics_led.parquet` -- scoped to
whatever handful of topics/institutions a caller actually needs. Same idiom
as `lib/collab_data.py:_collab_pair_slice`: a shared, memory-bounded duckdb
connection (`_duck`), a posix path inside `read_parquet('.')`, a
parameterised `WHERE`, `.df`, the known category columns cast back to
`category` on the returned slice (duckdb decodes a parquet category/
dictionary column to plain VARCHAR, not pandas `category`), and the result
cached on `ctx` under a `leaders:.` key, bounded to the `_PAIR_CACHE_MAX`
most recently used entries per cache namespace (`_lru_touch`) so a repeat
call for a still-resident key never re-scans the file while a session that
keeps hopping to new topics/institutions never accumulates an unbounded
number of slices (a concurrency fix, found via a stress test, phase B).
`ctx` is the engine context dict
(`lib.engine.substrates.load_context`'s return value, or a Streamlit page's
cached copy of it) -- every function below reads `ctx["data_dir"]`, exactly
like `collab_data`.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

import duckdb
import pandas as pd

# Same shared-connection + bounded-LRU idiom as `lib/collab_data.py`
# (module-duplicated like `_posix`) -- every per-args cache below used to
# accumulate on `ctx` forever, one entry per distinct (topics, institutions)
# combo ever requested.
_DUCK_LOCK = threading.Lock()
_PAIR_CACHE_MAX = 32


def _posix(path) -> str:
    """Windows backslashes inside a SQL string literal are ambiguous escape
    sequences -- duckdb's read_parquet takes forward-slash paths fine
    (same helper as `lib/engine/derive.py:_posix` / `lib/collab_data.py:_posix`)."""
    return Path(path).as_posix()


def _data_dir(ctx: dict) -> Path:
    return Path(ctx["data_dir"])


def _empty(cols_dtypes: dict) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=dt) for c, dt in cols_dtypes.items()})


def _duck(ctx: dict):
    """Cursor onto the ONE process-wide, memory-bounded duckdb connection
    (`SET memory_limit='512MB'` + `SET threads TO 2`), created lazily on
    `ctx` under `_DUCK_LOCK` -- identical helper to `lib/collab_data.py:
    _duck` (same shared `ctx` object in production, so truly one connection
    per process); a bare test ctx gets its own small one. `.cursor()` per
    call for thread-safety; callers `.close()` the cursor, never the parent
    connection."""
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
# topic_ranks -- topic_leaders.parquet, ANY rank <= 200 (the shared-frontier
# table shows a topic's rank even when it falls outside the top-10 that
# `topics_led`/`led_topics` are restricted to).
# ---------------------------------------------------------------------------

_TOPIC_RANKS_COLS = {"topic_id": "object", "institution_id": "object", "pool": "object", "rank": "int16"}


def topic_ranks(ctx: dict, topic_ids: list[str], inst_ids: list[str]) -> pd.DataFrame:
    """`topic_leaders.parquet` rows for the given topics x institutions
    (both pools, any rank 1.200). Returns (topic_id, institution_id, pool,
    rank); empty (right columns) when either list is empty or nothing
    matches -- a topic/institution combination absent here truly never
    appears among that topic's top-200 publishers in that pool."""
    if not topic_ids or not inst_ids:
        return _empty(_TOPIC_RANKS_COLS)
    topic_key = tuple(sorted(set(topic_ids)))
    inst_key = tuple(sorted(set(inst_ids)))
    key = f"leaders::topic_ranks::{topic_key}::{inst_key}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "topic_leaders.parquet")
        t_ph = ",".join(["?"] * len(topic_key))
        i_ph = ",".join(["?"] * len(inst_key))
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT topic_id, institution_id, pool, rank FROM read_parquet('{path}') "
                f"WHERE topic_id IN ({t_ph}) AND institution_id IN ({i_ph})",
                list(topic_key) + list(inst_key),
            ).df()
        finally:
            con.close()
        for c in ("topic_id", "institution_id", "pool"):
            df[c] = df[c].astype("category")
        df["rank"] = df["rank"].astype("int16")
        ctx[key] = df.sort_values(["topic_id", "pool", "rank"]).reset_index(drop=True)
    _lru_touch(ctx, key, "leaders_topic_ranks")
    return ctx[key]


# ---------------------------------------------------------------------------
# stars_by_topic -- inst_stars.parquet, every topic an institution holds
# >=1 star work in.
# ---------------------------------------------------------------------------

_STARS_BY_TOPIC_COLS = {"institution_id": "object", "topic_id": "object", "n_stars": "int16"}


def stars_by_topic(ctx: dict, inst_ids: list[str]) -> pd.DataFrame:
    """`inst_stars.parquet` rows for the given institutions -- (institution_id,
    topic_id, n_stars). Empty (right columns) when the list is empty or none
    of the institutions hold any star work."""
    if not inst_ids:
        return _empty(_STARS_BY_TOPIC_COLS)
    inst_key = tuple(sorted(set(inst_ids)))
    key = f"leaders::stars_by_topic::{inst_key}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "inst_stars.parquet")
        ph = ",".join(["?"] * len(inst_key))
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT institution_id, topic_id, n_stars FROM read_parquet('{path}') "
                f"WHERE institution_id IN ({ph})",
                list(inst_key),
            ).df()
        finally:
            con.close()
        df["institution_id"] = df["institution_id"].astype("category")
        df["topic_id"] = df["topic_id"].astype("category")
        df["n_stars"] = df["n_stars"].astype("int16")
        ctx[key] = df.sort_values(["institution_id", "topic_id"]).reset_index(drop=True)
    _lru_touch(ctx, key, "leaders_stars_by_topic")
    return ctx[key]


# ---------------------------------------------------------------------------
# pair_stars -- pair_stars.parquet, one joint star-work count.
# ---------------------------------------------------------------------------

def pair_stars(ctx: dict, a: str, b: str) -> int:
    """Joint star-work count for the (a, b) pair -- 0 when the pair is
    absent (`pair_stars.parquet` ships only pairs with >=1 joint star, so
    absence truly means zero, same convention as `collab_data.pulse`).
    Order-independent: `pair_stars(ctx, a, b) == pair_stars(ctx, b, a)`
    internally re-oriented to the table's own a<b convention before the
    lookup, exactly like `collab_data._collab_pair_slice`."""
    lo, hi = (a, b) if a < b else (b, a)
    key = f"leaders::pair_stars::{lo}::{hi}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "pair_stars.parquet")
        con = _duck(ctx)
        try:
            row = con.execute(
                f"SELECT n_stars FROM read_parquet('{path}') WHERE a = ? AND b = ?", [lo, hi]
            ).df()
        finally:
            con.close()
        ctx[key] = int(row["n_stars"].iloc[0]) if len(row) else 0
    _lru_touch(ctx, key, "leaders_pair_stars")
    return ctx[key]


# ---------------------------------------------------------------------------
# led_topics -- topics_led.parquet for ONE institution, joined with
# topics_dim for topic_name.
# ---------------------------------------------------------------------------

def led_topics(ctx: dict, iid: str) -> pd.DataFrame:
    """`topics_led.parquet` rows for ONE institution (rank<=10, both pools),
    joined with `topics_dim.parquet` for `topic_name`. Returns (topic_id,
    pool, rank, topic_name), sorted pool then rank; empty (right columns)
    when the institution leads no topic."""
    key = f"leaders::led_topics::{iid}"
    if key not in ctx:
        led_path = _posix(_data_dir(ctx) / "topics_led.parquet")
        dim_path = _posix(_data_dir(ctx) / "topics_dim.parquet")
        con = _duck(ctx)
        try:
            df = con.execute(
                f"""
                SELECT l.topic_id AS topic_id, l.pool AS pool, l.rank AS rank,
                       d.topic_name AS topic_name
                FROM read_parquet('{led_path}') l
                LEFT JOIN read_parquet('{dim_path}') d ON l.topic_id = d.topic_id
                WHERE l.institution_id = ?
                """,
                [iid],
            ).df()
        finally:
            con.close()
        df["topic_id"] = df["topic_id"].astype("category")
        df["pool"] = df["pool"].astype("category")
        df["rank"] = df["rank"].astype("int16")
        ctx[key] = df.sort_values(["pool", "rank"]).reset_index(drop=True)
    _lru_touch(ctx, key, "leaders_led_topics")
    return ctx[key]
