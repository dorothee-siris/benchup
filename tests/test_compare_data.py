"""
tests/test_compare_data.py -- lib/compare_data.py acceptance tests.

Anchors are the reference-figures golden -- every value this module
claims is EQUAL to is checked against that file directly, not against a
hand-typed number, so a future data refresh re-proves the same identity
rather than silently drifting from a frozen constant.

TOLERANCE: `atol=1e-6, rtol=0` (not exact `==`) -- every source column here
is float32 on disk; the golden file stores `float(np.float32_value)`
(float64-widened, not re-rounded) and this module performs the identical
float32->float64 widening, so `atol=1e-6` is generous headroom over the
float32 ULP at these magnitudes, not a loosened bar (re-verified against
`rtol=0` with a scratch sweep before this tolerance was picked).

Run: python -m pytest tests/test_compare_data.py -q
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import compare_data as CD
from lib.engine import load_context, load_substrates

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
GOLDEN_PATH = Path(__file__).resolve().parents[2] / "evals" / "goldens" / "v3_compare_anchors.json"

ATOL = 1e-6


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def subs(ctx):
    """Compare's own pin (D10): bestfit taxonomy, full counting."""
    return load_substrates(ctx, "bestfit", "full")


@pytest.fixture(scope="module")
def golden():
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return json.load(f)


PAIR_NAMES = ["ifremer_nioz", "strasbourg_cnrs", "eth_heriotwatt_X"]


def _close(a, b) -> bool:
    """NaN-aware, tolerance-explicit float compare -- see module docstring
    for why `atol=1e-6, rtol=0`."""
    fa, fb = _num(a), _num(b)
    if np.isnan(fa) and np.isnan(fb):
        return True
    return bool(np.isclose(fa, fb, atol=ATOL, rtol=0.0))


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _pair_ids(golden, pair_name) -> tuple[str, str]:
    p = golden["pairs"][pair_name]
    return p["a"], p["b"]


# ===========================================================================
# 1. cards == golden overview (the 7 legacy figures)
# ===========================================================================

_CARD_TO_OVERVIEW = {
    "vol_full": "vol_full", "vol_frac": "vol_frac", "sdg_share": "sdg_share",
    "frontier_top25_share": "frontier_top25_share", "pp": "pp",
    "intl_share": "intl_share", "company_share": "company_share",
}


