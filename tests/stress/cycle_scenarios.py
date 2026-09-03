"""
tests/stress/cycle_scenarios.py -- phase C: a BARE process
(no Streamlit server, no browser) that calls `scenario_cache.bundle()` then
`scenario_cache.get(tree, basis)` for all six (tree, basis) scenarios in
sequence, sampling this process's own RSS after each. Reuses the logic of
`tests/test_ram_budget.py::test_scenario_cycle` (replicated minimally rather
than imported -- that function is a pytest test, collected and driven by
pytest's own machinery, not meant to be called as a plain function; the BUILD
PLAN itself allows "reuse that logic by import if importable, else replicate
minimally").

Confirmed by `test_scenario_cycle`'s own docstring (and empirically, before
this script was written): `st.cache_resource` genuinely evicts and frees the
previous scenario dict in BARE mode (no real `streamlit run` context needed --
same "missing ScriptRunContext" condition a plain `python` invocation runs
under), so this script's weakref eviction proof is not vacuous.

Run standalone:
    cd app && ..\\envs\\env-app\\Scripts\\python.exe tests/stress/cycle_scenarios.py

Or folded into a `run_stress.py` report via `--phases ...,C` (that script
shells out to this one and captures its stdout + exit code unchanged).

Exit 0 iff peak RSS < PEAK_CEILING_MB AND every scenario swap actually freed
the previous scenario's l0 share array (weakref proof) -- exit 1 otherwise.
"""
from __future__ import annotations

import gc
import sys
import time
import weakref
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2]  # app/
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(APP_DIR / "ops"))

from lib.engine import scenario_cache as SC  # noqa: E402
from rss_probe import process_rss_mb  # noqa: E402

PEAK_CEILING_MB = 1800.0

SCENARIOS = [(tree, basis)
            for tree in ("original", "conservative", "bestfit")
            for basis in ("frac", "full")]


def main() -> int:
    rows: list[tuple[float, str, float]] = []  # (elapsed_s, label, rss_mb)
    t0 = time.time()

    r0 = process_rss_mb()
    if r0 is None:
        print("FAIL: could not read this process's own RSS (ctypes GetProcessMemoryInfo)")
        return 1
    print(f"[cycle] baseline RSS: {r0[0]:.2f} MB")
    rows.append((0.0, "baseline", r0[0]))

    SC.bundle()
    rb = process_rss_mb()
    print(f"[cycle] after bundle(): {rb[0]:.2f} MB (+{rb[0] - r0[0]:.2f} MB)")
    rows.append((time.time() - t0, "bundle", rb[0]))

    eviction_ok = True
    prev_weak = None

    print(f"[cycle] {'#':<3} {'tree':<12} {'basis':<6} {'rss_mb':>10}")
    for i, (tree, basis) in enumerate(SCENARIOS):
        subs = SC.get(tree, basis)
        r = process_rss_mb()
        if r is None:
            print(f"FAIL: could not read RSS at scenario {i} ({tree}, {basis})")
            return 1
        rows.append((time.time() - t0, f"{tree}/{basis}", r[0]))
        print(f"[cycle] {i + 1:<3} {tree:<12} {basis:<6} {r[0]:>10.2f}")

        weak = weakref.ref(subs["l0"]["share"])
        del subs
        gc.collect()
        if prev_weak is not None:
            still_alive = prev_weak() is not None
            if still_alive:
                eviction_ok = False
                print(f"[cycle] WARNING: previous scenario's l0 share array still alive "
                     f"after swapping to ({tree}, {basis}) -- max_entries did not evict it")
        prev_weak = weak

    peak = max(v for _, _, v in rows)
    mean = sum(v for _, _, v in rows) / len(rows)
    final = rows[-1][2]

    print("\n=== CYCLE SUMMARY ===")
    print(f"{'label':<14} {'elapsed_s':>10} {'rss_mb':>10}")
    for t, label, v in rows:
        print(f"{label:<14} {t:>10.2f} {v:>10.2f}")
    print(f"\nbaseline={r0[0]:.2f} MB  peak={peak:.2f} MB  mean={mean:.2f} MB  final={final:.2f} MB "
         f"(ceiling {PEAK_CEILING_MB:.0f} MB)")
    print(f"eviction proof (every swap freed the previous scenario): {'OK' if eviction_ok else 'FAILED'}")

    passed = peak < PEAK_CEILING_MB and eviction_ok
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
