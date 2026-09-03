"""
tests/test_scenarios.py -- identity + RAM proof.

For each of the 6 (tree, basis) scenarios, `lib.engine.substrates.load_substrates`
(reads `app/data/scenarios/`, written by `pipeline/21_scenario_substrates.py`)
must return the EXACT SAME dict an in-process reference build produces
same keys, dtypes, shapes, memory order (arrays), same values (frames,
exact incl. category dtype). The reference is the pipeline step's own
building blocks (`build_topic_share`/`build_common`/`build_scenario`),
loaded by file path since `pipeline/` has no `__init__.py` and its filename
starts with a digit (brief: "import the ORIGINAL build_substrates from the
pipeline step, or from \\app\\lib\\engine by sys.path -- read-only").

Run from `app/`: python -m pytest tests/test_scenarios.py -q -s

`test_scenarios.py:__main__` (not collected by pytest) is the RAM proof:
`python tests/test_scenarios.py` cycles the 6 scenarios keeping only the
latest (del + gc), printing RSS after each -- table pasted into progress/P1.md.
"""
from __future__ import annotations

import gc
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

APP_DIR = Path(__file__).resolve().parents[1]
V4_ROOT = APP_DIR.parent
DATA_DIR = APP_DIR / "data"
PIPELINE_SCRIPT = V4_ROOT / "pipeline" / "21_scenario_substrates.py"
if not PIPELINE_SCRIPT.exists():
    pytest.skip("the offline build step that writes data/scenarios/ is not part of this repository; "
                "this identity check runs only where it is present", allow_module_level=True)

# conftest.py puts APP_DIR on sys.path under pytest; running this file
# directly (`python tests/test_scenarios.py`, the RAM-proof entry point)
# needs the same bootstrap.
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib.engine.substrates import DEFAULT_BASIS, DEFAULT_TREE, load_context, load_substrates  # noqa: E402
from lib.engine.trees_agg import TREES  # noqa: E402

sys.path.insert(0, str(APP_DIR / "ops"))
from rss_probe import process_rss_mb  # noqa: E402


