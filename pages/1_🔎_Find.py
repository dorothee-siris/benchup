"""
The Find tab. Deliberately thin: page config,
the session-state defaults every page needs (lib/state.py's own docstring), then the
whole view, which lives in lib/views_find.py.
"""
from __future__ import annotations

import streamlit as st

from lib import state
from lib import views_find

st.set_page_config(page_title="BenchUp - Find", layout="wide")
state.ensure()
views_find.render()
