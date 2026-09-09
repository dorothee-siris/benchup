# BenchUp

BenchUp compares European research institutions on their published output, read from OpenAlex
the same way for every institution in its index. A strategy officer can check where a competitor
or a prospective partner stands without asking them for their own numbers. Every list and every
chart the tool produces is a set of candidates for review, not a verdict: a lens that places one
institution close to another, or a chart that puts two institutions side by side, is a starting
point for a conversation.

## The three pages

**Find** answers "which institutions have a research profile close to this one?" Pick a seed
institution and read who resembles it across several independent lenses (shared fields, shared
subfields, shared topics, shared frontier topics, shared specialisations, and more), with the
agreement between lenses shown rather than averaged into one score. Each lens shows its top 50
candidates, computed and searchable in full beneath that cut; the profile header carries the
institution's own key figures, including its star papers and the topics it leads. A concordance
count, alongside each candidate, states how many of the lenses defined for that seed place it in
their own top 30, a measure of how many independent readings agree, never a score of its own. A
further tab, aspirational, answers a different question: which of a seed's own subfield-lens
candidates its own impact already exceeds. A 15-sheet workbook download carries every lens and
every table on the page, the institution's own topics among them. Two toggles, taxonomy tree and
counting basis, sit beside the search box and reshape every subfield and field figure on the page;
a topic-grain figure, frontier scores, star papers and world leaders among them, is unaffected by
either, since a topic is the taxonomy's base unit and a tree only decides which subfield it rolls
up into. An institution's own topics sit on two linked charts, volume against impact and expansion
against acceleration, under one shared selector (top by volume, by FWCI_EU, topics led, topics
with star papers, or the world top decile of emergence); a thin ring marks a topic the institution
leads. A short "how to read" line sits above each of the two charts, naming what the marks and the
reference lines show for whichever mode is on screen.

**Compare** answers "where do these institutions differ, and by how much?" Put two institutions
side by side, in this order: key figures, thematic shape, SDG profile, topic overlap, and the
relationship between the two. Thematic shape carries a Profile tab (share of own output, against
the European mean) and an Impact tab (PP10_WD against the world reference); SDG is profile only,
with no Impact toggle. Topic overlap places both institutions' topics on the same frontier-style
chart Find uses, over the union of each institution's own top topics under the shared selector,
coloured by whichever institution's own set a topic came from, or by both when a topic is held by
both, with its own "how to read" line above it. A balance-bar chart sits beneath, sorted by
whichever quantity the selector reads and drawing a different pair of bars per mode: publications
either side of the joint count for "top by volume"; each institution's own FWCI_EU against the
European average for "top by FWCI_EU"; each institution's own world rank as a bar's distance to
number one for "topics led"; star papers, joint centred, for "topics with star papers"; and each
institution's own change in publications between the two dynamics windows for "top decile of
emergence". A right-margin column headed "Joint pubs" gives one linked figure per topic: the joint
publication count, opening those joint publications on OpenAlex, or, in the star-papers mode, the
pair's own joint star papers, opening exactly those works. There is no on-page table; the workbook
still carries the complete topic table, every column, uncapped. The relationship section closes on
a reciprocity chart, each institution's own share of a shared field against the pair's joint output
there, with a toggle to the same reading over the pair's own top 30 subfields by joint publications
instead. Compare pins every figure to the best-fit taxonomy and full counting, so the two
institutions on the page are always read the same way; the fractional count sits in hover, where
every line names its own indicator in bold before the value. A 6-sheet workbook and a shareable
link (`?compare=<id>,<id>`) close the page; opening an institution on Find seeds the first Compare
slot, so a reader moving from one page to the other never re-types a name.

**How it is built** (the Methods page) answers "where does each number come from, and what does
it leave out?" One section per question a reader is entitled to ask, every figure filled in at
run time from the same snapshot the other two pages read.

Ten lenses are defined, each reading resemblance a different way; eight show by default and two
sit one click away, an experimental SDG-specialisation lens among them.

| Lens | Reads | Shown by default |
|---|---|---|
| L0 · Field overlap | Shared field-level output shape | Yes |
| L1 · Subfield overlap | Shared subfield-level output shape | Yes |
| L2 · Topic overlap | Shared topics | Yes |
| L3 · Frontier-topic overlap | Shared topics inside the global frontier pool | Yes |
| L4 · Shared specialisations | Subfields both institutions specialise in, above a publication floor | Yes |
| L5 · ERC panel overlap | Shared European Research Council panel profile | Yes |
| L6 · ERC specialisation overlap | ERC panels both institutions specialise in | Yes |
| L7 · SDG profile overlap | Shared Sustainable Development Goal tagging profile | Yes |
| L8 · Core-shape overlap | Shared subfields again (L1), narrowed to the seed's own top subfields | One click away |
| L9 · SDG specialisation (experimental) | SDG goals both institutions specialise in | One click away |

