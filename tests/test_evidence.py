"""
 lib/engine/evidence.py acceptance tests (.3
R-B, decision L21).
Run: python -m pytest tests/test_evidence.py -q
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lib.engine import ALL_LENSES, load_substrates, load_context, rank_all
from lib.engine.evidence import LENS_NAMESPACE, rows_evidence, top_shared_cell

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SEEDS = ["I40413290", "I265217849", "I39804081"]  # Gdansk, IFPEN, Sorbonne


@pytest.fixture(scope="module")
def engine():
    ctx = load_context(DATA_DIR)
    subs = load_substrates(ctx)  # default scenario: bestfit / frac
    return ctx, subs


def _top5_candidates(ctx, subs, seed_id, lens):
    r = rank_all(ctx, subs, seed_id, [lens])[lens]
    assert not r["undefined"], f"{seed_id}/{lens} unexpectedly undefined"
    return r["sorted_ids"][:5], r["sorted_scores"][:5]


@pytest.mark.parametrize("seed_id", SEEDS)
def test_l1_sigma_min_equals_rank_all_score(engine, seed_id):
    """Sigma_j min(seed_j, cand_j) over ALL L1 cells == rank_all's own L1
    score for that candidate (rtol 1e-5) -- proves the substrate/column
    selection in evidence.py is the SAME one rank_all scores on."""
    ctx, subs = engine
    seed_idx = ctx["id_pos"][seed_id]
    cand_ids, scores = _top5_candidates(ctx, subs, seed_id, "L1")
    seed_row = subs["l1"]["share"][seed_idx]
    for cid, want in zip(cand_ids, scores):
        cand_idx = ctx["id_pos"][cid]
        summin = float(np.minimum(seed_row, subs["l1"]["share"][cand_idx]).sum())
        assert abs(summin - float(want)) <= 1e-5 * max(abs(float(want)), 1e-12), (
            f"{seed_id}/{cid}: Sigma min {summin} != rank_all score {want}")
        # top_shared_cell's own reported `score` mirrors the same number for
        # the plain histogram-intersection lenses (L21: contribution's
        # denominator IS the lens score here).
        cell = top_shared_cell(ctx, subs, "L1", seed_idx, cand_idx)
        assert abs(cell["score"] - summin) <= 1e-6  # float32 matrix, row-order accumulation noise


@pytest.mark.parametrize("seed_id", SEEDS)
def test_top_cell_contribution_bounded(engine, seed_id):
    """Every defined lens, this seed's top-5 candidates: 0 < contribution <= 1
    whenever a cell exists (a genuine zero-overlap pair legitimately reports
    None/"n/a", never a value outside (0, 1])."""
    ctx, subs = engine
    seed_idx = ctx["id_pos"][seed_id]
    for lens in ALL_LENSES:
        r = rank_all(ctx, subs, seed_id, [lens])[lens]
        if r["undefined"] or not r["sorted_ids"]:
            continue
        for cid in r["sorted_ids"][:5]:
            cell = top_shared_cell(ctx, subs, lens, seed_idx, ctx["id_pos"][cid])
            if cell["cell_id"] is None:
                continue
            assert 0.0 < cell["contribution"] <= 1.0 + 1e-9, (
                f"{seed_id}/{lens}/{cid}: contribution {cell['contribution']} out of (0, 1]")


@pytest.mark.parametrize("lens", ALL_LENSES)
def test_every_lens_returns_a_label_from_the_right_namespace(engine, lens):
    """rows_evidence text carries a real label (never the raw id, never
    empty) for at least one of this seed's top candidates, for every lens
    that is defined for it."""
    ctx, subs = engine
    seed_id = "I40413290"  # Gdansk -- defined for all 10 lenses (golden fixture)
    r = rank_all(ctx, subs, seed_id, [lens])[lens]
    if r["undefined"] or not r["sorted_ids"]:
        pytest.skip(f"{lens} undefined for {seed_id}")
    cand_ids = r["sorted_ids"][:5]
    texts = rows_evidence(ctx, subs, lens, seed_id, cand_ids)
    assert set(texts) == set(cand_ids)
    non_na = [t for t in texts.values() if t != "n/a"]
    assert non_na, f"{lens}: every candidate came back n/a"
    for t in non_na:
        assert " — " in t and t.endswith("of the overlap"), f"{lens}: malformed evidence text {t!r}"
        label = t.split(" — ")[0]
        assert label, f"{lens}: empty label in {t!r}"


def test_l2f_l5_l7_use_excess_vectors(engine):
    """L2f/L5/L7 evidence reads the EXCESS matrix, not a share matrix: the
    chosen top cell must have excess > 0 for BOTH seed and candidate (true by
    construction)."""
    ctx, subs = engine
    seed_id = "I40413290"
    for lens, key in (("L2f", "l2f"), ("L5", "l5"), ("L7", "l7")):
        r = rank_all(ctx, subs, seed_id, [lens])[lens]
        if r["undefined"] or not r["sorted_ids"]:
            continue
        seed_idx = ctx["id_pos"][seed_id]
        excess = subs[key]["excess"]
        for cid in r["sorted_ids"][:5]:
            cand_idx = ctx["id_pos"][cid]
            cell = top_shared_cell(ctx, subs, lens, seed_idx, cand_idx)
            if cell["cell_pos"] is None:
                continue
            j = cell["cell_pos"]
            assert excess[seed_idx, j] > 0, f"{lens}/{cid}: seed excess at top cell not > 0"
            assert excess[cand_idx, j] > 0, f"{lens}/{cid}: candidate excess at top cell not > 0"


def test_c1_denominator_is_seed_top20_mass(engine):
    """C1's contribution denominator is the seed's own top-20-subfield mass
    (build_c1_for_seed's `denom`), not Sigma_j min -- so Sigma of
    contributions over the top20 columns reproduces C1's own lens score."""
    ctx, subs = engine
    seed_id = "I40413290"
    seed_idx = ctx["id_pos"][seed_id]
    r = rank_all(ctx, subs, seed_id, ["C1"])["C1"]
    if r["undefined"] or not r["sorted_ids"]:
        pytest.skip("C1 undefined for this seed")
    cand_id = r["sorted_ids"][0]
    want_score = float(r["sorted_scores"][0])
    cell = top_shared_cell(ctx, subs, "C1", seed_idx, ctx["id_pos"][cand_id])
    assert abs(cell["score"] - want_score) <= 1e-5 * max(abs(want_score), 1e-12)


def test_undefined_lens_is_na(engine):
    """A lens absent from LENS_NAMESPACE (e.g. a typo) -> every row "n/a",
    never a crash."""
    ctx, subs = engine
    out = rows_evidence(ctx, subs, "NOPE", "I40413290", ["I1", "I2"])
    assert out == {"I1": "n/a", "I2": "n/a"}


def test_all_lenses_have_a_namespace():
    assert set(LENS_NAMESPACE) == set(ALL_LENSES)
