# Chrome contract — BenchUp

Normative, one page. Every value below was measured on the RENDERED app (Chromium,
Playwright, `getComputedStyle`) or read off the source constant it comes from — never
guessed. Screenshots and probe logs: `evals/chrome_audit_2C_shots/`,
`evals/_probe_find.json`, `evals/_probe_all.json`. Companion document:
`evals/chrome_audit_2C.md` (the deviation audit this contract is measured against).

## 0. The best existing chart chrome, and why it is the reference

**Reference: Compare's "Compare by" sections** (`views_compare._view_subject` /
`_view_erc` / `_view_sdg`, built on `charts_compare.fig_metric_bars` +
`views_compare._metric_tip` / `_note`). Not the Find profile panels (`fig_share_si`),
which are close but older and use a plainer caption; not the Find lens tables,
which pre-date the fold pattern entirely (see audit, VF rows).

Why this one: it is the ONLY chrome unit in the app that resolves every one of the six
things the user's directive names — same formatting, same intro pattern, same
tooltip-carried methodology — in one composed sequence, and it is reused **three
times verbatim** (Subject/ERC/SDG) with zero copy-paste drift because all three call
the same four functions. It is also the newest chrome, so it is the one direction to converge the rest of the app on rather than
the reverse.

**The sequence, in argument order (pin this order for every chart/table in the app):**

1. `st.subheader` — section name (e.g. "Compare by subject").
2. Controls row, if any — drill / metric selector / sort toggle, `st.columns` on one row.
3. `_legend` — the shared chip legend (`charts.chip_legend_html`), ABOVE the chart.
4. The chart itself (`st.plotly_chart`).
5. `_note(reading, tooltip)` — **exactly one** reading line + a "?" glyph carrying the
   methodology (scenario, denominator, gutter, reference, low-volume floor, accent,
   SI floors — whichever apply). Never a stack of `st.caption` lines.
6. `_not_offered_expander` — disclosure of what this frame does NOT show and why
   (collapsed, below the note, never above the chart).
7. `_download` — one "Download the figures behind this view" button.

## 1. Page & section titles

| Element | Selector / call | Measured | Notes |
|---|---|---|---|
| Page title | `st.title` (h1) | **44px / 700**, line-height 52.8px, "Source Sans" | Identical on Find/Compare/Methods — the one title level that IS coherent app-wide. |
| Page promise line | `st.caption` under the title | 14px / 400 | e.g. "Where do these institutions differ, and by how much?" |
| Section header | `st.header` (Find "Profile", "Benchmark") | not separately measured (Streamlit h2, larger than h3) | Two per page in Find, none in Compare (it goes straight to `st.subheader`). |
| Subsection header | `st.subheader` ("Key figures, side by side", "The relationship, year by year", "L1 · Subfield overlap" gloss lines are NOT subheaders — see audit) | **28px / 600**, line-height 33.6px | This is a bare Streamlit default (`h3`), not a hand-set token. |

**Binding rule:** page title = `st.title`; every chart/table/section intro = `st.subheader`,
never `st.header` (reserve `st.header` for the two page-level divisions Find already
uses: Profile / Benchmark). No third heading level.

