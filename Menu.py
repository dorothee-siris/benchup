"""
Landing page. Nav cards are enumerated from pages/ at runtime (a pattern
shared with an earlier SIRIS Streamlit tool): a dimension is a live st.page_link once a file matching its word exists under
pages/.

Three cards in narrative order (Find -> Compare -> Methods).
Collaborate is retired, and with it the fourth card and the shared sidebar search this
page used to render on every page load. Editorial labels/blurbs still come from copy.NAV
rather than the bare dimension word. The MATCH word (used only to find the live page file
under pages/, the same mechanism as elsewhere) stays the plain word -- it must be a substring of
the file's own name ("1_(magnifying-glass)_Find.py", "3_(open-book)_Methods.py",.),
which an editorial label like "How it is built" is not.

A dimension whose page file ever goes missing still renders its label and blurb, just
with no live link, rather than a stale placeholder.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from lib import copy, state
from lib.data_cache import index, manifest
from lib.exports import data_date_label
from lib.palette import NA_MARK

SEP = "·"   # middle dot, the separator every other caption in the app uses

st.set_page_config(page_title="BenchUp", layout="wide")
state.ensure()

st.title(copy.NAV["MENU_HEADER"])
st.caption(copy.NAV["MENU_INTRO"])
st.markdown(f"**{copy.VERDICT_LINE}**")

st.markdown("---")

PAGES_DIR = Path(__file__).parent / "pages"
_existing_pages = [p.name for p in PAGES_DIR.glob("*.py")] if PAGES_DIR.is_dir() else []

DIMENSIONS = [
    ("Find", copy.NAV["FIND_LABEL"], copy.NAV["FIND_BLURB"]),
    ("Compare", copy.NAV["COMPARE_LABEL"], copy.NAV["COMPARE_BLURB"]),
    ("Methods", copy.NAV["METHODS_LABEL"], copy.NAV["METHODS_BLURB"]),
]

with st.container(key="nav_cards"):
    cols = st.columns(len(DIMENSIONS), gap="medium")
    for col, (word, label, blurb) in zip(cols, DIMENSIONS):
        match = next((fn for fn in _existing_pages if word.lower() in fn.lower()), None)
        with col:
            with st.container(border=True, key=f"nav_card_{word.lower()}"):
                st.markdown(f"**{label}**")
                st.caption(blurb)
                if match:
                    st.page_link(f"pages/{match}", label=f"Open {label}")

st.markdown("---")

# : the snapshot LABEL ("august_2026") and its generated timestamp are
# both gone from the page -- an internal artefact name and a machine stamp told
# a reader nothing they could act on. What replaces them is what they were
# standing in for: how many institutions the index holds, and the date the data
# was harvested. Both are read at run time (the index length, the manifest's own
# source stamp) so no digit is typed here.
_manifest = manifest()
_stamp = (_manifest.get("source_manifest_generated_at") or _manifest.get("generated_at")
          or _manifest.get("deployed_at"))  # the deploy step's MANIFEST vs source_manifest keys
st.caption(copy.FIND["DATA_CAPTION"].format(
    n_institutions=f"{len(index()):,}", sep=SEP,
    date=data_date_label(_stamp, NA_MARK)))
