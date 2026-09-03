"""
app/lib/engine/lenses.py -- ranking, concordance, aspirational-by-impact and
the seed card.

Every formula here is copied from the two campaign generators, not rewritten:

  evals/campaign/gen_lists_recall.py -- rank_map, is_degenerate,
      parse_shape_top3, base_evidence, rank_under_l1_l3, build_seed_card
  evals/campaign_v2/gen_lists_v2.py -- full_sorted_positive,
      top_n_ids_with_ties, top_n_pairs_with_ties, competition_ranks,
      cut_rows_with_ties, base_evidence_v2, build_c1_for_seed,
      build_concordance, build_aspirational_v2, build_catchall_811_share,
      process_seed's per-lens branches (undefined tests + reason strings)

`RANK_VISIBLE_MAX = 50` is gen_lists_v2's own monkey-patched value (the golden
lists were generated with it), not gen_lists_recall's default 100.

Deviations from the sources are listed in VENDORED_engine.md; the load-bearing
ones are (a) the app takes the lens set as a parameter where the generators
hard-coded it, (b) the per-seed functions take an already-built substrate dict
instead of doing their own IO, and (c) `catchall_811_share` groups by the
integer institution position instead of `institution_id` (the column-subsetted
topics_all read -- see substrates.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import lens_lib as L

ALL_LENSES = ["L0", "L1", "L3", "F1", "L2f", "L4", "L5", "L6", "L7", "C1"]
DEFAULT_LENSES = ["L0", "L1", "L3", "F1", "L2f", "L4", "L5", "L6"]          # L1 of the plan
GOLDEN_CONCORDANCE_LENSES = ["L1", "L3", "F1", "L2f", "L4", "L5", "L6"]     # gen_lists_v2
RANK_VISIBLE_MAX = 50
DEPTH = 50
CONCORDANCE_N = 30


# --------------------------------------------------------- tie-aware cuts ---

def full_sorted_positive(scores: np.ndarray, self_idx: int) -> tuple[np.ndarray, np.ndarray]:
    """(indices, scores) of every OTHER institution with score>0, sorted desc,
    ties broken by stable array position -- gen_lists_v2.py verbatim."""
    s = scores.copy()
    s[self_idx] = -np.inf
    order = np.argsort(-s, kind="stable")
    ordered_scores = s[order]
    mask = ordered_scores > 1e-12
    return order[mask], ordered_scores[mask]


def top_n_pairs_with_ties(sorted_idx: np.ndarray, sorted_scores: np.ndarray, n: int):
    """gen_lists_v2.py verbatim."""
    if len(sorted_idx) <= n:
        return sorted_idx, sorted_scores
    cut_score = sorted_scores[n - 1]
    keep = sorted_scores >= cut_score
    return sorted_idx[keep], sorted_scores[keep]


def cut_with_ties(sorted_ids: list, sorted_scores: np.ndarray, n: int) -> tuple[list, np.ndarray]:
    """INDICATOR_SPEC S3's tie rule on an id/score pair: the n highest scores,
    ALL entries tied at the cut included; fewer than n positive scores -> all
    of them, NEVER padded (`top_n_ids_with_ties`, same arithmetic)."""
    sorted_scores = np.asarray(sorted_scores)
    if len(sorted_ids) <= n:
        return list(sorted_ids), sorted_scores
    cut_score = sorted_scores[n - 1]
    keep = sorted_scores >= cut_score
    return [cid for cid, k in zip(sorted_ids, keep) if k], sorted_scores[keep]


def competition_ranks(scores_desc) -> list[int]:
    """Standard competition ranking (1,2,2,4,.) -- gen_lists_v2.py verbatim."""
    ranks = []
    prev = None
    cur_rank = 0
    for i, sc in enumerate(scores_desc, 1):
        if prev is None or sc != prev:
            cur_rank = i
        ranks.append(cur_rank)
        prev = sc
    return ranks


def cut_rows_with_ties(items_sorted: list, key_of, n: int) -> list:
    """gen_lists_v2.py verbatim (concordance's own top-50 cut)."""
    if len(items_sorted) <= n:
        return items_sorted
    cut_key = key_of(items_sorted[n - 1])
    extra = n
    while extra < len(items_sorted) and key_of(items_sorted[extra]) == cut_key:
        extra += 1
    return items_sorted[:extra]


# ------------------------------------------------------------- ranking ------

def rank_map(scores: np.ndarray, self_idx: int, inst_ids: list,
             excluded_positions: frozenset | None = None) -> dict:
    """Full 1-based rank of every OTHER institution -- gen_lists_recall verbatim,
    plus the A6/R2-E pool-exclusion chokepoint: a position in
    `excluded_positions` (`ctx["pool_excluded_positions"]`) is dropped from the
    order BEFORE ranks are assigned, so a surviving institution's rank reads as
    if the excluded one had never been in the population -- never off by the
    excluded row's own place. `excluded_positions=None`/empty is a byte-for-byte
    no-op."""
    order = L.top_k_excluding_self(scores, self_idx, len(inst_ids) - 1)
    if excluded_positions:
        order = [j for j in order if j not in excluded_positions]
    return {inst_ids[j]: rank + 1 for rank, j in enumerate(order)}


def is_degenerate(vec_row: np.ndarray) -> bool:
    """gen_lists_recall verbatim."""
    return bool(np.nansum(vec_row) <= 1e-9)


# ------------------------------------------------------------- evidence -----

def parse_shape_top3(packed: object, field_name_by_id: dict) -> list:
    """gen_lists_recall verbatim."""
    if not isinstance(packed, str) or not packed:
        return []
    pairs = []
    for tok in packed.split("|"):
        fid_s, share_s = tok.split(":")
        pairs.append((int(fid_s), float(share_s)))
    pairs.sort(key=lambda t: -t[1])
    return [{"field_id": fid, "field_name": field_name_by_id.get(fid, f"field {fid}"),
             "share": round(share, 6)} for fid, share in pairs[:3]]


def top3_fields_from_l0(subs: dict, idx: int, field_name_by_id: dict) -> list:
    """R1 bug #5: top-3 fields FOLLOWING THE TREE -- top-3 by share on the
    L0 substrate row (`subs["l0"]["share"][idx]` / `subs["l0"]["cats"]`) of
    whichever (tree, basis) scenario `subs` was built with, same dict shape
    as `parse_shape_top3` ({field_id, field_name, share} rounded 6). On the
    DEFAULT scenario this is verified equal (ids + order) to
    `parse_shape_top3(row['shape_field_bestfit'])` for all 37 golden seeds
    (see progress/R1_B.md) -- both read the same bestfit/frac field shares,
    just from a matrix instead of a packed string."""
    row, cats = subs["l0"]["share"][idx], subs["l0"]["cats"]
    order = np.argsort(-row, kind="stable")[:3]
    return [{"field_id": int(cats[j]), "field_name": field_name_by_id.get(int(cats[j]), f"field {cats[j]}"),
             "share": round(float(row[j]), 6)} for j in order if row[j] > 0]


def base_evidence(cid: str, ctx: dict, subs: dict | None = None) -> dict:
    """gen_lists_recall.base_evidence + gen_lists_v2.base_evidence_v2's
    `type_openalex` line, merged (v2 is what the golden rows carry).

    R1 bug #5: when `subs` is given, `shape_top3_fields` follows subs's own
    (tree, basis) via `top3_fields_from_l0` instead of the fixed bestfit
    packed string; `subs=None` keeps the pre-R1 behaviour byte-for-byte (no
    caller in the golden regression passes subs here)."""
    row = ctx["index_by_id"].loc[cid]
    ev = {
        "institution_id": cid,
        "display_name": row["display_name"],
        "country_code": row["country_code"],
        "type": row["type"],
        "total_full_2020_2024": (None if pd.isna(row["total_full_2020_2024"])
                                 else float(row["total_full_2020_2024"])),
        "total_frac_2020_2024": (None if pd.isna(row["total_frac_2020_2024"])
                                 else float(row["total_frac_2020_2024"])),
        "hhi_subfield": (None if pd.isna(row["hhi_subfield"]) else float(row["hhi_subfield"])),
        "shape_top3_fields": (top3_fields_from_l0(subs, ctx["id_pos"][cid], ctx["field_name_by_id"])
                              if subs is not None
                              else parse_shape_top3(row["shape_field_bestfit"], ctx["field_name_by_id"])),
    }
    type_oa = row.get("type_openalex")
    ev["type_openalex"] = None if (pd.isna(type_oa) or type_oa == ev["type"]) else type_oa
    return ev


def rank_under_l1_l3(cid: str, l1_scores, l1_rmap, l3_scores, l3_rmap, id_pos) -> dict:
    """gen_lists_recall verbatim, with v2's RANK_VISIBLE_MAX = 50."""
    out = {}
    for ln, scores, rmap in (("L1", l1_scores, l1_rmap), ("L3", l3_scores, l3_rmap)):
        r = rmap.get(cid)
        r_visible = r if (r is not None and r <= RANK_VISIBLE_MAX) else None
        out[ln] = {"rank": r_visible, "score": round(float(scores[id_pos[cid]]), 6)}
    return out


def build_rows(ranking: dict, ctx: dict, depth: int, rankings: dict | None = None,
               subs: dict | None = None) -> list[dict]:
    """UI-facing rows for ONE lens (gen_lists_v2.build_rows_v2): tie-inclusive
    cut at `depth`, competition ranks, base evidence, this lens's score and
    when the L1/L3 rankings are supplied -- the cross-lens rank pair.

    R1 bug #5: `subs`, when given, is forwarded to `base_evidence` so every
    row's `shape_top3_fields` follows subs's own (tree, basis); `subs=None`
    keeps the pre-R1 byte-for-byte behaviour (no golden-regression caller
    passes it)."""
    ids, scores = cut_with_ties(ranking["sorted_ids"], ranking["sorted_scores"], depth)
    rows = []
    for rank, cid, sc in zip(competition_ranks(scores), ids, scores):
        ev = base_evidence(cid, ctx, subs)
        ev["rank"] = rank
        ev["lens"] = ranking["lens"]
        ev["lens_score"] = round(float(sc), 6)
        if rankings and "L1" in rankings and "L3" in rankings:
            ev["rank_under_other_lenses"] = rank_under_l1_l3(
                cid, rankings["L1"]["scores"], rankings["L1"]["rmap"],
                rankings["L3"]["scores"], rankings["L3"]["rmap"], ctx["id_pos"])
        rows.append(ev)
    return rows


# ------------------------------------------------------------------ C1 ------

def build_c1_for_seed(idx: int, ctx: dict, l1_sub: dict):
    """gen_lists_v2.build_c1_for_seed verbatim (itself gen_lists_recall's own
    C1 formula): L1 restricted to the seed's top-20 subfields, seed-relative
    normalisation so the seed scores 1.0 against itself."""
    l1_full_row = l1_sub["share"][idx]
    top20_col_idx = np.argsort(-l1_full_row, kind="stable")[:20]
    seed_sub_vec = l1_full_row[top20_col_idx]
    denom = float(seed_sub_vec.sum())
    top20_subfields_evidence = [
        {"subfield_id": int(l1_sub["cats"][j]),
         "name": ctx["subfield_name_by_id"].get(int(l1_sub["cats"][j]), f"subfield {l1_sub['cats'][j]}"),
         "share_frac": round(float(l1_full_row[j]), 6)}
        for j in top20_col_idx if l1_full_row[j] > 0
    ]
    undef = denom <= 1e-9
    if undef:
        return None, True, {"seed_top20_subfields": top20_subfields_evidence,
                            "seed_mass_in_top20_subfields": round(denom, 6)}
    sub_pop = l1_sub["share"][:, top20_col_idx]
    numerator = np.minimum(seed_sub_vec[None, :], sub_pop).sum(axis=1)
    scores = numerator / denom
    return scores, False, {"seed_top20_subfields": top20_subfields_evidence,
                           "seed_mass_in_top20_subfields": round(denom, 6)}


# --------------------------------------------------------------- rank_all ---

def rank_all(ctx: dict, subs: dict, seed_id: str, lenses=None) -> dict:
    """Full-population ranking per lens (self excluded, positive scores only,
    stable tie-break by population position). The per-lens branches, undefined
    tests and reason strings are gen_lists_v2.process_seed's, verbatim.

    A6/R2-E: `ctx["pool_excluded_positions"]` (built once in
    `load_context`, empty until the pipeline ships the `pool_excluded` column)
    is read HERE, in the one shared `_emit` every lens branch below calls
    not per lens -- so a flagged institution (a funder surfacing as a
    performer, or a duplicate row a canonical id already covers) can never
    surface as a CANDIDATE in any lens's `sorted_ids`, in the concordance pool
    `concordance` builds from those `sorted_ids`, or in the aspirational pool
    `aspirational`/`aspirational_frontier` cut from the L1 ranking's own
    `sorted_ids` -- one filter, inherited downstream by construction, never a
    second exclusion test written against any of those callers."""
    lenses = list(ALL_LENSES if lenses is None else lenses)
    idx = ctx["id_pos"][seed_id]
    inst_ids = ctx["inst_ids"]
    excluded_positions = ctx.get("pool_excluded_positions") or frozenset()
    out = {}

    def _emit(name, scores, undef, reason, evidence=None):
        if undef or scores is None:
            out[name] = {"lens": name, "seed_id": seed_id, "undefined": True, "reason": reason,
                         "sorted_ids": [], "sorted_scores": np.array([], dtype=float),
                         "sorted_idx": np.array([], dtype=int), "scores": None, "rmap": {},
                         "evidence": evidence or {}}
            return
        sorted_idx, sorted_scores = full_sorted_positive(scores, idx)
        if excluded_positions:
            keep = ~np.isin(sorted_idx, np.fromiter(excluded_positions, dtype=sorted_idx.dtype))
            sorted_idx, sorted_scores = sorted_idx[keep], sorted_scores[keep]
        out[name] = {"lens": name, "seed_id": seed_id, "undefined": False, "reason": None,
                     "sorted_ids": [inst_ids[i] for i in sorted_idx],
                     "sorted_scores": sorted_scores, "sorted_idx": sorted_idx,
                     "scores": scores, "rmap": rank_map(scores, idx, inst_ids, excluded_positions),
                     "evidence": evidence or {}}

    if "L0" in lenses:
        row = subs["l0"]["share"][idx]
        undef = is_degenerate(row)
        _emit("L0", None if undef else L.histogram_intersection_row(row, subs["l0"]["share"]), undef,
              None if not undef else "seed has ~0 mass across all 26 fields")

    if "L1" in lenses:
        row = subs["l1"]["share"][idx]
        undef = is_degenerate(row)
        _emit("L1", None if undef else L.histogram_intersection_row(row, subs["l1"]["share"]), undef,
              None if not undef else "seed's default-scenario subfield share vector is empty")

    if "L3" in lenses:
        row = subs["l3"]["share"][idx]
        undef = is_degenerate(row)
        _emit("L3", None if undef else L.histogram_intersection_row(row, subs["l3"]["share"]), undef,
              None if not undef else "seed's default-scenario topic share vector is empty")

    if "F1" in lenses:
        f1_row = subs["f1"]["share"][idx]
        seed_frontier_share = float(f1_row.sum())
        undef = seed_frontier_share <= 1e-9
        scores = None
        if not undef:
            scores = np.minimum(f1_row[None, :], subs["f1"]["share"]).sum(axis=1) / seed_frontier_share
        _emit("F1", scores, undef,
              None if not undef else "seed has ~0 mass in top25pct-frontier topics",
              {"seed_frontier_share": round(seed_frontier_share, 6)})

    if "L2f" in lenses:
        row = subs["l2f"]["excess"][idx]
        n_eligible = int(subs["l2f"]["eligible"][idx].sum())
        undef = is_degenerate(row)
        _emit("L2f", None if undef else L.histogram_intersection_row(row, subs["l2f"]["excess"]), undef,
              None if not undef else
              f"seed's excess-SI vector is empty under candidate (f), papers>=30 (n_eligible_cells={n_eligible})",
              {"n_eligible_cells": n_eligible})

    if "L4" in lenses:
        row = subs["l4"]["share"][idx]
        undef = is_degenerate(row)
        _emit("L4", None if undef else L.histogram_intersection_row(row, subs["l4"]["share"]), undef,
              None if not undef else "seed has ~0 ERC-classified mass over the 28 panels")

    if "L5" in lenses:
        row = subs["l5"]["excess"][idx]
        undef = is_degenerate(row)
        _emit("L5", None if undef else L.histogram_intersection_row(row, subs["l5"]["excess"]), undef,
              None if not undef else "seed's excess-SI vector is empty over the 28 ERC panels")

    if "L6" in lenses:
        raw_row = subs["l6"]["raw_share"][idx]
        undef = is_degenerate(raw_row)
        _emit("L6", None if undef else L.histogram_intersection_row(subs["l6"]["profile"][idx],
                                                                    subs["l6"]["profile"]), undef,
              None if not undef else
              "seed has ~0 SDG-tagged mass (raw multi-label share sums to 0 over all 16 SDGs)")

    if "L7" in lenses:
        row = subs["l7"]["excess"][idx]
        undef = is_degenerate(row)
        _emit("L7", None if undef else L.histogram_intersection_row(row, subs["l7"]["excess"]), undef,
              None if not undef else "seed's excess-ESI vector is empty over the 16 SDGs")

    if "C1" in lenses:
        scores, undef, extra = build_c1_for_seed(idx, ctx, subs["l1"])
        _emit("C1", scores, undef,
              None if not undef else
              "seed's default-scenario share vector is empty (no classified subfield mass)", extra)

    return out


def family_overlap_scores(ctx: dict, subs: dict, seed_id: str) -> np.ndarray:
    """The L0 (field-grain) score vector -- what the opt-in family post-filter
    thresholds (L6 of the plan, `family_filter_threshold` 0.7)."""
    idx = ctx["id_pos"][seed_id]
    return L.histogram_intersection_row(subs["l0"]["share"][idx], subs["l0"]["share"])


# ---------------------------------------------------------- concordance -----

def concordance(ctx: dict, rankings: dict, lenses=None, N: int = CONCORDANCE_N) -> list[dict]:
    """gen_lists_v2.build_concordance for ONE N, with the lens set as a
    parameter (the generator hard-coded its 7). k = # of DEFINED lenses whose
    tie-aware top-N contains the candidate; n = # defined. Order: (-k, mean
    rank over the HIT lenses only, id); tie-inclusive cut at 50; competition
    ranks on the (k, mean_rank) key."""
    lenses = list(GOLDEN_CONCORDANCE_LENSES if lenses is None else lenses)
    defined = [ln for ln in lenses if ln in rankings and not rankings[ln]["undefined"]]
    n_defined = len(defined)

    per_lens_ids = {ln: set(cut_with_ties(rankings[ln]["sorted_ids"],
                                          rankings[ln]["sorted_scores"], N)[0]) for ln in defined}
    candidate_pool = set()
    for s in per_lens_ids.values():
        candidate_pool |= s

    rows_data = []
    for cid in candidate_pool:
        hit_lenses = [ln for ln in defined if cid in per_lens_ids[ln]]
        k = len(hit_lenses)
        mean_rank = float(np.mean([rankings[ln]["rmap"].get(cid, 10 ** 9) for ln in hit_lenses]))
        rows_data.append((cid, k, mean_rank, hit_lenses))
    rows_data.sort(key=lambda t: (-t[1], t[2], t[0]))
    top50 = cut_rows_with_ties(rows_data, key_of=lambda t: (t[1], t[2]), n=50)

    rows_out = []
    prev_key = None
    cur_rank = 0
    for i, (cid, k, mean_rank, hit_lenses) in enumerate(top50, 1):
        key = (k, mean_rank)
        if prev_key is None or key != prev_key:
            cur_rank = i
        prev_key = key
        ev = base_evidence(cid, ctx)
        ev["rank"] = cur_rank
        ev["lens"] = "concordance"
        ev["k"] = k
        ev["n"] = n_defined
        ev["mean_rank_of_hit_lenses"] = round(mean_rank, 2)
        ev["hit_lenses"] = hit_lenses
        rows_out.append(ev)
    return rows_out


# -------------------------------------------------------- aspirational ------

def aspirational(ctx: dict, l1_ranking: dict, pool: int = DEPTH) -> list[dict]:
    """gen_lists_v2.build_aspirational_v2 verbatim: the L1 top-`pool`
    (tie-inclusive) filtered to pp_top10_frac > seed AND pp_ci_low > seed
    pp_ci_high, KEPT IN L1-OVERLAP ORDER (L4 of the plan -- never re-sorted by
    PP; that is what the golden pins)."""
    index_by_id = ctx["index_by_id"]
    iid = l1_ranking["seed_id"]
    seed_row = index_by_id.loc[iid]
    seed_pp, seed_ci_high = seed_row["pp_top10_frac"], seed_row["pp_ci_high"]

    pool_ids, _ = cut_with_ties(l1_ranking["sorted_ids"], l1_ranking["sorted_scores"], pool)

    qualified = []
    for cid in pool_ids:
        r = index_by_id.loc[cid]
        pp, ci_low = r["pp_top10_frac"], r["pp_ci_low"]
        if pd.isna(pp) or pd.isna(seed_pp) or pd.isna(ci_low) or pd.isna(seed_ci_high):
            continue
        if pp > seed_pp and ci_low > seed_ci_high:
            qualified.append(cid)

    rows = []
    for rank, cid in enumerate(qualified, 1):
        ev = base_evidence(cid, ctx)
        ev["rank"] = rank
        ev["lens"] = "aspirational_by_impact"
        ev["lens_score_L1_overlap"] = round(float(l1_ranking["scores"][ctx["id_pos"][cid]]), 6)
        r = index_by_id.loc[cid]
        ev["pp_top10_frac"] = float(r["pp_top10_frac"])
        ev["pp_ci_low"] = float(r["pp_ci_low"])
        ev["pp_ci_high"] = float(r["pp_ci_high"])
        rows.append(ev)
    return rows


def aspirational_frontier(ctx: dict, l1_ranking: dict, f1_ranking: dict | None,
                          pool: int = DEPTH) -> list[dict]:
    """A-frontier, ported from `evals/aspirational_R2/REPORT.md`
    S1: the SAME L1 top-`pool` (tie-inclusive) look-alike pool `aspirational`
    draws on, RE-RANKED by the F1 (frontier-topic overlap) score instead of
    filtered by impact. Used as the aspirational view's fallback for a seed
    whose V0 (`aspirational`) returns no row -- ETH Zurich in the R2
    campaign, a seed already near the impact ceiling of its own look-alike
    pool -- never as a replacement for V0 where V0 has something to show
    (REPORT.md S3.1: V0 holds up for ordinary universities).

    Candidates absent from F1's positive-score ranking (F1 undefined, or the
    candidate scored exactly zero) sort last, at an explicit zero rather than
    being dropped -- the pool is the SAME pool, just reordered, so nobody who
    qualified for L1 disappears here. `sorted` is stable, so ties in the F1
    score keep the pool's own L1-overlap order (`pool_ids` is already sorted by
    it), matching the campaign generator's tie behaviour.

    Because `pool_ids` is cut from `l1_ranking["sorted_ids"]`, which
    `rank_all`'s shared `_emit` has already dropped every `pool_excluded`
    position from, this pool inherits that exclusion for free (module
    docstring): no separate filter is written here."""
    index_by_id = ctx["index_by_id"]
    pool_ids, _ = cut_with_ties(l1_ranking["sorted_ids"], l1_ranking["sorted_scores"], pool)

    f1_by_id: dict = {}
    if f1_ranking is not None and not f1_ranking["undefined"]:
        f1_by_id = dict(zip(f1_ranking["sorted_ids"], (float(s) for s in f1_ranking["sorted_scores"])))

    ordered = sorted(pool_ids, key=lambda cid: -f1_by_id.get(cid, 0.0))

    rows = []
    for rank, cid in enumerate(ordered, 1):
        ev = base_evidence(cid, ctx)
        ev["rank"] = rank
        ev["lens"] = "aspirational_by_frontier"
        ev["lens_score_L1_overlap"] = round(float(l1_ranking["scores"][ctx["id_pos"][cid]]), 6)
        ev["lens_score_F1_overlap"] = round(f1_by_id.get(cid, 0.0), 6)
        r = index_by_id.loc[cid]
        ev["pp_top10_frac"] = None if pd.isna(r["pp_top10_frac"]) else float(r["pp_top10_frac"])
        ev["pp_ci_low"] = None if pd.isna(r["pp_ci_low"]) else float(r["pp_ci_low"])
        ev["pp_ci_high"] = None if pd.isna(r["pp_ci_high"]) else float(r["pp_ci_high"])
        rows.append(ev)
    return rows


# ----------------------------------------------------------- catch-all ------

def catchall_811_share(ctx: dict) -> dict:
    """gen_lists_v2.build_catchall_811_share: per-institution sum of
    topics_all.share_frac over topics flagged `topics_dim.is_excluded`.
    Grouped by integer institution position (topics_all is read without
    `institution_id` -- substrates.py), which is the same grouping."""
    td = ctx["topics_dim_df"]
    excluded = set(td.loc[td["is_excluded"] == True, "topic_id"])  # noqa: E712
    excl_cols = np.array(sorted(ctx["topic_pos"][t] for t in excluded if t in ctx["topic_pos"]),
                         dtype=np.int32)
    mask = np.isin(ctx["ta_topic"], excl_cols)
    tot = np.bincount(ctx["ta_inst"][mask],
                      weights=ctx["ta_share"][mask].astype(np.float64), minlength=ctx["n"])
    return {iid: float(tot[i]) for i, iid in enumerate(ctx["inst_ids"])}


# ----------------------------------------------------------- seed card ------

def seed_card(ctx: dict, seed_id: str, subs: dict | None = None, catchall: dict | None = None) -> dict:
    """gen_lists_recall.build_seed_card + the four fields gen_lists_v2's
    process_seed appends (total_frac, catch-all share, n eligible L2f
    subfields, type_openalex).

    R1 bug #5: `shape_top3_fields` follows `subs`'s own (tree, basis) via
    `top3_fields_from_l0` (both call sites -- the golden test and
    views_find.py -- always pass subs; `subs=None` is a defensive fallback to
    the pre-R1 fixed bestfit string, and `top5_subfields_default_scenario`
    is then empty since it has no other source). `top5_subfields_default_scenario`
    was ALREADY tree-aware before R1 (`subs["l1"]["share"]`), unchanged here."""
    idx = ctx["id_pos"][seed_id]
    row = ctx["index_by_id"].loc[seed_id]
    if subs is not None:
        l1_share_row, l1_cats = subs["l1"]["share"][idx], subs["l1"]["cats"]
        order = np.argsort(-l1_share_row)[:5]
        top5 = [{"subfield_id": int(l1_cats[j]),
                 "name": ctx["subfield_name_by_id"].get(int(l1_cats[j]), f"subfield {l1_cats[j]}"),
                 "share_frac": round(float(l1_share_row[j]), 6)}
                for j in order if l1_share_row[j] > 0]
        top3 = top3_fields_from_l0(subs, idx, ctx["field_name_by_id"])
    else:
        top5 = []
        top3 = parse_shape_top3(row["shape_field_bestfit"], ctx["field_name_by_id"])
    card = {
        "institution_id": seed_id, "display_name": row["display_name"],
        "country_code": row["country_code"], "type": row["type"],
        "total_full_2020_2024": (None if pd.isna(row["total_full_2020_2024"])
                                 else float(row["total_full_2020_2024"])),
        "hhi_subfield": (None if pd.isna(row["hhi_subfield"]) else float(row["hhi_subfield"])),
        "breadth_subfields": (None if pd.isna(row["breadth_subfields"])
                              else int(row["breadth_subfields"])),
        "shape_top3_fields": top3,
        "erc_classified_mass_frac": (None if pd.isna(row["erc_classified_mass_frac"])
                                     else float(row["erc_classified_mass_frac"])),
        "sdg_tagged_share": (None if pd.isna(row["sdg_tagged_share"])
                             else float(row["sdg_tagged_share"])),
        "sdg_classified_mass_frac": (None if pd.isna(row["sdg_classified_mass_frac"])
                                     else float(row["sdg_classified_mass_frac"])),
        "frontier_top25_share_index": (None if pd.isna(row["frontier_top25_share"])
                                       else float(row["frontier_top25_share"])),
        "top5_subfields_default_scenario": top5,
    }
    card["total_frac_2020_2024"] = (None if pd.isna(row["total_frac_2020_2024"])
                                    else float(row["total_frac_2020_2024"]))
    if catchall is None:
        catchall = catchall_811_share(ctx)
    card["catchall_811_share"] = float(catchall.get(seed_id, 0.0))
    card["n_eligible_subfields_L2f"] = (int(subs["l2f"]["eligible"][idx].sum())
                                        if subs is not None else None)
    type_oa = row.get("type_openalex")
    card["type_openalex"] = None if (pd.isna(type_oa) or type_oa == row["type"]) else type_oa
    return card
