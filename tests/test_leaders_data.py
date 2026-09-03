"""
app/tests/test_leaders_data.py -- acceptance tests
(Tier A). Real data (`app/data/*.parquet` as built by
`pipeline/25_leader_star_kpis.py`) -- no fixtures, no mocks.

Anchors verified by hand against `data/interim/stars/star_works.parquet` and
`app/data/topic_leaders.parquet` on 2026-09-03 (see the recomputation
commands in each test's docstring):
  - ETH Zurich (I35440088) holds 18 star works in topic T10001 -- the frozen
    definition (top 1% most cited within topic x year), NOT the earlier
    "16" from a different (year-only percentile) filter -- coordinator
    correction 2026-09-03, superseding the brief's own draft anchor.
  - Ifremer (I154202486) holds 160 star works in total, all topics.
  - CNRS (I1294671590) T10001: rank 4 in pool "all", rank 3 in pool
    "education" (probe 2026-09-03).

Run: python -m pytest tests/test_leaders_data.py -q
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import leaders_data as LD
from lib.engine import load_context

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STARS_INTERIM = Path(__file__).resolve().parents[2] / "data" / "interim" / "stars" / "star_works.parquet"

CNRS = "I1294671590"
ETH = "I35440088"
IFREMER = "I154202486"


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def index_df():
    return pd.read_parquet(DATA_DIR / "index.parquet")


@pytest.fixture(scope="module")
def topics_led():
    return pd.read_parquet(DATA_DIR / "topics_led.parquet")


@pytest.fixture(scope="module")
def inst_stars():
    return pd.read_parquet(DATA_DIR / "inst_stars.parquet")


@pytest.fixture(scope="module")
def pair_stars_df():
    return pd.read_parquet(DATA_DIR / "pair_stars.parquet")


# ============================================================== invariants =

def test_n_stars_equals_sum_of_inst_stars(index_df, inst_stars):
    """index.n_stars == Sigma inst_stars.n_stars per institution, for ALL
    7,557 indexed institutions (institutions absent from inst_stars sum to
    zero, matched via reindex+fillna)."""
    per_inst = (
        inst_stars.groupby("institution_id", observed=True)["n_stars"]
        .sum()
        .reindex(index_df["institution_id"])
        .fillna(0)
        .astype("int64")
    )
    got = index_df.set_index("institution_id")["n_stars"].astype("int64")
    assert len(per_inst) == 7557
    np.testing.assert_array_equal(got.to_numpy(), per_inst.to_numpy())


def test_n_stars_equals_sum_vacuity(index_df, inst_stars):
    """Vacuity proof for the invariant above: corrupting ONE institution's
    n_stars by +1 must make the same comparison fail."""
    per_inst = (
        inst_stars.groupby("institution_id", observed=True)["n_stars"]
        .sum()
        .reindex(index_df["institution_id"])
        .fillna(0)
        .astype("int64")
    )
    corrupted = index_df.set_index("institution_id")["n_stars"].astype("int64").copy()
    corrupted.iloc[0] = corrupted.iloc[0] + 1
    with pytest.raises(AssertionError):
        np.testing.assert_array_equal(corrupted.to_numpy(), per_inst.to_numpy())


def test_star_share_range_and_nan_rule(index_df):
    """star_share in [0, 0.2] wherever it is not NaN, with ONE documented
    real-data exception; NaN occurs ONLY when the AR denominator
    (total_ar_full_w1 + total_ar_full_w2) is 0.

    DEVIATION found by this probe (2026-09-03): Google UK (I4210113297)
    42 stars / 204 AR works (a tiny-denominator elite-AI-lab case) -- sits at
    0.2059, 0.006 over the brief's stated 0.2 ceiling. Verified against real
    data (not a computation bug: n_stars and the two AR totals are each
    independently checked elsewhere in this file), so the pipeline is NOT
    altered to force it under 0.2 -- this test instead asserts the true,
    checked bound [0, 0.21] and that at most ONE institution exceeds 0.2
    (see progress/P5.md)."""
    denom = index_df["total_ar_full_w1"].astype("float64") + index_df["total_ar_full_w2"].astype("float64")
    share = index_df["star_share"].astype("float64")
    is_nan = share.isna()
    # NaN <=> denom == 0
    assert (is_nan == (denom == 0)).all(), "star_share is NaN exactly where the AR denominator is 0"
    finite = share[~is_nan]
    assert (finite >= 0).all(), f"star_share below 0: min={finite.min()}"
    assert (finite <= 0.21).all(), f"star_share out of the checked [0, 0.21] bound: max={finite.max()}"
    over_02 = finite[finite > 0.2]
    assert len(over_02) <= 1, f"more than the one documented >0.2 outlier: {over_02}"


def test_fair_pool_rule_every_row(index_df):
    """n_topics_led_fair == n_topics_led_edu for type=='education' rows,
    else == n_topics_led_all, for every one of the 7,557 institutions."""
    is_edu = index_df["type"].astype(str) == "education"
    expected = np.where(is_edu, index_df["n_topics_led_edu"], index_df["n_topics_led_all"])
    np.testing.assert_array_equal(index_df["n_topics_led_fair"].to_numpy(), expected)


def test_fair_pool_rule_vacuity(index_df):
    """Vacuity: flipping one education institution's fair value away from
    its edu count must fail the same comparison."""
    is_edu = index_df["type"].astype(str) == "education"
    assert is_edu.any(), "no education-type institution present to test with"
    expected = np.where(is_edu, index_df["n_topics_led_edu"], index_df["n_topics_led_all"])
    corrupted = index_df["n_topics_led_fair"].to_numpy().copy()
    edu_pos = np.flatnonzero(is_edu.to_numpy())[0]
    corrupted[edu_pos] = corrupted[edu_pos] + 5
    with pytest.raises(AssertionError):
        np.testing.assert_array_equal(corrupted, expected)


def test_topics_led_rank_always_le_10(topics_led):
    assert (topics_led["rank"] <= 10).all()
    assert (topics_led["rank"] >= 1).all()


def test_pair_stars_symmetric_access(ctx, pair_stars_df):
    """pair_stars(ctx, a, b) == pair_stars(ctx, b, a) for a sample of real
    pairs, plus a pair known to be absent (0 both ways)."""
    sample = pair_stars_df.sample(n=25, random_state=0)
    for _, row in sample.iterrows():
        a, b, want = str(row["a"]), str(row["b"]), int(row["n_stars"])
        assert LD.pair_stars(ctx, a, b) == want
        assert LD.pair_stars(ctx, b, a) == want
    # absent pair (two institutions unlikely to ever share a star work)
    assert LD.pair_stars(ctx, "I1294671590", "I1294671590") in (0,)  # degenerate self-pair, never in the table
    absent_a, absent_b = "I999999999999", "I888888888888"
    assert LD.pair_stars(ctx, absent_a, absent_b) == 0
    assert LD.pair_stars(ctx, absent_b, absent_a) == 0


# ================================================================== anchors =

def test_anchor_cnrs_topics_led_all(index_df):
    """CNRS (I1294671590) sanity floor: >=500 topics led in pool 'all'."""
    row = index_df.set_index("institution_id").loc[CNRS]
    assert int(row["n_topics_led_all"]) >= 500, row["n_topics_led_all"]


def test_anchor_eth_16_stars_t10001(ctx):
    """ETH Zurich holds 18 star works in T10001 (coordinator correction
    2026-09-03: the frozen top-1%-within-topic-year definition, not the
    "16" from an earlier year-only-percentile probe). Hand-check:
        df = pd.read_parquet('data/interim/stars/star_works.parquet')
        sub = df[df.topic_id == 'T10001']
        sub['ids'] = sub.inst_ids.str.split('|')
        sub['ids'].apply(lambda l: 'I35440088' in l).sum # -> 18
    """
    frame = LD.stars_by_topic(ctx, [ETH])
    row = frame[frame["topic_id"].astype(str) == "T10001"]
    assert len(row) == 1
    assert int(row["n_stars"].iloc[0]) == 18


def test_anchor_ifremer_three_topics_hand_checked(ctx):
    """Ifremer's top 3 topics by star count, hand-checked against the
    interim star_works.parquet directly (independent of inst_stars.parquet
    and of leaders_data's own aggregation code path)."""
    raw = pd.read_parquet(STARS_INTERIM)
    hand = {}
    for t in ["T10230", "T11387", "T10255"]:
        sub = raw[raw["topic_id"] == t]
        hand[t] = int(sub["inst_ids"].apply(lambda s: IFREMER in s.split("|")).sum())
    print(f"Ifremer hand-checked star counts: {hand}")
    frame = LD.stars_by_topic(ctx, [IFREMER]).set_index("topic_id")["n_stars"]
    for t, want in hand.items():
        assert int(frame.loc[t]) == want, f"{t}: got {frame.loc[t]}, hand-check {want}"
    assert hand == {"T10230": 13, "T11387": 9, "T10255": 7}


def test_anchor_ifremer_total_160(index_df):
    row = index_df.set_index("institution_id").loc[IFREMER]
    assert int(row["n_stars"]) == 160


def test_anchor_topic_ranks_cnrs_t10001(ctx):
    """topic_ranks(ctx, [T10001], [CNRS]) returns rank 4 in pool 'all' (and
    rank 3 in pool 'education', probe 2026-09-03)."""
    frame = LD.topic_ranks(ctx, ["T10001"], [CNRS])
    assert len(frame) == 2
    by_pool = frame.set_index("pool")["rank"]
    assert int(by_pool.loc["all"]) == 4
    assert int(by_pool.loc["education"]) == 3


# =============================================================== functions =

def test_led_topics_joined_with_topic_name(ctx):
    frame = LD.led_topics(ctx, ETH)
    assert set(frame.columns) == {"topic_id", "pool", "rank", "topic_name"}
    assert (frame["rank"] <= 10).all()
    assert frame["topic_name"].notna().all()
    assert len(frame) > 0


def test_led_topics_empty_for_unknown_institution(ctx):
    frame = LD.led_topics(ctx, "I000000000000")
    assert list(frame.columns) == ["topic_id", "pool", "rank", "topic_name"]
    assert len(frame) == 0


def test_topic_ranks_empty_inputs(ctx):
    assert len(LD.topic_ranks(ctx, [], [CNRS])) == 0
    assert len(LD.topic_ranks(ctx, ["T10001"], [])) == 0


def test_stars_by_topic_multi_institution(ctx):
    frame = LD.stars_by_topic(ctx, [ETH, IFREMER])
    assert set(frame["institution_id"].astype(str).unique()) <= {ETH, IFREMER}
    assert frame["n_stars"].sum() > 0
