"""
evals/analysis_eu/lens_lib.py — shared helpers for the R5/R6-prep analysis and
gate scripts (REFINEMENT_PLAN.md S1 R5/R6; METHODS_FAISCEAU.md S2-S3).

Read-only, side-effect-free: loads the new `data/artefacts_eu` tables, builds
dense per-grain institution x category matrices, and implements the two
faisceau methods exactly as METHODS_FAISCEAU.md S2 defines them:

  Method A -- overlap: histogram intersection sum_i min(p_i, q_i) on a SHARE
    vector (sums to 1). Ranks identically to weighted (Ruzicka) Jaccard.
  Method B -- shared specialisations: a specialisation is a category with
    mass >= floor (G6, default 30, on the *fractional* volume column) AND
    SI >= theta (default 1.5). Lens = Jaccard of the two specialisation sets.
    Pre-registered continuous fallback (used when >1/3 of seeds show tied
    top-20 Jaccard values at a grain): overlap (method A's formula) of the
    normalised excess-specialisation profile e_i = max(SI_i - 1, 0) / sum(e).

No global state. Every function takes plain arrays/DataFrames in, returns
plain arrays/DataFrames out. Imports pipeline/agg/* strictly READ-ONLY (never
writes there, never modifies).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RESOURCES = Path(__file__).resolve().parent / "resources"

from .trees_agg import subfield_to_field_map  # noqa: E402 (vendored, see VENDORED_engine.md)

TREES = ("original", "conservative", "bestfit")
G6_FLOOR_DEFAULT = 30.0
THETA_DEFAULT = 1.5
TOP_K_DEFAULT = 20
CONCORDANCE_N_DEFAULT = 20

# D19 face-validity seeds, R2.7 Gdansk anchor = University of Gdansk (Gdansk
# Tech discarded). Short OpenAlex ids, matching data/artefacts_eu institution_id.
D19_SEEDS = [
    ("I39804081", "Sorbonne Université"),
    ("I277688954", "Université Paris-Saclay"),
    ("I899635006", "Université Grenoble Alpes"),
    ("I90183372", "Université de Lorraine"),
    ("I265217849", "IFP Énergies nouvelles (IFPEN)"),
    ("I154202486", "Ifremer"),
    ("I40413290", "University of Gdańsk"),
    ("I161046081", "University of Freiburg"),
    ("I200763008", "Justus-Liebig-Universität Gießen"),
    ("I35440088", "ETH Zurich"),
]
D19_IDS = [i for i, _ in D19_SEEDS]

SDG_LABELS = [
    "No Poverty", "Zero Hunger", "Good Health and Well-being", "Quality Education",
    "Gender Equality", "Clean Water and Sanitation", "Affordable and Clean Energy",
    "Decent Work and Economic Growth", "Industry, Innovation and Infrastructure",
    "Reduced Inequalities", "Sustainable Cities and Communities",
    "Responsible Consumption and Production", "Climate Action", "Life Below Water",
    "Life on Land", "Peace, Justice and Strong Institutions",
]  # SDG 1-16 in sdg_idx order (SDG 17 not covered, D8)


def log(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}", flush=True)


# --------------------------------------------------------------- loading ----

ALL_TABLES = ["index", "index_candidates", "fields", "subfields", "topics_all",
              "topics_dim", "erc", "sdg", "impact_cells"]


def load_artefacts(artefacts_dir: Path, tables: list[str] | None = None) -> dict:
    """Loads the requested artefact parquet tables + manifest.json from
    `artefacts_dir`. Raises FileNotFoundError with the exact missing path if
    a required table is absent (never silently substitutes a default dir
    the Sprint-1 lesson this whole stream is built around)."""
    artefacts_dir = Path(artefacts_dir)
    if not artefacts_dir.exists():
        raise FileNotFoundError(f"--artefacts-dir does not exist: {artefacts_dir}")
    wanted = tables if tables is not None else ALL_TABLES
    out = {}
    for t in wanted:
        p = artefacts_dir / f"{t}.parquet"
        if not p.exists():
            raise FileNotFoundError(f"missing required artefact table: {p}")
        out[t] = pd.read_parquet(p)
    manifest_p = artefacts_dir / "manifest.json"
    out["manifest"] = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {}
    return out


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
    does — R4code.md agg/trees_agg.py:subfield_to_field_map)."""
    m = topics_dim[["field_id", "field_name"]].drop_duplicates()
    assert m["field_id"].is_unique, "field_id -> field_name is not 1:1 in topics_dim"
    return dict(zip(m["field_id"], m["field_name"]))


def load_erc_labels() -> list[str]:
    d = json.loads((RESOURCES / "erc_id2label_verification.json").read_text(encoding="utf-8"))
    assert d["n_panels"] == 28
    return d["id2label"]


