"""tests/test_hatch_rule.py -- BenchUp V4 trim, guards the
caution-channel fork in `charts_compare.fig_metric_bars` (`_is_low_volume`,
`RATIO_HATCH_METRICS`) now that the trim narrows `METRICS` to exactly two
values, `("share", "pp")`.

The FORK ITSELF is unchanged (`_is_low_volume`'s own docstring, verbatim
from the pre-trim build): `pp` cautions on its own per-row `denom_value`
(n_covered) against `palette.RATIO_HATCH_FLOOR` (fifty); every other metric
this builder can still draw (`share`) cautions on `vol_full_annual_mean`
against `LOW_VOLUME_FLOOR` (ten a year, the same threshold in different
units) WHEN its frame carries that column. `two_tab_bars` (D3/D4's own
caller, `charts_compare.py`'s own docstring: "the profile tab never
cautions") never supplies `vol_full_annual_mean` on its `tab="profile"`
frame -- so in practice, on THIS page, only the Impact tab (`pp`) ever
cautions. This file pins both facts: the generic two-branch fork inside
`fig_metric_bars` (built with a synthetic frame, same fixture shape as
before the trim), AND the page-level guarantee that `two_tab_bars`'s
profile tab structurally never triggers the volume-keyed branch because its
own frame contract carries no such column.

VACUITY: the two-row fixture is built so the two candidate rules disagree
(same technique as the pre-trim file) -- a passing result tells you WHICH
rule fired, not just "something was cautioned".

Run from cwd `app/`: python -m pytest tests/test_hatch_rule.py -q
"""
from __future__ import annotations

import pandas as pd
import pytest

from lib import charts as C
from lib import charts_compare as X
from lib import palette as P

IID = "Ix"
NAMES = {IID: "Institution X"}


def _slots():
    return {IID: 1}


def _ink() -> str:
    return P.institution_ink(_slots()[IID])


# Row A: denom_value TINY (< RATIO_HATCH_FLOOR), vol_full_annual_mean AMPLE
#        (>= LOW_VOLUME_FLOOR) -- should caution under the denom-keyed rule
#        (pp) and NOT under the volume-keyed rule (share, when it carries
#        the column at all).
# Row B: the mirror image -- denom_value AMPLE, vol_full_annual_mean TINY
#        should caution under the volume-keyed rule and NOT the denom-keyed one.
assert P.RATIO_HATCH_FLOOR == 50, "fixture below is tuned to the ruled floor of 50"
assert X.LOW_VOLUME_FLOOR == 10.0, "fixture below is tuned to the ruled floor of 10/yr"

ROW_A = dict(taxon_id=1, taxon_label="Taxon A", value=0.20, ref_value=0.5,
            denominator="note", denom_value=10.0,             # < 50
            domain_id=1, domain_order=0,
            vol_display=10.0, vol_full_annual_mean=100.0)    # >= 10/yr
ROW_B = dict(taxon_id=2, taxon_label="Taxon B", value=0.30, ref_value=0.5,
            denominator="note", denom_value=1000.0,           # >= 50
            domain_id=1, domain_order=0,
            vol_display=1000.0, vol_full_annual_mean=2.0)    # < 10/yr


def _frame() -> pd.DataFrame:
    return pd.DataFrame([dict(institution_id=IID, **ROW_A), dict(institution_id=IID, **ROW_B)])


def _render(metric: str):
    """The one real trace this single-institution frame draws -- `gutter=False`
    isolates the caution-CHANNEL assertions below from the separate E6 left-
    gutter-column feature (its own dedicated tests live in
    tests/test_charts_compare.py / tests/test_gutter_and_caution_channel.py)."""
    fig = X.fig_metric_bars(_frame(), metric, [IID], slots=_slots(), names=NAMES,
                            level="field", gutter=False)
    assert len(fig.data) == 1
    return fig.data[0]


def _caution_flags(metric: str) -> list[bool]:
    """[row A cautioned?, row B cautioned?]. Also pins two other invariants
    on the SAME trace: every bar stays SOLID (no SURFACE fill, no pattern
    shape) and every outline keeps the SAME width -- the caution lives in
    text colour alone, nothing about the bar's own geometry changes."""
    tr = _render(metric)
    colors = list(tr.textfont.color)
    assert len(colors) == 2
    ink = _ink()
    assert set(colors) <= {ink, P.WARNING_CAPTION_COLOR}
    assert P.SURFACE not in tr.marker.color
    assert not any(tr.marker.pattern.shape or ())
    assert tr.marker.line.width == C.HAIRLINE_PX
    return [c == P.WARNING_CAPTION_COLOR for c in colors]