## The indicators

Every figure below is read the same way for every institution in the index, and every share
names its own denominator. Full definitions, with their exact source columns, sit in `docs/
METHODS_NOTE.md` and the Methods page; this table is the one-line version.

| Indicator | What it measures | Window / basis |
|---|---|---|
| Publications | Full-counted publication count | 2020 to 2024 (fractional counting in hover) |
| Change in mean annual volume | Mean annual publications, 2023 to 2024, against the same average, 2020 to 2022 | Same window pair, own counting basis |
| FWCI_EU | Mean field-weighted citation impact: an institution's own publications against the average publication of the same subfield, year and document type, over the European baseline (median in hover). No world-referenced version of FWCI exists in this tool; PP10_WD carries the world comparison instead | Articles and reviews, 2020 to 2024 |
| PP10_WD | Share of articles and reviews landing in the world top decile of citations for their own subfield, year and document type | Articles and reviews, 2020 to 2024, against the world |
| Star papers, star share | Star papers: an institution's count of the world's most-cited works within their own topic and year (the world top 1% by citations). Star share: that count against the institution's own article-and-review output, a size-free reading | Articles and reviews, 2020 to 2024 |
| Topics led | Topics where the institution ranks in the world top twenty publishers, one ranking across every institution type; a body running many institutes under one name accumulates more publications than any single university, so a handful of such organisations lead disproportionately many topics | Articles and reviews, 2020 to 2024, world top twenty |
| Frontier share and frontier scores | Frontier share: share of output sitting in the global top quarter of frontier-scored topics. Expansion and acceleration (the two scores behind the pool) read how fast world attention to a topic is moving: expansion is a standardised reading of the topic's world publication growth over the latest period, acceleration a standardised reading of whether that growth is speeding up or slowing down. Neither measures novelty or quality, only attention | Own institution's output against the global topic pool |
| SDG-tagged share | Share of output carrying at least one Sustainable Development Goal tag | 2020 to 2024 |
| International, company co-publication | Share of eligible works with at least one co-authoring institution outside the focal institution's own country (international) or typed as a company (company) | 2020 to 2024 |
| Momentum | A pair's mean annual joint output, 2023 to 2024, against 2020 to 2022, recentred against the same ratio's median across every eligible pair, shown only once a significance test on the two windows clears the 5% level | Joint articles and reviews, 2020 to 2024 |
| Reciprocity | One bubble per shared field: its two positions are that field's share of each institution's own output, and its size is the pair's joint volume in the field; a dotted diagonal marks equal weight for both institutions | By field, both institutions' own shares; joint volume as bubble size |
| Joint star papers | Count of star papers naming both institutions directly, with a link to the OpenAlex list, most cited first | Articles and reviews, 2020 to 2024 |

Two impact figures, FWCI_EU and PP10_WD, are never averaged into one score: they read two
different things, a typical level (FWCI_EU, against Europe) and an excellence tail (PP10_WD,
against the world). An institution can sit close to the European typical level on FWCI_EU and
still stand out, or fail to, on the world's own top decile.

Star share can run high on a very small article-and-review base, so the raw count always sits
beside the share; a small institution with a handful of highly cited papers can post a very high
share on a very small base (one elite specialist lab in this snapshot posts a star share above
20% on a base of little more than 200 articles and reviews). Frontier share and frontier scores
carry a related caveat in the other direction: a well-established, foundational topic can post a
low frontier score simply because the world's attention to it has stopped growing, not because
the topic itself has stopped mattering.

## Data

The snapshot behind every page is the 27 August 2026 OpenAlex harvest, covering 7,557
institutions across 31 countries: the European Union together with the United Kingdom,
Switzerland, Norway and Iceland. World leaders and star papers are pulled separately, live from
OpenAlex, on 2026-09-03, a different moment from the harvest snapshot, so the two can drift a
little apart; the Menu page states both dates.

An institution enters the index once it holds at least 200 publications overall and at least 20
in each of the two most recent years. An institution is credited with a publication when the
publication's own record names it directly, never through OpenAlex's parent-child organisation
graph, which would graft a partner's whole output onto a shared institution. Full counting
credits the whole publication to every institution named on it; fractional counting splits it
across institutions by each author's own declared share.

