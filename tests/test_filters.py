"""
 filters.py acceptance tests.
Run: python -m pytest tests/test_filters.py -q
"""
from __future__ import annotations

from pathlib import Path

import pytest

from lib.app_config import CFG
from lib.engine import build_rows, load_context, load_substrates, rank_all
from lib import copy
from lib.filters import active_controls_strip, apply_filters, explain_empty

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def engine():
    ctx = load_context(DATA_DIR)
    subs = load_substrates(ctx)
    return ctx, subs


def _rows_and_seed(engine_, seed_id, lens="L1", depth=50):
    ctx, subs = engine_
    r = rank_all(ctx, subs, seed_id, [lens])
    return build_rows(r[lens], ctx, depth), ctx["index_by_id"].loc[seed_id]


def test_exclude_own_country_removes_every_fr_row(engine):
    rows, seed_row = _rows_and_seed(engine, "I39804081", depth=50)  # Sorbonne Universite, FR
    out = apply_filters(rows, seed_row=seed_row, exclude_own_country=True)
    assert len(out) < len(rows)
    assert all(str(r["country_code"]) != "FR" for r in out)


def test_scale_guard_ratio_is_flat_three():
    """config.yaml's scale_guard is a single flat ratio -- the old
    two-tier size band and its own switchover threshold are gone."""
    assert CFG["scale_guard"] == {"ratio": 3}


def test_scale_guard_flat_ratio_below_old_20k_threshold(engine):
    rows, seed_row = _rows_and_seed(engine, "I40413290", depth=50)  # Gdansk, 8,786 works
    ratio = CFG["scale_guard"]["ratio"]
    out = apply_filters(rows, seed_row=seed_row, scale_guard=True)
    assert len(out) < len(rows)
    seed_total = float(seed_row["total_full_2020_2024"])
    for r in out:
        other = r["total_full_2020_2024"]
        assert max(seed_total, other) / min(seed_total, other) <= ratio + 1e-9


def test_scale_guard_flat_ratio_at_or_above_old_20k_threshold(engine):
    """Same ratio as the seed above -- proves the old size band (a
    stricter multiplier for the largest institutions) is gone: a seed on
    either side of that old switchover point is guarded identically."""
    rows, seed_row = _rows_and_seed(engine, "I9360294", depth=50)  # Bologna, 41,693 works
    ratio = CFG["scale_guard"]["ratio"]
    out = apply_filters(rows, seed_row=seed_row, scale_guard=True)
    assert len(out) < len(rows)
    seed_total = float(seed_row["total_full_2020_2024"])
    for r in out:
        other = r["total_full_2020_2024"]
        assert max(seed_total, other) / min(seed_total, other) <= ratio + 1e-9


def test_scale_guard_candidate_at_3_1x_removed_2_9x_kept_larger_candidate():
    seed_row = {"total_full_2020_2024": 10_000.0, "country_code": "XX"}
    rows = [
        {"total_full_2020_2024": 29_000.0, "institution_id": "under_2_9x"},  # 2.9x -> kept
        {"total_full_2020_2024": 31_000.0, "institution_id": "over_3_1x"},   # 3.1x -> removed
    ]
    out = apply_filters(rows, seed_row=seed_row, scale_guard=True)
    assert {r["institution_id"] for r in out} == {"under_2_9x"}


def test_scale_guard_symmetric_for_smaller_candidates():
    """The ratio test is max/min, so a candidate SMALLER than the seed by
    the same factor is guarded identically to one that is larger."""
    seed_row = {"total_full_2020_2024": 10_000.0, "country_code": "XX"}
    rows = [
        {"total_full_2020_2024": 10_000.0 / 2.9, "institution_id": "smaller_2_9x"},  # kept
        {"total_full_2020_2024": 10_000.0 / 3.1, "institution_id": "smaller_3_1x"},  # removed
    ]
    out = apply_filters(rows, seed_row=seed_row, scale_guard=True)
    assert {r["institution_id"] for r in out} == {"smaller_2_9x"}


def _defaults():
    return dict(tree=CFG["scenario"]["tree_default"], basis=CFG["scenario"]["basis_default"],
                depth=CFG["depth"]["default"], c1_on=False, l7_on=False, filters={})


def test_strip_is_none_at_all_defaults():
    assert active_controls_strip(**_defaults()) is None


@pytest.mark.parametrize("patch,expected_substr", [
    # `views_find._strip_tree` hands this function the DISPLAY label
    # for an off-default taxonomy, so the strip never prints "original".
    ({"tree": copy.TREE_LABELS["original"]}, copy.TREE_LABELS["original"]),
    # Depth is fixed at CFG["depth"]["max"] == CFG["depth"]["default"]
    # (50 == 50) -- there is no off-default depth left to name in the strip,
    # so that case is retired along with the radio that used to drive it.
    ({"c1_on": True}, "core-shape"),
    ({"l7_on": True}, "SDG-specialisation"),
])
def test_strip_names_each_off_default_dimension(patch, expected_substr):
    kwargs = _defaults()
    kwargs.update(patch)
    strip = active_controls_strip(**kwargs)
    assert strip is not None
    assert expected_substr in strip, strip


def test_strip_basis_full_mentions_erc_sdg_exemption():
    kwargs = _defaults()
    kwargs["basis"] = "full"
    strip = active_controls_strip(**kwargs)
    assert strip is not None and "ERC" in strip and "SDG" in strip, strip


def test_strip_names_active_post_filter():
    kwargs = _defaults()
    kwargs["filters"] = {"types": ["education", "facility"]}
    strip = active_controls_strip(**kwargs)
    assert strip is not None and "education" in strip and "facility" in strip, strip


def test_strip_country_shows_english_names_sorted_by_name():
    # .2 L22 / feedback #4: country codes -> names,
    # sorted by NAME (France < Germany < United Kingdom), not by ISO2 code
    # (DE < FR < GB).
    kwargs = _defaults()
    kwargs["filters"] = {"countries": ["GB", "FR", "DE"]}
    strip = active_controls_strip(**kwargs)
    assert strip is not None
    assert "France, Germany, United Kingdom" in strip, strip
    assert "GB" not in strip and "FR" not in strip and "DE" not in strip, strip


def test_explain_empty_names_both_size_filters():
    seed_row = {"display_name": "Test Seed University"}
    filters = {"size_range": (1000, 5000), "scale_guard": True}
    msg = explain_empty(filters, seed_row)
    assert "1000-5000" in msg, msg
    assert "scale guard" in msg, msg
    assert "Test Seed University" in msg, msg
