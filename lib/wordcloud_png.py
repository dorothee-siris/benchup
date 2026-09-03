"""
app/lib/wordcloud_png.py -- the subfield wordcloud as PNG BYTES.

Copied in from an earlier SIRIS Streamlit tool's
`render_lab_wordcloud_png`, including the two things that
implementation exists to fix:

  * it returns PNG **bytes**, never a resident matplotlib figure -- a
    known leak that tool's own docstring records was one figure pinned per
    render for the whole session, because `plt.close` was never called.
    `WordCloud.to_array` -> `PIL.Image` -> `io.BytesIO` touches no pyplot
    state at all, so there is nothing to leak;
  * it is `@st.cache_data`, keyed by every rendering parameter, so a rerun
    that changes nothing re-renders nothing (the cloud is the single most
    expensive object in the profile section).

ENCODING (stated in the caller's caption, VIZ_SPEC S2.13): word SIZE is the
subfield's works on the CURRENT counting basis; word COLOUR is its OpenAlex
domain, through `palette.domain_color` -- so the cloud re-tints itself when
the tree changes (a tree decides a subfield's field and therefore its domain)
and re-weights itself when the basis changes. No hex literal appears here:
even the background is `palette.SURFACE`, the same white every figure paints
(`tests/test_palette.py` walks `lib/`).

`wordcloud==1.9.6` (pinned in requirements.txt, wheel + render verified on
this env-app / Python 3.12) is the one new runtime dependency this module
adds; PIL arrives transitively with it. Both are imported INSIDE the function, a
pattern shared with an earlier SIRIS Streamlit tool, so an environment without
them degrades to `None` -- the caller
renders the empty-state line -- instead of failing the whole page at import.
"""
from __future__ import annotations

import io

import streamlit as st

from lib import palette as P

# Raster geometry. The PNG is drawn at these pixel dimensions and then scaled
# to the column by `st.image(., width="stretch")`, so this is a resolution
# choice, not a layout choice: wide enough that a long subfield name stays
# legible after downscaling into the left half of the profile's wide row.
DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 420
DEFAULT_MAX_WORDS = 120

# WordCloud tuning, values kept verbatim from an earlier SIRIS Streamlit tool.
PREFER_HORIZONTAL = 0.9   # mostly horizontal words: a rotated label is slower to read
RELATIVE_SCALING = 0.5    # font size tracks frequency at half strength (the library's
                           # own recommended middle ground between rank and count)
MIN_FONT_SIZE = 9         # the structural relief palette.py's validator run 3 asks for
                           # on the Social Sciences hue (lightness above the band): its
                           # words are drawn at a real weight, never a thin hairline.

# Measurement A15. `wordcloud` leaves `max_font_size` UNSET by
# default, which makes it the canvas height -- so a fractional-basis cloud
# whose top subfield dominates drew that one word at ~199 px, then fell off a
# font-size cliff that left only 34 of the 120 words placed at all. Capping the
# largest word at MAX_FONT_SIZE restores a readable ratio (top1/top3 = 1.79)
# and places 62 words on the same input. Measured on Strasbourg, both bases;
# the full-counting basis is cap-INERT (its largest word is ~47 px either way),
# which is why A15 waived the A/B on that basis rather than running it twice.
MAX_FONT_SIZE = 84


@st.cache_data(show_spinner=False, max_entries=16)
def render_wordcloud_png(weights: dict, domains: dict,
                         width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT,
                         max_words: int = DEFAULT_MAX_WORDS,
                         max_font_size: int = MAX_FONT_SIZE) -> bytes | None:
    """`({subfield_name: weight}, {subfield_name: domain_id})` -> PNG bytes.

    Returns `None` -- never a blank white box -- when there is nothing to draw
    (no positive weight) or when the optional dependency is absent; the caller
    turns that into the empty-state line with its reason (VIZ_SPEC S2.13).

    `weights`/`domains` are plain dicts so `st.cache_data` can hash them; the
    caller gets them from `profile_data.wordcloud_weights(ctx, subs, iid)`
    through its own `(iid, tree, basis)`-keyed cache, so the hash is paid on a
    frame that changed anyway.
    """
    freqs = {str(k): float(v) for k, v in (weights or {}).items() if float(v) > 0}
    if not freqs:
        return None
    try:
        from PIL import Image
        from wordcloud import WordCloud
    except ImportError:      # pragma: no cover -- env without the optional dep
        return None

    def color_func(word, *args, **kwargs):
        """Domain inheritance, the ONE colour decision in this module.
        `palette.domain_color` already returns the neutral grey for an unknown
        or unclassified domain, so there is no fallback branch here."""
        return P.domain_color((domains or {}).get(word))

    cloud = WordCloud(
        width=width, height=height, max_words=max_words,
        background_color=P.SURFACE, prefer_horizontal=PREFER_HORIZONTAL,
        relative_scaling=RELATIVE_SCALING, min_font_size=MIN_FONT_SIZE,
        max_font_size=max_font_size,
    )
    cloud.generate_from_frequencies(freqs)
    cloud.recolor(color_func=color_func)

    buf = io.BytesIO()
    Image.fromarray(cloud.to_array()).save(buf, format="PNG")
    return buf.getvalue()
