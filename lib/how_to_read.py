"""
Loads `app/docs/how_to_read.yaml` (the visible "How to read" line a chart
prints between its own controls and the chart itself -- see that file's own
header) into HOW_TO_READ, ONCE, at import time. Nothing else: no derivation,
no defaults, no Streamlit import; the path is __file__-relative so this works
whether the app is launched from `app/` or from anywhere else.

Two readers:
  `text(chart, mode)`  -- the line for a chart under the mode on screen
                          (mode = one of the five "Topics shown" cuts, or
                          "fields"/"subfields" on the reciprocity scatter)
  `methods(key)`       -- the two longer definitions the Methods page and the
                          topic-plane caption share ("frontier_scores",
                          "axis_def_topic_planes")

Both raise KeyError naming the key that was asked for and the keys that exist,
so a chart wired to a mode nobody wrote copy for fails loudly at first render
rather than printing an empty line.
"""
from __future__ import annotations

from pathlib import Path

import yaml

HOW_TO_READ_PATH = Path(__file__).resolve().parent.parent / "docs" / "how_to_read.yaml"

with open(HOW_TO_READ_PATH, "r", encoding="utf-8") as _f:
    HOW_TO_READ: dict = yaml.safe_load(_f)

CHARTS: dict = HOW_TO_READ["charts"]
METHODS: dict = HOW_TO_READ["methods"]


def text(chart: str, mode: str, **names: str) -> str:
    """The "How to read" line for `chart` under `mode`; `a=`/`b=` fill the
    two institutions' short names where a line names them."""
    try:
        modes = CHARTS[chart]
    except KeyError:
        raise KeyError(
            f"no how-to-read copy for chart {chart!r}; known charts: "
            f"{sorted(CHARTS)}") from None
    try:
        line = modes[mode]
    except KeyError:
        raise KeyError(
            f"no how-to-read copy for chart {chart!r} in mode {mode!r}; "
            f"known modes for this chart: {sorted(modes)}") from None
    return line.format(**names) if names else line


def methods(key: str) -> str:
    """One of the longer shared definitions."""
    try:
        return METHODS[key]
    except KeyError:
        raise KeyError(
            f"no how-to-read definition {key!r}; known keys: "
            f"{sorted(METHODS)}") from None
