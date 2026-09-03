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

Rewritten end to end for the trimmed app: the
pre-trim sections describing retired surfaces (the aspirational view, ERC
and SDG classifier detail, impact bootstrap intervals, gated type overrides,
the earlier standalone pair-view page's topic/field floors) are gone along with the
helpers that only ever fed them. Eleven sections remain, one per objection a
reader is entitled to raise about the trimmed app: what the tool is; data
and windows; counting bases and the Compare pin; the subject taxonomy; the
two impact baselines; frontier scores; world leaders; star papers; the
relationship block; matching; limits.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st
import yaml

from lib import copy
from lib.app_config import CFG
from lib.compare_data import ELITE_FRONTIER_PERCENTILE, PAIR_QUALIFYING_FLOOR
from lib.data_cache import DATA_DIR, index, manifest, topics_dim
from lib.engine import scenario_cache as SC
from lib.palette import NA_MARK
from lib.views_find import _sidebar_scenario

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
CONTRACT_PATH = DOCS_DIR / "data_contract.yaml"
NOTE_PATH = DOCS_DIR / "METHODS_NOTE.md"

# The star-paper cut is the upstream build's own k formula (k =
# max(1, ceil(0.01 * count)) per topic x year) -- it is not shipped
# to any table, so it is named here exactly the way `views_find.CORE_TOP_N`
# names an upstream constant with no data home of its own.
STAR_TOP_PCT = 1  # percent

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
    """How many institutions deep `topic_leaders.parquet` ranks each topic
    x pool leaderboard, read off the table's own `rank` column rather than
    typed in."""
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


@st.cache_resource(show_spinner=False)
def _momentum_facts() -> dict:
    """The two momentum windows and the significance level, read off
    `data/collab_facts.json` (shipped) rather than typed in: `w1`/`w2` are
    `[start, end]` year pairs, `alpha` a fraction formatted here as a whole
    percent."""
    if not COLLAB_FACTS_PATH.is_file():
        return {"momentum_w1": NA_MARK, "momentum_w2": NA_MARK, "momentum_alpha": NA_MARK}
    try:
        facts = json.loads(COLLAB_FACTS_PATH.read_text(encoding="utf-8"))
        w1, w2 = facts["w1"], facts["w2"]
        return {
            "momentum_w1": f"{w1[0]} to {w1[1]}",
            "momentum_w2": f"{w2[0]} to {w2[1]}",
            "momentum_alpha": f"{float(facts['alpha']) * 100:g}%",
        }
    except Exception:
        return {"momentum_w1": NA_MARK, "momentum_w2": NA_MARK, "momentum_alpha": NA_MARK}


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

    n_institutions = int(n_from_manifest) if n_from_manifest else int(len(idx))
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
        "concordance_n": CFG["concordance_N"],
        "depth_max": CFG["depth"]["max"],
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
