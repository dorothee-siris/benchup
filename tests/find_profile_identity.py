"""
tests/find_profile_identity.py -- acceptance step 5.

For the 12 seeds in the reference profile golden, recomputes the
SIX legacy profile-header KPI values through this stream's OWN code path
(`lib.engine.scenario_cache.bundle` / `.get`, the same objects
`views_find._render_profile` -> `_card_specs` reads) on the default scenario
(`bestfit`/`frac`, matching the golden's own `default_scenario`), and asserts
EXACT equality against the golden -- the new P5 KPIs (star papers, topics
led) are excluded on purpose: they are NEW figures with their own tier-A eval, not part of this identity claim.

Exit 0 on a clean match; prints a diff and exits 1 on the first mismatch.

Run from cwd `app/`: python tests/find_profile_identity.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
V4_ROOT = APP_DIR.parent
GOLDEN_PATH = V4_ROOT / "evals" / "goldens" / "v3_find_profile.json"

sys.path.insert(0, str(APP_DIR))

from lib.engine import scenario_cache as SC  # noqa: E402
from lib.engine import seed_card  # noqa: E402

# (golden JSON key, a callable pulling the SAME value from (card, row))
# the exact six KPI reads `views_find._card_specs` performs (
# "" build item 5's own description of the golden's "call" field).
_KPI_READS = {
    "KPI_PUBS": lambda card, row: card["total_full_2020_2024"],
    "KPI_SDG_TAGGED_SHARE": lambda card, row: card["sdg_tagged_share"],
    "KPI_FRONTIER_TOP25_SHARE_INDEX": lambda card, row: card["frontier_top25_share_index"],
    "KPI_PP_TOP10_FRAC": lambda card, row: row["pp_top10_frac"],
    "KPI_INTL_SHARE": lambda card, row: row["intl_share"],
    "KPI_COMPANY_SHARE": lambda card, row: row["company_share"],
}


def _equal(got, want, *, rtol: float = 1e-5) -> bool:
    if want is None or (isinstance(want, float) and math.isnan(want)):
        return got is None or (isinstance(got, float) and math.isnan(got))
    got_f, want_f = float(got), float(want)
    return math.isclose(got_f, want_f, rel_tol=rtol, abs_tol=1e-8)


def main() -> int:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    tree, basis = golden["default_scenario"].split("_")
    profiles = golden["profiles"]

    bundle = SC.bundle()
    ctx = bundle["ctx"]
    subs = SC.get(tree, basis)

    failures = []
    for seed_id, want in profiles.items():
        card = seed_card(ctx, seed_id, subs, bundle["catchall"])
        row = ctx["index_by_id"].loc[seed_id]
        for key, reader in _KPI_READS.items():
            got = reader(card, row)
            if not _equal(got, want[key]):
                failures.append((seed_id, key, got, want[key]))

    if failures:
        print(f"MISMATCH: {len(failures)} of {len(profiles) * len(_KPI_READS)} KPI reads differ")
        for seed_id, key, got, want in failures[:20]:
            print(f"  {seed_id} / {key}: got={got!r} want={want!r}")
        return 1

    print(f"OK: {len(profiles)} seeds x {len(_KPI_READS)} legacy KPIs, all identical "
          f"(scenario {tree}/{basis})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
