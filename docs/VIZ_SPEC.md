# VIZ SPEC — BenchUp Find tab

**Produced by:** the design team, before any page exists. Format follows an earlier
SIRIS studio run's own VIZ_SPEC convention: one app-wide system
section, then one row per view, each with form / encoding / interaction /
empty-state / export / composition and a named rejected alternative.
**Contract, not restated:** `INDICATOR_SPEC_v2.md` (lens statuses, recall figures,
judged reads, closed micro-choices) and the decisions log §1 (locked decisions
L1–L15) are binding and only summarised here where a viz decision hangs on them.
**House rules:** light mode only, full width, render-verify at 1920/1280/390 px.
`dataviz` skill loaded; palette validated `--mode light` only (SIRIS override of
the skill's dark pass) — see `design-system/palette_validation.txt`.
**No static string asserts a value**: every count, percentage and threshold below is written as a
parameter (`{n}`, `{N}`, `{k}`) even where a real number is shown for
illustration — illustrations are marked "e.g." and are never literal UI copy.

---

## 1. App-wide visual system (all Find views inherit)

### 1.1 Colour (computed, not eyeballed — validator runs 1–8, mode light)

Single source: `lib/palette.py`. Full validator log with every command and its
verbatim output: `design-system/palette_validation.txt`.

**The coexistence rule (binding): ONE identity family per chart.** A
chart is coloured by OpenAlex domain, OR by ERC domain, OR by SDG, OR by
document type — never two at once, and never a family plus `FOCAL`. The whole
profile section describes ONE institution, so there is nothing to highlight
against there: painting a bar `FOCAL` inside a domain-coloured panel would
assert a comparison the chart does not make. `FOCAL` therefore appears only in
the ranked/comparison views (seed row, ProgressColumn bars, links). The
yearly-breakdown pair swaps domain ↔ document type through one segmented
control, so exactly one family is on screen at a time and the chip legend is
rebuilt on every swap — which is precisely why the two families' mutual
validator distance is a NON-requirement (§2.14, palette_validation.txt run 6b).

**Family 1 — OpenAlex domains** (`OA_DOMAIN_COLORS`, inherited unchanged,
FIXED): Life `#0CA750`, Social `#FFCB3A`, Physical `#8190FF`, Health
`#F85C32`. **Fields, subfields and topics have no colour of their own — they
INHERIT their domain's** (`palette.domain_color`, a `get_field_color`
inheritance pattern). Because the active TREE decides which subfield, field and domain a
topic rolls up to, colours follow the tree × basis toggles with no extra code.
Unknown / unclassified → `COMPARISON` grey, never a fifth identity.
Validator run 3 is **descriptive**: these hexes are inherited, not chosen, and
its findings are carried as BINDING RELIEF, never as a reason to change a value
(a) `#FFCB3A` lightness 0.865 is outside the band and (b) `#FFCB3A` 1.52:1 /
`#8190FF` 2.85:1 contrast are below 3:1, both relieved because every bar and
segment carries its category name on the axis and every panel ships the same
numbers through the CSV export; (c) `#F85C32`↔`#0CA750` deutan ΔE 7.6 sits in the
6–8 floor band, legal only with the secondary encoding the axis labels provide,
and the two are non-adjacent in the fixed display order.

**Family 2 — ERC domains** (`ERC_DOMAIN_COLORS`, THREE NEW hues):
PE `#1F4E9C` deep blue, LS `#9B1B6B` deep magenta, SH `#8A5A00` dark ochre.
Validated ALONE (run 4, `--pairs all`): **ALL CHECKS PASS**, worst CVD ΔE 8.8
protan, worst normal-vision ΔE 20.3, every contrast ≥ 3:1. Validated TOGETHER
with the four OA hues (run 5, 7 slots, all pairs): the worst all-pairs
normal-vision distance in the whole set is 20.3, so **every OA↔ERC pair clears
the ΔE ≥ 12 requirement by ~1.7×**, and every ERC-involving CVD pair is ≥ 8.1.
The strategy, stated so a future edit does not undo it: OA lives in the light-to-
mid lightness band (L 0.63–0.87), ERC is deliberately a DARK triad (L 0.45–0.55)
on three hue angles OA does not use. Rejected candidates and their measured
reasons are listed in `lib/palette.py`.

**Family 3 — the UN SDGs** (`SDG_COLORS`, 17 stored, **16 drawn**): the official
UN goal colours, FIXED by the UN. Source: taken directly, matching the 2019 UN
guidelines as commonly published; a live check of un.org's communications-material
page confirms the governing document — *Sustainable Development
Goals Guidelines for the use of the SDG logo including the colour wheel and 17
icons*, August 2019 edition, revised September 2023 — but that page publishes the
assets, not the hex table. Validator run 7 **FAILS and is descriptive only**; the
findings are real and oblige structural relief, not a hue change. The sharpest:
`#FD9D24` (goal 11) ↔ `#DDA63A` (goal 2) at normal-vision ΔE 5.3 — the UN palette
contains two near-identical ambers, so **no chart may rely on telling SDG colours
apart by hue**. Relief: the SDG panel is a labelled bar chart in fixed goal order,
every bar carrying its goal number and short label on the axis. Goal 17
(`#19486A`) is stored but never drawn — the classifier does not cover it, and the
panel says so from `palette.SDG_UNCOVERED`, never from a typed string.

**Family 4 — document types** (`DOCTYPE_COLORS`): article `#22A2BD`, review
`#A55F8F`, book `#667900`, book-chapter `#7838B6` (an already-validated
set, taken over unchanged) + **`letter` `#A10A4E`, new for BenchUp** (the hue
an earlier palette carried in that slot; BenchUp's corpus has letters where
that palette had conference papers). The five ALONE (run 6a, all pairs): **ALL
CHECKS PASS**. The new hue clears the OA quartet on its own by min normal-vision
ΔE 24.0 / min CVD ΔE 17.5. The five WITH the four OA hues (run 6b, 9 slots) FAILS
on two PRE-EXISTING pairs that do not involve the new hue (`#667900`↔`#0CA750`
normal 13.1; `#667900`↔`#F85C32` protan 3.3) — disposed of by the coexistence
rule above, recorded rather than suppressed because the swap does put the two
families in sequential memory.

**Focal / comparison / neutral / ink (unchanged):** `FOCAL` `#0072B2` is the seed
institution in the ranked views only — and, mirrored there alone,
`.streamlit/config.toml` `primaryColor`. `COMPARISON` `#8C9196` is candidate rows,
reference marks and every family's unknown/unclassified slot. `NEUTRAL` `#E6E8EB`
is background/zebra/empty-state fill. `INK` `#333333` is text only (the validator
fails it as a series colour by design). `SURFACE` `#FFFFFF` is every figure's
`paper_bgcolor` and `plot_bgcolor`, and is the `--surface` every palette validator run
was executed against.

**Chrome tokens (text and furniture — excluded from categorical validation by
design, run 8 reproduces the expected FAIL):** `INK_SECONDARY` `#5A5F66` for KPI
sublines, gutter numbers, chip labels and axis ticks (6.43:1 on white, above the
4.5:1 body-text floor — the only check that matters for it); `BORDER` `#E3E6EA`
for tile/panel hairlines; `GRID` `#D9DDE2` for gridlines and zero lines, which
must RECEDE, so their low contrast is the requirement and not the defect.

**Flags are SHAPE, never a new hue.** A catch-all (811) topic keeps its domain
colour at `MUTED_OPACITY` plus a glyph in its label; a top-quartile frontier
topic keeps its domain colour with an `INK` outline of `OUTLINE_WIDTH`. Both are
secondary encodings on top of the family colour. BenchUp still defines no
status palette (no good/bad or momentum read exists in the spec).

**REMOVED: `TYPE_COLORS` / `type_group`.** The badge column was removed
from every table (the type filter covers the need),
which left the institution-type identity set with no consumer. A grep before
deletion returned only `palette.py`, `tests/test_palette.py` and two prose lines
in `DESIGN_TOKENS.md` — no live code path — so both symbols were deleted rather
than kept as dead colour. Institution type is now plain text in its own table
column plus a post-filter; the seed's own type sits in the profile header.
`tests/test_palette.py:test_type_colors_removed_in_r1` pins the deletion.

### 1.2 Typography

Base 16 px / line-height 1.5 floor on all body and table text; one precision
level per numeric measure; thousands separator; every percentage states its
denominator in the same cell or the line immediately above it (never a bare
"{x}%"). Full scale: `DESIGN_TOKENS.md` §3.

### 1.3 Control placement — sidebar vs the controls row (supersedes the original all-in-the-sidebar order)

 feedback #1: the sidebar was over-loaded, and controls that act on the
benchmark tables were a page away from the tables they act on. This splits them by
SCOPE, not by type — **the sidebar holds what changes the whole app; a control
that changes one section lives at the head of that section.**

**Sidebar (app-wide only):**
1. **Scenario** — tree (`{original, conservative, bestfit}`, default `bestfit`)
   × basis (`{frac, full}`, default `frac`), with the disclosure line "ERC and
   SDG lenses are fractional-only; this toggle does not change them"
   (INDICATOR_SPEC_v2 §5, L5). Scenario is app-wide because it re-derives every
   shape on the page, profile panels included.

**Controls row (at the head of the Benchmark section, above the lens tabs):**
C1 checkbox · L7 checkbox (depth is fixed at 50, no control needed) — each
with a `help=` tooltip that explains the option rather than naming it — then
a **"Post-filters" expander**
holding type, country, exclude-own-country, size range, scale guard and family.
C1 and L7 stay two SEPARATE affordances, never bundled, and L7 stays the visibly
more discouraging of the two (INDICATOR_SPEC_v2 §1.8/§1.9, ruling 8).

**Widget keys are UNCHANGED by the move** (`depth`, `c1_on`, `l7_on`, `f_types`,
`f_countries`, `f_excl_own`, `f_size`, `f_guard`, `f_family`) and every one keeps
`persist_state="session"` — so cross-page persistence and the Playwright
`st-key-*` selectors survive relocation. That is the whole reason the move is
cheap; a rename would have cost the smoke suite.

The "Filtered by…" strip (§1.4) still names EVERY off-default dimension,
including tree and basis, wherever their control now lives.

> **Rejected alternative:** move depth and the post-filters into each lens tab,
> so every tab carries its own copy. Rejected because the controls are shared
> state across all ten tabs — per-tab copies would either drift (ten widget keys
> for one value) or lie (one value shown ten times, edited in one place). One row
> above the tab strip states once that these settings govern everything below it.

### 1.4 "Filtered by…" strip (mandatory whenever ANY control is off-default)

