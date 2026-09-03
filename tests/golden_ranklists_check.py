"""
tests/golden_ranklists_check.py -- exact rank-list identity check against
the reference rank-list figures.

Reproduces every (seed, scenario, lens) top-50 EXACTLY -- same institution_id
order, same scores -- via `load_context` + `load_substrates` +
`lib.engine.lenses.rank_all`, run live against the app's own code. No
tolerance: this is the SAME arithmetic run through a different
(offline-precomputed) substrate path, so a mismatch of any size is a real
regression, not float noise.

The reference figures ship with the repo at tests/golden/reference/ranklists.json
(numbers generated once from the same data this app ships, for the app to
reproduce exactly).

Run from `app/`: python tests/golden_ranklists_check.py
Exit 0 = every list reproduced exactly. Exit 1 = at least one mismatch (a
diff summary is printed). Exit 2 = reference file missing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"
GOLDEN_PATH = Path(__file__).resolve().parent / "golden" / "reference" / "ranklists.json"

sys.path.insert(0, str(APP_DIR))
from lib.engine import load_context, load_substrates, rank_all  # noqa: E402


def main() -> int:
    if not GOLDEN_PATH.exists():
        print(f"[golden_check] STATUS: reference file missing -- {GOLDEN_PATH} not found")
        return 2

    gold = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    seeds = gold["rankings"]
    ctx = load_context(DATA_DIR)

    n_checked = 0
    mismatches: list[str] = []
    subs_cache: dict[tuple[str, str], dict] = {}

    for seed_id, scenarios in seeds.items():
        for scenario_key, lens_golds in scenarios.items():
            tree, basis = scenario_key.rsplit("_", 1)
            key = (tree, basis)
            if key not in subs_cache:
                subs_cache[key] = load_substrates(ctx, tree, basis)
            subs = subs_cache[key]
            rankings = rank_all(ctx, subs, seed_id)

            for lens_name, g in lens_golds.items():
                n_checked += 1
                r = rankings[lens_name]
                label = f"{seed_id}/{scenario_key}/{lens_name}"

                if r["undefined"] != g["undefined"]:
                    mismatches.append(f"{label}: undefined {r['undefined']} != golden {g['undefined']}")
                    continue
                if r["undefined"]:
                    if r["reason"] != g["reason"]:
                        mismatches.append(f"{label}: reason {r['reason']!r} != golden {g['reason']!r}")
                    continue

                got_ids = list(r["sorted_ids"][:50])
                got_scores = [float(s) for s in r["sorted_scores"][:50]]
                want_ids = [row["institution_id"] for row in g["top50"]]
                want_scores = [row["score"] for row in g["top50"]]

                if got_ids != want_ids:
                    pos = next((i for i, (a, b) in enumerate(zip(got_ids, want_ids)) if a != b),
                              min(len(got_ids), len(want_ids)))
                    mismatches.append(f"{label}: id order differs at position {pos} "
                                      f"({len(got_ids)} vs {len(want_ids)} rows)")
                    continue
                for i, (gs, ws) in enumerate(zip(got_scores, want_scores)):
                    if gs != ws:
                        mismatches.append(f"{label}: score[{i}] ({want_ids[i]}) {gs!r} != golden {ws!r}")
                        break

    print(f"[golden_check] {n_checked} (seed, scenario, lens) combinations checked")
    if mismatches:
        print(f"[golden_check] {len(mismatches)} MISMATCH(ES):")
        for m in mismatches[:50]:
            print(f"  - {m}")
        if len(mismatches) > 50:
            print(f"  ... and {len(mismatches) - 50} more")
        return 1

    print("[golden_check] ALL RANK LISTS REPRODUCED EXACTLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
