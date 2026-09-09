"""
app/lib/views_methods.py -- the Methods page.

`copy.METHODS` is a dict of `{title, body}` templates whose every number is a
`{placeholder}` filled at RUN TIME, never typed as a literal (the digit-ban
RULE at the top of lib/copy.py). `methods_values` below is the one place
that fills them, from CFG (lib/app_config.py), the manifest, the shipped
tables (index, topics_dim, topic_leaders, collab_pairs, collab_pair_domain_year)
and docs/data_contract.yaml's own prose. `docs/METHODS_NOTE.md` is the
human-readable twin of the same sections (never rendered by the app; offered
as a download at the foot of the page).

Rewritten end to end for the trimmed app, then again to add the topic
planes, the topic overlap and the momentum-evidence detail: sections
describing a retired surface (the aspirational view's old detail, ERC and
SDG classifier detail, impact bootstrap intervals, gated type overrides, the earlier
standalone pair-view page's topic/field floors, the two-pool "topics led"
reading, the pooled frontier positioning KPIs, the shared-frontier mirror
chart and its diamond mark) are gone along with the helpers that only ever
fed them. Fifteen sections remain, one per objection a reader is entitled to
raise about the app as it stands: what the tool is; data and windows;
counting bases and the Compare pin; the subject taxonomy; the two impact
baselines; frontier scores; world leaders; star papers; the topic planes;
Compare's topic overlap; the relationship block; reading momentum; matching;
the scale guard; limits.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st
import yaml

from lib import copy
from lib import how_to_read as HTR
from lib.app_config import CFG
from lib.compare_data import ELITE_FRONTIER_PERCENTILE, PAIR_QUALIFYING_FLOOR
from lib.data_cache import DATA_DIR, index, manifest, topics_dim
from lib.engine import scenario_cache as SC
from lib.palette import NA_MARK
from lib.topic_data import (
    FWCI_MODE_FLOOR, N_MAX as TOPIC_N_MAX, N_MIN as TOPIC_N_MIN,
    PAIR_N_MAX, PLANE_A_MIN_COVERED, emergence_threshold,
)
from lib.views_find import TOPIC_N_DEFAULT, _sidebar_scenario

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
CONTRACT_PATH = DOCS_DIR / "data_contract.yaml"
NOTE_PATH = DOCS_DIR / "METHODS_NOTE.md"

# The star-paper cut is the upstream build's own k formula (k =
# max(1, ceil(0.01 * count)) per topic x year) -- it is not shipped
# to any table, so it is named here exactly the way `views_find.CORE_TOP_N`
# names an upstream constant with no data home of its own.
STAR_TOP_PCT = 1  # percent

# Two build-time facts about `inst_topic_impact.parquet` (the institution x
# primary-topic impact table behind the topic planes and Compare's topic
# overlap), each measured ONCE during that table's own pipeline build by
# reconciling it against a SEPARATELY built table this app does not hold in
# a joinable shape at page-load time (fwci_taxa.parquet's own frozen anchor
# cells for the first; topics_all.parquet's own per-topic whole-run volume
# for the second). Recomputing either live would mean re-deriving
# institution attribution from the raw record a second time (the first) or
# reading topics_all.parquet's own wide, per-topic-per-year columns across
# the whole table (the second) -- both pipeline-scale operations, not a
# Streamlit page-load one. Typed as constants rather than recomputed; the
# total row count they are read against (p7_bound_total_rows) IS read live,
# off the manifest, below. See copy.METHODS_SOURCES's own entries for these
# two names.
P7_FWCI_RESIDUAL_CELLS = 3   # of P7_FWCI_ANCHOR_CELLS anchor cells, each off by one or two works
P7_FWCI_ANCHOR_CELLS = 561
P7_BOUND_VIOLATION_N = 115   # rows sitting exactly one work above topics_all's own whole-run volume

_DOC_TYPE_WORDS = {
    "article": "articles", "review": "reviews", "book": "books",
    "book-chapter": "book chapters", "letter": "letters",
}


def _and_join(words: list[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    return f"{', '.join(words[:-1])} and {words[-1]}"


def _pct(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%"


def _doc_types_text() -> str:
    return _and_join([_DOC_TYPE_WORDS.get(t, t) for t in CFG["corpus_types"]])


def _core_ar_window() -> object:
    """`window_conventions.core_ar_window`, read verbatim off
    docs/data_contract.yaml rather than retyped (same pattern the pre-trim
    page already used for the two dynamics windows): NA_MARK if the contract
    prose this depends on ever reshapes."""
    try:
        contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
        return contract["window_conventions"]["core_ar_window"]
    except Exception:
        return NA_MARK


@st.cache_resource(show_spinner=False)
def _taxonomy_facts() -> dict:
    """Live counts off `topics_dim.parquet`, the shipped taxonomy dimension:
    how many of its topics the best-fit and the conservative repair each
    move to a different subfield from OpenAlex's own placement, how many
    carry no frontier score (the catch-all exclusion list), and how many
    needed a forced or a no-fit placement in the repair itself."""
    td = topics_dim()
    return {
        "n_topics": int(len(td)),
        "n_excluded": int(td["is_excluded"].fillna(False).sum()),
        "n_best_diff": int((td["bestfit_subfield_id"] != td["original_subfield_id"]).sum()),
        "n_cons_diff": int((td["conservative_subfield_id"] != td["original_subfield_id"]).sum()),
        "n_forced_or_nofit": int(td["fit_quality"].isin(["forced", "no_fit"]).sum()),
    }


@st.cache_resource(show_spinner=False)
def _leader_depth() -> object:
    """How many institutions deep `topic_leaders.parquet` ranks each topic's
    leaderboard (one ranking across every institution type), read off the
    table's own `rank` column rather than typed in."""
    try:
        col = pd.read_parquet(DATA_DIR / "topic_leaders.parquet", columns=["rank"])
        return int(col["rank"].max())
    except Exception:
        return NA_MARK


