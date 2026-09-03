"""
tests/test_narrative.py --: the digit-ban regression.

RULE: no digit character appears in a Find-page user-facing string except
inside an allowlisted token (tests/digit_allowlist.txt) or a `{placeholder}`
a caller fills at render time from CFG or the live data. Two scopes:

  (a) every string constant in lib/copy.py (dict values included), which
      since (2026-08-29) also carries the Find-page strings
      formerly in lib/views_find.py's EXTRA_COPY dict, folded into
      lib/copy.py's own `FIND` dict -- one collector, no separate
      views_find.py import needed for this scope any more.

  (b) string literals passed to a Streamlit UI call, or to that call's
      label=/help=/caption=/placeholder= kwarg, in pages/*.py, Menu.py,
      lib/views_*.py, lib/ranked.py, lib/filters.py,
      lib/badges.py, lib/selection.py, lib/exports_xlsx.py,
      lib/charts_compare.py, lib/tiles.py, lib/wordcloud_png.py.

      WIDENED in an earlier round: rev 0 of this
      file scanned a five-file literal list + pages/*.py -- nothing
      created (the Compare page and its six new lib modules)
      was covered. `SCOPE_B_FILES` below now globs lib/views_*.py rather than
      naming lib/views_find.py alone, and explicitly adds the other five new
      modules the brief names. Two of them (lib/charts_compare.py,
      lib/exports_xlsx.py) hold no `import streamlit` at all -- they are
      scanned anyway (the AST walk costs nothing on a file with zero matches)
      so a future UI call added to either is covered from day one, not
      discovered by a second widening.

      DEVIATION FROM THE LITERAL BRIEF WORDING ("ast walk: Call nodes whose
      func is st.<name> or st.column_config.<name>"): lib/views_find.py
      aliases st.sidebar to `sb`, st.columns(.) to `cols`, individual
      columns to `col_a`/`col_b`/`cols[0]`, etc. (this is ordinary Streamlit
      style, not an obfuscation) -- a matcher that only recognises a literal
      `st.xxx` / `st.column_config.xxx` attribute chain would silently miss
      almost every real call in that file (sb.header, sb.selectbox,
      cols[0].metric, col_a.write,.), making the test vacuous for the
      file with the most UI copy. Instead a Call is treated as an in-scope
      UI call when its final attribute name is a real, callable member of
      the INSTALLED `streamlit` module or `streamlit.column_config` (built
      from `dir(st)` / `dir(st.column_config)` at test-collection time)
      grounded in the actual Streamlit API surface, alias-proof, and needs
      no maintenance as new aliases or files appear (test_palette.py uses
      the same "scan whatever exists" philosophy for its own directory
      walk).

EXCLUDED:
  lib/palette.py -- hex colour constants only, no UI copy.
  lib/data_cache.py -- parquet/JSON column names and file paths, not UI copy.
  lib/app_config.py -- loads config.yaml verbatim into CFG, defines no strings.
  lib/exports.py -- CSV filename template, not rendered UI copy.
  lib/engine/** -- no Streamlit import anywhere in the engine package.
  lib/compare_data.py, lib/collab_data.py, lib/profile_data.py, lib/links.py,
  lib/search.py, lib/countries.py -- additions, checked at
  test-collection time (test_pure_data_modules_hold_no_ui_copy below): none
  imports streamlit, so none can define a `st.*` UI call for the AST walk to
  find, and none is an uppercase copy.py-style constant module either
  excluded on the same "no UI copy possible" ground as the five files above,
  not by omission.
  lib/state.py -- DOES import streamlit (checked, deliberately not in the
  list above), but only ever calls `st.session_state`'s dict-like methods
  (`setdefault`/`.remove`/`.clear`/subscript) -- `session_state` is not a
  callable member of `dir(st)`, so its own attribute accesses never match
  ST_CALL_NAMES, and `.setdefault`/`.remove`/`.clear` are dict methods, not
  Streamlit ones. test_pure_data_modules_hold_no_ui_copy checks the weaker,
  correct claim for this file: zero calls whose function name is itself a
  `dir(st)` member.

NON-VACUITY PROOF: run standalone (not part of this suite):
    python - <<'PY'
    import shutil, sys
    sys.path.insert(0, ".")
    shutil.copy("lib/copy.py", "lib/_scratch_copy.py")
    with open("lib/_scratch_copy.py", "a", encoding="utf-8") as f:
        f.write('\nINJECTED = "showing 30 rows"\n')
    from tests.test_narrative import collect_copy_module_strings, has_digit_violation, load_allowlist
    import importlib
    scratch = importlib.import_module("lib._scratch_copy")
    tokens = load_allowlist
    bad = [s for _, s in collect_copy_module_strings(scratch) if has_digit_violation(s, tokens)]
    print("scratch violations:", bad) # -> ['showing 30 rows'] (FAIL as expected)
    PY
    rm lib/_scratch_copy.py

A5 WIDENING NON-VACUITY PROOF: scope (a) above only proves lib/copy.py was
already covered; the point of A5 is that scope (b) now reaches the SIX
 files rev 0 never touched. Proof on one of them
(lib/views_compare.py, none of the five old scope-(b) names):
    python - <<'PY'
    import shutil, sys
    from pathlib import Path
    APP_DIR = Path(".").resolve
    scratch = APP_DIR / "lib" / "_scratch_views_compare.py"
    shutil.copy(APP_DIR / "lib" / "views_compare.py", scratch)
    with open(scratch, "a", encoding="utf-8") as f:
        f.write('\n\ndef _injected_probe:\n import streamlit as st\n'
                ' st.caption("showing 30 rows")\n')
    sys.path.insert(0, str(APP_DIR))
    from tests.test_narrative import collect_ui_call_strings, has_digit_violation, load_allowlist
    tokens = load_allowlist
    bad = [s for _, s in collect_ui_call_strings(scratch) if has_digit_violation(s, tokens)]
    print("FAIL-CASE (injected):", bad) # -> ['showing 30 rows'] (FAIL as expected)
    shutil.copy(APP_DIR / "lib" / "views_compare.py", scratch) # remove the injection
    bad2 = [s for _, s in collect_ui_call_strings(scratch) if has_digit_violation(s, tokens)]
    print("PASS-CASE (clean):", bad2) # -> [] (PASS as expected)
    PY
    rm lib/_scratch_views_compare.py

Run from cwd `app/`: python -m pytest tests/test_narrative.py -q
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = Path(__file__).resolve().parent / "digit_allowlist.txt"

# label=/help=/caption=/placeholder= only -- scope,
# not every kwarg a Streamlit call accepts (e.g. `format=`, `page_title=` are
# deliberately not scanned: out of the brief's named kwarg set).
KW_NAMES = {"label", "help", "caption", "placeholder"}

# Grounded in the real installed Streamlit API (see module docstring)
# alias-proof and future-proof, unlike a hand-maintained name list.
ST_CALL_NAMES = ({n for n in dir(st) if not n.startswith("_") and callable(getattr(st, n, None))}
                  | {n for n in dir(st.column_config) if not n.startswith("_")})

SCOPE_B_FILES = [
    APP_DIR / "Menu.py",
    *sorted((APP_DIR / "lib").glob("views_*.py")),  # A5: a family, globbed -- covers a new
                                                     # views_*.py automatically, no edit here
    APP_DIR / "lib" / "ranked.py",
    APP_DIR / "lib" / "filters.py",
    APP_DIR / "lib" / "badges.py",
    APP_DIR / "lib" / "selection.py",
    APP_DIR / "lib" / "exports_xlsx.py",
    APP_DIR / "lib" / "charts_compare.py",
    APP_DIR / "lib" / "tiles.py",
    APP_DIR / "lib" / "wordcloud_png.py",
    *sorted((APP_DIR / "pages").glob("*.py")),
]

PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")


def load_allowlist(path: Path = ALLOWLIST_PATH) -> list[str]:
    tokens = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tokens.append(line)
    return tokens


def _allow_re(tokens: list[str]) -> re.Pattern:
    if not tokens:
        return re.compile(r"(?!)")  # matches nothing
    ordered = sorted(tokens, key=len, reverse=True)  # longest first: "PP(top10%)" before "top10"
    return re.compile("|".join(re.escape(t) for t in ordered))


def has_digit_violation(s: str, tokens: list[str]) -> bool:
    """A string violates the digit-ban if, after stripping every allowlisted
    token and every `{.}` placeholder, a digit character remains."""
    cleaned = _allow_re(tokens).sub("", s)
    cleaned = PLACEHOLDER_RE.sub("", cleaned)
    return bool(re.search(r"\d", cleaned))


def collect_copy_module_strings(copy_module) -> list[tuple[str, str]]:
    """Every uppercase module-level str / dict-of-str constant -- copy.py's
    own convention (mirrors its `scan_for_digit_violations`), reimplemented
    independently against the SHARED allowlist file rather than copy.py's
    own hard-coded `_ALLOWLIST_RE`, so the two can never silently drift
    apart unnoticed. Takes a module OBJECT (not an import path) so the
    non-vacuity proof can point it at a scratch module without touching
    sys.modules["lib.copy"]."""
    out = []
    mod_name = getattr(copy_module, "__name__", "copy")
    for name, value in vars(copy_module).items():
        if name.startswith("_") or not name.isupper():
            continue
        for path, v in _walk_strings(value, name):
            out.append((f"{mod_name}::{path}", v))
    return out


def _walk_strings(value, path: str):
    """Recursive, because 's `copy.METHODS` is a dict of
    {"title", "body"} sub-dicts: the one-level walk this collector used
    before this widening would have silently skipped every Methods-page sentence, i.e.
    gone vacuous exactly where the longest new copy lives. `lib/copy.py`'s
    own `_iter_strings` carries the same widening independently."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _walk_strings(v, f"{path}[{k}]")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from _walk_strings(v, f"{path}[]")


