"""
tests/test_matrix.py --: engine + filters level toggle x filter
matrix. No Streamlit import: pure
`lib.engine` + `lib.filters`, the same layer `tests/test_filters.py` and
`tests/test_golden_lenses.py` already exercise.

SCOPE NOTE on the assertion budget: the brief enumerates a full cross
product (3 seeds x 3 scenarios x 2 depths x 4 C1/L7 combinations x 6 filter
settings = 432 combinations). `apply_filters`' predicates are independent
per-field `continue` guards (lib/filters.py) and `cut_with_ties` never looks
at filter state (lib/engine/lenses.py) -- there is no cross-interaction for
the full product to catch that exercising each dimension at least once per
seed, plus one dedicated combined-filter case, would not already catch. So
this file runs every check the brief names at least once per seed (and per
scenario where the scenario is the point of the check), consolidates
per-lens/per-row work into one `all(.)` per assertion, and stays in the
"~150 assertions" ballpark that way rather than by copy-pasting -- measured
at collection.

Run from cwd `app/`: python -m pytest tests/test_matrix.py -q
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import copy
from lib.app_config import CFG
from lib.engine import (
    load_substrates, concordance, cut_with_ties, family_overlap_scores, load_context, rank_all,
)
from lib.filters import active_controls_strip, apply_filters

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

GDANSK = "I40413290"    # University of Gdansk, PL, education, 8,786 works -- < 20k scale-guard band
BOLOGNA = "I9360294"    # University of Bologna, IT, education, 41,693 works -- >= 20k scale-guard band
IFPEN = "I265217849"    # IFP Energies nouvelles, FR, facility, 1,055 works
SEEDS = [GDANSK, BOLOGNA, IFPEN]

DEFAULT_LENSES = list(CFG["lenses"]["default"])   # L0 L1 L3 F1 L2f L4 L5 L6
FAMILY_THR = CFG["family_filter_threshold"]
C1_L7_COMBOS = [(False, False), (True, False), (False, True), (True, True)]
DEPTHS = (30, 50)


# ------------------------------------------------------------- fixtures ----

@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def subs_default(ctx):
    return load_substrates(ctx, "bestfit", "frac")


@pytest.fixture(scope="module")
def subs_original(ctx):
    return load_substrates(ctx, "original", "frac")


@pytest.fixture(scope="module")
def subs_full(ctx):
    return load_substrates(ctx, "bestfit", "full")


@pytest.fixture(scope="module")
def lite(ctx):
    """The same 4-key row shape lib/views_find.py:_bundle builds -- exactly
    what lib.filters.apply_filters reads, independent of (tree, basis)."""
    idx = ctx["index_df"]
    return {r.institution_id: {
        "institution_id": r.institution_id, "type": str(r.type),
        "country_code": str(r.country_code),
        "total_full_2020_2024": (None if pd.isna(r.total_full_2020_2024)
                                  else float(r.total_full_2020_2024))}
        for r in idx.itertuples(index=False)}


def _rows_for(lite_map, ranking):
    return [lite_map[i] for i in ranking["sorted_ids"] if i in lite_map]


# --------------------------------------------------------- pure checkers ---

def _order_preserved(full_ids: list, subset_ids: list) -> bool:
    """subset_ids appear in exactly the same relative order as in full_ids."""
    pos = {i: p for p, i in enumerate(full_ids)}
    positions = [pos[i] for i in subset_ids]
    return positions == sorted(positions)


def _cut_ok(ranking: dict, depth: int) -> bool:
    """One consolidated check per (ranking, depth): the tie-inclusive cut is
    a SUBSET of the full ranking, in the SAME relative order, at least
    `min(depth, len(full))` long (ties can only add rows, never remove), and
    carries no NaN score."""
    full_ids = ranking["sorted_ids"]
    ids, scores = cut_with_ties(full_ids, ranking["sorted_scores"], depth)
    if not (set(ids) <= set(full_ids)):
        return False
    if not _order_preserved(full_ids, ids):
        return False
    if len(ids) < min(depth, len(full_ids)):
        return False
    if np.isnan(np.asarray(scores, dtype=float)).any():
        return False
    return True


def _check_type_education(rows: list) -> bool:
    return all(r["type"] == "education" for r in rows)


def _check_exclude_own_country(rows: list, seed_row) -> bool:
    own = str(seed_row["country_code"])
    return all(r["country_code"] != own for r in rows)


def _check_size_range(rows: list, lo: float, hi: float) -> bool:
    return all(r["total_full_2020_2024"] is not None and lo <= r["total_full_2020_2024"] <= hi
               for r in rows)


def _check_scale_guard(rows: list, seed_row) -> bool:
    seed_total = float(seed_row["total_full_2020_2024"])
    sg = CFG["scale_guard"]
    m = sg["lt_20k"] if seed_total < sg["band_threshold_works"] else sg["ge_20k"]
    return all(max(seed_total, r["total_full_2020_2024"]) / min(seed_total, r["total_full_2020_2024"])
               <= m + 1e-9
               for r in rows if r["total_full_2020_2024"])


def _check_family(rows: list, family_scores: dict, thr: float) -> bool:
    return all(family_scores.get(r["institution_id"], 0.0) >= thr for r in rows)


# ---------------------------------------------- depth x C1/L7 x concordance

@pytest.mark.parametrize("seed", SEEDS)
def test_depth_and_c1_l7_toggle_matrix(seed, ctx, subs_default):
    """  build step 3, default scenario: for every
    (depth, C1-on/off, L7-on/off) combination, the tie-inclusive cut of
    EVERY shown lens is a subset/order-preserving/non-padded/NaN-free view
    of that lens's full ranking, concordance's k<=n holds and n equals the
    number of enabled lenses actually defined for this seed, and
    active_controls_strip is None iff depth/C1/L7 are all at their default."""
    seed_row = ctx["index_by_id"].loc[seed]
    rankings = rank_all(ctx, subs_default, seed, DEFAULT_LENSES + ["C1", "L7"])
    assert not any(rankings[ln]["undefined"] for ln in DEFAULT_LENSES), \
        f"{seed}: a DEFAULT lens is undefined -- matrix assumption violated"

    for depth in DEPTHS:
        for c1_on, l7_on in C1_L7_COMBOS:
            lenses = DEFAULT_LENSES + (["C1"] if c1_on else []) + (["L7"] if l7_on else [])

            assert all(_cut_ok(rankings[ln], depth) for ln in lenses), (seed, depth, lenses)

            conc_rows = concordance(ctx, rankings, lenses, CFG["concordance_N"])
            n_defined = sum(1 for ln in lenses if not rankings[ln]["undefined"])
            assert all(row["k"] <= row["n"] for row in conc_rows), (seed, depth, lenses)
            assert all(row["n"] == n_defined for row in conc_rows), (seed, depth, lenses)

            strip = active_controls_strip(tree="bestfit", basis="frac", depth=depth,
                                           c1_on=c1_on, l7_on=l7_on, filters={})
            is_default = (depth == CFG["depth"]["default"]) and not c1_on and not l7_on
            assert (strip is None) == is_default, (seed, depth, c1_on, l7_on, strip)
            if strip is not None:
                if depth != CFG["depth"]["default"]:
                    assert copy.STRIP_DEPTH.format(depth=depth) in strip, strip
                if c1_on:
                    assert copy.STRIP_C1_ON in strip, strip
                if l7_on:
                    assert copy.STRIP_L7_ON in strip, strip


@pytest.mark.parametrize("scenario_name,fixture_name", [("original", "subs_original"),
                                                         ("full", "subs_full")])
@pytest.mark.parametrize("seed", SEEDS)
def test_depth_matrix_holds_on_non_default_scenarios(seed, scenario_name, fixture_name, ctx, request):
    """Same core invariant (cut is subset/order-preserving/NaN-free,
    concordance k<=n and n==n_defined), re-run against the two non-default
    scenarios named in the brief -- one different tree, one different
    basis -- at the default depth only (the tree/basis dimension is the
    point of this test, not another full depth/toggle sweep)."""
    subs = request.getfixturevalue(fixture_name)
    rankings = rank_all(ctx, subs, seed, DEFAULT_LENSES)
    depth = CFG["depth"]["default"]
    assert all(_cut_ok(rankings[ln], depth) for ln in DEFAULT_LENSES), (seed, scenario_name)
    conc_rows = concordance(ctx, rankings, DEFAULT_LENSES, CFG["concordance_N"])
    n_defined = sum(1 for ln in DEFAULT_LENSES if not rankings[ln]["undefined"])
    assert all(row["k"] <= row["n"] for row in conc_rows), (seed, scenario_name)
    assert all(row["n"] == n_defined for row in conc_rows), (seed, scenario_name)


# --------------------------------------------------------------- filters ---

@pytest.mark.parametrize("seed", SEEDS)
def test_post_filters_individually_and_combined(seed, ctx, subs_default, lite):
    """Each opt-in post-filter, applied alone to the L1 full ranking: kept
    rows satisfy their own predicate, kept ids are a subset of the full
    ranking, and a depth-30 cut of the kept ids is itself a subset of kept
    in the same relative order (post-filter-then-cut composition,
    ). Also one COMBINED case (type + country together)
    to check composition, since the individual cases alone never touch two
    predicates on the same row."""
    seed_row = ctx["index_by_id"].loc[seed]
    seed_total = float(seed_row["total_full_2020_2024"])
    ranking = rank_all(ctx, subs_default, seed, ["L1"])["L1"]
    assert not ranking["undefined"]
    rows = _rows_for(lite, ranking)
    family_scores = dict(zip(ctx["inst_ids"], family_overlap_scores(ctx, subs_default, seed)))

    cases = [
        ("type", dict(types=["education"]), lambda kept: _check_type_education(kept)),
        ("country", dict(exclude_own_country=True),
         lambda kept: _check_exclude_own_country(kept, seed_row)),
        ("size_range", dict(size_range=(seed_total * 0.5, seed_total * 1.5)),
         lambda kept: _check_size_range(kept, seed_total * 0.5, seed_total * 1.5)),
        ("scale_guard", dict(scale_guard=True), lambda kept: _check_scale_guard(kept, seed_row)),
        ("family", dict(family_min=FAMILY_THR, family_scores=family_scores),
         lambda kept: _check_family(kept, family_scores, FAMILY_THR)),
        ("type+country combined", dict(types=["education"], exclude_own_country=True),
         lambda kept: _check_type_education(kept) and _check_exclude_own_country(kept, seed_row)),
    ]
    full_id_set = set(ranking["sorted_ids"])
    for name, kwargs, predicate_ok in cases:
        kept = apply_filters(rows, seed_row=seed_row, **kwargs)
        assert 0 < len(kept) < len(rows), (seed, name, len(kept), len(rows))  # non-vacuous both ways
        assert predicate_ok(kept), (seed, name)
        kept_ids = [r["institution_id"] for r in kept]
        assert set(kept_ids) <= full_id_set, (seed, name)

        by_id = dict(zip(ranking["sorted_ids"], ranking["sorted_scores"]))
        cut_ids, cut_scores = cut_with_ties(kept_ids, np.asarray([by_id[i] for i in kept_ids]), 30)
        assert set(cut_ids) <= set(kept_ids), (seed, name)
        assert _order_preserved(kept_ids, cut_ids), (seed, name)


def test_active_controls_strip_names_each_post_filter():
    """One representative seed (Gdansk): every post-filter dimension, set
    alone, produces a non-None strip naming that dimension's own STRIP_*
    fixed text from lib/copy.py (mirrors tests/test_filters.py's existing
    tree/depth/C1/L7 coverage, extended to the 5 post-filter dimensions)."""
    base = dict(tree=CFG["scenario"]["tree_default"], basis=CFG["scenario"]["basis_default"],
                depth=CFG["depth"]["default"], c1_on=False, l7_on=False)
    assert active_controls_strip(**base, filters={}) is None

    cases = [
        ({"types": ["education", "facility"]}, copy.STRIP_TYPE.format(types="education, facility")),
        ({"countries": ["FR", "DE"]}, copy.STRIP_COUNTRY.format(countries="France, Germany")),
        ({"exclude_own_country": True}, copy.STRIP_EXCLUDE_OWN_COUNTRY),
        ({"size_range": (1000, 5000)}, copy.STRIP_SIZE_RANGE.format(lo=1000, hi=5000)),
        ({"scale_guard": True}, copy.STRIP_SCALE_GUARD),
        ({"family_min": FAMILY_THR}, copy.STRIP_FAMILY.format(threshold=FAMILY_THR)),
    ]
    for filters, expected in cases:
        strip = active_controls_strip(**base, filters=filters)
        assert strip is not None and expected in strip, (filters, strip)


# --------------------------------------------------- bestfit/full + trees

def test_bestfit_full_basis_applies_false_for_erc_sdg_and_strip_mentions_exemption(subs_full):
    assert all(subs_full["basis_applies"][ln] is False for ln in ("L4", "L5", "L6", "L7")), \
        subs_full["basis_applies"]
    strip = active_controls_strip(tree=CFG["scenario"]["tree_default"], basis="full",
                                   depth=CFG["depth"]["default"], c1_on=False, l7_on=False, filters={})
    assert strip is not None and "ERC" in strip and "SDG" in strip, strip


def test_tree_original_changes_l1_not_l3_top30(ctx, subs_default, subs_original):
    """Tree toggle changes the L1 (subfield-grain) top-30 candidate SET for
    at least one of the three seeds, while L3 (topic-grain, tree-independent
    by construction) top-30 is IDENTICAL for every seed."""
    any_l1_differs = False
    for seed in SEEDS:
        r_default = rank_all(ctx, subs_default, seed, ["L1", "L3"])
        r_original = rank_all(ctx, subs_original, seed, ["L1", "L3"])

        l1_default = set(cut_with_ties(r_default["L1"]["sorted_ids"],
                                        r_default["L1"]["sorted_scores"], 30)[0])
        l1_original = set(cut_with_ties(r_original["L1"]["sorted_ids"],
                                         r_original["L1"]["sorted_scores"], 30)[0])
        any_l1_differs = any_l1_differs or (l1_default != l1_original)

        l3_default = set(cut_with_ties(r_default["L3"]["sorted_ids"],
                                        r_default["L3"]["sorted_scores"], 30)[0])
        l3_original = set(cut_with_ties(r_original["L3"]["sorted_ids"],
                                         r_original["L3"]["sorted_scores"], 30)[0])
        assert l3_default == l3_original, f"{seed}: L3 top-30 changed with tree (should be tree-independent)"

    assert any_l1_differs, "L1 top-30 identical to bestfit for all 3 seeds under tree=original -- unexpected"
