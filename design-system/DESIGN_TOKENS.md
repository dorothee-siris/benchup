# Design tokens — BenchUp

Reconciles `design-system/benchup-/MASTER.md` (ui-ux-pro-max, one `--design-system`
pass + 3 targeted `--domain ux` queries) against the SIRIS house rules and the Studio
KB (`RULES.md`, `COMPOSITION_AND_CONTROLS.md`, `LEGIBILITY_BUDGETS.md`). Where the two
conflict, **SIRIS wins** (CLAUDE.md: "these instructions OVERRIDE any default
behavior"). Charts and colour are `dataviz` + `lib/palette.py`'s job, never
ui-ux-pro-max's — its material is form inspiration only, queried, not adopted whole.

## 1. Light-only, full-width — the two non-negotiables

- `color-scheme: light` on `:root`; no `@media (prefers-color-scheme: dark)`, no
  `[data-theme="dark"]` block, anywhere in `app/`. `.streamlit/config.toml` pins
  `[theme] base = "light"`.
- No `max-width` character-measure clamp on the page body; `layout="wide"`
  (Streamlit config). Wide tables (ranked lenses, concordance matrix) own their
  scroll — `st.dataframe`'s native horizontal scroll, never a page-level one.
- Render-verify at 1920 / 1280 / 390 px before shipping.

## 2. Spacing scale (dense dashboard, 8–32 px)

One scale, multiples of 4, used everywhere a gap/padding/margin is set:

| Token | px | Use |
|---|---:|---|
| `space-1` | 4 | icon-to-label gap inside a badge/chip |
| `space-2` | 8 | table cell padding (dense rows — LEGIBILITY_BUDGETS "table rows. add search at ~50 rows"); gap between a value and its unit |
| `space-3` | 12 | gap between adjacent stat tiles in a KPI row |
| `space-4` | 16 | gap between a control row and the panel it filters; sidebar section gap |
| `space-6` | 24 | gap between the seed card and the tab strip below it |
| `space-8` | 32 | top-of-page padding under the snapshot stamp; gap between major page sections (seed card → overview → tabs) |

No token above 32 px in — this is a working dashboard, not a marketing page
(ui-ux-pro-max's persisted "Enterprise Gateway" hero-section pattern is explicitly
**rejected**, §5).

## 3. Type scale — measured, not aspirational

**2026-09-01 finding (chrome_audit_2C.md, "App-wide / Page-section headings",
owner PAL):** the hand-built CSS scale this section documented through
(`text-xs 12 / text-sm 14 / text-base 16 / text-lg 18 / text-xl 22 / text-2xl
28`) was **never implemented anywhere** — `grep -rn "18px|text-lg|text-xl|:root|<style>" app/lib`
returns zero matches. Every heading and cell the app actually renders is
Streamlit's bare default, not this table. A future editor who came here for
"the contract" would be reading a scale that describes nothing on screen — the
deviation the audit flagged. This section now leads with what the RENDERED app
measures (cross-referenced to `design-system/CHROME_CONTRACT.md`, the
render-verified, authoritative source going forward), and keeps the old
aspirational scale below for provenance only.

| Element | Measured | Weight | Source |
|---|---:|---:|---|
| Page title (`st.title`) | 44px | 700 | Streamlit default — identical across Find/Compare/Methods (`CHROME_CONTRACT.md` §1) |
| Subsection header (`st.subheader`) | 28px | 600 | Streamlit default (`h3`) — the level every chart/table section intro uses |
| Figure-wide default font (`FONT_PX`, `lib/charts.py`) | 12px | 400 | chart layout font; the D5 caption and the `_note` reading line both use this |
| Bar text / tick labels / "?" glyph (`GUTTER_FONT_PX`, `lib/charts.py`) | 11px | 400 | measured live at `rgb(90,95,102)` = `INK_SECONDARY`, matching spec exactly |
| Table header cell (`st.dataframe`) | 16px | 700 | Streamlit default — consistent app-wide |
| Table body cell (`st.dataframe`) | 16px | 400 | Streamlit default |
| KPI tile label / value / subline (`lib/tiles.py`) | 15 / 22 / 12px | — | **the one place a hand-set type scale IS real** — `LABEL_PX`/`VALUE_PX`/`META_PX`, explicitly imported by `charts_compare._card_html` "so the two card families cannot drift apart" (its own docstring). Cite THIS as the pattern to generalise, never the retired table below. |

Line-height 1.5 on all body/table text (WCAG 1.4.8 baseline) remains the binding
rule regardless of which scale is real. Numeric labels: one precision level per
measure (RULES §5), thousands separator, percentages state their denominator
inline (never a bare "24.7%" without "of 26 subfields" or equivalent alongside)
— unchanged, still correctly followed app-wide (`CHROME_CONTRACT.md` §9).

**Retired (2026-09-01) — kept for provenance only, no longer this app's contract:**

| Retired token | px | Weight | Would-have-been use |
|---|---:|---|---|
| `text-xs` | 12 | 400 | table footnotes, "Filtered by…" strip, evidence-line caveats |
| `text-sm` | 14 | 400 | table body cells, badge text, tab labels |
| `text-base` | 16 | 400 | page body copy, sidebar control labels — the "16px floor" finding itself stays a valid house rule (ui-ux-pro-max ux-guidelines.csv "Readable Font Size," Severity High) even though no CSS token enforces it today |
| `text-lg` | 18 | 600 | tab-panel section headers ("Overview", "L1 — Subfield overlap") |
| `text-xl` | 22 | 600 | seed card institution name |
| `text-2xl` | 28 | 600 | page title ("Find") |

A future editor who wants this scale to become real should add it as actual CSS
and re-run the chrome audit's font-probe script against it — not edit this table
again, which is exactly how it drifted from reality the first time.

## 4. Table density rules

- Row height: compact (`st.dataframe` default density is already close; do not
  add custom CSS padding beyond `space-2`).
- Depth default 30 rows on-screen, one click to 50 (INDICATOR_SPEC_v2 §1/§9 #1)
  — never render the full ranking inline; tail is searchable +
  downloadable (RULES §9.9 "top-N cuts amputating the tail").
- Above ~50 rows visible at once, a search/filter box is mandatory, not optional
  (LEGIBILITY_BUDGETS "Table rows. working rule: add search at ~50 rows").
- Every ranked table's score column, evidence column and type/badge column keep
  identical widths and order across all 10 lens tabs — "a reader learns each form
  once" (Lorraine VIZ_SPEC.md §3 rule 1, `same-read-same-form`).
- Wide tables (concordance rank matrix, 8+ lens columns) scroll horizontally inside
  their own container; the page body never does (SIRIS house rule; ui-ux-pro-max
  ux-guidelines.csv "Table Handling": "Use horizontal scroll. overflow-x-auto
  wrapper," Severity Medium — this is the ONE ui-ux-pro-max UX finding adopted
  verbatim, because it restates the house rule rather than conflicting with it).

## 5. Badge / chip grammar — text + glyph, never colour alone

Every badge in the app (umbrella/aggregate, type-corrected, catch-all-share,
tie-inclusive-rank, undefined-lens) follows one shape:

```
short text label [ⓘ tooltip trigger]
```

**R1 change:** the optional leading coloured dot is
GONE. removed the badge column from every table (user ruling
#8: the type post-filter covers the need), which left the
institution-type identity set with no consumer, so `lib.palette.TYPE_COLORS` and
`type_group` were DELETED — a grep before deletion found them referenced only by
`palette.py` itself, `tests/test_palette.py` and two prose lines in THIS file. No
badge in the app carries a colour any more; every one is text + an optional
tooltip trigger. Colour in R1 belongs exclusively to the four IDENTITY FAMILIES
of `VIZ_SPEC.md` §1.1 (OpenAlex domain, ERC domain, SDG, document type), one
family per chart. The five deleted hexes stay recorded in
`design-system/palette_validation.txt` run 1 and in `lib/palette.py`'s removal
note, so restoring them would need a consumer and a ledger line, not a new
validator run.

- Colour is never the only signal — RULES §4 "status: never encode good/bad as
  red/green alone" generalises here to *any* categorical fact worth flagging.
  Concretely: `type-corrected` renders as the text "type corrected by SIRIS (was:
  {type_openalex})" and `umbrella` as the text "EXPERIMENTAL" + a tooltip
  neither carries colour, and since R1 neither does anything else that calls
  itself a badge. The same principle governs the two CHART flags that replaced
  the idea of a badge hue: a catch-all (811) topic is marked by a glyph plus
  reduced fill opacity, and a top-quartile frontier topic by an ink outline
  shape and opacity on top of the family colour, never a new hue.
- **Never both an umbrella badge and a type-corrected badge on one row**.
- A badge's tooltip carries the evidence (median compared against, "was:" value,
  catch-all share number) — RULES §6 "tooltips repeat labels and expose
  provenance/detail; they never carry information essential to the static read"
  — so the badge's own visible text must stand alone without the hover.

## 5b. tokens

Three new `lib/palette.py` exports, contracted by name for the streams that
consume them (VC, CD5) — do not rename on a future edit without updating both
sides.

| Export | Value | Role |
|---|---|---|
| `palette.SHARED_FRONTIER` | `#821D13` | **D7 ratified.** Retires old `#7A1600` (2026-09-01) — full validator pass, no exception needed: vs vermillion 22.8/23.0 (normal/deutan), vs navy trio min 20.5/16.0, contrast on white 9.84:1. See `palette.py`'s own provenance comment and `palette_validation.txt` run 37 for every number, the two rejected candidates, and the disclosed residual below. |
| `palette.FRONTIER_SHARED_HALO` | `{"color": SURFACE, "width": 1.5}` | The non-colour differentiator on a "held by more than one institution" mark — a white/`SURFACE` outline ring, shaped as a Plotly `marker.line` dict so VC can drop it straight into the frontier scatter's marker spec. Exists because D7's own re-measurement found the residual below has no colour-only fix. |
| `palette.WARNING_CAPTION_COLOR` | `= SHARED_FRONTIER` (by reference, not a second literal) | D5's ratio-chart warning-caption colour (CHROME_CONTRACT.md §7): red, **not bold**, 12px (`FONT_PX`), same visual weight as an ordinary `_note` reading line. Composition (never bold, never a `st.warning` banner) is the caller's job — this file exports only the hex. |
| `palette.RATIO_HATCH_FLOOR` | `50` | **D6 AMENDED.** One user-facing sentence — "a bar hatches when it rests on fewer than 50 works over 2020–2024" — two implementations: PP and FWCI charts hatch a ROW when its own `denom_value < 50` (per-row, varies bar to bar); Share/SI/SDG-share/ERC/Dynamics charts keep their existing `vol_full_annual_mean < 10/yr` numerator trigger, because THEIR `denom_value` is the institution's constant total, not a per-row count, and applying the floor to that column would silently disable hatching (WT_2C.md claim 4: share denominators measured at 400–1,200, never below 50). |

**D7 residual, disclosed rather than hidden (do not let a future edit drop
this):** `#821D13` clears every ΔE check with margin, but the luminance/contrast
separation from navy slot 2 barely moves and is marginally WORSE than the old
colour (1.75:1 vs 1.93:1) — the whole gain is a modest lightness lift capped by
a hard deutan-vs-navy floor (any candidate at L≥0.50 fails that floor outright,
measured). If the user's original complaint is really about two dark marks
reading as "similarly dark blobs" (a luminance problem) rather than about hue,
no ΔE-passing red fully solves it alone — `FRONTIER_SHARED_HALO` is the
compensating SHAPE signal for exactly that gap.

## 6. Reconciliation vs `design-system/benchup-/MASTER.md`

The ui-ux-pro-max pass returned a **B2B-SaaS marketing-adjacent "Enterprise
Gateway" pattern** paired with a **"Data-Dense Dashboard" style** at density 8/10.
The style card is useful form guidance; the pattern card and its own palette are
not this app's shape at all (BenchUp's Find tab has one page, no marketing
funnel). Kept vs. rejected, explicitly:

