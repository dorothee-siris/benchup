"""
Loads app/config.yaml (the flat, ruling-id-commented app config -- see that file's own
header) into CFG. Nothing else: no derivation, no defaults, no Streamlit import. Path is
__file__-relative so this works whether Streamlit is launched from app/ or elsewhere.
"""
from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as _f:
    CFG: dict = yaml.safe_load(_f)
