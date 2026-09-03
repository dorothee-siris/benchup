"""
app/lib/filters.py -- opt-in post-filters applied AFTER ranking, the
"Filtered by." strip, and the emptied-list explainer. Pure functions over `lib.engine.lenses.build_rows`'s row dicts
no Streamlit import, no depth cut (: depth is a
DISPLAY-ONLY cut applied by the caller AFTER these filters, never here).
"""
from __future__ import annotations

from lib import copy
from lib import countries as countries_lib
from lib.app_config import CFG


def apply_filters(rows, *, seed_row, types=None, countries=None, exclude_own_country=False,
                   size_range=None, scale_guard=False, family_min=None, family_scores=None):
    """Predicates only, opt-in, evaluated in this order. `scale_guard`'s ratio
    test -- `max(a,b)/min(a,b) <= ratio` -- reads a single flat ratio from
    config.yaml (no size band). `family_min` thresholds `family_scores`
    (an institution_id -> L0 score dict, e.g. `engine.family_overlap_scores`
    zipped with `ctx["inst_ids"]`) at >= `family_min` (config.yaml
    family_filter_threshold)."""
    seed_total = float(seed_row["total_full_2020_2024"])
    seed_country = str(seed_row["country_code"])
    ratio = CFG["scale_guard"]["ratio"]
    out = []
    for r in rows:
        if types and str(r["type"]) not in types:
            continue
        if countries and str(r["country_code"]) not in countries:
            continue
        if exclude_own_country and str(r["country_code"]) == seed_country:
            continue
        if size_range is not None:
            total = r["total_full_2020_2024"]
            lo, hi = size_range
            if total is None or not (lo <= total <= hi):
                continue
        if scale_guard:
            other = r["total_full_2020_2024"]
            if not other or other <= 0 or seed_total <= 0:
                continue
            if max(seed_total, other) / min(seed_total, other) > ratio:
                continue
        if family_min is not None:
            score = (family_scores or {}).get(r["institution_id"], 0.0)
            if score < family_min:
                continue
        out.append(r)
    return out


def _active_filter_labels(filters: dict, *, scale_guard_removed: int | None = None) -> list[str]:
    """One label per active post-filter, shared by `active_controls_strip`
    and `explain_empty` so the two never drift apart. `scale_guard_removed`
    is the count of candidates the guard alone dropped from the current
    lens's full ranking (None when that count was not computed, e.g. from
    `explain_empty`'s narrower call, in which case the label states only
    the ratio)."""
    labels = []
    types = filters.get("types")
    if types:
        labels.append(copy.STRIP_TYPE.format(types=", ".join(sorted(types))))
    country_codes = filters.get("countries")
    if country_codes:
        # The strip shows country NAMES, sorted by name (not by code).
        names = sorted(countries_lib.name(c) for c in country_codes)
        labels.append(copy.STRIP_COUNTRY.format(countries=", ".join(names)))
    if filters.get("exclude_own_country"):
        labels.append(copy.STRIP_EXCLUDE_OWN_COUNTRY)
    size_range = filters.get("size_range")
    if size_range is not None:
        lo, hi = size_range
        labels.append(copy.STRIP_SIZE_RANGE.format(lo=lo, hi=hi))
    if filters.get("scale_guard"):
        ratio_disp = f"{CFG['scale_guard']['ratio']:g}"
        suffix = (f"; {scale_guard_removed:,} removed from the current lens"
                 if scale_guard_removed is not None else "")
        labels.append(copy.STRIP_SCALE_GUARD.format(ratio=ratio_disp, suffix=suffix))
    family_min = filters.get("family_min")
    if family_min is not None:
        labels.append(copy.STRIP_FAMILY.format(threshold=family_min))
    return labels


def active_controls_strip(*, tree, basis, depth, c1_on, l7_on, filters: dict,
                          scale_guard_removed: int | None = None) -> str | None:
    """None iff tree/basis/depth are all at their CFG default AND C1/L7 are
    off AND every post-filter is inactive. Otherwise names every
    off-default dimension, never a generic "filters active" line."""
    dims = []
    if tree != CFG["scenario"]["tree_default"]:
        dims.append(copy.STRIP_TREE.format(tree=tree))
    if basis == "full":
        dims.append(copy.STRIP_BASIS_FULL)
    if depth != CFG["depth"]["default"]:
        dims.append(copy.STRIP_DEPTH.format(depth=depth))
    if c1_on:
        dims.append(copy.STRIP_C1_ON)
    if l7_on:
        dims.append(copy.STRIP_L7_ON)
    dims.extend(_active_filter_labels(filters, scale_guard_removed=scale_guard_removed))
    if not dims:
        return None
    return copy.STRIP_PREFIX + copy.STRIP_JOIN.join(dims)


def explain_empty(filters: dict, seed_row) -> str:
    """Names the filter(s) responsible for a 0-row list -- / VIZ_SPEC S1.6. Never a generic "no results"."""
    labels = _active_filter_labels(filters)
    joined = copy.EMPTY_STATE_JOIN.join(labels) if labels else copy.NO_ACTIVE_FILTER_LABEL
    return copy.EMPTY_STATE_TEMPLATE.format(filters=joined, seed=seed_row["display_name"])
