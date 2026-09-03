# Tooltip specification — reading notes

`docs/tooltip_spec.yaml` is the machine-readable contract: for every chart, the ordered
fields of its hover string; for every KPI tile, the lines behind its `?`. This file says
*why* each chart carries what it carries. Where the two disagree, the YAML wins — it is
the file the tests read.

## Shared conventions

**A hover is not a data dump.** Each one carries, in this order: the entity, the channels
the eye cannot decode on its own (an axis value, a bubble size, a colour, a ring), then the
one or two figures that can change the reading, then the perimeter facts that keep the
figure honest. Anything a reader can get by looking at the chart is left out.

**Eight lines, hard.** No hover exceeds eight lines. The ten topic keywords count as two of
them, so a topic hover has six lines left for everything else. Conditional lines count in
the worst case: a line that only draws for a led catch-all topic still uses its slot in the
budget.

**The first line is the entity.** The topic, subfield, field, goal, panel, field-pair or
year the mark stands for — never the institution first. On a two-institution bar the
institution is the second line, because the reader already knows which colour they are on
and needs to know which row they landed in.

**Keywords everywhere a topic appears.** OpenAlex topic labels are not always faithful to
what the topic actually contains, so every topic hover and the topic table carry the topic's
ten keywords, laid out as two lines of five. This is the reason a topic hover budgets six
lines and not eight.

**Perimeters are named when they differ.** The app mixes windows on purpose: subject shares
run over the whole run (2020–2025, the bonus year included), volumes and co-publication
shares over the core window (2020–2024, all document types), and every impact figure over
articles and reviews 2020–2024 only. A tooltip that puts two of those on adjacent lines
names both in the labels. A ratio whose numerator and denominator come from different
windows is a bug, not a caveat.

**Floors and flags.**

| Situation | What the hover does |
|---|---|
| FWCI on fewer than 3 covered works | the FWCI line is not drawn at all |
| Any ratio resting on fewer than 10 works | the figure keeps a dagger, and the work count is shown beside it |
| A thin bar row on Compare | a closing dagger line, in the caution colour, saying it rests on few publications a year |
| Catch-all topic | the name line gains `— catch-all topic: {reason}`, matching the lighter tint of the mark |
| A pair under 5 joint publications | joint figures read `joint count not available under 5 joint publications`, never 0 |
| A topic whose plane cannot place it | it is not drawn; the caption counts how many were left out |

**Formats come from a fixed vocabulary** (top of the YAML). Three of them do real work:
`vol_pair` prints a volume on both counting bases on one line, so the reader on fractional
counting is never left guessing; `fwci_pair_2dp` prints mean, median and the number of works
behind them on one line, with the dagger inline, which is how a single line can carry a
figure and its own floor; `rank_and_leader` prints the institution's world rank when it is in
the top 20 and, either way, names the topic's leading publisher.

## Find

**Fields · Top subfields.** The bar is a share and the gutter is a volume, so the hover's job
is the third dimension: is this a field they are specialised in, and is the work cited? Both
volumes (full and fractional), the specialisation index, then FWCI_EU and the world
top-decile share on the articles-and-reviews window, whose labels say so because the share
above them is on a wider window. Subfields add the parent field on line two — a subfield name
alone is often ambiguous.

**Volume and impact (plane A).** The two axes are volume and FWCI_EU, so both are spelled out
with the exact perimeter, and the FWCI line always draws — the plane places no topic with
fewer than three covered works. The bubble is star papers and the ring is a topic led, and a
visual channel with no legend needs a hover line: both get one, the ring line naming the
topic's leading publisher so a reader can see who they are ranked against. The whole-run
volumes on both bases are there for one reason: the plane is fixed to articles and reviews
2020–2024, full counting, whatever the page's own counting toggle says, and the reader needs
their own basis back.

**Frontier (plane B).** Same topics, different question. Expansion and acceleration are the
axes; the bubble repeats plane A's volume, so the label says so explicitly rather than
letting a reader assume it is a third measure. The outline (global top quarter of emergence)
and the world rank each get a conditional line. The whole-run volumes are the line this plane
gives up to fit both of those — plane A carries them for the same topic set.

