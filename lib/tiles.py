"""
app/lib/tiles.py -- the KPI card, copied in from an earlier SIRIS
Streamlit tool's `_kpi_tile` component and reduced to what BenchUp
needs: name + value + one small line, no per-tile download button.

CARD ANATOMY: the metric
NAME is the FIRST visual element and the largest label on the card, the value
sits in bold under it, and exactly ONE small line closes the card. The gate
read the old order the wrong way round -- a column of big numbers whose names
were set in small grey type under them, which is a scoreboard, not six
measures. The card now answers "what is this?" before "how much?".

The small line is one of two things, never both:
  * the index baseline -- "index median {m}. higher than {pct} of
    institutions" -- for the five measures the index has a median for;
  * a NOTE with one bold figure inside it, which is what the publications card
    carries instead ("({N} in fractional counting)"): full and fractional are
    one measure under two conventions, so the second convention belongs on the
    same card as a companion figure, not on a card of its own and not as a
    second baseline line.
Both render into the SAME `SUBLINE_CLASS` hook, so "every card carries exactly
one small line" stays countable (`html.count(SUBLINE_CLASS) == 1`) whichever
form a card uses.

WHY HTML AND NOT `st.metric`: `st.metric` has no small line, and the small line
is the whole point -- the house rule "every KPI pairs its value with the
denominator or reference it is computed against" is what
it carries. `st.metric`'s delta arrow would also imply a change-over-time
reading that none of these point-in-time measures has (VIZ_SPEC.md S2.11, the
named rejected alternative).

Two house rules this module obeys mechanically:
  * every colour comes from `lib.palette` (`tests/test_palette.py` fails the
    build on a `#RRGGBB` anywhere under `lib/` except `palette.py`);
  * every number inside the rendered markup is composed from a named int
    constant, never typed into the string -- the same discipline
    `lib/charts.py` follows, so this file stays clean if the digit-ban scope
    (`tests/test_narrative.py`) ever widens to it.

The caller passes ALREADY-FORMATTED strings: this module formats no number and
reads no data, so `n/a` (`palette.NA_MARK`) versus a value is the caller's
decision, taken once, in `lib/views_find.py`. The one thing this module does
to a string is SPLIT a note template on its `{n}` slot, so the figure inside a
sentence can be bolded without the sentence itself living here.
"""
from __future__ import annotations

import streamlit as st

from lib import palette as P

# Type scale (an earlier SIRIS Streamlit tool's own tile sizes).
# -6: the NAME gets its own step -- above the small line, below the value,
# so the reading order down the card is name -> value -> reference.
LABEL_PX = 15
VALUE_PX = 22
META_PX = 12
LABEL_WEIGHT = 600
VALUE_WEIGHT = 700
VALUE_LINE_HEIGHT = 1.25
LABEL_LINE_HEIGHT = 1.3
META_LINE_HEIGHT = 1.4

# A stable hook so a test or the Playwright probe can count rendered cards
# without matching a user-facing label (which would break with any copy edit).
TILE_CLASS = "benchup-kpi"
# The card's one small line -- baseline or note, same hook either way.
SUBLINE_CLASS = "benchup-kpi-sub"
# The note form additionally carries this hook, so "the publications card
# really shows both counting bases" stays countable rather than a claim about a
# rendered string.
VALUE2_CLASS = "benchup-kpi-value2"

# The slot a note template reserves for its one bold figure. A placeholder
# token, never rendered: `note_html` splits on it instead of formatting, which
# is what lets the figure be bolded inside the sentence.
NOTE_SLOT = "{n}"


def _esc(value) -> str:
    """Minimal HTML escape: these strings are institution-derived data, and
    they are injected with `unsafe_allow_html=True`."""
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _sub_open(extra_class: str = "") -> str:
    cls = f"{SUBLINE_CLASS} {extra_class}".strip()
    return (f'<div class="{cls}" style="font-size:{META_PX}px;'
            f'line-height:{META_LINE_HEIGHT};color:{P.INK_SECONDARY};">')


def _subline_html(text: str) -> str:
    return f"{_sub_open()}{_esc(text)}</div>"


def note_html(template: str, value: str) -> str:
    """The note form of the small line: the template's `{n}` slot replaced by
    `value` in bold ink, the rest of the sentence in secondary ink at the same
    size as a baseline line. A template with no slot renders as a plain small
    line, so a caller can never produce a card with an unlabelled bold figure
    floating on it."""
    before, slot, after = template.partition(NOTE_SLOT)
    if not slot:
        return _subline_html(template)
    return (f"{_sub_open(VALUE2_CLASS)}{_esc(before)}"
            f'<span style="font-weight:{VALUE_WEIGHT};color:{P.INK};">{_esc(value)}</span>'
            f"{_esc(after)}</div>")


def tile_html(label: str, value: str, subline: str | None = None, *,
              note_template: str | None = None, note_value: str | None = None) -> str:
    """The card's markup on its own (no Streamlit call) -- pure, so a test can
    assert on it without a running app.

    `subline` is the index-baseline line; `note_template`/`note_value` are the
    alternative small line described in the module docstring. Give one form or
    the other: a card with two small lines is the grey stack -6 removed,
    and a card with none is a number with no reference at all (L11)."""
    has_note = note_template is not None
    if (note_value is None) != (not has_note):
        raise ValueError("note_template and note_value are given together or not at all")
    if has_note == (subline is not None):
        raise ValueError("a card carries either a baseline subline or a note, never both/neither")
    parts = [
        f'<div class="{TILE_CLASS}">',
        f'<div style="font-size:{LABEL_PX}px;font-weight:{LABEL_WEIGHT};'
        f'line-height:{LABEL_LINE_HEIGHT};color:{P.INK};">{_esc(label)}</div>',
        f'<div style="font-size:{VALUE_PX}px;font-weight:{VALUE_WEIGHT};'
        f'line-height:{VALUE_LINE_HEIGHT};color:{P.INK};">{_esc(value)}</div>',
        note_html(note_template, note_value) if has_note else _subline_html(subline),
        '</div>',
    ]
    return "".join(parts)


def kpi_tile(col, label: str, value: str, subline: str | None = None, *,
             help: str | None = None, note_template: str | None = None,
             note_value: str | None = None) -> None:
    """Render one card into `col` (a `st.columns(.)` slot): a bordered
    container whose chrome is Streamlit's own `border=True` hairline, holding
    the three-line block above.

    `help` puts the measure's WHOLE methodology behind Streamlit's own
    `?` affordance on the markdown block. That is the ruled home for it: the
    cards show a value and its position in the index, and a reader who wants
    the definition asks for it rather than reading it under every card on every
    visit. It shadows the builtin `help` inside this function only, which costs
    nothing here and keeps the keyword named after the Streamlit parameter it
    forwards to."""
    with col:
        with st.container(border=True):
            st.markdown(tile_html(label, value, subline, note_template=note_template,
                                  note_value=note_value),
                        unsafe_allow_html=True, help=help)
