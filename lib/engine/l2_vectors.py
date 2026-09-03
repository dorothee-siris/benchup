"""
app/lib/engine/l2_vectors.py -- vendored subset of `pipeline/agg/l2_variants.py`: only the per-cell public API `l2_vectors` and the
three private helpers it calls (`_apply_variant`, `_raw_scenario`,
`_dense_from_scenario`), copied VERBATIM. The 11-candidate campaign runner, the
binomial-thinning stability test, the self-test and the CLI stay upstream.

See the upstream module docstring for the candidate definitions; the app only
ever uses variant "f" (paper-count floor 30), which is L2f. Deviations from the
source are limited to the import block (relative imports, no sys.path surgery)
and are listed in VENDORED_engine.md.
"""
from __future__ import annotations

import functools

import numpy as np
import pandas as pd

from . import lens_lib as L
from .derive import derive_shapes

VALID_VARIANTS = ("a", "b", "d", "e", "f", "ef")


# ------------------------------------------------------------- core arithmetic

def _apply_variant(
    m: np.ndarray, n: np.ndarray, share: np.ndarray, mean_share_row: np.ndarray,
    inst_total_mass: np.ndarray, variant: str, params: dict,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray, np.ndarray]:
    """All of m/n/share: (n_rows, n_cats) float64, aligned to the same `cats`
    axis. mean_share_row: (n_cats,) -- the FIXED population statistic (never
    recomputed here; the caller decides whether `share` is a full-population
    row or a binomial-thinned half). inst_total_mass: (n_rows,) -- Sigma_j
    m_ij for whichever population `share`'s rows actually represent (the
    institution's own total normally, a HALF's own total when scoring a
    split -- G1's "normalized within each half's own total" convention).
    Returns (eligible bool matrix, si_star matrix-or-None, value matrix used
    for excess (si_star if shrinkage else si), excess float32 matrix -- each
    row max(value-1,0) on eligible cells only, normalised to sum 1, all-zero
    if no eligible cell has positive excess)."""
    if variant not in VALID_VARIANTS:
        raise ValueError(f"variant must be one of {VALID_VARIANTS}, got {variant!r}")
    with np.errstate(invalid="ignore", divide="ignore"):
        si = np.divide(share, mean_share_row[None, :], out=np.zeros_like(share),
                        where=mean_share_row[None, :] > 0)

    si_star = None
    if variant == "a":
        eligible = m >= 30.0
    elif variant == "b":
        eligible = m >= 10.0
    elif variant == "d":
        p = params["p"]
        thresh = np.maximum(10.0, p * inst_total_mass[:, None])
        eligible = m >= thresh
    elif variant == "f":
        eligible = n >= 30.0
    elif variant in ("e", "ef"):
        kappa = params["kappa"]
        with np.errstate(invalid="ignore", divide="ignore"):
            s_star = (n * share + kappa * mean_share_row[None, :]) / (n + kappa)
            si_star = np.divide(s_star, mean_share_row[None, :], out=np.zeros_like(s_star),
                                 where=mean_share_row[None, :] > 0)
        eligible = np.ones_like(m, dtype=bool) if variant == "e" else (n >= 30.0)
    else:  # pragma: no cover -- guarded above
        raise ValueError(variant)

    value = si_star if si_star is not None else si
    excess_raw = np.where(eligible, np.maximum(value - 1.0, 0.0), 0.0)
    row_sum = excess_raw.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        excess = np.divide(excess_raw, row_sum, out=np.zeros_like(excess_raw), where=row_sum > 0)
    return eligible, si_star, value, excess.astype(np.float32)


