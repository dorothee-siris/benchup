"""
The shared ranked-table component for every `tbl-lens-ranked` tab and the
concordance overview (VIZ_SPEC.md S2.3, S2.4). Consumed by.

Implements the A/B verdict (`design-system/ab/AB_VERDICT.md`,
`docs/VIZ_SPEC.md` S4):
  - A/B #1 winner: `st.column_config.ProgressColumn` for the lens score,
    never a Plotly ranked-dot chart, in every ordinary lens tab.
  - A/B #2 winner: a k-of-n table with a hit-lens-chip text column, never a
    full rank matrix, for the concordance overview.

Refinement R1: the
badge column is gone (badges now live on the seed profile header only
L7/L17); every table carries two size columns (full, fractional); the
evidence cell is the lens-specific text the engine computes
(`row["evidence_text"]`, L21/S9.4 -- "top field" no longer fits every lens);
country is shown by its English name (`lib.countries.name`), with the raw
code kept as a hidden column for anything downstream that still wants it.

Pure functions (`format_rows`, `depth_caption`, `format_concordance`,
`concordance_caption`) take engine output and return `pandas.DataFrame`/`str`
no Streamlit import, testable headlessly (`tests/test_ranked.py`). The two
render functions own the Streamlit widget calls only.
"""
from __future__ import annotations

from urllib.parse import quote

import pandas as pd
import streamlit as st

from lib import copy, countries
from lib.app_config import CFG
from lib.engine import RANK_VISIBLE_MAX
from lib.palette import NA_MARK

WINDOW_START, WINDOW_END = CFG["window"]
NOT_IN_TOPN = "--"  # A/B #2 winner's matrix cell language is unused here (k-count
                     # table won); kept only as the "candidate outside a lens's
                     # visible rank" mark inside the rank_under text below.

# A10: "fragment" is the primary mode -- the institution NAME column
# becomes the OpenAlex-works LinkColumn via the `#<name>` fragment trick, and
# the old separate "OpenAlex works" link column is dropped. Flip to "fallback"
# (never in normal operation; only if a live Playwright render check ever
# shows the fragment trick failing on this Streamlit build) to keep the two
# columns side by side instead, with the harmonised label the plan names.
NAME_LINK_MODE = "fragment"
WORKS_LINK_FALLBACK_LABEL = "See works ↗"

# The OpenAlex works deep link carries the harvest's own filters (L23) and lives
# in ONE place, lib/links.py (R-B). Manager edit 2026-08-29: the R-F2 import-time
# fallback was dropped once lib/links.py landed (progress/R1_F2.md NEEDS_CHANGE).
from lib.links import works_url as _works_link

# D9: the shared 0-100 progress-column idiom.
# Streamlit's OWN `format="percent"` keyword scales a 0-1 value to a percentage
# internally but renders it through the HOST BROWSER LOCALE -- confirmed live,
# comma-decimal ("76,04 %") -- which is exactly the D9-banned behaviour. A
# printf spec applied directly to the raw 0-1 value does not fix this: it has
# no scaling of its own, so "%.0f%%" on 0.76 prints "1%" (the value rounded to
# the nearest whole FRACTION, not a percentage) -- the trap the retired
# "manager fix 2026-08-29" comment on the old `score` config named correctly
# but then still shipped the banned keyword as its workaround. The fix needs
# BOTH halves in the right place: the caller's own dataframe column carries the
# value already multiplied by 100 (`_pct100` below feeds `format_rows`'s own
# `score` column), and this ONE printf format string is shared by every such
# column in the app so they render identically. `views_find.py`'s Aspirational
# `L1 overlap` column (line ~1476) is the other live call site -- CHROME-F does
# not own that file; the one-line swap it needs is recorded in
# `progress/2C_CHROME-F.md`.
PCT_PROGRESS_FORMAT = "%.1f%%"


def pct_progress_column(label: str) -> "st.column_config.Column":
    """A `ProgressColumn` for a percentage already scaled 0-100 -- printf-style,
    period-decimal regardless of host locale (D9). The caller's OWN dataframe
    column must carry the *100 value; this function only builds the column
    config, since Streamlit's column_config has no value-transform hook of its
    own (`_pct100` is the transform half, applied where the column is built)."""
    return st.column_config.ProgressColumn(label, min_value=0, max_value=100,
                                            format=PCT_PROGRESS_FORMAT)


