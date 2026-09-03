"""
app/lib/engine -- BenchUp's pure-python ranking engine. NO Streamlit import anywhere in this package: it takes a data
directory in and returns plain dicts / numpy arrays out, so the golden
regression can drive it headless.

Provenance for every vendored function: VENDORED_engine.md (same folder).
"""
from .derive import derive_shapes
from .evidence import rows_evidence, top_shared_cell
from .l2_vectors import l2_vectors
from .lens_lib import (
    SDG_LABELS, build_dense_matrix, excess_profile_matrix, histogram_intersection_row,
    load_erc_labels, load_subfield_codebook, top_k_excluding_self,
)
from .lenses import (
    ALL_LENSES, CONCORDANCE_N, DEFAULT_LENSES, DEPTH, GOLDEN_CONCORDANCE_LENSES,
    RANK_VISIBLE_MAX, aspirational, aspirational_frontier, base_evidence, build_rows,
    catchall_811_share, competition_ranks, concordance, cut_with_ties, family_overlap_scores,
    is_degenerate, rank_all, rank_map, seed_card, top3_fields_from_l0,
)
from .substrates import (
    BASIS_APPLIES, DEFAULT_BASIS, DEFAULT_TREE, load_context, load_impact_cells, load_substrates,
)
from .trees_agg import G6_FLOOR, TREES

__all__ = [
    "ALL_LENSES", "BASIS_APPLIES", "CONCORDANCE_N", "DEFAULT_BASIS", "DEFAULT_LENSES",
    "DEFAULT_TREE", "DEPTH", "G6_FLOOR", "GOLDEN_CONCORDANCE_LENSES", "RANK_VISIBLE_MAX",
    "SDG_LABELS", "TREES", "aspirational", "aspirational_frontier", "base_evidence", "build_dense_matrix",
    "build_rows", "catchall_811_share", "competition_ranks",
    "concordance", "cut_with_ties", "derive_shapes", "excess_profile_matrix",
    "family_overlap_scores", "histogram_intersection_row", "is_degenerate", "l2_vectors",
    "load_context", "load_erc_labels", "load_impact_cells", "load_substrates", "load_subfield_codebook",
    "rank_all", "rank_map", "rows_evidence", "seed_card", "top3_fields_from_l0",
    "top_k_excluding_self", "top_shared_cell",
]
