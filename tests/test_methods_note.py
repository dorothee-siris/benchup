"""tests/test_methods_note.py --.

The Methods page renders `lib/copy.METHODS`, a dict of `{title, body}`
templates whose every number is a `{placeholder}` the page fills at run time.
`docs/METHODS_NOTE.md` is the human-readable source of the same sections,
with the numbers written out and a citation per claim, and is never rendered
by the app. Nothing keeps the two in step except this file:

  1. every `METHODS` section has a `## ` heading in the.md carrying its
     exact title, so a section cannot be added to the page without its
     source text;
  2. every `{placeholder}` appearing in a `METHODS` body or title is
     documented in `copy.METHODS_SOURCES`, so no number can reach the page
     without a named source (CFG key, manifest key, index column);
  3. `METHODS_SOURCES` carries no dead entries, so the mapping stays a
     contract rather than a wish list.

The digit-ban is NOT relaxed anywhere here: `METHODS_SOURCES` describes each
source in words ("CFG bonus_year", "count of distinct panel_idx in
erc.parquet") and is scanned by `tests/test_narrative.py` like every other
uppercase constant in `lib/copy.py`.

Run from cwd `app/`: python -m pytest tests/test_methods_note.py -q
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
NOTE_PATH = APP_DIR / "docs" / "METHODS_NOTE.md"

PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")


def note_headings() -> list[str]:
    """Every `## ` heading in the source note, in order."""
    return [line[3:].strip()
            for line in NOTE_PATH.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")]


def methods_placeholders() -> dict[str, list[str]]:
    """section key -> the placeholder names its title and body use."""
    from lib import copy as copy_mod

    out = {}
    for key, section in copy_mod.METHODS.items():
        names = []
        for part in (section["title"], section["body"]):
            names += PLACEHOLDER_RE.findall(part)
        out[key] = sorted(set(names))
    return out


# ------------------------------------------------------------------ tests

def test_note_file_exists_and_is_not_a_stub():
    assert NOTE_PATH.exists(), f"{NOTE_PATH} is missing"
    assert len(NOTE_PATH.read_text(encoding="utf-8")) > 4000, (
        "docs/METHODS_NOTE.md is too short to be the source text of the Methods page")


def test_every_methods_section_has_a_heading_in_the_note():
    from lib import copy as copy_mod

    headings = set(note_headings())
    missing = [(k, s["title"]) for k, s in copy_mod.METHODS.items()
               if s["title"] not in headings]
    if missing:
        detail = "\n".join(f"  METHODS[{k!r}] title {t!r}" for k, t in missing)
        pytest.fail("section(s) rendered by the Methods page with no `## ` heading in "
                    f"docs/METHODS_NOTE.md:\n{detail}")


def test_note_has_no_heading_the_page_does_not_render():
    """The other direction: a heading with no section is a section someone
    deleted from the page and forgot here (or a typo in a title)."""
    from lib import copy as copy_mod

    titles = {s["title"] for s in copy_mod.METHODS.values()}
    orphans = [h for h in note_headings() if h not in titles]
    assert not orphans, (
        f"`## ` heading(s) in docs/METHODS_NOTE.md matching no METHODS section: {orphans}")


def test_every_placeholder_is_documented():
    from lib import copy as copy_mod

    documented = set(copy_mod.METHODS_SOURCES)
    undocumented = sorted({name
                           for names in methods_placeholders().values()
                           for name in names} - documented)
    assert not undocumented, (
        "placeholder(s) used in copy.METHODS with no entry in copy.METHODS_SOURCES "
        f"(no source documented for them): {undocumented}")


def test_methods_sources_has_no_dead_entries():
    from lib import copy as copy_mod

    used = {name for names in methods_placeholders().values() for name in names}
    dead = sorted(set(copy_mod.METHODS_SOURCES) - used)
    assert not dead, (
        f"copy.METHODS_SOURCES documents placeholder(s) no template uses: {dead}")


def test_placeholder_collector_is_not_vacuous():
    """Guards the regex and the import: if this drops to zero, the templates
    stopped carrying placeholders (i.e. someone typed a number into copy.py)
    or the collector broke."""
    total = sum(len(v) for v in methods_placeholders().values())
    assert total >= 15, (
        f"only {total} placeholders found across copy.METHODS -- collector likely broken, "
        "or numbers were typed into the templates instead of being filled at run time")


def test_no_em_dash_or_double_hyphen_in_methods_or_note():
    """The VOICE rule at the top of lib/copy.py, extended to the source note:
    an em dash and a `--` standing in for one are both banned in SIRIS prose."""
    from lib import copy as copy_mod

    bad = []
    for key, section in copy_mod.METHODS.items():
        for part_name in ("title", "body"):
            text = section[part_name]
            if "—" in text or "--" in text:
                bad.append(f"METHODS[{key!r}][{part_name!r}]")
    note = NOTE_PATH.read_text(encoding="utf-8")
    for i, line in enumerate(note.splitlines(), start=1):
        if "—" in line:
            bad.append(f"METHODS_NOTE.md:{i}")
    assert not bad, f"em dash or '--' found in: {bad}"