def _pct100(v):
    """D9: pre-scale a 0-1 score to 0-100 for `pct_progress_column`. Stays a
    plain float/None (never a formatted string) -- `ProgressColumn` draws the
    bar's fill fraction from the numeric value itself; only the DISPLAY text
    goes through `PCT_PROGRESS_FORMAT`."""
    return None if v is None or pd.isna(v) else float(v) * 100.0


def works_link_named(iid: str, display_name: str) -> str:
    """A10: the works URL plus a `#<urlencoded display name>`
    fragment -- inert for OpenAlex (a fragment never reaches the server, so
    the corpus counted is unchanged), read back by `LinkColumn`'s per-cell
    `display_text=r"#(.*)$"` regex so the INSTITUTION NAME itself becomes the
    clickable link (measurement A10 refuted per-row `display_text`, which
    Streamlit's `column_config.LinkColumn` does not support -- one fixed
    string/regex for the whole column, applied against each row's OWN URL
    value, is the supported mechanism)."""
    return f"{_works_link(iid)}#{quote(display_name, safe='')}"


def _fmt_size(value) -> str:
    """Thousands separator; NA_MARK for missing (: n/a never 0)."""
    if value is None or pd.isna(value):
        return NA_MARK
    return f"{value:,.0f}"


def _rank_under_text(row: dict) -> str:
    """'L1 #4 - L2 #7' style secondary reference; '>50' beyond RANK_VISIBLE_MAX
    (engine already caps at RANK_VISIBLE_MAX and returns None past it).

    : `ref` is keyed by the INTERNAL lens id ("L1"/"L3" -- the engine's
    `rank_under_l1_l3` is unchanged), but the label printed is the DISPLAY
    code (`copy.LENS_DISPLAY_CODE`): "L1" stays "L1", "L3" (topic overlap)
    prints as "L2" now that the eight defaults are renumbered in tab order."""
    ref = row.get("rank_under_other_lenses")
    if not ref:
        return NA_MARK
    parts = []
    for ln in ("L1", "L3"):
        r = ref.get(ln, {}).get("rank")
        disp = copy.LENS_DISPLAY_CODE.get(ln, ln)
        parts.append(f"{disp} #{r}" if r is not None else f"{disp} >{RANK_VISIBLE_MAX}")
    return " · ".join(parts)


def format_rows(rows: list[dict], *, lens: str, depth: int) -> pd.DataFrame:
    """Pure transform: engine `build_rows(.)` output -> the one DataFrame
    shape every `tbl-lens-ranked` render shares (VIZ_SPEC.md S2.4).

    R1/L22: no `badges` kwarg any more; two size columns (`size_full`,
    `size_frac`); `evidence` is whatever lens-specific text the caller set on
    `row["evidence_text"]` (R-B's `evidence.rows_evidence`, wired in by E2),
    NA_MARK when absent or empty -- never a generic "top field" line.

     (A10): `institution` now carries the URL (`works_link_named`),
    rendered as the OpenAlex-works LinkColumn -- the institution NAME is the
    clickable text, and the old separate "OpenAlex works" column is gone
    (`render_ranked_table`). `institution_name` is kept alongside, plain text,
    for anything reading the name without going through the link (the tail
    search's own display, a future non-link consumer)."""
    out = []
    for row in rows:
        iid = row["institution_id"]
        code = str(row["country_code"])
        out.append({
            "rank": row["rank"],
            "institution": works_link_named(iid, str(row["display_name"])),
            "institution_name": row["display_name"],
            "country": countries.name(code),
            "country_code": code,
            "type": str(row["type"]),
            "size_full": _fmt_size(row.get("total_full_2020_2024")),
            "size_frac": _fmt_size(row.get("total_frac_2020_2024")),
            "score": _pct100(row.get("lens_score")),  # D9: pre-scaled 0-100, see pct_progress_column
            "evidence": row.get("evidence_text") or NA_MARK,
            "rank_under": _rank_under_text(row),
            "institution_id": iid,
        })
    df = pd.DataFrame(out)
    df.attrs["lens"] = lens
    df.attrs["depth"] = depth
    return df


