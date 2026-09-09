"""tests/test_how_to_read.py -- the visible "How to read" line, one per
(chart, mode), lives in `docs/how_to_read.yaml` and is read through
`lib/how_to_read.py`. This suite holds that copy to the rules its own file
header states, so a later edit cannot quietly ship a paragraph where a caption
belongs, drop a mode, or let build vocabulary reach a reader:

  * the matrix is COMPLETE -- the four mode-driven charts carry all five modes
    (the same five `lib.topic_data.MODES` offers), the reciprocity scatter
    carries both grains, and the two shared definitions exist;
  * every chart line is at most two sentences and at most 340 characters (a
    line that has to wrap three times stops being a caption);
  * no line uses an abbreviation -- besides being unfriendly to read, a
    trailing dot inside one would make the sentence count meaningless;
  * no line contains a forbidden term, reusing `test_forbidden_vocabulary`'s
    OWN list rather than a second copy of it;
  * the frontier lines and both definitions name the two bins they compare
    (2019-21 and 2022-23) -- the whole point of the corrected wording;
  * a missing chart, mode or definition raises KeyError, loudly.

Run from cwd `app/`: python -m pytest tests/test_how_to_read.py -q
"""
from __future__ import annotations

import re

import pytest

from lib import how_to_read as H
from tests.test_forbidden_vocabulary import FORBIDDEN_CI, FORBIDDEN_CODES

MODE_CHARTS = ("find_plane_impact", "find_plane_frontier",
               "compare_topic_overlay", "compare_balance_bars")
MODES = ("volume", "fwci", "led", "stars", "emergence")
GRAINS = ("fields", "subfields")
METHOD_KEYS = ("frontier_scores", "axis_def_topic_planes")

MAX_CHARS = 340
MAX_SENTENCES = 2

# A sentence ends at a period followed by whitespace or by the end of the
# string -- so "1.0", "0.7" and "2022-23" inside a sentence do not count, and
# an abbreviation would (which is why the copy carries none, checked below).
_SENTENCE_END = re.compile(r"\.(?:\s|$)")
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "approx.")


def _chart_items() -> list[tuple[str, str, str]]:
    items = [(c, m, H.text(c, m)) for c in MODE_CHARTS for m in MODES]
    items += [("compare_reciprocity", g, H.text("compare_reciprocity", g)) for g in GRAINS]
    return items


# ------------------------------------------------------------- completeness

def test_every_chart_and_mode_of_the_matrix_is_present():
    """4 charts x 5 modes + the reciprocity scatter's 2 grains = 22 lines,
    and no chart carries a mode the selector cannot produce."""
    assert sorted(H.CHARTS) == sorted(MODE_CHARTS + ("compare_reciprocity",))
    for chart in MODE_CHARTS:
        assert sorted(H.CHARTS[chart]) == sorted(MODES), chart
    assert sorted(H.CHARTS["compare_reciprocity"]) == sorted(GRAINS)
    assert len(_chart_items()) == 22


def test_the_five_modes_are_the_selector_s_own_five():
    """The keys are not a parallel vocabulary: they are exactly the modes the
    topic selector offers, so a mode added there fails here until it has copy."""
    from lib import topic_data

    assert sorted(MODES) == sorted(topic_data.MODES)


def test_both_shared_definitions_are_present():
    for key in METHOD_KEYS:
        assert H.methods(key).strip(), key
    assert sorted(H.METHODS) == sorted(METHOD_KEYS)


def test_every_line_is_a_non_empty_string():
    for chart, mode, t in _chart_items():
        assert isinstance(t, str) and t.strip(), f"{chart}/{mode}"


# ------------------------------------------------------------------- length

def test_every_chart_line_is_at_most_two_sentences():
    long_ones = [(c, m, len(_SENTENCE_END.findall(t)))
                 for c, m, t in _chart_items()
                 if len(_SENTENCE_END.findall(t)) > MAX_SENTENCES]
    assert not long_ones, f"more than {MAX_SENTENCES} sentences: {long_ones}"


