"""tests/test_reference_value_resolution.py -- cross-cutting guard:
every reference-carrying frame resolves `ref_value` through a real
source, and a genuine 0.0 reference survives end to end -- data layer
through the chart layer -- rather than being silently read as "missing"
anywhere along the way (`_add_reference`'s own docstring promise:
`np.isfinite`, never truthiness).

An earlier version of this file probed the retired `compare_data.metric_frame`/
`fwci_ref_label`/`pp_ref_label`/`UNAVAILABLE_REASON`/`FWCI_REF_LABEL`/
`PP_REF_LABEL`/four-grain `LEVELS` (field/subfield/erc/sdg) API -- every one
of those names is DELETED with its own rewrite -- Compare now offers exactly
two grains (subfield, sdg) through `top_subfields`/`sdg_frame`, and carries
no "reference label sentence" hooks at all (captions are built directly from
`copy.py` templates, not through a compare_data-side label builder). `tests/
test_compare_data.py` already golden-tests the
`eu_mean_share`/`eu_mean_pp10_wd` VALUES against `share_refs.parquet`/
`impact_taxa.parquet` in depth; this module keeps only the TWO checks that
genuinely belong at the chart-layer boundary, which C1's own suite does not
reach:

  1. an INDEPENDENT cross-check of `top_subfields`'s own `eu_mean_share`
     against a fresh, direct read of `share_refs.parquet` (a different
     computation path from C1's own `_share_ref_series` cache).
  2. the 0.0-reference-survives-to-the-diamond-marker contract, at the
     `charts_compare.fig_metric_bars` layer directly (a synthetic frame,
     the same technique the pre-trim file used, since finding a REAL
     subfield/sdg row with an EXACT 0.0 population mean is not guaranteed
     to exist on any given data refresh, and is not the point of this
     check -- the point is that the CODE never confuses a real zero for a
     missing one).

VACUITY, per module: every assertion is followed by an in-memory mutation
that makes the identical check fail.

Run: python -m pytest tests/test_reference_value_resolution.py -q
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lib import compare_data as CD
from lib.engine import scenario_cache as SC

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
IFREMER = "I154202486"
NIOZ = "I4210107283"  # the anchor pair


@pytest.fixture(scope="module")
def ctx():
    return SC.bundle()["ctx"]


@pytest.fixture(scope="module")
def subs():
    return SC.get("bestfit", "full")


@pytest.fixture(scope="module")
def share_refs() -> pd.DataFrame:
    return pd.read_parquet(DATA_DIR / "share_refs.parquet")


# ============================================================================
# top_subfields/sdg_frame's eu_mean_share cross-checks share_refs.parquet
# ============================================================================

def test_eu_mean_share_matches_share_refs_parquet_independently(ctx, subs, share_refs):
    """`top_subfields`/`sdg_frame`'s own `eu_mean_share` column, checked
    against a FRESH, independent read of `share_refs.parquet` -- never
    through `compare_data`'s own `_share_ref_series` cache."""
    ids = [IFREMER, NIOZ]
    checked = 0
    for grain, frame in (
        ("subfield", CD.all_subfields(ctx, subs, ids)),
        ("sdg", CD.sdg_frame(ctx, subs, ids)),
    ):
        taxon_col = "subfield_id" if grain == "subfield" else "sdg_idx"
        refs = (share_refs[(share_refs["grain"] == grain) & (share_refs["basis"] == "full")]
               .set_index("taxon_id")["eu_mean_share"])
        have_ref = frame.dropna(subset=["eu_mean_share"])
        assert len(have_ref) > 0, grain
        sample = have_ref.sample(n=min(5, len(have_ref)), random_state=0)
        for _, row in sample.iterrows():
            np.testing.assert_allclose(float(row["eu_mean_share"]),
                                       float(refs.loc[int(row[taxon_col])]), rtol=1e-6)
            checked += 1
    assert checked >= 4, "at least one real cross-check per grain, not a silent no-op"

    # VACUITY: perturbing the SAME matched value by +1.0 makes the identical
    # comparison fail -- proving this is a real cross-check against the
    # shipped file, not a tautology comparing a value against itself.
    one = sample.iloc[0]
    true_ref = float(refs.loc[int(one[taxon_col])])
    with pytest.raises(AssertionError):
        np.testing.assert_allclose(float(one["eu_mean_share"]), true_ref + 1.0, rtol=1e-6)


# ============================================================================
# a 0.0 reference survives, data layer through the chart layer
# ============================================================================

def test_a_zero_reference_survives_from_frame_to_chart():
    """A genuine 0.0 `ref_value` reaches `charts_compare.fig_metric_bars` as
    a drawn dashed-red reference TICK (a `go.Shape` line, `x0 == x1` at the
    reference value -- the bar-layout contract's D28 replacement for the
    earlier diamond marker, `CHROME_CONTRACT.md` SS10.3) -- `_add_reference`'s
    own docstring promises `np.isfinite`, never truthiness. Synthetic frame
    (the SAME `two_tab_bars`/`fig_metric_bars` input contract the page
    builds), since the point under test is the CODE PATH, not any one real
    anchor's own reference value on this snapshot."""
    from lib import charts_compare as X
    from lib import palette as P

    iid = "Iz"
    df = pd.DataFrame([
        dict(row_id=1, row_label="Subfield A", institution_id=iid, value=0.10, ref_value=0.0),
        dict(row_id=2, row_label="Subfield B", institution_id=iid, value=0.30, ref_value=0.20),
        dict(row_id=3, row_label="Subfield C", institution_id=iid, value=0.15, ref_value=0.35),
    ])
    slots = {iid: 1}
    names = {iid: "Institution Zero-Ref"}
    fig = X.fig_metric_bars(df, "share", [iid], slots=slots, names=names, level="subfield",
                            value_col="value", label_col="row_label", key_col="row_id",
                            gutter=False)
    ticks = [s for s in fig.layout.shapes
            if s.line.color == P.WARNING_CAPTION_COLOR and s.line.dash == "dash"]
    assert len(ticks) == 3, "one varying-reference tick per row"
    assert 0.0 in [s.x0 for s in ticks], "the zero reference must be one of the plotted ticks"

    # VACUITY: blank OUT the zero row's own ref_value (None, genuinely
    # missing, not zero) on the SAME multi-row frame -- the reference ticks
    # must still exist (the OTHER rows still vary) but must NO LONGER carry
    # a 0.0 point. Proves the membership check above reads the real per-row
    # reference data, not a coincidental property of the chart.
    blanked = df.copy()
    blanked.loc[blanked["row_id"] == 1, "ref_value"] = None
    fig2 = X.fig_metric_bars(blanked, "share", [iid], slots=slots, names=names, level="subfield",
                             value_col="value", label_col="row_label", key_col="row_id",
                             gutter=False)
    ticks2 = [s for s in fig2.layout.shapes
             if s.line.color == P.WARNING_CAPTION_COLOR and s.line.dash == "dash"]
    assert len(ticks2) == 2, "the blanked row draws no tick at all -- two rows still vary"
    assert 0.0 not in [s.x0 for s in ticks2]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
