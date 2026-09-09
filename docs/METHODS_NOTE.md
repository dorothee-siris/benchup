# BenchUp methods note (source text)

**This file is not rendered by the app.** The Methods page renders `lib/copy.py`'s `METHODS`
dict, whose numbers are `{placeholders}` filled at run time from the config, the manifest and
the shipped tables. This file carries the same fifteen sections with the numbers written out and
a citation per claim, so a reviewer can check what the page says without reading the data. Keep
the two in step: `tests/test_methods_note.py` fails when a `METHODS` section has no `## ` heading
here, or when a template grows a placeholder `METHODS_SOURCES` does not document.

Snapshot described here: **august_2026** (`app/data/MANIFEST.json` `snapshot`), index of **7,557**
institutions (`MANIFEST.json` `files["index.parquet"].n_rows`).

---

## What the tool is

BenchUp compares European research institutions on their published output, read from OpenAlex,
the same way for every institution in its index (`app/lib/app_config.py`, `CFG`; `app/lib/
data_cache.py`, `index`). A strategy officer can check where a competitor or a prospective
partner stands without asking them for their own numbers.

Every list and every chart the tool produces is a set of candidates for review: a lens that
places an institution close to another, or a chart that puts two institutions side by side, is a
starting point for a conversation, never a verdict (`copy.VERDICT_LINE`). The index behind every
page holds 7,557 institutions across 31 countries (`app/config.yaml` `perimeter_countries`).

## Data and windows

The snapshot behind every page is the OpenAlex harvest of `august_2026` (`app/config.yaml`
`snapshot`; `app/data/MANIFEST.json` `snapshot`). The perimeter is 31 countries: the European
Union, together with the United Kingdom, Switzerland, Norway and Iceland (`app/config.yaml`
`perimeter_countries`). An institution outside that perimeter never enters the index, though it
can still appear as a co-author on someone else's publication.

A publication counts if OpenAlex carries it as one of: articles, reviews, books, book chapters
and letters, with a DOI (`app/config.yaml` `corpus_types`, `openalex_filters`).

Two windows are in use, and every chart and card states which one it reads. Impact, star papers,
world leaders and the relationship block all read the CORE-AR window: articles and reviews only,
2020 to 2024, full counting (`app/docs/data_contract.yaml` `window_conventions.core_ar_window`).
Find's own volume charts read the whole run instead, 2020 to 2025, because a change over time
needs every year harvested; 2025 still carries its own bonus-year mark, since the harvest catches
it only partway through and it is left out of every impact figure (`app/config.yaml`
`bonus_year`).

## Counting bases, and the Compare pin

An institution is credited with a publication when the publication's own record names it
directly, never through OpenAlex's own parent-child organisation graph, which would graft a
partner's whole output onto a shared institution (SIRIS `CLAUDE.md`, OpenAlex gotchas).

Full counting credits the whole publication to every institution named on it. Fractional counting
instead splits the publication across the institutions an author declares, by that author's own
share. Neither is more correct, and the setting that governs them is stated on every page that
uses it.

Find offers both bases, plus three taxonomy trees, as sidebar toggles (`app/config.yaml`
`scenario.toggles`). Compare pins every figure to the best-fit tree and full counting instead, so
the two institutions on the page are always read the same way; the fractional count sits in the
hover wherever a Compare figure needs it (`copy.COMPARE` `PIN_CAPTION`).

## The subject taxonomy

OpenAlex files every publication under a topic, and every topic under a subfield and a field. A
measurable share of those subfield placements is wrong, so this tool ships three versions of the
tree: the original OpenAlex placement, a conservative repair, and a best-fit repair
(`app/data/topics_dim.parquet`, `original_subfield_id`/`conservative_subfield_id`/
`bestfit_subfield_id`).

The best-fit tree moves 2,601 of the taxonomy's 4,516 topics to a different subfield from
OpenAlex's own placement; the conservative tree accepts a smaller set, 955 topics, changing only
the cases with the clearest evidence (measured live off `topics_dim.parquet`,
`lib.views_methods._taxonomy_facts`).

Compare always reads the best-fit tree. Find lets a reader switch between the three, and the
choice reshapes every subfield and field figure on the page. Topic-grain figures, frontier
scores, star papers and world leaders among them, are unaffected by the choice: a topic is the
taxonomy's base unit, and a tree only decides which subfield it rolls up into.

