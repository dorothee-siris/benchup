# BenchUp methods note (source text)

**This file is not rendered by the app.** The Methods page renders `lib/copy.py`'s `METHODS`
dict, whose numbers are `{placeholders}` filled at run time from the config, the manifest and
the shipped tables. This file carries the same eleven sections with the numbers written out and
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

FWCI_EU is a typical-level reading: the median, across an institution's own publications, of each
publication's citations set against the average publication of the same subfield, year and
document type, computed over the tool's European baseline, the 31-country perimeter above. The
mean of the same distribution sits in hover, beside the median.

PP10_WD is an excellence-tail reading instead: the share of an institution's articles and
reviews, 2020 to 2024, landing in the world top decile of citations for their own subfield, year
and document type, computed against the whole world rather than the European baseline
(`index.parquet` `pp_top10_frac`).

The two differ on two axes at once: what each one measures, a typical level against an excellence
tail, and whom each one is measured against, Europe against the world. An institution can sit
close to the European typical level on FWCI_EU and still stand out, or fail to, on the world's
own top decile.

## Frontier scores

Frontier scores read how fast world attention to a topic is moving. Expansion is a standardised
reading of how fast the world's publication volume in a topic grew over the latest period;
acceleration is a standardised reading of whether that growth is itself speeding up or slowing
down, against the period before it (`topics_dim.parquet` `expansion_latest`/`acceleration_
latest`). A well-established, foundational topic can carry a low score simply because the world's
attention to it has stopped growing.

811 of the taxonomy's 4,516 topics carry no frontier score at all: catch-all topics sitting
outside the taxonomy's own subject scope, excluded by construction (`topics_dim.parquet`
`is_excluded`, verified live). Every scored topic sits in one of four quadrants, crossing the
sign of expansion against the sign of acceleration (`topics_dim.parquet` `quadrant`).

The frontier topic pool Compare measures an institution against is fixed at the global top
quarter of scored topics (`topics_dim.parquet` `top25pct_frontier`). A further mark, a filled
diamond in the shared-frontier table, flags a topic in the global top 10% of frontier score among
every scored topic (`lib.compare_data.ELITE_FRONTIER_PERCENTILE` = 0.90), a stricter cut than the
top-quarter pool it sits inside.

## World leaders

For every topic, this tool ranks the world's publishers twice: once across every institution
type, and once restricted to universities alone (`app/data/topic_leaders.parquet`, `pool` in
`{all, education}`). Both leaderboards run up to 200 institutions deep, articles and reviews
only, 2020 to 2024, pulled live from OpenAlex on the day the leader list was built (measured live
as the maximum `rank` on the shipped table.

The two leaderboards exist because a single ranking across every institution type favours large,
multi-site research and technology organisations by construction: a body that runs many
institutes under one name accumulates more publications than any single university. An
institution's own "topics led" figure reads the fair pool for its own type: the university
leaderboard for a university, the all-institution leaderboard for everyone else (`app/data/
topics_led.parquet`; `index.parquet` `n_topics_led_fair`). Every rank shown on the page names its
own pool, so a reader never mistakes one leaderboard's tenth place for the other's.

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
stars over 204 articles and reviews, P5 finding); the raw count sits beside the share for exactly
this reason, so a high share is never read without its own denominator.

## The relationship

A pair's joint total, at the top of Compare's relationship block, counts every publication naming
both institutions directly, any document type, over the whole run (`collab_pairs.parquet`
`copubs_total`). Everything below it reads a narrower window instead: articles and reviews only,
2020 to 2024, full counting (the CORE-AR basis), the same filter carried on every link, so the
number on the page and the count the link opens on agree.

The yearly stack breaks that joint total down by year and by the four OpenAlex domains
(`collab_pair_domain_year.parquet`). A small share of joint publications, about 0.01% of joint
volume across every qualifying pair, carries no subject topic and cannot be placed in a domain;
the stack leaves them out, though the total above it still counts them (measured live: 1 minus
the sum of `collab_pair_domain_year.vol` over the sum of `collab_pairs.core_total`, restricted to
`core_total >= 5`). A topic or a field breakdown needs at least 5 shared articles and reviews to
stay meaningful (`lib.compare_data.PAIR_QUALIFYING_FLOOR`); a pair below that floor keeps its
joint total and a link to every shared publication, without the breakdown.

Momentum compares a pair's mean annual joint output over 2023 to 2024 against 2020 to 2022,
recentred against the same ratio's median across every eligible pair, so corpus-wide growth over
those years does not read as growth specific to the pair (`data/collab_facts.json` `w1`/`w2`/
`med`). A change is only shown once a significance test on the two windows' raw counts clears the
5% level (`data/collab_facts.json` `alpha`); below it, the pair reads as no significant change
rather than up or down (`collab_pairs.parquet` `mom_class`/`mom_rr`/`mom_p`).

Reciprocity reads a pair's joint output in a field against each side's own portfolio
(`lib.collab_data.reciprocity_frame`): each field carries two bars, one institution's own share
of its output sitting in that field, and the pair's joint publications in that field are shown
once, between the two bars. A field that weighs heavily for both institutions and carries many
joint publications is where the relationship matters to both sides.

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

## Limits

A lens places a candidate close to a seed by shared output shape. That is a resemblance signal a
reader still has to judge for a true partnership case; an institution with a genuinely different
output shape from the seed's own, a national-system peer or a mission peer among them, can go
unfound by every lens at once.

The taxonomy repair leaves gaps too: 859 of the taxonomy's 4,516 topics needed a forced or a
no-fit placement, sitting in the tree without a confident match (`topics_dim.parquet`
`fit_quality` in `{forced, no_fit}`, measured live). The type behind a fair pool, or a company and
international share, follows a small set of corrections SIRIS made to OpenAlex's own institution
type (a locked, human-adjudicated override list applied at data-build time, upstream of what
ships in `app/data/`); a type this tool has not reviewed keeps OpenAlex's own label.

World leaders and star papers are pulled from OpenAlex on the day they were built, a different
moment from the harvest snapshot behind every other figure on the page, so the two can drift a
little apart. OpenAlex itself keeps changing: a rerun on a later date, against a fresh OpenAlex
pull, will not reproduce this snapshot's exact counts, even from the same code (SIRIS `CLAUDE.md`,
vintage churn).

Candidates for review, not a verdict.
