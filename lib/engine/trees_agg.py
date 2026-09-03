"""
Tree-dependent `fields` (26) / `subfields` (252) tables. One row per
(institution, field-or-subfield, tree), tree in {original, conservative,
bestfit} (ported from the upstream taxonomy_trees.py, read-only import).
A work's per-tree subfield is looked up
from its ORIGINAL-tree `primary_topic_id` via that tree's own
topic->subfield map -- so re-tree-ing only changes which BUCKET a work's mass
lands in, never which works exist or how much mass they carry (institution
totals are IDENTICAL across trees by construction; only the subfield/field
split changes).

subfield->field membership is tree-INDEPENDENT (the repair only reassigns which
of the 252 subfields a topic maps to; it never moves a subfield to a different
field) -- derived once from `topics_dim`'s own (subfield_id, field_id,.)
columns and asserted 1:1 here, not re-derived per tree.

Shares include EVERY topic's mass (811 excluded topics count in shape)
by construction here, since inclusion is at the WORK level (a work's primary
topic always resolves to a subfield under every tree, `is_excluded` never
removes it from this table; exclusion only ever touches frontier denominators,
computed elsewhere).
ENGINE PORT: only the docstring, `TREES`,
`G6_FLOOR` and `subfield_to_field_map` are ported in -- the corpus-grain
builders (`build_subfields`/`build_fields`, `topic_to_subfield_maps`,
`_pack_year_columns`) stay upstream; the app derives shapes from the
topic-grain master via `derive.derive_shapes` instead.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TREES = ("original", "conservative", "bestfit")
G6_FLOOR = 30.0