def display_name_map(index_df: pd.DataFrame) -> dict:
    return dict(zip(index_df["institution_id"], index_df["display_name"]))


# ------------------------------------------------------------ seed pool ----

def pick_seeds(index_df: pd.DataFrame, seed: int = 42, n_random: int = 40) -> list[str]:
    """D19 (10 ids, guaranteed if present) + n_random random OTHER index
    institutions, fixed seed. Institutions not present in this artefacts_dir's
    index (e.g. a provisional dry-run population) are dropped with a note by
    the caller, not silently assumed present."""
    present = set(index_df["institution_id"])
    d19_present = [i for i in D19_IDS if i in present]
    missing = [i for i in D19_IDS if i not in present]
    if missing:
        log("lens_lib", f"WARNING: D19 seeds absent from this index: {missing}")
    pool = sorted(present - set(d19_present))
    rng = np.random.default_rng(seed)
    n_random = min(n_random, len(pool))
    random_seeds = rng.choice(pool, size=n_random, replace=False).tolist()
    return d19_present + random_seeds


# ------------------------------------------------------- dense matrices -----

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


def subfield_matrices(subfields_df: pd.DataFrame, tree: str, inst_ids: list[str]) -> dict:
    """Dense (n_inst, 252) matrices for one tree: share_frac, vol_frac, si.
    subfield_id columns used as the category axis (int, canonical 252-space)."""
    sub = subfields_df[subfields_df["tree"] == tree]
    cats = sorted(sub["subfield_id"].unique().tolist())
    share, _ = build_dense_matrix(sub, inst_ids, "subfield_id", "share_frac", cats)
    vol, _ = build_dense_matrix(sub, inst_ids, "subfield_id", "vol_frac", cats)
    # SI: NaN below the G6 floor by construction (R4). Keep NaN (not 0) so
    # spec-set / excess-profile logic can tell "no SI" from "SI==0".
    si_wide = sub.pivot_table(index="institution_id", columns="subfield_id", values="si", aggfunc="mean")
    si_wide = si_wide.reindex(index=inst_ids, columns=cats)
    si = si_wide.to_numpy(dtype=np.float64).astype(np.float32)
    return {"share_frac": share, "vol_frac": vol, "si": si, "cats": cats}


def field_matrices(fields_df: pd.DataFrame, tree: str, inst_ids: list[str]) -> dict:
    fld = fields_df[fields_df["tree"] == tree]
    cats = sorted(fld["field_id"].unique().tolist())
    share, _ = build_dense_matrix(fld, inst_ids, "field_id", "share_frac", cats)
    vol, _ = build_dense_matrix(fld, inst_ids, "field_id", "vol_frac", cats)
    return {"share_frac": share, "vol_frac": vol, "cats": cats}


def topic_matrices(topics_all_df: pd.DataFrame, inst_ids: list[str]) -> dict:
    """Dense (n_inst, n_topics) matrices, tree-independent. share_frac (Find,
    share-based L3) and vol_frac (pair view, volume-based L3)."""
    cats = sorted(topics_all_df["topic_id"].unique().tolist())
    share, _ = build_dense_matrix(topics_all_df, inst_ids, "topic_id", "share_frac", cats)
    vol, _ = build_dense_matrix(topics_all_df, inst_ids, "topic_id", "vol_frac", cats)
    return {"share_frac": share, "vol_frac": vol, "cats": cats}


def erc_matrices(erc_df: pd.DataFrame, inst_ids: list[str]) -> dict:
    cats = list(range(28))
    share, _ = build_dense_matrix(erc_df, inst_ids, "panel_idx", "share", cats)
    mass, _ = build_dense_matrix(erc_df, inst_ids, "panel_idx", "mass", cats)
    si_wide = erc_df.pivot_table(index="institution_id", columns="panel_idx", values="si", aggfunc="mean")
    si_wide = si_wide.reindex(index=inst_ids, columns=cats)
    si = si_wide.to_numpy(dtype=np.float64).astype(np.float32)
    return {"share_frac": share, "vol_frac": mass, "si": si, "cats": cats}


def sdg_matrices(sdg_df: pd.DataFrame, inst_ids: list[str]) -> dict:
    cats = list(range(16))
    share, _ = build_dense_matrix(sdg_df, inst_ids, "sdg_idx", "share", cats)
    mass, _ = build_dense_matrix(sdg_df, inst_ids, "sdg_idx", "mass", cats)
    esi_wide = sdg_df.pivot_table(index="institution_id", columns="sdg_idx", values="esi", aggfunc="mean")
    esi_wide = esi_wide.reindex(index=inst_ids, columns=cats)
    esi = esi_wide.to_numpy(dtype=np.float64).astype(np.float32)
    return {"share_frac": share, "vol_frac": mass, "si": esi, "cats": cats}


# ------------------------------------------------------------- Method A -----