def test_pp_cautions_on_denom_value_not_on_volume():
    """Row A (denom<50, vol ample) is cautioned; Row B (denom>=50, vol
    tiny) is NOT -- pp's own denom-keyed rule, plus its converse."""
    flags = _caution_flags("pp")
    assert flags == [True, False], flags
    # VACUITY: not the pattern the volume-keyed rule would draw.
    assert flags != [False, True]


def test_share_cautions_on_volume_when_the_frame_carries_it():
    """`share` is NOT in `RATIO_HATCH_METRICS`, so it falls to the generic
    `vol_full_annual_mean`-keyed branch: Row A (vol ample) is NOT cautioned,
    Row B (vol tiny) IS -- the mirror pattern from `pp`'s own test, proving
    the fork genuinely keys on two DIFFERENT columns rather than one metric
    silently reusing the other's rule."""
    flags = _caution_flags("share")
    assert flags == [False, True], flags
    # VACUITY: not the denom-keyed pattern pp draws on this same fixture.
    assert flags != [True, False]


def test_two_tab_bars_profile_tab_never_cautions_even_with_a_low_volume_row():
    """D3's own rule, stated in `two_tab_bars`'s docstring ("the profile tab
    never cautions"): its `tab="profile"` frame carries no
    `vol_full_annual_mean` column at all, so even a row that WOULD be
    flagged if the column were present renders with no caution ink
    `_is_low_volume`'s own "a frame missing the relevant column is NOT low
    volume" rule, exercised through the real page-facing entry point rather
    than `fig_metric_bars` directly."""
    frame = pd.DataFrame([
        dict(row_id=1, row_label="Subfield A", institution_id=IID, value=0.20, ref_value=0.5),
        dict(row_id=2, row_label="Subfield B", institution_id=IID, value=0.30, ref_value=0.5),
    ])
    assert "vol_full_annual_mean" not in frame.columns
    fig = X.two_tab_bars(frame, "profile", NAMES, _slots(), grouped_by_field=False)
    tr = fig.data[0]
    ink = _ink()
    assert set(tr.textfont.color) == {ink}, tr.textfont.color

    # VACUITY: the SAME two rows, drawn through `fig_metric_bars` DIRECTLY
    # with the low-volume column added, DO caution -- proving the profile
    # tab's silence above is the missing COLUMN's effect, not a fixture
    # that never triggers cautioning at all.
    with_col = frame.copy()
    with_col["vol_full_annual_mean"] = [100.0, 2.0]
    fig2 = X.fig_metric_bars(with_col, "share", [IID], slots=_slots(), names=NAMES,
                             level="subfield", value_col="value", label_col="row_label",
                             key_col="row_id", gutter=False)
    assert P.WARNING_CAPTION_COLOR in list(fig2.data[0].textfont.color)


def test_ratio_hatch_metrics_vocabulary_is_exactly_pp():
    """The fork itself, not just its effect: `RATIO_HATCH_METRICS` must name
    exactly the one metric with a genuinely per-row diagnostic denominator
    that this trimmed chart still draws -- `fwci` is gone with the retired
    selector (C2's own deletion), so it can no longer be a member."""
    assert set(X.RATIO_HATCH_METRICS) == {"pp"}
    assert set(X.RATIO_HATCH_METRICS) <= set(X.METRICS)
    assert set(X.METRICS) == {"share", "pp"}


def test_dagger_still_marks_every_cautioned_value():
    """The caution channel is TEXT COLOUR + dagger together, never colour
    alone -- a reader who cannot distinguish the two inks still sees the
    glyph."""
    for metric in ("pp", "share"):
        tr = _render(metric)
        daggered = [X.LOW_VOLUME_GLYPH in t for t in tr.text]
        cautioned = [c == P.WARNING_CAPTION_COLOR for c in tr.textfont.color]
        assert daggered == cautioned, (metric, daggered, cautioned)
        assert any(cautioned), metric


def test_one_user_facing_sentence_for_both_mechanisms():
    """ONE sentence for every cautioned bar, whichever mechanism triggered
    it -- `HOVER_LOW_VOLUME` is a `{floor}` template filled from
    `palette.RATIO_HATCH_FLOOR`, and it is the SAME string regardless of
    which family cautioned."""
    rendered = {}
    for metric in ("pp", "share"):
        tr = _render(metric)
        hovers = "".join(tr.customdata)
        expected = X.HOVER_LOW_VOLUME.format(floor=X._fmt_vol(P.RATIO_HATCH_FLOOR))
        assert expected in hovers, (metric, hovers)
        rendered[metric] = expected
    assert rendered["pp"] == rendered["share"]  # literally the same rendered sentence

    # VACUITY: the two mechanisms really are different code paths even
    # though they render the same sentence -- proven by the fixture-flip
    # tests above (a metric collapsed onto the wrong rule renders a
    # DIFFERENT caution PATTERN, not a different sentence).