def depth_caption(shown: int, total_ranked: int, depth: int, n_tied_extra: int = 0) -> str:
    """VIZ_SPEC.md S2.6, parametric ( -- no typed digit)."""
    tied = f", +{n_tied_extra} tied" if n_tied_extra else ""
    return (f"Showing the top {shown} of {total_ranked} ranked institutions "
            f"(depth {depth}{tied}) -- search the tail below or download the full ranking.")


def render_ranked_table(df: pd.DataFrame, *, key: str, score_form: str = "progress"):
    """`st.dataframe` per the A/B #1 winner: ProgressColumn score, LinkColumn
    institution, hidden id/country_code, NO badge column (R1/L22). Returns
    the selected `institution_id`s (multi-row select) so the caller can offer
    its own "add to comparison" affordance -- composition stays with
    the caller.

     (A10): the institution NAME is now the clickable OpenAlex-works
    link. Measurement A10 refuted a per-row `display_text` (`LinkColumn`
    takes one fixed string/regex for the WHOLE column, a Streamlit API limit,
    not a per-row substitution) -- the fix `format_rows` already applied is a
    `#<urlencoded name>` fragment on the URL itself (inert for OpenAlex) plus
    `display_text=r"#(.*)$"`, which Streamlit applies PER CELL against each
    row's OWN url value (the same mechanism the column_config docs' own
    `streamlit.app` subdomain example demonstrates). `NAME_LINK_MODE` is the
    kill switch this stream's own Playwright render check gates: "fragment"
    (the normal path) makes `institution` itself the LinkColumn; "fallback"
    keeps the institution name a plain TextColumn and re-adds a SEPARATE,
    harmonised-label works-link column, pushed last."""
    assert score_form == "progress", "A/B #1 winner is ProgressColumn (docs/VIZ_SPEC.md S4)"
    if NAME_LINK_MODE == "fragment":
        order = ["rank", "institution", "country", "type",
                 "size_full", "size_frac", "score", "evidence", "rank_under"]
        institution_cfg = st.column_config.LinkColumn(
            copy.FIND["COL_INSTITUTION"], display_text=r"#(.*)$")
    else:
        # fallback (A10, if the render check ever needs it): institution name
        # stays plain text, the works link is its own column, pushed last,
        # under the harmonised label the plan names.
        order = ["rank", "institution_name", "country", "type", "size_full", "size_frac",
                 "score", "evidence", "rank_under", "institution"]
        institution_cfg = st.column_config.LinkColumn(
            WORKS_LINK_FALLBACK_LABEL, display_text=WORKS_LINK_FALLBACK_LABEL)
    event = st.dataframe(
        df,
        hide_index=True,
        width="stretch",  # manager fix 2026-08-29: use_container_width deprecated in 1.61 (warning flood)
        on_select="rerun",
        selection_mode="multi-row",
        key=key,
        column_order=order,
        column_config={
            "rank": st.column_config.NumberColumn("Rank"),
            "institution": institution_cfg,
            "institution_name": st.column_config.TextColumn(copy.FIND["COL_INSTITUTION"]),
            "institution_id": None,
            "country": st.column_config.TextColumn("Country"),
            "country_code": None,
            "type": st.column_config.TextColumn("Type"),
            "size_full": st.column_config.TextColumn(copy.FIND["COL_SIZE_FULL"]),
            "size_frac": st.column_config.TextColumn(copy.FIND["COL_SIZE_FRAC"]),
            "score": pct_progress_column("Score"),  # D9 fix: was format="percent" (comma-decimal live)
            "evidence": st.column_config.TextColumn(copy.FIND["COL_EVIDENCE"]),
            "rank_under": st.column_config.TextColumn("Rank under"),
        },
    )
    rows_sel = event.selection.rows if event and event.selection else []
    return [df.iloc[i]["institution_id"] for i in rows_sel]


