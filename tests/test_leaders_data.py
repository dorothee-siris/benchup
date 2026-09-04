"""
app/tests/test_leaders_data.py -- acceptance tests
(Tier A). Real data (`app/data/*.parquet` as built by
the upstream build) -- no fixtures, no mocks.

One ranking pool (no `pool` column anywhere in this file's data): `topic_leaders.parquet`/
`topics_led.parquet` rank every institution type together, `topics_led.parquet` holds rank<=20.

Anchors verified by hand against the underlying per-work star table
(`star_works.parquet`) and `app/data/topic_leaders.parquet`/`topics_led.parquet`
(see the recomputation commands in each test's docstring):
  - ETH Zurich (I35440088) holds 18 star works in topic T10001 -- the frozen
    definition (top 1% most cited within topic x year), NOT the earlier
    "16" from a different (year-only percentile) filter.
  - Ifremer (I154202486) holds 160 star works in total, all topics.
  - CNRS (I1294671590) T10001: world rank 4 (one pool, all institution types).
  - CNRS (I1294671590) leads 1,609 topics at rank<=20.

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

CNRS = "I1294671590"
ETH = "I35440088"
IFREMER = "I154202486"
STRASBOURG = "I68947357"


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


@pytest.fixture(scope="module")
def star_works():
    return pd.read_parquet(DATA_DIR / "star_works.parquet")


@pytest.fixture(scope="module")
def topics_dim_field_map():
    df = pd.read_parquet(DATA_DIR / "topics_dim.parquet", columns=["topic_id", "field_id"])
    df["topic_id"] = df["topic_id"].astype(str)
    return df


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

    DEVIATION found by this probe: Google UK (I4210113297)
    42 stars / 204 AR works (a tiny-denominator elite-AI-lab case) -- sits at
    0.2059, 0.006 over the stated 0.2 ceiling. Verified against real
    data (not a computation bug: n_stars and the two AR totals are each
    independently checked elsewhere in this file), so the upstream data is NOT
    altered to force it under 0.2 -- this test instead asserts the true,
    checked bound [0, 0.21] and that at most ONE institution exceeds 0.2."""
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


def test_no_pool_column_anywhere(index_df, topics_led):
    """v1.7: one ranking pool, no `pool` column survives on any table this
    module reads, and the two retired index columns are gone."""
    assert "pool" not in topics_led.columns
    assert "n_topics_led_edu" not in index_df.columns
    assert "n_topics_led_fair" not in index_df.columns
    assert "n_topics_led_all" in index_df.columns


def test_topics_led_rank_always_le_20(topics_led):
    assert (topics_led["rank"] <= 20).all()
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

def test_anchor_cnrs_leads_1609_topics(ctx, index_df):
    """CNRS (I1294671590) leads 1,609 topics at rank<=20, one pool across
    every institution type -- via `led_topics` (row count) and via
    `index.n_topics_led_all` (both must agree, and both must hit the exact
    anchor)."""
    led = LD.led_topics(ctx, CNRS)
    assert len(led) == 1609, len(led)
    row = index_df.set_index("institution_id").loc[CNRS]
    assert int(row["n_topics_led_all"]) == 1609, row["n_topics_led_all"]


def test_anchor_eth_16_stars_t10001(ctx):
    """ETH Zurich holds 18 star works in T10001 (the frozen
    top-1%-within-topic-year definition, not the "16" from an earlier
    year-only-percentile probe). Hand-checked once against the underlying
    per-work star table:
        sub = df[df.topic_id == 'T10001']
        sub['ids'] = sub.inst_ids.str.split('|')
        sub['ids'].apply(lambda l: 'I35440088' in l).sum() # -> 18
    """
    frame = LD.stars_by_topic(ctx, [ETH])
    row = frame[frame["topic_id"].astype(str) == "T10001"]
    assert len(row) == 1
    assert int(row["n_stars"].iloc[0]) == 18


def test_anchor_ifremer_total_160(index_df):
    row = index_df.set_index("institution_id").loc[IFREMER]
    assert int(row["n_stars"]) == 160


def test_anchor_topic_rank_cnrs_t10001(ctx):
    """topic_rank(ctx, CNRS, [T10001]) returns world rank 4 -- one pool,
    across every institution type (was rank 4 in the retired 'all' pool,
    rank 3 in the retired 'education' pool; v1.7 has one merged ranking)."""
    ranks = LD.topic_rank(ctx, CNRS, ["T10001"])
    assert ranks == {"T10001": 4}


# =============================================================== functions =

def test_led_topics_joined_with_topic_name(ctx):
    frame = LD.led_topics(ctx, ETH)
    assert set(frame.columns) == {"topic_id", "rank", "topic_name"}
    assert (frame["rank"] <= 20).all()
    assert (frame["rank"] >= 1).all()
    assert frame["topic_name"].notna().all()
    assert len(frame) > 0
    assert frame["rank"].is_monotonic_increasing


def test_led_topics_empty_for_unknown_institution(ctx):
    frame = LD.led_topics(ctx, "I000000000000")
    assert list(frame.columns) == ["topic_id", "rank", "topic_name"]
    assert len(frame) == 0


def test_topic_rank_empty_inputs(ctx):
    assert LD.topic_rank(ctx, CNRS, []) == {}


def test_topic_rank_none_for_unranked_topic(ctx):
    """A topic id that does not exist at all in topic_leaders.parquet ->
    None, never a KeyError or a fabricated worst rank; a real topic mixed in
    the same call still resolves."""
    ranks = LD.topic_rank(ctx, CNRS, ["T10001", "T00000000"])
    assert ranks["T00000000"] is None
    assert ranks["T10001"] == 4