## Two baselines, kept apart

Two impact figures sit behind the tool, and they are never averaged into one score, because they
read two different things.

FWCI_EU is a typical-level reading: the mean, across an institution's own publications, of each
publication's citations set against the average publication of the same subfield, year and
document type, computed over the tool's European baseline, the 31-country perimeter above. The
mean is the headline because it keeps the highly-cited tail a median would discard; the median of
the same distribution sits beside it wherever this tool shows the figure (`index.parquet`
`fwci_eu_mean`/`fwci_eu_median`).

PP10_WD is an excellence-tail reading instead: the share of an institution's articles and
reviews, 2020 to 2024, landing in the world top decile of citations for their own subfield, year
and document type, computed against the whole world rather than the European baseline
(`index.parquet` `pp_top10_frac`). It is the only world-referenced impact figure this tool ships:
there is no world-referenced version of FWCI here, so a reader wanting the world comparison reads
PP10_WD, and a reader wanting the European comparison reads FWCI_EU.

The two differ on two axes at once: what each one measures, a typical level against an excellence
tail, and whom each one is measured against, Europe against the world. An institution can sit
close to the European typical level on FWCI_EU and still stand out, or fail to, on the world's
own top decile.

## Frontier scores

Frontier scores read where a topic sits in world attention and where it is heading. They are
built on three-year bins of world publication volume, 2004-06 through 2019-21, plus a two-year
latest bin, 2022-23 (`topics_dim.parquet` `expansion_latest`/`acceleration_latest`). Expansion is
a position: how far the topic's world volume in the latest bin sits above or below the global
baseline, standardised across topics, so zero means the topic has expanded no more than science
as a whole over the long run. Acceleration is momentum: the topic's growth against that baseline
from 2019-21 to 2022-23, again standardised, so zero means it is moving with science as a whole,
and the frontier score weighs the two at 0.7 expansion plus 0.3 acceleration. A topic at expansion
0.01 with acceleration 0.5 therefore reads as an average long-run position that gained momentum in
2022-23. A well-established, foundational topic can carry a low score simply because the world's
attention to it is no longer expanding.

811 of the taxonomy's 4,516 topics carry no frontier score at all: catch-all topics sitting
outside the taxonomy's own subject scope, excluded by construction (`topics_dim.parquet`
`is_excluded`, verified live). Every scored topic sits in one of four quadrants, crossing the
sign of expansion against the sign of acceleration (`topics_dim.parquet` `quadrant`).

The frontier topic pool Compare measures an institution against is fixed at the global top
quarter of scored topics (`topics_dim.parquet` `top25pct_frontier`), the same pool a bold outline
marks on every frontier chart. A stricter cut of the same score, the world top 10%
(`lib.compare_data.ELITE_FRONTIER_PERCENTILE` = 0.90), sits inside that pool: it powers the
emergence selector on the topic planes and on Compare's topic overlap, and Topic planes, below,
states the cutoff score itself (`lib.topic_data.emergence_threshold()`).

## World leaders

For every topic, this tool ranks the world's publishers by output, one ranking across every
institution type (`app/data/topic_leaders.parquet`). The ranking runs up to 200 institutions
deep, articles and reviews only, 2020 to 2024, pulled live from OpenAlex on the day the leader
list was built (measured live as the maximum `rank` on the shipped table).

Ranking every institution type together favours large, multi-site research and technology
organisations by construction: a body that runs many institutes under one name accumulates more
publications than any single university, so a handful of such organisations lead
disproportionately many topics. An institution's own "topics led" figure counts the topics where
it ranks in the world top 20 of that one ranking (`app/data/topics_led.parquet`; `index.parquet`
`n_topics_led_all`); a reader comparing institutions of very different kinds should keep that
skew in mind.

## Star papers

A star paper is one of the world's most-cited works within its own topic and publication year:
the top 1% by citations, articles and reviews only, 2020 to 2024, pulled live from OpenAlex on
the day the star list was built (k = max(1, ceil(0.01 x count)) per
topic x year, sorted pull). A tie sitting exactly on the cutoff, beyond the number the cut
allows, is left out rather than included.