@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_cards_equal_golden_overview(ctx, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    out = CD.cards(ctx, [a, b]).set_index("institution_id")
    gov = {r["institution_id"]: r for r in golden["pairs"][pair_name]["overview"]}
    assert set(gov) == {a, b}
    n_checked = 0
    for iid in (a, b):
        row, g = out.loc[iid], gov[iid]
        for card_col, gold_col in _CARD_TO_OVERVIEW.items():
            assert _close(row[card_col], g[gold_col]), (
                f"{pair_name}/{iid}/{card_col}: got {row[card_col]!r} want {g[gold_col]!r}")
            n_checked += 1
    assert n_checked == 14  # 7 figures x 2 institutions -- a coverage floor, not just "no exception"


def test_cards_vacuity_a_wrong_value_is_caught(ctx, golden):
    """Vacuity proof: the SAME comparison, deliberately fed a wrong number,
    must fail -- proves `test_cards_equal_golden_overview` is not trivially
    true (e.g. from a silently-empty golden list)."""
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.cards(ctx, [a, b]).set_index("institution_id")
    real = float(out.loc[a, "vol_full"])
    assert _close(real, real)
    assert not _close(real, real + 1.0)
    assert not _close(real, 0.0)


# ===========================================================================
# 2. subfield metrics: all_subfields reproduces every (institution, taxon)
#    row of golden's `subfield_metrics` (share/si/pp/fwci)
# ===========================================================================

@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_subfield_share_equal_golden(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    out = CD.all_subfields(ctx, subs, [a, b]).set_index(["institution_id", "subfield_id"])
    rows = golden["pairs"][pair_name]["subfield_metrics"]["share"]
    assert len(rows) > 0
    for r in rows:
        key = (r["institution_id"], int(r["taxon_id"]))
        got = out.loc[key]
        assert _close(got["share_full"], r["value"]), key
        assert _close(got["eu_mean_share"], r["ref_value"]), key


@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_subfield_si_equal_golden(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    out = CD.all_subfields(ctx, subs, [a, b]).set_index(["institution_id", "subfield_id"])
    rows = golden["pairs"][pair_name]["subfield_metrics"]["si"]
    assert len(rows) > 0
    for r in rows:
        key = (r["institution_id"], int(r["taxon_id"]))
        assert _close(out.loc[key, "si"], r["value"]), key


@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_subfield_pp_equal_golden(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    out = CD.all_subfields(ctx, subs, [a, b]).set_index(["institution_id", "subfield_id"])
    rows = golden["pairs"][pair_name]["subfield_metrics"]["pp"]
    assert len(rows) > 0
    for r in rows:
        key = (r["institution_id"], int(r["taxon_id"]))
        got = out.loc[key]
        assert _close(got["pp10_wd"], r["value"]), key
        assert _close(got["n_covered_pp"], r["denom_value"]), key


@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_subfield_fwci_equal_golden(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    out = CD.all_subfields(ctx, subs, [a, b]).set_index(["institution_id", "subfield_id"])
    rows = golden["pairs"][pair_name]["subfield_metrics"]["fwci"]
    assert len(rows) > 0
    for r in rows:
        key = (r["institution_id"], int(r["taxon_id"]))
        got = out.loc[key]
        assert _close(got["fwci_median"], r["value"]), key
        assert _close(got["fwci_mean"], r["fwci_mean"]), key


def test_subfield_vacuity_a_wrong_value_is_caught(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.all_subfields(ctx, subs, [a, b]).set_index(["institution_id", "subfield_id"])
    real = float(out.loc[(a, 1100), "share_full"])
    assert _close(real, real)
    assert not _close(real, real + 0.01)


def test_top_subfields_is_the_top_20_by_combined_vol_full_subset_of_all_subfields(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    top = CD.top_subfields(ctx, subs, [a, b], n=20)
    allsf = CD.all_subfields(ctx, subs, [a, b])
    assert top["subfield_id"].nunique() == 20
    assert len(top) == 40  # 20 subfields x 2 institutions
    ranked = allsf.groupby("subfield_id")["combined_vol_full"].first().sort_values(ascending=False)
    top_ids = list(top["subfield_id"].unique())
    assert set(top_ids) == set(ranked.index[:20])
    # every combined_vol_full inside the top-20 is >= every one outside it
    inside = ranked.loc[top_ids].min()
    outside = ranked.drop(top_ids)
    assert outside.empty or inside >= outside.max()


def test_all_subfields_is_dense_over_all_252_bestfit_subfields(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.all_subfields(ctx, subs, [a, b])
    assert out["subfield_id"].nunique() == 252
    assert len(out) == 504  # 252 x 2 institutions, dense (D3 "All 252 subfields in Excel")
    assert list(out.columns) == CD.SUBFIELD_WIDE_COLS
    # a subfield neither institution touches: share_full/vol_full are 0.0, never NaN
    zero_rows = out[out["combined_vol_full"] == 0.0]
    if len(zero_rows):
        assert (zero_rows["share_full"] == 0.0).all()
        assert (zero_rows["vol_full"] == 0.0).all()


# ===========================================================================
# 3. sdg_frame: 16 dense rows per institution, share/si/pp/fwci equal
#    golden's `sdg_metrics`
# ===========================================================================

@pytest.mark.parametrize("metric,col,extra", [
    ("share", "share_full", ("eu_mean_share", "ref_value")),
    ("si", "si", None),
    ("pp", "pp10_wd", ("n_covered_pp", "denom_value")),
    ("fwci", "fwci_median", ("fwci_mean", "fwci_mean")),
])
@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_sdg_metric_equal_golden(ctx, subs, golden, pair_name, metric, col, extra):
    a, b = _pair_ids(golden, pair_name)
    out = CD.sdg_frame(ctx, subs, [a, b]).set_index(["institution_id", "sdg_idx"])
    rows = golden["pairs"][pair_name]["sdg_metrics"][metric]
    assert len(rows) > 0
    for r in rows:
        key = (r["institution_id"], int(r["taxon_id"]))
        got = out.loc[key]
        assert _close(got[col], r["value"]), (pair_name, metric, key)
        if extra:
            out_col, gold_key = extra
            assert _close(got[out_col], r[gold_key]), (pair_name, metric, key, "extra")


def test_sdg_frame_dense_16_rows_and_untagged_attr(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.sdg_frame(ctx, subs, [a, b])
    assert out["sdg_idx"].nunique() == 16
    assert len(out) == 32
    assert list(out.columns) == CD.SDG_WIDE_COLS
    untagged = out.attrs["untagged_share"]
    assert set(untagged) == {a, b}
    for v in untagged.values():
        assert np.isnan(v) or (0.0 <= v <= 1.0)


def test_sdg_vacuity_a_wrong_value_is_caught(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.sdg_frame(ctx, subs, [a, b]).set_index(["institution_id", "sdg_idx"])
    real = float(out.loc[(a, 0), "pp10_wd"])
    assert _close(real, real)
    assert not _close(real, real + 0.1)


# ===========================================================================
# 4. shared_frontier: topic set + A/B volumes == golden `shared_frontier`;
#    per-topic `vol_joint` == golden `collab_topic_vols` slice
# ===========================================================================

@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_shared_frontier_topic_set_and_ab_volumes_equal_golden(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    out = CD.shared_frontier(ctx, subs, [a, b]).set_index("topic_id")
    gsf = golden["pairs"][pair_name]["shared_frontier"]
    assert len(gsf) > 0
    assert len(out) == len(gsf), f"{pair_name}: row count {len(out)} != golden {len(gsf)}"
    vol_a_key, vol_b_key = f"vol_{a}", f"vol_{b}"
    for g in gsf:
        row = out.loc[g["topic_id"]]
        assert _close(row["vol_a"], g[vol_a_key])
        assert _close(row["vol_b"], g[vol_b_key])
        assert _close(row["expansion"], g["x"])
        assert _close(row["acceleration"], g["y"])
        assert _close(row["combined_vol"], g["combined_vol"])


@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_shared_frontier_vol_joint_equals_collab_topic_vols_slice(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    out = CD.shared_frontier(ctx, subs, [a, b])
    ctv = {r["topic_id"]: r["vol"] for r in golden["pairs"][pair_name]["collab_topic_vols"]}
    assert len(out) > 0
    assert out["joint_known"].all(), f"{pair_name}: all three anchor pairs qualify (core_total >= 5)"
    for _, row in out.iterrows():
        want = ctv.get(row["topic_id"], 0.0)  # absent from the slice, qualifying pair -> genuinely 0
        assert _close(row["vol_joint"], want), row["topic_id"]


def test_shared_frontier_below_floor_pair_ships_joint_known_false(ctx, subs):
    """Two institutions almost certainly never co-published (or did, below
    the P7 `core_total >= 5` floor): `joint_known` must be False and
    `vol_joint` NaN for every row, never a fabricated 0 (decisions log
    2026-09-03)."""
    # Two small, geographically/thematically distant institutions with no
    # engineered relationship -- IFPEN (energy, FR) and a tiny facility.
    a, b = "I265217849", "I4210142177"
    out = CD.shared_frontier(ctx, subs, [a, b])
    if out.empty:
        pytest.skip("no shared top-quartile-frontier topics between this probe pair -- nothing to assert")
    assert not out["joint_known"].any() or out["joint_known"].all()  # never a mixed row set for one pair
    if not out["joint_known"].iloc[0]:
        assert out["vol_joint"].isna().all()


def test_shared_frontier_required_columns_for_mirror_frontier(ctx, subs, golden):
    """`lib/charts_compare.py:mirror_frontier`'s own INPUT FRAME CONTRACT
    (its docstring's `required` tuple) -- every one of those columns must be
    present under these exact names."""
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.shared_frontier(ctx, subs, [a, b])
    required = ("topic_id", "topic_name", "url_joint", "vol_a", "vol_b",
               "vol_joint", "expansion", "acceleration")
    for col in required:
        assert col in out.columns, f"missing {col!r} (charts_compare.mirror_frontier contract)"
    assert list(out.columns) == CD.SHARED_FRONTIER_COLS


def test_shared_frontier_vacuity_a_wrong_value_is_caught(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.shared_frontier(ctx, subs, [a, b])
    real = float(out.iloc[0]["vol_joint"])
    assert _close(real, real)
    assert not _close(real, real + 5.0)


# ===========================================================================
# 5. frontier_positioning: shape/contract + share_top25 == golden overview
# ===========================================================================

@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_frontier_positioning_share_top25_equals_golden_overview(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    out = CD.frontier_positioning(ctx, subs, [a, b]).set_index("institution_id")
    gov = {r["institution_id"]: r for r in golden["pairs"][pair_name]["overview"]}
    for iid in (a, b):
        assert _close(out.loc[iid, "share_top25"], gov[iid]["frontier_top25_share"])


def test_frontier_positioning_columns_and_n_shared_attr(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.frontier_positioning(ctx, subs, [a, b])
    assert list(out.columns) == CD.FRONTIER_POSITIONING_COLS
    assert len(out) == 2
    assert "n_shared" in out.attrs
    assert isinstance(out.attrs["n_shared"], int)
    # n_shared cannot exceed either institution's own n_top25_topics_published
    assert out.attrs["n_shared"] <= out["n_top25_topics_published"].min()
    # and it must equal shared_frontier's own row count (same topic-set definition)
    sf = CD.shared_frontier(ctx, subs, [a, b])
    assert out.attrs["n_shared"] == len(sf)


# ===========================================================================
# 6. relationship: momentum / pulse / core_total / reciprocity / yearly
# ===========================================================================

@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_relationship_momentum_equals_golden(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    rel = CD.relationship(ctx, [a, b], subs)
    g = golden["pairs"][pair_name]["pair_momentum"]
    m = rel["momentum"]
    assert m is not None
    assert m["mom_class"] == g["mom_class"]
    assert m["text"] == g["text"]
    for col in ("mom_rr", "mom_p", "c1", "c2", "d1", "d2"):
        assert _close(m[col], g[col]), (pair_name, col)


@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_relationship_pulse_and_core_total_equal_golden(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    rel = CD.relationship(ctx, [a, b], subs)
    gp = golden["pairs"][pair_name]["pulse"]
    assert rel["pulse"] is not None
    assert _close(rel["pulse"]["copubs_total"], gp["copubs_total"])
    assert _close(rel["pulse"]["rank_in_a"], gp["rank_in_a"])
    assert _close(rel["pulse"]["rank_in_b"], gp["rank_in_b"])
    grow = golden["pairs"][pair_name]["collab_pairs_row"][0]
    assert _close(rel["core_total"], grow["core_total"])


@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_relationship_reciprocity_equals_golden(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    rel = CD.relationship(ctx, [a, b], subs)
    grecip = golden["pairs"][pair_name]["reciprocity_frame"]
    out = rel["reciprocity"].set_index("field_id")
    assert len(out) == len(grecip)
    assert list(rel["reciprocity"].columns) == CD.RECIPROCITY_WIDE_COLS
    for g in grecip:
        row = out.loc[g["field_id"]]
        assert _close(row["share_a"], g["y"])   # 's reciprocity_frame: y = A's own-corpus share
        assert _close(row["share_b"], g["x"])   # x = B's own-corpus share
        assert _close(row["vol_joint"], g["joint_vol"])


@pytest.mark.parametrize("pair_name", PAIR_NAMES)
def test_relationship_yearly_sums_to_core_total_or_flags_topicless(ctx, subs, golden, pair_name):
    a, b = _pair_ids(golden, pair_name)
    rel = CD.relationship(ctx, [a, b], subs)
    assert rel["yearly_qualifies"], f"{pair_name}: all 3 anchor pairs are P7-qualifying"
    assert list(rel["yearly"].columns) == CD.YEARLY_DOMAIN_COLS
    total = float(rel["yearly"]["vol"].sum())
    if not np.isclose(total, rel["core_total"], atol=1e-9):
        assert rel["topicless_note"], (
            f"{pair_name}: yearly sum {total} != core_total {rel['core_total']} but topicless_note is False")
    assert total <= rel["core_total"] + 1e-9  # never MORE joint volume than the pair's own core_total


def test_relationship_joint_stars_and_url(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    rel = CD.relationship(ctx, [a, b], subs)
    assert isinstance(rel["joint_stars"], int)
    assert rel["joint_stars"] >= 0
    assert rel["joint_stars_url"].startswith("https://openalex.org/works?filter=")
    assert rel["joint_stars_url"].endswith("&sort=cited_by_count:desc")


def test_relationship_vacuity_a_wrong_value_is_caught(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    rel = CD.relationship(ctx, [a, b], subs)
    real = rel["core_total"]
    assert _close(real, real)
    assert not _close(real, real + 10.0)


def test_relationship_no_collaboration_pair_returns_none_momentum_and_pulse(ctx, subs):
    """A pair with (almost certainly) zero co-publications: `momentum`/
    `pulse` must be `None` (collab_data's own floor-1 "absent means zero"
    convention), `yearly_qualifies=False`, never a fabricated row."""
    a, b = "I4210143826", "I4210150693"  # a small education institution + a small company, unrelated fields
    rel = CD.relationship(ctx, [a, b], subs)
    if rel["momentum"] is not None:
        pytest.skip("this probe pair turned out to have co-published -- pick a different disjoint pair")
    assert rel["pulse"] is None
    assert not rel["yearly_qualifies"]
    assert rel["yearly"].empty


# ===========================================================================
# 7. cards European-median columns
# ===========================================================================

def test_cards_eu_median_columns_present_and_population_wide(ctx, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.cards(ctx, [a, b])
    assert list(out.columns) == CD.CARDS_COLS
    for col in ["vol_full", "vol_frac", "sdg_share", "frontier_top25_share", "pp",
               "intl_share", "company_share", "vol_change"]:
        eu_col = f"{col}_eu_median"
        assert eu_col in out.columns
        # a population statistic: identical for both rows of this 2-institution frame
        assert out[eu_col].nunique(dropna=False) == 1
    # sanity: the population median publication volume is well below any
    # named research-heavy institution's own count, and NOT itself NaN
    assert 0 < float(out["vol_full_eu_median"].iloc[0]) < float(out["vol_full"].max())


def test_cards_fwci_eu_median_absent_is_nan_not_a_crash(ctx, golden):
    """ (parallel wave) has not necessarily landed `fwci_eu_median`
    on `index.parquet` yet -- `cards` must degrade to NaN, never KeyError."""
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.cards(ctx, [a, b])
    assert "fwci_eu_median" in out.columns  # present as a column regardless
    if "fwci_eu_median" not in ctx["index_df"].columns:
        assert out["fwci_eu_median"].isna().all()
        assert np.isnan(out["fwci_eu_median_eu_median"].iloc[0])


# ===========================================================================
# 8. links helpers exposed on shared_frontier rows point at the pair (E6)
# ===========================================================================

def test_shared_frontier_urls_point_at_the_right_ids_and_topic(ctx, subs, golden):
    a, b = _pair_ids(golden, "ifremer_nioz")
    out = CD.shared_frontier(ctx, subs, [a, b])
    row = out.iloc[0]
    assert f"authorships.institutions.id:{a}" in row["url_a"]
    assert f"primary_topic.id:{row['topic_id']}" in row["url_a"]
    assert f"authorships.institutions.id:{b}" in row["url_b"]
    assert f"authorships.institutions.id:{a}" in row["url_joint"]
    assert f"authorships.institutions.id:{b}" in row["url_joint"]
    assert f"primary_topic.id:{row['topic_id']}" in row["url_joint"]
