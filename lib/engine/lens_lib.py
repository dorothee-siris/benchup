"""
app/lib/engine/lens_lib.py -- shared, side-effect-free helpers used by the
engine's substrate loaders and by the L2 shared-specialisations lens: dense
(institution x category) matrix construction, the histogram-intersection
overlap statistic, top-k selection, and the codebook loaders that map
subfield/field ids to their display names.

No global state. Every function takes plain arrays/DataFrames in, returns
plain arrays/DataFrames out.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RESOURCES = Path(__file__).resolve().parent / "resources"


def load_subfield_codebook() -> tuple[dict, dict]:
    """subfield_id -> subfield_name, subfield_id -> field_name (canonical
    252-subfield codebook; the subfield id space is shared by all three
    trees, so this single codebook labels subfield ids regardless of which
    tree assigned a topic to them)."""
    cb = pd.read_csv(
        RESOURCES / "openalex_subfield_codebook_v1.csv",
        dtype=str, usecols=["subfield_id", "subfield_name", "field_name"],
    )
    cb["subfield_id"] = cb["subfield_id"].astype(int)
    return dict(zip(cb["subfield_id"], cb["subfield_name"])), dict(zip(cb["subfield_id"], cb["field_name"]))


def load_field_name_map(topics_dim: pd.DataFrame) -> dict:
    """field_id -> field_name. Fixed/tree-independent (only topic->subfield
    changes per tree; subfield->field membership, hence field_id/name, never
    does)."""
    m = topics_dim[["field_id", "field_name"]].drop_duplicates()
    assert m["field_id"].is_unique, "field_id -> field_name is not 1:1 in topics_dim"
    return dict(zip(m["field_id"], m["field_name"]))


def build_dense_matrix(
    long_df: pd.DataFrame, inst_ids: list[str], cat_col: str, value_col: str,
    cats: list | None = None,
) -> tuple[np.ndarray, list]:
    """long_df: (institution_id, cat_col, value_col,.) rows -> dense
    (n_inst, n_cats) float32 matrix, institutions reindexed to `inst_ids`
    (missing rows -> all-zero), NaNs -> 0.0. Returns (matrix, cats_used)."""
    if cats is None:
        cats = sorted(long_df[cat_col].unique().tolist())
    wide = long_df.pivot_table(index="institution_id", columns=cat_col, values=value_col, aggfunc="sum")
    wide = wide.reindex(index=inst_ids, columns=cats)
    mat = wide.to_numpy(dtype=np.float64)
    mat = np.nan_to_num(mat, nan=0.0).astype(np.float32)
    return mat, cats


def erc_matrices(erc_df: pd.DataFrame, inst_ids: list[str]) -> dict:
    """Dense (n_inst, 28) ERC panel matrices: share_frac, vol_frac (mass), si.
    Used by the offline scenario-substrate build, precomputed before deployment,
    not by the live app, which reads the precomputed result instead."""
    cats = list(range(28))
    share, _ = build_dense_matrix(erc_df, inst_ids, "panel_idx", "share", cats)
    mass, _ = build_dense_matrix(erc_df, inst_ids, "panel_idx", "mass", cats)
    si_wide = erc_df.pivot_table(index="institution_id", columns="panel_idx", values="si", aggfunc="mean")
    si_wide = si_wide.reindex(index=inst_ids, columns=cats)
    si = si_wide.to_numpy(dtype=np.float64).astype(np.float32)
    return {"share_frac": share, "vol_frac": mass, "si": si, "cats": cats}


def sdg_matrices(sdg_df: pd.DataFrame, inst_ids: list[str]) -> dict:
    """Dense (n_inst, 16) SDG matrices: share_frac, vol_frac (mass), si (esi).
    Same offline-build-only caller as erc_matrices above."""
    cats = list(range(16))
    share, _ = build_dense_matrix(sdg_df, inst_ids, "sdg_idx", "share", cats)
    mass, _ = build_dense_matrix(sdg_df, inst_ids, "sdg_idx", "mass", cats)
    esi_wide = sdg_df.pivot_table(index="institution_id", columns="sdg_idx", values="esi", aggfunc="mean")
    esi_wide = esi_wide.reindex(index=inst_ids, columns=cats)
    esi = esi_wide.to_numpy(dtype=np.float64).astype(np.float32)
    return {"share_frac": share, "vol_frac": mass, "si": esi, "cats": cats}


def histogram_intersection_row(target_share: np.ndarray, pop_share: np.ndarray) -> np.ndarray:
    """sum_i min(target_i, pop_i) for a single target row against every row
    of pop_share (both must be share vectors summing to <=1; all-zero rows
    -> intersection 0 with everything, incl. self)."""
    return np.minimum(target_share[None, :], pop_share).sum(axis=1)


def top_k_excluding_self(scores: np.ndarray, self_idx: int, k: int) -> np.ndarray:
    """Indices of the top-k scores, self excluded, ties broken by index
    (stable) for full reproducibility."""
    s = scores.copy()
    s[self_idx] = -np.inf
    order = np.argsort(-s, kind="stable")
    return order[:k]


def excess_profile_matrix(si_matrix: np.ndarray) -> np.ndarray:
    """Row-wise excess-specialisation profile: e_i = max(SI_i - 1, 0), NaN ->
    0, each row normalised to sum 1 independently (all-zero row -> all-zero).
    This is L2's scoring vector -- histogram intersection is then applied to
    these rows exactly like any other share vector."""
    e = np.maximum(np.nan_to_num(si_matrix, nan=0.0) - 1.0, 0.0)
    row_sum = e.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.divide(e, row_sum, out=np.zeros_like(e), where=row_sum > 0)
    return out.astype(np.float32)
