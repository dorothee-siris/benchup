"""
app/lib/leaders_data.py.

Pure-function duckdb-pushdown slice loaders over the tables the
upstream build writes -- `topic_leaders.parquet`,
`inst_stars.parquet`, `pair_stars.parquet`, `topics_led.parquet`, `star_works.parquet` --
scoped to whatever handful of topics/institutions a caller actually needs. Same idiom
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

One ranking pool: `topic_leaders.parquet`/`topics_led.parquet` rank every
institution type together (no `pool` column, no education-only leaderboard);
`topics_led.parquet` holds rank<=20. A topic's rank-1 publisher's own name is
exposed by `topic_leader_name` for use in "world #k of 200, led by X" copy.

`star_works.parquet` (one row per star paper, its own PRIMARY topic and
year, a pipe-delimited `inst_ids` string of every direct-authorship
institution on the work) backs three institution/pair accessors below --
`stars_for_topics`, `pair_stars_by_topic`, `pair_stars_by_field` -- each
matching one institution id by testing for the EXACT pipe-delimited token
(`'|' || inst_ids || '|' LIKE '%|' || ? || '|%'`), never a plain substring
search, since one institution id can be a text prefix of another.
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

# One institution's pipe-delimited token, matched at exact token boundaries
# inside a `inst_ids` string padded with a leading/trailing pipe -- shared by
# every star_works.parquet accessor below so the match rule lives in one place.
_TOKEN_LIKE = "('|' || inst_ids || '|') LIKE '%|' || ? || '|%'"


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
    (`SET memory_limit='256MB'` + `SET threads TO 1`, tightened from
    512MB/2 threads -- a concurrency fix, found via a stress test, phase B;
    see `lib/collab_data.py:_duck`'s own docstring for the measurement and
    the traded ceiling), created lazily on
    `ctx` under `_DUCK_LOCK` -- identical helper to `lib/collab_data.py:
    _duck` (same shared `ctx` object in production, so truly one connection
    per process); a bare test ctx gets its own small one. `.cursor()` per
    call for thread-safety; callers `.close()` the cursor, never the parent
    connection."""
    with _DUCK_LOCK:
        con = ctx.get("_duck_con")
        if con is None:
            con = duckdb.connect()
            con.execute("SET memory_limit='256MB'")
            con.execute("SET threads TO 1")
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
# topic_rank -- topic_leaders.parquet, ONE institution's rank (1..200, or
# None when it does not appear at all) on each of a list of topics.
# ---------------------------------------------------------------------------

def topic_rank(ctx: dict, iid: str, topic_ids: list[str]) -> dict[str, int | None]:
    """This institution's world rank on each of `topic_ids`
    (`topic_leaders.parquet`, one ranking across every institution type,
    1..200) -- None for a topic where `iid` does not appear among that
    topic's ranked publishers at all (never a fabricated worst rank). Every
    requested topic_id is a key in the returned dict, empty dict when
    `topic_ids` is empty."""
    topic_key = tuple(sorted(set(topic_ids)))
    if not topic_key:
        return {}
    key = f"leaders::topic_rank::{iid}::{topic_key}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "topic_leaders.parquet")
        t_ph = ",".join(["?"] * len(topic_key))
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT topic_id, rank FROM read_parquet('{path}') "
                f"WHERE institution_id = ? AND topic_id IN ({t_ph})",
                [iid] + list(topic_key),
            ).df()
        finally:
            con.close()
        ranks = {str(t): int(r) for t, r in zip(df["topic_id"], df["rank"])}
        ctx[key] = {t: ranks.get(t) for t in topic_key}
    _lru_touch(ctx, key, "leaders_topic_rank")
    return ctx[key]


# ---------------------------------------------------------------------------
# topic_leader_name -- topic_leaders.parquet, the rank-1 publisher's own name
# for ONE topic.
# ---------------------------------------------------------------------------

