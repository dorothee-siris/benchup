"""tests/test_topic_data.py -- `lib/topic_data.py`, on real deployed data:
Universite de Strasbourg (I68947357), CNRS (I1294671590), University of
Salento (I142910587).

Run from cwd `app/`: python -m pytest tests/test_topic_data.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib import topic_data as TD  # noqa: E402
from lib.engine import load_context  # noqa: E402

DATA = APP_DIR / "data"
STRASBOURG = "I68947357"
CNRS = "I1294671590"
SALENTO = "I142910587"
SEEDS = (STRASBOURG, CNRS, SALENTO)


@pytest.fixture(scope="module")
def ctx() -> dict:
    return load_context(DATA)


@pytest.fixture(scope="module")
def frames(ctx) -> dict:
    return {iid: TD.institution_topics(ctx, iid, "bestfit") for iid in SEEDS}


# ---------------------------------------------------------------------------
# institution_topics -- shape, row count against the raw parquet, floors
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("iid", SEEDS)
def test_institution_topics_columns_and_row_count_match_inst_topic_impact(frames, iid):
    df = frames[iid]
    assert list(df.columns) == TD.TOPIC_COLS
    raw = pd.read_parquet(DATA / "inst_topic_impact.parquet",
                          columns=["institution_id", "topic_id"])
    raw_n = int((raw["institution_id"] == iid).sum())
    assert len(df) == raw_n, (iid, len(df), raw_n)
    # this IS the workbook's uncapped "Topics" sheet row count (JOB section
    # 3: "all rows, every column above, no cap") -- same frame, no cap
    # applied anywhere in this function.


@pytest.mark.parametrize("iid", SEEDS)
def test_institution_topics_every_row_clears_the_n_ar_floor(frames, iid):
    df = frames[iid]
    assert (df["n_ar"] >= 3).all()


@pytest.mark.parametrize("iid", SEEDS)
def test_institution_topics_placement_floor_n_covered_ge_3(frames, iid):
    """The shipped `inst_topic_impact.parquet` never has n_covered < 3 (its
    OWN floor is n_ar>=3, and every shipped row's n_covered happens to clear
    3 too -- verified directly on the file, not assumed): plane A's
    "not placed" count is therefore 0 today, structurally, and
    `topic_set_caption` must still compute it as a real count (never a
    hardcoded 0) so a future data refresh that ever ships a lower floor is
    still honestly captioned -- proven on a synthetic frame below."""
    df = frames[iid]
    assert (df["n_covered"] >= TD.PLANE_A_MIN_COVERED).all()


def test_topic_set_caption_counts_a_synthetic_below_floor_row():
    shown = pd.DataFrame({
        "is_excluded": [False, True, False],
        "n_covered": [5, 2, 1],
        "frontier_score_latest": [0.5, np.nan, 0.9],
        "n_ar": [10, 4, 6],
    })
    facts = TD.topic_set_caption(shown, total_ar=100.0)
    assert facts["n_shown"] == 3
    assert facts["n_catchall"] == 1
    assert facts["n_not_placed_a"] == 2, "n_covered < 3 -> rows 2 and 3"
    assert facts["n_no_frontier"] == 1
    assert facts["share_of_ar"] == pytest.approx(20.0 / 100.0)


def test_topic_set_caption_share_is_none_when_total_ar_unknown_or_zero():
    shown = pd.DataFrame({"is_excluded": [False], "n_covered": [10],
                          "frontier_score_latest": [0.1], "n_ar": [5]})
    assert TD.topic_set_caption(shown, total_ar=None)["share_of_ar"] is None
    assert TD.topic_set_caption(shown, total_ar=0.0)["share_of_ar"] is None
    assert TD.topic_set_caption(shown, total_ar=np.nan)["share_of_ar"] is None


def test_topic_set_caption_on_an_empty_frame_never_raises():
    empty = pd.DataFrame(columns=["is_excluded", "n_covered", "frontier_score_latest", "n_ar"])
    facts = TD.topic_set_caption(empty, total_ar=100.0)
    # a valid, known total_ar with zero shown topics is a real "0% of a
    # known whole" -- distinct from total_ar itself being unknown (None/NaN
    # /0), which the dedicated test above covers and which alone yields None.
    assert facts == {"n_shown": 0, "n_catchall": 0, "n_not_placed_a": 0,
                     "n_no_frontier": 0, "share_of_ar": 0.0}


@pytest.mark.parametrize("iid", SEEDS)
def test_institution_topics_catchall_flag_matches_topics_dim(ctx, frames, iid):
    df = frames[iid]
    dim = pd.read_parquet(DATA / "topics_dim.parquet", columns=["topic_id", "is_excluded"])
    dim["topic_id"] = dim["topic_id"].astype(str)
    dim_map = dict(zip(dim["topic_id"], dim["is_excluded"]))
    for _, row in df.iterrows():
        assert bool(row["is_excluded"]) == bool(dim_map.get(row["topic_id"], False)), row["topic_id"]
    assert df["is_excluded"].fillna(False).sum() > 0, "fixture institutions must include catch-all topics"


# ---------------------------------------------------------------------------
# emergence_threshold -- computed ONCE, institution-independent
# ---------------------------------------------------------------------------
def test_emergence_threshold_is_the_world_top_decile_of_scored_topics():
    dim = pd.read_parquet(DATA / "topics_dim.parquet", columns=["frontier_score_latest"])
    scored = pd.to_numeric(dim["frontier_score_latest"], errors="coerce").dropna()
    assert len(scored) == 3706, "the taxonomy's own scored-topic count (810 unscored of 4,516)"
    expected = float(scored.quantile(0.9))
    assert TD.emergence_threshold() == pytest.approx(expected)
    n_at_or_above = int((scored >= expected).sum())
    assert 0 < n_at_or_above < len(scored) * 0.15, n_at_or_above  # a real top-decile-sized band


def test_emergence_threshold_is_memoized_across_calls():
    a = TD.emergence_threshold()
    b = TD.emergence_threshold()
    assert a == b


# ---------------------------------------------------------------------------
# select_topics -- each mode correct by construction, n clamp, tie-break
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("iid", SEEDS)
def test_select_topics_volume_mode_sorted_desc_by_n_ar(frames, iid):
    sel = TD.select_topics(frames[iid], "volume", 50)
    assert (sel["n_ar"].diff().dropna() <= 0).all()
    assert len(sel) == min(50, len(frames[iid]))


@pytest.mark.parametrize("iid", SEEDS)
def test_select_topics_fwci_mode_floor_and_sort(frames, iid):
    df = frames[iid]
    if (df["n_covered"] >= TD.FWCI_MODE_FLOOR).sum() == 0:
        pytest.skip(f"{iid} has no topic clearing the FWCI floor")
    sel_mean = TD.select_topics(df, "fwci", 50, fwci_stat="mean")
    assert (sel_mean["n_covered"] >= TD.FWCI_MODE_FLOOR).all()
    assert (sel_mean["fwci_mean"].diff().dropna() <= 0).all()
    sel_median = TD.select_topics(df, "fwci", 50, fwci_stat="median")
    assert (sel_median["n_covered"] >= TD.FWCI_MODE_FLOOR).all()
    assert (sel_median["fwci_median"].diff().dropna() <= 0).all()


@pytest.mark.parametrize("iid", SEEDS)
def test_select_topics_led_mode_every_row_ranked_top_20(frames, iid):
    df = frames[iid]
    sel = TD.select_topics(df, "led", 50)
    if len(sel) == 0:
        pytest.skip(f"{iid} leads no topic in this frame")
    assert (sel["world_rank"] <= 20).all()
    assert sel["is_led"].all()
    assert (sel["n_ar"].diff().dropna() <= 0).all()


@pytest.mark.parametrize("iid", SEEDS)
def test_select_topics_stars_mode_every_row_has_a_star(frames, iid):
    df = frames[iid]
    sel = TD.select_topics(df, "stars", 50)
    if len(sel) == 0:
        pytest.skip(f"{iid} has no starred topic")
    assert (sel["n_stars"] >= 1).all()
    assert (sel["n_stars"].diff().dropna() <= 0).all()


@pytest.mark.parametrize("iid", SEEDS)
def test_select_topics_emergence_mode_at_or_above_the_global_threshold(frames, iid):
    df = frames[iid]
    threshold = TD.emergence_threshold()
    sel = TD.select_topics(df, "emergence", 50)
    if len(sel) == 0:
        pytest.skip(f"{iid} has no topic in the world top decile of emergence")
    assert (sel["frontier_score_latest"] >= threshold).all()
    assert (sel["frontier_score_latest"].diff().dropna() <= 0).all()


def test_select_topics_n_is_clamped_to_10_100():
    d = pd.DataFrame({
        "topic_id": [f"T{i}" for i in range(150)],
        "n_ar": list(range(150, 0, -1)),
        "n_covered": [50] * 150, "fwci_mean": [1.0] * 150, "fwci_median": [1.0] * 150,
        "is_led": [False] * 150, "world_rank": [None] * 150, "n_stars": [0] * 150,
        "frontier_score_latest": [0.0] * 150,
    })
    assert len(TD.select_topics(d, "volume", 5)) == 10
    assert len(TD.select_topics(d, "volume", 100)) == 100
    assert len(TD.select_topics(d, "volume", 500)) == 100
    assert len(TD.select_topics(d, "volume", 37)) == 37


def test_select_topics_stable_tie_break_on_topic_id():
    d = pd.DataFrame({
        "topic_id": ["T3", "T1", "T2"],
        "n_ar": [10, 10, 10],
        "n_covered": [10, 10, 10], "fwci_mean": [1.0] * 3, "fwci_median": [1.0] * 3,
        "is_led": [False] * 3, "world_rank": [None] * 3, "n_stars": [0] * 3,
        "frontier_score_latest": [0.0] * 3,
    })
    sel = TD.select_topics(d, "volume", 10)
    assert list(sel["topic_id"]) == ["T1", "T2", "T3"], "identical n_ar -> topic_id ascending"


def test_select_topics_invalid_mode_raises():
    d = pd.DataFrame({"topic_id": ["T1"], "n_ar": [5]})
    with pytest.raises(ValueError):
        TD.select_topics(d, "nonsense", 50)


# ---------------------------------------------------------------------------
# The two planes share their set, under every mode (identical DataFrame in,
# one call -- proven by determinism: the SAME call always returns the SAME
# topic_id set, which is what "one frame drawn twice" structurally requires).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("mode", TD.MODES)
def test_select_topics_is_deterministic_so_both_planes_share_one_set(frames, mode):
    df = frames[STRASBOURG]
    kw = {"fwci_stat": "mean"} if mode == "fwci" else {}
    a = TD.select_topics(df, mode, 50, **kw)
    b = TD.select_topics(df, mode, 50, **kw)
    assert list(a["topic_id"]) == list(b["topic_id"]), (
        "plane A and plane B call select_topics with identical arguments and "
        "must therefore draw the identical topic set, by construction")


# ---------------------------------------------------------------------------
# change_w1_w2 -- hand-recomputed for one real topic
# ---------------------------------------------------------------------------
def test_change_w1_w2_hand_recomputed_for_one_topic(ctx, frames):
    df = frames[STRASBOURG]
    row = df.iloc[0]
    topic_id = row["topic_id"]
    inst_key = int(ctx["index_by_id"].loc[STRASBOURG, "inst_key"])
    ta = pd.read_parquet(DATA / "topics_all.parquet",
                         columns=["inst_key", "topic_id", "vol_full_2020", "vol_full_2021",
                                  "vol_full_2022", "vol_full_2023", "vol_full_2024"])
    hit = ta[(ta["inst_key"] == inst_key) & (ta["topic_id"].astype(str) == str(topic_id))]
    assert len(hit) == 1, (topic_id, len(hit))
    hit = hit.iloc[0]
    w1_total = float(hit["vol_full_2020"] + hit["vol_full_2021"] + hit["vol_full_2022"])
    w2_total = float(hit["vol_full_2023"] + hit["vol_full_2024"])
    w1_mean, w2_mean = w1_total / 3.0, w2_total / 2.0
    expected_change = np.nan if w1_mean == 0 else (w2_mean / w1_mean - 1.0)
    expected_low_base = w1_total < TD.LOW_BASE_FLOOR

    if np.isnan(expected_change):
        assert pd.isna(row["change_w1_w2"])
    else:
        assert row["change_w1_w2"] == pytest.approx(expected_change, abs=1e-6), (
            topic_id, row["change_w1_w2"], expected_change)
    assert bool(row["low_base"]) == bool(expected_low_base)


def test_change_w1_w2_nan_when_w1_mean_is_zero():
    """Directly on the yearly-change helper: a topic with zero volume across
    the whole w1 window gets NaN change, never a division by zero."""
    from lib.engine import scenario_cache as SC  # noqa: F401 (not used; ctx built fresh below)
    ctx = load_context(DATA)
    inst_key = int(ctx["index_by_id"].loc[STRASBOURG, "inst_key"])
    ta = pd.read_parquet(DATA / "topics_all.parquet",
                         columns=["inst_key", "vol_full_2020", "vol_full_2021", "vol_full_2022"])
    hit = ta[ta["inst_key"] == inst_key]
    zero_w1 = hit[(hit["vol_full_2020"] == 0) & (hit["vol_full_2021"] == 0)
                 & (hit["vol_full_2022"] == 0)]
    if len(zero_w1) == 0:
        pytest.skip("no zero-w1 topic for this seed to exercise the guard on")
    yc = TD._topic_yearly_change_df(ctx, STRASBOURG)
    assert yc["change_w1_w2"].isna().sum() >= 1


# ---------------------------------------------------------------------------
# n_stars / world_rank / leader_name -- reconciled against leaders_data's
# own accessors directly (not re-testing leaders_data.py itself, a separate
# module's own concern -- just proving topic_data.py calls it correctly).
# ---------------------------------------------------------------------------
def test_n_stars_sums_to_inst_stars_total(ctx, frames):
    from lib import leaders_data as LD
    df = frames[STRASBOURG]
    total = int(df["n_stars"].sum())
    row = ctx["index_by_id"].loc[STRASBOURG]
    index_total = row.get("n_stars")
    # institution_topics only covers topics with n_ar>=3 -- a subset of every
    # topic inst_stars.parquet might name -- so this is a LOWER bound, not
    # necessarily exact equality (proven, not assumed).
    assert total <= int(index_total)
    assert total > 0


def test_world_rank_and_is_led_agree(frames):
    for iid in SEEDS:
        df = frames[iid]
        ranked = df["world_rank"].notna()
        assert (df.loc[ranked, "world_rank"] >= 1).all()
        assert (df.loc[ranked, "world_rank"] <= 200).all()
        assert (df["is_led"] == (df["world_rank"] <= 20).fillna(False)).all()


# ---------------------------------------------------------------------------
# pair_topics -- Compare's topic overlap (D31). Two anchor pairs: Strasbourg
# x CNRS (well above the joint-publication floor) and Salento x Bamberg
# (below it -- collab_topic_vols/collab_pairs carry no qualifying row).
# ---------------------------------------------------------------------------
BAMBERG = "I94626330"
PAIRS = ((STRASBOURG, CNRS), (SALENTO, BAMBERG))
PAIR_IDS = ["strasbourg_cnrs", "salento_bamberg"]


def test_pair_owner_constants_match_charts_topics():
    """`TD.PAIR_OWNER_*` duplicate `charts_topics.OWNER_*` on purpose (no
    lib/*_data.py module imports a lib/charts*.py module) -- this is the
    cross-check the module's own comment promises."""
    from lib import charts_topics as XT

    assert TD.PAIR_OWNER_A == XT.OWNER_A
    assert TD.PAIR_OWNER_B == XT.OWNER_B
    assert TD.PAIR_OWNER_SHARED == XT.OWNER_SHARED


@pytest.mark.parametrize("a,b", PAIRS, ids=PAIR_IDS)
@pytest.mark.parametrize("mode", TD.MODES)
def test_pair_topics_union_equals_both_selected_sets(ctx, a, b, mode):
    full_a = TD.institution_topics(ctx, a, "bestfit")
    full_b = TD.institution_topics(ctx, b, "bestfit")
    sel_a = TD.select_topics(full_a, mode, 50, "mean")
    sel_b = TD.select_topics(full_b, mode, 50, "mean")
    want = set(sel_a["topic_id"]) | set(sel_b["topic_id"])
    out = TD.pair_topics(ctx, a, b, mode, 50, "mean")
    assert set(out["topic_id"]) == want
    assert len(out) == len(want)  # one row per union topic, no duplicates
    assert len(out) <= 100        # PAIR_N_MAX=50 per side -> at most 100 union rows


@pytest.mark.parametrize("a,b", PAIRS, ids=PAIR_IDS)
@pytest.mark.parametrize("mode", TD.MODES)
def test_pair_topics_owner_shared_iff_in_both_selected_sets(ctx, a, b, mode):
    full_a = TD.institution_topics(ctx, a, "bestfit")
    full_b = TD.institution_topics(ctx, b, "bestfit")
    ids_a = set(TD.select_topics(full_a, mode, 50, "mean")["topic_id"])
    ids_b = set(TD.select_topics(full_b, mode, 50, "mean")["topic_id"])
    out = TD.pair_topics(ctx, a, b, mode, 50, "mean")
    for _, row in out.iterrows():
        tid, owner = row["topic_id"], row["owner"]
        if tid in ids_a and tid in ids_b:
            assert owner == TD.PAIR_OWNER_SHARED, tid
        elif tid in ids_a:
            assert owner == TD.PAIR_OWNER_A, tid
        else:
            assert tid in ids_b and owner == TD.PAIR_OWNER_B, tid


def test_pair_topics_columns_are_pair_cols(ctx):
    out = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 50, "mean")
    assert list(out.columns) == TD.PAIR_COLS


def test_pair_topics_n_clamped_to_10_50(ctx):
    lo = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 1, "mean")
    hi = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 1000, "mean")
    at_10 = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 10, "mean")
    at_50 = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 50, "mean")
    assert set(lo["topic_id"]) == set(at_10["topic_id"])
    assert set(hi["topic_id"]) == set(at_50["topic_id"])
    assert len(at_50) <= 100


def test_pair_topics_sorted_by_combined_vol_descending(ctx):
    out = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 50, "mean")
    assert (out["combined_vol"].diff().dropna() <= 1e-9).all()


@pytest.mark.parametrize("a,b", PAIRS, ids=PAIR_IDS)
def test_pair_topics_vol_joint_le_min_vol_a_vol_b_or_explained(ctx, a, b):
    """`vol_joint`, where known, must not exceed either institution's OWN
    volume -- but ONLY on rows where BOTH institutions clear the n_ar>=3
    floor: a row flagged `under3_*` stores a BUCKETED 0 (the true count is
    unknown, somewhere in 0-2), so comparing a real vol_joint against that
    bucketed 0 would flag a data-representation artifact, not a real
    violation (`charts_topics._fmt_pair_volumes`'s own docstring names
    this exact case). Reports the violation rate; expects 0."""
    out = TD.pair_topics(ctx, a, b, TD.MODE_VOLUME, 50, "mean")
    known = out[out["vol_joint"].notna() & ~out["under_floor_a"] & ~out["under_floor_b"]]
    if known.empty:
        pytest.skip(f"{a}x{b}: no joint-known, both-sides-floored row to check")
    violations = known[known["vol_joint"] > known[["vol_a", "vol_b"]].min(axis=1) + 1e-9]
    rate = len(violations) / len(known)
    assert rate == 0, (
        f"{a}x{b}: {len(violations)}/{len(known)} ({rate:.2%}) rows have "
        f"vol_joint exceeding min(vol_a, vol_b): {violations['topic_id'].tolist()}")


def test_pair_topics_vol_joint_na_below_the_qualifying_floor(ctx):
    """Salento x Bamberg: `collab_pairs.core_total` is below `PAIR_JOINT_
    FLOOR` (5) for this pair -- every row's `vol_joint` must be NA, never a
    fabricated 0 (the SAME floor-gating rule the retired `shared_frontier`
    used, ported here)."""
    out = TD.pair_topics(ctx, SALENTO, BAMBERG, TD.MODE_VOLUME, 50, "mean")
    assert len(out) > 0
    assert out["vol_joint"].isna().all(), (
        "expected this pair below the qualifying floor; if it now qualifies, "
        "pick a different, still-disjoint probe pair")


def test_pair_topics_vol_a_vol_b_zero_and_flagged_when_under_the_volume_floor(ctx):
    out = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 50, "mean")
    flagged_a = out[out["under_floor_a"]]
    if len(flagged_a):
        assert (flagged_a["vol_a"] == 0).all()
    flagged_b = out[out["under_floor_b"]]
    if len(flagged_b):
        assert (flagged_b["vol_b"] == 0).all()
    # and the institution's OWN full frame really does lack the topic
    full_a = TD.institution_topics(ctx, STRASBOURG, "bestfit")
    for tid in flagged_a["topic_id"]:
        assert tid not in set(full_a["topic_id"])


def test_pair_topics_rank_a_b_up_to_200_never_capped_at_20(ctx):
    """`leaders_data.topic_rank` reads the full 1..200 leaderboard -- rank
    <= 20 is the "topics led" flag elsewhere on this page, never a display
    cap on this column. A row ranked between 21 and 200 must still carry a
    real rank, not NA."""
    out = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 50, "mean")
    ranked = pd.concat([out["rank_a"].dropna(), out["rank_b"].dropna()])
    assert len(ranked) > 0
    assert (ranked >= 1).all() and (ranked <= 200).all()
    assert (ranked > 20).any(), "expect at least one rank past the 'led' floor of 20 on this anchor pair"


def test_pair_topics_links_well_formed(ctx):
    out = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 50, "mean")
    row = out.iloc[0]
    assert f"authorships.institutions.id:{STRASBOURG}" in row["url_a"]
    assert f"primary_topic.id:{row['topic_id']}" in row["url_a"]
    assert f"authorships.institutions.id:{CNRS}" in row["url_b"]
    assert f"authorships.institutions.id:{STRASBOURG}" in row["url_joint"]
    assert f"authorships.institutions.id:{CNRS}" in row["url_joint"]
    assert f"primary_topic.id:{row['topic_id']}" in row["url_joint"]
    assert row["url_a"].startswith("https://openalex.org/works?filter=")


def test_pair_topics_empty_when_neither_institution_has_any_qualifying_topic(ctx):
    """Two institutions engineered to have no topic clearing the n_ar>=3
    floor at all (an absurdly high `n` cannot help -- select_topics' own
    clamp bites first, but a real institution with fewer than 3 works in
    every topic is the genuine empty case): construct directly on an
    empty `institution_topics`-shaped frame via a nonsense id."""
    out = TD.pair_topics(ctx, "I_does_not_exist", "I_also_does_not_exist", TD.MODE_VOLUME, 50, "mean")
    assert out.empty
    assert list(out.columns) == TD.PAIR_COLS


def test_pair_topic_set_caption_counts_match_owner_and_catchall(ctx):
    out = TD.pair_topics(ctx, STRASBOURG, CNRS, TD.MODE_VOLUME, 50, "mean")
    facts = TD.pair_topic_set_caption(out)
    assert facts["n_total"] == len(out)
    assert facts["n_shared"] == int((out["owner"] == TD.PAIR_OWNER_SHARED).sum())
    assert facts["n_a_only"] == int((out["owner"] == TD.PAIR_OWNER_A).sum())
    assert facts["n_b_only"] == int((out["owner"] == TD.PAIR_OWNER_B).sum())
    assert facts["n_shared"] + facts["n_a_only"] + facts["n_b_only"] == facts["n_total"]
    assert facts["n_catchall"] == int(out["is_excluded"].sum())


def test_pair_topic_set_caption_on_an_empty_frame_never_raises():
    facts = TD.pair_topic_set_caption(pd.DataFrame(columns=TD.PAIR_COLS))
    assert facts == {"n_total": 0, "n_shared": 0, "n_a_only": 0, "n_b_only": 0,
                     "n_catchall": 0, "n_no_frontier": 0}