def test_every_chart_line_ends_on_a_full_stop():
    """A count of sentence ends is only meaningful if every line closes one."""
    for chart, mode, t in _chart_items():
        assert t.rstrip().endswith("."), f"{chart}/{mode} does not end on a full stop"


def test_every_chart_line_is_within_the_character_cap():
    over = [(c, m, len(t)) for c, m, t in _chart_items() if len(t) > MAX_CHARS]
    assert not over, f"over {MAX_CHARS} characters: {over}"


def test_no_line_uses_an_abbreviation():
    hits = [(c, m, a) for c, m, t in _chart_items()
            for a in _ABBREVIATIONS if a in t.lower()]
    hits += [(k, "-", a) for k in METHOD_KEYS
             for a in _ABBREVIATIONS if a in H.methods(k).lower()]
    assert not hits, f"abbreviations found: {hits}"


# -------------------------------------------------------------- vocabulary

def _violations(pairs: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    out = []
    for loc, s in pairs:
        low = s.lower()
        for term in FORBIDDEN_CI:
            if term.lower() in low:
                out.append((loc, term, s))
        m = FORBIDDEN_CODES.search(s)
        if m:
            out.append((loc, m.group(1), s))
    return out


def test_no_forbidden_vocabulary_in_any_how_to_read_string():
    """Same list, same regex, as the app-wide sweep -- imported, not copied."""
    pairs = [(f"{c}/{m}", t) for c, m, t in _chart_items()]
    pairs += [(k, H.methods(k)) for k in METHOD_KEYS]
    violations = _violations(pairs)
    if violations:
        detail = "\n".join(f"  {loc} -- matched {term!r} in {s!r}" for loc, term, s in violations)
        pytest.fail(f"{len(violations)} forbidden-vocabulary violation(s):\n{detail}")


# ------------------------------------------------------ the corrected bins

def test_the_frontier_plane_lines_name_both_bins():
    """The second topic plane compares the latest two bins by name: without
    them the reader cannot tell a long-run position from recent momentum."""
    for mode in MODES:
        t = H.text("find_plane_frontier", mode)
        assert "2022" in t and "2019" in t, f"find_plane_frontier/{mode}: {t!r}"


def test_both_definitions_name_both_bins_and_the_weighting():
    for key in METHOD_KEYS:
        t = H.methods(key)
        assert "2022" in t and "2019" in t, key
    frontier = H.methods("frontier_scores")
    assert "0.7" in frontier and "0.3" in frontier
    assert "0.01" in frontier and "0.5" in frontier, "the worked example is missing"


def test_the_definitions_read_expansion_as_a_position_and_acceleration_as_momentum():
    """The correction itself: expansion is where the topic stands, not how
    fast it grew last period."""
    for key in METHOD_KEYS:
        low = H.methods(key).lower()
        assert "expansion is a position" in low, key
        assert "acceleration is momentum" in low, key


# ----------------------------------------------------------- missing keys

def test_text_raises_key_error_on_an_unknown_chart():
    with pytest.raises(KeyError, match="no how-to-read copy for chart"):
        H.text("find_plane_nonesuch", "volume")


def test_text_raises_key_error_on_an_unknown_mode():
    with pytest.raises(KeyError, match="in mode"):
        H.text("find_plane_impact", "nonesuch")


def test_methods_raises_key_error_on_an_unknown_key():
    with pytest.raises(KeyError, match="no how-to-read definition"):
        H.methods("nonesuch")


def test_the_module_holds_no_streamlit_import():
    """This module is read by charts and by the Methods page alike; keeping it
    Streamlit-free is what lets the tests above import it with no app running."""
    import ast
    from pathlib import Path

    path = Path(H.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not any(
        (isinstance(n, ast.Import) and any(a.name == "streamlit" for a in n.names))
        or (isinstance(n, ast.ImportFrom) and n.module == "streamlit")
        for n in ast.walk(tree))
