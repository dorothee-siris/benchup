"""
app/lib/engine/evidence.py -- lens-specific evidence: "the top shared cell" for a
seed/candidate pair under one lens, i.e. the single field/subfield/topic/ERC
panel/SDG that contributes most to that lens's overlap score, replacing the
lens-blind "Top field" evidence line every table showed before R1.

Formula (per lens, mirroring `lenses.rank_all`'s own branch exactly):
  cell = argmax_j min(seed_j, cand_j) over the lens's substrate row pair
  contribution = min(seed_j, cand_j) / denom, where denom is the SAME quantity
                 the lens's own score formula divides by:
                   - the eight plain histogram-intersection lenses (L0, L1,
                     L3, L4, L6, L2f, L5, L7): denom = Sigma_j min(seed_j,
                     cand_j) -- which IS that lens's score (`rank_all`/
                     `lens_lib.histogram_intersection_row` return exactly this
                     sum, no further division), so `score` below equals
                     `rank_all`'s own number and contributions sum to 1.
                   - C1: denom = the seed's own top-20-subfield mass
                     (`build_c1_for_seed`'s `denom`), NOT Sigma_j min
                     mirroring the engine's numerator/denom split (the plan's
                     own instruction for this lens).
                   - F1: same reasoning extended to F1's own numerator/denom
                     split (`rank_all`'s F1 branch divides by the seed's total
                     frontier share, not by Sigma_j min) -- not named
                     explicitly in the plan's C1 sentence, but the identical
                     shape of the formula, so mirrored the same way rather
                     than left inconsistent (documented in progress/R1_B.md
                     as an interpretation, not a literal instruction).
                 Bounded by construction: min_j <= seed_j always, and denom is
                 either Sigma_j min_j (>= any one term) or a seed-only mass
                 that is itself the sum of the seed_j values the min_j terms
                 are drawn from -- so 0 < contribution <= 1 whenever the cell
                 exists.

Namespaces: L0 -> field name, L1/C1/L2f -> subfield name, L3/F1 -> topic name
(topics_dim.parquet, loaded lazily and cached on ctx -- that table is NOT the
five-column topics_all slice `load_context` already holds), L4/L5 -> ERC panel
label (resources/erc_panels.csv), L6/L7 -> SDG label (resources/sdg_labels.csv).

Deviation from the plan's literal signature: `top_shared_cell` takes `ctx` as
its first argument (plan text: `top_shared_cell(subs, lens, seed_idx,
cand_idx)`) because labelling needs `ctx`'s name maps / lazily-cached topic
and resource lookups, which `subs` does not carry. `rows_evidence`'s
signature is unchanged (it already takes `ctx`, the plan's own S9.4 contract).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RESOURCES = Path(__file__).resolve().parent / "resources"
NA = "n/a"

# Which (grain, matrix-kind) each lens reads, and which name namespace labels
# its cells -- mirrors `lenses.rank_all`'s own per-lens branch (share vectors
# for the histogram-intersection lenses, EXCESS vectors for the
# excess-profile lenses L2f/L5/L7).
LENS_MATRIX = {
    "L0": ("l0", "share"), "L1": ("l1", "share"), "L3": ("l3", "share"),
    "L4": ("l4", "share"), "L6": ("l6", "profile"),
    "L2f": ("l2f", "excess"), "L5": ("l5", "excess"), "L7": ("l7", "excess"),
}
LENS_NAMESPACE = {
    "L0": "field", "L1": "subfield", "C1": "subfield", "L2f": "subfield",
    "L3": "topic", "F1": "topic", "L4": "erc", "L5": "erc", "L6": "sdg", "L7": "sdg",
}
TOPIC_LENSES = {"L3", "F1"}


def _topic_name_by_id(ctx: dict) -> dict:
    """Lazy, cached on ctx: `topics_dim.parquet`'s `topic_id -> topic_name`
    (`load_context` only keeps TOPICS_DIM_COLS, which excludes `topic_name`
    this is a second, narrow read of the same file, four bytes on disk
    per row, cached once for the life of the process)."""
    if "topic_name_by_id" not in ctx:
        df = pd.read_parquet(Path(ctx["data_dir"]) / "topics_dim.parquet",
                             columns=["topic_id", "topic_name"])
        ctx["topic_name_by_id"] = dict(zip(df["topic_id"], df["topic_name"]))
    return ctx["topic_name_by_id"]


def _erc_label_by_idx(ctx: dict) -> dict:
    if "erc_panel_label_by_idx" not in ctx:
        df = pd.read_csv(RESOURCES / "erc_panels.csv")
        ctx["erc_panel_label_by_idx"] = dict(zip(df["panel_idx"].astype(int), df["panel_label"]))
    return ctx["erc_panel_label_by_idx"]


def _sdg_label_by_idx(ctx: dict) -> dict:
    if "sdg_label_by_idx" not in ctx:
        df = pd.read_csv(RESOURCES / "sdg_labels.csv")
        ctx["sdg_label_by_idx"] = dict(zip(df["sdg_idx"].astype(int), df["sdg_label"]))
    return ctx["sdg_label_by_idx"]


def _label_for(ctx: dict, lens: str, cell_id) -> str:
    ns = LENS_NAMESPACE[lens]
    if ns == "field":
        return ctx["field_name_by_id"].get(cell_id, f"field {cell_id}")
    if ns == "subfield":
        return ctx["subfield_name_by_id"].get(cell_id, f"subfield {cell_id}")
    if ns == "topic":
        return _topic_name_by_id(ctx).get(cell_id, f"topic {cell_id}")
    if ns == "erc":
        return _erc_label_by_idx(ctx).get(cell_id, f"ERC panel {cell_id}")
    if ns == "sdg":
        return _sdg_label_by_idx(ctx).get(cell_id, f"SDG {cell_id}")
    return str(cell_id)  # pragma: no cover -- LENS_NAMESPACE covers every lens


def _seed_and_pop(subs: dict, lens: str, seed_idx: int):
    """(seed_row, pop_matrix, cats, seed_denom) for one lens. `seed_denom` is
    None for the eight plain lenses (caller falls back to Sigma_j min);
    C1/F1 carry the seed-only mass their own score formula divides by
    (`build_c1_for_seed` / `rank_all`'s F1 branch, module docstring)."""
    if lens == "C1":
        l1 = subs["l1"]
        full_row = l1["share"][seed_idx]
        top20 = np.argsort(-full_row, kind="stable")[:20]
        seed_row = full_row[top20]
        cats = [l1["cats"][j] for j in top20]
        return seed_row, l1["share"][:, top20], cats, float(seed_row.sum())
    if lens == "F1":
        f1 = subs["f1"]
        seed_row = f1["share"][seed_idx]
        return seed_row, f1["share"], f1["cats"], float(seed_row.sum())
    if lens not in LENS_MATRIX:
        return None, None, None, None
    grain, kind = LENS_MATRIX[lens]
    m = subs[grain][kind]
    return m[seed_idx], m, subs[grain]["cats"], None


def top_shared_cell(ctx: dict, subs: dict, lens: str, seed_idx: int, cand_idx: int) -> dict:
    """The single cell that contributes most to `lens`'s overlap score
    between the institution at `seed_idx` and the one at `cand_idx`. Returns
    `{cell_pos, cell_id, label, contribution, score}`; an undefined lens or a
    zero-overlap pair returns `cell_pos=cell_id=None, label="n/a",
    contribution=0.0, score=0.0` (never raises, never a silent gap)."""
    seed_row, pop, cats, seed_denom = _seed_and_pop(subs, lens, seed_idx)
    if seed_row is None:
        return {"cell_pos": None, "cell_id": None, "label": NA, "contribution": 0.0, "score": 0.0}
    cand_row = pop[cand_idx]
    mins = np.minimum(seed_row, cand_row).astype(np.float64)
    summin = float(mins.sum())
    denom = seed_denom if seed_denom is not None else summin
    if denom <= 1e-12 or summin <= 1e-12:
        return {"cell_pos": None, "cell_id": None, "label": NA, "contribution": 0.0, "score": 0.0}
    j = int(np.argmax(mins))
    cell_id = str(cats[j]) if lens in TOPIC_LENSES else int(cats[j])
    score = summin / denom if seed_denom is not None else summin
    return {"cell_pos": j, "cell_id": cell_id, "label": _label_for(ctx, lens, cell_id),
            "contribution": float(mins[j] / denom), "score": float(score)}


def rows_evidence(ctx: dict, subs: dict, lens: str, seed_id: str, cand_ids) -> dict:
    """`{institution_id: "{label} -- {pct:.0%} of the overlap"}` for the
    VISIBLE candidates only (never the whole population, S9.4 contract)
    "n/a" per candidate whose lens is undefined for this pair or whose top
    cell has zero overlap."""
    if lens not in LENS_NAMESPACE:
        return {cid: NA for cid in cand_ids}
    seed_idx = ctx["id_pos"].get(seed_id)
    out = {}
    for cid in cand_ids:
        cand_idx = ctx["id_pos"].get(cid)
        if seed_idx is None or cand_idx is None:
            out[cid] = NA
            continue
        cell = top_shared_cell(ctx, subs, lens, seed_idx, cand_idx)
        out[cid] = NA if cell["cell_id"] is None else f"{cell['label']} — {cell['contribution']:.0%} of the overlap"
    return out
