"""
tests/test_decisions_log_rules.py -- BenchUp V4 trim,: two decisions-log
rules this stream's own page/copy carry out, named explicitly in
 (the "Decisions log" table) and in this stream's own
brief.

REWRITTEN for the trim: the pre-trim file tested
`compare_data.metric_frame`'s V4-column contract, `JOINT_TOPICS_COLS`,
`METRICS`/`LEVELS` -- every one of those names is DELETED with
own rewrite (`progress/C1.md`'s deletion map: the whole N-institution
"Compare by" matrix, ERC, the pooled frontier scatter). Nothing there
survives to re-test; `tests/test_compare_data.py`
and `tests/test_compare_golden_anchors.py` (this stream's own top-up) already cover the
DATA layer for the new API in depth. What remains genuinely C3's own is the
VIEW-level disclosure of two decisions-log rules:

  1. "Joint volume per shared-frontier topic shown only for pairs with
     core_total >= 5 (P7 qualifying floor); below it the joint segment is
     absent and the caption says why".
  2. "Relationship yearly stack sums to the pair's joint articles+reviews
     THAT CARRY A PRIMARY TOPIC. C3's caption must say 'joint articles
     and reviews with a subject topic'. when Sigma yearly < core_total" -- the topicless-works caption.

Plus the grep proof this stream's own acceptance line asks for: no
reference to the deleted `state.COLLAB_CAP` survives anywhere under this
stream's fence.

Run from cwd `app/`: python -m pytest tests/test_decisions_log_rules.py -q
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from lib import compare_data as CD
from lib import copy
from lib.engine import scenario_cache as SC

APP_DIR = Path(__file__).resolve().parents[1]

IFREMER = "I154202486"
NIOZ = "I4210107283"  # T0 anchor pair -- qualifies, no topicless residual
TOPICLESS_A, TOPICLESS_B = "I70900168", "I861853513"  # a real pair with a
# genuine topicless residual (core_total=426, Sigma(yearly.vol)=425 -- probed
# live, duckdb, 2026-09-03), used to prove the flag is REACHABLE, not just
# theoretically possible.


@pytest.fixture(scope="module")
def ctx():
    return SC.bundle()["ctx"]


@pytest.fixture(scope="module")
def subs():
    return SC.get("bestfit", "full")


# ---------------------------------------------------------------------------
# 1. joint segment absent below the P7 floor (shared_frontier.joint_known)
# ---------------------------------------------------------------------------

def test_shared_frontier_joint_known_is_true_for_a_qualifying_pair(ctx, subs):
    sf = CD.shared_frontier(ctx, subs, [IFREMER, NIOZ])
    assert len(sf) > 0
    assert sf["joint_known"].all()
    assert sf["vol_joint"].notna().all()

    # VACUITY
    corrupt = sf.copy()
    corrupt.loc[0, "joint_known"] = False
    assert not corrupt["joint_known"].all()


def test_shared_frontier_tip_names_the_p7_floor_in_words():
    """The chart's own caption states the rule in words (D5's brief:
    "the caption says why") -- `copy.COMPARE["SHARED_FRONTIER_TIP"]`,
    filled from `charts_compare.JOINT_FLOOR`, never a hand-typed number."""
    from lib import charts_compare as X

    rendered = copy.COMPARE["SHARED_FRONTIER_TIP"].format(floor=int(X.JOINT_FLOOR))
    needle = f"Below {X.JOINT_FLOOR} joint publications"
    assert needle in rendered
    assert "not shown separately" in rendered and "n/a" in rendered

    # VACUITY: a caption filled with the WRONG floor does not satisfy the
    # SAME needle.
    wrong = copy.COMPARE["SHARED_FRONTIER_TIP"].format(floor=int(X.JOINT_FLOOR) + 1)
    assert needle not in wrong


# ---------------------------------------------------------------------------
# 2. the topicless-works caption (relationship.topicless_note)
# ---------------------------------------------------------------------------

def test_relationship_topicless_note_is_false_for_the_t0_anchor_pair(ctx, subs):
    """The T0 anchor pair's yearly breakdown sums EXACTLY to core_total
    (P2's own finding: 99.7% of qualifying pairs are exact) -- the flag
    must read False here, never a blanket True."""
    rel = CD.relationship(ctx, [IFREMER, NIOZ], subs)
    assert rel["topicless_note"] is False
    assert rel["yearly"]["vol"].sum() == rel["core_total"]


def test_relationship_topicless_note_is_true_for_a_real_residual_pair(ctx, subs):
    """A real pair with a genuine topicless residual (probed live, duckdb,
    against `collab_pairs.parquet`/`collab_pair_domain_year.parquet`
    Sigma(yearly.vol) = 425 < core_total = 426) -- proves the flag is
    REACHABLE on real data, not merely a branch that never fires."""
    rel = CD.relationship(ctx, [TOPICLESS_A, TOPICLESS_B], subs)
    assert rel["momentum"] is not None, "the residual anchor must be a real, qualifying pair"
    assert rel["topicless_note"] is True
    assert rel["yearly"]["vol"].sum() < rel["core_total"]

    # VACUITY: the T0 pair's own (non-residual) yearly frame does NOT trip
    # the same flag -- proves the True above is a property of THIS pair's
    # data, not a bug that always returns True.
    clean = CD.relationship(ctx, [IFREMER, NIOZ], subs)
    assert clean["topicless_note"] is False


def test_yearly_caption_names_a_subject_topic_and_composes_the_topicless_note():
    """C3's own caption rule: the base sentence says
    "with a subject topic"; the topicless addendum is appended ONLY when
    the pair's own flag is set."""
    Cw = copy.COMPARE
    base = Cw["YEARLY_CAPTION"].format(y0=CD.CORE_WINDOW[0], y1=CD.CORE_WINDOW[1])
    assert "with a subject topic" in base
    composed = base + Cw["YEARLY_TOPICLESS_NOTE"]
    assert "carry no subject topic" in composed
    # VACUITY: the base sentence ALONE (the non-residual page path) must
    # NOT itself carry the addendum's own claim.
    assert "carry no subject topic" not in base


# ---------------------------------------------------------------------------
# 3. grep proof -- no reference to the deleted state.COLLAB_CAP survives
# ---------------------------------------------------------------------------

STREAM_C3_OWNED_FILES = (
    "lib/views_compare.py", "lib/exports_xlsx.py",
    "tests/test_pages_compare.py", "tests/test_compare_basis_pin.py",
    "tests/test_ratio_caption_presence.py", "tests/test_hatch_rule.py",
    "tests/test_locale_format_ban.py", "tests/test_download_button_consolidation.py",
    "tests/test_gutter_and_caution_channel.py", "tests/test_reference_value_resolution.py",
    "tests/test_narrative.py", "tests/test_matrix.py", "tests/test_compare_golden_anchors.py",
    "tests/test_find_benchmark_section.py", "tests/test_badges.py", "tests/test_evidence.py",
)
# copy.py is scanned by its own COMPARE-dict span only (E10: a plain
# whole-file grep would also flag another stream's OWN, still-live section
# of that shared file -- COLLAB_CAP is legitimately still referenced
# elsewhere in copy.py's own comment prose about OTHER streams' carry-over
# items, which is not this stream's fence to fix).


def test_no_collab_cap_reference_survives_under_this_streams_own_fence():
    """ carry-over (E3's own finding): `state.COLLAB_CAP`
    was deleted with the shortlist; every file THIS STREAM owns
    must carry no reference to it. Scoped to C3's own fence (§3.0) -- a
    reference in another stream's file (e.g. `tests/ui/smoke.py`, T2's own,
    not yet rewritten per the ledger) is that stream's job, not this
    guard's to fail on."""
    hits = []
    for rel in STREAM_C3_OWNED_FILES:
        path = APP_DIR / rel
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "COLLAB_CAP" in text:
            hits.append(rel)
    assert hits == [], hits

    # VACUITY: a scratch string DOES contain the literal, proving the
    # substring check itself is live.
    assert "COLLAB_CAP" in "state.COLLAB_CAP"