**SDG profile · ERC profile.** Share, mass and the specialisation index describe the profile;
FWCI_EU and the top-decile share say whether that part of the portfolio is cited. The share
and mass are on the whole run and the impact figures on articles and reviews 2020–2024 — the
labels carry both windows, because this is the one place where mixing them silently would
produce a ratio nobody could reconcile.

**Publication breakdown.** Three and four lines respectively. A breakdown chart's whole
content is composition, and the one thing neither bar shows is what the part is a part of, so
each hover carries the share of the total (global) or of that year (yearly). Nothing else.

## Compare

**Cards.** Every card names the European median of the same statistic in its `?`, so a value
is never read alone. FWCI_EU shows the mean on the card and puts the median, the work count
and the world top-decile share in the `?` — the mean keeps the highly-cited tail that a
median discards, and the world-referenced reading of impact is the top-decile share, not a
second FWCI.

**Thematic shape.** The Profile tab answers "how big is this subfield here", so it carries the
share, the European reference, both volumes and the specialisation index. The Impact tab
answers "is it cited", so it drops the volumes and carries the top-decile share, its world
reference, the number of articles and reviews behind it, and FWCI_EU as mean and median. The
denominator is a line of its own on the Impact tab: a share of nine works and a share of nine
hundred read identically without it.

**SDG profile.** Profile only, no tabs. The share is denominated on the whole run and the
volumes on the core window — two different windows one line apart, both named.

**Topic overlap.** One selected set of topics, three surfaces, one hover grammar. The overlay
is plane B drawn over the union of both institutions' top topics, coloured by who holds the
topic, so the hover carries the owner clause (the colour), each institution's own volume (the
bubble is their sum), and the joint volume — the number the whole section exists for. The
balance bars run on exactly that set and carry the same facts with the two frontier scores,
so a reader moving between the two surfaces reads the same lines in the same order.

**Topic table.** Not a hover: eighteen columns, capped at 200 rows with the full set in the
workbook. Its order follows the overlay's reading — what the topic is, who holds it, its
keywords, its frontier position, the three volumes, each institution's own change, world
ranks, star papers, then the three OpenAlex links. `Held by` is the column that makes a union
set readable at all.

**The relationship.** The three tiles are counts, so their `?` texts carry the window and the
one alternative figure worth knowing (all document types over the whole run, for joint
publications). The momentum tile's `?` explains the correction and the significance test; the
evidence line below it is always visible and states the two per-year means, the corrected
percentage and the test result in one sentence — five non-numeric states (new, dormant, thin
base, not significant, never co-published) each have their own one-clause wording, so the
line never falls back to a bare dash.

**Yearly stack.** Domain, year, volume, and the share of that year — a stack's segments are
composition, and the eye cannot measure a middle segment against its own bar.

**Reciprocity.** The two axes are the two shares, the bubble is the joint volume, and the
question the chart cannot answer on its own is whether that joint work is any good: FWCI_EU
mean and median of the joint papers, the joint top-decile share, and the joint star papers in
that field. The partner-rank clause draws when one institution ranks among the other's top
partners in that field. There is no FWCI at pair-and-topic grain anywhere in the app, which is
why the topic surfaces carry volumes and the field surfaces carry impact.

## What was deliberately left out

- **Star papers on the Find field and subfield panels.** The star count lives at topic grain;
  rolling it to a field would need a rollup the app does not otherwise use, and the topic
  planes already put stars on a visual channel.
- **A frontier score on plane B.** It is a composite of the two axes already plotted.
- **The quadrant name.** It is the sign of the two axis values, readable from the position.
- **A second FWCI reference.** Impact against the world is the top-decile share, everywhere.
- **Any figure at pair-and-topic grain beyond joint volume.** Nothing else exists at that
  grain, and a hover that invents one would be worse than a hover that says the floor.
