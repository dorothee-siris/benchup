# VENDORED — provenance for every piece of copied-in code

Standalone-project principle (SIRIS CLAUDE.md): reused code is copied INTO `app/` and adapted,
never referenced from outside at runtime. This file is the ONE provenance record for that copying;
the engine section (§2) is maintained separately, at `app/lib/engine/VENDORED_engine.md`, and
merged in here verbatim.

**Engine provenance (live pointer): `lib/engine/VENDORED_engine.md`** — read that file directly
for the freshest version; §2 below is a merge taken 2026-08-29 and will drift if that file is
edited afterwards.

---

## 1. Contract / deploy code

Pattern source: the Lorraine Explorer (an earlier SIRIS Streamlit tool) — its
data-contract / deploy-validator machinery, per CLAUDE.md's "Multi-source pipeline layout" /
Studio conventions pointer and this stream's own brief.

| Source | What was taken | Destination | Form |
|---|---|---|---|
| the Lorraine Explorer's `docs/data_contract.yaml` | overall shape: `contract_version`, `snapshot_id`→`snapshot`, `deploy_target`, `policy` block (fail_on_* flags), per-file `grain`/`keys`/`columns[{name,dtype,...}]`, the convention of naming every share/ratio column's denominator in prose next to it | `app/docs/data_contract.yaml` | STRUCTURE copied, all CONTENT is BenchUp's own (8 parquet tables + 2 override CSVs, verified column-by-column against the real files 2026-08-29 — never taken from source_manifest.json's table_schemas from memory; one divergence found and recorded there: `index.type_openalex` is shipped but absent from the manifest's schema listing) |
| the Lorraine Explorer's `pipeline/60_deploy.py` | the validate-then-copy-then-manifest shape: iterate `contract["files"]`, validate each declared file (missing/extra/dtype/key checks), copy only if validation is clean, write a deploy manifest, exit non-zero on any failure, print every verdict always (not only on failure) | `app/ops/deploy.py` + `app/ops/contract_check.py` (split into a `check()` library function + a thin CLI/copy driver, since this stream's brief asks for `contract_check.check(tables_dir, contract) -> list[str]` as an importable function, which Lorraine's monolithic script does not expose) | REWRITTEN in the split shape; the validation LOGIC (declared-column presence, dtype coercion check, key-uniqueness, extra-column logging) follows Lorraine's `validate_file()` function structure. Two differences, both because BenchUp's sources are byte-copied verbatim (parquet in, parquet out, no schema-driven re-serialization step) rather than Lorraine's cast-into-declared-dtype-then-rewrite: (a) `deploy.py` does a `shutil.copy2` byte copy, never `to_parquet()`, so repeated runs are byte-identical by construction (verified, acceptance b); (b) dtype checking is read-only (compare `str(df[col].dtype)` to the declared string), never a coercion, since BenchUp's shipped dtypes are already exactly what the contract declares. |
| the Lorraine Explorer's `lib/artifact.py` (`check_completeness`) | the idea of a CODE (not eyeball) completeness check that walks a data-contract-shaped structure and reports every uncovered column as a named violation, never silently | `app/ops/contract_check.py`'s "undeclared drop vs source_manifest.json table_schemas" check | IDEA only, not code: `check_completeness` is a bespoke column-family/exemption-token parser for a different (`data_foundation.yaml`) shape; `contract_check.check()` instead diffs `source_manifest.json`'s `table_schemas` dict directly against `data_contract.yaml`'s declared columns — simpler because BenchUp's source manifest already lists columns as a flat dict per table (no family/alias parsing needed). |

## 2. Engine — merged from `app/lib/engine/VENDORED_engine.md`, snapshot 2026-08-29

Provenance for the engine only. Everything below was **copied**, not rewritten: the numbers this
app shows are the numbers `evals/campaign_v2/gen_lists_v2.py` produced, and
`tests/test_golden_lenses.py` pins that (37 seeds × 10 lenses + concordance + aspirational + seed
card, 37/37 PASS).

Source root: the prior working codebase this project was trimmed forward from (paths below are relative to it).

### 2.1 Module map — source → destination

| Source | What was taken | Destination | Form |
|---|---|---|---|
| `pipeline/agg/trees_agg.py` | module docstring, `TREES`, `G6_FLOOR`, `subfield_to_field_map` | `trees_agg.py` | verbatim slice |
| `pipeline/agg/derive.py` | `_posix`, `_detect_year_cols`, `_cast_output`, `derive_shapes`, `VALID_BASES` + the whole docstring | `derive.py` | verbatim, `__main__` self-test dropped |
| `pipeline/agg/l2_variants.py` | `VALID_VARIANTS`, `_apply_variant`, `_raw_scenario`, `_dense_from_scenario`, `l2_vectors` | `l2_vectors.py` | verbatim slices, new import header |
| `evals/analysis_eu/lens_lib.py` | whole file (loaders, matrix builders, `histogram_intersection_row`, `excess_profile`, `top_k_excluding_self`, `D19_SEEDS`, `SDG_LABELS`, codebook loaders) | `lens_lib.py` | verbatim + path/import fixes |
| `evals/analysis_eu/r2/lens_lib_r2.py` | `excess_profile_matrix` | appended to `lens_lib.py` | verbatim |
| `evals/campaign/gen_lists_recall.py` | `load_everything`, substrate builders, `rank_map`, `is_degenerate`, `base_evidence`, `build_seed_card` | `substrates.py`, `lenses.py` | formulas verbatim, IO/CLI removed |
| `evals/campaign_v2/gen_lists_v2.py` | L0 substrate, tie-inclusive cut helpers, `competition_ranks`, `concordance`, `aspirational`, `catchall_811_share`, `rank_all`'s per-lens branches | `lenses.py`, `tests/test_engine_identity.py` | formulas verbatim |