@st.cache_resource(show_spinner=False)
def _star_share_example() -> dict:
    """The institution with the highest `star_share` in the shipped index:
    the live illustration of 'a small denominator can post a very high
    share', read off the data rather than named as a fixed example."""
    try:
        cols = index()[["display_name", "star_share"]].dropna(subset=["star_share"])
        if cols.empty:
            raise ValueError("no institution carries a star_share value")
        row = cols.loc[cols["star_share"].idxmax()]
        return {"top_star_name": str(row["display_name"]),
                "top_star_share": _pct(float(row["star_share"]))}
    except Exception:
        return {"top_star_name": NA_MARK, "top_star_share": NA_MARK}


@st.cache_resource(show_spinner=False)
def _topicless_pct() -> object:
    """Share of joint CORE-AR volume, across every pair that qualifies for
    the relationship block's topic and yearly detail, that the yearly
    domain stack cannot place (a joint work carrying no subject topic)
    measured live as 1 minus (sum of `collab_pair_domain_year.vol`) over
    (sum of `collab_pairs.core_total`), restricted to `core_total >=
    PAIR_QUALIFYING_FLOOR`, rather than a number typed from a past run."""
    pairs_path = (DATA_DIR / "collab_pairs.parquet").as_posix()
    yearly_path = (DATA_DIR / "collab_pair_domain_year.parquet").as_posix()
    con = duckdb.connect()
    try:
        out = con.sql(f"""
            WITH yearly AS (
                SELECT a, b, SUM(vol) AS vol_sum
                FROM read_parquet('{yearly_path}') GROUP BY a, b
            )
            SELECT SUM(p.core_total) AS total_core, SUM(y.vol_sum) AS total_yearly
            FROM read_parquet('{pairs_path}') p
            JOIN yearly y ON p.a = y.a AND p.b = y.b
            WHERE p.core_total >= {PAIR_QUALIFYING_FLOOR}
        """).df()
    except Exception:
        return NA_MARK
    finally:
        con.close()
    if out.empty or pd.isna(out.loc[0, "total_core"]) or not out.loc[0, "total_core"]:
        return NA_MARK
    total_core, total_yearly = float(out.loc[0, "total_core"]), float(out.loc[0, "total_yearly"])
    share = max(0.0, (total_core - total_yearly) / total_core)
    return _pct(share, decimals=2)