def _literal_parts(node: ast.AST) -> list[str]:
    """The literal text of a plain string Constant, or of a JoinedStr's own
    literal segments -- deliberately excludes a FormattedValue's
    `format_spec` (e.g. ',.0f', '.1%'): those are printf-style specs, not
    user-facing constant strings, and are structurally separate from
    JoinedStr.values so they are never visited here."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [v.value for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)]
    return []


def collect_ui_call_strings(path: Path) -> list[tuple[str, str]]:
    """Every literal string passed positionally to a recognised Streamlit UI
    call, or via its label=/help=/caption=/placeholder= kwarg, in one file."""
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
            if kw.arg in KW_NAMES:
                for s in _literal_parts(kw.value):
                    out.append((loc, s))
    return out


def all_scoped_strings() -> list[tuple[str, str]]:
    from lib import copy as copy_mod

    # copy.FIND (Find-page strings, folded in from views_find.py's former
    # EXTRA_COPY dict by ) is scanned here too: it is an uppercase
    # module-level dict-of-str constant in lib/copy.py, exactly what
    # collect_copy_module_strings already walks -- no separate collector
    # needed, and scope (a) no longer needs a views_find.py import.
    out = collect_copy_module_strings(copy_mod)
    for f in SCOPE_B_FILES:
        out += collect_ui_call_strings(f)
    return out


# ------------------------------------------------------------------ tests

def test_allowlist_has_required_tokens_and_stays_small():
    # : L2/L8/L9 are the DISPLAY codes needs once
    # the eight default lenses are renumbered L0.L7 in tab order (L2 is the
    # topic lens's new code, distinct from the pre-existing L2f) plus the two
    # optional tabs (C1 -> L8, L7 -> L9) -- the cap moved 15->18 for exactly
    # these three, same category as the other tokens (a stable lens
    # identifier, not a data value).
    # Later: an earlier token was retired (dead, press audit J2) and
    # "PP10_WD" took its slot at no cost to the cap; "EU27" then pushed the
    # count to nineteen -- E1's ruled perimeter phrase ("the European
    # baseline (EU27 plus the United Kingdom, Switzerland, Norway and
    # Iceland)") is typed verbatim, on first mention, on every page that
    # names the term. Cap moves 18->19 for exactly this one token, same
    # "stable identifier, not a data value" category as every token above it.
    tokens = load_allowlist()
    required = {"L0", "L1", "L2", "L2f", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "F1", "C1",
                "top10", "PP(top10%)", "PP10_WD", "EU27"}
    missing = required - set(tokens)
    assert not missing, f"digit_allowlist.txt is missing required token(s): {sorted(missing)}"
    assert len(tokens) <= 19, (
        f"digit_allowlist.txt has {len(tokens)} non-comment lines (cap 19) -- "
        "a growing allowlist is the historical failure mode")


def test_scope_b_matcher_is_not_vacuous():
    """Guards the AST matcher itself: if this drops to ~0, ST_CALL_NAMES (or
    a file path) broke -- e.g. a Streamlit rename -- not that the app has no
    UI copy left to scan. 76 is the count measured against this build after
    the A5 widening (Menu.py 15, lib/views_*.py 48 across four files,
    lib/ranked.py 13, the other seven scoped files 0 each -- ranked/views_*
    alone already clear the old 33-count baseline the earlier, narrower scope reached);
    the floor is set well below the measured total, not at it, so a routine
    copy edit does not make this brittle."""
    total = sum(len(collect_ui_call_strings(f)) for f in SCOPE_B_FILES)
    assert total >= 50, f"only {total} UI-call strings found across scope (b) -- matcher likely broken"


def test_a5_widening_actually_added_files_versus_the_pre_2b_scope():
    """Non-vacuity of the WIDENING itself, not just of the matcher: guards
    against a future edit collapsing SCOPE_B_FILES back to the earlier,
    single-name list without anyone noticing (e.g. a bad merge). BenchUp V4
    trim: `views_collab.py` does not exist (D1, the earlier standalone pair-view page is out of scope
    for this app) -- the THREE lib/views_*.py files this build ships must
    all still be present, plus the five other additions."""
    names = {f.name for f in SCOPE_B_FILES}
    assert {"views_compare.py", "views_methods.py", "views_find.py"} <= names
    assert "views_collab.py" not in names, "Collaborate is out of scope for BenchUp V4 (D1)"
    assert {"selection.py", "exports_xlsx.py", "charts_compare.py", "tiles.py",
            "wordcloud_png.py"} <= names


def test_pure_data_modules_hold_no_ui_copy():
    """Turns the EXCLUDED-list claim above into a live check: every
    data/logic module named there imports no streamlit, so it structurally
    cannot define a `st.*` UI call -- if one of these ever gains a Streamlit
    import, this fails and the module needs adding to SCOPE_B_FILES instead
    of silently staying excluded."""
    pure_modules = ["compare_data.py", "collab_data.py", "profile_data.py",
                    "links.py", "search.py", "countries.py"]
    for name in pure_modules:
        path = APP_DIR / "lib" / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports_st = any(
            (isinstance(node, ast.Import) and any(a.name == "streamlit" for a in node.names))
            or (isinstance(node, ast.ImportFrom) and node.module == "streamlit")
            for node in ast.walk(tree))
        assert not imports_st, (
            f"lib/{name} now imports streamlit -- it can define UI copy and must "
            "move from EXCLUDED into SCOPE_B_FILES")


def test_state_module_calls_no_real_streamlit_ui_function():
    """lib/state.py DOES import streamlit (session_state bookkeeping), so the
    "imports no streamlit" test above cannot cover it -- this checks the
    claim that actually matters: no Call in the file resolves to a real
    `dir(st)` member (session_state's own setdefault/remove/clear do not),
    so collect_ui_call_strings finds nothing there structurally, not by
    accident of today's content."""
    assert collect_ui_call_strings(APP_DIR / "lib" / "state.py") == []


def test_copy_and_extra_copy_scan_is_not_vacuous():
    from lib import copy as copy_mod
    n = len(collect_copy_module_strings(copy_mod))
    assert n >= 50, f"only {n} strings collected from copy.py (incl. copy.FIND) -- collector likely broken"
    from lib import copy as _c
    nested = [v for _, v in collect_copy_module_strings(copy_mod) if "METHODS[" in _]
    assert len(nested) >= 2 * len(_c.METHODS), (
        "the collector is not walking copy.METHODS's nested {title, body} dicts")


def test_no_digit_ban_violations():
    """The regression itself. A real violation here is an APPLICATION defect
    (a static string in pages/Menu.py/lib/{views_find,ranked,filters,badges}.py
    or lib/copy.py that types a digit the digit-ban forbids) -- owns
    the test, not the fix (a dispatch contract)."""
    tokens = load_allowlist()
    violations = [(loc, s) for loc, s in all_scoped_strings() if has_digit_violation(s, tokens)]
    if violations:
        detail = "\n".join(f"  {loc} -- {s!r}" for loc, s in violations)
        pytest.fail(f"{len(violations)} digit-ban violation(s) found (see progress/2A_G.md):\n{detail}")