**Known drift, flagged not fixed here (owner PAL):** `design-system/DESIGN_TOKENS.md`
§3 declares a hand-built type scale (`text-xs 12 / text-sm 14 / text-base 16 /
text-lg 18 / text-xl 22 / text-2xl 28`). A grep of `app/lib` for `18px`, `text-lg`,
`text-xl` or any `:root`/`<style>` block returns **zero matches** — the scale is
never implemented as CSS anywhere. Every heading measured above is a bare Streamlit
default (44/28/16), not the documented tokens. The one place the token scale IS real
is `lib/tiles.py`'s `LABEL_PX=15 / VALUE_PX=22 / META_PX=12`, which
`charts_compare._card_html` explicitly imports rather than retyping ("so the two
card families cannot drift apart" — its own docstring) — cite this as the pattern to
generalise, not the header scale.

## 2. Chart chrome — fonts, marks, spacing

All from `lib/charts.py` unless noted; these are the numbers every chart/table
should share.

| Token | Value | Role |
|---|---:|---|
| `FONT_PX` | 12 | figure-wide default font (`layout.font`) |
| `GUTTER_FONT_PX` | 11 | bar text (value+gutter), tick labels, annotations — measured live: Compare's "?" glyph renders at **11px**, colour `rgb(90,95,102)` = `INK_SECONDARY`, matching exactly |
| `HAIRLINE_PX` | 1 | every hairline: bar borders, reference dashes, table hairlines |
| `MARKER_PX` / `LINE_PX` | 10 / 2 | SI dot / stem |
| `BUBBLE_MIN_PX` / `BUBBLE_MAX_PX` | 6 / 34 | frontier scatter bubble range |
| `ROW_PX` / `BASE_PX` / `MIN_HEIGHT` | 18 / 50 / 300 | `row_height(n) = max(300, 18n + 50)` |
| `BAR_GAP` | 0.25 | single-series category charts (`fig_share_si`, frontier) |
| `OUTLINE_WIDTH` | 2 (`palette.py`) | frontier flag outline; hollow/low-vol mark border |

**Known drift, flagged not fixed here (owner CHROME-F, confirm with VC before
changing either):** `DESIGN_TOKENS.md` §8.5 documents `ROW_PX/BASE_PX/MIN_HEIGHT =
22/60/300`; the live constants in `lib/charts.py` are **18/50/300**. The doc is
stale — treat the code
as the reference for the contract above.

**Bar-group spacing has two DIFFERENT constant pairs for what should be one geometry
idiom:**

| Constant pair | Value | Used by |
|---|---:|---|
| `charts.DEFAULT_GROUP_SPAN` / `DEFAULT_GROUP_FILL` | 0.80 / 0.90 | Fields/Subfields/Topics panels, yearly-breakdown pair (`_series_offset_width`) |
| `charts_compare.BAR_GROUP_SPAN` / `BAR_GROUP_FILL` | 0.82 / 0.86 | `fig_metric_bars` (Compare's Subject/ERC/SDG) |

Both feed the same `_series_offset_width` helper, so the visual effect is close but
not identical — a grouped bar in Compare sits fractionally wider/narrower than the
"same" geometry in Find's profile panels. **Owner CHROME-F to reconcile to one pair**
(see audit row VC/CHROME-F "bar-group span").

## 3. Colour, borders, grid (source: `lib/palette.py`, validated — not restated here)

| Token | Value | Role |
|---|---|---|
| `SURFACE` | `#FFFFFF` | every `paper_bgcolor`/`plot_bgcolor` |
| `INK` / `INK_SECONDARY` | `#333333` / `#5A5F66` | value text / secondary text (ticks, gutter numbers, chip labels, "?" glyphs, captions) |
| `BORDER` | `#E3E6EA` | tile/panel hairlines, "?" glyph border |
| `GRID` | `#D9DDE2` | gridlines, zero line — must recede |
| `FOCAL` / `COMPARISON` | `#0072B2` / `#8C9196` | seed institution (ranked views only) / candidate & reference marks |
| `MUTED_OPACITY` | 0.35 | catch-all-topic fill |

Four identity families (OpenAlex domain / ERC domain / SDG / document type), one per
chart, never mixed with `FOCAL` — unchanged from `VIZ_SPEC.md` §1.1, still correctly
followed everywhere audited.

## 4. Legend

- **Form:** `charts.chip_legend_html` — a row of coloured squares + label, `CHIP_PX=12`
  square, `CHIP_GAP_PX=6`, text at `GUTTER_FONT_PX` (11px).
- **Placement:** ABOVE the chart(s) it labels, never beside or below — confirmed on
  the Find breakdown pair and Compare's Subject/ERC/SDG charts, its
  domain-crossing chart and its year-by-year chart.
- **Rule:** one legend serves a whole pair/section when both panels share the same
  colour key (`showlegend=False` on every trace; the chip row is the only legend).
  Colour follows the entity, not the sort order or the rank — never repainted on
  toggle.

## 5. Hover template skeleton (`charts_compare._metric_hover`, the reference form)

Fixed line order, `<br>`-joined, each line `label + THIN_SPACE + value`:

```
{institution name}
{taxon / row label}
{metric label, lowercase}␣{value}
works␣{gutter volume} ← only if the frame carries a gutter column
index reference␣{ref value} ← only for REF_METRICS (PP, SDG-tagged share, Dynamics)
denominator␣{denom_value, formatted as a NUMBER, never a note string}
†␣few publications a year on average, read with care ← only if low-volume
```

**Binding fix already load-bearing (do not regress):** the denominator line renders
the numeric `denom_value` column, never the human-readable `denominator` note
string — the two were once conflated and produced a literal "denominator: n/a" bug
(`_metric_hover` docstring). Any new hover builder must keep this
separation.

## 6. Method-note / caption convention (`charts_compare.chart_note` / `views_compare._note`)

- **Exactly one reading line**, ≤160 characters (`NOTE_MAX_CHARS`), no line breaks
  enforced at render time (`ValueError`), not a style guideline.
- Reading line in `INK_SECONDARY`, `FONT_PX` (12px), inline with the "?" glyph.
- "?" glyph: a `1px`-bordered circle, `FONT_PX` (12px) box, `GUTTER_FONT_PX` (11px)
  text, `INK_SECONDARY` colour, `title=` attribute (native tooltip, no script)
  measured live at **11px / rgb(90,95,102)**, matches spec exactly.
- Everything the reading line does NOT say (scenario, denominator sentence, gutter
  meaning, reference identity, low-volume floor, SI floors, accent-colour meaning,
  fractional-only caveat) goes inside the "?", assembled by `_metric_tip`/`_taxon_tip`
  — never typed twice, never left as a second caption line underneath.
- **This is the pattern every chart AND every table intro should converge on.**
  Tables currently do not use it at all (see audit) — `ranked.py`/`views_find.py`'s
  lens-tab gloss+caveat is full prose above the table with no fold, by original
  design intent (`VIZ_SPEC.md` §2.4: "caveat sits directly under the gloss, never
  tooltip-only"). That intent pre-dates this pattern's own existence and now reads as the one deliberate, spec-sanctioned
  exception to this contract — CHROME-A does not overrule it, but flags the
  resulting two-system app as the single largest source of "does this chart/table
  introduce itself the same way" inconsistency a reader will notice.

## 7. D5 — new ratio-chart caption rule (nothing in the shipped app implements it yet)

Every ratio chart (Share, PP, SDG-tagged share, Dynamics, and the new FWCI tabs) gets
**one line under the title**, above the legend, stating corpus basis · floor ·
N-taxa-unscored, parametrically. Style, to sit consistently beside the existing
`_note` line:

- Normal state: `INK_SECONDARY`, `text-xs` (12px), regular weight (400) — same visual
  weight as a `chart_note` reading line, so the two read as one family of small print.
- **Warning state (taxa unscored > 0, or a floor bites): red, NOT bold, small** — D5's
  own wording. Concretely: colour = PAL's new frontier-red (D7, not yet ratified at
  time of writing — do not hand-pick a hex here), weight stays 400, size stays 12px.
  Never `**bold**` red text, never a `st.warning`/`st.error` banner (those add an
  icon+box chrome this contract does not otherwise use for a one-line caption).
- Composition order: subheader → **D5 caption** → controls row → legend → chart →
  `_note` reading+tooltip. The D5 caption is a NEW line, not a merge into `_note`'s
  single-line cap — it states a fact about the DATA (basis/floor/coverage), `_note`
  states how to READ the chart; keeping them separate avoids blowing `_note`'s
  160-character ceiling.

## 8. Tables

Reference: `lib/ranked.py:render_ranked_table` (the shared lens-table form) +
the pair-topic table.

- **Column header:** `st.dataframe` default — measured **16px / 700** (bold), `INK`.
- **Body cell:** measured **16px / 400**, `INK`. (Both are Streamlit's bare
  `st.dataframe` styling — no custom CSS anywhere overrides table typography; this
  is consistent app-wide, the one table convention that IS coherent.)
- **Progress-bar columns:** `st.column_config.ProgressColumn` — the shared idiom for
  any 0–1 score (`Score` in lens tables, `In the world top decile` / `Tagged to a
  goal` in the pair-topic table). **Binding fix required (D9, see audit):** never
  `format="percent"` (locale-dependent, confirmed rendering **comma decimals**
  live — `76,04 %` — on the very column meant to be scannable); use a printf-style
  spec on a value already scaled 0–100, or `format="%.0f%%"` after pre-multiplying
  the column, so every environment renders the same period-decimal string.
- **Link columns:** the institution NAME is the clickable OpenAlex-works link, via
  `st.column_config.LinkColumn` + the `#<urlencoded name>` fragment trick
  (`NAME_LINK_MODE="fragment"`, `ranked.py`) — this is the CANONICAL link convention.
  ~~The pair-topic table instead ships a separate trailing "Open" text-link
  column~~ **RESOLVED (VL, 2026-09-01):** the pair-topic and untapped tables
  now use the name-as-link convention; the separate "Open" column and its
  `copy.COLLAB["COL_LINK"]` key are retired. One link idiom app-wide.
- **Long-list pattern — two different, both valid, never mixed on one table:**
  - **Find lens/concordance/aspirational tables:** app-wide depth radio `{30, 50}`
    (`ctl-depth`, sidebar-adjacent controls row) + tail search + full-ranking CSV
    export. Row-count caption: *"Showing the top {N} of {M} ranked institutions
    (depth {N})"*.
  - **The pair-topic tables:** per-table `ROWS_DEFAULT = 20` + one **"Show all
    {N}"** button. Row-count
    caption: *"{n} rows shown of {N}."*
  - These are legitimately different tools for different shapes (one ranking with a
    global depth control that must stay in sync across 10 tabs, vs. one self-
    contained per-table cutoff) — the contract does not ask CHROME-F to unify the
    control, only the **caption phrasing**, which currently differs for no reason
    tied to the mechanism (see audit).

## 9. Number formats (D9, binding, printf-style, period decimal, locale-independent)

- One decimal convention app-wide: printf-style format strings (`"%.1f"`,
  `"%.2f"`), never a locale-sensitive keyword.
- `format="percent"` is BANNED. Two live call sites still use it and must be fixed:
  - `lib/ranked.py:193` (`Score` ProgressColumn) — carries a manager comment
    ("printf spec on a 0-1 score printed '1%'") that describes the workaround
    reason but the workaround itself (`format="percent"`) is exactly what D9 bans.
  - `lib/views_find.py:1476` (Aspirational tab's `L1 overlap` ProgressColumn)
    same reasoning, same fix needed.
- `views_collab.py`'s `FWCI_FORMAT = "%.2f"` is the compliant pattern to copy.
- Every percentage states its denominator in the same cell or the line directly
  above (unchanged house rule, still correctly followed everywhere audited outside
  the two `format="percent"` cells above).
- Thousands separator on every count ≥ 1,000 (confirmed consistent everywhere
  audited — e.g. "7,557 institutions").

## 10. Bar-family contract v2 — E5/E6/E8/E9

Normative source: the manager's own render review (the manager read
every PNG named below personally, E13, before ratifying — ).
Reference builder, unchanged from §0 above: `charts_compare.fig_metric_bars`.
**This is the per-chart-TYPE contract E9's propagation audit runs against for
every horizontal-bar chart** — every ratio chart in Compare (Subject/Subfield/
ERC/SDG/FWCI) already draws through this one function, so "propagate" here
means "do not build a second implementation of any of the four rows below",
not "copy code".

| # | Element | Rule |
|---|---|---|
| 1 | **Gutter column (E6)** | `gutter=True` (default): a phantom `go.Bar` trace per institution, offset into the SAME lane as its real bar, at `x = -GUTTER_NEG_AXIS_FRAC * basis * GUTTER_TIP_FRAC` (a DATA-space negative offset, never a pixel margin), text = the row's `gutter_col` value (`vol_display` by default) formatted by `charts._fmt_vol` — an integer when the value is integral, one decimal otherwise, thin-space thousands. `gutter_header` (new parameter) draws ONE small `INK_SECONDARY` label above the column, at `GUTTER_FONT_PX`, naming the basis — the caller supplies the word (VC4/VF4/VL4's job to wire), this module never invents one. |
| 2 | **Caution channel (E5)** | Every bar is SOLID, in the institution's own colour — `marker.color` and `marker.line.color` are both the SAME hex on EVERY point, `marker.line.width` is `HAIRLINE_PX` on every point, and `marker.pattern` is never set. A row `_is_low_volume` flags (E4 floor unchanged: PP/FWCI on `denom_value < palette.RATIO_HATCH_FLOOR`, every other metric on `vol_full_annual_mean < LOW_VOLUME_FLOOR`) switches BOTH its own bar-end value text AND its gutter-column text (row 1) to `palette.WARNING_CAPTION_COLOR` (`#821D13`), weight 400 (never bold), keeping `LOW_VOLUME_GLYPH` (†). The hover keeps the reason line, unchanged. |
| 3 | **Diamond reference (E8)** | Every metric in `REF_METRICS` that ships a per-row VARYING `ref_value` draws a `go.Scatter` marker per row, `symbol="diamond-tall"` (`REF_MARKER_SYMBOL`), `size=8` (`REF_MARKER_SIZE`), colour `palette.INK`, `hoverinfo="skip"`, added to the figure BEFORE the institution bar traces (so it sits behind a bar's own outside-text at the one row where the two can coincide). A CONSTANT reference (SI's neutral value, or any single-value case) stays ONE rule across the panel, `palette.INK` at `LINE_PX` (2 px), dashed — heavier and darker than the earlier `INK_SECONDARY`/`HAIRLINE_PX` dash, but still a rule, never a repeated marker. |
| 4 | **Fonts** | Unchanged from §2: `FONT_PX` (12) figure-wide, `GUTTER_FONT_PX` (11) for bar text, gutter text, gutter header and tick labels. |
| 5 | **Hover skeleton** | Unchanged from §5, with the gutter-column text change carrying no new hover line — the raw volume was already in the hover's "works" line independent of whether the gutter COLUMN is drawn, and stays there. |
| 6 | **Right-of-bar value** | Unchanged: `textposition="outside"`, `cliponaxis=False`, the value at the bar's own outer end. The earlier bar-end PARENTHESISED volume (`"{value} ({volume})"`) is RETIRED — row 1's dedicated column replaces it everywhere; a bar's own text now carries only its value (+ † when cautioned). |
| 7 | **Below ~600 px plot width** | The gutter column (row 1) has nowhere to go — WT_2D measured a wrapped first-row label alone can need the large majority of a 390 px figure's own width. Streamlit cannot read the viewport width server-side (unchanged constraint, §2.15/VIZ_SPEC's `fig_share_si`'s `stacked` argument already lives with this), so `fig_metric_bars` exposes `gutter=False` as the OFF switch and the CALLER (VC4/VF4/VL4) decides when to pass it below that breakpoint. There is never a horizontal scroll either way — the raw volume stays in hover regardless. |
| 8 | **Field accent + hover line (C2 follow-up 2, 2026-09-03, `two_tab_bars` only)** | When the caller's frame carries `domain_id`, `two_tab_bars`'s `grouped_by_field=True` (shape) call already gets a domain-coloured accent SQUARE in front of each subfield row's own label -- the EXISTING mechanism (`_accent_ticktext`, already wired for `level="subfield"`), no new drawing code, only the frame contract gaining the column. `_metric_hover` (this row's own primitive) additionally puts `"Field: {group_label}"` as the literal FIRST hover line (ahead of the institution name) whenever `group_label` is present and not null -- opportunistic, so a caller without it (SDG rows, `reciprocity_bars`) is unaffected. |