COLLAB_FACTS_PATH = DATA_DIR / "collab_facts.json"

_MOMENTUM_NA = {"momentum_w1": NA_MARK, "momentum_w2": NA_MARK,
                "momentum_alpha": NA_MARK, "momentum_band": NA_MARK}


@st.cache_resource(show_spinner=False)
def _momentum_facts() -> dict:
    """The two momentum windows, the significance level and the stable-band
    width, read off `data/collab_facts.json` (shipped) rather than typed in:
    `w1`/`w2` are `[start, end]` year pairs, `alpha`/`band` are fractions
    formatted here as whole percents."""
    if not COLLAB_FACTS_PATH.is_file():
        return dict(_MOMENTUM_NA)
    try:
        facts = json.loads(COLLAB_FACTS_PATH.read_text(encoding="utf-8"))
        w1, w2 = facts["w1"], facts["w2"]
        return {
            "momentum_w1": f"{w1[0]} to {w1[1]}",
            "momentum_w2": f"{w2[0]} to {w2[1]}",
            "momentum_alpha": f"{float(facts['alpha']) * 100:g}%",
            "momentum_band": f"{float(facts['band']) * 100:g}%",
        }
    except Exception:
        return dict(_MOMENTUM_NA)


@st.cache_resource(show_spinner=False)
def _emergence_facts() -> dict:
    """The frontier-emergence selector's own world top-decile cutoff:
    `lib.topic_data.emergence_threshold()` (memoized there; the SAME value
    both Find's frontier plane and Compare's topic overlap read for their
    own 'top decile of emergence' mode), plus a live count of how many of
    `topics_dim.parquet`'s own scored topics clear it -- measured off the
    shipped table, never retyped from a past run."""
    try:
        td = topics_dim()
        scored = td["frontier_score_latest"].notna()
        threshold = float(emergence_threshold())
        n_scored = int(scored.sum())
        n_at_or_above = int((td.loc[scored, "frontier_score_latest"] >= threshold).sum())
        return {
            "emergence_threshold": f"{threshold:.3f}",
            "n_scored_topics": f"{n_scored:,}",
            "n_emergence_topics": f"{n_at_or_above:,}",
        }
    except Exception:
        return {"emergence_threshold": NA_MARK, "n_scored_topics": NA_MARK,
                "n_emergence_topics": NA_MARK}