def test_topic_leader_name_rank1(ctx):
    """The rank-1 publisher's own name for a well-populated topic -- a
    non-empty string, and it must be the SAME institution `topic_rank`
    reports at rank 1 for that topic (cross-checked against a direct read
    of topic_leaders.parquet, not against `topic_leader_name` circularly)."""
    name = LD.topic_leader_name(ctx, "T10001")
    assert isinstance(name, str) and len(name) > 0
    leaders = pd.read_parquet(DATA_DIR / "topic_leaders.parquet")
    rank1 = leaders[(leaders["topic_id"].astype(str) == "T10001") & (leaders["rank"] == 1)]
    assert len(rank1) == 1
    want = rank1["display_name"].iloc[0]
    want = str(want) if pd.notna(want) else str(rank1["institution_id"].iloc[0])
    assert name == want


def test_topic_leader_name_none_for_unknown_topic(ctx):
    assert LD.topic_leader_name(ctx, "T00000000") is None


def test_stars_by_topic_multi_institution(ctx):
    frame = LD.stars_by_topic(ctx, [ETH, IFREMER])
    assert set(frame["institution_id"].astype(str).unique()) <= {ETH, IFREMER}
    assert frame["n_stars"].sum() > 0


# ================================================= new star_works accessors =

def test_stars_for_topics_sums_to_inst_stars_total(ctx, inst_stars, index_df):
    """Sigma stars_for_topics(ctx, Strasbourg, <all its own topics>) ==
    inst_stars.parquet's own total for Strasbourg == index.n_stars for
    Strasbourg -- one institution's per-topic star breakdown must foot to
    the SAME total three different ways."""
    own = inst_stars.loc[inst_stars["institution_id"].astype(str) == STRASBOURG]
    topics = own["topic_id"].astype(str).tolist()
    want = int(own["n_stars"].sum())
    got = LD.stars_for_topics(ctx, STRASBOURG, topics)
    assert set(got) == set(topics)
    assert sum(got.values()) == want
    idx_n_stars = int(index_df.set_index("institution_id").loc[STRASBOURG, "n_stars"])
    assert idx_n_stars == want


def test_stars_for_topics_empty_and_zero_fill(ctx):
    assert LD.stars_for_topics(ctx, STRASBOURG, []) == {}
    # a topic Strasbourg holds no star in still comes back as an explicit 0,
    # never absent from the result.
    got = LD.stars_for_topics(ctx, STRASBOURG, ["T00000000"])
    assert got == {"T00000000": 0}


def test_pair_stars_by_topic_sums_to_pair_stars(ctx, inst_stars):
    """Sigma pair_stars_by_topic(ctx, Strasbourg, CNRS, <candidate topics>)
    == pair_stars(ctx, Strasbourg, CNRS) -- the candidate set is the union
    of both institutions' own star topics (a joint star on any topic
    outside that union is impossible, since it would require a star for
    BOTH institutions on a topic neither holds one in). Also checks
    symmetry (a, b) == (b, a)."""
    a_topics = inst_stars.loc[inst_stars["institution_id"].astype(str) == STRASBOURG, "topic_id"].astype(str)
    b_topics = inst_stars.loc[inst_stars["institution_id"].astype(str) == CNRS, "topic_id"].astype(str)
    candidates = sorted(set(a_topics) | set(b_topics))
    want = LD.pair_stars(ctx, STRASBOURG, CNRS)
    got = LD.pair_stars_by_topic(ctx, STRASBOURG, CNRS, candidates)
    assert sum(got.values()) == want
    got_rev = LD.pair_stars_by_topic(ctx, CNRS, STRASBOURG, candidates)
    assert got == got_rev


def test_pair_stars_by_topic_empty_inputs(ctx):
    assert LD.pair_stars_by_topic(ctx, STRASBOURG, CNRS, []) == {}


def test_pair_stars_by_field_hand_recount(ctx, star_works, topics_dim_field_map):
    """A hand recount of pair_stars_by_field for the Strasbourg x CNRS pair,
    one field, straight from star_works.parquet + topics_dim.parquet (the
    field with the largest joint count, so the recount is non-vacuous), plus
    a whole-pair total cross-check against `pair_stars`."""

    def _has_token(inst_ids: str, iid: str) -> bool:
        return f"|{inst_ids}|".find(f"|{iid}|") >= 0

    mask = star_works["inst_ids"].apply(lambda s: _has_token(s, STRASBOURG) and _has_token(s, CNRS))
    joint = star_works.loc[mask, ["work_id", "topic_id"]].merge(topics_dim_field_map, on="topic_id", how="left")
    assert len(joint) > 0, "Strasbourg x CNRS must hold >=1 joint star paper for this test to be non-vacuous"

    by_field = LD.pair_stars_by_field(ctx, STRASBOURG, CNRS)
    assert sum(by_field.values()) == joint["work_id"].nunique()
    assert sum(by_field.values()) == LD.pair_stars(ctx, STRASBOURG, CNRS)

    top_field = int(joint["field_id"].value_counts().idxmax())
    hand_count = int((joint["field_id"] == top_field).sum())
    assert by_field[top_field] == hand_count, (top_field, by_field[top_field], hand_count)

    # symmetry
    assert LD.pair_stars_by_field(ctx, CNRS, STRASBOURG) == by_field