def format_concordance(rows: list[dict], *, lenses: list[str], N: int) -> pd.DataFrame:
    """Pure transform: engine `concordance(.)` rows -> the A/B #2 winner's
    k-of-n + hit-lens-chip table (VIZ_SPEC.md S2.3, S4). R1/L22: two size
    columns, country by name (code hidden).

    : `institution` carries the name-link URL like `format_rows`
    (A10); `hit_lenses` is translated through `copy.LENS_DISPLAY_CODE` -- the
    engine's own `hit_lenses` list is INTERNAL ids ("L1", "L3",.), and the
    chips a reader sees must be the same renumbered codes the tabs carry."""
    out = []
    for row in rows:
        code = str(row["country_code"])
        out.append({
            "institution": works_link_named(row["institution_id"], str(row["display_name"])),
            "institution_name": row["display_name"],
            "country": countries.name(code),
            "country_code": code,
            "type": str(row["type"]),
            "k": row["k"],
            "n": row["n"],
            "k_of_n": f"{row['k']} of {row['n']}",
            "hit_lenses": ", ".join(copy.LENS_DISPLAY_CODE.get(h, h) for h in row["hit_lenses"]),
            "size_full": _fmt_size(row.get("total_full_2020_2024")),
            "size_frac": _fmt_size(row.get("total_frac_2020_2024")),
            "institution_id": row["institution_id"],
        })
    df = pd.DataFrame(out)
    df.attrs["N"] = N
    df.attrs["lenses"] = list(lenses)
    return df


def concordance_caption(n_defined: int, N: int, n_rows: int) -> str:
    """Parametric: states N and n per VIZ_SPEC.md S1.6/S2.3."""
    # manager fix 2026-08-29: the engine's concordance returns the
    # tie-inclusive top-50 INCLUDING k=1 rows, so the caption must not assert a k floor.
    return (f"{n_rows} candidates, ranked by how many of the {n_defined} lenses defined "
            f"for this seed place them in their top-{N} (the k column).")


def render_concordance_table(df: pd.DataFrame, *, key: str):
    """`st.dataframe` per the A/B #2 winner: k-of-n + hit-lens chip text.
    Returns selected `institution_id`s, same contract as `render_ranked_table`.

     (A10): same institution-name-as-link mechanism as
    `render_ranked_table`, gated by the SAME `NAME_LINK_MODE`."""
    if NAME_LINK_MODE == "fragment":
        order = ["institution", "country", "type", "k_of_n", "hit_lenses",
                 "size_full", "size_frac"]
        institution_cfg = st.column_config.LinkColumn(
            copy.FIND["COL_INSTITUTION"], display_text=r"#(.*)$")
    else:
        order = ["institution_name", "country", "type", "k_of_n", "hit_lenses",
                 "size_full", "size_frac", "institution"]
        institution_cfg = st.column_config.LinkColumn(
            WORKS_LINK_FALLBACK_LABEL, display_text=WORKS_LINK_FALLBACK_LABEL)
    event = st.dataframe(
        df,
        hide_index=True,
        width="stretch",  # manager fix 2026-08-29: use_container_width deprecated in 1.61 (warning flood)
        on_select="rerun",
        selection_mode="multi-row",
        key=key,
        column_order=order,
        column_config={
            "institution": institution_cfg,
            "institution_name": st.column_config.TextColumn(copy.FIND["COL_INSTITUTION"]),
            "institution_id": None,
            "k": None,
            "n": None,
            "country": st.column_config.TextColumn("Country"),
            "country_code": None,
            "type": st.column_config.TextColumn("Type"),
            "k_of_n": st.column_config.TextColumn("k of n"),
            "hit_lenses": st.column_config.TextColumn("Hit lenses", width="large"),
            "size_full": st.column_config.TextColumn(copy.FIND["COL_SIZE_FULL"]),
            "size_frac": st.column_config.TextColumn(copy.FIND["COL_SIZE_FRAC"]),
        },
    )
    rows_sel = event.selection.rows if event and event.selection else []
    return [df.iloc[i]["institution_id"] for i in rows_sel]
