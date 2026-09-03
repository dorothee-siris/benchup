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


def _scale_guard_multiplier(seed_total: float) -> float:
    """config.yaml scale_guard bands (M5.6/H15): a single multiplier is not
    band-safe. `seed_total` is the SEED's total_full_2020_2024."""
    sg = CFG["scale_guard"]
    return sg["lt_20k"] if seed_total < sg["band_threshold_works"] else sg["ge_20k"]


def apply_filters(rows, *, seed_row, types=None, countries=None, exclude_own_country=False,
                   size_range=None, scale_guard=False, family_min=None, family_scores=None):
    """Predicates only, opt-in, evaluated in this order. `scale_guard`'s ratio
    test -- `max(a,b)/min(a,b) <= m` -- is the same scale-guard form the
    reference implementation uses, m from `_scale_guard_multiplier`
    banded on the SEED's size. `family_min` thresholds `family_scores`
    (an institution_id -> L0 score dict, e.g. `engine.family_overlap_scores`
    zipped with `ctx["inst_ids"]`) at >= `family_min` (config.yaml
    family_filter_threshold)."""
    seed_total = float(seed_row["total_full_2020_2024"])
    seed_country = str(seed_row["country_code"])
    m = _scale_guard_multiplier(seed_total)
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
            if max(seed_total, other) / min(seed_total, other) > m:
                continue
        if family_min is not None:
            score = (family_scores or {}).get(r["institution_id"], 0.0)
            if score < family_min:
                continue
        out.append(r)
    return out


def _active_filter_labels(filters: dict) -> list[str]:
    """One label per active post-filter, shared by `active_controls_strip`
    and `explain_empty` so the two never drift apart."""
    labels = []
    types = filters.get("types")
    if types:
        labels.append(copy.STRIP_TYPE.format(types=", ".join(sorted(types))))
    country_codes = filters.get("countries")
    if country_codes:
        # R1/L22: the strip shows country NAMES, sorted by name (not by code).
        names = sorted(countries_lib.name(c) for c in country_codes)
        labels.append(copy.STRIP_COUNTRY.format(countries=", ".join(names)))
    if filters.get("exclude_own_country"):
        labels.append(copy.STRIP_EXCLUDE_OWN_COUNTRY)
    size_range = filters.get("size_range")
    if size_range is not None:
        lo, hi = size_range
        labels.append(copy.STRIP_SIZE_RANGE.format(lo=lo, hi=hi))
    if filters.get("scale_guard"):
        labels.append(copy.STRIP_SCALE_GUARD)
    family_min = filters.get("family_min")
    if family_min is not None:
        labels.append(copy.STRIP_FAMILY.format(threshold=family_min))
    return labels


def active_controls_strip(*, tree, basis, depth, c1_on, l7_on, filters: dict) -> str | None:
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
    dims.extend(_active_filter_labels(filters))
    if not dims:
        return None
    return copy.STRIP_PREFIX + copy.STRIP_JOIN.join(dims)


def explain_empty(filters: dict, seed_row) -> str:
    """Names the filter(s) responsible for a 0-row list -- / VIZ_SPEC S1.6. Never a generic "no results"."""
    labels = _active_filter_labels(filters)
    joined = copy.EMPTY_STATE_JOIN.join(labels) if labels else copy.NO_ACTIVE_FILTER_LABEL
    return copy.EMPTY_STATE_TEMPLATE.format(filters=joined, seed=seed_row["display_name"])