Star share is the size-free reading: an institution's own star-paper count divided by its own
article-and-review output over the same window (`index.parquet` `n_stars`/`star_share`). A small
institution with a handful of highly cited papers can post a very high share on a very small
base. Google (United Kingdom) illustrates the case on this snapshot, with a 20.6% star share
resting on a small output (measured live as the index row with the highest `star_share`; 42
stars over 204 articles and reviews); the raw count sits beside the share for exactly
this reason, so a high share is never read without its own denominator.

Behind every star-paper figure sits one record, `star_works.parquet` (310,327 rows, one per star
paper naming its own topic, year and every institution on it). The same record is read at
whatever perimeter a chart needs, not only an institution's own total: a topic's own bubble size
on the topic planes, an institution's own column in Compare's topic overlap table, and a pair's
own joint star-papers tile are all counted straight off it.

## Topic planes

Find places an institution's topics on two charts, side by side, sharing one perimeter: articles
and reviews, 2020 to 2024, full counting, the publication's primary topic only, regardless of the
counting basis chosen in the sidebar (that choice still reshapes the subfield and field figures
elsewhere on the page); this is `data/artefacts/inst_topic_impact.parquet`'s own perimeter
(988,587 rows, one per institution and primary topic with at least three qualifying articles and
reviews).

The first plane reads volume against impact: publications on one axis, FWCI_EU on the other, mean
by default with the same mean/median switch used everywhere else on this page, a topic's own star
papers sized as the bubble. A topic needs at least three citation-eligible articles and reviews to
be placed here at all (`lib.topic_data.PLANE_A_MIN_COVERED`); the chart's own caption counts how
many of the institution's topics fall short. The second plane reads expansion against
acceleration, the same two frontier scores defined in Frontier scores; a topic with no frontier
score at all, every catch-all topic among them, cannot be placed here and is counted instead. A
thin dark ring marks a topic where the institution ranks among the world top twenty, the same
threshold "Topics led" counts.

One selector governs both charts at once, so they always carry the same topics: top by volume,
the default; top by FWCI_EU, restricted to topics with at least ten citation-eligible articles and
reviews (`lib.topic_data.FWCI_MODE_FLOOR`); the topics the institution leads; the topics carrying
at least one star paper; or the world top decile of emergence defined in Frontier scores, a raw
frontier score of 0.360 on this snapshot (`lib.topic_data.emergence_threshold()`, measured live,
`pandas.quantile(0.9)` over the taxonomy's 3,706 scored topics), clearing for 371 of them on this
snapshot. A slider then sets how many topics show, from 10 to 100 (`lib.topic_data.N_MIN`/`N_MAX`),
50 by default (`lib.views_find.TOPIC_N_DEFAULT`). Catch-all topics are shown in a lighter tint on
the first plane, flagged in its tooltip, and left off the second entirely, since they carry no
frontier score by construction.

## Topic overlap

Compare places both institutions' topics on the same two planes Find uses, under the same
selector, applied to each institution separately and then combined: the union of each
institution's own top 50 (`lib.topic_data.PAIR_N_MAX`), so the chart never carries more than 100
topics in all. A topic held by both institutions' own top sets is drawn in one shared colour on
the chart (`lib.palette.SHARED_FRONTIER`), whichever side it came from; a topic held by one
institution only keeps that institution's own colour. The perimeter is the same as Find's topic
planes: articles and reviews, 2020 to 2024, full counting, primary topic.

A balance-bar chart carries exactly the topics on the plane, sorted by whichever metric the
selector reads; what each bar shows changes with that same selector. Top by volume draws each
institution's own publications on the topic either side, the pair's joint publications centred
between; top by FWCI_EU draws each institution's own FWCI_EU as paired bars running outward from a
shared centre, a red dashed tick at the European average (1.0) on each side; topics led draws each
institution's own world rank as its distance to the world's number one, a longer bar reading as a
better rank, with a tick at rank 20; topics with star papers draws star papers the same way volume
draws publications, joint star papers centred; and top decile of emergence draws each
institution's own change in publications between the two dynamics windows (2020-2022 against
2023-2024), a decline shown in grey. Below five joint articles and reviews
(`lib.compare_data.PAIR_QUALIFYING_FLOOR`, the same floor the relationship block uses) a topic's
own joint segment is left off rather than shown as zero, since the true count is not known
precisely enough to state (a topic can clear one institution's own top set while the other holds
fewer than three articles and reviews on it, `lib.topic_data.PLANE_A_MIN_COVERED`, the true count
then unrecoverable between zero and two).