OpenAlex files every publication under a topic, and every topic under a subfield and a field. A
measurable share of those subfield placements is wrong, so the index ships three versions of the
taxonomy: the original OpenAlex placement, a conservative repair that moves only the clearest
cases, and a best-fit repair that moves a wider set. Find offers both counting bases and all
three trees as toggles; Compare pins every figure to the best-fit tree and full counting, so the
two institutions on the page are always read the same way, and the fractional count sits in hover
wherever a figure needs it.

`docs/data_contract.yaml` is the one schema authority for every file `data/` ships: grain, keys,
columns, dtypes, and the denominator of every share or ratio column, checked by `ops/
contract_check.py`. `config.yaml` carries every threshold the app itself applies
at run time (lens set, depth, the specialisation floor, the scale-guard ratio), each with a
one-line comment naming why the value is what it is.

## Run locally

Any Python 3.12 works; the pins below are what this app is verified against.

```powershell
git clone https://github.com/dorothee-siris/benchup.git
cd benchup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # only needed to run tests/smoke/probe, not to run the app
streamlit run Menu.py
```

The clone already contains `data/`, ready to run: 25 declared tables plus the `data/scenarios/`
folder (the ranking engine's precomputed substrates). There is no separate data download step.
Check the data you have against the contract at any time:

```powershell
python ops/contract_check.py
```

## Tests

```powershell
pytest tests -q --ignore=tests/test_ram_budget.py
pytest tests/test_ram_budget.py -q -s   # RAM census, isolated -- run on its own, never inside a full-suite process
python tests/ui/smoke.py --port 8611    # end-to-end proof against a live server
python tests/ui/probe.py all            # every rendered value recomputed straight from the data layer
python tests/stress/run_stress.py       # permanent RAM gate: deterministic crash-path replay,
                                         # sustained concurrent sessions, a bare-process scenario
                                         # cycle; peak server RSS must stay under 1,800 MB (half
                                         # Streamlit Community Cloud's 2.7 GB container cap) and
                                         # the server must stay alive throughout
```

The reference figures the suite reproduces exactly live in `tests/golden/`; `tests/golden_ranklists_check.py`
and `tests/find_profile_identity.py` are the exact-reproduction checks against them.

Exact pytest, smoke and probe counts move as work lands; run the commands above for the live
number rather than trusting a count typed into this file.

`smoke.py` drives the live Streamlit server end to end: opening an institution, switching taxonomy
and counting basis, moving to Compare, downloading a workbook, one pass/fail line per check and a
summary count at the end. `probe.py` recomputes every rendered value straight from the data layer
(`lib/compare_data.py`, `lib/collab_data.py`, `lib/leaders_data.py`), bypassing the page entirely,
so a chart that renders without erroring but shows the wrong number is still caught. `ops/
rss_probe.py` reads the running server's own resident memory (Windows `ctypes`, no dependency);
the stress harness and `test_ram_budget.py` both build on it.

## Configuration and schema

- `config.yaml`: every threshold the app applies at run time, one key at a time, each commented.
- `docs/data_contract.yaml`: the schema authority for every file `data/` ships, validated by
  `ops/contract_check.py` and `tests/test_contract*.py`.

## Repository layout

| Path | Holds |
|---|---|
| `Menu.py`, `pages/` | The three pages: Find, Compare, How it is built |
| `lib/` | Data loaders, the ranking engine (`lib/engine/`), page logic, chart builders, workbook exports |
| `data/` | The 25 declared tables plus `data/scenarios/`, validated against `docs/data_contract.yaml` |
| `docs/` | The data contract, the design system's chrome contract and viz spec, the Methods source text |
| `config.yaml` | Every run-time threshold, one key at a time |
| `ops/` | The contract-check script and an RSS reader |
| `tests/` | Pytest suite, the Playwright smoke and probe scripts (`tests/ui/`), the memory stress harness (`tests/stress/`), fixtures and golden files |

## Deploy

Public Streamlit Community Cloud app, built from this repository, branch `master`, main file
`Menu.py`. Community Cloud builds directly from the repository's `data/`, already baked; there
is no separate data upload. A single session's steady memory footprint measures under 1 GB.
The contract check (`ops/contract_check.py`) runs before any data refresh is pushed, so a
contract violation is caught here, not on the deploy platform.

## Limits

A lens places a candidate close to a seed by shared output shape, a resemblance signal a reader
still has to judge for a true partnership case; an institution with a genuinely different output
shape from the seed's own can go unfound by every lens at once. The taxonomy repair leaves gaps
too: a measurable share of topics sit in the tree without a confident match. World leaders and
star papers are pulled from OpenAlex on their own date, separate from the harvest snapshot behind
every other figure, so the two can drift apart over time; a rerun on a later date, against a
fresh OpenAlex pull, will not reproduce this snapshot's exact counts, even from the same code.
The full account of every known limit lives on the Methods page.