def methods_values() -> dict:
    """Every `{placeholder}` copy.METHODS uses, filled from CFG / manifest
    / the shipped tables above. Keys match copy.METHODS_SOURCES exactly
    (tests/test_methods_note.py cross-checks the two dicts don't drift)."""
    mf = manifest()
    idx = index()
    n_from_manifest = mf.get("files", {}).get("index.parquet", {}).get("n_rows")
    taxonomy = _taxonomy_facts()
    stars = _star_share_example()
    momentum = _momentum_facts()
    emergence = _emergence_facts()

    n_institutions = int(n_from_manifest) if n_from_manifest else int(len(idx))
    n_inst_topic_rows = mf.get("files", {}).get("inst_topic_impact.parquet", {}).get("n_rows")
    scale_guard_ratio = CFG.get("scale_guard", {}).get("ratio")
    return {
        "n_institutions": f"{n_institutions:,}",
        "n_countries": len(CFG["perimeter_countries"]),
        "snapshot": mf.get("snapshot") or CFG.get("snapshot", NA_MARK),
        "doc_types": _doc_types_text(),
        "y0": CFG["window"][0],
        "y1": CFG["window"][1],
        "bonus_year": CFG["bonus_year"],
        "core_ar_window": _core_ar_window(),
        "n_trees": len(CFG["scenario"]["toggles"]["tree"]),
        "n_topics": f"{taxonomy['n_topics']:,}",
        "n_excluded": f"{taxonomy['n_excluded']:,}",
        "n_best_diff": f"{taxonomy['n_best_diff']:,}",
        "n_cons_diff": f"{taxonomy['n_cons_diff']:,}",
        "n_forced_or_nofit": f"{taxonomy['n_forced_or_nofit']:,}",
        "frontier_scores_intro": HTR.methods("frontier_scores"),
        "top_decile_pct": _pct(1 - ELITE_FRONTIER_PERCENTILE, decimals=0),
        "leader_depth": _leader_depth(),
        "star_pct": f"{STAR_TOP_PCT:g}%",
        "top_star_name": stars["top_star_name"],
        "top_star_share": stars["top_star_share"],
        "pair_qualifying_floor": PAIR_QUALIFYING_FLOOR,
        "topicless_pct": _topicless_pct(),
        "momentum_w1": momentum["momentum_w1"],
        "momentum_w2": momentum["momentum_w2"],
        "momentum_alpha": momentum["momentum_alpha"],
        "momentum_band": momentum["momentum_band"],
        "concordance_n": CFG["concordance_N"],
        "depth_max": CFG["depth"]["max"],
        "plane_a_min_covered": PLANE_A_MIN_COVERED,
        "fwci_mode_floor": FWCI_MODE_FLOOR,
        "emergence_threshold": emergence["emergence_threshold"],
        "n_scored_topics": emergence["n_scored_topics"],
        "n_emergence_topics": emergence["n_emergence_topics"],
        "n_topic_min": TOPIC_N_MIN,
        "n_topic_max": TOPIC_N_MAX,
        "topic_n_default": TOPIC_N_DEFAULT,
        "pair_n_max": PAIR_N_MAX,
        "scale_guard_ratio": f"{scale_guard_ratio:g}" if scale_guard_ratio is not None else NA_MARK,
        "p7_fwci_residual_cells": P7_FWCI_RESIDUAL_CELLS,
        "p7_fwci_anchor_cells": P7_FWCI_ANCHOR_CELLS,
        "p7_bound_violation_n": P7_BOUND_VIOLATION_N,
        "p7_bound_total_rows": f"{int(n_inst_topic_rows):,}" if n_inst_topic_rows else NA_MARK,
    }


def _note_bytes() -> bytes:
    return NOTE_PATH.read_bytes()


def render() -> None:
    """The Methods page: the counting-and-taxonomy sidebar every other page
    shows (for chrome consistency only -- nothing on this page reads a
    scenario, so a tree/basis flip here costs nothing), then title/lead from
    copy.NAV, the verdict line, one expander per copy.METHODS section in
    dict order, and a footer offering docs/METHODS_NOTE.md as a download
    alongside the snapshot stamp."""
    SC.bundle()
    _sidebar_scenario()
    values = methods_values()

    st.title(copy.NAV["METHODS_LABEL"])
    st.caption(copy.NAV["METHODS_LEAD"])
    st.markdown(f"**{copy.VERDICT_LINE}**")
    st.markdown("---")

    for section in copy.METHODS.values():
        title = section["title"].format(**values)
        with st.expander(title, expanded=False):
            st.markdown(section["body"].format(**values))

    st.markdown("---")
    mf = manifest()
    generated_at = (mf.get("source_manifest_generated_at") or mf.get("generated_at")
                    or mf.get("deployed_at") or NA_MARK)
    st.caption(copy.FIND["SNAPSHOT_CAPTION"].format(
        snapshot=values["snapshot"], generated_at=generated_at, sep=copy.STRIP_JOIN,
        n_institutions=f"{len(index()):,}"))
    st.download_button(
        copy.METHODS_UI["DOWNLOAD_LABEL"],
        _note_bytes,
        file_name="METHODS_NOTE.md",
        mime="text/markdown",
        key="dl_methods_note",
    )
    st.caption(copy.METHODS_UI["DOWNLOAD_CAPTION"])