A right-margin column beside the bars, headed "Joint pubs", gives one linked figure per topic: the
joint publication count, opening those joint articles and reviews on OpenAlex; in the star-papers
mode the same column links the pair's own joint star papers instead (their exact OpenAlex work
ids, up to 100 per topic, comfortably above the largest joint count any one topic carries), the
exact works the bar counts. Below the joint floor the column shows a dash rather than a link. The
workbook download still carries the complete topic table, every column, uncapped.

Reading the hovers: every hover line on this page and on Find's own charts names its own indicator
in bold before the value it states.

## The relationship

A pair's joint total, at the top of Compare's relationship block, counts every publication naming
both institutions directly, any document type, over the whole run (`collab_pairs.parquet`
`copubs_total`). Everything below it reads a narrower window instead: articles and reviews only,
2020 to 2024, full counting (the CORE-AR basis), the same filter carried on every link, so the
number on the page and the count the link opens on agree.

Three tiles open the block: joint publications, on that narrower window (`collab_pairs.parquet`
`core_total`); joint star papers, with a link straight to the pair's own joint articles and
reviews on OpenAlex, most cited first (`lib.leaders_data.pair_stars`, read off `star_works.
parquet`); and momentum, a glyph and a short label. Underneath the tiles, one sentence always
states the pair's own figures behind the momentum glyph (`lib.collab_data.momentum_evidence`);
Reading momentum, below, explains every state that sentence can take.

The yearly stack breaks the joint total down by year and by the four OpenAlex domains
(`collab_pair_domain_year.parquet`). A small share of joint publications, about 0.01% of joint
volume across every qualifying pair, carries no subject topic and cannot be placed in a domain;
the stack leaves them out, though the total above it still counts them (measured live: 1 minus
the sum of `collab_pair_domain_year.vol` over the sum of `collab_pairs.core_total`, restricted to
`core_total >= 5`). A topic or a field breakdown needs at least 5 shared articles and reviews to
stay meaningful (`lib.compare_data.PAIR_QUALIFYING_FLOOR`); a pair below that floor keeps its
joint total and a link to every shared publication, without the breakdown.

Reciprocity plots a pair's joint output in a field against each side's own portfolio
(`lib.collab_data.reciprocity_frame`): one axis is that field's share of one institution's own
output, the other axis is the same field's share of the other institution's own output, and the
size of the mark is the pair's joint publications in the field. A dotted diagonal marks equal
weight for both institutions; a field sitting well above or below it matters more to one side's
own portfolio than to the other's. Its tooltip carries the field's own FWCI_EU, PP10_WD and
star-paper count for the joint works alone; two different counts sit behind that FWCI figure
(`collab_pair_fields.parquet` `n_fwci`/`n_covered`): one, `n_fwci`, counts every joint work
carrying a computed FWCI; the other, `n_covered`, narrower, counts only the works eligible for
the world top-decile share (a threshold-covered, non-retracted population); on the shipped table
`n_fwci` is at least `n_covered` on every one of its 3,571,800 rows. A toggle switches the same
chart from the pair's shared fields to its top 30 subfields by joint publications instead
(`collab_pair_subfields.parquet`), at a finer grain but reading the same two axes and the same
hover.

## Reading momentum

Momentum reads whether a pair's joint output is speeding up or slowing down, on the same two
windows the evidence sentence states, 2020 to 2022 against 2023 to 2024 (`data/collab_facts.json`
`w1`/`w2`): the pair's mean annual joint articles and reviews in the later window, against the
same average in the earlier one.

A raw comparison of those two figures would read as growth for almost every pair, because joint
output is itself growing across the corpus over the same years; before anything is classified,
every eligible pair's own change is corrected against the median of that same change across every
other eligible pair (`data/collab_facts.json` `med`), so what is left over is the pair's own
change relative to how collaboration generally is moving, not corpus-wide drift dressed up as a
finding about the pair.