**Binding fix carried in the same round (E11, not a chrome rule but load-
bearing for row 1 above at real density):** `metric_row_height`'s fallback
branch now folds `n_wrapped` into its own per-row `need` estimate — see §12.

## 11. Dot/SI-family contract v2 — audited, confirmed

`fig_share_si` (Find's profile panels) and `fig_mirror_dots` (Compare's dot-
row mirror, where still called) are a DIFFERENT chart TYPE from row 10's bar
family — a filled/hollow DOT, not a bar — and an earlier brief asked whether any of
row 10's changes should propagate to them. Audited and judged NO on all three
counts, each for a reason specific to the dot family, not by default:

| # | Element | Ruling |
|---|---|---|
| 1 | **Below-floor marker** | STAYS a hollow dot (SURFACE fill, institution-coloured `OUTLINE_WIDTH` outline) — UNCHANGED. A filled-vs-hollow marker swap still reads as an IDENTITY (a ring in the institution's own hue), not a hole or a damaged mark, which is a different visual grammar from the diagonal `marker.pattern` texture row 10 §2 retires from bars — the two were never the same mechanism wearing different names, so retiring one does not obligate retiring the other. Plotly's own pattern fill is a Bar-family feature with no Scatter-marker equivalent in the first place (unchanged reasoning, `fig_metric_bars`'s own earlier docstring). |
| 2 | **Gutter mechanism** | STAYS folded into the row's own tick label (`charts._tick_display`) — NOT unified with row 10 §1's phantom-trace column. Different problem shape: one number per row (this chart shows ONE institution) vs up to three. WT_2D's own prior-art note: an EARLIER version of this exact gutter WAS a separate annotation in a negative-x sliver — precisely row 10 §1's refuted candidate A — and was retired because it relied on `automargin` to keep two independently-positioned text systems apart, which collided at 390 px. Re-splitting it back into a column now would reintroduce the bug its own fix already solved, for a chart that never needed the up-to-three-numbers form. |
| 3 | **Reference mark** | STAYS a dashed vertical rule at the neutral/index value, with the existing unit grid — NOT the diamond marker. Row 10 §3's diamond specifically answers "a reference next to a panel already full of solid bars, where a thin dash reads as a stray pixel"; the dot family's reference sits against a MOSTLY EMPTY panel (WT_2D claim 3's own distinction, drawn from `VIZ_SPEC.md` §5.5's original reasoning), where the same dash reads cleanly — a different situation, not an oversight. |

**Fonts, hover skeleton:** unchanged from §§2/5 for both families — the dot
family was never asked to change these, and did not.

## 12. Dynamic-viewport proof-capture rule — E11

**Binding for every proof script (this round's and future ones) that
screenshots a `.js-plotly-plot` element:** before capturing, read the chart's
own rendered height — `gd.layout.height` via `page.evaluate`, or the
element's `getBoundingClientRect.height` — and set the page's viewport to
AT LEAST that height. **Never a viewport fixed in advance.**

**Why, with evidence:** investigation root-caused an earlier "first row clipped"
symptom to `render_proof.py`'s
own `viewport={"height": 1400}`, applied to EVERY chart regardless of its own
declared height. The identical live app, identical URL, identical chart,
captured at a viewport TALLER than the chart's own `layout.height` (1700 px
vs. a declared 1513 px) renders the first row perfectly, every wait duration
tested. `gd.layout.height`, the element's `getBoundingClientRect.height`
and the SVG's own `height` attribute were all self-consistently 1513 px
throughout — the chart's internal geometry was correct; only the SCREENSHOT
HARNESS was lying about what the app renders. A 26-row × 3-series share
chart legitimately needs 1513 px (`metric_row_height(26, 3, 0)`); ANY fixed
viewport is a ticking version of the same bug for the next chart that
exceeds it, not a fix for this one instance.

`evals/ch2_2D_shots/`'s own capture script implements this rule (read the
element's bounding box, resize the viewport, THEN screenshot). I5's
inspection battery and any later grouped-bar proof script should adopt the
same pattern rather than a fixed height.

## 13. Mirror contract -- `charts_compare.mirror_frontier`

Normative source: `progress/C2.md` (this stream's own render proof, read
personally by the manager before ratifying, same E13 discipline as SS10-12
above). D5's shared-frontier chart: the app's one row-per-topic form that is
NOT a bar-family or dot-family chart -- it needs its own short contract.

| # | Element | Rule |
|---|---|---|
| 1 | **Geometry** | Three FLOATING `go.Bar` traces per row via `base=`, centred on a common zero: A-only `[-(joint/2 + a_only), -joint/2]` in institution A's colour, JOINT `[-joint/2, +joint/2]` in `palette.SHARED_FRONTIER` with `palette.FRONTIER_SHARED_HALO` as the segment's own outline, B-only `[+joint/2, +(joint/2 + b_only)]` in institution B's colour. `a_only = max(0, vol_a - vol_joint)`, `b_only = max(0, vol_b - vol_joint)` -- CLAMPED at zero (never a negative-length bar) when the pair's own counts are inconsistent; total row width = A-only + joint + B-only. |
| 2 | **Missing joint** | `vol_joint` NaN (below the P7 qualifying floor, `mirror_frontier.JOINT_FLOOR`) draws NO red segment for that row (the JOINT trace simply has no point at that row index) and the hover states the floor by name, never a silent gap. |
| 3 | **Row label = a real link** | The y-axis tick is `<a href="{url_joint}" target="_blank">{topic_name}{glyph}</a>` via plotly's tick pseudo-html (the SAME mechanism `charts._tick_display`'s `<span style>` already exploits on this pinned plotly). **Binding fact, not a guess:** plotly renders this as an SVG anchor whose link attribute is `xlink:href`, never a bare HTML `href` -- any DOM check (a test, a future probe script) must read `xlink:href` (or `getAttributeNS('http://www.w3.org/1999/xlink','href')`), and any Playwright click must pass `force=True` (Plotly's own hover-capture `div.svg-container` sits on top of the SVG and fails the default actionability check even though a real click at that point reaches the anchor and its `target="_blank"` still opens a new tab -- verified live, `progress/C2.md`). |
| 4 | **World top-decile glyph** | `is_top_decile` appends `mirror_frontier.TOP_DECILE_GLYPH` (a black diamond) to the label text -- ink, never a colour, the same "shape flag on top of an existing encoding" idiom `top25pct_frontier`'s outline uses elsewhere in the app. |
| 5 | **Axis** | Symmetric range around zero, non-negative tick VALUES on both sides (absolute counts, never a signed number -- the sign is a direction, not a magnitude), a bold black rule at zero (`_bold_axes`). |
| 6 | **Row order** | Ranked by combined volume (`vol_a + vol_b`) descending, computed by the builder itself -- `top_n` (D5: "top 20. + show all") keeps the largest `top_n` rows; `None` draws every row given. |
| 7 | **Colour family** | Institution (A/B) plus the one `SHARED_FRONTIER` exception for the joint segment -- never an OA-domain hue on this chart. The caller's legend (`legend_strip(., shared=True)`) names all three. |
| 8 | **Label wrap + margin cap (C2 follow-up 1, revised follow-up 2, 2026-09-03)** | A topic name wraps onto at most `mirror_frontier.MIRROR_LABEL_MAX_LINES` (THREE, raised from two in follow-up 2 -- real OpenAlex names run 25-60 chars and were losing their meaning at two 20-char lines) at `mirror_frontier.MIRROR_LABEL_WRAP_WIDTH` (twenty) characters per line, unchanged -- the ONE label-shortening rule in this module, because there is no Streamlit-side viewport width to condition a `gutter=False`-style per-width switch on (row 7 of SS10 does not apply here). **The ellipsis decision is keyed on the ORIGINAL name's own character count** (`mirror_frontier.MIRROR_LABEL_CHAR_BUDGET`, sixty), never on how many lines greedy wrap happens to want: a name at or under the budget that still needs a fourth line under strict word-boundary wrapping gets its overflow MERGED into the last kept line instead (never a lost character); only a name actually longer than the budget is cut, with `mirror_frontier.ELLIPSIS` marking the cut. **Binding fact, measured not estimated:** `yaxis.automargin=True` (unchanged, still on) GROWS the configured left margin past `mirror_frontier.MIRROR_MARGIN_CAP_PX` whenever the tick text still needs more room -- the wrap WIDTH and the margin CAP were tuned together against a live character-length sweep on the actual Playwright render (`progress/C2_renders/render_c2.py`), not derived from a font-metric formula. Re-verified after the three-line change: automargin's left-margin need is driven by line WIDTH (unchanged at twenty chars), never by line COUNT, so the 390 px acceptance floor (`>= 120 px` for bars) held with NO further tuning -- the two-line/forty-char fallback the follow-up 2 brief allowed for was not needed (`progress/C2.md`). A row's actual line count also drives its OWN pitch, generalised past the shared `charts.row_height`'s binary two-line-only `n_wrapped` term: `mirror_frontier._mirror_row_height(n_rows, max_lines_used)`, linearly extrapolating `WRAP_ROW_FACTOR` to three lines (still calibrated to reproduce the SAME two-line number every other wrapped chart in the app uses) -- replaces the plain `metric_row_height(n, 1, n_wrapped=.)` call follow-up 1 shipped, which under-allocated height once three-line rows existed (found on this fix's own first render, the SAME "measure the live render, do not assume" discovery pattern follow-up 1's two bugs came from). |

## 14. Yearly-domain-stack contract -- `charts_compare.yearly_domain_stack`

D7's replacement for the earlier single-series pair-pulse chart (`fig_pulse`,
deleted): joint publications per year, STACKED by the four OpenAlex domains.

| # | Element | Rule |
|---|---|---|
| 1 | **Colour family** | OpenAlex domain (`palette.OA_DOMAIN_COLORS`, `palette.OA_DOMAIN_ORDER`) -- no institution identity on this chart (D7: the joint corpus belongs to neither side, the same reasoning 's `fig_pulse` used for `JOINT_COLOR`). One `go.Bar` trace per domain PRESENT in the frame; `barmode="stack"`. |
| 2 | **Year axis** | `type="category"`, `categoryarray` = the frame's own distinct years, ascending. |
| 3 | **Year totals** | Written as text ABOVE each year's stacked bar via `add_annotation`. **Binding fix, load-bearing (do not regress):** the annotation's `x` MUST be the category's INTEGER INDEX (`enumerate(years)`), never the year's own string label -- measured live on this pinned plotly (5.24.1, `progress/C2.md`): `add_annotation(x="2020",.)` against a `type="category"` axis collapses every category into one slot and stray-positions the annotation off past the plot's right edge, a different manifestation of the same "annotation positioning is not trustworthy without an explicit numeric anchor" class of bug `_tick_display`'s own fix note already warns about for `xref="paper"`. |
| 4 | **Legend (REVISED, C2 follow-up 2026-09-03)** | `showlegend=True`, `legend.orientation="h"`, anchored just above the plot (`yanchor="bottom", y=1.0`) -- the ONE chart in this module with its OWN native Plotly legend rather than the app-wide HTML chip strip (SS4). Four unlabelled bar colours with no institution axis to caption against were unreadable on their own; `map_legend_strip(color_by="domain",.)` stays available for a caller that wants the chip-strip form elsewhere (a workbook caption), but the chart no longer depends on it to be legible. `_base_layout`'s shared `showlegend=False` default is explicitly RE-enabled after that call, for this one builder only -- every other chart in this module keeps the shared convention. |
| 5 | **No institution gutter, no diamond, no caution** | This chart carries none of the bar-family contract's row 10 devices -- there is no per-institution comparison here to gutter, benchmark or caution against. |

## 15. Reciprocity contract (C2 follow-up, 2026-09-03) -- `charts_compare.reciprocity_bars`

Reuses the bar-family primitive (`fig_metric_bars(gutter=False,.)`) for the
bars themselves, then two chart-specific additions live OUTSIDE that shared
primitive (so `two_tab_bars`'s own unchanged, accepted gutter/hover stay
exactly as SS10 already documents them):

| # | Element | Rule |
|---|---|---|
| 1 | **Gutter drawn ONCE per row, centred** | `vol_joint` is a FIELD fact (the same number on both of a row's institution bars), not an institution fact -- `fig_metric_bars`'s own per-series gutter (SS10.1) would repeat it once per lane. `reciprocity_bars` calls `fig_metric_bars(gutter=False,.)` and adds exactly ONE phantom `go.Bar` gutter trace itself (`_add_centred_gutter`), un-offset so it sits centred on the row's own category position, with the SAME `GUTTER_NEG_AXIS_FRAC`/`GUTTER_TIP_FRAC` geometry SS10.1 uses. |
| 2 | **x-axis title is explicit** | `"Joint publications as a share of each institution's own output in the field"` (`reciprocity_bars.AX_RECIPROCITY`) -- never the bare generic `Share of output` `fig_metric_bars` would otherwise print for `metric="share"`, passed in via `metric_label=`. |
| 3 | **Hover is a narrative sentence, not the generic skeleton** | `_rewrite_reciprocity_hover` REPLACES `fig_metric_bars`'s SS5 skeleton on the two real bar traces (matched by their own fill colour, deterministic via `palette.institution_color`, since trace ADD ORDER follows ascending slot, not A/B position): `"{joint} joint publications = {share} of {this_name}'s output in {field}"`, with `"; {other_name} is {this_name}'s partner #{rank} here"` appended only when the frame's OPTIONAL `rank_in_a`/`rank_in_b` columns are present AND that row's own cell is not null. |
| 4 | **Domain stays a label accent, never a mark colour** | Unchanged from the original (pre-follow-up) design: `level="field"`'s own `domain_id` accent -- bars stay institution-coloured throughout, the coexistence rule intact. |
| 5 | **Input contract is WIDE, not long (REVISED)** | One row per FIELD (`field_id, field_name, domain_id, vol_joint, share_a, share_b`, optional `rank_in_a`/`rank_in_b`) -- not one row per institution x field. `names`/`colors` are TWO-ITEM SEQUENCES `[a, b]`, the same convention `mirror_frontier` uses, since this frame carries no `institution_id` column to key a Mapping by. See `reciprocity_bars`'s own docstring for the authoritative column list. |