Resources: `reference/taxonomy_repair_v1.3/openalex_subfield_codebook_v1.csv` and
`evals/erc_calibration/id2label_verification.json` → `lib/engine/resources/`.
Golden fixtures: `evals/campaign_v2/lists/I*.json` (37), `evals/face_validity_ids.json`,
`evals/campaign_v2/panel_v2.json` → `app/tests/golden/`.

### 2.2 Deviations from the sources (full list, verbatim from Stream B)

**Mechanical:** package-relative imports replace `sys.path` surgery; CLI/IO/rendering
(checkpointing, markdown renderers, external-peer marking) not ported; `RANK_VISIBLE_MAX = 50` is
a module constant; `base_evidence` merges the v1/v2 variants (golden carries the v2 shape);
Streamlit-free (asserted by grep).

**Parametrised where the generators hard-coded:** `rank_all`/`concordance` take the lens set and N
as arguments (golden pins `{L1,L3,F1,L2f,L4,L5,L6}` at N∈{10,20,30}); `build_substrates(ctx, tree,
basis)` threads both through every lens; `basis_applies` flags L4/L5/L6/L7 as fractional-only;
`pool`/`depth` are parameters, not hard-coded constants; `cut_with_ties` fuses the id/score-pair
tie-inclusive cut into one function.

**Data-layer deviations (measured, could move a number):**
1. `topics_all` read with 5 columns only (`inst_key, topic_id, share_frac, vol_frac, vol_full`) —
   L3/F1/catch-all key on integer `inst_key` position, not `institution_id`; the resulting scatter
   matrix is bit-identical to a pivot-table build (0 differing cells of 7,557×4,516).
2. **Memory order is load-bearing**: the topic matrix must be F-contiguous (C-order changes an L3
   score by 1.4e-6, outside the golden's 1e-6 tolerance) — do not "clean up" this allocation.
3. L1/C1 always come from `derive_shapes`, never the shipped `subfields.parquet`, even on the
   default scenario (the two agree only to float32, which can move a top-50 tie) — the golden
   pins the derived values.
4. L0 on the default scenario comes from the shipped `fields.parquet` (asymmetric with #3 on
   purpose — both halves follow the golden).
5. `impact_cells.parquet` is not loaded by `load_context` (lazy); aspirational reads PP columns
   from `index.parquet` directly.
6. `exclude_811` is hard-wired `False` (the UI toggle was removed by design).

**Documented upstream nuances preserved (not bugs — do not "fix"):** the G6 floor stays on
`vol_frac` regardless of displayed `basis`; the mean-share population is institutions with a
NONZERO row for that cell, not the whole index; `si` is NaN below the floor and must stay NaN, not
0; `sdg.share` is multi-label (Σ>1 per institution); L0 spans 26 fields (no 19-field cut exists in
the shipped taxonomy); aspirational rows stay in L1-overlap order, never re-sorted by PP.

### 2.3 Known limits of the Tier-A identity check
`basis="full"` has no reference table to check against (trees_agg never computed it); one
G6-floor boundary cell (`vol_frac == 30.0` exactly, tree=original) falls on opposite sides of the
floor between the two computation paths; float32 cell-level noise (worst measured 1.2e-7, a float32
ulp) is reported by the test, not asserted away; the tolerance is symmetric (`|a-b|/max(|a|,|b|)`),
never `np.allclose`'s asymmetric `rtol*|b|`.

---

## 3. `umbrella_supplement.csv` — content provenance (this stream)

24 named umbrellas + their `institution_id`s are taken verbatim from
`evals/campaign_v2/badge_calibration.json`'s `known_umbrellas_found` dict (all 24 resolved,
0 blank ids — the 25th named umbrella, Helmholtz Association, has no OpenAlex institution row and
is omitted entirely per `badge_calibration.md`, not shipped with a blank id). Cross-checked against
`app/data/index.parquet` 2026-08-29: all 24 institution_ids present, `type`/`type_openalex` and
`total_full_2020_2024` spot-checked. The 3 "structurally unflaggable" notes (Fraunhofer Society,
Portuguese FCT, UKRI) are copied verbatim from `config.yaml`'s
`proposal_r5.umbrella_badge.structurally_unflaggable` list and `badge_calibration.md`'s "Structural
(non-tunable) misses" section. The file is shipped **ASCII-safe** (accents transliterated — e.g.
"Ciencia" not "Ciência", "Cientificas" not "Científicas") rather than UTF-8, matching this stream's
brief; `index.display_name` remains the UTF-8, fully-accented source of truth for these same
institutions where the app needs to display them elsewhere.