@functools.lru_cache(maxsize=8)
def _raw_scenario(topics_all_path: str, topics_dim_path: str, tree: str, basis: str, exclude_811: bool):
    """derive_shapes(., g6_floor=0.0) -- unfloored substrate shared by every
    candidate (eligibility is decided in THIS module, independently of
    derive.py's own G6 floor). Cached: the whole campaign calls this exactly
    once per (tree, basis, exclude_811) scenario, regardless of how many of
    the 11 candidates are run against it."""
    subfields_df, _ = derive_shapes(
        topics_all_path, topics_dim_path, tree=tree, basis=basis,
        exclude_811=exclude_811, index_institution_ids=None, g6_floor=0.0,
    )
    return subfields_df


def _dense_from_scenario(topics_all_path, topics_dim_path, tree, basis, exclude_811):
    """One-time (institution x subfield) dense substrate for a scenario:
    m, n, share (float64), mean_share_row, inst_total_mass, inst_ids, cats."""
    subfields_df = _raw_scenario(str(topics_all_path), str(topics_dim_path), tree, basis, exclude_811)
    share_col = "share_frac" if basis == "frac" else "share_full"
    inst_ids = sorted(subfields_df["institution_id"].unique().tolist())
    cats = sorted(subfields_df["subfield_id"].unique().tolist())
    m, _ = L.build_dense_matrix(subfields_df, inst_ids, "subfield_id", "vol_frac", cats)
    n, _ = L.build_dense_matrix(subfields_df, inst_ids, "subfield_id", "vol_full", cats)
    share, _ = L.build_dense_matrix(subfields_df, inst_ids, "subfield_id", share_col, cats)
    mean_share_row = subfields_df.groupby("subfield_id")[share_col].mean().reindex(cats).to_numpy(dtype=np.float64)
    inst_total_mass = subfields_df.groupby("institution_id")["vol_frac"].sum().reindex(inst_ids).fillna(0.0).to_numpy()
    return {
        "subfields_df": subfields_df, "share_col": share_col,
        "inst_ids": inst_ids, "cats": cats,
        "m": m.astype(np.float64), "n": n.astype(np.float64), "share": share.astype(np.float64),
        "mean_share_row": mean_share_row, "inst_total_mass": inst_total_mass,
    }


# --------------------------------------------------------------- public API

def l2_vectors(
    topics_all_path, topics_dim_path, tree: str = "bestfit", basis: str = "frac",
    exclude_811: bool = False, variant: str = "a", params: dict | None = None,
) -> pd.DataFrame:
    """Returns (institution_id, subfield_id, m, n, share, si, si_star,
    eligible) -- one row per (institution, subfield) cell with nonzero mass
    in this scenario (the same sparse convention as the shipped
    subfields.parquet / derive_shapes' own output -- a truly-zero cell is
    never represented, not silently 0-filled)."""
    params = params or {}
    dense = _dense_from_scenario(topics_all_path, topics_dim_path, tree, basis, exclude_811)
    eligible, si_star, _value, _excess = _apply_variant(
        dense["m"], dense["n"], dense["share"], dense["mean_share_row"], dense["inst_total_mass"], variant, params,
    )
    with np.errstate(invalid="ignore", divide="ignore"):
        si = np.divide(dense["share"], dense["mean_share_row"][None, :], out=np.zeros_like(dense["share"]),
                        where=dense["mean_share_row"][None, :] > 0)

    sub = dense["subfields_df"]
    id_pos = {iid: i for i, iid in enumerate(dense["inst_ids"])}
    cat_pos = {c: i for i, c in enumerate(dense["cats"])}
    ii = sub["institution_id"].map(id_pos).to_numpy()
    jj = sub["subfield_id"].map(cat_pos).to_numpy()
    out = pd.DataFrame({
        "institution_id": sub["institution_id"].to_numpy(),
        "subfield_id": sub["subfield_id"].to_numpy(),
        "m": dense["m"][ii, jj],
        "n": np.rint(dense["n"][ii, jj]).astype("int64"),
        "share": dense["share"][ii, jj],
        "si": si[ii, jj],
        "si_star": (si_star[ii, jj] if si_star is not None else np.full(len(sub), np.nan)),
        "eligible": eligible[ii, jj],
    })
    return out
