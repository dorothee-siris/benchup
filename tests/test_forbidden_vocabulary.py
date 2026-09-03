"""tests/test_forbidden_vocabulary.py --. RULE: no string a reader actually sees names a plan code, a build
artefact, a pipeline, a stream, or a table/file name. A strategy officer
reading this tool for the first time must never meet "", "BUILD_PLAN",
"artefact", "pipeline", "parquet" or a stream name (MU3, CP3, LP3, WT2, P6,
G2, H2, I2, VS3, FA3, CD3,.).

SCOPE -- every RENDERED string, two sources:
  (a) `lib/copy.py`'s own uppercase module constants, reusing
      `tests/test_narrative.py`'s `collect_copy_module_strings` collector
      (the same recursive walk the digit-ban already trusts), MINUS
      `METHODS_SOURCES`: that dict is the Methods page's own provenance
      map, read only by this test suite and by `docs/METHODS_NOTE.md`'s own
      cross-check (`tests/test_methods_note.py`), never passed to a
      Streamlit call or rendered on any page (`views_methods.render` only
      ever reads `copy.METHODS`, `copy.NAV`, `copy.VERDICT_LINE` and
      `copy.METHODS_UI`) -- this is the ONE allowlisted section the brief
      anticipates ("an allowlist ONLY for the Methods provenance section if
      it genuinely needs it"), and it earns the exemption on "never
      rendered" grounds rather than on a word-by-word carve-out: every
      OTHER string in copy.py, METHODS's own {title, body} templates
      included, is scanned in full.
  (b) `lib/compare_data.py`'s `UNAVAILABLE_REASON` values.
      `lib/collab_data.py` carries no equivalent reason dict today (grepped
      2026-08-31: no module-level string constant holding a `reason:` value
      or a `REASON` name) -- `_reason_frame_strings` below still imports
      the module and reads any dict whose name ends in `REASON` generically,
      so a reason dict LP3 adds next wave is picked up with no edit here.

FALSE-POSITIVE GUARD: "artefact" is also an ordinary English word (an
unintended effect, as in "a country artefact" / "a statistical artefact"),
not only internal build vocabulary. Two pre-existing LENS_INTRO/LENS_CAVEAT
sentences used it that way; MU3 rephrased both ("not simply an effect of
shared country" / "does not simply reflect a shared country") rather than
carving a word-sense exception into this test, per the brief's own
"prefer rephrasing" instruction -- so the banned-term list below is applied
literally, with no per-string exemption.

Run from cwd `app/`: python -m pytest tests/test_forbidden_vocabulary.py -q
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.test_narrative import collect_copy_module_strings

# Case-insensitive except the bare stream-code tokens (MU3, CP3,. read as
# uppercase identifiers; a lowercase "cp3" is not a stream code, and "P6" as
# a bare token would false-positive on ordinary prose, so every stream code
# is matched with a word boundary and its exact case).
FORBIDDEN_CI = [
    "2B-R", "2b-r", "BUILD_PLAN", "artefact", "pipeline", "parquet",
    "wind tunnel", "wind-tunnel",
    #  TEV-U (wave 3 acceptance): "pastel" (the retired institution
    # trio's own family name -- never a word a reader needs, even in the
    # abstract) and the ""/"" stream-round family, alongside every
    # earlier round's "" this list already banned.
    "pastel", "2b-r3", "2br3",
    # , BenchUp V4 trim,: the trim's own sweep. ""
    # (lowercased, so it also catches "") bans the old app's own name
    # wherever it survives -- D13/D15, plain "BenchUp" everywhere. "phase 2"
    # bans the pre-trim phase-numbering scheme by name. "basket" and
    # "collaborate" ban the two retired surfaces (the sidebar basket, the
    # Collaborate page) outright, not only the stream-round codes that built
    # them -- grepped clean against every current rendered string before
    # being added (no live copy uses "collaborate"/"collaboration" as an
    # ordinary word; "co-publication" and "joint" carry that meaning
    # instead).
    "v3", "phase 2", "basket", "collaborate",
]
FORBIDDEN_CODES = re.compile(
    r"\b(MU3|CP3|LP3|VS3|FA3|CD3|WT2?|P[1-6]|G2|H2|I2|2C|2D|2E)\b"
)

# METHODS_SOURCES: the one non-rendered exemption (see module docstring).
# Every other name in lib.copy is in scope, including copy.METHODS itself.
NON_RENDERED_NAMES = {"METHODS_SOURCES"}


def _violations(strings: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    out = []
    for loc, s in strings:
        low = s.lower()
        for term in FORBIDDEN_CI:
            if term.lower() in low:
                out.append((loc, term, s))
        m = FORBIDDEN_CODES.search(s)
        if m:
            out.append((loc, m.group(1), s))
    return out


def _copy_rendered_strings() -> list[tuple[str, str]]:
    from lib import copy as copy_mod

    return [(loc, s) for loc, s in collect_copy_module_strings(copy_mod)
            if not any(f"::{name}[" in loc for name in NON_RENDERED_NAMES)]


def _reason_frame_strings() -> list[tuple[str, str]]:
    """Every string value in a `*REASON*`-named dict of `lib.compare_data`
    or `lib.collab_data` -- the 'frame reason strings' the brief names:
    `compare_data.metric_frame`'s empty-frame `.attrs["reason"]` is filled
    from exactly this kind of dict (`UNAVAILABLE_REASON`, per that module's
    own docstring), so scanning the dict scans every reason the page can
    ever render without needing to drive every (metric, level) pair through
    the UI here."""
    out = []
    for mod_name in ("lib.compare_data", "lib.collab_data"):
        mod = __import__(mod_name, fromlist=["_"])
        for name, value in vars(mod).items():
            if not name.isupper() or "REASON" not in name:
                continue
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, str):
                        out.append((f"{mod_name}.{name}[{k!r}]", v))
    return out


def all_rendered_strings() -> list[tuple[str, str]]:
    return _copy_rendered_strings() + _reason_frame_strings()


# ------------------------------------------------------------------ tests

def test_scan_is_not_vacuous():
    """Guards the collectors themselves: if this drops near zero, an import
    broke (lib.compare_data/lib.collab_data are CD3's concurrent files) or
    collect_copy_module_strings stopped walking -- not that the app has no
    copy left to scan."""
    total = len(all_rendered_strings())
    assert total >= 50, f"only {total} rendered strings collected -- collector likely broken"


def test_reason_dict_scan_is_generic_and_currently_empty():
    """ note: `compare_data.UNAVAILABLE_REASON` (the pre-trim
    'metric not shown, here is why' dict this scan's docstring names) did
    not survive C1/C3's rewrite -- the sections that ever emptied a frame
    with a reason (ERC panels, coverage, impact-by-subfield intervals) are
    themselves retired. `_reason_frame_
    strings` stays a GENERIC scan of any `*REASON*`-named dict in either
    module rather than a hard import of one name, so a future reason dict
    either module adds is picked up with no edit here; today it is
    legitimately empty, not broken -- checked directly rather than assumed."""
    from lib import collab_data, compare_data

    for mod in (compare_data, collab_data):
        assert not any(name.isupper() and "REASON" in name for name in vars(mod)), (
            f"{mod.__name__} grew a REASON dict back -- give it a real assertion here")
    assert _reason_frame_strings() == []


def test_methods_sources_itself_would_fail_without_the_exemption():
    """Proves the METHODS_SOURCES exemption is doing real work (and is not
    hiding a violation that also lives somewhere rendered): several of its
    values name a real table file on purpose (it is the provenance map),
    so this documents WHY it is excluded rather than leaving that claim
    unverified. If this ever passes, METHODS_SOURCES stopped naming files
    and the exemption in NON_RENDERED_NAMES can be dropped."""
    from lib import copy as copy_mod

    raw = [(f"copy::METHODS_SOURCES[{k}]", v) for k, v in copy_mod.METHODS_SOURCES.items()]
    assert _violations(raw), "expected METHODS_SOURCES to still name a table/pipeline term"


def test_no_forbidden_vocabulary_in_rendered_strings():
    """The regression itself. A hit here is copy a reader can actually see
    naming a plan code, a build artefact, a pipeline, a table file or a
    stream -- see the module docstring for scope and the one exemption."""
    violations = _violations(all_rendered_strings())
    if violations:
        detail = "\n".join(f"  {loc} -- matched {term!r} in {s!r}" for loc, term, s in violations)
        pytest.fail(f"{len(violations)} forbidden-vocabulary violation(s):\n{detail}")


# ==============================================================================
# , BenchUp V4 trim,: the trim's own sweep, additive to
# the scan above (which already covers every string above via the extended
# FORBIDDEN_CI/FORBIDDEN_CODES, ""/"phase 2"/"basket"/"collaborate"/2C/2D/2E
# included). Two gaps the ORIGINAL scope never reached:
#
#   (a) `page_title=` -- test_narrative.py's own `collect_ui_call_strings`
#       deliberately excludes it (its own docstring: "out of the brief's
#       named kwarg set", scoped to the DIGIT ban only) alongside every other
#       keyword outside label/help/caption/placeholder. A stray "BenchUp"
#       page_title is exactly the browser-tab string a reader meets first,
#       so this sweep reads EVERY keyword on a recognised Streamlit call
#       (broader than the digit-ban's own scope, correctly so: this check
#       cares about a different failure mode). Two such literals were found
#       and fixed by this stream (pages/1_(magnifying-glass)_Find.py,
#       pages/3_(open-book)_Methods.py) before this test was written.
#   (b) `docs/METHODS_NOTE.md` -- a markdown file, not Python: read as raw
#       text, one violation check per line (test_methods_note.py separately
#       guards its own em-dash rule).
#
# lib/*.py and pages/*.py themselves are covered by (a) over
# `test_narrative.SCOPE_B_FILES` (every lib/views_*.py, ranked.py,
# filters.py, badges.py, selection.py, exports_xlsx.py, charts_compare.py,
# tiles.py, wordcloud_png.py, Menu.py, pages/*.py) plus the ORIGINAL scan's
# own coverage of lib/copy.py -- between the two, every file the brief names
# is swept; a lib/*.py module holding no Streamlit call (compare_data.py,
# collab_data.py, links.py, search.py, countries.py, profile_data.py) is
# structurally incapable of defining a rendered string (test_narrative.py's
# own test_pure_data_modules_hold_no_ui_copy proves this), so it needs no
# separate pass here.
# ==============================================================================

import ast

from tests.test_narrative import ST_CALL_NAMES, SCOPE_B_FILES, _literal_parts

APP_DIR = Path(__file__).resolve().parents[1]
NOTE_PATH = APP_DIR / "docs" / "METHODS_NOTE.md"


def _every_keyword_ui_call_strings(path: Path) -> list[tuple[str, str]]:
    """Like `test_narrative.collect_ui_call_strings`, except EVERY keyword on
    a recognised Streamlit call is in scope, not only label/help/caption/
    placeholder -- this check's own reason is in the module comment above."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in ST_CALL_NAMES):
            continue
        loc = f"{path.relative_to(APP_DIR)}:{node.lineno}"
        for arg in node.args:
            for s in _literal_parts(arg):
                out.append((loc, s))
        for kw in node.keywords:
            for s in _literal_parts(kw.value):
                out.append((f"{loc}[{kw.arg}]", s))
    return out


def _note_lines() -> list[tuple[str, str]]:
    return [(f"docs/METHODS_NOTE.md:{i}", line)
            for i, line in enumerate(NOTE_PATH.read_text(encoding="utf-8").splitlines(), start=1)]


def wave5_scope_strings() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for f in SCOPE_B_FILES:
        out += _every_keyword_ui_call_strings(f)
    out += _note_lines()
    return out


def test_wave5_scan_is_not_vacuous():
    total = len(wave5_scope_strings())
    assert total >= 50, f"only {total} strings collected -- collector likely broken"


# The acceptance line's OWN pattern, narrower than the FORBIDDEN_CI
# list above on purpose: "parquet"/"pipeline"/"artefact" are fine in
# docs/METHODS_NOTE.md (a citation-heavy download, exactly the pre-trim
# note's own style -- it names a table or a pipeline script per claim by
# design, `test_methods_sources_itself_would_fail_without_the_exemption`'s
# own reasoning for METHODS_SOURCES applies here too) but never in a page
# title or a widget label, which is what this scan actually checks (the
# ORIGINAL `test_no_forbidden_vocabulary_in_rendered_strings` above already
# holds lib/copy.py, including METHODS itself, to the FULL FORBIDDEN_CI
# list -- this second, narrower pattern is additive, not a relaxation).
WAVE5_CI_TERMS = ["v3", "phase 2", "2b-r", "basket", "collaborate page", "collaborate", "build_plan"]
WAVE5_CODES = re.compile(r"\b2C\b|\b2D\b|\b2E\b")


def _wave5_violations(strings: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    out = []
    for loc, s in strings:
        low = s.lower()
        for term in WAVE5_CI_TERMS:
            if term in low:
                out.append((loc, term, s))
        m = WAVE5_CODES.search(s)
        if m:
            out.append((loc, m.group(0), s))
    return out


def test_no_v3_trim_vocabulary_in_pages_menu_lib_or_the_methods_note():
    """The acceptance line: `||Phase 2||2C|2D|2E|BUILD_PLAN|
    basket|Collaborate` over lib/*.py rendered strings, pages/*.py, Menu.py,
    docs/METHODS_NOTE.md -- 0 hits, no allow-list needed (the two genuine
    pre-existing hits found while writing this test, both a `page_title=`
    still reading "BenchUp", were fixed rather than allow-listed:
    pages/1_(magnifying-glass)_Find.py and pages/3_(open-book)_Methods.py)."""
    violations = _wave5_violations(wave5_scope_strings())
    if violations:
        detail = "\n".join(f"  {loc} -- matched {term!r} in {s!r}" for loc, term, s in violations)
        pytest.fail(f"{len(violations)} v3-trim vocabulary violation(s):\n{detail}")