Appears directly under the page title, one line, and **names every off-default
dimension by itself** — never a generic "filters active" line (COMPOSITION_AND_CONTROLS.md
Control layer #3). Parametric caption, e.g.:

> Filtered by: tree = original · type = education, facility · scale guard on

`None` (the strip renders nothing) **iff** tree = bestfit AND basis = frac AND
C1 off AND L7 off AND every post-filter is at its default — depth has no
control any more (fixed at 50 app-wide) so it is never an off-default
dimension and never appears in this strip — this exact predicate is the
non-vacuity target for toggle × filter matrix test (`test_matrix.py`).

### 1.5 Badge grammar

Text + glyph, never colour alone (`DESIGN_TOKENS.md` §5). **Change:** the
institution-TYPE badge family is GONE together with `TYPE_COLORS` (§1.1) — type
is plain text in its own table column plus a post-filter. Two badge families
remain, both text-only and both seed-level (profile header, §2.10), neither
carrying a colour at all: umbrella/aggregate ("EXPERIMENTAL" text + tooltip
carrying the country×type median compared against) and type-corrected ("type
corrected by SIRIS (was: {type_openalex})"). **Never both an umbrella badge and a type-corrected
badge on the same row** — this is a hard invariant,
not a styling preference, and `badges.py` asserts it in code.

### 1.6 Empty, undefined and thin states

- **Empty (0 rows after post-filters):** name the responsible filter(s) by
  themselves, never a generic "no results" — e.g. "No candidates match `{filter
  A}` ∩ `{filter B}` for this seed at depth {N}. Remove a filter, or increase
  depth to 50." (RULES §8 Empty: an emptied list names the
  filter(s) responsible).
- **Undefined lens** (e.g. L2f with `n_eligible_subfields_L2f = 0`, or F1 for a
  seed with no frontier-topic mass): an explicit reason line replaces the table
  — never a silently empty table, never a gate on the OTHER lenses (INDICATOR_SPEC_v2
  L8 "lens undefined → explicit reason, never a silent empty list") — e.g. "L2f
  is undefined for this seed: 0 shared-specialisation cells clear the ≥30-paper
  floor."
- **Thin** (few candidates returned, e.g. a small seed whose top-50 has fewer
  than 50 real rows before ties): show the true n and continue — never pad, never
  suppress the mark (RULES §8 Thin, tie rule: never pad).
- **Concordance caption always states both N and n** parametrically — "found in
  the top-{N} of {k} of {n} lenses defined for this seed" — n shrinks when C1/L7
  are off (excluded from n unless enabled) or when a lens is undefined for this
  particular seed; k is never recomputed by post-filters.

### 1.7 Export rules

One "Download full ranking (CSV)" button per lens tab, exporting the FULL
filtered ranking (not just the on-screen depth cut), original competition ranks
preserved (gaps kept, not renumbered), plus constant columns for
`seed_id, lens, tree, basis, snapshot, filters` so a downloaded file is
self-describing outside the app. Filename
`benchup_{seed}_{lens}_{tree}_{basis}[_filtered].csv`. No panel is exported as a
PNG-only artefact. A whole-page or xlsx-with-method-sheet export is
explicitly deferred.

### 1.8 390 px degradation

Sidebar controls collapse to Streamlit's native top drawer; main content stacks
in argument order — seed search → profile section → controls row → tab strip (Streamlit's native horizontally-scrollable pill
tabs) → ranked table (its own `overflow-x:auto`, never the page body). Legends
and badges wrap to a second line rather than truncating silently (RULES §8
Small screen). Render-verified at 1920/1280/390 px with `scrollWidth ≤
innerWidth+2` as the acceptance gate; this section only fixes the rule
renders are checked against.

**Additions, measured rather than assumed** (an A/B verdict record,
A/B #3, run at 390x844):

- **The share + SI pair STACKS below the small breakpoint** — share panel above,
  SI panel below, same row order, one shared category axis read twice — because
  side by side at 390 px each panel collapses to a measured 61 px of plot area,
  which is not a chart. Above the breakpoint they stay side by side.
- **The KPI tiles wrap to one per row**, never truncated, sublines intact.
- **The wordcloud + breakdown pair stacks vertically**, cloud first.
- **The six chart panels stay collapsed** and each owns its horizontal scroll;
  the page body still never scrolls sideways.
- **The volume gutter survives at 390 px** (0 clipped annotations measured,
  against 1 clipped for the rejected right-of-bar form) — which is one of the two
  reasons it won A/B #4.

### 1.9 Profile section composition (replaces the seed card of §2.2; re-lays the rows as a reference dashboard's grid, not just its chart panels)

Feedback: the page was chart-poor. Further feedback:
the resulting layout still read as "leftovers" — a coverage line with no clear
audience, a wordcloud oddly paired with a chart it has nothing to do with. The
fix is a reference dashboard's actual GRID, not just its panels. Fixed order,
top to bottom:

1. **Row 1 — three columns, `[1.0, 2.0, 1.4]`** (§2.10–§2.13): **identity**
   (name, type · city, country NAME, seed-level badges, links) | **KPI tiles**
   (2×4 grid, eight tiles, each positioned against the index baseline) |
   **subfield wordcloud**.
2. **Row 2 — two columns, full width** (§2.14): **global breakdown** |
   **yearly breakdown**, with ONE segmented control and the shared chip legend
   sitting ABOVE both panels — this pair no longer shares its row with the
   wordcloud, so both panels get the full section width instead of half of it.
3. **Six collapsed panels** (§2.15–§2.20), every one `st.expander(expanded=False)`:
   Fields · Top subfields · Top topics · Frontier positioning · SDG profile ·
   ERC profile.

The former "Coverage caption" step is GONE: its four items
relocated to the panel/tile/tab each one actually qualifies, so there is no
longer a fourth composition step between the tiles and the breakdown row.

Rules that hold across the whole section, so they are stated once here rather
than repeated in every row below:

- **Everything shape-grain follows tree × basis.** Colours follow too, for free,
  because a topic's domain is decided by the active tree (§1.1, family 1).
- **ERC and SDG are fractional-only artefacts.** When basis = full, those two
  panels say so in their caption instead of silently ignoring the toggle.
- **One identity family per chart** (§1.1) — the profile section never paints a
  bar `FOCAL`.
- **Grouped bars, never stacked.** The standing rule: "a bar chart may
  never stack a second categorical dimension." The grouped geometry uses explicit
  `offset`/`width` under `barmode="overlay"` because `offsetgroup` is BROKEN on
  the pinned plotly 5.24.1 (`lib/charts.py:_series_offset_width`,
  verbatim).
- **The paired share + SI form and the left volume gutter are A/B verdicts on
  real data**, not preferences — an A/B verdict record,
  A/B #3 and #4.
- **Every panel that drops rows says how many it dropped**, from the data
  (`is_excluded.sum`, unscored counts), never from a typed number (L10).
- **No panel is a PNG-only artefact**: every panel's numbers are also in the CSV
  the section exports.

> **Rejected alternative:** render all six panels expanded, as one long scroll
> (an earlier layout). Rejected on the measured cost: the six panels are
> ~150 plotly traces and >1,300 marks for a large seed, all built on every rerun,
> against a warm-rerun budget of 1.5 s; and the section's job is to characterise
> the seed in one screen before the reader goes to the benchmark tables, which a
> six-panel scroll defeats. Collapsed-by-default keeps the header + tiles +
> breakdown pair above the fold and makes each panel an explicit choice.

---

## 2. View specs — one row per Find view (9 original views; §2 bis adds 13 more)

Status: all **[NEW]** — is the first build of this app.

### 2.1 Seed search

**Decision sentence:** *After typing a few characters, the analyst can find the
one institution they mean, even with an accent, an acronym, or a typo, and move
on to its benchmark.*
**Composition:** hero search box, no default listing — a search-first page
(COMPOSITION_AND_CONTROLS.md harvested pattern "search-first directory": "the
default state is a search prompt. NEVER a full default listing").

| Form id | Form & encoding | Interaction | Empty-state | Export |
|---|---|---|---|---|
| `search-seed` | text input; ≤10 ranked candidates below as a plain list (name · country · type · size), rank = exact name > prefix > substring, fuzzy fallback on token vocabulary | type-ahead on every keystroke (debounced by Streamlit's own rerun cadence); click a candidate to load its seed card | 0 matches: "No institution matches '{query}'. Check the spelling, or try an acronym." — no silent blank | — (not an exportable view) |

**Rejected alternative:** a full alphabetical directory as the page's default
state — rejected on the same COMPOSITION_AND_CONTROLS.md precedent above: a
default listing (alphabetical or otherwise) invites a scan-ranking read the
Find tab never intends, and blows the row budget for no benefit when a search
box resolves the same task in one keystroke sequence.

### 2.2 Seed card

**Decision sentence:** *After reading the card, the analyst can describe the
seed institution's shape, size, and impact position well enough to judge whether
any candidate below is a fair comparison.*
**Composition (argument order, top to bottom):** (1) header — name, `FOCAL`
underline/marker, type + badge, country, ROR link, homepage link; (2) KPI row
size full **and** fractional (both, each with its own label — never one number
presented as if it were the other), HHI class (a named band, not a bare
number), breadth (n subfields); (3) top-3 fields / top-5 subfields (bestfit,
current scenario) as a short text list, not a chart (RULES form heuristic: a
3–5 item share-of-whole reads faster as text than as a pie); (4) evidence lines
(erc-classified mass share, SDG-tagged share, frontier-top25 share, catch-all
share) — continuous, never a pass/fail gate (INDICATOR_SPEC_v2 L8); (5)
PP(top10%) with its CI, stated as "{pp} [{ci_low}–{ci_high}]" — never the point
estimate alone (RULES honesty rule 6); (6) OpenAlex works deep link
(`authorships.institutions.id:{id},publication_year:2020-2024`), filtered to the
same window used throughout.
**Empty-state:** a seed with `catchall_811_share` undefined (no 811-adjacent
topics at all) shows "n/a" (`palette.NA_MARK`), never 0.
**Export:** none at the card level, deferred (the ranked-table exports below carry
the seed's own row wherever it appears as a candidate for another seed).

| Form id | Form & encoding | Interaction | Empty-state | Export |
|---|---|---|---|---|
| `card-seed` | header + KPI tiles + text lists + evidence lines + CI line + 3 outbound links, as composed above | outbound links open in a new tab; no in-card filtering (one primary interaction per view is spent on the search box that produced this card) | undefined evidence line → `NA_MARK`, never 0 | — |

**Rejected alternative:** a radar/spider chart for the top-3-fields shape
rejected on the same grounds already documented for an analogous
profile card (`VIZ_SPEC.md` §2.6): angle encoding is weak and OpenAlex fields
are not comparable radially; a ranked text list states the same three shares
more precisely in less space.

### 2.3 Concordance overview

**Decision sentence:** *After seeing the overview, the analyst can name the
candidates multiple independent lenses agree on, before opening any single
lens tab.*
**Composition:** displayed prominently as the FIRST tab (INDICATOR_SPEC_v2 §3:
"display prominently as the overview, still never the sole ranking") — a
k-count table: candidate, k of n lenses hit (chip per hit lens, e.g. `L1 L3 F1`),
per-lens rank on hover/expand. Caption states N and n parametrically (§1.6).
Rows removed by post-filters disappear from the table but k is **never**
recomputed (k/n is computed on the unfiltered ranking).

| Form id | Form & encoding | Interaction | Empty-state | Export |
|---|---|---|---|---|
| `tbl-concordance` | table: candidate · country · type+badge · k (of n) · hit-lens chips · size, sorted by k desc then by the best individual lens rank | row click ↔ jump to that candidate's rank in the first hit lens tab; search box for the tail | 0 candidates hit ≥2 lenses: state it plainly and point at the single-lens tabs, never an empty grid | full concordance table CSV (candidate, k, n, per-lens ranks) |

**Rejected alternative:** as this row's DEFAULT — not eliminated outright: this
exact contrast (k-count table vs. a full rank matrix of candidates × lenses) is
**Cross-cutting A/B #2** in §3 below, resolved on real data by. The
k-count table is proposed as the working default because INDICATOR_SPEC_v2 §3
already calls concordance "the cleanest list" (15 sensible / 1 mixed / 0
nonsense, the best judged read of any lens/mode) and a single sortable k number
serves that read more directly than a matrix that needs full lens-column width
to stay legible at 1280 px.

### 2.4 Lens tab (shared form, all 10 lenses)

**Decision sentence:** *After opening any one lens tab, the analyst reads
exactly the same table shape they already learned on the first lens — rank,
who, where, what kind, how big, how strong the read is, and why it might be
noisy — for L0 through L7 and both optional lenses alike.*
**Composition:** gloss (one line, from the table below) + evidence line +
caveat, ALL above the table, never buried in a tooltip only; then the ranked
table; then the depth caption (§2.6) and tail search + export (§2.7) below it.
**Same read, same form** (`VIZ_SPEC.md` §3 rule 1): every one of L0,
L1, L3, F1, L2f, L4, L5, L6, C1, L7 renders through the ONE shared form id
below — never a bespoke per-lens layout.

| Form id | Form & encoding | Interaction | Empty-state | Export |
|---|---|---|---|---|
| `tbl-lens-ranked` | table: competition rank · institution (OpenAlex works deep link) · country · type+badge · size (full) · score (form decided by Cross-cutting A/B #1, §3) · evidence (continuous line, lens-specific) · secondary reference "rank under L1/L3" · add-to-shortlist button (retired) | column sort disabled on score (rank order IS the read — RULES honesty rule 6, no re-sorting past what the ranking already asserts); search scoped to the full ranking (§2.7) | lens undefined for this seed → §1.6 reason line replaces the table entirely | full filtered ranking CSV, §1.7 |

**Per-lens gloss + caveat (source: `INDICATOR_SPEC_v2.md` §1; caveat sits
directly under the gloss, never tooltip-only, per the placement rule):**

| Lens | One-line gloss | Caveat shown with it |
|---|---|---|
| L0 | Field-grain overlap — the coarsest shape, 26 OpenAlex fields | Generic look-alikes for concentrated profiles; moderate outlier crowding among the defaults |
| L1 | Subfield overlap — the anchor lens | Safe to read to rank 50; the most consistently informative lens across seeds |
| L3 | Topic overlap — the workhorse, highest recall of all 10 | Highest same-country clustering of any lens (country post-filter tooltip shown on this tab specifically) |
| F1 | Frontier-topic overlap | Under-represents Social Sciences & Humanities profiles |
| L2f | Shared specialisations (≥30-paper floor per cell) | The failure axis is a diffuse profile, not raw institution size — reads well for concentrated mid-size institutions, poorly for very diffuse or very thin ones |
| L4 | ERC panel overlap | Occasional company/governance leakage into the candidate set |
| L5 | ERC specialisation | The lens with the thinnest external corroboration of the 8 defaults — kept because it still surfaced peers no other lens found; read its candidates with that in mind |
| L6 | SDG profile overlap | Country clustering below L1's — not a peer-finding artefact |
| C1 (optional) | Core-shape — L1 restricted to the seed's own top-20 subfields | A refinement of L1, not a sibling of L7; noise grows faster than L1's past rank 20 |
| L7 (optional, separate toggle) | Experimental SDG-specialisation view | Mostly noise, occasionally unique — the worst judged read of any lens/mode this cycle; kept for the rare peer no other lens surfaces |

L5 and L7's caveats are written to the honest-but-non-alarming standard
(`Portfolio Mapping\units\press\INBOX.md`: neutral, FR-ready vocabulary, no
loaded metaphors) — L5's copy states a fact ("thinnest external corroboration")
rather than a verdict ("weakest"/"unreliable"); L7's copy is the literal
ratified UI string from INDICATOR_SPEC_v2 §1.9 ruling 8 ("mostly noise,
occasionally unique") and is intentionally more discouraging in placement
(§1.3 #3) than in wording — the wording stays factual, the AFFORDANCE carries
the discouragement.

**Rejected alternative:** ten separately laid-out per-lens tables (different
column order/labels per lens) — rejected because a reader would have to relearn
the table on every tab switch, and because `ranked.py` exists
specifically to prevent ten divergent implementations of the same row-rendering
logic.

### 2.5 Aspirational tab

**Decision sentence:** *After opening this tab, the analyst sees which
candidates already found by L1 look like they may be punching above the seed's
current impact level — with the uncertainty on that read shown, not hidden.*
**Composition:** the L1 top-50 pool (tie-inclusive) filtered to
`pp_top10_frac > seed` AND `pp_ci_low > seed pp_ci_high`, kept in L1-overlap
order (this order is what the golden regression pins); a PP
sort is offered as an explicit control, never the default.

| Form id | Form & encoding | Interaction | Empty-state | Export |
|---|---|---|---|---|
| `tbl-aspirational` | `tbl-lens-ranked` base columns, PP(top10%) column replaced by an interval mark: point estimate + CI whiskers rendered per row (RULES form heuristic, Uncertainty/coverage family: "interval dot/caterpillar + n/coverage") | default sort = L1-overlap order; "sort by PP" toggle re-sorts by point estimate, CI still shown | 0 candidates clear the interval test: "No L1 candidate's impact interval sits fully above {seed}'s at this depth." — never silently blank | full pool CSV incl. `pp_top10_frac, pp_ci_low, pp_ci_high` |

**Rejected alternative:** `st.column_config.ProgressColumn` for the PP value
alone — the shared-form default being evaluated for ordinary lens tabs in
Cross-cutting A/B #1 (§3) — rejected specifically for THIS tab regardless of
that A/B's outcome, because a single progress bar cannot render an interval,
and RULES honesty rule 6 explicitly forbids presenting a ranked value without
its uncertainty ("do not narrate rank 7 vs 8 when intervals overlap"). The
interval mark is not optional here even if it loses the general-purpose A/B.

### 2.6 Depth control

**Decision sentence:** *Depth is fixed at 50 for every Find lens, concordance
and aspirational table, so the analyst always knows exactly how many rows
they are looking at out of how many computed, and that the rest is one
search or one download away, not gone.*

| Form id | Form & encoding | Interaction | Empty-state | Export |
|---|---|---|---|---|
| `ctl-depth` | **RETIRED.** The two-option depth segmented control is gone; depth is fixed at 50 app-wide (`config.yaml`'s `depth.default == depth.max == 50`, single source). Caption under every table: "showing top {N} of {M} ranked — search the tail or download" (RULES §9.9) | none — there is no control; `M` and `N` are always read from the live ranking, never typed | — (depth never empties a non-empty ranking) | — (the caption itself is not exportable; the CSV always carries the full ranking regardless of the on-screen depth) |

**Rejected alternative:** a continuous slider over the full ranking length
rejected on simplicity grounds ("ONE global control, not a
per-lens cutoff") and because a freely-draggable depth would need its own
per-value caption logic where a two-option control needs one sentence with two
possible fills; the real per-lens noise-growth-with-depth difference
(INDICATOR_SPEC_v2 §1 table) is handled by disclosure and the post-filter
layer, not by a finer-grained depth control.

### 2.7 Tail search + CSV export

**Decision sentence:** *After the analyst searches for a name they expect but
don't see in the top {N}, they can find it in the full ranking or take the
whole thing away as data.*

| Form id | Form & encoding | Interaction | Empty-state | Export |
|---|---|---|---|---|
| `ctl-tail-search` + `btn-export-csv` | text input scoped to the CURRENT lens's full ranking (not just the on-screen depth cut); one "Download full ranking (CSV)" button beside it | type a name → matching rows appear below the visible table with their true (uncut) rank, even past 50 | 0 matches in the full ranking (not just the depth cut): "'{query}' does not appear anywhere in this lens's ranking for this seed." | CSV per §1.7 |

**Rejected alternative:** pagination or infinite scroll through the tail
instead of search + download — rejected on ponytail grounds (ponytail: "one
line before fifty" — Streamlit has no built-in paginator worth adding a
dependency for) and because the tail is, by construction, a rarely-visited
long list (RULES §9.9's own remedy is "keep the long tail searchable/
downloadable," not "keep it browsable").

### 2.8 Badges (umbrella, type-corrected, catch-all)

**Decision sentence:** *After seeing a badge, the analyst knows in one glance
why a row's numbers might need a second look, without the badge ever implying
the row is wrong or excluded.*
**Composition:** inline in the type/name cell of every ranked table (§2.4);
never a separate panel (RULES §8 "disclose, never demote" — same principle
the ARTIFACT-FLAG pattern already applies: a flag discloses, it does not
grey out or hide the row).

| Form id | Form & encoding | Interaction | Empty-state | Export |
|---|---|---|---|---|
| `badge-umbrella` / `badge-type-corrected` / `chip-catchall` | text label + tooltip (median compared against / `was: {type_openalex}` / catch-all share number); institution-type dot from §1.1 where applicable | hover/tap for tooltip detail; badges are never clickable filters (COMPOSITION_AND_CONTROLS.md Control layer #7: "legends filter only when clickable state is obvious" — these aren't legends) | a row with no applicable badge shows none — absence of a badge is not itself a signal requiring an empty-state | badge state is a plain column in the export CSV (not just a visual) |

**Rejected alternative:** a single merged "flag" icon standing in for either
umbrella-or-type-corrected — rejected because it would visually erase the
"never both on one row" mutual-exclusion invariant that the
two SEPARATE, distinctly-worded badges make legible at a glance; RULES §4's
"never encode two facts as one colour" reasoning generalises to "never encode
two facts as one badge."

## 2 bis. View specs — the profile section and the changed controls/tables

Same row format as §2.1–§2.8: form / encoding / interaction /
empty-state / export, each ending in ONE named rejected alternative. Builders
live in `lib/charts.py` (pure plotly, no Streamlit import); `lib/views_find.py`
composes. Frames are the §9.4 column contracts from `lib/profile_data.py`.

**§2.2 (Seed card) is SUPERSEDED by §2.10–§2.20** and is kept only as the record
of what the original page did.

### 2.10 Profile header

**Updated ("profile space not optimised, a reference dashboard card as
the model"):** the header is now COLUMN 1 of the section's three-column
row 1 (`[1.0, 2.0, 1.4]` — identity | KPI tiles | wordcloud, §2.11–§2.13), not a
full-width block above the tiles. Nothing about the header's own content or rules
changes — only its position and width, which is why this row's prose below is
otherwise the original text unaltered.

- **Form.** One block filling column 1: institution name (`text-xl`), then a
  meta line "type · city, country NAME", then the seed-level badges, then a link
  row — ROR · OpenAlex works · homepage. The OpenAlex-works link sits beside the
  `PUBLICATIONS_TOOLTIP` that states the corpus
  definition once for the whole section, so every tile and panel beneath it can
  say "publications" without re-explaining doc types, the DOI requirement or the
  bonus year each time.
- **Encoding.** Text only; no chart, no colour. Type is a WORD, not a coloured
  dot (§1.1: `TYPE_COLORS` removed). Country is the English NAME, never the
  two-letter code (L22, `lib/countries.py`, frozen `data/countries_en.csv`).
  Badges keep their original rules exactly — umbrella/aggregate (EXPERIMENTAL +
  tooltip carrying the country × type median compared against) and type-corrected
  ("type corrected by SIRIS (was: {type_openalex})") — and the hard invariant
  that **never both on one row** still holds.
- **Interaction.** The OpenAlex link carries the harvest's OWN server-side
  filters (L23: institution, the year window, the five corpus types, `has_doi`),
  percent-encoded; a link that silently returned a different corpus than the app
  counted was bug #9. Badges expose their evidence on hover only — the
  visible text stands alone without it (§1.5).
- **Empty state.** A missing ROR, homepage or city drops that item silently
  rather than rendering an empty affordance; a missing TYPE renders `n/a`, never
  a blank or a guess.
- **Export.** Nothing of its own; the identity columns ride in every CSV.

> **Rejected alternative:** keep the institution-type colour dot beside the type
> word, reusing the earlier `TYPE_COLORS`. Rejected because the badge column that
> justified a five-hue identity set is gone (L22) and a lone dot on the header
> would be a fifth colour family competing with the four the profile section
> actually encodes (§1.1) — one entity's own type is not a categorical worth a
> hue when it is stated in words two characters away.

### 2.11 KPI cards

`lib/views_find.py`'s `_profile_cards`/`_card_specs` build EIGHT cards in a
2×4 grid filling the left half of the profile row (cards left, identity and
its wordcloud right): publications, SDG-tagged share, frontier top-quartile
share, PP(top10%), international co-publications, industrial co-publications,
star papers, and topics led. Concentration (HHI), breadth, the two separate
size measures (merged into the publications card's fractional-basis small
line) and the bonus-year figure (now read on the yearly breakdown's own year
axis, §2.14) are NOT cards — dropped or relocated, not carried forward from
an earlier tile design.

- **Form.** `tiles.kpi_tile`: **value + label + one small line**, chrome
  `NEUTRAL` fill, `BORDER` hairline, `INK` value, `INK_SECONDARY` subline —
  all from `palette.py`, never inline hex. Every definition that used to
  print as a subline now lives in the card's own `?` tooltip: the card
  surface carries only the name, the value and (for six of the eight) the
  index position.
- **Encoding.** Fixed order (`copy.FIND`'s `KPI_*_LABEL`/`KPI_*_HELP` keys):
  publications · SDG-tagged share · frontier top-quartile share · PP(top10%)
  · international co-publications · industrial co-publications · star papers
  · topics led. Six of the eight position their value against the index
  ("index median {m} · higher than {pct} of institutions"); the publications
  card's small line is the same measure on the fractional basis instead
  (a companion figure, not an index position); star papers and topics led
  read `index.parquet` directly (the newer columns).
- **Interaction.** None (a card is not a control).
- **Empty state.** `n/a` (or `MISSING_KPI_MARK` for the two newer cards) for
  anything the data cannot support — never 0, never a hidden card (§1.6,
  `palette.NA_MARK`).
- **Export.** The same eight numbers are the seed's row in every CSV the page
  writes.

The single caption line once shown under an earlier tile design is gone: its
items each moved to the place they are actually read instead of a
pre-emptive list nobody had context for yet — ERC-classified mass share to
the ERC panel caption (§2.20), catch-all (811) share to the top-topics panel
caption (§2.17), and SDG-tagged share to a card (§2.11) above.

### 2.13 Subfield wordcloud

**Updated:** moves from "left half of a wide row shared with the yearly
breakdown" to COLUMN 3 of row 1 (identity | tiles | wordcloud, `[1.0, 2.0, 1.4]`)
— it now sits beside the tiles it illustrates, not beside the breakdown pair,
which has its own row (§2.14) with the global panel it was never paired with
before.

- **Form.** A PNG (a `WordCloud` → `PIL` → `st.image` pattern, copied
  into `lib/wordcloud_png.py`), filling column 3 of the section's row 1.
- **Encoding.** **Word size = the subfield's works on the CURRENT basis; word
  colour = its domain colour** (`palette.domain_color` through a `color_func`),
  so the cloud re-tints itself when the tree changes and re-weights itself when
  the basis changes. The caption states both encodings — a wordcloud whose size
  channel is unstated is a decoration.
- **Interaction.** None: it is a raster. Every number it hints at is available
  precisely in §2.16 immediately below it, which is what makes an
  interaction-free ornamental form acceptable here rather than a dead end.
- **Empty state.** A seed with no subfield mass renders the empty-state panel
  (`NEUTRAL` fill) and the reason, never a blank white box.
- **Export.** None of its own (§1.7: no PNG-only artefact) — its underlying
  frame is exactly §2.16's CSV.

> **Rejected alternative:** a plotly treemap of subfields, sized by works and
> coloured by domain. It is interactive, exportable and quantitatively honest
> and it was still rejected: the user asked for the word cloud by name, and
> the treemap would duplicate §2.16's bar panel in a second, weaker geometry
> (area comparisons across non-adjacent rectangles) two rows above it. The cloud
> earns its place by being the one deliberately impressionistic object on the
> page; a second precise chart would not.

### 2.14 Yearly breakdown pair

**Updated:** this pair's own FORM is unchanged — it was already the global +
yearly pair under one control before. What changes is its ROW: it moves out
of sharing a row with the wordcloud (§2.13) into its OWN full-width row 2,
directly under row 1's three columns, so both panels get the section's full
width instead of half of it each.

- **Form.** Row 2 of the section, full width: two figures side by side under
  ONE `st.segmented_control` and ONE shared chip legend, both sitting ABOVE the
  pair. **Left** = global horizontal bars, one per series, sorted by volume
  descending, direct end labels, no legend (`charts.fig_breakdown_global`);
  **right** = per-year GROUPED bars (`charts.fig_breakdown_yearly`). Both
  render `showlegend=False`; `charts.chip_legend_html` is the ONE legend for
  the pair (`render_chip_legend`).
- **Encoding.** The segmented control swaps the IDENTITY FAMILY: OpenAlex domain
  (from `profile_data.yearly_by_domain`) ↔ document type (from the
  `doctype_by_year.parquet` artefact). Series order is the family's FIXED order
  (`palette.OA_DOMAIN_ORDER` / `palette.DOCTYPE_ORDER`), never a data-dependent
  sort, and a series that is zero across every year is KEPT so the absence is
  visible. Years are STRINGS (a numeric x-axis autoranges and ticks unlike every
  other chart here). The window covers the analysis years plus 2025 as a labelled
  **bonus year** — partial by construction, said so in the caption, taken from
  CFG rather than typed.
- **Interaction.** One control drives both figures, so they can never disagree.
  Hover gives series, year and volume; the direct end labels on the left panel
  mean the global read needs no hover at all.
- **Empty state.** A year with no output still renders its (empty) group — a
  missing year is data. A seed with no doc-type rows falls back to the domain
  view and discloses the fallback, never silently.
- **Export.** The pair's frame is one CSV (institution × year × series × volume).

> **Rejected alternative:** ONE stacked bar per year, with the segmented control
> choosing what is stacked. It is more compact and gives the year total for free
> — and it is forbidden here: the standing rule is that "a bar chart may
> never stack a second categorical dimension", because a stack makes the year
> total the figure and hides each series' own trajectory, which is the only claim
> this pair exists to make. (The same rule is why the grouped geometry uses
> explicit `offset`/`width`: `offsetgroup` is broken on plotly 5.24.1.)

### 2.15 Panel — Fields (share + SI)

> **Gutter, margin and reference SUPERSEDED by §12 (bar-layout contract,
> D28)** — the volume gutter is now its own phantom-trace column (not folded
> into the tick text), the left margin is the CONSTANT `LABEL_COL_PX["find"]
> + GUTTER_COL_PX["find"] + COL_PAD_PX`, and the neutral SI/ESI reference
> below is a full-height RED dashed line (its connecting stem retired) —
> everything else in this row (the unit grid, the dot family, the taxonomy
> sort) is unchanged.

- **Form.** `st.expander(expanded=False)`. Inside: `charts.fig_share_si(family="oa")`
  — two aligned panels of one figure sharing the y axis; share bars left with the
  volume in a left gutter column, SI lollipops right against a dashed reference at
  the neutral value (A/B #3 and #4 winners), plus a **unit grid** — a
  light `GRID`-coloured vertical line at every integer 1, 2, 3 … up to the SI
  axis's own max, tick-labelled at those integers, so a reader can place a dot
  at "about 2.3×" without hovering.
- **Encoding.** One row per field, coloured by the field's DOMAIN (inheritance,
  §1.1). Share is on the current basis; SI has **no floor at field grain** (the
  G6 floor applies to subfields only — the data contract says so on both rows;
  L34 confirms this row explicitly: "Fields: no floor," only the zero-volume
  no-mark rule applies here). A field's mark is FILLED (never hollow) whenever
  it has a defined SI and nonzero volume, since the solid/hollow floor distinction
  is a subfield-grain concept (§2.16) that does not exist at field grain.
- **Interaction.** A sort toggle: **volume** (share descending) | **taxonomy**
  (domain → field id). Colour follows the entity, never the rank, so the toggle
  never repaints anything (`tests/test_charts.py` pins this).
- **Empty state.** A field with zero mass is absent (it is not a fact about the
  seed); a field with mass but undefined SI keeps its bar and gets NO SI mark
  never a dot at zero, never a dot at the neutral value; a field with mass but
  ZERO volume also gets no mark, whatever any `si_status` might otherwise say
  (the ERC-bug fix generalised to every panel this builder serves).
- **Export.** CSV of the panel's frame, all columns, full precision.

> **Rejected alternative:** a single chart with SI encoded as bar colour
> intensity over the domain hue. Rejected because it destroys the domain
> inheritance that makes every panel in this section legible as one system (a
> field would no longer be its domain's colour), and because a lightness ramp
> laid over four different hues is not comparable across hues — the reader cannot
> tell a "strong" yellow from a "weak" green.

> **Fix X3 (inspection finding I-4).** A/B #4's own verdict
> (§5, "left text gutter, numbers right-aligned against the zero baseline")
> held at 1280 px but broke at 390 px: the gutter number was a SEPARATE
> annotation from the y-axis category label, so nothing kept the two apart at
> the narrow breakpoint — they merged into unreadable text ("hemistry,
> Genetics and Molecular Biolog213.7"), truncated from BOTH ends. Verdict kept,
> mechanism made robust: the volume now folds INTO the y tick text as ONE
> right-anchored string per row (`lib/charts.py:_tick_display`), so there is
> nothing separate left to collide with; a label longer than
> `charts.MAX_LABEL_CHARS` is ellipsised from the RIGHT only, never the left,
> with the full label kept in hover/customdata (`_truncate_label`); the left
> margin is reserved from the longest resulting string
> (`_gutter_margin_px`) because `yaxis.automargin` — measured on plotly 5.24.1
> — only stops a label being clipped by the figure's OUTER edge, not by the
> plot's own bars, so it cannot be relied on alone to keep a long label out of
> the data area. **Robustness rule for any future y-axis-label form in this
> app:** a caption or number placed BESIDE a category label must never be laid
> out by a second, independent text system (a separate annotation, a second
> `<text>` element) at a width where the two can run out of room to stay
> apart — fold them into one string, or reserve the margin the wider of the
> two actually needs, never assume. Proof: `tests/test_charts.py`'s
> truncation/margin tests plus `tests/ui/smoke.py`'s bounding-box check at
> 390 px and 1280 px.
>
> **Updated (REVERSES the ellipsis half of this
> fix, keeps the folding half).** The one-string-per-row mechanism above is
> UNCHANGED and still the reason there is nothing to collide with; what changed
> is what happens to a string over budget. The earlier version ellipsised it from the right
> (`_truncate_label`/`MAX_LABEL_CHARS`/`ELLIPSIS`, all now deleted, not left as
> dead code); this version WRAPS it onto at most two lines at a word boundary instead
> (`charts.wrap_label`), because the user's own read of a shortened field name
> was that losing text is worse than a taller row. Two mechanical consequences
> the next editor should know: (1) `_gutter_margin_px` now measures the
> longest LINE of a (possibly two-line) tick string, not the longest whole
> string — a wrapped row's own margin need can be SMALLER than an unwrapped
> row's, which is correct, not a regression; (2) `charts.row_height` grows a
> row's own budget by `WRAP_ROW_FACTOR` (measured ≈1.7×) for every row whose
> label wrapped, via its new `n_wrapped` argument, so a frame with several long
> names is proportionally taller rather than uniformly cramped. Proof:
> `tests/test_charts.py`'s wrap/row-height/margin tests (§2.15) plus a
> render proof PNG (§5).

### 2.16 Panel — Top subfields (share + SI)

**Rewrite ("top 30, no taxonomy sort" / "SI
charts: unit grid lines; no SI mark at zero volume; harmonised floors").**
Three changes at once, all measured on IFPEN's real profile (top-30 subfields
carry 2 cells ≥30 fractional mass but 17 ≥10 — the old single 30-floor was
throwing away a disclosable signal on 15 of those rows):

- **Form.** As §2.15, `charts.fig_share_si`, on the **top 30 subfields by
  volume** (the caller passes exactly 30 rows — `charts.py` itself types
  neither 20 nor 30 anywhere; the cut is the caller's, not the builder's), plus the same
  unit grid described in §2.15.
- **Encoding.** Domain colour inherited through the subfield → field → domain
  chain, so the panel re-tints with the tree. **SI display is now a THREE-WAY
  floor on fractional mass** (`si_status`, harmonised across subfields/ERC/SDG,
  the panel floor — the lens-ranking floor at 30 is untouched, ratified
  separately): mass ≥30 → **solid** (filled) mark; 10 ≤ mass <30 → **hollow**
  mark (white fill, coloured outline) — a below-the-old-floor cell disclosed
  instead of erased; mass <10, or **zero volume regardless of mass**, → no
  mark at all, `n/a` in the row's hover. On real Gdansk data most subfields
  still sit below even the 10 floor, so a mix of solid, hollow and no-mark rows
  in one panel is the common case, not an edge case.
- **Interaction.** **No sort toggle** (reverses the taxonomy | volume toggle
  §2.15 keeps) — always volume order, because "top 30" is itself a
  volume-ordered concept and a taxonomy re-sort of a volume-defined cut reads as
  an arbitrary 30 rows in ID order. The depth of the cut (top 30) is stated
  parametrically in the panel caption, not typed.
- **Empty state.** If NO row in the frame has a mark-eligible SI (mass <10
  throughout, or every row zero-volume), the figure collapses to a single share
  panel and the caption says why, rather than drawing an empty second axis
  (`charts.fig_share_si` does this itself).
- **Export.** CSV of the FULL subfield frame, not just the displayed top-30 cut
  — the §1.7 rule that an export is never the screen's truncation.

> **Rejected alternative:** keep the single 30-floor (solid-or-nothing) and only
> add the unit grid. Rejected on the IFPEN measurement above: a single floor
> would still show a 2-of-30-marked panel that reads as "SI is mostly undefined
> here," when 17 of 30 cells actually carry a usable (if less certain) reading
> the hollow mark is what lets the chart say "usable, but read it with more
> caution" instead of forcing a binary defined/undefined choice the data does
> not actually make.

### 2.17 Panel — Top topics

- **Form.** `st.expander(expanded=False)` → `charts.fig_topics`: horizontal share
  bars for the top topics by share, volume in the left gutter. Topic names are
  the longest labels in the app, so this panel is the wrap mechanism's
  (§2.15, `charts.wrap_label`) hardest real test — a topic name over
  budget now wraps to two lines instead of losing its tail.
- **Encoding.** Colour = the topic's DOMAIN (inherited through the active tree).
  A **catch-all / out-of-scope (811) topic is flagged three ways at once**: a
  glyph prefixed to its axis label, its domain hue at `palette.MUTED_OPACITY`,
  and a hover line naming it — shape and opacity, never a new hue (§1.1).
- **Interaction.** Sort toggle volume | taxonomy (domain → field → subfield →
  topic). Hover gives the topic, its share and its volume.
- **Empty state.** The panel caption **counts the flagged topics from the data**
  (`topics_dim.is_excluded.sum`), never from a typed number (L10) — a flagged
  topic is shown and counted, never dropped, because its presence is exactly the
  thing a reader needs to discount.
- **Export.** CSV of the full topic frame with `is_excluded` as a column, so the
  flag survives outside the app.

> **Rejected alternative:** exclude the catch-all topics from the panel entirely
> (the earlier 811 toggle's behaviour). Rejected because the toggle was REMOVED
> precisely so the catch-all mass would be disclosed rather than
> switched off: hiding those rows makes a seed's profile look cleaner than the
> data is, and the share they carry is a caveat on every other number in the
> section.

### 2.18 Panel — Frontier positioning

**Rewrite ("frontier panel unreadable/slow: toggle
top-200-by-volume ↔ all global-top-quartile topics").** The panel used to plot
EVERY scored topic at once, which on a large seed is both visually dense and,
per the feedback, slow. It now offers two MODES via a segmented control, each
handing `charts.fig_frontier` a pre-filtered frame — the builder's own API is
unchanged, it never knows which mode produced its input.

- **Form.** `st.expander(expanded=False)` → a segmented control, **"Top {n}
  topics by volume"** (n = `FRONTIER_TOP_N`, a module constant fixed at
  two hundred, `charts` module docs) | **"All topics in the global top quartile
  of emergence"** (`top25pct_frontier == True` — NOT a subset of the top-N mode;
  a topic can be small-volume and still top-quartile emergence, or vice versa),
  default = the volume mode. Below it, `charts.fig_frontier`: a scatter of the
  filtered topic set, **x = Expansion, y = Acceleration**, with the two quadrant
  lines at the origin on both axes (verified against `topics_dim.quadrant`,
  which flips sign exactly there).
- **Encoding.** Bubble area = the topic's mass on the current basis (`sqrt` scale
  between a floor and a ceiling in px, so a big topic cannot swallow the panel);
  colour = domain; **a top-quartile frontier topic carries an `INK` outline**
  a shape signal on top of the family colour, never a fifth hue (in the
  top-quartile MODE every plotted point therefore carries the outline; in the
  volume mode it marks the subset that also clears the quartile bar).
- **Interaction.** The segmented control swaps which frame `fig_frontier`
  receives; hover names the topic and gives expansion, acceleration and mass in
  either mode. No zoom, no animation (house rule: no motion).
- **Empty state.** Topics with no frontier score are DROPPED from the scatter and
  **counted in the caption**, together with the excluded ones, in WHICHEVER mode
  is active — the caption states the count shown and the count excluded/unscored
  for that mode specifically, never a number left over from the other one. A
  seed with no scored topic renders the reason, not an empty axis, in either mode.
- **Export.** CSV of every topic with its expansion, acceleration, quadrant,
  top-quartile flag, `rank_volume` and mass — scored and unscored alike, ALL
  topics regardless of which mode is on screen, so the export is never a
  function of the toggle.
- **Copy (binding, from DESIGN §4).** The panel says that this measures
  **attention dynamics, not novelty or quality**, and that **low can mean
  foundational**. The sentence is not optional decoration: without it a
  bottom-left quadrant reads as a verdict.

> **Rejected alternative:** a 2×2 quadrant grid of topic COUNTS (a heatmap of
> four cells) instead of the scatter. It is far more compact and needs no
> caveating about position — and it was rejected because it throws away the two
> continuous measures that make the panel worth showing, turning a position into
> a bucket, and because the quadrant boundaries sit at zero on both axes, so a
> topic just either side of a line would be assigned to opposite cells with no
> visible indication of how marginal that assignment is.
> **Rejected alternative (for this toggle specifically):** a single combined
> mode showing the UNION of top-200-by-volume and top-quartile-emergence.
> Rejected because a union hides which criterion put a given topic on the
> chart — the whole point of the user's own two-mode framing was to let the
> reader ask "what does my BIGGEST work look like on this axis" and "what does
> my MOST EMERGENT work look like" as two separate questions, and a union
> answers neither cleanly.

### 2.19 Panel — SDG profile

> **§12 addition (bar-layout contract, D28):** each row's label now carries a
> small square in the goal's own official UN colour (`fig_sdg`'s
> `label_accent=True`) — the same taxonomy-accent idiom Compare's SDG chart
> carries, so a reader sees the goal's colour on either page.

- **Form.** `st.expander(expanded=False)` → `charts.fig_sdg`, which delegates to
  `charts.fig_share_si` with ESI in the SI slot, so the reader learns ONE form
  and reuses it (`same-read-same-form`) — including the same unit grid
  (§2.15) and the harmonised solid/hollow/no-mark floor (§2.16), since `fig_sdg`
  reads whatever `si_status` the caller's frame carries with no SDG-specific code.
- **Encoding.** Sixteen bars in **fixed SDG number order** (never sorted by
  value), each in its **official UN colour**; ESI dots against the same dashed
  neutral reference, with the unit grid at every integer. **Axis labels now carry
  the goal number** ("SDG labels carry the number"):
  `sdg_label_numbered` ("SDG {n} · {short label}", number from the resource,
  never typed) when the caller's frame carries that column, falling back to the
  plain `sdg_label` otherwise (`charts._LABEL_COLS` preference order,
  `_first_col`). Every bar still carries its label on the axis, which is the
  structural relief for the UN palette's measured CVD and contrast failures
  (§1.1, family 3): identity is never colour-alone here.
- **Interaction.** Hover gives the goal, its share, its mass and its ESI. Sort is
  FIXED to goal order — the one panel in the section with no sort toggle, because
  the SDG numbers are a canonical sequence a reader navigates by position.
- **Empty state.** **SDG 17 is not covered by the classifier** and is stated as
  such from `palette.SDG_UNCOVERED`, never typed. A goal with zero tagged mass
  renders a zero-length bar in its place, never a gap.
- **Export.** CSV with `sdg_number, share, esi, mass`.
- **Copy (binding).** The caption states the **multi-label denominator**: the
  share is over SDG-TAGGED fractional mass, one work can carry several goals, and
  **these shares therefore do not sum to one**. It also carries the epistemic
  label from DESIGN §5 — this is a policy-vocabulary lens, not a field
  classification.

> **Rejected alternative:** a stacked bar of the SDG mix, one bar per
> institution, so seeds could be compared later in the Compare tab. Rejected as
> arithmetically false for THIS measure: the labelling is multi-label, so the
> segments do not partition anything and a stack would assert a whole that does
> not exist. The same reason forbids a pie.

### 2.20 Panel — ERC profile

**Bug fix ("concentration KPI wrong" led the review to
the actual finding: "ERC bug", a specialisation dot floating on a panel with NO
classified publications at all).**

- **Form.** `st.expander(expanded=False)` → `charts.fig_erc` (again
  `fig_share_si`): the ERC evaluation panels, share left, SI right, with the same
  unit grid (§2.15) and the harmonised solid/hollow floor (§2.16) — again no
  ERC-specific code, `fig_erc` reads whatever `si_status` the frame carries.
- **Encoding.** One row per panel, coloured by its **ERC DOMAIN** — three hues,
  `palette.ERC_DOMAIN_COLORS` — and grouped in the fixed PE → LS → SH order under
  `sort="taxonomy"`. No OpenAlex domain hue may appear in this chart
  (`tests/test_charts.py` asserts the two sets do not intersect): it is a
  different taxonomy of the same output, and colouring it like the OA panels
  would invite a false one-to-one reading. **A panel with ZERO classified mass
  NEVER gets an SI mark**, whatever its `si` or `si_status` value happens to
  hold — this is the exact bug the user saw (a dot at a numeric SI value on a
  panel with no publications behind it) and it is now a hard rule in
  `charts.fig_share_si` itself (the zero-volume override, §2.15), not a
  per-caller precaution, so it cannot recur in any panel this builder serves.
- **Interaction.** Sort toggle: taxonomy (ERC domain, then panel code) | volume.
- **Empty state.** A panel with zero classified mass keeps its row at zero rather
  than disappearing (its SHARE bar is a visible zero) — the ERC structure is
  fixed, and a missing panel is a fact about the institution, not about the
  taxonomy; per the fix above, that same zero-mass row draws NO SI mark.
- **Export.** CSV with `panel_code, panel_label, erc_domain, share, si, mass`.
- **Copy (binding, DESIGN §5).** The caption carries the **weak-panel caveat**
  (Biotechnology and Arts are thinly and unevenly populated, so their share and
  SI carry less weight than the others) and, when basis = full, the
  **fractional-only** disclosure.

> **Rejected alternative:** small multiples — three mini-charts, one per ERC
> domain, side by side. Rejected because the panels' shares are all on ONE
> denominator (the institution's classified mass), so three separate x-axes would
> either be three different scales (incomparable) or three copies of the same
> scale (wasteful), and the grouped single chart already carries the domain
> grouping through colour and the taxonomy sort.

### 2.21 Controls row (Benchmark section head)

- **Form.** One horizontal row directly above the lens tab strip: C1 checkbox ·
  L7 checkbox · a "Post-filters" expander (depth is fixed at 50, no control
  needed). See §1.3 for the sidebar/section split and the unchanged widget keys.
- **Encoding.** No colour, no chart. Each control carries a `help=` tooltip that
  explains what the option DOES, not what it is called — the complaint
  was that the sidebar named options without explaining them.
- **Interaction.** Every widget keeps `persist_state="session"`, so the settings
  survive a Menu ↔ Find round trip; the post-filters stay inside a collapsed
  expander so the default page shows six controls, not fifteen.
- **Empty state.** When a post-filter empties a list, the emptied lens names the
  responsible filter(s) by themselves (§1.6), and the strip above the title names
  every off-default dimension including tree and basis.
- **Export.** The active control state rides in every CSV as constant columns and
  in the filename.

> **Rejected alternative:** a single "Advanced" expander holding depth, C1, L7
> and all six post-filters together. Rejected because depth and the optional
> lenses are ORDINARY controls a reader touches on the first visit, while the
> post-filters are the advanced ones; burying all nine at the same depth would
> hide the two that feedback said should be closest to the tables.

### 2.22 Ranked tables — the changes (supersedes §2.4's column list)

- **Form.** Unchanged: the shared `lib/ranked.py` renderer, same form on every
  lens tab, `st.column_config.ProgressColumn` for the score.
- **Encoding — what changed (L21, L22).** (a) **Two size columns**, full AND
  fractional, in every table (lens, concordance, aspirational, tail search) and
  in the CSV — a single size column forced the reader to know which counting
  basis was in play. (b) **The badge column is REMOVED** from all tables; the
  seed-level badges live in the profile header (§2.10), and institution type
  stays as plain text plus the type post-filter. (c) **Country NAMES** (English)
  everywhere in the UI — tables, filter labels, the strip, the header — while the
  CSV keeps `country_code` AND adds `country`. (d) **Evidence is lens-specific**:
  the top shared cell for THAT lens (`argmax_j min(seed_j, cand_j)` over the
  lens's own substrate row pair), labelled in the lens's own namespace — field,
  subfield, topic, ERC panel or SDG label — with its contribution share of the
  score. The earlier "Top field" column only ever made sense for L1.
- **Interaction.** Unchanged (sort, tail search, CSV download; the add-to-shortlist
  button described here is retired).
- **Empty state.** Unchanged (§1.6), except that the emptied-list message now
  names countries by NAME.
- **Export.** CSV gains `country`, `total_frac_2020_2024` and the lens-specific
  `evidence`; original competition ranks are still preserved with their gaps.

> **Rejected alternative:** keep the badge column and simply narrow it to an icon.
> Rejected on the user's own ruling (#8) and on the arithmetic behind it: the
> umbrella badge fired on 158 of 7,557 institutions in calibration, so on a
> typical 30-row table the column is empty on every row and costs width on all of
> them, while the information it carries is available as a filter and on the one
> row that matters — the seed's own header.

---

## 2 ter. View specs — the Compare view (earlier spec, superseded by §11 below)

**Produced by:** the design team, in an early wave — before `pages/2_⚖️_Compare.py`
existed, against the data contract's §4 column
contracts. Same row format as §2 and
§2 bis: form / encoding / interaction / empty state / export, and one NAMED
rejected alternative each. Builders: `lib/charts_compare.py` (pure plotly, no
Streamlit, no hex literal, no digit in any string — the same three scans
`lib/charts.py` passes).

**The one rule every row below obeys.** In Compare the
INSTITUTION is the identity: the categorical axis names the field, subfield,
panel, goal, quadrant or grey state, and the COLOUR names the institution
(`palette.INSTITUTION_COLORS`, §1.1). No OA-domain, ERC, SDG or document-type
hue appears in any figure of this page. That is not a preference — the six
institution hues and the four OA hues FAIL the validator as one ten-slot set
(`palette_validation.txt` run 10), and the coexistence rule is what carries
them.

**Slot assignment is stable by `inst_key`, never by click order** (A8). Adding a
comparator does not repaint the ones already on screen unless the newcomer's key
falls between two of them, and removing one never repaints the rest. The k ≤ 5
Studio identity budget is exceeded here by design, ONCE, and this stability is
the justification (`palette.py`, FAMILY 5).

**Two things are the caller's, not the builder's, on every row below:** the
caption (which must state the denominator, the basis, the tree and the snapshot)
and the legend placement. `charts_compare.institution_legend_html` is the ONE
legend of a Compare view; every figure ships `showlegend=False`. **The legend is
mandatory, not decorative** — the palette carries a deutan ΔE 7.6 pair and two
sub-3:1 contrasts (run 9), and the legend + the axis labels + the per-mark hover
ARE the secondary encoding that makes those legal.

**Reading order note the captions must carry** (measured need, from the render
proof): in a lane-split mirror the institutions read TOP TO BOTTOM of each row in
the same order the legend reads LEFT TO RIGHT. Without that line the reader has
to infer the mapping from colour alone, which is precisely what the CVD floor
forbids relying on.

### 3.1 Institution strip (the Compare header)

- **Form.** Not a chart: a `st.columns` strip of {k} identical cards, one per
  compared institution, in SLOT order. Each card carries a colour swatch (the
  institution's own `institution_color`), the display name, the type, the
  country and the size on the current basis. Directly under it, the standard
  "Filtered by…" strip (§1.4) whenever any control is off-default.
- **Encoding.** The swatch is the ONLY place the colour↔institution binding is
  stated in full, so it is repeated in the chip legend above every figure. Size
  is a number, not a bar: {k} bars of "total output" would be a chart nobody
  asked for and would compete with the panels below (§1.6, "is it even a chart").
- **Interaction.** A remove control per card and one "add" search box; the cap
  is read from a module constant and the copy line says so from that constant,
  never from a typed numeral.
- **Empty state.** Fewer than two institutions → the panels are not drawn at
  all and the page shows the add affordance plus the Find link. One institution
  is a PROFILE, and the app already has one.
- **Export.** The strip's own fields are the first sheet of the xlsx workbook and the header block of every CSV.

> **Rejected alternative:** a single table with one row per institution instead
> of cards. Rejected because the swatch is doing identity work here, and a
> swatch inside a dataframe cell cannot be styled without the `ProgressColumn`
> hack that was already removed from the ranked tables (L22); cards also degrade
> to a stack at 390 px, where a six-column table would scroll sideways — which
> §1.8 forbids outright.

### 3.2 Fields mirror (dot rows)

- **Form.** `charts_compare.fig_mirror_dots(family="oa")` — two aligned panels of
  ONE figure sharing the y axis: one row per field, {k} coloured dots on the
  share axis left, the mass-paired specialisation dots right against the dashed
  neutral reference and the unit grid. **This is A/B #5's winner, measured**
  (§6). It replaces the grouped bars the plan first proposed, which the wind
  tunnel measured at 2.6 px per bar for 26 fields × 6 institutions (A4).
- **Encoding.** Dot = institution. `DOT_PX` diameter with the 2 px SURFACE ring
  the dataviz mark specs require of overlapping marks. Share on the current
  basis; no floor at field grain (§2.15 — the G6 floor is a subfield concept).
  When any row of the frame would put two marks closer than half a dot, EVERY
  row splits into {k} lanes, one per institution, in slot order — all-or-nothing,
  so a lane means the same thing in every row and a reader can scan one
  institution down the panel. An undodged frame is exactly as tall as the
  profile panel it mirrors. Alternate rows carry a `NEUTRAL` zebra band whenever
  lanes are on, which is what keeps {k} lanes reading as one row.
- **Volumes are in the HOVER, not in a gutter.** A/B #4's left gutter is a
  profile form and does not survive {k} institutions: one gutter column cannot
  hold six numbers per row. The hover names the institution in words, gives the
  share, the volume on the current counting basis and the SI; the xlsx and CSV
  carry the same numbers for the reader who wants a column.
- **Interaction.** Sort toggle **volume** (share summed across the compared set,
  descending) | **taxonomy** (domain → field id). Colour follows the entity, so
  the toggle never repaints anything. Tree and basis toggles are the page's, not
  the panel's.
- **Empty state.** A field an institution has no row for gets NO dot for that
  institution — never a dot at zero. A `si_status` of `none`, a NaN SI, or a
  zero volume gets no specialisation mark and `palette.NA_MARK` in the hover; a
  `thin` cell gets a HOLLOW dot (SURFACE fill, institution-coloured outline), so
  a below-the-floor cell is disclosed rather than erased. If NOTHING in the
  frame is eligible for an SI mark, the figure collapses to the share panel
  alone rather than showing an empty half.
- **Export.** CSV of the panel frame, all columns, full precision; one xlsx
  sheet per view.

> **Rejected alternative:** small multiples — one mini profile panel per
> institution, 26 field bars each. Measured and rejected in A/B #5 (§6): it is
> compact (900 px against 2,020 px) but it costs 900 px of eye travel to compare
> one field across the set where the dot row costs 74 px, it gives each
> institution a 299 px plot where the dot row gives 496 px, its wrapped category
> labels collided at the shipped pitch, and it has no room for the mass-paired
> SI panel at all — which would break outright.

### 3.3 Subfields mirror (dot rows, top-N shared)

- **Form.** `fig_mirror_dots(family="oa")` on a subfield frame. Identical
  grammar to §3.2 — same read, same form.
- **Encoding.** The N rows are the subfields with the largest share **summed
  across the compared institutions** (A3). This is a ruling, not a default: the
  INTERSECTION of the per-institution top-6 lists is one subfield at k = 6 and
  two at k = 4, measured on real sets, so an intersection rule would render a
  one-row panel and call it a comparison. The caption must state the selection
  rule, because "top subfields" reads as "each institution's top" unless it is
  told otherwise. Subfield SI carries the G6 floor, so `si_status` does real work
  here: solid ≥ 30, hollow 10–30, absent below (L34).
- **Interaction.** Same sort toggle; N is a module constant surfaced in the
  caption as a `{placeholder}`.
- **Empty state.** As §3.2. A subfield that only one institution holds still
  earns its row if its summed share ranks — the other {k}−1 marks are simply
  absent, which IS the finding.
- **Export.** As §3.2.

> **Rejected alternative:** show every subfield the set touches (252 rows).
> Rejected on the same arithmetic that killed the grouped bars: 252 rows at the
> lane-split pitch is over 15,000 px, and a panel nobody can reach the bottom of
> is not a panel. The full frame stays available through the export.

### 3.4 ERC mirror (dot rows)

- **Form.** `fig_mirror_dots(family="erc", sort="taxonomy")`.
- **Encoding.** One row per ERC evaluation panel, in the fixed PE → LS → SH
  domain order. **The ERC domain does NOT colour anything here** — that is the
  coexistence rule biting: in the profile the three ERC hues are the identity,
  in Compare the institution is, and the panel's domain lives in the row label
  and in the taxonomy sort instead. Share denominator is ERC-classified mass;
  the caption states each institution's classified share, which is the
  only honest way to read a thin institution's panel.
- **Interaction.** Sort toggle as §3.2; taxonomy is the default here because the
  PE/LS/SH grouping is the reason the panel exists.
- **Empty state.** A panel with zero mass for an institution gets no dot for it.
  The weak-panel caveat is caption text (§2.20), never a mark.
- **Export.** As §3.2.

> **Rejected alternative:** keep the ERC domain hues and encode the institution
> by marker SHAPE (circle / square / triangle …). Rejected because shape is a
> far weaker channel than hue at 12 px, because six shapes exceed what anyone
> can hold, and because it would put two identity families in one figure — the
> exact thing run 10 measured as unsafe.

### 3.5 SDG mirror (dot rows, numbered labels)

- **Form.** `fig_mirror_dots(family="sdg", sort="taxonomy")`.
- **Encoding.** One row per goal in fixed goal order, labelled with
  `sdg_label_numbered` (L36) so the goal NUMBER is on the axis — which matters
  more here than anywhere: the UN palette contains two near-identical ambers
  (run 7) and the app's rule is that no chart may rely on telling SDG colours
  apart. In Compare that rule is free, because the SDG hues are not on screen at
  all; the numbered label is doing the work it was already doing. ESI sits in the
  specialisation slot with its own axis title. Shares do NOT sum to one
  (multi-label) and the caption says so; goal 17 is absent from the classifier
  and the caption states that from `palette.SDG_UNCOVERED`.
- **Interaction / empty state / export.** As §3.2, with `si_status` from SDG
  mass.

> **Rejected alternative:** order the goals by summed share instead of by goal
> number. Rejected because the SDG axis is a *known list* the reader navigates
> by number — re-ordering it makes goal 7 appear in a different place in every
> comparison, and the volume sort is already available on the toggle for the
> reader who wants it.

### 3.6 Frontier — quadrant mix and the topic plane

- **Form (mix).** `fig_quadrant_mix` — **five** dot rows, not four: the four
  quadrants plus "not frontier-scored". A2 measured that the four quadrant
  shares sum to a median of 0.967 and a minimum of 0.128, and that quadrants +
  excluded + unscored = 1 for all 7,557 institutions; a four-part figure would
  silently drop 3 % to 87 % of an institution's mass. The fifth row is computed
  as the residual to one, so it cannot disagree with the four.
- **Form (plane).** `fig_frontier_small_multiples` — one Expansion × Acceleration
  panel per institution, all panels on the SAME axes and the SAME bubble scale.
  **A/B #6's winner, measured** (§6). `fig_frontier_overlay` (all institutions in
  one plane) is kept as an explicitly secondary mode behind the same control that
  swaps the top-200-by-volume and top-quartile point sets, with its
  occlusion figure in its caption.
- **Encoding.** Mix: dot = institution, row = quadrant, share of the
  institution's own mass. Plane: bubble = topic, area = mass on the current
  basis on a scale shared by every panel (so a small institution's panel is not
  silently magnified), colour = institution, quadrant lines at the origin on both
  axes, a top-quartile topic outlined in `INK` — a SHAPE flag, never a new hue.
- **Interaction.** A segmented control for the point set (top by volume /
  top-quartile) and one for the form (panels / one plane). Hover names the
  institution, the topic, both scores and the mass.
- **Empty state.** A quadrant an institution does not ship is drawn at zero with
  `palette.NA_MARK` in its hover — one real institution ships three quadrants,
  and an absent row would read as "not measured" rather than "none". Unscored
  topics are dropped from the plane and COUNTED in the caption.
- **Export.** The mix frame and the plotted topic rows, both as CSV, plus their
  own xlsx sheets.

> **Rejected alternative (mix):** one stacked 100 % bar per institution, the four
> quadrants plus not-scored as segments. It is the more obvious picture and it is
> refused for one reason: the segments would need a second identity family
> (quadrant hues) inside a Compare chart, and makes the institution the only
> identity. An earlier coverage-strip chart was the one exemption on the same
> reasoning (grey STATES rather than identities), but that chart is retired.

> **Rejected alternative (plane):** the overlay as the default. Measured in
> A/B #6: 90.7 % of marks have their centre covered by a mark of a DIFFERENT
> institution at k = 6, 78.0 % at k = 3, 62.6 % at k = 2, and 85.7 % even in the
> sparser top-quartile mode — against 0.0 % faceted. A figure that carries
> identity by colour cannot bury nine marks in ten behind another colour.

### 3.7 Impact — index level and per subfield

- **Form (index).** `fig_impact_intervals` — one dot-interval row per
  institution: the PP(top10%) point estimate with its rendered bootstrap
  interval.
- **Form (subfields).** `fig_impact_subfields` — dot-interval rows over the
  UNION of the subfields any compared institution clears, one lane per
  institution, unconditionally.
- **Encoding.** The interval is the panel's point, not decoration: a PP gap
  smaller than the overlap of two intervals is not a finding, and dots alone
  would invite exactly that read. Per-subfield lanes are always on because an
  interval occupies a stretch of axis rather than a point — a collision test on
  the point estimates alone would not see two intervals lying on top of each
  other.
- **Interaction.** Sort **volume** (estimate descending) | **taxonomy** (stable
  slot order / subfield id). A floor toggle for the per-subfield panel: floor 30
  (fewer cells, tighter intervals) ↔ floor 10 ("more cells, wider intervals"),
  both shipped in `impact_cells` (A1). The bonus year is excluded and the
  caption says so.
- **Empty state.** A missing cell is the NORMAL case, not an error: only 3,342
  of 7,557 institutions have any floor-30 cell, the median is 2, and 40 of 40
  random four-tuples intersect to zero (A1). It is drawn as NO MARK — never a
  dot at zero, which would read as "no top-decile output" when the truth is "too
  few publications to estimate". The caption states how many of the {k}
  institutions each row actually carries.
- **Export.** The union frame with its `in_all_ids` flag, `n/a` where a cell is
  missing (never 0), plus the denominator columns L11 requires beside every rate.

> **Rejected alternative:** render only the subfields ALL compared institutions
> clear, as the plan first said. Refuted on data, not on taste: for IFPEN
> plus three L1 peers that intersection is empty, and so is every one of 40
> random four-tuples. A panel that is blank on the gate case is not a panel.

### 3.8 Trends — subfield × year small multiples

- **Form.** `fig_trends_small_multiples` — a grid of small panels, one per
  subfield, one line per institution inside each. Small multiples is right here
  and a dot row is not: the question is "who is growing in this subfield", a
  change-over-time read, and change over time is a line.
- **Encoding.** The N panels are the top-N subfields by share summed across the
  compared set (A3 again, same reason as §3.3). **Every panel shares one y
  scale** — `shared_yaxes` alone links a row of panels, not the grid, so the
  builder matches every axis explicitly; a grid whose second row has its own
  scale is the exact lie small multiples exist to avoid. Because of that shared
  scale the caller passes an institution-NORMALISED measure whenever the compared
  sizes differ by an order of magnitude (a raw count would pin the small
  institutions to the floor), and the caption names which measure it passed.
- **The partial final year is drawn, not hidden.** Its segment is DOTTED and its
  point HOLLOW, so it is visibly not the same kind of observation; the year
  itself is a caller-supplied string, since this module never names a year.
- **Interaction.** Basis toggle (the page's); hover names the institution, the
  panel, the year and the value.
- **Empty state.** An institution with no mass in a panel's subfield has no line
  in that panel — never a line at zero.
- **Export.** The long frame (institution × year × subfield), one xlsx sheet.

> **Rejected alternative:** one panel per INSTITUTION with a line per subfield.
> Rejected because it answers a different question (the institution's internal
> mix over time, which the profile already answers) and because it puts {N}
> subfield lines in one panel with no identity family free to colour them
> institution is taken.


### 3.11 Gaps tables (A → B and B → A)

- **Form.** Two tables, directional and side by side at wide widths, stacked
  below the small breakpoint.
- **Encoding.** A's gaps = the topics B holds inside A's own top-10 subfields
  that A does not hold, with B's share and the frontier flag; B's gaps
  symmetric. The direction is stated in the table's own title, not left to the
  column order — a directional table read the wrong way round is a wrong answer,
  not a confusing one.
- **Interaction.** Sort by B's share (default) or by subfield; the frontier
  filter is the same taxonomy that fed the retired shared-topics header.
- **Empty state.** No gap rows → a stated sentence naming the pair and the
  subfield scope; the honest reading is "nothing B does inside A's strengths
  that A does not already do", which is a finding.
- **Export.** Both directions, one sheet each.

> **Rejected alternative:** one merged table with a direction column. Rejected
> because the two tables answer two different questions and a merged one invites
> a total that means nothing; user testing also showed this content is read
> as a partnering shortlist, and a shortlist is read one direction at a time.

### 3.12 Breadth-overlap diagnostic

- **Form.** A single labelled number with its two counts beside it — a stat
  tile, not a chart (§1.6 / the dataviz form heuristic: one value is never a
  one-bar bar chart).
- **Encoding.** The unweighted Jaccard over topics with nonzero share, shown with
  the intersection and union counts that produced it, and a one-line statement
  that it answers a DIFFERENT question from the shared-topics table: breadth
  overlap, not weight agreement. Two institutions can score high here and share
  almost no mass.
- **Interaction.** None. It is a number.
- **Empty state.** Undefined only if both topic sets are empty, which the corpus
  filters make impossible; the tile still renders `palette.NA_MARK` rather than
  zero if it ever happens.
- **Export.** In the Methods sheet of the pair's workbook, with its counts.

> **Rejected alternative:** a share-weighted overlap coefficient instead of the
> unweighted Jaccard. Rejected because the weighted version is what the
> shared-topics Σ min already is — shipping both as one number would give the
> reader two names for one quantity and no diagnostic at all.

### 3.13 Link-outs

- **Form.** A row of external links under the pair's shared-topics tables.
- **Encoding.** The co-publication query on OpenAlex for the pair, built with the
  comma-joined repeated filter `authorships.institutions.id:A,authorships.institutions.id:B`
  plus the corpus filters. The `+` form is FORBIDDEN: it silently returns A's own
  count with HTTP 200 (A7, verified on a real pair), and a test asserts the comma
  form. Each institution's own OpenAlex page is linked from its header card.
- **Interaction.** Links open in a new tab; the co-publication count is NOT shown
  — no co-publication data exists in the artefacts, and a number the app cannot
  reproduce offline does not belong on the page.
- **Empty state.** Nothing to guard: a query with no results is a legitimate
  answer on OpenAlex's own page.
- **Export.** The URLs are written into the Methods sheet so a workbook stays
  self-describing.

> **Rejected alternative:** fetch the co-publication count live and print it in
> the page. Rejected on the standalone principle (`CLAUDE.md`): the app must
> re-run from its own artefacts, and a live figure would be a number in the
> deliverable that no snapshot can reproduce.

---

## 2 quater. View specs — the redesigned views

**Produced by:** the design team, before `lib/views_compare.py`
and `lib/views_collab.py` are rewritten, against the data contract's §4
interface contracts. Same row format as §2, §2 bis and §2 ter: form / encoding /
interaction / empty state / export, and one NAMED rejected alternative each.
Builders: `lib/charts_compare.py` (pure plotly, no Streamlit, no hex literal, no
digit in any string).

**What changed, and why it is not a change of taste.** caps Compare at
**three** institutions. An earlier round refused grouped bars on an arithmetic
that was true at six — 26 fields × 6 institutions is 2.6 px per bar — and that
arithmetic does not survive the new cap. A/B #7 (§7) re-ran the contest on the
real trio and the grouped bar won, on the one criterion the dot row can never
meet: **the number sits on the mark**. Every §2 quater row below therefore takes
`fig_metric_bars` where its §2 ter ancestor took `fig_mirror_dots`.

**The one rule survives, narrowed once.** Colour on a MARK is the
institution and nothing else. lets a taxonomy's OFFICIAL colour — the
three ERC domain hues, the sixteen UN goal hues — appear as a glyph in the ROW
LABEL of the ERC and SDG views. The direction is one-way and routed through
`palette.label_accent_color`: **taxonomy colour on labels, institution colour on
marks, never the reverse**. Validator run 17 records the co-occurrence honestly
(ERC PE `#1F4E9C` vs institution slot 3 `#6A3D9A`, protan ΔE 1.7) and it is
DISPOSED of, not suppressed: the two are never two marks a reader must tell
apart.

**One new hue.** `palette.SHARED_FRONTIER` (`#C2185B`, validator runs 14–16) is
not a fourth institution — it is the intersection. It paints the pooled frontier
map's shared bubbles and the pair's joint-corpus pulse chart, whose subject is
likewise the pair's JOINT corpus rather than either side.

**Legend above EVERY chart**. `charts_compare.legend_strip(ids, …)` is
the one export a view calls; `shared=True` adds the shared chip. It is not
decoration: the palette carries a deutan ΔE 7.6 pair and two sub-3:1 contrasts
(run 9) plus two sequential-memory FAILs on the new hue (run 16), and the strip
plus the axis labels plus the per-mark hover ARE the secondary encoding that
makes those legal.

**Two things stay the caller's on every row below:** the caption and the legend placement.

### 4.1 Compare overview — the KPI strip

- **Form.** Not a chart. One `st.columns` card per compared institution, in SLOT
  order, each carrying the swatch, the name, and the seven overview values of
  `compare_data.overview` — publications (full and fractional), % SDG-tagged,
  frontier top-quartile share, PP(top10%) with its interval, % international
  co-publications and % with a company partner.
- **Encoding.** Numbers, not bars. Three institutions × seven measures is a
  table's job; drawing it would produce seven mini-charts that compete with the
  metric selector immediately below and answer nothing it does not. The swatch
  is the only colour on the strip and it is the same `institution_color` the
  charts use, which is what binds the strip to everything under it.
- **Interaction.** A remove control per card and one add box; the cap line
  reads from `COMPARE_CAP`, never from a typed numeral. The
  interval's exact coverage is stated beside it, from `METHODS_FAISCEAU.md`, pinned by a test.
- **Empty state.** Fewer than two institutions → no panels at all, the add
  affordance and the Find link instead: one institution is a PROFILE and the app
  has one. An institution whose intl/company share is not yet in the artefacts
  shows `palette.NA_MARK`, never zero.
- **Export.** First sheet of the xlsx workbook and the header block of every CSV.

> **Rejected alternative:** a seven-row dot-plot strip, one row per measure, all
> three institutions on each. Rejected because the seven measures share no unit
> or range — a share, a count, a percentage-point estimate and two coverage
> percentages on one axis is the dual-axis mistake with five axes instead of two
> — and because an earlier render already showed that a "size" bar beside identity
> cards competes with the panels below (§3.1).

### 4.2 Metric-selector grouped bars — fields

- **Form.** `charts_compare.fig_metric_bars(frame, metric, ids, level="field")`.
  Horizontal grouped bars, one row per field, ≤ 3 bars per row, the value written
  at each bar's outer end. **A/B #7's measured winner** (§7); **A/B #9** fixes the
  label position (§7).
- **Encoding.** Bar = institution, colour = `institution_color` by ascending
  `inst_key`. Bar thickness is `BAR_PX`, and that is arithmetic, not luck:
  `metric_row_height` sizes the row band from the bar stack, so no row count can
  make a bar thinner (measured 12.8 px at 26 fields × 3 at 1280 px). A 2 px
  SURFACE gap separates adjacent bars; a hairline `BORDER` rule separates rows
  a filled zebra band would fight three touching bars for the same ink.
- **Metrics.** Share · Volume of top-decile works · PP(top10%) · % SDG-tagged ·
  Dynamics Δ · SI. A metric×level pair the data cannot serve returns a
  typed empty and the option is HIDDEN, never shown returning zero.
- **Reference.** `si` defaults to the neutral value, drawn as one dashed rule.
  Every other reference is DATA (`ref_value`): constant across rows → one rule;
  varying by row → a short dash inside each row band, because an index PP is a
  different number in every field and one line would assert a benchmark that does
  not exist. `dynamics` is signed and gets the BOLD BLACK zero.
- **Interaction.** One "Compare by" selector. No sort toggles: the frame
  arrives ranked and the builder never re-sorts, so colour cannot move with a
  control. Hover names the institution, the taxon, the value, the reference and
  the denominator.
- **Empty state.** A missing cell gets NO bar and NO label; a GENUINE zero gets
  no visible bar but keeps its value label at the origin, so "measured, and it is
  zero" and "not measured" look different. Measured on the real trio: Veterinary
  renders two `0.0 %` labels and one absence.
- **Export.** CSV of the frame at full precision; one xlsx sheet per metric×level.

> **Rejected alternative:** keep the §3.2 dot mirror and put the values in the
> hover. Measured in A/B #7 and rejected: at k = 3 the bar is 12.8 px against the
> dot's 12.0 px and the eye travel is 43 px against 39 px — i.e. the dot row buys
> nothing back — while the bar carries 77 value labels against the dot row's
> zero. A comparison the reader must hover to read is a different chart.

### 4.3 Metric-selector grouped bars — subfield drill

- **Form.** `fig_metric_bars(level="subfield")` on the subfields of ONE chosen
  field. Identical grammar to §4.2 — same read, same form, same builder.
- **Encoding.** As §4.2. The rows are the subfields of the selected field ranked
  by the value SUMMED across the compared set (the A3 ruling, which the earlier
  measurement stands behind: the INTERSECTION of per-institution top lists is one
  subfield at k = 6 and is not a comparison). The caption states the selection
  rule, because "top subfields" reads as "each institution's top" otherwise.
  Subfield SI carries the G6 floor, so a below-floor cell is disclosed in the
  hover rather than drawn.
- **Interaction.** A field picker above the chart; the metric selector is the
  page's and does not reset when the field changes.
- **Empty state.** As §4.2. A subfield only one institution holds keeps its row
  if its summed value ranks — the other bars are simply absent, which IS the
  finding.
- **Export.** As §4.2, with the chosen field named in the sheet.

> **Rejected alternative:** drill by expanding a field row in place (an
> accordion inside the chart). Rejected because a plotly categorical axis cannot
> grow a row without re-laying every other row, so the panel would jump under
> the reader's cursor, and because the drilled panel needs its own caption
> (different denominator, different floor) which an in-place row has nowhere to
> put.

### 4.4 Metric-selector grouped bars — ERC panels

- **Form.** `fig_metric_bars(level="erc")`, rows in the fixed PE → LS → SH order.
- **Encoding.** As §4.2, plus the accent: each row label carries
  `ACCENT_GLYPH` in its ERC domain's official hue, so the PE/LS/SH grouping is
  visible without a second axis and without any mark changing colour. Metrics
  Volume / Share / SI. Share denominator is ERC-classified mass and the caption
  states each institution's classified share — the only honest way to read a thin
  institution's panel.
- **Interaction.** As §4.2. The domain grouping is the row ORDER, not a control.
- **Empty state.** A panel with zero mass for an institution gets no bar for it;
  the weak-panel caveat is caption text, never a mark.
- **Export.** As §4.2, with `erc_domain` as a column.

> **Rejected alternative:** paint the BARS in the ERC domain hues and encode the
> institution by hatch or marker shape. Rejected on measurement, not taste:
> validator run 17 puts ERC PE `#1F4E9C` at protan ΔE 1.7 from institution slot 3
> `#6A3D9A`, so the two families cannot both be marks in one figure; and texture
> at 13 px of bar thickness is not a channel that survives a screenshot.

### 4.5 Metric-selector grouped bars — SDG goals

- **Form.** `fig_metric_bars(level="sdg")`, rows in fixed goal order.
- **Encoding.** As §4.4 with the UN goal colours as the label accent. The label
  itself is the NUMBERED goal (`sdg_label_numbered`), which matters more here
  than anywhere: the UN palette contains two near-identical ambers (run 7), so
  the number, not the colour, is the encoding — the accent is brand recognition
  on top of it. Metrics Volume tagged / % tagged / Dynamics. Shares do NOT sum to
  one (multi-label) and the caption says so; goal 17 is absent from the classifier
  and the caption states that from `palette.SDG_UNCOVERED`.
- **Interaction / empty state / export.** As §4.4.

> **Rejected alternative:** order the goals by summed value instead of by goal
> number. Rejected because the SDG axis is a *known list* the reader navigates by
> number — re-ordering puts goal 7 in a different place in every comparison — and
> because the accent would then be the only thing locating a goal, which is
> exactly the colour-alone read the amber pair forbids.

### 4.6 Frontier map (pooled)

- **Form.** `charts_compare.fig_frontier_map(points, top_n)` — ONE
  Expansion × Acceleration plane, one bubble per TOPIC, over the compared
  institutions' top-quartile frontier topics.
- **Encoding.** Area = combined volume across the compared set, one scale for the
  plane. Colour = the institution that EXCLUSIVELY holds the topic, or
  `palette.SHARED_FRONTIER` when more than one does. **Bold black rules at the
  origin on both axes**: the quadrant split is the figure's frame of
  reference, so it is the one line allowed to out-weigh the grid. A top-quartile
  topic takes an INK outline — a shape flag, never a new hue. Autoscaled, with the
  origin forced inside the range (a pooled top-N set can sit entirely in one
  quadrant, and a quadrant plot whose lines are off-screen is not one).
- **Why pooled beats the earlier overlay.** The overlay drew each institution's own
  cloud, so the same topic appeared k times and 90.7 % of marks were occluded by
  a DIFFERENT institution's (A/B #6). Pooling happens in the data, so
  cross-institution occlusion is not reduced — it is impossible.
- **Interaction.** A top-N slider, and it does real work: measured
  bubble occlusion on the real trio is 0.450 at N = 40 and N = 60, 0.588 at
  N = 80, 0.708 at N = 120. **Default N = 60.** Hover names the topic, the owner
  in words, both scores and the combined volume.
- **Empty state.** Unscored topics are DROPPED and counted in the caption. The
  caption must ALSO state how many plotted topics are shared, because the answer
  is extreme and the picture does not say it: on the real trio **114 of the top
  120 pooled topics are held by all three and only 1 by a single institution**
  (118 of 120 shared for the Sorbonne–Strasbourg pair). At the head of the volume
  ranking the colour split is therefore near-degenerate, and the map's work is
  POSITION and SIZE; exclusivity is a tail phenomenon and the caption says so
  from data, never from prose.
- **Export.** The plotted topic rows with `owner` as TEXT — which is also what
  keeps "shared" from being colour-alone.

> **Rejected alternative:** one bubble per (institution, topic) with the shared
> topics drawn k times, i.e. the §3.6 overlay retargeted. Rejected on A/B #6's
> own numbers (0.907 cross-occlusion at k = 6, 0.780 at k = 3) and on a second
> ground the pooling makes obvious: with 95 % of the head shared, an overlay
> would draw the same topic three times in three colours and let the last one
> drawn win — a picture whose colour is decided by trace order.

### 4.7 Who holds the shared frontier — diverging bars

- **Form.** `charts_compare.fig_diverging_shared(rows)`. Two institutions → a
  DIVERGING pair, one bar left of a bold zero and one right. Three → grouped rows
  on one side (a diverging bar has no second direction for a third series, and
  stacking would turn three volumes into a total nobody asked for).
- **Encoding.** Row = shared topic, ranked by combined volume. Bar length = that
  institution's own joint volume, value written at the outer end. **The x ticks
  carry ABSOLUTE values**: the sign is a direction, not a magnitude, and a
  negative publication count would be a lie about the data.
- **Why it is the second chart and not a colour on the first.** A/B #8: the real
  Sorbonne–Strasbourg pair's most lopsided shared topic is *Cosmology and
  Gravitation Theories*, 373 against 18 (20.7:1). The paired bars put that
  imbalance on screen as 305 px of length difference (71 px minimum, 188 px
  median across the 14 plotted rows); a colour gradient puts it at ΔE 14.9 from
  the most balanced plotted topic — **below the validator's own 15 normal-vision
  floor** — and at ΔE 2.3 from a 10:1 topic.
- **Interaction.** Top-N on the same slider as §4.6. Hover names both sides'
  volumes and the combined total.
- **Empty state.** A topic one side does not hold is not a shared topic and is
  not in the frame; a hole inside a plotted row (three-way case) is an absent bar,
  never a zero-length one.
- **Export.** One row per (topic, institution) with both volumes and the combined.

> **Rejected alternative:** a single stacked 100 % bar per topic, the two sides
> as segments. Rejected because it encodes the RATIO and discards the size — the
> 373/18 row and a 20/1 row would be the same picture — and because the reader's
> question here is "how much does each side actually put in", which is a length
> from a common baseline, not a share of a bar.

### 4.10 Untapped potential — table

- **Form.** A table, not a chart (§1.6, "is it even a chart"): one row per topic
  both institutions hold with joint output at or below the expected level, with
  each side's own volume, the joint volume, the expected joint volume and the
  sibling topics (same subfield via `topics_dim`).
- **Encoding.** Numbers in columns. The row's *claim* is an arithmetic comparison
  the reader has to be able to audit, and a bar that says "less than expected"
  hides the two numbers that make the claim. Institution NAME is the clickable
  OpenAlex link; no colour is used
  at all, so no identity family is implicated.
- **Interaction.** Sort by any column; the expectation formula is stated in
  Methods and linked from the caption. Row count capped, with the cap in the
  caption from the constant.
- **Empty state.** No qualifying topic → an explicit "nothing below expectation"
  line, never an empty table. Missing expectation → `palette.NA_MARK`.
- **Export.** CSV and one xlsx sheet, full precision, including the topics the
  cap dropped.

> **Rejected alternative:** a scatter of joint volume against expected joint
> volume with a y = x line, the gap read as vertical distance. Rejected because
> the interesting rows all sit near the origin where the bubbles collide (the
> same crowding §4.6 measures at 0.708), and because the reader's next action is
> to read topic NAMES and follow a link — which a scatter can only give through
> a hover, one at a time.

## 2 quinquies. View specs — the colour rework and chart mechanics

**Produced by:** in an earlier wave, before `lib/compare_data.py`
lands the unified frame contract and before the pages are rewritten. Same row
format as every section above — form / encoding / interaction / empty state /
export, one NAMED rejected alternative each. Builders: `lib/charts_compare.py`,
colours: `lib/palette.py`, evidence: `design-system/palette_validation.txt`
runs 18–25.

**The A5 amendment governs this section.** An earlier round refused the plan's
four independent acceptances (taxonomy order, volume gutter, low-volume marker,
reference lines) and made them ONE contract change: `metric_frame` grows
`domain_id, domain_order, vol_display, vol_full_annual_mean, ref_value`. CD3
produces it, `fig_metric_bars` consumes it, and every row below cites it. The
contract is ADDITIVE — a frame without the new columns still renders, with no
gutter and no separators — which is what keeps CD3's landing from being a flag
day.

### 5.1 The colour system — three light institution fills and their dark twins

- **Form.** Not a view: the parameter every view below reads.
  `palette.INSTITUTION_COLORS` (3 fills at OKLCH L = 0.77),
  `palette.INSTITUTION_COLORS_DARK` (one darker same-hue TEXT twin each),
  `palette.ERC_DOMAIN_COLORS` reassigned to the trio the institutions vacate.
- **Encoding.** Fill = the institution, on a MARK only. Twin = the same
  institution, on TEXT only — the value label, the gutter number, the legend
  name, the KPI dot's caption. The direction is one-way and has one resolver
  each (`institution_color` / `institution_ink`), so "colour on a mark" and
  "colour on text" can never drift into two different meanings.
- **Why light at all.** The user ruled "much lighter fills so the value labels
  can be read". Literally that is unbuildable: the validator's lightness gate is
  L ∈ [0.43, 0.77] at every hue and an exhaustive search returned
  ZERO passing triples at L ≥ 0.78. L = 0.77 is the lightest legal rung and it is
  what ships (run 18).
- **Why these three hues.** Searched, not inherited: every 6° hue triple at
  L 0.74–0.77 that passes the validator, clears the dataviz CVD **target** of 8
  inside the trio, and stays ≥ 15 from the chrome that shares the Compare screen
  — 11,379 survivors, ranked by distance to OA + SDG (run 18b). Winner
  `#FF8BA6 / #B4BF07 / #8EB3FF`: in-trio CVD 12.6, normal-vision 20.2.
- **The coexistence exception, with its numbers.** No triple at any lightness
  reaches ΔE 15 against the OA domain hues AND the sixteen drawn SDG hues — a
  measured impossibility, not a shortfall. Shipped distances: OA 9.4, SDG 9.6,
  doctype 14.4, ERC 18.7, FOCAL 24.2, SHARED_FRONTIER 24.6. Legal for exactly
  the reason runs 6b and 10 already are: an institution fill never shares a
  figure with an OA / SDG / doctype fill, and the taxonomy colours reach a
  Compare figure only as row-label glyphs.
- **What the rework FIXED.** Run 17 recorded the app's worst same-screen
  collision (ERC PE `#1F4E9C` vs institution slot 3 `#6A3D9A`, protan ΔE 1.7,
  normal 10.8) as "descriptive". Moving both families at once turns that exact
  co-occurrence into ALL CHECKS PASS at normal-vision 18.7 (run 25).
- **Empty state.** A fourth institution is refused by the builder and greyed by
  the resolver — never a generated hue, never a cycle.
- **Export.** Every panel still exports its numbers, which is half the relief the
  fills' contrast WARN obliges; the twins are the other half.

> **Rejected alternative:** an earlier candidate trio `#FC9095 / #28CFB7 /
> #90B3FC`. It PASSES and it is prettier — but its worst in-trio CVD is 6.1
> (deutan), inside the band the dataviz non-negotiables call "legal ONLY with
> secondary encoding", against 12.6 for the shipped trio at the SAME distance to
> OA and SDG (9.3 vs 9.4). Run 18c, and A/B #10 renders both at the real bar
> pitch. Every survivor at CVD ≥ 8 contains a yellow-green slot: at L 0.77 the
> red/green confusion lines collapse and yellow-green is the only region that
> stays separable, which is why slot 2 is an acid olive rather than a mint.

### 5.2 Metric-selector grouped bars — taxonomy grouping and the sort toggle

- **Form.** `fig_metric_bars(., sort="taxonomy"|"value")`, superseding §4.2's
  "the frame arrives ranked and the builder never re-sorts".
- **Encoding.** `sort="taxonomy"` (the default) groups the rows under their
  domains in the taxonomy's own order (`domain_order`), and marks each domain
  boundary with the row rule one step heavier and one step darker — `GRID` at
  `DOMAIN_RULE_PX` against `BORDER` at `ROW_RULE_PX`. Subtle on purpose: the
  grouping is already carried by the ORDER, so the rule only confirms it.
- **Interaction.** A per-section "sort by value" toggle ranks by the value summed
  across the compared institutions and DROPS the separators — a domain separator
  under a value ranking would draw a grouping the rows no longer have. Colour
  follows the entity in both, so nothing repaints when the toggle flips.
- **Why taxonomy is the default.** Order stability across metric tabs: a row that
  stays put between Share and Dynamics can be compared across the two. Pinned by
  `test_the_order_is_stable_across_every_metric_tab`.
- **Empty state.** A frame with no `domain_order` keeps the caller's arrival
  order and draws no separator.
- **Export.** The CSV carries `domain_id` so the grouping survives the download.

> **Rejected alternative:** a coloured domain BAND behind each group, or a domain
> name in the axis. Both put a second identity family (the OA domain hues) into a
> figure whose only identity is the institution — the coexistence rule forbids it
> outright, and validator run 20 measures what it would cost (institution
> `#8EB3FF` vs OA Physical `#8190FF`, normal-vision ΔE 9.4, in one figure).

### 5.3 The raw-volume gutter, on every metric

> **SUPERSEDED by §10.1.** The
> mechanism below predates the rework described there, which moves the gutter into a dedicated LEFT
> COLUMN — a phantom `go.Bar` trace per institution — with a small header
> naming the basis, kept here as the historical record of this section's own
> A/B history, not as the current behaviour.

- **Form.** The row label's right edge carries one number per drawn institution,
  in slot order, right-anchored — `charts._tick_display`'s idiom, extended to
  three cells (`vol_display`, current basis).
- **Encoding.** Each number wears its own institution's DARK TWIN. That is the
  one place in the module where text carries identity, and it is deliberate: the
  fills sit at 2:1, so three grey numbers in a row would be unreadable as
  "whose", while three twins are instant.
- **Why on every metric.** -3: a share chart provokes the question "forty
  per cent of how many?" and answers it nowhere. The gutter answers it without
  spending a tab, which is what let `vol_top10` be retired as a tab at all.
- **Empty state.** An institution with no cell contributes no number (never a
  zero); a non-numeric `vol_display` is printed verbatim, which is how -4's
  raw-Δ gutter reaches the axis without this module composing a sentence it does
  not own. `gutter=False` turns the whole thing off.
- **Export.** The volumes are frame columns, so every CSV already has them.

> **Rejected alternative:** ONE number per row (the compared set's total), the
> form A/B #9 assumed when it wrote "three per row is not a gutter, it is a
> collision". That verdict was about three METRIC VALUES competing with the bars
> for the same horizontal space; these are short right-anchored integers in three
> distinct inks, and A/B #10's render at 26 fields × 3 shows them separating
> cleanly. The row total was rejected because it answers a question nobody asks:
> the reader wants to know whether THIS institution's share rests on 12 papers or
> 12,000, and a pooled total hides exactly that.

### 5.4 The low-volume marker

> **SUPERSEDED by §10.2.** The hatch/hollow BAR rendering below is DELETED — every bar
> is now solid, and the disclosure moves to the value/gutter TEXT COLOUR
> alone. The FLOOR itself (`LOW_VOLUME_FLOOR`, `RATIO_HATCH_METRICS`) is
> unchanged; only how a flagged row is drawn changed. `fig_mirror_dots`'s
> hollow-dot floor, mentioned below, is UNCHANGED and reconfirmed by that same rework (see
> §10.3) — it was never the same mechanism as the bar hatch this note
> retires.

- **Form.** A cell whose `vol_full_annual_mean` is below `LOW_VOLUME_FLOOR` (10)
  is drawn HOLLOW — SURFACE fill, institution outline at `OUTLINE_WIDTH` — and
  its value label carries `LOW_VOLUME_GLYPH`.
- **Encoding.** Shape and glyph, never a hue: a second colour would be a second
  identity family. The outline stays the institution's, so a hollow bar is still
  an identity rather than a hole — the same hollow-means-thin idiom
  `fig_mirror_dots` uses for a below-floor SI cell.
- **Interaction.** The hover carries the reason in plain words.
- **Empty state.** No marker column, or no value in it → NOT flagged. An
  unmeasured thing is never marked, the same direction as "n/a never zero".
- **Export.** The mean annual volume is a frame column.

> **Rejected alternative:** drop the row below the floor, the way the impact
> panels drop a below-floor cell. Rejected because a share IS defined at low
> volume — it is just unstable — so deleting it would answer "how does this
> institution compare here?" with silence when the honest answer is "it looks
> strong, on very little". Disclosure beats suppression; the dagger is the
> disclosure.

### 5.5 Reference lines — three metrics, and why not share

> **SUPERSEDED (partially) by §10.4.** The "why not share" arithmetic below (a mean share is 1/n-taxa, not a
> benchmark) is UNCHANGED and still the reason Share/Volume draw no
> reference. What changed is the ENCODING of the two cases this section
> already distinguishes: the per-row VARYING case moves from a short dash
> per row to a dark diamond MARKER per row (refC); the constant case stays a
> rule but takes a heavier, darker treatment (refB) than the one described
> below.

- **Form.** `REF_METRICS = (pp, sdg_share, dynamics)` draw the population mean
  among institutions with nonzero mass. `si` draws its own constant neutral. Share and Volume draw
  NOTHING, even when the frame carries `ref_value`.
- **Encoding.** Constant across rows → ONE dashed rule across the panel; varying
  by row → a short dash inside each row band, because a per-taxon index mean is a
  different number in every row and one line would assert a benchmark that does
  not exist.
- **Interaction.** The hover names the reference beside the value, and the
  section tooltip says what population it is a mean over.
- **Empty state.** A non-finite reference draws no dash for that row.
- **Export.** `ref_value` ships in the CSV.

> **Rejected alternative:** a reference on the Share tab too, for symmetry.
> Rejected on arithmetic: the shares of a partition sum to one, so their mean
> across institutions is 1/(number of taxa) — an artefact of how many fields the
> taxonomy has, not a benchmark anyone can be above or below in a meaningful
> sense. A line there would be read as one anyway.

### 5.6 Frontier map — two pools and the colour-by-domain toggle

- **Form.** `fig_frontier_map(., pool=, color_by=)`. One pooled
  Expansion × Acceleration plane, unchanged in geometry.
- **Encoding.** `pool="volume"` ranks the slider's cut by combined volume (where
  the mass is); `pool="frontier"` ranks it by `frontier_score_latest` (what is
  most frontier). Only the RANKING changes — bubble AREA stays combined volume in
  both, because area means one thing in this app and a pool switch must not
  silently redefine it. `color_by="domain"` REPLACES the ownership hues with the
  OpenAlex domain hues and the legend is rebuilt on the swap
  (`map_legend_strip`), so exactly one identity family is ever on screen.
- **Interaction.** Two controls, both persisted with the slider. The caption
  states the pool rule and the shared count in plain words; -10 rules the
  top-10 % cut GLOBAL, so the pool does not move when the compared set does.
- **Empty state.** Unscored topics are dropped and counted in the caption; a
  frame with no `domain_id` refuses the domain toggle loudly rather than
  colouring everything grey.
- **Export.** Owner, domain, both coordinates and the volume, per topic.

> **Rejected alternative:** colour by domain and outline by owner, so both
> readings live in one picture. Rejected: it is two identity families in one
> figure, the thing the coexistence rule exists to prevent — and the outline is
> already spent on the top-quartile flag, which would then have nowhere to go.

### 5.7 Compare overview cards — the best-value dot

- **Form.** `best_value_dot(slot, label)` — a small dot in the LEADING
  institution's fill, followed by that institution's name in its twin.
- **Encoding.** A MARK, sitting beside the value, the same object the chart below
  draws. The card's own numbers stay in ink because they belong to all three
  institutions, not to the leader.
- **Interaction.** The window and basis move into the card's `?` tooltip; the bootstrap-interval line is deleted.
- **Empty state.** An unknown slot yields COMPARISON grey and secondary ink — a
  card with no leader says so instead of picking one.
- **Export.** The strip's numbers ride in the Compare xlsx.

> **Rejected alternative:** tint the whole card in the leader's hue. Rendered in
> A/B #13 and rejected on two measurements: the card's secondary text drops to
> 1.4–1.9:1 on the L 0.77 tints (below every text floor), and the tint reads as
> "this card belongs to Lille" when the card's number is a comparison across all
> three.

### 5.8 The reading line and the ? tooltip

- **Form.** `chart_note(reading, tooltip)` — one short line under a chart, plus a
  bordered `?` carrying the methodology in `title=`.
- **Encoding.** Secondary ink, chart font size; the `?` inherits the ink and is a
  `<span>`, not an emoji, so it cannot arrive as a colour glyph no palette owns.
- **Interaction.** Hover / focus reveals the payload; it degrades to plain text
  with no script and reads out to a screen reader.
- **Empty state.** No tooltip → no `?` at all, rather than an affordance that
  reveals nothing.
- **It REFUSES a wall of prose.** A reading longer than `NOTE_MAX_CHARS` or
  containing a line break raises `ValueError`. -8 is enforced, not
  requested: a silent truncation would let the grey paragraph back in one
  release later.

> **Rejected alternative:** a Streamlit expander per chart ("Method"). Rejected
> because an expander is a heading plus a click plus a layout shift for two
> sentences, and because the page already scrolls through six panels — six
> collapsed expanders read as six unfinished sections. The `?` costs one glyph.


## 3. Cross-cutting A/Bs to run on real data

Resolved against
real engine output (`app/lib/engine`, University of Gdańsk `I40413290`, L1
top-50) with Playwright screenshots at 1280 px, appended to this file as a new
"§4 A/B verdict" section (the one exception to this file's normal single-owner
convention).

### A/B #1 — score column in every `tbl-lens-ranked` row

| Candidate | Description |
|---|---|
| A | `st.column_config.ProgressColumn` — a horizontal bar per row, confirmed present in Streamlit 1.61.1 |
| B | A Plotly ranked-dot chart, one dot per row at its score, sharing the table's row order |

**Measured criterion:** rows legible above the fold at 1280 px (how many of the
top 50 are visible without scrolling); label-truncation count (institution
names cut off); zero-baseline compliance (RULES honesty rule 1 — does the form
imply a false zero or a false ceiling); an honest read of ties (does the form
visually distinguish two rows tied at the same competition rank, or wrongly
imply one beats the other).
**Real seed to render:** University of Gdańsk (`I40413290`), L1, top-50.
**Downstream consequence already fixed regardless of winner:** the Aspirational
tab (§2.5) never uses Candidate A alone, because A cannot render a confidence
interval (see §2.5's own rejected-alternative note).

### A/B #2 — concordance overview form

| Candidate | Description |
|---|---|
| A | k-count table with hit-lens chips (this document's proposed default, §2.3) |
| B | A full rank matrix: candidates × lenses, cell = rank (or blank) |

**Measured criterion:** rows legible above the fold at 1280 px; label-truncation
count; whether the form still fits full width without the page body scrolling
horizontally (house rule) once all 8 default lens columns are present; an
honest read of ties/undefined cells (does a blank cell in the matrix read as
"not found" or ambiguously as "not computed" — RULES honesty rule 12, "'0' is
not 'not computed'").
**Real seed to render:** University of Gdańsk (`I40413290`), the 8 default
lenses at N=50.

---

## 4. A/B verdict

Full measured criteria, screenshots and the one-paragraph reasoning for each
verdict live in an A/B verdict record
(not duplicated here in full). Summary:

**A/B #1 (score column, §3):** Winner **A -- `st.column_config.ProgressColumn`**.
Both candidates were zero-baseline compliant and showed the same row count
above the fold in their table portion at 1280px; the decisive difference was
structural, not a Studio-RULES violation on either side: Candidate B (the
Plotly ranked-dot chart) needs two widgets kept in lockstep (a `st.dataframe`
and a `plotly_chart`) that do not share one scroll region, so past row 10 the
table and the chart drift out of visual sync (the chart, rendered at a fixed
height to show all 30 points, exposes rows the table's own internal scroll
has not reached yet). Candidate A keeps rank, identity and score strength in
one coherent, single-scroll widget, with the percent value printed on the bar
itself. No tied competition rank exists in the L1 top-50 of any of the 19
seeds (checked programmatically), so the honest-tie-rendering criterion
could not be exercised on real data and is scored a tie between candidates.
**Per §2.5, this verdict does not extend to the Aspirational tab**, which
keeps its own interval-mark form regardless (a bare progress bar cannot
render a confidence interval).

**A/B #2 (concordance overview, §3):** Winner **A -- k-count table with
hit-lens chips**. At 1280px both forms fit full width and are equally legible;
the decisive evidence is the 390px render, where Candidate A needs only one
internal horizontal table-scroll to reveal `k of n` and the hit-lens list
(the columns that answer this view's own decision sentence), while Candidate
B's full rank matrix shows only one of its 8 lens columns before its own
scroll is needed, burying the concordance signal behind several swipes.
Both forms keep the page body itself free of horizontal scroll (the house
rule); Candidate B's genuine strength -- column-wise "which candidates does
L6 find" scanning -- answers a different question than the overview's own,
and that question is already answered by each lens's own `tbl-lens-ranked`
tab (§2.4).

**Consequence for `lib/ranked.py`:**
`render_ranked_table`'s score column is always the winning A/B #1 form; every
ordinary lens tab in §2.4 uses it. `render_concordance_table` is always the
winning A/B #2 form for the view in §2.3. Neither verdict changes any other
row in §2 of this document.

---

## 5. A/B verdicts — the profile section forms

Two further A/Bs were run on REAL deployed data (Universite de Strasbourg
`I68947357`, resolved by `display_name` in `data/index.parquet`, and University
of Gdansk `I40413290`), rendered through a throwaway Streamlit prototype and
photographed headless by Playwright at 1280 and 390 px. Full tables, measured
criteria, commands and screenshots: an A/B verdict record.

- **A/B #3 — the share + SI form. WINNER: two aligned panels of one figure
  sharing the y axis**, share bars left, SI lollipops right against a dashed
  reference at the neutral value, no mark where SI is `n/a`. The rival (SI as an
  expected-share tick on the share row itself, the only dual-axis-free form of
  "a secondary marker on the same row") put SI on a per-row scale — equal SIs
  land at different x, so the column cannot be read as a ranking — and stretched
  the share axis by a measured factor of 1.59 on Strasbourg, foreshortening
  every share bar by ~37 %. The winner's own cost is a 390 px collapse to 61 px
  per panel, answered by §1.8's stacking rule, not ignored.
- **A/B #4 — where the volume number goes. WINNER: a left text gutter**, numbers
  right-aligned against the zero baseline. Both variants were given the same
  1.18× horizontal budget, so the test isolated placement: the right-of-bar rival
  clipped one real number at 390 px (0 clipped in the gutter form) and scattered
  the 25 numbers across 850 px (travel std 204 px vs 0). Scope: the verdict
  governs a volume printed BESIDE a bar encoding a different measure; a direct
  label on a bar encoding that very number (the yearly global breakdown) keeps
  its end label.

  **Note (re-gated on a later finding):** the verdict
  above still stands, but the ORIGINAL implementation of it (a separate
  `add_annotation` per row, independent of the y tick label) collided with the
  category label at 390 px — see §2.15's fix note for the mechanism, the
  measured cause (`yaxis.automargin` does not reserve room away from a plot's
  own bars), and the robustness rule this leaves for the next A/B that places
  a number beside a label.

  **Update: the gutter placement STAYS, the
  ellipsis rule it was paired with does NOT.** A/B #4's verdict is about WHERE
  the volume number goes (the left gutter, right-aligned) — it says nothing
  about what happens to an over-length CATEGORY label sharing that same tick
  string, which was a separate, later decision (the earlier ellipsis rule, chosen only
  because that fix needed some rule for the label half of the folded string). The
  user's own read was that shortening a field or topic name is a
  worse failure than a taller row, so this update replaces the ellipsis with a two-line
  WRAP (`charts.wrap_label`, §2.15's update) while leaving A/B #4's own
  finding — gutter over right-of-bar, numbers right-aligned against the zero
  baseline — completely untouched. No re-test of A/B #4 was needed or run: the
  wrap change touches only the LABEL half of the folded tick string, never the
  volume half the A/B actually measured.

Both winners are implemented in `lib/charts.py` and exercised on the real frames
by `tests/test_charts.py`.

---

## 6. A/B verdicts

Two A/Bs were run on **real deployed data**, on the six institutions named
below — Iscte `I110026055`, ETH Zurich `I35440088`, Sorbonne
`I39804081`, University of Gdańsk `I40413290`, IMT Atlantique `I4210127572`,
Université de Strasbourg `I68947357` — rendered through a throwaway Streamlit
prototype and photographed headless by
Playwright at 1280 px. Frames come from the
deployed parquet files, reproducing the §4 contracts by hand rather than
importing the app's own modules.

**Everything below is MEASURED off the live DOM, not eyeballed.** The runner
reads every rendered mark's bounding box and computes: `min_mark_px` (the
smallest mark), `max_overlap_frac` (the largest overlap between two marks OF ONE
ROW, as a fraction of a mark's own diameter — rows are resolved from geometry,
`floor((y_centre − plot_top) / (plot_height / n_rows))`, not guessed),
`span_px` (how far the eye must travel to compare every institution on ONE
category) and `cross_occluded_frac` (the share of marks whose centre is covered
by a mark of a DIFFERENT institution). Screenshots: `ab5_a_1280.png`,
`ab5_b_1280.png`, `ab6_a_1280.png`, `ab6_a2_1280.png`, `ab6_a3_1280.png`,
`ab6_aq_1280.png`, `ab6_b_1280.png`.

### A/B #5 — the Compare mirror form. WINNER: dot rows.

Fields mirror, 26 fields × 6 institutions, 1280 px. The grouped-bar form the
plan first proposed was already refuted before this A/B (measurement #16 / A4:
2.6 px per bar at the shipped pitch), so the contest is dot rows against small
multiples.

| measured at 1280 px | **A — dot rows (shipped)** | B — small multiples |
|---|---|---|
| `min_mark_px` (floor 8) | **12.0** ✔ | 10.8 (bar thickness) ✔ |
| `max_overlap_frac` in one row (ceiling 0.5) | **0.000** ✔ | 0.000 (bars cannot overlap) |
| `span_px` — eye travel to compare all six on ONE field | **74** | **900** (12.2×) |
| share-axis plot width per institution | **496 px** | 299 px |
| figure height | 2,020 px | 900 px |
| mass-paired SI panel | **yes**, 12 traces = 6 × 2 panels | **no**, 6 traces, share only |
| category labels | wrapped, no collision | **collide** at the 14.5 px panel pitch |
| horizontal scroll | none | none |

**Verdict.** The dot row wins on the criterion the panel exists for. Comparing
one field across the compared set costs 74 px of eye travel in the dot row and
900 px in the grid — the grid puts the six marks that answer the question in six
different panels, which is the one thing a *mirror* must not do. It also gives
each institution a 496 px share axis against 299 px, and it is the only form
with room for the mass-paired specialisation panel that makes mandatory.
Its cost is real and is accepted: 2,020 px against 900 px, i.e. the Fields
mirror is a scrolling panel at k = 6. The A4 acceptance is met with margin
every mark 12.0 px against a floor of 8, and zero row-overlap against a ceiling
of half a dot — and it is met **by construction, not by luck**: lanes are
`LANE_PITCH_PX` apart inside a row band whose own height is sized from the lane
count, so no frame can violate it.

Two things the render changed in the shipped builder, both found by looking at
the picture rather than at the numbers:
* the first draft dodged marks GREEDILY, per row, which was more compact (1,204
  px) but put institution 3 second from the top in one row and fourth in the
  next. A vertical position that changes meaning row by row is worse than the
  overlap it fixed, so the split became all-or-nothing with the lane index fixed
  to the SLOT — and the panel grew to 2,020 px, which is the honest price of a
  lane that means something;
* `charts.row_height`'s two-line pitch is not enough for a stacked lane set:
  `compare_row_height` adds the SHORTFALL between the profile pitch and the lane
  stack's own need, per row. Multiplying the whole row budget instead produced a
  2,852 px panel for the same picture.

### A/B #6 — the frontier plane. WINNER: small multiples.

Top-200-by-volume topics per institution, 1,145 rendered bubbles, 1280 px.

| measured at 1280 px | A — overlay | **B — small multiples (shipped)** |
|---|---|---|
| `cross_occluded_frac`, k = 6 | **0.907** | **0.000** |
| `cross_occluded_frac`, k = 3 | 0.780 | 0.000 |
| `cross_occluded_frac`, k = 2 | 0.626 | 0.000 |
| `cross_occluded_frac`, top-quartile mode, k = 6 | 0.857 | 0.000 |
| `min_mark_px` | 9.4 ✔ | 7.5 ✘ in the prototype (the shipped builder raises its own bubble minimum to 8) |
| plot area per institution | 1,039 × 425 shared by six | 329 × 255 each |
| figure height | 520 px | 640 px |

**Verdict.** The overlay loses, and it loses at every k tested and in both point
modes. At k = 6, nine marks in ten have their centre covered by a mark of a
DIFFERENT institution; the last institution drawn blankets the dense core and the
five under it are gone. Opacity does not rescue it — `OVERLAY_OPACITY` was on for
every measurement above. The dataviz series ladder predicted exactly this
("all-pairs forms cap at three"), and the sparser top-quartile mode does not fix
it either (0.857) because top-quartile topics cluster in the same corner of the
plane by definition. Faceting takes the number to 0.000 by construction and keeps
it there at any k, at a cost of 120 px of height and a 3.2× smaller plane per
institution.

`fig_frontier_overlay` is nonetheless KEPT, as an explicitly secondary mode
(§3.6): the single plane answers one question the facets cannot — whose topics
sit furthest out, over everybody — and a bubble stays identifiable on hover. Its
caption carries the occlusion figure, so the reader is told what the picture is
hiding. What is NOT acceptable is the overlay as the default, which is what the
plan assumed.

### Scope of these two verdicts

A/B #5 governs the **mirror** family (§3.2–§3.5): a categorical axis, one value
per institution per category. It says nothing about a part-to-whole read, which
is why a part-to-whole read earns a stacked bar rather than dot rows. A/B #6
governs a **topic-cloud** plane; it does not reopen §2.18's single-institution
frontier scatter, which has one series and no occlusion problem.

### Render proof

A screenshot of every shipped builder on the
six real institutions, one page, 1280 × 9,900 px, 11 figures, `scroll_ok: true`.

## 7. A/B verdicts

Three A/Bs, run on **real deployed data**, on the trio named below
— University of Freiburg `I161046081` (slot 1, `inst_key` 876), Sorbonne
Université `I39804081` (slot 2, 2 922), Université de Strasbourg `I68947357`
(slot 3, 13 085) — rendered through a throwaway Streamlit prototype
and photographed headless by Playwright at
1280 px. Frames come from the deployed parquet
files, reproducing the data contract's §4 contracts by hand rather than
importing modules, which do not exist yet.

**Everything below is MEASURED off the live DOM.** The runner reads every mark's
and every label's bounding box and computes `min_mark_px` (a bar's mark size is
its THICKNESS, a dot's its diameter), `span_px` (eye travel to compare all three
institutions on ONE row), `n_value_labels` (labels drawn on marks),
`label_gap_px` (label edge to its own mark), `label_collisions` (overlapping
label boxes), `occluded_frac` (bubbles whose centre is covered by another
bubble) and `bar_gap_px` (the length difference between the two bars of a
diverging row).

### A/B #7 — the Compare metric form at N ≤ 3. WINNER: grouped bars.

26 fields × 3 institutions, metric = share, 1280 px. The earlier verdict (§6, A/B #5)
chose dot rows over grouped bars at **k = 6**, where measurement had found
2.6 px per bar. caps Compare at three, so the contest is re-run.

| measured at 1280 px | **A — grouped bars (shipped)** | B — dot rows (the earlier form) |
|---|---|---|
| `min_mark_px` (floor 8) | **12.8** ✔ | 12.0 ✔ |
| `span_px` — eye travel across one row | 43 | 39 |
| `n_value_labels` on marks | **77** | **0** |
| `label_collisions` | **0** | — (no labels) |
| plot width for the compared measure | **799 px** | 496 px (the rest goes to the SI panel) |
| figure height | 1,513 px | 1,158 px |
| marks drawn | 77 (= 26 × 3 − 1 missing cell) | 154 (77 share + 77 SI) |
| horizontal scroll | none | none |

**Verdict.** At k = 3 the dot row's advantage is gone and its cost is not. The
bar is 12.8 px against the dot's 12.0 and the eye travel is 43 px against 39
a 4 px difference, i.e. the two forms are equivalent on every legibility number
A/B #5 was decided on. What separates them is the **value label**: 77 numbers on
the marks against zero. The dot row put volumes in the hover because six numbers
could not fit in a row; three fit, and a comparison the reader can read without
hovering is a different chart. The price is 355 px of height and the loss of the
paired share + SI panel — which pays deliberately, because SI is now one
of six options on the metric selector rather than a permanent second panel.

The label budget was the one thing that could have refused this: Studio
`LEGIBILITY_BUDGETS.md` puts "bars with direct value labels" at ≤ 12 and this
figure draws 77. The budget is one of the file's own **unmeasured** working
rules; the measurement here — 0 label collisions, a constant 3 px label-to-mark
gap at 26 rows — is what overrides it, and the reason it survives is that the
labels are distributed one per bar down a 1,513 px column rather than crowded
along one axis. **Reported back to the Studio as a measured data point.**

Two things the render changed, both found by looking at the picture:
* `textposition="outside"` clips at the plot frame unless the x range carries
  headroom — `AXIS_PAD_FRAC` is that headroom, and `cliponaxis=False` the belt;
* a hairline row rule beats a zebra band here. The earlier dot-row mirror's zebra keeps a
  lane stack reading as one row across whitespace; behind three touching bars it
  fights the bars for the same ink.

### A/B #8 — recovering an imbalance. WINNER: map + diverging bars.

Sorbonne–Strasbourg shared frontier topics, 1280 px. The question is whether a
reader can recover a 1-vs-20 split, and at what occlusion cost.

The probe rows are real, not invented: the most lopsided shared topic is
**Cosmology and Gravitation Theories, 373 (Sorbonne) against 18 (Strasbourg) =
20.7:1**; the most balanced plotted topic is **Advancements in Battery Materials,
137 against 54 = 2.5:1**.

| measured at 1280 px | **A — map + diverging bars (shipped)** | B — one gradient chart |
|---|---|---|
| how the imbalance is encoded | bar LENGTH + the two counts on the marks | a hue on a diverging ramp |
| 20.7:1 vs 2.5:1, as rendered | **305 px** of length difference | ΔE **14.9** (normal vision) — **below the 15 floor** |
| 20:1 vs 10:1 | ~2 bar-lengths apart, both counts printed | ΔE **2.3** |
| 20:1 vs 5:1 | ditto | ΔE **7.0** |
| `bar_gap_px` across the 14 plotted rows | min 71.4 · median 187.5 · max 305.4 | — |
| `occluded_frac` | 0.708 at N = 120 · **0.450 at N = 60** | **0.834** at its 362 shared topics |
| bubbles | 120 | 362 |
| `min_mark_px` | 19.4 | 13.7 |
| exact values recoverable | **yes** (28 value labels) | no |

**Verdict.** The gradient loses on its own numbers, and it loses where it is
supposed to be strong. Its whole claim is that one chart can carry the imbalance;
put through the same validator the palette is built with, the distance between
the MOST and LEAST lopsided topics it plots is ΔE 14.9 — under the normal-vision
floor the app applies to every categorical pair — and the distance between a 20:1
and a 10:1 topic is 2.3, which is nothing. A reader cannot rank two topics by
imbalance in it, let alone read 373 and 18. The paired bars encode the same fact
as 71–305 px of length with both counts printed on the marks.

The gradient also loses the occlusion argument it was meant to win: 0.834 of its
bubbles have a covered centre against the map's 0.708 at the same style of plane,
because a single chart has to plot every shared topic where the map has a top-N
slider. **The slider was measured, not assumed**: 0.450 at N = 40 and N = 60,
0.588 at N = 80, 0.708 at N = 120 — so the map ships with **N = 60 as the
default**, where a bubble is 22.7 px and fewer than half have a covered centre.

One finding the render forced into the spec and into CD/CP's captions: on this
data the exclusive-vs-shared colour split is **near-degenerate at the head**. Of
the 120 largest pooled topics, 114 are held by all three institutions, 5 by two
and 1 by one (118 of 120 shared for the pair). The map's real work is POSITION
and SIZE; exclusivity is a tail phenomenon. §4.6 therefore obliges the caption to
state the shared count from data — a picture that is 95 % one colour must say so
rather than let the reader infer that the colour is doing work.

### A/B #9 — where the value label goes. WINNER: the bar's own outer end.

The same 26 × 3 figure, metric = SI, 1280 px. A — each label at its own bar's
outer end. B — all labels pooled into one column at a fixed x, in lane order.

| measured at 1280 px | **A — outer end (shipped)** | B — pooled centre column |
|---|---|---|
| labels drawn | 77 | 77 |
| `label_collisions` | **0** | **76** |
| `label_gap_px` median | **3.0** | 271.7 |
| `label_gap_px` max | **3.0** | 423.7 |
| labels actually readable | 77 | **1 per row at best** |

**Verdict.** Not close, and the picture is worse than the table. Pooling the
three labels of a row at one x stacks them on top of each other: 76 of the 77
label boxes overlap, and the render shows the result — "2.94", "2.41"
and "2.44" printed over one another into an unreadable glyph. The pooled column
also puts a median of 272 px between a number and the mark it describes, so even
where a label survives, pairing it back to a bar is a scan across the panel.
A/B #4's aligned left gutter (§4 of this file) worked because it held ONE number
per row; three per row is not a gutter, it is a collision.

The constant 3 px gap in variant A is `textposition="outside"`'s own offset and
it does not grow with the row count, which is why 26 rows collide zero times.

**Scope.** This verdict governs a value label attached to a MARK — the §4.2–§4.5
grouped bars and, by the same measurement, SI panels, where
"outer end" means the end of the bar away from the SI = 1 reference. It says
nothing about the single-number left gutter of §2.15/§2.16, which A/B #4 decided
and which this A/B does not reopen.

### Render proof

Every new builder rendered on the real
trio, one page, 1280 × 6,200 px, 6 figures, 350 marks, 230 value labels,
0 label collisions, `scroll_ok: true`. The pulse frame on that page is **synthetic and
labelled as such** — `collab_pairs.parquet` lands with pipeline; what
the render proves there is the builder's geometry, not any number.

## 8. A/B verdicts

Every variant drawn
through the SHIPPED builders and screenshotted in a real browser (kaleido is not
installed and is not to be added). Colour distances: the dataviz validator
itself, logged in `design-system/palette_validation.txt` runs 18–25. Frames are synthetic at the REAL geometry (26 fields × 3
institutions, 7 ERC panels × 3) — what these A/Bs test is legibility at the
shipped pitch, not any number.

### A/B #10 — the institution trio. WINNER: the searched trio.

| | A `#FC9095/#28CFB7/#90B3FC` (earlier candidate) | B `#FF8BA6/#B4BF07/#8EB3FF` (search) |
|---|---|---|
| worst in-trio CVD ΔE | **6.1** deutan (the 6–8 band) | **12.6** deutan |
| worst in-trio normal ΔE | 16.5 | 20.2 |
| min ΔE to OA / SDG | 9.6 / 9.3 | 9.4 / 9.6 |
| min ΔE to FOCAL / SHARED | 24.2 / 25.1 | 24.2 / 24.6 |
| contrast on white | 2.20 / 1.96 / 2.09 | 2.21 / 2.02 / 2.09 |
| validator | ALL CHECKS PASS (run 18c) | ALL CHECKS PASS (run 18) |

Both pass. They tie on the axis the coexistence exception already forgives (OA
and SDG, unreachable at any lightness) and they differ by 2× on the axis that is
a requirement: telling the three institutions apart. Read at 1280 px, A is the
prettier set — salmon, mint and periwinkle are a softer family — and that is
exactly the problem: its salmon and its mint are the ΔE 6.1 pair, so the two
bars a reader most often has to separate are the two that collapse under deutan.
B's acid olive is unlovely beside them and unmistakable, which is what a
categorical slot is for. Every triple in the search that clears CVD 8 contains a
yellow-green: at L 0.77 the red/green confusion lines have collapsed and that
region is the only one left.

**Also read on the same renders:** at 26 rows × 3 the bars are 12.8 px, the
2 px SURFACE gap holds, no value label collides, and the two low-volume rows
(hollow + dagger) are distinguishable from the 24 solid ones at a glance
including in the pale fills, because the outline keeps the institution's hue.

### A/B #11 — value labels and gutter numbers: twins or secondary ink. WINNER: the twins.

Variant A: labels and gutter in `INK_SECONDARY` (contrast 6.43:1). Variant B:
each in its institution's dark twin (4.51 / 4.54 / 4.53:1). Both clear the 4.5:1
body-text floor, so this is not a contrast question — it is an attribution one.
On the VALUE labels the difference is small (the label sits at its own bar's
end). On the GUTTER it is decisive: three grey integers in a row
(`231 268 305`) carry no clue which institution each belongs to, and the render
shows the ink variant reading as one meaningless run of digits where the twin
variant reads as three institutions. This is the one deliberate departure from
the dataviz rule "text wears text tokens, never the series colour", and the
justification is the same measurement that forced the twins into existence: at
2:1 the mark alone cannot carry identity, so the text has to help.

**Fixed on the second render:** the first pass joined the three gutter numbers
with a thin space and they ran together; they are now separated by two no-break
spaces (an ordinary space would be a legal line break inside a tick label).

### A/B #12 — which ERC domain gets which hue. WINNER: PE violet / LS green / SH vermillion.

The trio's legality was never open (run 13 = run 23, ALL CHECKS PASS, no
warning); only the assignment was. Scored over all six permutations as
"close to the OA domain that means the SAME thing, far from the ones that mean
something else":

| permutation | score |
|---|---|
| **PE violet · LS green · SH vermillion** | **+32.8** |
| PE violet · LS vermillion · SH green | −0.0 |
| PE vermillion · LS green · SH violet *(the plan's listing order)* | −7.1 |
| PE green · LS violet · SH vermillion | −7.8 |
| PE vermillion · LS violet · SH green | −21.0 |
| PE green · LS vermillion · SH violet | −26.7 |

The winner wins by a chasm because of one leg: ERC Life Sciences green sits 6.0
from OpenAlex Life Sciences green and 28.7 from everything else — the same
meaning wearing nearly the same colour in both taxonomies. SH is the weak leg in
every permutation (OA Social Sciences is yellow and none of the three hues is),
which is why the row label naming the panel in full is load-bearing rather than
decorative. Read on the renders: with the plan's order the vermillion PE glyph
sits beside the rose institution bars — the trio's nearest cross-family pair
(normal ΔE 18.7) — where the winner puts violet there and keeps every glyph
plainly outside the institution family.

**The mapping was "fixed by a quick A/B". The A/B overturned the
plan's own listing order. That is what the A/B was for.**

### A/B #13 — the Compare overview card's leader mark. WINNER: the dot.

Variant A: a `DOT_HTML_PX` dot in the leader's fill plus its name in the twin.
Variant B: the whole card tinted in the leader's fill. Rendered side by side and
read: the tint puts the card's secondary text (`INK_SECONDARY`) on an L 0.77
ground, where it measures 1.4–1.9:1 — below every text floor in this app — and
it makes the card LOOK like it belongs to one institution when its number is a
comparison across all three. The dot is a mark of the same kind the chart below
draws, it sits beside the value, and the card's ink is untouched. An earlier
ruling, now measured rather than assumed.

### Render proof

The shipped trio through the shipped
`fig_metric_bars` at 26 fields × 3 institutions, 1280 px: 78 bars, 78 value
labels, 78 gutter numbers in three inks, 3 domain separators, 2 hollow
low-volume rows with daggers, 0 label collisions, no horizontal overflow.

## 9. Chrome contract convergence

Normative source: `design-system/CHROME_CONTRACT.md` (derived from a full audit
of every rendered chart/table). This section folds
the two binding conventions that section produced into VIZ_SPEC's own record,
since both change how numbers and grouped bars are built by this document's own
prior sections (§1.2, §2.14/§2.15's `_series_offset_width` geometry).

### 9.1 Number-format policy: printf-style, period-decimal, everywhere

**Rule, superseding any prior silence on this point:** every number the app
renders — a share, a score, an SI value, a count — is composed with a
printf-style format string (`"%.1f"`, `"%.2f"`, `".1%"` via Python's own
`format`) or an equivalent locale-INDEPENDENT spec, never a keyword whose
rendering the host locale can change. `st.column_config`'s `format="percent"`
is the one keyword this rule specifically bans: it looks like a formatting
convenience, but it renders through the browser's own locale (confirmed live,
comma-decimal — `76,04 %` — on the exact column the app's Find lens tabs are
built around) rather than through anything the app's own code controls.
`views_collab.py`'s `FWCI_FORMAT = "%.2f"` was already the compliant pattern to
copy (CHROME_CONTRACT.md §9); generalises it to every
`ProgressColumn` that shows a score or a share.

**The scaling trap, so the next editor does not reintroduce it:** a
`ProgressColumn` bound to a raw 0–1 value cannot simply switch to a printf
`format=` string, because the format string has no scaling step of its own
`"%.0f%%"` applied to `0.76` prints `"1%"` (the value rounded to the nearest
whole FRACTION, not a percentage), which is the exact defect a since-retired
`# fix` comment on `lib/ranked.py`'s score column named correctly but
then still shipped `format="percent"` as its workaround. The fix has two
halves that both have to be in place: **the underlying dataframe column must
already carry the value ×100**, and the column config's format string then
formats that 0–100 number. `lib/ranked.py` ships both halves as one shared
pair — `ranked.PCT_PROGRESS_FORMAT` (`"%.1f%%"`) and `ranked.pct_progress_column(label)`
(the `ProgressColumn` builder, `min_value=0, max_value=100`) — plus
`ranked._pct100(v)`, the ×100 transform `format_rows`'s own `score` column now
applies. Any other 0–1 score rendered as a `ProgressColumn` elsewhere in the
app should import and reuse this pair rather than hand-roll a second one.

**Fixed:** `lib/ranked.py`'s lens-table
`Score` column (`render_ranked_table`) — the app's single most-read column
(§2.4 above). **Fixed elsewhere from the same shared pair:**
`lib/views_find.py`'s Aspirational-tab `L1 overlap` column;
`lib/views_collab.py`'s topic-table `top10_share`/`sdg_share` columns, which
share ONE `PROGRESS_FORMAT = "percent"` constant feeding two `ProgressColumn`
calls. A whole-`app/lib` grep for `format="percent"`, `toLocaleString`,
`Intl.NumberFormat` and a locale-sensitive `{:n}`/`,n` spec found no other hit
of any of the four shapes.

### 9.2 Bar-group spacing: one constant pair, not two

**Superseded by this section:** §2.14's `fig_breakdown_yearly` and every
`fig_share_si`/`fig_topics` caller of `_series_offset_width` (§2.15–§2.17)
previously drew from `charts.DEFAULT_GROUP_SPAN`/`DEFAULT_GROUP_FILL` = **0.8 /
0.9**. `lib/charts_compare.py`'s `fig_metric_bars` (Compare's Subject/ERC/SDG
sections, §2 ter) independently defined its OWN pair for the identical
geometry helper, `BAR_GROUP_SPAN`/`BAR_GROUP_FILL` = **0.82 / 0.86**, so the
same grouped-bar idiom drew at two fractionally different pitches depending on
which page it appeared on.

CHROME_CONTRACT.md §0 names Compare's `fig_metric_bars` chrome as the chart the
rest of the app should converge ON (the newest chrome, reused three times
verbatim with zero copy-paste drift) — so **0.82 / 0.86 is the value that
wins**. `lib/charts.py`'s `DEFAULT_GROUP_SPAN`/`DEFAULT_GROUP_FILL` are now
**0.82 / 0.86**, the single source for both pages; `charts_compare.py` should
import these two names rather than keep its own copies. Consequence: Compare's own geometry is
UNCHANGED (it already drew at 0.82/0.86); the Find yearly-breakdown pair now
draws fractionally tighter than before — visually the same idiom, one
constant pair instead of two.

## 10. Chart primitives rebuild

Ratified per §7's decisions log, after a full personal review of the
render proofs before ratifying. Scope: `fig_metric_bars`
— the bar-family chart every horizontal-bar chart in `charts.py`/
`charts_compare.py` is asked to converge on — plus an explicit audit of
the dot/SI family, confirmed to keep its own, already-correct conventions
(§10.3). Render proof: the Ifremer/NIOZ/GEOMAR sample trio,
share/PP/FWCI(subject grain)/SDG-share/ERC, at 1920/1280/390 px, captured
with a DYNAMIC viewport (§10.5). CHROME_CONTRACT.md §§10–12 are the
per-chart-TYPE contract this section feeds and that every propagation audit
runs against.

### 10.1 The left gutter COLUMN (replaces §5.3)

> **Partially SUPERSEDED by §12 (bar-layout contract, D28).** The mechanism
> below (a phantom `go.Bar` trace) is UNCHANGED and is now single-sourced in
> `lib/charts.py` for BOTH views. What changed: the header line above the
> column is RETIRED (no chart draws one any more), and the left margin this
> column sits inside is a CONSTANT (`LABEL_COL_PX[view] + GUTTER_COL_PX[view]
> + COL_PAD_PX`), never the per-frame measurement this section describes.

- **Form.** A phantom, zero-visible-fill `go.Bar` trace per drawn institution,
  offset into the SAME lane as its real bar, sitting at a small negative x
  (`GUTTER_NEG_AXIS_FRAC` of the data span) with the raw volume as its own
  `text`, `textposition="outside"` pushing it further left. `gutter_header`
  (new) names the basis in a small `INK_SECONDARY` label above the column.
- **Encoding.** The number wears the institution's DARK TWIN — or the
  caution colour (§10.2) on a below-floor row, the SAME rule the real bar's
  own value text follows, so the two texts agree on every row.
- **Mechanism, and why not an annotation.** A prior investigation tested a per-bar
  `add_annotation` first (candidate A) and refuted it on TWO independent
  counts, both reproduced live: (1) an annotation anchored at the plot's own
  `x=0` collides with plotly's NATIVE y-tick label, which is anchored at the
  identical point — enlarging the margin pushes the still-colliding pair
  further right, it does not separate two elements pinned to one anchor; (2)
  even after hiding the native tick and drawing the row label as a SECOND
  hand-placed annotation, `xref="paper"` mislands ONCE ANY chart sets a
  custom margin (which every chart here does) — confirmed through the real
  app's own bundled plotly.js, not only an offline embed. The shipped
  mechanism (candidate B) uses a SINGLE coordinate system throughout — a real
  `go.Bar` trace at a small negative x — so there is no second anchor family
  to collide with, and no `xref="paper"` annotation anywhere in this module.
- **Interaction.** The raw volume is ALSO always in the hover
  (`_metric_hover`'s "works" line), independent of whether the column is
  drawn — so the number survives even where the column does not (below).
- **Empty state / the 390 px breakpoint.** Below roughly 600 px of plot
  width, the column has nowhere to go: a wrapped first-row label alone can
  need the large majority of a 390 px figure's own width, leaving no room
  for a gutter zone AND legible bars — recalibrating the reserved fraction
  from 0.16 to 0.45 still collided, because it is a fraction of the DATA
  range and the data range's pixel footprint shrinks with the plot area (no
  fraction can conjure pixels that are not there). Streamlit cannot read the
  viewport width server-side, so — the SAME "the builder makes the layout
  available, the caller decides when to switch" idiom §2.15's `stacked`
  argument already uses — the CALLER passes `gutter=False` below that
  breakpoint; there is never a horizontal scroll either way.
- **Export.** The volumes are frame columns, so every CSV already has them,
  unchanged.

> **Rejected alternative:** candidate A in either form (see Mechanism,
> above) — a dead end in this app's actual rendering stack independent of the
> narrower same-anchor bug, since `xref="paper"` cannot be trusted once a
> chart reserves its own margin. PNGs: `gutterA_naive_*.png` (the same-anchor
> collision), `gutterA_*.png` (the paper-coordinate bug); the shipped
> mechanism: `gutterB_*.png` (clean at 1920/1280 px) and `gutterB_calib_*.png`
> (the 390 px real-estate limit, confirmed not a coding slip).

### 10.2 The caution channel (replaces §5.4)

- **Form.** Every bar is SOLID, in the institution's own colour, at every
  volume — no hollow fill, no diagonal `marker.pattern`, anywhere in
  `fig_metric_bars`. A flagged row's VALUE text and gutter-column text (§10.1)
  switch to `palette.WARNING_CAPTION_COLOR` instead, keeping
  `LOW_VOLUME_GLYPH` (the dagger).
- **Encoding.** Colour on TEXT only, never on the mark: the bar itself stays
  the one and only identity family this chart carries (the institution), so
  a caution never competes with that for the reader's eye the way a second
  fill treatment would.
- **The floor itself is UNCHANGED.** `_is_low_volume`'s per-metric fork
  — PP/FWCI on their own per-row `denom_value` against
  `palette.RATIO_HATCH_FLOOR`, every other metric on `vol_full_annual_mean`
  against `LOW_VOLUME_FLOOR` — is the SAME flag computation as an earlier
  amendment. Only the RENDERING of a flagged row changed.
- **Interaction.** The hover still carries the reason in plain words
  (`HOVER_LOW_VOLUME`), unchanged.
- **Empty state.** No marker column, or no value in it → NOT flagged,
  unchanged.
- **Export.** The mean annual volume / denom_value are frame columns,
  unchanged.

> **Rejected alternative:** keep the hatch, only retint it. Rejected because
> a full eyes-on PNG review named the
> hatch/hollow rendering itself as the thing to retire, not its colour — a
> diagonal texture on a bar's own fill reads as "this mark is damaged/
> half-rendered" at density in a way a caution-coloured NUMBER, sitting
> exactly where every other value sits, does not.

### 10.3 The dot/SI family — audited, confirmed UNCHANGED (partially converged by §12)

> **§12 update (bar-layout contract, D28):** two of the three findings below
> are SUPERSEDED, not by reopening the judgement but because the thing they
> ruled "stays apart" later converged anyway. The gutter mechanism is no
> longer folded into the tick label at all — Find now draws the SAME
> phantom-trace column §10.1 describes, single-sourced in `lib/charts.py`
> for both views (`_tick_display`, named below, is retired). The neutral
> reference's COLOUR changes to `palette.WARNING_CAPTION_COLOR` (red),
> matching §10.4's own repaint — it stays a dashed RULE, never a diamond,
> exactly as this section already judged; only the hue moves. The below-
> floor hollow-dot ruling (bullet one) is genuinely UNCHANGED, including
> under D28: the DOT survives, only its connecting STEM is retired (a
> per-row connector to a now-unmistakable red reference line is redundant).
> Full current detail: `CHROME_CONTRACT.md` §11.

The question was raised whether the SI/mirror-dot below-floor MARKER should be
retired too. Judged and confirmed NO, for two independent reasons:

- **It is a different visual grammar, not the same mechanism wearing a
  different name.** `fig_share_si`/`fig_mirror_dots`'s below-floor cell is a
  HOLLOW dot — SURFACE fill, a coloured OUTLINE at `OUTLINE_WIDTH` — which
  still reads as an IDENTITY (a ring in the institution's own hue) rather
  than a hole or a damaged mark. The bar hatch this round retired was a
  diagonal texture stamped ACROSS a mark's own fill, which is what read as
  "broken" at density; a filled-vs-hollow marker swap does not carry that
  failure mode, and plotly's own pattern fill is a Bar-family feature that
  does not exist for a Scatter marker in the first place (§5.4's own
  reasoning, unchanged).
- **The two sections were never asked to use the SAME mechanism, only the
  same DISCLOSURE** (a below-floor cell is drawn, never dropped, and the
  reason is in the hover) — which both still do.
- **The gutter-in-tick-label mechanism (§5.3's original form, still live in
  `fig_share_si`) is intentionally NOT unified with §10.1's phantom-trace
  column.** It solves a DIFFERENT problem: one number per row (this
  institution's own volume) rather than up to three. WT_2D's own prior-art
  note: an EARLIER version of this exact profile gutter WAS a separate
  `add_annotation` in a negative-x sliver — precisely candidate A's shape
  and was retired specifically because it relied on `automargin` to keep two
  independently-positioned text systems apart, which collided into one
  garbled word at 390 px. Folding the one number into the tick string
  (`_tick_display`) fixed that for a ONE-number-per-row chart; re-splitting
  it back into a separate column now would only reintroduce the bug its own
  fix already solved, for a chart that never needed the up-to-three-numbers
  form Compare's `fig_metric_bars` does.
- **The SI/ESI neutral reference stays a dashed rule, not a diamond.** §10.4
  below distinguishes "a reference beside a panel already full of solid
  bars" (where a thin dash reads as a stray pixel) from "a reference on a
  MOSTLY EMPTY dot panel" (where the same dash reads cleanly) — the dot
  family is the second case, unchanged.

### 10.4 The reference mark (replaces §5.5's encoding — the arithmetic stays)

> **SUPERSEDED by §12 (bar-layout contract, D28).** The `diamond-tall`
> marker described below is RETIRED — the reported defect named it directly
> ("a dark diamond that is not visible"). Both the varying and the constant
> case now draw in `palette.WARNING_CAPTION_COLOR` (red): a per-row `go.Shape`
> vertical line (never a marker) for the varying case, one full-height rule
> for the constant case. See §12 for the full mechanism and its render proof.

- **Form.** A reference that VARIES by row (PP / SDG-tagged share / Dynamics
  / FWCI's own per-taxon population mean) is now a dark `REF_MARKER_SYMBOL`
  ("diamond-tall") MARKER per row, `go.Scatter`, size `REF_MARKER_SIZE`,
  `palette.INK` — added to the figure BEFORE the bar traces so it sits
  BEHIND a bar's own outside-text where the two coincide. A reference that
  is the SAME for every row (SI's neutral value; any single-value
  `REF_METRICS` case) stays ONE rule across the panel, now `palette.INK` at
  `LINE_PX` (2 px) rather than the earlier `INK_SECONDARY` hairline.
- **Encoding.** A MARKER is a different mark FAMILY from a bar, a grid line
  or a row rule — unmistakable at 26×3 density;
  the earlier per-row DASH (refA) was confirmed nearly invisible next to a
  panel already full of solid institution-coloured bars, and refB (the same
  dash, heavier and darker) was a real improvement but still a thin line
  competing with the row rules and the grid at a glance. A marker repeated
  on a value that never changes (the constant case) would be visual noise,
  not a benchmark, which is why that case keeps a rule rather than moving to
  the diamond too.
- **Interaction.** The hover still names the reference beside the value,
  unchanged; the marker itself carries no hover of its own
  (`hoverinfo="skip"`) since the same fact is already on the bar's line.
- **Empty state.** A non-finite reference draws no marker for that row,
  unchanged.
- **Export.** `ref_value` still ships in the CSV, unchanged.

> **Rejected alternative:** refB (heavier/darker dash) for the VARYING case
> too. Measured (`refB_sdgshare_1920.png`) and rejected: visibly darker and
> thicker than refA, but still a thin dash competing with the row-rule
> hairlines and the vertical grid at a glance — an improvement, not a fix.
> One placement caveat carried forward as a documented, not blocking, detail:
> a diamond can land on top of a bar's own value text when the reference
> value coincides with where that text sits (`refC_pp10_1920.png`, row 2);
> this module resolves it by z-order (the reference trace draws first, so it
> sits behind the bar's text), not by moving the mark family.

### 10.5 Dynamic-viewport proof capture (E11)

**Not a chart-code defect — a proof-HARNESS one, closed at the harness.**
Investigation root-caused an earlier "first row clipped" symptom
to a capture script's own fixed
`viewport={"height": 1400}`, used for EVERY chart width regardless of the
chart's own declared height: the SAME app, the SAME URL, the SAME chart,
captured at a viewport TALLER than the chart's own `layout.height` renders
the first row perfectly, every time. A 26-row × 3-series share chart
legitimately needs 1513 px (`metric_row_height(26, 3, 0)`) — every
grouped-bar Compare chart at real row density will exceed a 1400 px
viewport eventually, and any FIXED viewport is therefore a ticking version
of the same bug, not a fix for this one instance of it.

**The rule, binding for every future proof script that screenshots a
`.js-plotly-plot` element:** read the chart's own rendered height (
`gd.layout.height`, or the element's `getBoundingClientRect.height`) and
set the page's viewport to AT LEAST that height before screenshotting
never a viewport fixed in advance. Any screenshot script that captures a
`.js-plotly-plot` element should implement this rule (CHROME_CONTRACT.md §12).

A SEPARATE, real, currently-dormant defect was found while investigating and
is fixed in code, not just in the harness: `metric_row_height`'s FALLBACK
branch (the one that fires whenever `BAR_PX * n_series` exceeds the base row
pitch — true for every ≥2-institution Compare chart) used to compute
`need * n_rows` from `BAR_PX` alone, dropping `n_wrapped` entirely
`metric_row_height(26, 3, n_wrapped=0)` and `metric_row_height(26, 3,
n_wrapped=1)` returned the IDENTICAL number. Fixed by folding the SAME
`WRAP_ROW_FACTOR` term `charts.row_height`'s own base estimate already
applies (plotly spaces a categorical axis UNIFORMLY, so one wrapped label
forces every row to the two-line pitch) into the fallback branch too.
Verified: `metric_row_height(26, 3, n_wrapped=0)` is unchanged at 1513 (today's
real data does not clip); `metric_row_height(26, 3, n_wrapped=1)` now
correctly returns a larger number instead of the same one.

## 11. V4 trim — Compare page rebuild

This section replaces the whole earlier Compare page (§2 ter
through §10 above) with a FIXED two-institution page (two search slots,
no cross-tab shortlist — every "up to `COMPARE_MAX_SERIES`" ceiling above is generous
headroom now, never a live cap) built from four sections: Thematic shape,
SDG profile, Shared frontier, The relationship. The
metric-selector surface (§8/§9's Dynamics/SDG-tagged-as-a-tab/Specialisation/
Volume/FWCI tabs, `SELECTOR_METRICS`) is RETIRED along with the selector UI
it served — the profile and impact sections need exactly two fixed tabs, Profile and Impact. `docs/
CHROME_CONTRACT.md` §§13-14 are the normative chart-chrome record for the two
genuinely new forms below; this section is the render-proof record.

**Deleted, per the "out of scope" list (grep-proved):**
`fig_mirror_dots` (the whole dot-mirror family, §7 quinquies), `fig_
quadrant_mix`, `fig_frontier_overlay`/`fig_frontier_small_multiples` (§6),
`fig_impact_intervals`/`fig_impact_subfields` ("Impact-by-subfield interval
section", out of scope), `fig_frontier_map` and `fig_diverging_shared`, and the pair-pulse
`fig_pulse` (superseded by `yearly_domain_stack` below). The bar-pattern-fill
remnants (`LOW_VOLUME_PATTERN_SHAPE`/`SOLIDITY`, §10's own note that `fig_
pulse` was their one remaining caller) are deleted with it — no hatch
mechanism survives anywhere in `charts_compare.py` after this rebuild.

**Kept, unchanged in substance:** `fig_metric_bars` (§9/§10's bar-family
primitive) — trimmed to the two metrics the profile/impact tabs need (`share`, `pp`) — is the
primitive `two_tab_bars` (below) is a thin adapter onto; `legend_strip`/
`map_legend_strip`/`chart_note`/`basis_caption`/`best_value_dot` (page-level
presentation helpers, not builders).

### 11.1 `two_tab_bars` — Thematic shape and SDG profile

One call site, one `tab` switch (`"profile"` → metric `share`, `"impact"` →
metric `pp`), `grouped_by_field` toggling the field-domain row grouping
no new bar-drawing code, the existing SS10 bar-family contract unchanged.
See `lib/charts_compare.py:two_tab_bars`'s own docstring for the frame
contract; the render proof at all three widths confirms it.

> **§12 changes (bar-layout contract, D28):** the SDG section (`_render_sdg`)
> now calls `_render_two_tab_section` with `tabs=False` — Profile only, no
> Impact tab and no tab strip at all; the Thematic-shape section's own call
> site is untouched and keeps both tabs. The gutter's per-chart header
> ("Publications, full count") is retired. The diamond reference is a dashed
> red tick/line now. Tick font 13 px, gutter font 12 px. The SDG accent
> square (missing before this stream) now shows via a new
> `accent_key_col="sdg_number"` passed through `_render_sdg`.

### 11.2 `mirror_frontier` — Shared frontier

New geometry, three floating `go.Bar` traces per topic via `base=` (A-only /
JOINT / B-only around a common centre) — no kept primitive draws this shape.
Full contract: `CHROME_CONTRACT.md` §13.

**Measured fact, load-bearing for any future DOM check of this chart:**
Plotly renders a tick's `<a href="…" target="_blank">…</a>` pseudo-html as a
real SVG anchor, but SVG spells the link attribute `xlink:href` — a plain
`document.querySelectorAll('a[href]')` finds NOTHING, and a Playwright click
must pass `force=True` because Plotly's own hover-capture `div.svg-container`
sits on top of the SVG and fails the default actionability check (a real
click at that point DOES still reach the anchor and its `target="_blank"`
still opens a new tab — verified end-to-end, including the click).

> **Rejected alternative — a two-panel share+SI-style mirror redrawn for exactly two institutions.** Not
> measured on real data (this redesign supersedes the whole dot-mirror family before
> any A/B on it would matter): the mirror's whole point is showing the THREE
> quantities of one relationship (A-only, joint, B-only) as one continuous
> bar whose SEGMENTS sum to the row's total volume — a dot per institution
> plus a third dot for "joint" would ask the reader to sum three marks
> mentally instead of reading one bar's own composition, exactly the
> "the number is not on the mark" problem A/B #7 (§9) already measured
> against the dot family at low institution counts.

### 11.3 `yearly_domain_stack` — The relationship, year by year

Replaces the earlier single-series pair-pulse chart (`fig_pulse`) with the SAME
joint-publications-per-year figure, stacked by the four OpenAlex domains
instead of drawn as one undifferentiated series. Full contract:
`CHROME_CONTRACT.md` §14.

**Measured fact, load-bearing (do not regress):** on this pinned plotly
(5.24.1), `fig.add_annotation(x="2020", …)` against a `type="category"` axis
whose categories are given as strings does NOT address that category slot
it collapses every category into one slot and strands the annotation off
past the plot's right edge. The fix is to pass the category's own INTEGER
INDEX (`enumerate(years)`) as `x`, never its string label; the bar traces
keep using the label strings (`x=years`), since THEY populate the category
axis correctly — only `add_annotation` needs the index. Found and fixed
during this section's own render proof (screenshot before/after
recorded) — a different manifestation of the same "plotly annotation
positioning is not trustworthy without an explicit numeric anchor" class of
defect `charts._tick_display`'s own fix note already warns about for
`xref="paper"` (§0 of `CHROME_CONTRACT.md`'s companion audit).

### 11.4 `reciprocity_bars` — Strategic reciprocity by field

ADAPTED from `views_collab._reciprocity_chart` + `collab_data.
reciprocity_frame` (credited in the builder's own docstring): the original
was a bubble SCATTER (x = a field's share of B's own corpus, y = the same
for A, area = joint volume, colour = OA domain, one dotted equal-weight
diagonal). V4 keeps the same two numbers per field but draws them as
institution-coloured `fig_metric_bars` bars — the domain, formerly the
bubble's colour, survives as the row-label ACCENT GLYPH instead of a mark colour, and the joint volume,
formerly the bubble's area, is now the LEFT gutter column. No new bar-
drawing code; the geometry CHANGE (scatter → bars) is the deliberate part,
matching the rest of this section's convergence onto the bar-family
chrome rather than adding a second chart grammar for one section.

> **Rejected alternative — keep the scatter verbatim, ported unchanged.**
> Consistency, not a measured A/B: every other Compare section in this trim
> (the profile, impact and shared-frontier charts) now draws through the SS10 bar-family contract, and a lone
> surviving scatter would be the one section whose reference line, hover
> skeleton, colour family and caution channel all diverge from the rest of
> the page for no reason tied to what the data actually needs to show.

### 11.5 Three fixes from a full PNG read (2026-09-03)

A full read of all 21 renders from §§11.1–11.4's first pass accepted
`two_tab_bars` (both tabs) as shipped, and asked for three fixes
full contract detail: `CHROME_CONTRACT.md` §§13.8, 14.4, 15.

1. **`mirror_frontier@390 px` was unusable** (zero visible bars, the x-axis
   title clipped to "Publicatio"). Root cause, measured rather than
   assumed: `yaxis.automargin=True` (already on) grows the configured left
   margin to fit whatever tick text arrives — a wrap-width choice is
   therefore a MARGIN choice, not an independent character-count guess. A
   live Playwright character-length sweep against the actual render found
   the plot area collapses above ~26 chars/line at 390 px and plateaus at
   its margin-capped maximum at 22 and below; `MIRROR_LABEL_WRAP_WIDTH=20`
   keeps headroom under that knee. Fixing the margin ALONE surfaced a
   second, independent defect on the fixed render's own screenshot — every
   wrapped row's second line overlapped the row below it, because
   `mirror_frontier`'s height call omitted the `n_wrapped` term
   `metric_row_height` (and `charts.row_height` before it) already exists
   for exactly this. Both fixes are one system, verified together in
   a render-proof harness (which itself had a
   third, harness-only bug found in the same pass: `html,body{padding:16px}`
   doubled the intended page padding to 32 px per side — fixed by moving the
   padding to `body` alone).
2. **`yearly_domain_stack` had four unlabelled bar colours.** Fixed by
   giving this ONE chart its own native Plotly legend (`showlegend=True`,
   horizontal, anchored above the plot) instead of the app-wide HTML chip
   strip every other builder in this module still uses — CHROME_CONTRACT.md
   §14.4.
3. **`reciprocity_bars`'s x-axis said only "Share of output" and its gutter
   repeated the same joint count on both of a field's bars.** The INPUT
   CONTRACT itself changed from long (one row per institution × field) to
   WIDE (one row per field: `field_id, field_name, domain_id, vol_joint,
   share_a, share_b`, optional `rank_in_a`/`rank_in_b`) to match how C1 will
   naturally produce this shape; the gutter now draws once, centred, via a
   dedicated phantom trace built OUTSIDE `fig_metric_bars` (`gutter=False`
   on the shared call, `_add_centred_gutter` after it — `two_tab_bars`'s own
   per-series gutter is untouched); the x-axis title is now the explicit
   sentence requested; and the hover is a rewritten narrative
   sentence naming the joint count, the share, and (when the optional rank
   columns are present) the partner's rank — CHROME_CONTRACT.md §15.

All three fixes, plus an extra render proving
`grouped_by_field=True`'s row-boundary rules, are documented with proof.

### 11.6 Two more readability fixes (2026-09-03)

A full read of the re-renders confirmed: `mirror_frontier@390px`, the
yearly-stack legend and `reciprocity_bars` all accepted. Two more fixes,
full contract detail in `CHROME_CONTRACT.md` SS13 row 8 and SS10 row 8.

1. **`mirror_frontier` labels were losing real meaning.** At 1280/1920 every
   topic name was cut to two 20-char lines plus an ellipsis regardless of
   its own length -- real OpenAlex topic names run 25-60 characters (for
   example: "Geological and Geochemical Analysis") and were
   unreadable as a result. Fixed: `MIRROR_LABEL_MAX_LINES` raised to three
   (width per line unchanged at twenty); the ellipsis decision moved from
   "however many lines greedy wrap wants" to "the ORIGINAL name is over
   sixty characters" (`MIRROR_LABEL_CHAR_BUDGET`) -- a name at or under the
   budget that still needs a fourth greedy-wrap line gets its overflow
   MERGED into the last line instead (never a lost character, matching
   `charts.wrap_label`'s own two-line philosophy, now applied at three).
   Re-checked at 390 px: the two-line/
   forty-char fallback it allowed for was NOT needed -- automargin's left-
   margin need is driven by line WIDTH (unchanged at twenty chars), not
   line COUNT, so the 120 px bar-area floor held with no further tuning.
   A second bug surfaced on this fix's own first render (the SAME discovery
   pattern as the earlier fix): a three-line row needs MORE vertical pitch than
   `metric_row_height`'s binary two-line-only `n_wrapped` term could supply
   — fixed by `mirror_frontier._mirror_row_height`, a dedicated formula
   generalising `charts.WRAP_ROW_FACTOR` linearly to three lines.
2. **`two_tab_bars`'s `grouped_by_field=True` boundaries named no field.**
   The row separators were there but nothing told a reader WHICH field a
   subfield belonged to. Fixed with two additions, both reusing EXISTING
   mechanisms rather than inventing new ones: the frame contract gains an
   optional `domain_id` column, which the ALREADY-WIRED accent glyph
   (`_accent_ticktext`, `reciprocity_bars`'s own domain accent since
   the earlier fix) now also draws for grouped subfield rows with zero new
   code; and `_metric_hover` puts `"Field: {group_label}"` as the literal
   first hover line whenever the frame carries `group_label`. No group
   header rows were added.

Re-rendered at all three widths. Full proof (render-script assertions,
before/after screenshots) recorded.

## 12. Bar-layout contract (D28) — supersedes the margin/gutter/diamond/font
##     passages in §§2.15–2.20, 10.1, 10.4 and 11.1 above

Triggered by two user reports read together rather than separately: (O4)
"the ERC panel leaves ~150 empty px between the collapsible panel's left
border and the longest y-label… every bar must start at the same pixel,
every bar the same height, every gutter (and its volume) aligned
vertically… in Compare the gutter font size and bar heights differ across
charts" and (C2) "the baseline is a dark diamond that is not visible → a
dashed vertical red line; the gutter is too large; remove 'Publications,
full count'". Both views' bar-family charts now share ONE set of rules
instead of two independently-tuned ones (Find's fold-into-tick-text
mechanism, Compare's phantom-trace column) — single-sourced in
`lib/charts.py`, `lib/charts_compare.py` imports every constant.

**The columns are CONSTANTS, not per-frame measurements.** `LABEL_COL_PX`
and `GUTTER_COL_PX`, one pair per view, are derived ONCE from the WHOLE
label universe on disk — every field, subfield, ERC panel, SDG goal and
topic name the app could ever show, not the current seed's or pair's own
frame — so a bar starts at the identical pixel on every chart of a view,
whatever institution or pair is loaded. This is the mechanical fix for O4:
the old `_gutter_margin_px` measured the CURRENT frame's longest line, which
is why two charts of the "same" panel type could reserve two different
margins and why the ERC panel (labels up to ~68 chars) left dead space when
a shorter panel's own estimate happened to be reused, or reserved more than
a given seed's own labels needed.

**Derivation, offline and reproducible (no browser needed at chart-build
time).** The real rendered tick font — family read ONCE, live, off a y-tick
`<text>` element's computed style on the actual app (`"Source Sans", sans-
serif`) — at `TICK_FONT_PX`; a per-character pixel-width table measured with
that exact font via canvas `measureText`, committed as `lib/resources/
glyph_widths.json` (13 px for a label, 12 px for a gutter number, every
character present in today's label universes, +8 % safety already folded
into the derived constants below to absorb the gap between a canvas
measurement and plotly's own SVG text layout); a pixel-accurate greedy
word-wrap (`charts.wrap_label_px`) capped at two lines, the same "never
split a word, merge a third line into the second" algorithm `wrap_label`
already used, `len()` swapped for the measured width. The label column is
the smallest width at which every label of the family wraps to ≤ 2 lines
with no rendered line wider than the column itself — a fixed point: start
at the family's own longest single word (a word can never be split, so this
is the true floor), wrap the whole universe, remeasure the widest resulting
line, widen if it exceeds the starting width, repeat (converges in a
handful of steps on real data).

**Find's column (306 px) is the widest fixed point over {field, subfield,
ERC, SDG}** (`WRAP_PX = {field: 170, subfield: 242, erc: 292, sdg: 228}`) —
ERC panel labels are the widest family (up to "Molecules of Life: Biological
Mechanisms, Structures and Functions"), so ERC decides Find's column;
topics (the app's own longest labels, up to 86 characters) are NOT part of
this fixed-point search but are measured against the resulting column
separately and fit inside it with room to spare (`WRAP_PX["topic"] = 241 <
292`). **Compare's column (261 px) is the widest fixed point over
{subfield, SDG, topic}** (topics are included here because a later stream's
topic-overlap balance bars will carry topic labels in this same column) —
every family there also carries the taxonomy accent square (below), whose
width is charged to the FIRST wrapped line before the fixed point is
solved. Measured on the real 4,516-topic universe: **0 topics need an
ellipsis fallback** at the derived column (well under the 1 % ceiling this
decision was conditioned on) — `wrap_label_px` still carries the ellipsis
branch as a standing safety net for a future, longer topic name, not a live
path today.

**The gutter column (44 px Find, 41 px Compare)** holds the row's raw
volume, right-aligned, `GUTTER_FONT_PX`, immediately left of the bar
origin — sized off the widest volume that can ever appear there (an
institution's own scenario total, `index.total_full_2020_2024` /
`total_frac_2020_2024`, since no single taxon's volume can exceed the
institution's own grand total), formatted exactly as `_fmt_vol` prints it.
Find's column is wider because its fractional basis can print one decimal
("36 956.0"); Compare's `vol_full` gutter is always an integer.

**ONE gutter mechanism for both views now**, replacing Find's own
fold-into-the-tick-text idiom (§2.15's "Fix X3", `_tick_display`/
`_gutter_margin_px`, RETIRED — not kept as dead code): a phantom,
zero-visible-fill `go.Bar` trace at a small negative x
(`GUTTER_NEG_AXIS_FRAC`/`GUTTER_TIP_FRAC` of the panel's own data span),
its own pre-formatted volume as `text`, pushed further left by
`textposition="outside"` — the exact mechanism Compare's `fig_metric_bars`
already proved at 1920/1280/390 px (CHROME_CONTRACT.md §10.1), now
single-sourced in `lib/charts.py` (`_add_gutter_column`) so both views call
the identical helper. **No header text above the gutter, anywhere** — the
per-chart basis label ("Publications, full count", "Joint publications")
that used to sit above Compare's own gutter column is retired; the basis is
named once, in the section's own caption, never repeated per chart.

**Row pitch and bar thickness — TWO shapes, both fixed.**
`ROW_PITCH_SINGLE = 27` / `BAR_PX_SINGLE = 20` for one-bar-per-row charts
(Find's Fields, Top subfields, Top topics, SDG, ERC panels — up from an
18 px pitch, the O4 "raise each bar's height by ~50 %" ask; `BAR_GAP_SINGLE
= 1 − BAR_PX_SINGLE⁄ROW_PITCH_SINGLE` is solved so the target thickness is
exact, not tuned by eye). `ROW_PITCH_PAIR = 40` / `BAR_PX_PAIR = 16` for
two-institutions-per-row charts (Compare's `fig_metric_bars` family:
Thematic shape, SDG profile, reciprocity — `PAIR_GROUP_FILL = 0.86`
unchanged from the app's existing grouped-bar fill ratio, `PAIR_GROUP_SPAN`
solved so two `PAIR_GROUP_FILL`-filled bars at this pitch are exactly
`BAR_PX_PAIR` px thick). Figure height is now the direct formula "margins +
`n` rows at the row-shape's own pitch" (`charts.row_height_single`/
`row_height_pair`) — **the `n_wrapped` height correction goes away
entirely**: two-line labels are the norm the new pitch already hosts, not
an exception that grows the whole panel the moment one row wraps.

**Fonts: `TICK_FONT_PX = 13`, `GUTTER_FONT_PX = 12`.** The category tick
label (the row's own name) is now BIGGER than the figure's other chrome — an
explicit `tickfont` on the category axis, the O4 "raise the font 1–2 pt"
ask. `GUTTER_FONT_PX` moves from 11 to 12, now equal to the figure-wide
default (`FONT_PX`) — the O4 complaint "the gutter volume font size… differ
across charts" is fixed by every consumer reading the SAME shared constant,
not by tuning each chart individually.

**References: a dashed RED tick or line, never a diamond, never a
dot-and-stem.** A reference that VARIES by row (the European-mean share in
Compare's profile tab, the world PP10 reference in the impact tab) is now a
`go.Shape` vertical LINE per row — `x0 == x1` at the reference value,
`y0`/`y1` spanning exactly that row's own band (`row_index ± 0.5`) — in
`palette.WARNING_CAPTION_COLOR` (the SAME validated red `SHARED_FRONTIER`
already uses, `#821D13`; re-validated for this new role — every hue it can
now share a screen with, OA/ERC/SDG/institution marks — in
`design-system/palette_validation.txt`), `LINE_PX` (2 px), dashed. This
REPLACES the earlier `diamond-tall` `go.Scatter` marker (§10.4/
CHROME_CONTRACT.md §10.3), which the reported defect named directly: a dark
diamond barely visible against a panel already full of solid institution-
coloured bars. A reference that is CONSTANT across every row (SI/ESI = 1 in
Find's `fig_share_si`/`fig_sdg`/`fig_erc`; any single-value `REF_METRICS`
case in Compare) stays ONE rule — the SAME red, the SAME dash, spanning the
WHOLE panel (`add_vline`'s own default span) — replacing the earlier
`INK_SECONDARY` hairline (Find) / `palette.INK` dash (Compare) with one
shared "the reference is red" rule for both chart families. **Find's SI
lollipop loses its connecting STEM** (the `go.Scatter` line from the
neutral reference to each row's own dot): once the panel-wide reference is
an unmistakable red line, a per-row line connecting back to it is a
redundant second read of the same fact. The DOT itself — filled/hollow per
`si_status`, carrying its own formatted value as text — is UNCHANGED; only
the connector is retired.

**Compare's SDG chart is profile-only.** No Impact tab, no tab UI at all —
`_render_two_tab_section` gains a `tabs=False` path (the thematic-shape
section's own call site is untouched and keeps both tabs; only `_render_sdg`
passes `tabs=False`). **The SDG accent square, found and fixed.** The
taxonomy-accent mechanism (a small coloured square before a row's label,
already wired for subfields via `domain_id`, `_LEVEL_ACCENT_FAMILY`) was
silently absent for SDG rows because `_shape_long` (the frame builder both
sections share) only adds `domain_id`/`group_label` when `grouped=True` —
the SDG call (`grouped=False`) added nothing in its place, so
`fig_metric_bars`'s own accent lookup (`_ACCENT_COLS["sdg"] = ("sdg_number",
"sdg_idx")`) never found a column to key by. Fixed by a new
`accent_key_col` parameter on `_render_two_tab_section`: `_render_sdg`
passes `accent_key_col="sdg_number"`, copying that column straight through
onto the frame `two_tab_bars` draws (position-aligned, since `_shape_long`
never reorders rows) — no change to `_shape_long` itself, no change to the
already-working subfield path. **Find's SDG panel gets the identical
square** (`fig_sdg`'s new `label_accent=True`, reusing the per-row colour
`_colors_for` already computed for the bar itself) — Fields, Subfields and
ERC do not, since their bars are already coloured by the SAME family the
accent would repeat.

**Mirror_frontier converges its OWN margin and wrap onto the shared
Compare contract**, its floating-segment geometry (row 1, edge-to-edge, no
internal bargap — a different visual grammar from an isolated bar with
breathing room, deliberately unchanged) aside: `margin.l` is now
`LABEL_COL_PX["compare"]` directly (the earlier `MIRROR_MARGIN_CAP_PX`
belt-and-braces ceiling on a per-frame `_gutter_margin_px` measurement is
retired), and a topic name wraps via `charts.wrap_label_px` at
`charts.WRAP_PX["topic"]` — the SAME two-line pixel budget the rest of
Compare's bar charts use, replacing the bespoke three-line character-count
wrap (`_wrap_topic_label`/`MIRROR_LABEL_MAX_LINES`/
`MIRROR_LABEL_WRAP_WIDTH`/`MIRROR_LABEL_CHAR_BUDGET`, all retired). Row
height simplifies to `charts.row_height_single` — a CONSTANT pitch
regardless of how many lines a row's own label wraps to, since the shared
contract's "two-line labels are the norm" reasoning applies here too
(`_mirror_row_height`'s own line-count-driven formula, and
`MIRROR_THREE_LINE_FACTOR`, are retired with it). Full detail:
`CHROME_CONTRACT.md` §13 row 8.

**What is UNCHANGED.** Every builder's colours, sort order, hover fields,
empty-state rules and export columns — this is a LAYOUT contract, not a
data or encoding change; `tests/test_charts.py`/`test_charts_compare.py`'s
own goldens on those axes stay green. `fig_frontier` (a scatter, no
category axis, no gutter) and `yearly_domain_stack` (a year-axis chart, no
row-per-taxon geometry) are untouched beyond the shared `GUTTER_FONT_PX`
bump every consumer of that one constant inherits automatically.
`fig_breakdown_global`/`fig_breakdown_yearly` (Find's yearly-breakdown pair)
keep the pre-contract `row_height`/`DEFAULT_GROUP_SPAN`/`DEFAULT_GROUP_FILL`
idiom unchanged — a different section, never named by O4 or C2.

**Verification.** `tests/test_chart_layout.py` (new) checks the contract
systematically across every bar-family builder: the margin formula, tick/
gutter fonts, pitch and bar thickness derived from the rendered figure,
"no annotation ever reads 'Publications, full count'", every reference
shape's colour/dash/span, the SDG accent fix, and the label-universe wrap
(every field/subfield/ERC/SDG label ≤ 2 lines in its column, topic
ellipsis share < 1 % of 4,516) — read against the SAME committed glyph
table the constants above were derived from, so a future font or label-set
change that breaks the fixed point fails this test before it reaches a
render. Screenshots at 1920/1280/390 px (`scrollWidth ≤ innerWidth`) of
Find's ERC/Fields/Subfields/SDG panels and Compare's thematic + SDG
sections are the manager's own render-proof, per stream practice.
