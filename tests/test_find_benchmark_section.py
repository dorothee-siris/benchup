"""
tests/test_find_benchmark_section.py -- the Find page's
benchmark section rework.

Five claims, one section each:

  1. LENS DISPLAY CODES. The renumbered L0.L7 (defaults, tab
     order) + L8/L9 (optional C1/L7) mapping is a bijection onto exactly the
     ten internal `ALL_LENSES` ids, and every `LENS_DISPLAY_NAMES` sentence
     opens with its own new code.

  2. POOL EXCLUSION (A6). `ctx["pool_excluded_positions"]` -- built by
     `engine.load_context` from an index `pool_excluded` column when one
     exists, empty otherwise -- is read at ONE chokepoint (`lenses.rank_all`'s
     shared `_emit`) that every lens, `concordance` and `aspirational`
     inherit from. Proven on REAL data (three real seeds, the real Romanian
     Ministry id). The wiring test (`test_load_context_reads_pool_excluded_
     column_when_present`) still injects the flag onto a fake index, engine-
     level, independent of any deploy. The two acceptance tests below were
     originally written to inject the flag onto `ctx` because PC had not yet
     deployed `pool_excluded` to `app/data/index.parquet`; PC's deploy has
     since landed it (3 ids: the Romanian Ministry + the Shell UK / INESC
     duplicate rows, `data/overrides/*`), so re-cut both
     to assert against the REAL deployed column instead of a synthetic one.

  3. ASPIRATIONAL MODE B. `aspirational_frontier` reorders the SAME
     L1 pool by F1 score (never drops or adds a candidate), ties keep the
     pool's own L1 order, and a real seed whose base ranking returns no
     row (ETH Zurich) still returns rows from it on this
     snapshot.

  4. NAME-AS-LINK (A10). `ranked.works_link_named` embeds the display name as
     a URL fragment for `LinkColumn`'s per-cell `display_text=r"#(.*)$"`
     regex to extract, and `format_rows`/`format_concordance` no longer carry
     a separate `institution_link` column.

  5. LENS-CODE TEXT. `ranked._rank_under_text` prints the
     DISPLAY code (not the internal id) for the L1/L3 cross-reference.

Run from cwd `app/`: python -m pytest tests/test_find_benchmark_section.py -q
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from lib import copy
from lib.engine import (
    ALL_LENSES, CONCORDANCE_N, DEFAULT_LENSES, aspirational, aspirational_frontier, load_substrates,
    concordance, load_context, rank_all,
)
from lib.ranked import _rank_under_text, works_link_named

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

ROMANIAN_MINISTRY = "I4210092262"           # pool_excluded upstream
PROBE_SEEDS = ["I40413290", "I103320735", "I76903346"]   # Gdansk + two large-index institutions
ETH_ZURICH = "I35440088"                    # base-ranking-empty seed


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def subs(ctx):
    return load_substrates(ctx)


# ------------------------------------------- 1. lens display codes

def test_display_code_is_a_bijection_onto_all_lenses():
    code = copy.LENS_DISPLAY_CODE
    assert set(code.keys()) == set(ALL_LENSES)
    assert len(set(code.values())) == len(code), "two internal lenses must never share a display code"
    assert set(code.values()) == {f"L{i}" for i in range(len(ALL_LENSES))}


def test_default_lenses_renumbered_in_tab_order_then_c1_then_l7():
    code = copy.LENS_DISPLAY_CODE
    expected_order = list(DEFAULT_LENSES) + ["C1", "L7"]
    for i, lens in enumerate(expected_order):
        assert code[lens] == f"L{i}", f"{lens} should display as L{i}, got {code[lens]}"


def test_display_names_open_with_their_own_new_code():
    for lens, disp in copy.LENS_DISPLAY_CODE.items():
        assert copy.LENS_DISPLAY_NAMES[lens].startswith(disp), (
            f"LENS_DISPLAY_NAMES[{lens!r}] does not open with its display code {disp!r}: "
            f"{copy.LENS_DISPLAY_NAMES[lens]!r}")


def test_display_codes_pass_the_copy_digit_ban():
    # LENS_DISPLAY_CODE/LENS_DISPLAY_NAMES live inside copy.FIND, already
    # covered by copy.scan_for_digit_violations; this just re-asserts PASS
    # after recent edits, isolated from the rest of the file.
    bad = copy.scan_for_digit_violations()
    assert bad == [], bad


# --------------------------------------------------- 2. pool exclusion (A6)

def test_load_context_reads_pool_excluded_column_when_present(tmp_path, monkeypatch):
    """Engine-level proof of the WIRING (`load_context` -> `pool_excluded_positions`),
    independent of whether `app/data/index.parquet` has shipped the column yet."""
    import pandas as pd

    real_index = pd.read_parquet(DATA_DIR / "index.parquet")
    fake_index = real_index.copy()
    fake_index["pool_excluded"] = False
    flagged_id = fake_index["institution_id"].iloc[7]
    fake_index.loc[fake_index["institution_id"] == flagged_id, "pool_excluded"] = True

    fake_dir = tmp_path / "data"
    fake_dir.mkdir()
    fake_index.to_parquet(fake_dir / "index.parquet")
    for name in ("topics_dim.parquet", "erc.parquet", "sdg.parquet", "fields.parquet",
                "subfields.parquet", "topics_all.parquet"):
        import shutil
        shutil.copy(DATA_DIR / name, fake_dir / name)

    fake_ctx = load_context(fake_dir)
    assert fake_ctx["pool_excluded_positions"] == frozenset({fake_ctx["id_pos"][flagged_id]})


POOL_EXCLUDED_IDS = {ROMANIAN_MINISTRY, "I4210164678", "I4210125590"}   # deployed: Romanian
                                                                        # Ministry + the Shell/INESC duplicates


def test_pool_excluded_positions_reflects_the_deployed_column(ctx):
    """A re-check: the deploy has landed `pool_excluded` on
    `app/data/index.parquet` (it had not, when an earlier pass wrote this
    file -- see the superseded docstring above). Exactly the 3 flagged ids
    (Romanian Ministry + the Shell UK / INESC duplicate rows)."""
    want = frozenset(ctx["id_pos"][i] for i in POOL_EXCLUDED_IDS)
    assert ctx["pool_excluded_positions"] == want


def test_romanian_ministry_excluded_from_every_lens_list_for_three_probe_seeds(ctx, subs):
    """A6 acceptance, verbatim, re-run against the NOW-DEPLOYED real data
    (superseding FC's synthetic-injection version, which ran before PC's
    deploy): I4210092262 appears in NO lens list (nor the concordance, nor V0
    aspirational) for three probe seeds where it previously could surface.
    `before` simulates the pre-deploy engine (pool_excluded_positions
    cleared) to prove these seeds are a real fixture -- i.e. the id WOULD
    surface without the exclusion; `after` is the REAL, deployed ctx, no
    injection needed any more."""
    target = ROMANIAN_MINISTRY

    def _hits(ctx_):
        hits = []
        for seed in PROBE_SEEDS:
            r = rank_all(ctx_, subs, seed)
            for lens in ALL_LENSES:
                if target in r[lens]["sorted_ids"]:
                    hits.append((seed, lens))
            if any(target == row["institution_id"]
                   for row in concordance(ctx_, r, DEFAULT_LENSES, CONCORDANCE_N)):
                hits.append((seed, "concordance"))
            l1 = r["L1"]
            if not l1["undefined"] and any(row["institution_id"] == target
                                           for row in aspirational(ctx_, l1)):
                hits.append((seed, "aspirational"))
        return hits

    ctx_before = dict(ctx)
    ctx_before["pool_excluded_positions"] = frozenset()
    before = _hits(ctx_before)
    assert before, ("fixture assumption failed: the Romanian Ministry id never surfaced for these "
                    "three seeds even without the exclusion -- pick different probe seeds")

    after = _hits(ctx)
    assert after == [], f"still surfaces after exclusion: {after}"


def test_pool_exclusion_never_touches_the_seeds_own_row(ctx, subs):
    """A6: exclusion is a CANDIDATE-pool filter, never a population change
    a probe seed itself must still rank normally (this ctx dict copy changes
    nothing about the substrates or the index)."""
    ctx_excluded = dict(ctx)
    ctx_excluded["pool_excluded_positions"] = frozenset({ctx["id_pos"][ROMANIAN_MINISTRY]})
    for seed in PROBE_SEEDS:
        r = rank_all(ctx_excluded, subs, seed)
        assert not r["L1"]["undefined"]
        assert len(r["L1"]["sorted_ids"]) > 0


# --------------------------------------------- 3. aspirational mode B

def test_aspirational_frontier_reorders_the_same_pool_it_is_given(ctx, subs):
    seed = "I40413290"
    r = rank_all(ctx, subs, seed)
    l1 = r["L1"]
    from lib.engine.lenses import cut_with_ties, DEPTH
    pool_ids, _ = cut_with_ties(l1["sorted_ids"], l1["sorted_scores"], DEPTH)
    af = aspirational_frontier(ctx, l1, r.get("F1"))
    assert set(row["institution_id"] for row in af) == set(pool_ids), \
        "A-frontier must be a REORDERING of the L1 pool, never a different candidate set"


def test_aspirational_frontier_sorted_by_f1_score_desc_ties_keep_l1_order(ctx, subs):
    seed = "I40413290"
    r = rank_all(ctx, subs, seed)
    af = aspirational_frontier(ctx, r["L1"], r.get("F1"))
    scores = [row["lens_score_F1_overlap"] for row in af]
    assert scores == sorted(scores, reverse=True)
    # ties at the F1-absent floor (score 0.0) must be in the pool's own
    # L1-overlap order: their rank ordinal in `af` matches their rank ordinal
    # among all-zero-F1 rows drawn from cut_with_ties, which is itself sorted
    # by L1 score descending -- so L1 overlap must be non-increasing across
    # any run of equal F1 scores.
    for a, b in zip(af, af[1:]):
        if a["lens_score_F1_overlap"] == b["lens_score_F1_overlap"]:
            assert a["lens_score_L1_overlap"] >= b["lens_score_L1_overlap"]


def test_aspirational_frontier_excludes_the_pool_excluded_id_for_free(ctx, subs):
    """The A6 chokepoint lives in `rank_all`'s L1 branch; `aspirational_frontier`
    cuts its pool from `l1_ranking["sorted_ids"]`, so the exclusion is
    inherited -- no separate filter is written in `aspirational_frontier`."""
    seed = "I40413290"
    ctx_excluded = dict(ctx)
    ctx_excluded["pool_excluded_positions"] = frozenset({ctx["id_pos"][ROMANIAN_MINISTRY]})
    r = rank_all(ctx_excluded, subs, seed)
    af = aspirational_frontier(ctx_excluded, r["L1"], r.get("F1"))
    assert ROMANIAN_MINISTRY not in {row["institution_id"] for row in af}


def test_v0_empty_seed_has_a_populated_frontier_fallback(ctx, subs):
    """ETH Zurich: the base ranking (`aspirational`)
    returns no row on this snapshot, and the mode-B fallback must not be
    empty too (else there is nothing for `_render_aspirational` to fall back
    to and the seed would need a different probe)."""
    assert ETH_ZURICH in ctx["id_pos"]
    r = rank_all(ctx, subs, ETH_ZURICH)
    l1 = r["L1"]
    assert not l1["undefined"]
    v0 = aspirational(ctx, l1)
    assert v0 == [], "fixture assumption failed: ETH Zurich's V0 is no longer empty on this snapshot"
    fallback = aspirational_frontier(ctx, l1, r.get("F1"))
    assert len(fallback) > 0


def test_v0_empty_fallback_renders_in_the_app(ctx):
    """End-to-end proof the wiring in `views_find._render_aspirational` picks
    up the fallback: an AppTest run on ETH Zurich shows the fallback caption
    and NOT the "no candidate" empty state."""
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest

    app_dir = Path(__file__).resolve().parents[1]
    find_page = str(app_dir / "pages" / "1_\U0001F50E_Find.py")
    at = AppTest.from_file(find_page, default_timeout=180)
    at.session_state["seed_id"] = ETH_ZURICH
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    texts = " ".join(c.value for c in at.caption)
    assert copy.FIND["ASP_FRONTIER_FALLBACK"] in texts
    assert copy.FIND["ASP_EMPTY"].split("{")[0] not in texts


# ----------------------------------------------------- 4. name-as-link (A10)

def test_works_link_named_embeds_urlencoded_fragment():
    url = works_link_named("I123", "Université de Strasbourg")
    base, frag = url.split("#", 1)
    assert base.endswith("I123") or "I123" in base
    assert " " not in frag, "the fragment must be urlencoded (no literal spaces)"
    assert "%20" in frag or "+" in frag


def test_format_rows_and_concordance_drop_the_separate_link_column():
    from lib.ranked import format_concordance, format_rows

    row = {"institution_id": "I1", "rank": 1, "display_name": "Alpha U",
           "country_code": "FR", "type": "education"}
    df = format_rows([row], lens="L1", depth=1)
    assert "institution_link" not in df.columns
    assert "institution" in df.columns and "#" in df.iloc[0]["institution"]

    crow = {"institution_id": "I1", "display_name": "Alpha U", "country_code": "FR",
            "type": "education", "k": 1, "n": 3, "hit_lenses": ["L1", "L3"],
            "total_full_2020_2024": 100.0, "total_frac_2020_2024": 50.0}
    cdf = format_concordance([crow], lenses=["L1", "L3", "L0"], N=CONCORDANCE_N)
    assert "institution_link" not in cdf.columns
    # : hit_lenses chips are DISPLAY codes -- internal "L3" prints "L2".
    assert cdf.iloc[0]["hit_lenses"] == "L1, L2"


# --------------------------------------------------- 5. lens-code text ------

def test_rank_under_text_prints_display_codes_not_internal_ids():
    row = {"rank_under_other_lenses": {"L1": {"rank": 4, "score": 0.5},
                                       "L3": {"rank": 7, "score": 0.3}}}
    text = _rank_under_text(row)
    assert text == "L1 #4 · L2 #7"


def test_rank_under_text_na_mark_when_absent():
    from lib.palette import NA_MARK
    assert _rank_under_text({}) == NA_MARK