### Kept (form/structure guidance only, no colour adopted)
- **Density profile** ("multiple charts/widgets, data tables, KPI cards, minimal
  padding, grid layout, space-efficient, maximum data visibility") — matches
  the Find-tab journey (seed card → concordance → 10 lens tabs →
  aspirational) and is the basis for the spacing scale in §2.
- **"Fira Code / Fira Sans" typography pairing's mood** ("dashboard, data,
  analytics. precise") as a *directional* cue only — BenchUp does not adopt
  a custom webfont (see rejection below); the mood confirms text-forward, low-
  ornament styling is right for this app.
- **Pre-delivery checklist items that restate house/accessibility rules already
  in force:** no emoji-as-icon, visible focus states, 4.5:1 text contrast,
  `prefers-reduced-motion` respected, responsive breakpoints tested. These are
  kept because they are true regardless of source, not because ui-ux-pro-max is
  the authority on them.
- **ux-guidelines.csv "Table Handling" (overflow-x-auto)** — restates the SIRIS
  house rule verbatim; adopted as confirmation, not as new guidance.
- **ux-guidelines.csv "Readable Font Size" (16px floor)** — adopted app-wide per §3.
- **ux-guidelines.csv "Active State" (current nav/tab visually indicated,
  `border-b-2` underline pattern)** — Streamlit's native `st.tabs` already does
  this; noted so a future custom tab component does not regress it.

### Rejected from ui-ux-pro-max (explicit, per brief)
1. **The entire "Enterprise Gateway" pattern** (hero video/mission, mega menu,
   client-logo carousel, "Contact Sales" CTA, path-selection landing) — this is a
   marketing-site pattern; BenchUp's Menu page is a nav-card grid to two
   internal tools, not a conversion funnel. No hero, no video, no CTA button, no
   logo carousel.
2. **The persisted colour palette in full** (`#1E40AF` primary, `#3B82F6`
   secondary, `#D97706` accent, `#DC2626` destructive, etc.) — SIRIS colour comes
   exclusively from `lib/palette.py`, validated by the `dataviz` skill's
   CVD/contrast script, not from a generic B2B palette that was never run through
   that validator. None of these hexes appear anywhere in `app/`.
3. **Dark-mode support** ("Light supported / Dark supported") — SIRIS house rule
   is light-only, always; the dark branch is never built, not even as a stub.
4. **"Fira Code / Fira Sans" as an actual webfont import** — no custom Google
   Fonts import ships in. The *mood* is kept
   (§ above), the font family itself is not.
5. **"Hover tooltips, chart zoom on click, row highlighting on hover, smooth
   filter animations, data loading spinners"** as a bundled "Key Effects" list
   BenchUp keeps hover tooltips (RULES §6/§7) but explicitly has **no motion**
   (SIRIS house rule: "no motion") — no chart zoom, no smooth animation, no
   spinner choreography beyond Streamlit's own built-in (unstyled) loading state.
6. **`ux-guidelines.csv` "Active States" (`active:scale-95` press feedback)**
   a scale-transform micro-interaction is motion; rejected under the same
   no-motion house rule, even though the category ("show feedback on
   interaction") is legitimate — Streamlit's native button/widget states already
   provide non-animated feedback (colour/border change only).
7. **`ux-guidelines.csv` "Excessive Motion" card's own remedy** ("Animate 1-2 key
   elements per view maximum") — BenchUp's remedy is stricter: zero animated
   elements, not one or two. The finding's diagnostic value (too much motion is
   bad) is kept as directional confirmation of the house rule; its suggested
   *floor* of 1–2 animations is rejected as still too much for this app.

## 7. `<slug>` for the record

`design-system/benchup-/MASTER.md` — persisted 2026-08-29, density 8/10,
category "Analytics Dashboard", query "peer benchmarking analytics dashboard
higher education research" (`--design-system` mode) + 3 targeted `--domain ux`
queries ("ranked table dense rows readable", "active filters disclosure strip",
"tab navigation many tabs").

## 8. R1 addendum — the profile section

Refinement R1 adds a chart-heavy profile section (VIZ_SPEC §1.9, §2.10–§2.20).
Two sources were consulted for it, in the house order: `dataviz` first and
binding (form heuristic, colour formula, the runnable validator, mark specs),
then ONE `ui-ux-pro-max` pass for a FORM second opinion only. **SIRIS wins every
conflict, and no colour of any kind was taken from ui-ux-pro-max** — the four
identity families come from `lib/palette.py`, validated by the dataviz script.

### 8.1 Colour: four identity families, one per chart

See `VIZ_SPEC.md` §1.1 and `lib/palette.py` for the values, the validator runs
and the rejected candidates. The token-level consequences for this file:

| Token | Value | Role |
|---|---|---|
| `SURFACE` | `#FFFFFF` | every figure's `paper_bgcolor` + `plot_bgcolor`; also the `--surface` of every R1 validator run |
| `INK_SECONDARY` | `#5A5F66` | KPI-tile sublines, volume-gutter numbers, chip labels, axis ticks, chart annotations (6.43:1 on white — above the body-text floor) |
| `BORDER` | `#E3E6EA` | tile/panel hairlines, the gutter's zero baseline |
| `GRID` | `#D9DDE2` | gridlines and zero lines — must RECEDE; the low contrast is the requirement, not the defect |
| `MUTED_OPACITY` | `0.35` | fill opacity of a flagged-but-included mark (catch-all topics) — a transparency, never a hue |
| `OUTLINE_WIDTH` | `2` | ink outline on a top-quartile frontier topic — the dataviz "surface ring on overlapping marks" spacer, used as a flag |

All three chrome tokens are EXCLUDED from categorical validation by design;
`palette_validation.txt` run 8 reproduces the expected FAIL for exactly these
hexes before they were locked in, the same way run 2 did for COMPARISON /
NEUTRAL / INK.

### 8.2 `dataviz` findings applied (binding)

- **Colour last, and computed.** Every family was run through
  `scripts/validate_palette.js --mode light --surface "#FFFFFF" --pairs all`
  (runs 3–8), `--pairs all` rather than `adjacent` because a sort toggle can put
  any two categories side by side.
- **Never a dual axis.** This is why A/B #3's rival had to be built as a
  single-axis expected-share tick rather than "SI on a second x-scale": the
  literal reading of the brief would have been the skill's #1 anti-pattern.
- **Colour follows the entity, never its rank.** The sort toggle re-orders rows
  and repaints nothing; `tests/test_charts.py` pins it.
- **Selective direct labels, never a number on every point.** Applied to the
  yearly global breakdown (one label per bar, the bar's own value) and NOT to the
  frontier scatter (hover only).
- **Legend always present for ≥ 2 series.** The breakdown pair carries one shared
  chip legend for two figures; the single-series panels carry none, their axis
  names them.
- **Recessive grid/axes; text wears text tokens.** `GRID` for lines,
  `INK`/`INK_SECONDARY` for every number and label — a value never wears its
  series colour.
- **Step 7, render it and look at it.** Eight PNGs at 1280 and 390 px, read
  visually, not inferred from the code (`design-system/ab/`).

### 8.3 `ui-ux-pro-max` R1 pass — kept

Queries: `--domain chart "horizontal bar chart ranking comparison scatter bubble"`,
`--domain ux "expander collapsible panel KPI card scatter plot legend placement"`,
`--domain ux "progressive disclosure accordion"`.

- **`charts.csv` "Compare Categories" volume thresholds** — "<20 categories:
  vertical bar; 20–50: horizontal bar; >50: paginated table". Adopted as
  confirmation: fields (25), ERC panels (28) and the top-subfield/topic cuts
  (20) all sit in the horizontal-bar band, which is the form the panels use.
- **`charts.csv` accessibility note** — "never encode category solely by bar
  colour; use direct category/value labels". Restates the house rule and is the
  documented structural relief for the fixed UN SDG palette (VIZ_SPEC §1.1
  family 3), so it is kept as an independent corroboration of a rule we already
  had rather than as new guidance.
- **`charts.csv` "Correlation / Distribution" fit for the frontier panel**
  scatter/bubble is the right form for two continuous variables with clusters and
  outliers, and its own "when NOT to use" list (categorical variables, fewer than
  ~20 points, mobile-primary) does not describe this panel. Kept as a check that
  the form choice was not merely inherited from BenchUp V1.
- **`charts.csv` A11y fallback pattern** — "visible data table plus summary".
  Already satisfied: every panel's numbers ship as CSV and its caption states the
  reading (VIZ_SPEC §1.7, and no panel is a PNG-only artefact).

### 8.4 `ui-ux-pro-max` R1 pass — rejected (explicit)

1. **"Colour axis: gradient (blue → red)" for the scatter** — rejected. That is a
   sequential ramp for a third continuous variable; the frontier scatter's colour
   is a CATEGORICAL family (domain), and a blue→red ramp would additionally read
   as good→bad on a panel whose whole caveat is that it measures attention
   dynamics, not quality.
2. **"Opacity 0.6–0.8 to show density" on the scatter** — rejected. Opacity is
   already load-bearing in this app as the catch-all flag (`MUTED_OPACITY`); a
   blanket density opacity would make every mark look flagged. Overlap is handled
   instead by a bounded bubble-size range and the `SURFACE` ring on each marker,
   which is the dataviz mark spec for overlapping marks.
3. **"Always sort descending by value"** — rejected as an absolute. Every panel
   ships a sort TOGGLE, because for the ERC panels and the SDG goals the taxonomy
   order IS the read (a canonical sequence the reader navigates by position);
   value-descending is the default, not the only option.
4. **`ux-guidelines.csv` "Error Placement" (the only ux hit for the panel query)**
   — not applicable: the profile section has no form inputs. Recorded so the
   thin ux return is visible rather than dressed up.
5. **The persisted "Enterprise Gateway" pattern and its palette** — already
   rejected in §6 and re-rejected here; nothing about a chart-heavy profile
   section changes that verdict.
6. **The KB's stack CSVs generally** — 22 stacks, none of them Streamlit, and
   none of its component code is transferable to `st.expander` /
   `st.segmented_control` / `st.plotly_chart`. Form vocabulary only, as the house
   rule says.

### 8.5 New numeric tokens (chart geometry, `lib/charts.py`)

These live as int/float constants in `lib/charts.py`, never inside a string
the digit-ban makes that a mechanical requirement, not a style preference.

| Token | Value | Use |
|---|---:|---|
| `ROW_PX` / `BASE_PX` / `MIN_HEIGHT` | 22 / 60 / 300 | `row_height(n) = max(300, 22n + 60)` — the one height idiom for every category chart |
| `GUTTER_FRACTION` / `GUTTER_INSET` | 0.16 / 0.06 | the left volume gutter (A/B #4 winner) as a fraction of the x range |
| `MARKER_PX` / `LINE_PX` / `HAIRLINE_PX` | 10 / 2 / 1 | SI dot, SI stem and every hairline — thin marks, per the dataviz mark specs |
| `BUBBLE_MIN_PX` / `BUBBLE_MAX_PX` | 6 / 34 | frontier bubble range (area ∝ mass via a sqrt scale) |
| `DEFAULT_GROUP_SPAN` / `DEFAULT_GROUP_FILL` | 0.8 / 0.9 | Lorraine's grouped-bar geometry, verbatim — `offsetgroup` is broken on plotly 5.24.1 |
| `SHARE_DECIMALS` / `SI_DECIMALS` | 1 / 2 | one precision level per measure (RULES §5); number formats are composed from these |
