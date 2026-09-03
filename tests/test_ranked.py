"""
Tests for `lib/ranked.py`.

Pure-function tests only (`format_rows`, `depth_caption`, `format_concordance`,
`concordance_caption`) -- no Streamlit server, run directly:
    python -m pytest tests/test_ranked.py -q
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from lib.app_config import CFG
from lib.engine import DEFAULT_LENSES, build_rows, concordance, load_context, load_substrates, rank_all
from lib.palette import NA_MARK
from lib.ranked import concordance_caption, depth_caption, format_concordance, format_rows

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SEED = "I40413290"  # University of Gdansk
DEPTH = 30
N = 30
WINDOW_START, WINDOW_END = CFG["window"]


@pytest.fixture(scope="module")
def engine():
    ctx = load_context(DATA_DIR)
    # V4 trim: `build_substrates` moved out of the app
    # package into `pipeline/21_scenario_substrates.py`; `load_substrates`
    # returns the identical dict from the precomputed `data/scenarios/` files
    # (same keys/dtypes/shapes -- `lib/engine/substrates.py`'s own docstring).
    subs = load_substrates(ctx)
    r = rank_all(ctx, subs, SEED)
    return ctx, r


@pytest.fixture(scope="module")
def l1_rows(engine):
    ctx, r = engine
    return build_rows(r["L1"], ctx, DEPTH, r)


def test_format_rows_row_count_and_ranks(l1_rows):
    df = format_rows(l1_rows, lens="L1", depth=DEPTH)
    assert len(df) >= DEPTH  # DEPTH rows, or more if ties extend the cut (never fewer)
    ranks = df["rank"].tolist()
    assert ranks[0] == 1
    # competition ranks: non-decreasing, gaps only where ties precede
    for prev, cur in zip(ranks, ranks[1:]):
        assert cur >= prev
    # gaps are only ever (number of rows tied at prev rank), never an arbitrary jump
    seen = {}
    for rk in ranks:
        seen[rk] = seen.get(rk, 0) + 1
    expected_next = 1
    for rk in sorted(seen):
        assert rk == expected_next, f"rank {rk} is not a valid competition rank position"
        expected_next = rk + seen[rk]


def test_format_rows_link_has_seed_free_id_and_window_years(l1_rows):
    #  (A10): the institution NAME column now carries the works URL
    # (a `#<urlencoded name>` fragment appended); the plain name is kept
    # alongside as `institution_name`.
    df = format_rows(l1_rows, lens="L1", depth=DEPTH)
    assert SEED not in df["institution_id"].tolist(), "self must be excluded (rank_all excludes seed)"
    for link, iid, name in zip(df["institution"], df["institution_id"], df["institution_name"]):
        assert iid in link
        assert f"{WINDOW_START}-{WINDOW_END}" in link
        assert "authorships.institutions.id:" in link
        assert link.split("#", 1)[1] != "", "the name fragment must not be empty"
        assert isinstance(name, str) and name


def test_format_rows_no_nan_score_and_str_type(l1_rows):
    # D9: `score` is now pre-scaled 0-100 (was
    # 0-1) so `ranked.pct_progress_column`'s printf format ("%.1f%%") renders
    # period-decimal regardless of host locale -- see `ranked._pct100`.
    df = format_rows(l1_rows, lens="L1", depth=DEPTH)
    assert df["score"].notna().all()
    assert df["score"].between(0, 100, inclusive="both").all()
    assert df["type"].map(lambda v: isinstance(v, str)).all()
    assert df["type"].dtype == object


def test_format_rows_no_badge_column(l1_rows):
    # .2 L22: badges live on the
    # seed profile header only, never in a table.
    df = format_rows(l1_rows, lens="L1", depth=DEPTH)
    assert "badge" not in df.columns


def test_format_rows_takes_no_badges_kwarg(l1_rows):
    with pytest.raises(TypeError):
        format_rows(l1_rows, lens="L1", depth=DEPTH, badges={})


def test_format_rows_has_two_size_columns(l1_rows):
    # L22: full AND fractional size, both thousands-formatted or NA_MARK.
    #  (A10): "institution_link" is gone -- "institution" itself now
    # carries the works URL (name-as-link), with the plain name kept as
    # "institution_name".
    df = format_rows(l1_rows, lens="L1", depth=DEPTH)
    assert list(df.columns) == ["rank", "institution", "institution_name", "country",
                                 "country_code", "type", "size_full", "size_frac", "score",
                                 "evidence", "rank_under", "institution_id"]
    for col in ("size_full", "size_frac"):
        for v in df[col]:
            assert v == NA_MARK or ("," in v or v.isdigit())


def test_format_rows_evidence_passthrough_and_na_default():
    row_with_text = {"institution_id": "I1", "rank": 1, "display_name": "Alpha U",
                      "country_code": "FR", "type": "education", "evidence_text": "Physics -- 42% of the overlap"}
    row_without_text = {"institution_id": "I2", "rank": 2, "display_name": "Beta U",
                        "country_code": "DE", "type": "education"}
    row_empty_text = {"institution_id": "I3", "rank": 3, "display_name": "Gamma U",
                      "country_code": "IT", "type": "education", "evidence_text": ""}
    df = format_rows([row_with_text, row_without_text, row_empty_text], lens="L1", depth=3)
    by_id = df.set_index("institution_id")["evidence"]
    assert by_id["I1"] == "Physics -- 42% of the overlap"
    assert by_id["I2"] == NA_MARK
    assert by_id["I3"] == NA_MARK  # empty string counts as absent, never a blank cell


def test_format_rows_country_is_english_name_code_kept_hidden():
    row = {"institution_id": "I1", "rank": 1, "display_name": "Alpha U",
           "country_code": "GB", "type": "education"}
    df = format_rows([row], lens="L1", depth=1)
    assert df.iloc[0]["country"] == "United Kingdom"
    assert df.iloc[0]["country_code"] == "GB"


def test_depth_caption_parametric():
    cap = depth_caption(30, 7556, 30)
    assert "30" in cap
    assert "7556" in cap
    other_digits = [c for c in cap if c.isdigit()]
    # every digit present must belong to one of the two numbers passed in
    allowed = set("30") | set("7556")
    assert set(other_digits) <= allowed
    # and both full numbers appear as substrings, not just their digits scattered
    assert "top 30" in cap
    assert "of 7556" in cap


def test_depth_caption_with_ties():
    cap = depth_caption(32, 7556, 30, n_tied_extra=2)
    assert "32" in cap and "7556" in cap and "30" in cap and "2" in cap


@pytest.fixture(scope="module")
def conc_rows(engine):
    ctx, r = engine
    return concordance(ctx, r, DEFAULT_LENSES, N)


def test_format_concordance_k_le_n_and_hit_list_len(conc_rows):
    df = format_concordance(conc_rows, lenses=DEFAULT_LENSES, N=N)
    assert len(df) > 0
    n_lenses = len(DEFAULT_LENSES)
    for _, row in df.iterrows():
        assert 1 <= row["k"] <= row["n"] <= n_lenses
        hit_list = [h for h in row["hit_lenses"].split(", ") if h]
        assert len(hit_list) == row["k"]


def test_format_concordance_two_size_columns_and_country_name(conc_rows):
    # L22: concordance table also carries both size bases and the country
    # NAME, with the raw code kept hidden.
    df = format_concordance(conc_rows, lenses=DEFAULT_LENSES, N=N)
    assert "badge" not in df.columns
    assert {"size_full", "size_frac", "country", "country_code"} <= set(df.columns)
    assert df["country"].map(lambda v: isinstance(v, str) and len(v) > 2).all()


def test_concordance_caption_parametric():
    cap = concordance_caption(8, 30, 50)
    assert "8" in cap and "30" in cap and "50" in cap
