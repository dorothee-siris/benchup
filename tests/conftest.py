"""Test bootstrap: put `app/` on sys.path. Nothing else belongs here.

NAMESPACE GUARD: `tests/` has
no `__init__.py`, and this file just put APP_ROOT (which contains the `lib`
package AND every top-level `tests/*.py` file) on sys.path -- so a test file
that was ever named the SAME as a lib module's own basename (e.g. a
`tests/selection.py` instead of `tests/test_selection.py`) would be import-
ambiguous with `lib/selection.py` under pytest's default "prepend" import
mode. This app added eleven new lib modules (compare_data, collab_data,
selection, views_compare, views_collab, views_methods, charts_compare,
exports_xlsx, tiles, wordcloud_png, state) that a mis-named test file could
now collide with; this check runs at collection time, for every test run, so
a future change cannot introduce the collision unnoticed. Real test files
(the "test_*.py" convention every file in this suite already follows) never
collide by construction -- this guards the convention itself, once."""
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def _lib_module_stems() -> set[str]:
    lib_dir = APP_ROOT / "lib"
    return {p.stem for p in lib_dir.rglob("*.py")
            if p.stem != "__init__" and "__pycache__" not in p.parts}


def _test_module_stems() -> dict[str, Path]:
    tests_dir = Path(__file__).resolve().parent
    return {p.stem: p for p in tests_dir.rglob("*.py")
            if p.stem not in ("conftest", "__init__") and "__pycache__" not in p.parts}


def _check_no_test_module_shadows_a_lib_module() -> None:
    lib_stems = _lib_module_stems()
    collisions = {stem: path for stem, path in _test_module_stems().items() if stem in lib_stems}
    if collisions:
        detail = ", ".join(f"{p.relative_to(APP_ROOT)} shadows lib/{stem}.py"
                           for stem, p in collisions.items())
        raise RuntimeError(
            f"tests/ namespace guard: {len(collisions)} test file basename(s) collide with a "
            f"lib module basename -- rename the test file (the 'test_' prefix convention "
            f"exists exactly to avoid this): {detail}")


_check_no_test_module_shadows_a_lib_module()