def topic_leader_name(ctx: dict, topic_id: str) -> str | None:
    """The rank-1 publisher's `display_name` for one topic
    (`topic_leaders.parquet`), falling back to its `institution_id` when the
    name itself is null (a handful of rows ship that way, see the table's
    own build note); None when the topic has no rank-1 row at all."""
    key = f"leaders::topic_leader_name::{topic_id}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "topic_leaders.parquet")
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT institution_id, display_name FROM read_parquet('{path}') "
                f"WHERE topic_id = ? AND rank = 1",
                [topic_id],
            ).df()
        finally:
            con.close()
        if len(df):
            name = df["display_name"].iloc[0]
            ctx[key] = str(name) if pd.notna(name) else str(df["institution_id"].iloc[0])
        else:
            ctx[key] = None
    _lru_touch(ctx, key, "leaders_topic_leader_name")
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
    """`topics_led.parquet` rows for ONE institution (rank<=20, one ranking
    across every institution type), joined with `topics_dim.parquet` for
    `topic_name`. Returns (topic_id, rank, topic_name), sorted by rank;
    empty (right columns) when the institution leads no topic."""
    key = f"leaders::led_topics::{iid}"
    if key not in ctx:
        led_path = _posix(_data_dir(ctx) / "topics_led.parquet")
        dim_path = _posix(_data_dir(ctx) / "topics_dim.parquet")
        con = _duck(ctx)
        try:
            df = con.execute(
                f"""
                SELECT l.topic_id AS topic_id, l.rank AS rank,
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
        df["rank"] = df["rank"].astype("int16")
        ctx[key] = df.sort_values(["rank"]).reset_index(drop=True)
    _lru_touch(ctx, key, "leaders_led_topics")
    return ctx[key]


# ---------------------------------------------------------------------------
# stars_for_topics -- star_works.parquet, one institution's star-paper count
# per topic (a scoped, per-topic breakdown of what index.n_stars totals).
# ---------------------------------------------------------------------------

def stars_for_topics(ctx: dict, iid: str, topic_ids: list[str]) -> dict[str, int]:
    """Star-paper counts for institution `iid`, one count per requested
    topic (0 when absent) -- `star_works.parquet`, works whose pipe-
    delimited `inst_ids` contain `iid`'s exact token, deduplicated per work
    (`COUNT(DISTINCT work_id)`, defensive: this table's own grain is already
    one row per work). Every requested topic_id is a key in the result, so
    `sum(stars_for_topics(ctx, iid, topics).values())` is always a valid
    total over exactly those topics -- summed over ALL of one institution's
    topics, it equals that institution's `inst_stars.parquet` total
    (`index.n_stars`)."""
    topic_key = tuple(sorted(set(topic_ids)))
    if not topic_key:
        return {}
    key = f"leaders::stars_for_topics::{iid}::{topic_key}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "star_works.parquet")
        t_ph = ",".join(["?"] * len(topic_key))
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT topic_id, COUNT(DISTINCT work_id) AS n FROM read_parquet('{path}') "
                f"WHERE topic_id IN ({t_ph}) AND {_TOKEN_LIKE} "
                f"GROUP BY topic_id",
                list(topic_key) + [iid],
            ).df()
        finally:
            con.close()
        counts = {str(t): int(n) for t, n in zip(df["topic_id"], df["n"])}
        ctx[key] = {t: counts.get(t, 0) for t in topic_key}
    _lru_touch(ctx, key, "leaders_stars_for_topics")
    return ctx[key]


# ---------------------------------------------------------------------------
# pair_stars_by_topic / pair_stars_by_field -- star_works.parquet, a pair's
# JOINT star-paper counts (both institutions' exact token present on the
# same work), by topic or rolled up to field via topics_dim.
# ---------------------------------------------------------------------------

def pair_stars_by_topic(ctx: dict, a: str, b: str, topic_ids: list[str]) -> dict[str, int]:
    """Joint star-paper counts for the (a, b) pair, one count per requested
    topic (0 when absent) -- `star_works.parquet`, works whose `inst_ids`
    contain BOTH a's and b's exact token, deduplicated per work. Symmetric:
    `pair_stars_by_topic(ctx, a, b, X) == pair_stars_by_topic(ctx, b, a, X)`,
    re-oriented to a fixed lo/hi pair before the cache key/lookup, same
    convention as `pair_stars`. Summed over ALL of a pair's shared topics,
    equals `pair_stars(ctx, a, b)`."""
    lo, hi = (a, b) if a < b else (b, a)
    topic_key = tuple(sorted(set(topic_ids)))
    if not topic_key:
        return {}
    key = f"leaders::pair_stars_by_topic::{lo}::{hi}::{topic_key}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "star_works.parquet")
        t_ph = ",".join(["?"] * len(topic_key))
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT topic_id, COUNT(DISTINCT work_id) AS n FROM read_parquet('{path}') "
                f"WHERE topic_id IN ({t_ph}) AND {_TOKEN_LIKE} AND {_TOKEN_LIKE} "
                f"GROUP BY topic_id",
                list(topic_key) + [lo, hi],
            ).df()
        finally:
            con.close()
        counts = {str(t): int(n) for t, n in zip(df["topic_id"], df["n"])}
        ctx[key] = {t: counts.get(t, 0) for t in topic_key}
    _lru_touch(ctx, key, "leaders_pair_stars_by_topic")
    return ctx[key]


def pair_star_ids_by_topic(ctx: dict, a: str, b: str, topic_ids: list[str]) -> dict[str, list[str]]:
    """Joint star-paper WORK IDS for the (a, b) pair, one list per requested
    topic (empty list when absent) -- `star_works.parquet`, the SAME token-
    match join `pair_stars_by_topic` uses, but returning the underlying
    `work_id` values (deduplicated, sorted for a deterministic order) rather
    than a count: the exact ids the balance bars' star-mode link column (and
    the live count check that verifies it) both need. Symmetric like
    `pair_stars_by_topic`: `pair_star_ids_by_topic(ctx, a, b, X) ==
    pair_star_ids_by_topic(ctx, b, a, X)`, re-oriented to a fixed lo/hi pair
    before the cache key/lookup, same convention. `len(ids)` for a topic
    always equals `pair_stars_by_topic(ctx, a, b, [topic])[topic]`."""
    lo, hi = (a, b) if a < b else (b, a)
    topic_key = tuple(sorted(set(topic_ids)))
    if not topic_key:
        return {}
    key = f"leaders::pair_star_ids_by_topic::{lo}::{hi}::{topic_key}"
    if key not in ctx:
        path = _posix(_data_dir(ctx) / "star_works.parquet")
        t_ph = ",".join(["?"] * len(topic_key))
        con = _duck(ctx)
        try:
            df = con.execute(
                f"SELECT DISTINCT topic_id, work_id FROM read_parquet('{path}') "
                f"WHERE topic_id IN ({t_ph}) AND {_TOKEN_LIKE} AND {_TOKEN_LIKE}",
                list(topic_key) + [lo, hi],
            ).df()
        finally:
            con.close()
        ids_map: dict[str, list[str]] = {t: [] for t in topic_key}
        for t, w in zip(df["topic_id"], df["work_id"]):
            ids_map[str(t)].append(str(w))
        for t in ids_map:
            ids_map[t].sort()
        ctx[key] = ids_map
    _lru_touch(ctx, key, "leaders_pair_star_ids_by_topic")
    return ctx[key]


def pair_stars_by_field(ctx: dict, a: str, b: str) -> dict[int, int]:
    """Joint star-paper counts for the (a, b) pair, grouped by field via
    each star work's own PRIMARY topic mapped through `topics_dim.parquet`
    (topic -> field_id). Symmetric like `pair_stars_by_topic`, re-oriented
    to a fixed lo/hi pair before the cache key/lookup. A field absent from
    the result holds zero joint stars (never a fabricated 0 row -- callers
    that need every field present fill from their own field list)."""
    lo, hi = (a, b) if a < b else (b, a)
    key = f"leaders::pair_stars_by_field::{lo}::{hi}"
    if key not in ctx:
        star_path = _posix(_data_dir(ctx) / "star_works.parquet")
        dim_path = _posix(_data_dir(ctx) / "topics_dim.parquet")
        con = _duck(ctx)
        try:
            df = con.execute(
                f"""
                SELECT d.field_id AS field_id, COUNT(DISTINCT s.work_id) AS n
                FROM read_parquet('{star_path}') s
                JOIN read_parquet('{dim_path}') d ON s.topic_id = d.topic_id
                WHERE {_TOKEN_LIKE.replace('inst_ids', 's.inst_ids')}
                  AND {_TOKEN_LIKE.replace('inst_ids', 's.inst_ids')}
                GROUP BY d.field_id
                """,
                [lo, hi],
            ).df()
        finally:
            con.close()
        ctx[key] = {int(f): int(n) for f, n in zip(df["field_id"], df["n"])}
    _lru_touch(ctx, key, "leaders_pair_stars_by_field")
    return ctx[key]


def pair_stars_by_subfield(ctx: dict, a: str, b: str) -> dict[int, int]:
    """Joint star-paper counts for the (a, b) pair, grouped by BESTFIT
    subfield via each star work's own PRIMARY topic mapped through
    `topics_dim.parquet` (topic -> bestfit_subfield_id) -- the same join
    `pair_stars_by_field` runs one level coarser. Symmetric like
    `pair_stars_by_topic`/`pair_stars_by_field`, re-oriented to a fixed
    lo/hi pair before the cache key/lookup. A subfield absent from the
    result holds zero joint stars (never a fabricated 0 row -- callers that
    need every subfield present fill from their own subfield list)."""
    lo, hi = (a, b) if a < b else (b, a)
    key = f"leaders::pair_stars_by_subfield::{lo}::{hi}"
    if key not in ctx:
        star_path = _posix(_data_dir(ctx) / "star_works.parquet")
        dim_path = _posix(_data_dir(ctx) / "topics_dim.parquet")
        con = _duck(ctx)
        try:
            df = con.execute(
                f"""
                SELECT d.bestfit_subfield_id AS subfield_id, COUNT(DISTINCT s.work_id) AS n
                FROM read_parquet('{star_path}') s
                JOIN read_parquet('{dim_path}') d ON s.topic_id = d.topic_id
                WHERE {_TOKEN_LIKE.replace('inst_ids', 's.inst_ids')}
                  AND {_TOKEN_LIKE.replace('inst_ids', 's.inst_ids')}
                GROUP BY d.bestfit_subfield_id
                """,
                [lo, hi],
            ).df()
        finally:
            con.close()
        ctx[key] = {int(f): int(n) for f, n in zip(df["subfield_id"], df["n"])}
    _lru_touch(ctx, key, "leaders_pair_stars_by_subfield")
    return ctx[key]