def histogram_intersection_row(target_share: np.ndarray, pop_share: np.ndarray) -> np.ndarray:
    """Method A: sum_i min(target_i, pop_i) for a single target row against
    every row of pop_share (both must be share vectors summing to <=1;
    all-zero rows -> intersection 0 with everything, incl. self)."""
    return np.minimum(target_share[None, :], pop_share).sum(axis=1)


def excess_profile(si_row: np.ndarray) -> np.ndarray:
    """e_i = max(SI_i - 1, 0), NaN (below-floor) treated as 0, normalised to
    sum 1 (all-zero -> all-zero, caller must guard div-by-zero downstream)."""
    e = np.maximum(np.nan_to_num(si_row, nan=0.0) - 1.0, 0.0)
    s = e.sum()
    return e / s if s > 0 else e


# ------------------------------------------------------------- Method B -----

def specialisation_mask(vol_row: np.ndarray, si_row: np.ndarray, floor: float, theta: float) -> np.ndarray:
    """Boolean specialisation set for one institution: mass (vol_frac) >=
    floor AND SI >= theta. NaN SI (below-floor by construction) -> False."""
    si_ok = np.nan_to_num(si_row, nan=-np.inf) >= theta
    return (vol_row >= floor) & si_ok


def jaccard_set_row(target_mask: np.ndarray, pop_mask: np.ndarray) -> np.ndarray:
    """Jaccard(target_mask, each row of pop_mask). Union==0 (both empty) ->
    defined as 0.0 (no shared specialisations to report, not undefined)."""
    inter = (target_mask[None, :] & pop_mask).sum(axis=1)
    union = (target_mask[None, :] | pop_mask).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        j = np.where(union > 0, inter / np.maximum(union, 1), 0.0)
    return j.astype(np.float64)


# --------------------------------------------------------- top-k / agree ---

def top_k_excluding_self(scores: np.ndarray, self_idx: int, k: int) -> np.ndarray:
    """Indices of the top-k scores, self excluded, ties broken by index
    (stable) for full reproducibility."""
    s = scores.copy()
    s[self_idx] = -np.inf
    order = np.argsort(-s, kind="stable")
    return order[:k]


def has_ties_in_topk(scores: np.ndarray, self_idx: int, k: int) -> bool:
    """True if the k-th and (k+1)-th ranked scores are exactly equal (a tie
    straddling the top-k boundary) OR any two of the top-k scores are exactly
    equal to each other -- both count as 'ties inside the top-20' for the
    method-B calibration rule."""
    s = scores.copy()
    s[self_idx] = -np.inf
    order = np.argsort(-s, kind="stable")
    top = s[order[:k]]
    if len(top) < k:
        return False
    if len(order) > k and np.isclose(s[order[k - 1]], s[order[k]]):
        return True
    # any internal duplicate value among the top-k (excluding the -inf/self placeholder)
    finite_top = top[np.isfinite(top)]
    return len(finite_top) != len(np.unique(finite_top))


def jaccard_of_lists(a: np.ndarray, b: np.ndarray) -> float:
    sa, sb = set(a.tolist()), set(b.tolist())
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def topk_overlap(a: np.ndarray, b: np.ndarray, k: int) -> float:
    """|top-k(a) ∩ top-k(b)| / k -- the G1/G4-style overlap statistic (fixed
    denominator k, not the general Jaccard)."""
    return len(set(a.tolist()) & set(b.tolist())) / k


def df_to_md_table(df: pd.DataFrame, float_fmt: str = "{:.3f}") -> str:
    """Minimal DataFrame -> markdown-table renderer (no `tabulate` dependency
    in env-nlp; index is rendered as the first column)."""
    cols = [str(df.index.name or "")] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        cells = [str(idx)]
        for v in row:
            cells.append(float_fmt.format(v) if isinstance(v, (int, float, np.floating)) and not pd.isna(v) else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def subfield_id_to_field_id_map(topics_dim: pd.DataFrame) -> dict:
    m = subfield_to_field_map(topics_dim)
    return dict(zip(m["subfield_id"].astype(int), m["field_id"].astype(int)))


# ---- vendored verbatim from evals/analysis_eu/r2/lens_lib_r2.py ----

def excess_profile_matrix(si_matrix: np.ndarray) -> np.ndarray:
    """Row-wise `lens_lib.excess_profile`: e_i = max(SI_i - 1, 0), NaN -> 0,
    each row normalised to sum 1 independently (all-zero row -> all-zero).
    This is L2's r2 scoring vector -- method A (histogram intersection) is
    then applied to these rows exactly like any other share vector."""
    e = np.maximum(np.nan_to_num(si_matrix, nan=0.0) - 1.0, 0.0)
    row_sum = e.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.divide(e, row_sum, out=np.zeros_like(e), where=row_sum > 0)
    return out.astype(np.float32)
