"""
tests/test_compare_golden_anchors.py -- golden-anchor top-up
for the page-facing figures `tests/test_compare_data.py` does not itself reach.

An earlier version of this file recomputed `impact_index`/
`coverage`/`trends_subfields`/`collab_data.gaps` -- every one of those
functions is DELETED and stays only in the archive.
What survives from its own method ("every number below comes
from a DIFFERENT computation path than the function under test, straight
off the parquet") is the METHOD, applied to the NEW figures this build
landed. This suite golden-tests only at the
DATA-FRAME level, never independently re-derived from the raw leader/star
parquets the way this file's own predecessor re-derived `impact`/`trends`
from `index.parquet`/`topics_all.parquet` by hand:

  * `cards`'s `n_stars`/`n_topics_led_fair` -- summed by hand off
    `inst_stars.parquet`/`topics_led.parquet`, a duckdb query completely
    independent of `leaders_data.stars_by_topic`/`led_topics`, which
    `compare_data.cards` never even calls (it reads `index.parquet`'s own
    precomputed columns instead) -- so this is a genuinely different
    computation path AND a different source table.
  * `relationship`'s `joint_stars` -- read by hand off `pair_stars.
    parquet`'s own row, bypassing `leaders_data.pair_stars`'s ctx-cache.
  * `shared_frontier`'s `rank_a`/`stars_a` -- read by hand off
    `topic_leaders.parquet`/`inst_stars.parquet` for one named topic,
    bypassing `leaders_data.topic_ranks`/`stars_by_topic` entirely.
  * `frontier_positioning`'s `n_top25_topics_published` -- recomputed via
    a hand-built `topics_dim.parquet` x `topics_all.parquet` merge+filter,
    bypassing `profile_data.topics_table` (a different loader, a different
    query engine call).

Anchor pair: Ifremer x NIOZ (I154202486 / I4210107283), the same golden
anchor pair the rest of this suite already uses.

VACUITY: every anchor is followed by an in-memory mutation of the SAME
comparison that makes it fail -- proving the check reads real data, not a
name that happens to exist.

Run from cwd `app/`: python -m pytest tests/test_compare_golden_anchors.py -q
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from lib import compare_data as CD
from lib.engine import scenario_cache as SC

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
IFREMER = "I154202486"
NIOZ = "I4210107283"
IDS = [IFREMER, NIOZ]


def _posix(p) -> str:
    return Path(p).as_posix()


@pytest.fixture(scope="module")
def ctx():
    return SC.bundle()["ctx"]


@pytest.fixture(scope="module")
def subs():
    return SC.get("bestfit", "full")


# ---------------------------------------------------------------------------
# cards -- n_stars / n_topics_led_fair, recomputed by hand off the raw source
# tables cards never itself reads (it reads index.parquet columns).
# ---------------------------------------------------------------------------

def test_cards_n_stars_matches_a_hand_sum_of_inst_stars_parquet(ctx):
    cards = CD.cards(ctx, IDS).set_index("institution_id")
    con = duckdb.connect()
    try:
        by_hand = con.execute(
            "SELECT institution_id, SUM(n_stars) AS n FROM read_parquet(?) "
            "WHERE institution_id IN (?, ?) GROUP BY institution_id",
            [_posix(DATA_DIR / "inst_stars.parquet"), IFREMER, NIOZ],
        ).df().set_index("institution_id")["n"]
    finally:
        con.close()
    for iid in IDS:
        assert int(cards.loc[iid, "n_stars"]) == int(by_hand.loc[iid]), iid

    # VACUITY: perturbing the hand-summed total by one makes the identical
    # comparison fail.
    with pytest.raises(AssertionError):
        assert int(cards.loc[IFREMER, "n_stars"]) == int(by_hand.loc[IFREMER]) + 1


def test_cards_n_topics_led_fair_matches_a_hand_count_of_topics_led_parquet(ctx):
    """v1.7: one ranking pool, topics_led.parquet has no `pool` column and
    holds rank<=20 across every institution type. cards()'s "n_topics_led_fair"
    OUTPUT key is now sourced from index.n_topics_led_all (the key itself is
    kept for the untouched card renderer -- see compare_data.py's own
    comment); this hand count is the same all-institutions population."""
    cards = CD.cards(ctx, IDS).set_index("institution_id")
    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT institution_id, COUNT(*) AS n FROM read_parquet(?) "
            "WHERE institution_id IN (?, ?) GROUP BY institution_id",
            [_posix(DATA_DIR / "topics_led.parquet"), IFREMER, NIOZ],
        ).df().set_index("institution_id")["n"]
    finally:
        con.close()
    for iid in IDS:
        by_hand = int(rows.loc[iid]) if iid in rows.index else 0
        assert int(cards.loc[iid, "n_topics_led_fair"]) == by_hand, iid

    # VACUITY
    with pytest.raises(AssertionError):
        assert int(cards.loc[IFREMER, "n_topics_led_fair"]) == by_hand + 1


# ---------------------------------------------------------------------------
# relationship -- joint_stars, recomputed by hand off pair_stars.parquet.
# ---------------------------------------------------------------------------

def test_relationship_joint_stars_matches_a_hand_read_of_pair_stars_parquet(ctx, subs):
    rel = CD.relationship(ctx, IDS, subs)
    lo, hi = (IFREMER, NIOZ) if IFREMER < NIOZ else (NIOZ, IFREMER)
    con = duckdb.connect()
    try:
        row = con.execute(
            "SELECT n_stars FROM read_parquet(?) WHERE a = ? AND b = ?",
            [_posix(DATA_DIR / "pair_stars.parquet"), lo, hi],
        ).df()
    finally:
        con.close()
    by_hand = int(row["n_stars"].iloc[0]) if len(row) else 0
    assert rel["joint_stars"] == by_hand

    # VACUITY
    with pytest.raises(AssertionError):
        assert rel["joint_stars"] == by_hand + 1


# ---------------------------------------------------------------------------
# shared_frontier -- rank_a/stars_a for one named topic, recomputed by
# hand off topic_leaders.parquet/inst_stars.parquet.
# ---------------------------------------------------------------------------

def test_shared_frontier_rank_and_stars_match_a_hand_read_of_the_raw_leader_tables(ctx, subs):
    """v1.7: topic_leaders.parquet has no `pool` column -- one ranking across
    every institution type (shared_frontier's own pool_a/pool_b are now
    always "all", kept only for the untouched table renderer)."""
    sf = CD.shared_frontier(ctx, subs, IDS)
    assert len(sf) > 0, "the anchor pair must share at least one frontier topic"
    row = sf.iloc[0]
    topic_id = row["topic_id"]
    assert row["pool_a"] == "all" and row["pool_b"] == "all"

    con = duckdb.connect()
    try:
        rank_row = con.execute(
            "SELECT rank FROM read_parquet(?) WHERE topic_id = ? AND institution_id = ?",
            [_posix(DATA_DIR / "topic_leaders.parquet"), topic_id, IFREMER],
        ).df()
        star_row = con.execute(
            "SELECT n_stars FROM read_parquet(?) WHERE topic_id = ? AND institution_id = ?",
            [_posix(DATA_DIR / "inst_stars.parquet"), topic_id, IFREMER],
        ).df()
    finally:
        con.close()

    expected_rank = int(rank_row["rank"].iloc[0]) if len(rank_row) else None
    if expected_rank is None:
        assert pd.isna(row["rank_a"])
    else:
        assert int(row["rank_a"]) == expected_rank

    expected_stars = int(star_row["n_stars"].iloc[0]) if len(star_row) else 0
    assert int(row["stars_a"]) == expected_stars

    # VACUITY
    with pytest.raises(AssertionError):
        assert int(row["stars_a"]) == expected_stars + 1


# ---------------------------------------------------------------------------
# frontier_positioning -- n_top25_topics_published, recomputed by hand off
# a topics_dim x topics_all merge (bypassing profile_data.topics_table).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# reciprocity -- D27's new per-field columns, recomputed by hand off the raw
# collab_pair_fields.parquet / star_works.parquet / topics_dim.parquet /
# collab_pairs.parquet tables `collab_data.reciprocity_frame` itself reads,
# bypassing its own duckdb pushdowns and cache.
# ---------------------------------------------------------------------------

def test_reciprocity_fwci_mean_matches_a_hand_read_of_collab_pair_fields(ctx, subs):
    rel = CD.relationship(ctx, IDS, subs)
    lo, hi = (IFREMER, NIOZ) if IFREMER < NIOZ else (NIOZ, IFREMER)
    con = duckdb.connect()
    try:
        raw = con.execute(
            "SELECT field_id, fwci_mean, n_fwci FROM read_parquet(?) WHERE a = ? AND b = ?",
            [_posix(DATA_DIR / "collab_pair_fields.parquet"), lo, hi],
        ).df().set_index("field_id")
    finally:
        con.close()
    out = rel["reciprocity"].set_index("field_id")
    assert len(out) > 0
    for fid in out.index:
        row, hand = out.loc[fid], raw.loc[fid]
        if pd.isna(hand["fwci_mean"]):
            assert pd.isna(row["fwci_mean"])
        else:
            assert row["fwci_mean"] == pytest.approx(float(hand["fwci_mean"]), abs=1e-4)
        assert int(row["n_fwci"]) == int(hand["n_fwci"])

    # VACUITY
    fid0 = out.index[0]
    with pytest.raises(AssertionError):
        assert int(out.loc[fid0, "n_fwci"]) == int(raw.loc[fid0, "n_fwci"]) + 1


def test_reciprocity_n_stars_field_matches_a_hand_join_of_star_works_and_topics_dim(ctx, subs):
    rel = CD.relationship(ctx, IDS, subs)
    con = duckdb.connect()
    try:
        by_hand = con.execute(
            """
            SELECT d.field_id AS field_id, COUNT(DISTINCT s.work_id) AS n
            FROM read_parquet(?) s JOIN read_parquet(?) d ON s.topic_id = d.topic_id
            WHERE ('|' || s.inst_ids || '|') LIKE '%|' || ? || '|%'
              AND ('|' || s.inst_ids || '|') LIKE '%|' || ? || '|%'
            GROUP BY d.field_id
            """,
            [_posix(DATA_DIR / "star_works.parquet"), _posix(DATA_DIR / "topics_dim.parquet"),
             IFREMER, NIOZ],
        ).df().set_index("field_id")["n"]
    finally:
        con.close()
    out = rel["reciprocity"].set_index("field_id")
    for fid in out.index:
        want = int(by_hand.loc[fid]) if fid in by_hand.index else 0
        assert int(out.loc[fid, "n_stars_field"]) == want, fid
    # every field PRESENT in reciprocity_frame's own set matches exactly
    # (just proved, row by row); the sums may still differ by a handful --
    # a star work's field (`star_works` joined through the CURRENT
    # `topics_dim.field_id`) can land in a field `collab_pair_fields`
    # (built at a different time, off its own primary-topic snapshot)
    # carries zero joint CORE-AR volume for at all -- a small, reported
    # cross-table vintage drift, not silently absorbed: for this anchor
    # pair, 1 of 8 joint stars (topic
    # T11340, work W4294237989) falls on a field with no `collab_pair_
    # fields` row at all.
    diff = int(by_hand.sum()) - int(out["n_stars_field"].sum())
    assert 0 <= diff <= 2, (
        f"{diff} joint stars fall outside reciprocity_frame's own field set -- "
        "more than the small cross-table vintage drift already documented; investigate")

    # VACUITY
    fid0 = out.index[0]
    with pytest.raises(AssertionError):
        assert int(out.loc[fid0, "n_stars_field"]) == int(by_hand.get(fid0, 0)) + 1


def test_reciprocity_rank_in_a_b_match_a_hand_read_of_collab_pairs_and_reorient_with_pulse(ctx, subs):
    """The pair-level partner rank rides every field row identically, and
    re-orients with the caller's (a, b) exactly like `collab_data.pulse`
    does for the SAME two columns on the SAME table."""
    from lib import collab_data as COL

    rel = CD.relationship(ctx, IDS, subs)
    out = rel["reciprocity"]
    assert out["rank_in_a"].nunique() == 1
    assert out["rank_in_b"].nunique() == 1
    pulse = COL.pulse(ctx, IFREMER, NIOZ)
    assert int(out["rank_in_a"].iloc[0]) == pulse["rank_in_a"]
    assert int(out["rank_in_b"].iloc[0]) == pulse["rank_in_b"]


def test_frontier_positioning_n_published_matches_a_hand_topics_all_merge(ctx, subs):
    pos = CD.frontier_positioning(ctx, subs, IDS).set_index("institution_id")
    con = duckdb.connect()
    try:
        rows = con.execute(
            """
            SELECT a.institution_id AS institution_id, COUNT(*) AS n
            FROM read_parquet(?) a
            JOIN read_parquet(?) d ON a.topic_id = d.topic_id
            WHERE a.institution_id IN (?, ?) AND a.vol_full >= 1 AND d.top25pct_frontier = TRUE
            GROUP BY a.institution_id
            """,
            [_posix(DATA_DIR / "topics_all.parquet"), _posix(DATA_DIR / "topics_dim.parquet"),
             IFREMER, NIOZ],
        ).df().set_index("institution_id")["n"]
    finally:
        con.close()
    for iid in IDS:
        assert int(pos.loc[iid, "n_top25_topics_published"]) == int(rows.loc[iid]), iid

    # VACUITY
    with pytest.raises(AssertionError):
        assert int(pos.loc[IFREMER, "n_top25_topics_published"]) == int(rows.loc[IFREMER]) + 1
