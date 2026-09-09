"""tests/test_tiles.py -- the KPI-tile "?" help
formatter, `lib/tiles.py`'s own markdown mirror of `lib.charts.hover_line`/
`hover_entity`.

Run from cwd `app/`: python -m pytest tests/test_tiles.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib import tiles as T   # noqa: E402


def test_help_line_is_bold_label_colon_value():
    assert T.help_line("European median", "4.2%") == "**European median**: 4.2%"


def test_help_line_none_value_means_not_drawn():
    assert T.help_line("European median", None) is None


def test_help_entity_is_bold_no_label():
    assert T.help_entity("Universite de Strasbourg") == "**Universite de Strasbourg**"


def test_bold_label_clauses_wraps_only_the_named_labels():
    text = "European median: 4.2%. Not a label: still not one."
    out = T.bold_label_clauses(text, ["European median"])
    assert out == "**European median**: 4.2%. Not a label: still not one."


def test_bold_label_clauses_longest_first_avoids_double_wrap():
    """'European median' is a PREFIX of 'European median of the mean' --
    the longer label must win, or the shorter match would wrap first and
    leave a broken '**European median** of the mean**' behind."""
    text = "European median of the mean: 1.10. European median: 1.05."
    out = T.bold_label_clauses(text, ["European median", "European median of the mean"])
    assert out == "**European median of the mean**: 1.10. **European median**: 1.05."
    assert "****" not in out


def test_bold_label_clauses_leaves_unlisted_prose_untouched():
    text = "A share of the institution's fractional output, read against the world."
    assert T.bold_label_clauses(text, ["European median"]) == text