Seven readings cover what a corrected change can look like, matching `collab_pairs.parquet`
`mom_class`'s own seven values: up and down, a rise or a fall confirmed by a significance test at
the 5% level (`data/collab_facts.json` `alpha`); not significant (`ns`), a change large enough to
look like a rise or a fall but not confirmed by that test; stable, a corrected change small
enough, within 25% either way (`data/collab_facts.json` `band`), to be read as no real change;
weak, too little joint output in the earlier window for a rate to mean anything; new, no joint
output in the earlier window and a real amount since; and dormant, joint output in the earlier
window and none since.

The sentence under the momentum tile (`lib.collab_data.momentum_evidence`) always states the
pair's own two figures in plain counts first. Where a rate can be read at all, it adds the
corrected change and, once a significance test has run, that test's own result; a reading with no
meaningful rate (weak, new, dormant, or a corrected change with too little joint work behind it
for a test to run) states that in place of a percentage, so the sentence is never a bare,
unexplained number.

## Matching

Find compares one seed institution against the rest of the index through several independent
lenses, each reading resemblance a different way: shared fields, shared subfields, shared topics,
shared frontier topics, shared specialisations, and more (`copy.LENS_DISPLAY_CODE`/
`LENS_DISPLAY_NAMES`; ten lenses, eight shown by default and two one click away, `app/config.yaml`
`lenses`).

Every lens shows its top 50 candidates (`app/config.yaml` `depth.max`, fixed since the 30/50 depth
radio was retired); the full ranking is always computed underneath, and can be searched or
downloaded whatever the display cutoff. Concordance counts how many of the lenses defined for a
seed place a given candidate inside their own top-50 (`app/config.yaml` `concordance_N`), a
measure of how many independent readings agree rather than a score of its own: it adds no
candidate the lenses do not already find on their own.

A further tab, aspirational, answers a different question: which of a seed's own subfield-lens
candidates its own impact already exceeds.

## Scale guard

A post-filter on Find's benchmark tables, off by default (`config.yaml` `scale_guard.ratio`).
Switched on, it keeps only candidates within 3x of the seed's own size, in either direction, on
full-counted publications (`lib.filters.apply_filters`); once it is on, the active-filters line
states how many candidates it removed from the lens currently open.

The aspirational tab is exempt: it is not a size-matched candidate list to begin with, so the
guard never applies there, even when it is switched on for every other tab (`lib.views_find.
_render_aspirational`, `scale_guard: False` on that one call regardless of the sidebar setting).

## Limits

A lens places a candidate close to a seed by shared output shape. That is a resemblance signal a
reader still has to judge for a true partnership case; an institution with a genuinely different
output shape from the seed's own, a national-system peer or a mission peer among them, can go
unfound by every lens at once.

The taxonomy repair leaves gaps too: 859 of the taxonomy's 4,516 topics needed a forced or a
no-fit placement, sitting in the tree without a confident match (`topics_dim.parquet`
`fit_quality` in `{forced, no_fit}`, measured live). The type behind a company or international
co-publication share follows a small set of corrections SIRIS made to OpenAlex's own institution
type (a locked, human-adjudicated override list applied at data-build time, upstream of what
ships in `app/data/`); a type this tool has not reviewed keeps OpenAlex's own label.

The institution-by-topic table behind the topic planes and the topic overlap
(`inst_topic_impact.parquet`, 988,587 rows) carries two small, measured limits of its own, both
found while building it and both typed here as fixed facts of that build rather than recomputed
on every page load. On a reconciliation against `fwci_taxa.parquet`'s own anchor cells, 3 of 561
land one or two works away from the same cell read the other way, from re-deriving which
institutions share credit for a work straight off the raw record a second time rather than off
the frozen internal file the reconciliation target itself was built from. Separately, 115 of its
988,587 rows sit exactly one work above the same topic's own whole-run volume in
`topics_all.parquet`, concentrated in 18 topics, where a publication's own year moved by one
between the two tables' own snapshots, the ordinary kind of drift a living database produces
between two extraction dates. Both gaps are small (0.53% and 0.01% of their own populations),
one-directional and fully traced, never a broad drift.

World leaders and star papers are pulled from OpenAlex on the day they were built, a different
moment from the harvest snapshot behind every other figure on the page, so the two can drift a
little apart. OpenAlex itself keeps changing: a rerun on a later date, against a fresh OpenAlex
pull, will not reproduce this snapshot's exact counts, even from the same code (SIRIS `CLAUDE.md`,
vintage churn).

Candidates for review, not a verdict.
