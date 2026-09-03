"""
Golden regression for `lib/engine`.

The 37 files in `tests/golden/lists/` are `evals/campaign_v2/gen_lists_v2.py`'s
own output -- the lists that were externally graded (519 peers, SPEC S0). The
engine must reproduce them exactly: same tie-inclusive top-50 per lens, same
scores to 6 dp, same undefined/reason, same concordance, same
aspirational-by-impact pool and order, same seed card.

Run from `app/`: python -m pytest tests/test_golden_lenses.py -q
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from lib.engine import (
    ALL_LENSES, GOLDEN_CONCORDANCE_LENSES, aspirational, catchall_811_share,
    concordance, cut_with_ties, load_context, load_substrates, rank_all, seed_card,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "lists"
GOLDEN_FILES = sorted(GOLDEN_DIR.glob("I*.json"))
DEPTH = 50
TOL = 1e-6

CARD_FIELDS = ["total_full_2020_2024", "hhi_subfield", "breadth_subfields", "catchall_811_share",
               "n_eligible_subfields_L2f", "shape_top3_fields", "top5_subfields_default_scenario"]


@pytest.fixture(scope="module")
def engine():
    ctx = load_context(DATA_DIR)
    subs = load_substrates(ctx)                         # default scenario: bestfit / frac
    return ctx, subs, catchall_811_share(ctx)


def _close(a, b, what):
    """`hhi_subfield`/`total_full_2020_2024`/etc. are read
    straight off index.parquet, now float32 (was float64) -- np.isclose-style
    combined tolerance (TOL absolute for the [0,1]-scale lens scores, a small
    relative term for larger-magnitude raw columns) absorbs the expected
    float32 rounding (e.g. hhi_subfield ~724: max abs diff ~1.6e-5, a ~2e-8
    relative error -- not a value change, a representation-precision one)."""
    assert a is not None and b is not None, f"{what}: {a!r} vs {b!r}"
    af, bf = float(a), float(b)
    tol = max(TOL, 1e-6 * max(abs(af), abs(bf)))
    assert abs(af - bf) <= tol, f"{what}: {a!r} != {b!r}"


def _same_shape_list(got, want, what):
    """shape_top3_fields / top5_subfields_default_scenario: same length, same
    ids in order, numeric members within TOL."""
    assert len(got) == len(want), f"{what}: {len(got)} entries vs {len(want)}"
    for i, (g, w) in enumerate(zip(got, want)):
        for k, v in w.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                _close(g[k], v, f"{what}[{i}].{k}")
            else:
                assert g[k] == v, f"{what}[{i}].{k}: {g[k]!r} != {v!r}"


assert len(GOLDEN_FILES) == 37, f"expected 37 golden seed files, found {len(GOLDEN_FILES)}"


@pytest.mark.parametrize("path", GOLDEN_FILES, ids=[p.stem for p in GOLDEN_FILES])
def test_golden_seed(engine, path):
    ctx, subs, catchall = engine
    gold = json.loads(path.read_text(encoding="utf-8"))
    iid = gold["institution_id"]
    rankings = rank_all(ctx, subs, iid, ALL_LENSES)

    # ---- (1) every lens: undefined/reason, then the tie-inclusive top-50 ----
    for lens in ALL_LENSES:
        g = gold["lenses"][lens]
        r = rankings[lens]
        assert r["undefined"] == g["undefined"], f"{iid}/{lens}: undefined {r['undefined']} != {g['undefined']}"
        assert r["reason"] == g["reason"], f"{iid}/{lens}: reason {r['reason']!r} != {g['reason']!r}"
        ids, scores = cut_with_ties(r["sorted_ids"], r["sorted_scores"], DEPTH)
        want_ids = [row["institution_id"] for row in g["rows"]]
        assert ids == want_ids, (
            f"{iid}/{lens}: top-{DEPTH} id sequence differs at position "
            f"{next((i for i, (a, b) in enumerate(zip(ids, want_ids)) if a != b), min(len(ids), len(want_ids)))} "
            f"({len(ids)} vs {len(want_ids)} rows)")
        for row, sc in zip(g["rows"], scores):
            _close(sc, row["lens_score"], f"{iid}/{lens}/{row['institution_id']} lens_score")

    # ---- (2) concordance, golden 7-lens set ----
    g_conc = gold["concordance"]
    # reference lists were generated at N=30; the app runs the same function at
    # CONCORDANCE_N -- this pins the algorithm, not the product setting.
    rows30 = concordance(ctx, rankings, GOLDEN_CONCORDANCE_LENSES, N=30)
    assert [r["institution_id"] for r in rows30] == g_conc["N30_top50_ids"], f"{iid}: concordance N=30 top-50 ids"
    rows20 = concordance(ctx, rankings, GOLDEN_CONCORDANCE_LENSES, N=20)
    want20 = g_conc["N20"]["rows"]
    assert [r["institution_id"] for r in rows20] == [r["institution_id"] for r in want20], f"{iid}: concordance N=20 ids"
    for got, want in zip(rows20, want20):
        assert got["k"] == want["k"], f"{iid}: concordance k for {want['institution_id']}"
        assert got["n"] == want["n"] == g_conc["n_lenses_defined"], f"{iid}: concordance n"
        assert got["hit_lenses"] == want["hit_lenses"], f"{iid}: hit_lenses for {want['institution_id']}"

    # ---- (3) aspirational-by-impact (L1 top-50 pool, kept in L1-overlap order) ----
    asp = aspirational(ctx, rankings["L1"], pool=DEPTH)
    want_asp = gold["aspirational"]["rows"]
    assert [r["institution_id"] for r in asp] == [r["institution_id"] for r in want_asp], f"{iid}: aspirational ids/order"
    for got, want in zip(asp, want_asp):
        for f in ("pp_top10_frac", "pp_ci_low", "pp_ci_high", "lens_score_L1_overlap"):
            _close(got[f], want[f], f"{iid}: aspirational {want['institution_id']}.{f}")

    # ---- (4) seed card ----
    card = seed_card(ctx, iid, subs, catchall)
    for f in CARD_FIELDS:
        if isinstance(gold["card"][f], list):
            _same_shape_list(card[f], gold["card"][f], f"{iid}: card.{f}")
        else:
            _close(card[f], gold["card"][f], f"{iid}: card.{f}")


def test_population_order_is_index_row_order(engine):
    """L14: the tie-break every assertion above relies on."""
    ctx, _subs, _c = engine
    assert ctx["inst_ids"] == ctx["index_df"]["institution_id"].tolist()
    assert ctx["index_df"]["inst_key"].is_monotonic_increasing
    assert ctx["index_df"]["institution_id"].is_monotonic_increasing
    assert np.array_equal(np.array([ctx["id_pos"][i] for i in ctx["inst_ids"]]), np.arange(ctx["n"]))