def _load_pipeline_module():
    """`pipeline/21_scenario_substrates.py` is not an importable package
    member (no __init__.py, filename starts with a digit) -- load it by
    path, the same mechanism `run`/ad-hoc tooling uses for numbered
    pipeline scripts."""
    spec = importlib.util.spec_from_file_location("_p1_pipeline_scenario_substrates", PIPELINE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PL = _load_pipeline_module()
BASES = PL.BASES
SCENARIOS = [(tree, basis) for tree in TREES for basis in BASES]


@pytest.fixture(scope="module")
def ctx():
    return load_context(DATA_DIR)


@pytest.fixture(scope="module")
def topic_share_ref(ctx):
    return {basis: PL.build_topic_share(ctx, basis) for basis in BASES}


@pytest.fixture(scope="module")
def common_ref(ctx):
    return PL.build_common(ctx)


def _reference_subs(ctx, tree, basis, topic_share_ref, common_ref) -> dict:
    """Mirrors `load_substrates`'s own assembly exactly (same F1-from-L3
    derivation), but from FRESH in-process builds instead of disk reads
    the ground truth `load_substrates` is being checked against."""
    scenario = PL.build_scenario(ctx, tree, basis)
    topic_share = topic_share_ref[basis]
    common = common_ref

    td = ctx["topics_dim_df"]
    frontier_ids = set(td.loc[td["top25pct_frontier"] == True, "topic_id"])  # noqa: E712
    excluded_ids = set(td.loc[td["is_excluded"] == True, "topic_id"])  # noqa: E712
    f1_cats = sorted(frontier_ids)
    keep_cols = np.array([ctx["topic_pos"][t] for t in f1_cats], dtype=np.int32)

    subs = {"tree": tree, "basis": basis, "basis_applies": dict(PL.BASIS_APPLIES)}
    subs["l0"] = {"share": scenario["l0"]["share"], "cats": scenario["l0"]["cats"]}
    subs["l1"] = {"share": scenario["l1"]["share"], "cats": scenario["l1"]["cats"]}
    subs["fields_df"] = scenario["fields_df"]
    subs["subfields_df"] = scenario["subfields_df"]
    subs["l3"] = {"share": topic_share, "cats": ctx["topic_ids"]}
    subs["f1"] = {"share": topic_share[:, keep_cols], "cats": f1_cats,
                  "n_frontier_topics": len(frontier_ids),
                  "excluded_and_frontier_topic_ids": sorted(frontier_ids & excluded_ids)}
    subs["l2f"] = {"excess": scenario["l2f"]["excess"], "eligible": scenario["l2f"]["eligible"],
                   "cats": scenario["l2f"]["cats"]}
    subs["l4"] = {"share": common["l4"]["share"], "cats": common["l4"]["cats"]}
    subs["l5"] = {"excess": common["l5"]["excess"], "si": common["l5"]["si"], "cats": common["l5"]["cats"]}
    subs["l6"] = {"profile": common["l6"]["profile"], "raw_share": common["l6"]["raw_share"],
                  "cats": common["l6"]["cats"]}
    subs["l7"] = {"excess": common["l7"]["excess"], "esi": common["l7"]["esi"], "cats": common["l7"]["cats"]}
    return subs


def _assert_equal(a, b, path: str) -> int:
    """Recurses through the substrate dict; returns the number of leaf
    comparisons made (so a test that silently compares nothing is itself
    detectable -- see test_identity_makes_real_comparisons)."""
    n = 0
    if isinstance(a, dict):
        assert isinstance(b, dict), f"{path}: type differs (dict vs {type(b)})"
        assert set(a.keys()) == set(b.keys()), f"{path}: key sets differ {set(a) ^ set(b)}"
        for k in a:
            n += _assert_equal(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, np.ndarray):
        assert isinstance(b, np.ndarray), f"{path}: type differs (ndarray vs {type(b)})"
        assert a.dtype == b.dtype, f"{path}: dtype {a.dtype} != {b.dtype}"
        assert a.shape == b.shape, f"{path}: shape {a.shape} != {b.shape}"
        assert a.flags["C_CONTIGUOUS"] == b.flags["C_CONTIGUOUS"], (
            f"{path}: C_CONTIGUOUS {a.flags['C_CONTIGUOUS']} != {b.flags['C_CONTIGUOUS']}")
        assert a.flags["F_CONTIGUOUS"] == b.flags["F_CONTIGUOUS"], (
            f"{path}: F_CONTIGUOUS {a.flags['F_CONTIGUOUS']} != {b.flags['F_CONTIGUOUS']}")
        assert np.array_equal(a, b), f"{path}: values differ ({int(np.sum(a != b))} cells)"
        n += 1
    elif isinstance(a, pd.DataFrame):
        assert isinstance(b, pd.DataFrame), f"{path}: type differs (DataFrame vs {type(b)})"
        pd.testing.assert_frame_equal(a, b, check_dtype=True, check_categorical=True, obj=path)
        n += 1
    elif isinstance(a, list):
        assert a == b, f"{path}: list differs"
        n += 1
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"
        n += 1
    return n


@pytest.mark.parametrize("tree,basis", SCENARIOS, ids=[f"{t}_{b}" for t, b in SCENARIOS])
def test_load_substrates_matches_reference_build(ctx, topic_share_ref, common_ref, tree, basis):
    loaded = load_substrates(ctx, tree, basis)
    ref = _reference_subs(ctx, tree, basis, topic_share_ref, common_ref)
    n = _assert_equal(ref, loaded, f"subs[{tree}/{basis}]")
    print(f"[test_scenarios] {tree}/{basis}: {n} leaf comparisons, all equal")
    assert n >= 14, f"{tree}/{basis}: only {n} leaf comparisons made -- suspiciously few, check for a vacuous walk"


def test_topic_share_is_shared_across_trees(ctx, topic_share_ref):
    """D11 architecture claim: l3/f1 are tree-invariant -- `load_substrates`
    must hand back the SAME cached array object (identity, not just equal
    values) across every tree for a fixed basis."""
    arrays = [load_substrates(ctx, tree, "frac")["l3"]["share"] for tree in TREES]
    assert all(a is arrays[0] for a in arrays), "topic-share matrix was rebuilt/re-read per tree, not shared"


def test_f1_is_exact_column_subset_of_l3():
    """The design decision documented in pipeline/21_scenario_substrates.py's
    module docstring: f1 is never stored separately."""
    ctx_ = load_context(DATA_DIR)
    subs = load_substrates(ctx_, DEFAULT_TREE, DEFAULT_BASIS)
    td = ctx_["topics_dim_df"]
    frontier_ids = set(td.loc[td["top25pct_frontier"] == True, "topic_id"])  # noqa: E712
    keep_cols = np.array([ctx_["topic_pos"][t] for t in sorted(frontier_ids)], dtype=np.int32)
    assert np.array_equal(subs["l3"]["share"][:, keep_cols], subs["f1"]["share"])


# ------------------------------------------------------------- RAM proof ---

def _ram_cycle() -> list[tuple[str, str, float]]:
    """Bare-process cycle: ctx once, then the 6 scenarios in turn, keeping
    only the latest (del + gc.collect) -- prints RSS after each so a
    regression that starts accumulating scenarios is visible immediately."""
    rows = []
    ctx_ = load_context(DATA_DIR)
    gc.collect()
    baseline = process_rss_mb()[0]
    rows.append(("baseline(ctx)", "-", baseline))
    subs = None
    for tree in TREES:
        for basis in BASES:
            del subs
            gc.collect()
            subs = load_substrates(ctx_, tree, basis)
            gc.collect()
            rss = process_rss_mb()[0]
            rows.append((tree, basis, rss))
    return rows


if __name__ == "__main__":
    rows = _ram_cycle()
    baseline = rows[0][2]
    print(f"{'tree':<14}{'basis':<8}{'RSS (MB)':<12}{'delta vs baseline (MB)'}")
    for tree, basis, rss in rows:
        delta = rss - baseline
        print(f"{tree:<14}{basis:<8}{rss:<12.1f}{delta:+.1f}")
    peak = max(r[2] for r in rows)
    print(f"\npeak RSS: {peak:.1f} MB ({peak / 1024:.3f} GB)")
    print(f"baseline(ctx): {baseline:.1f} MB")
    worst_delta = max(rss - baseline for _, _, rss in rows[1:])
    print(f"worst per-step delta over baseline: {worst_delta:.1f} MB (budget 700 MB)")
    print(f"acceptance: peak <= 1300 MB: {'PASS' if peak <= 1300 else 'FAIL'}")
    print(f"acceptance: every step <= baseline+700MB: {'PASS' if worst_delta <= 700 else 'FAIL'}")
