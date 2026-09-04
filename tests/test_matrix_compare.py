"""
tests/test_matrix_compare.py -- Compare-page coverage matrix (lib/compare_data.py).

Compare is pinned to bestfit/full -- there is no tree/basis matrix for the
page itself to sweep. What this file covers instead: the "one scenario per
cell, cheap enough to run every cell every time" idea, applied to
`lib.compare_data`'s OWN pure functions (never the page) over every
institution PAIR with reference ground truth (the 3 golden pairs in
tests/golden/reference/compare_pairs.json) plus two additional, non-golden
pairs chosen to widen coverage (a small/small pair and a cross-type pair)
-- so every builder is exercised on 5 real pairs, not just the 3 anchor
pairs `test_compare_data.py` value-checks in depth.

Run: python -m pytest tests/test_matrix_compare.py -q
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
GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "reference" / "compare_pairs.json"


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def subs(ctx):
    return load_substrates(ctx, "bestfit", "full")  # Compare's ONE pin -- no other scenario exists for this page


def _golden_pairs() -> list[tuple[str, str]]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        g = json.load(f)
    return [(p["a"], p["b"]) for p in g["pairs"].values()]


# Two additional, non-golden pairs (from the 6 named seeds also used in the
#   README) -- widens the sweep beyond the 3 golden pairs
# with exact ground truth without inventing new anchor numbers.
_EXTRA_PAIRS = [
    ("I4210143826", "I142910587"),   # two education institutions, one very small (<2000 works)
    ("I4210150693", "I4210131494"),  # a company and a government institution -- cross-type
]

ALL_PAIRS = _golden_pairs() + _EXTRA_PAIRS
PAIR_IDS = [f"{a}_{b}" for a, b in ALL_PAIRS]


@pytest.mark.parametrize("a,b", ALL_PAIRS, ids=PAIR_IDS)
def test_every_c1_builder_runs_and_agrees_internally(ctx, subs, a, b):
    """One cell = one pair: every public compare_data builder must run with no
    exception and satisfy the cross-builder invariants that hold for ANY
    pair (not just the 3 with golden ground truth)."""
    ids = [a, b]

    cards = CD.cards(ctx, ids)
    assert len(cards) == 2
    assert list(cards.columns) == CD.CARDS_COLS
    assert set(cards["institution_id"]) == set(ids)

    top = CD.top_subfields(ctx, subs, ids, n=20)
    allsf = CD.all_subfields(ctx, subs, ids)
    assert allsf["subfield_id"].nunique() == 252
    assert len(allsf) == 504
    assert top["subfield_id"].nunique() <= 20
    assert set(top["subfield_id"]) <= set(allsf["subfield_id"])
    # share_full sums to <= 1 + eps per institution over the WHOLE 252 (never > 1)
    sums = allsf.groupby("institution_id", observed=True)["share_full"].sum()
    assert (sums <= 1.0 + 1e-6).all(), sums.to_dict()

    sdg = CD.sdg_frame(ctx, subs, ids)
    assert len(sdg) == 32
    assert sdg["sdg_idx"].nunique() == 16
    assert set(sdg.attrs["untagged_share"]) == set(ids)

    # frontier_positioning/shared_frontier are DELETED, absorbed into
    # Compare's topic overlap (`lib.topic_data.pair_topics`, not
    # `compare_data.py` any more) -- this cell's own coverage of that area
    # moves to the new function, same "every builder, every pair" spirit.
    from lib import topic_data as TD

    ov = TD.pair_topics(ctx, ids[0], ids[1], TD.MODE_VOLUME, 50, "mean")
    assert list(ov.columns) == TD.PAIR_COLS
    assert len(ov) <= 100
    if len(ov):
        assert np.isclose(ov["combined_vol"].to_numpy(), (ov["vol_a"] + ov["vol_b"]).to_numpy()).all()
        # sorted by combined_vol descending (the topic-overlap row-order contract)
        assert (ov["combined_vol"].diff().dropna() <= 1e-9).all()
        assert set(ov["owner"]) <= {TD.PAIR_OWNER_A, TD.PAIR_OWNER_B, TD.PAIR_OWNER_SHARED}

    rel = CD.relationship(ctx, ids, subs)
    assert set(rel) == {"a", "b", "momentum", "pulse", "yearly", "yearly_qualifies",
                        "core_total", "topicless_note", "reciprocity", "joint_stars", "joint_stars_url"}
    assert list(rel["reciprocity"].columns) == CD.RECIPROCITY_WIDE_COLS
    assert list(rel["yearly"].columns) == CD.YEARLY_DOMAIN_COLS
    if rel["yearly_qualifies"]:
        assert float(rel["yearly"]["vol"].sum()) <= rel["core_total"] + 1e-6
    else:
        assert rel["yearly"].empty
    assert isinstance(rel["joint_stars"], int) and rel["joint_stars"] >= 0


def test_fields_long_still_exported_for_collab_data(ctx, subs):
    """`lib/collab_data.py:reciprocity_frame` imports `compare_data.
    fields_long` by name -- a
    regression here would silently break the Relationship block's
    reciprocity chart. Import-path check, not just a call-and-hope."""
    import lib.collab_data as COL
    assert COL.CD is CD  # collab_data's own `from. import compare_data as CD`
    a, b = ALL_PAIRS[0]
    df = CD.fields_long(ctx, subs, [a, b])
    assert list(df.columns) == CD.FIELDS_LONG_COLS
    # exercised end to end through the real consumer, not just a direct call
    recip = COL.reciprocity_frame(ctx, subs, a, b)
    assert set(recip.columns) == set(COL.RECIPROCITY_COLS)  # fwci/pp10/stars/rank additions


def test_deleted_matrix_machinery_is_gone():
    """`metric_frame`/`METRICS`/`LEVELS`/`UNAVAILABLE_REASON`, ERC frames,
    the dynamics section, the pooled frontier scatter, `coverage`,
    `impact_subfields` and `top_shared_subfields` are DELETED from this
    module (the code stays only in the archive). `state.COLLAB_CAP` (this
    file's own OLD reference) is also deleted -- checked here, not just
    asserted in prose, so a re-add of any of these surfaces is caught at
    collection time."""
    deleted_names = [
        "metric_frame", "metric_frame_available", "METRICS", "LEVELS", "METRIC_FRAME_COLS",
        "erc_long", "frontier_mix", "frontier_points", "frontier_pooled", "_frontier_pool_frame",
        "FRONTIER_POOLS", "QUADRANTS", "NOT_SCORED", "UNAVAILABLE_REASON",
        "impact_index", "impact_subfields", "coverage", "top_shared_subfields",
        "fwci_ref_label", "FWCI_REF_LABEL", "pp_ref_label", "PP_REF_LABEL",
        "overview",  # renamed to `cards`
    ]
    for name in deleted_names:
        assert not hasattr(CD, name), f"{name} should have been deleted from compare_data.py"

    import lib.state as state
    assert not hasattr(state, "COLLAB_CAP")
