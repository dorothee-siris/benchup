"""tests/test_locale_format_ban.py -- guards the locale-format ban.

The rule: "Locale: kill comma-decimal
printf-style locale-independent formats on every column (incl.
`ProgressColumn`), one decimal convention app-wide." Streamlit's OWN
`format="percent"` keyword (and any same-shaped constant assignment, e.g. the
kind of `PROGRESS_FORMAT = "percent"` module-level constant a column-builder
might read from) renders under the ACTIVE LOCALE -- on a comma-decimal
locale this silently prints "12,3%" instead of "12.3%", which is exactly the
class of bug the fix (`lib/ranked.py`'s `pct_progress_column`,
`lib/views_collab.py`'s own comment) replaced with an explicit `%.1f%%`-style
printf format.

This is a PERMANENT TRIPWIRE, not a one-time regression test: it walks every
`.py` file under `app/lib/` (recursively -- `lib/engine/` included) and
fails the whole suite the day anyone reintroduces either shape, in ANY file,
not just the ones this plan's streams happened to touch.

The scanner strips COMMENTS and DOCSTRINGS before matching (via `ast` for
docstring line-spans, `tokenize` for comment spans) -- a bare textual grep
would false-positive on the very comments quoted above, which exist
precisely to document the ban and therefore must be ALLOWED to say the words
"format" and "percent" together in prose.

VACUITY: `_scan_source_for_locale_violations` is exercised against three
synthetic in-memory snippets before it is ever pointed at a real file
one with the LIVE keyword (must be flagged), one with the SAME text but only
inside a comment/docstring (must NOT be flagged, proving the stripping
actually strips), and one with a `PROGRESS_FORMAT`-style constant (must be
flagged). Only after the detector is shown to discriminate correctly is it
run for real over `app/lib/`.

Run from cwd `app/`: python -m pytest tests/test_locale_format_ban.py -q
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
LIB_DIR = APP_DIR / "lib"

_FORMAT_KW_PAT = re.compile(r"""format\s*=\s*["']percent["']""")
_CONST_ASSIGN_PAT = re.compile(r"""\b[A-Z][A-Z0-9_]*\s*=\s*["']percent["']""")


def _strip_comments_and_docstrings(source: str) -> str:
    """Blank out (never shift line numbers -- keeps error messages useful)
    every COMMENT token and every module/class/function docstring
    STATEMENT, leaving all other code -- including a live
    `format="percent"` keyword argument's own string literal -- untouched."""
    lines = source.splitlines(keepends=True)

    # 1) comments, via tokenize -- exact (row, col) spans.
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                row = tok.start[0] - 1
                c0, c1 = tok.start[1], tok.end[1]
                line = lines[row]
                lines[row] = line[:c0] + (" " * (c1 - c0)) + line[c1:]
    except (tokenize.TokenizeError, SyntaxError, IndentationError):
        pass  # a file that does not even tokenize is handled by the ast pass below (or skipped)

    source_no_comments = "".join(lines)

    # 2) docstrings, via ast -- a bare string-literal EXPRESSION STATEMENT
    # that is the first statement of a module/class/function body. Blanking
    # the whole line range is safe: a docstring statement occupies its own
    # statement entirely, on those lines, so no live code shares them.
    try:
        tree = ast.parse(source_no_comments)
    except SyntaxError:
        return source_no_comments  # can't parse -> nothing more to strip, scan what remains

    docstring_lines: set[int] = set()

    def _mark(node) -> None:
        body = getattr(node, "body", None)
        if not body:
            return
        first = body[0]
        if (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            start = first.lineno - 1
            end = getattr(first, "end_lineno", first.lineno) - 1
            for ln in range(start, end + 1):
                docstring_lines.add(ln)

    _mark(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _mark(node)

    lines2 = source_no_comments.splitlines(keepends=True)
    for ln in docstring_lines:
        if ln < len(lines2):
            lines2[ln] = "\n" if lines2[ln].endswith("\n") else ""
    return "".join(lines2)


def _scan_source_for_locale_violations(source: str) -> list[str]:
    """Returns the list of offending line snippets (empty == clean)."""
    stripped = _strip_comments_and_docstrings(source)
    hits = []
    for lineno, line in enumerate(stripped.splitlines(), start=1):
        if _FORMAT_KW_PAT.search(line):
            hits.append(f"line {lineno} (format= keyword): {line.strip()}")
        if _CONST_ASSIGN_PAT.search(line):
            hits.append(f"line {lineno} (constant assignment): {line.strip()}")
    return hits


# ---------------------------------------------------------------------------
# VACUITY: prove the detector discriminates BEFORE trusting it on real files
# ---------------------------------------------------------------------------

def test_detector_flags_a_live_format_percent_keyword():
    src = 'st.column_config.ProgressColumn("Score", format="percent")\n'
    hits = _scan_source_for_locale_violations(src)
    assert hits, "the detector must flag a live format=\"percent\" keyword"


def test_detector_flags_a_progress_format_style_constant():
    src = 'PROGRESS_FORMAT = "percent"\n'
    hits = _scan_source_for_locale_violations(src)
    assert hits, "the detector must flag a PROGRESS_FORMAT-style constant"


def test_detector_ignores_the_same_words_inside_a_comment():
    src = '# format="percent" is BANNED, never use it again\nx = 1\n'
    hits = _scan_source_for_locale_violations(src)
    assert not hits, f"a comment must never be flagged: {hits}"


def test_detector_ignores_the_same_words_inside_a_docstring():
    src = (
        'def f():\n'
        '    """Historical note: format="percent" used to live here.\n'
        '    PROGRESS_FORMAT = "percent" was the old constant."""\n'
        '    return 1\n'
    )
    hits = _scan_source_for_locale_violations(src)
    assert not hits, f"a docstring must never be flagged: {hits}"


def test_detector_ignores_a_module_docstring_at_the_top_of_the_file():
    src = (
        '"""Module docstring mentioning format="percent" for history."""\n'
        'from __future__ import annotations\n'
        'x = 1\n'
    )
    hits = _scan_source_for_locale_violations(src)
    assert not hits, f"a module docstring must never be flagged: {hits}"


def test_detector_still_catches_live_code_that_follows_a_clean_docstring():
    """Stripping a docstring must not accidentally swallow the LIVE code
    that follows it on a later line -- guards the line-blanking implementation
    itself against an off-by-one that ate too much."""
    src = (
        'def f():\n'
        '    """A clean docstring."""\n'
        '    return st.column_config.ProgressColumn("x", format="percent")\n'
    )
    hits = _scan_source_for_locale_violations(src)
    assert hits, "live code after a docstring must still be scanned"


# ---------------------------------------------------------------------------
# The real sweep -- every.py file under app/lib/, recursively
# ---------------------------------------------------------------------------

def _lib_py_files() -> list[Path]:
    return sorted(p for p in LIB_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def test_lib_files_exist_to_scan():
    files = _lib_py_files()
    assert len(files) >= 20, f"only found {len(files)} lib .py files -- LIB_DIR path is probably wrong"


@pytest.mark.parametrize("path", _lib_py_files(), ids=lambda p: str(p.relative_to(LIB_DIR)))
def test_no_locale_dependent_percent_format_in_lib(path: Path):
    source = path.read_text(encoding="utf-8")
    hits = _scan_source_for_locale_violations(source)
    assert not hits, (
        f"{path.relative_to(APP_DIR)} uses a locale-dependent percent format "
        f"(locale-format ban): {hits}")
