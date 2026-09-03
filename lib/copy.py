"""
app/lib/copy.py -- every user-facing string in the Find tab.

RULE: no digit character appears anywhere in a string constant below
except inside a lens code or the literal "top10" / "PP(top10%)". Every other number a caption needs
(a count,
a threshold, a share, a median) is a `{named}` format placeholder the CALLER
fills from CFG or the live data -- never typed here. `scan_for_digit_violations`
at the bottom is the self-check; `tests/test_badges.py` runs it.

VOICE (R2-C, `siris-voice-en`): no em dash and no "--" standing in for one
inside a user-facing string; a comma, a colon or parentheses instead. Plain
words over jargon, because the reader is a strategy officer meeting OpenAlex
for the first time: "histogram intersection", "excess-SI vector" and "HHI"
do not appear in UI copy. Every figure is followed by its reading.
"""
from __future__ import annotations

import re

# ------------------------------------------------- scenario display labels
# R2 / L29: the sidebar shows a label, the app keeps the internal value. E3
# passes these dicts to `format_func`; the KEYS are the contract and never
# change.

TREE_LABELS = {
    "bestfit": "Repaired taxonomy (best fit, default)",
    "conservative": "Repaired taxonomy (conservative)",
    "original": "OpenAlex taxonomy as published",
}

BASIS_LABELS = {
    "frac": "Fractional counting",
    "full": "Full counting",
}

# ---------------------------------------------------------- lens naming -----
# R2 / L29: the code stays the identifier (Overview chips, evidence column,
# CSV export), the name says what the lens looks at. Tabs carry these labels.


# One plain sentence per lens: what "similar" means here, and what the lens
# reads well or badly. Source: INDICATOR_SPEC_v2.md S1. No placeholder, on
# purpose, so the caller renders the sentence as it stands.
LENS_INTRO = {
    "L0": "Similar means the two institutions divide their publications across the broad fields in "
          "much the same proportions; it finds look-alikes quickly, and returns generic matches when "
          "a profile is narrow.",
    "L1": "Similar means the same subfields in the same proportions, one level finer than fields; "
          "this is the reference view of the set, and it stays readable deep into the ranking.",
    "L3": "Similar means the same topics, the finest grain the index carries; it recovers more known "
          "peers than the coarser views, and candidates from the seed's own country come up often.",
    "F1": "Similar means shared presence in the topics the world is currently expanding into, so the "
          "list leans towards where attention is moving; Social Sciences and Humanities profiles are "
          "under-represented.",
    "L2f": "Similar means specialised in the same subfields relative to the average institution, "
           "counting only subfields where both publish enough to judge; it reads well for concentrated "
           "mid-size institutions, and poorly for very diffuse or very thin ones.",
    "L4": "Similar means the same distribution across the ERC evaluation panels, the categories the "
          "European Research Council uses to sort proposals; companies and government bodies "
          "occasionally appear in the list.",
    "L5": "Similar means specialised in the same ERC panels relative to the average; it surfaces peers "
          "the other views miss, with thinner outside corroboration than they have.",
    "L6": "Similar means the same profile of SDG-tagged output across the goals; its candidates come "
          "from other countries readily, so the list is not simply an effect of shared country.",
    "C1": "Similar means the same subfields as L1, with the comparison narrowed to the seed's own "
          "strongest subfields, so it reads the core rather than the whole profile; noise grows "
          "quickly past the first ranks.",
    "L7": "Similar means over-represented in the same SDGs relative to the average; the view is "
          "experimental and most of what it returns is noise, with the occasional peer nothing else "
          "finds.",
}

# R2 / L29: the reader-facing reason a lens has nothing to show
# for this seed. `lib/engine/lenses.py` produces its own diagnostic string
# ("seed's excess-SI vector is empty under candidate (f), papers>=30
# (n_eligible_cells=0)") which is a debugging artefact, not copy: it names
# internal structures and types digits this file bans everywhere else. The
# engine keeps it for its own log; the page renders the sentence below.
LENS_UNDEFINED_REASON = {
    "L0": "none of the seed's publications could be placed in a field, so there is no field profile "
          "to compare",
    "L1": "none of the seed's publications could be placed in a subfield, so there is no subfield "
          "profile to compare",
    "L3": "none of the seed's publications could be placed in a topic, so there is no topic profile "
          "to compare",
    "F1": "the seed holds no publications in the topics the world is currently expanding into",
    "L2f": "the seed has no subfield where it publishes enough for a specialisation to be measured",
    "L4": "none of the seed's publications could be placed in an ERC evaluation panel",
    "L5": "the seed has no ERC panel where it publishes enough for a specialisation to be measured",
    "L6": "none of the seed's publications carries an SDG tag, so there is no goal profile to compare",
    "C1": "the seed has no strongest subfields to narrow the comparison to",
    "L7": "the seed has no goal where it publishes enough for a specialisation to be measured",
}

# --------------------------------------------------------- lens glosses -----
# Source: VIZ_SPEC.md S2.4 / INDICATOR_SPEC_v2.md S1, every digit replaced by
# a named placeholder the caller fills from CFG/data. The placeholders these
# two dicts may use are exactly the six keys `_gloss_values` builds in
# views_find.py: n_fields, n_named_lenses, n_default_lenses, floor_papers,
# core_top_n, depth_max.

LENS_GLOSS = {
    "L0": "Overlap of the publication shares held across the {n_fields} OpenAlex fields, the coarsest "
          "view of a profile",
    "L1": "Overlap of the publication shares held across subfields, the anchor view",
    "L3": "Overlap of the publication shares held across topics, the finest grain the index carries",
    "F1": "Topic overlap restricted to the topics the world is currently expanding into",
    "L2f": "Overlap of specialisations across subfields, counting only cells that hold at least "
           "{floor_papers} papers",
    "L4": "Overlap of the publication shares held across the ERC evaluation panels",
    "L5": "Overlap of specialisations across the ERC evaluation panels",
    "L6": "Overlap of the shares of SDG-tagged output across the goals",
    "C1": "L1 again, with the comparison restricted to the seed's own top-{core_top_n} subfields",
    "L7": "Overlap of specialisations across the SDGs, an experimental view",
}

LENS_CAVEAT = {
    "L0": "Reads as a generic look-alike list when the seed has a narrow profile, and brings in more "
          "non-university rows than the finer views.",
    "L1": "Steady to read down to rank {depth_max}.",
    "L3": "Candidates cluster in the seed's own country more than on the other default views, so the "
          "country filter is worth a look here in particular.",
    "F1": "Under-represents Social Sciences and Humanities profiles.",
    "L2f": "The failure axis is a diffuse profile rather than institution size: it reads well for "
           "concentrated mid-size institutions, poorly for very diffuse or very thin ones.",
    "L4": "Companies and government bodies occasionally leak into the candidate set.",
    "L5": "Kept because it surfaced peers no other view found, with less outside corroboration than "
          "the other defaults; read its candidates with that in mind.",
    "L6": "Country clustering is modest here, so the list does not simply reflect a shared country.",
    "C1": "A refinement of L1 rather than a view of its own; noise grows faster than L1's past rank "
          "{core_top_n}.",
    "L7": "Mostly noise, with the occasional peer no other view surfaces.",
}

# ------------------------------------------------------------ toggles -------

L7_TOGGLE_LABEL = ("Show the experimental SDG-specialisation view (mostly noise, with the occasional "
                   "peer no other lens finds)")
C1_TOGGLE_LABEL = "Restrict to my core subfields"
VERDICT_LINE = "Candidates for review, not a verdict."

# ------------------------------------------------------------ tooltips ------

L3_COUNTRY_TOOLTIP = ("Of this lens's top candidates, {share} share the seed's country, the highest "
                      "figure among the default lenses; the country filter is worth a look here in "
                      "particular.")
UMBRELLA_BADGE_LABEL = "umbrella / aggregate (EXPERIMENTAL)"
UMBRELLA_TOOLTIP = ("EXPERIMENTAL: this institution publishes far more than the {median} median for "
                    "its country and type, which usually means the record covers a group of "
                    "institutions rather than one. The list of known umbrellas is not exhaustive.")

# --------------------------------------------------------------- strip ------

STRIP_PREFIX = "Filtered by: "
STRIP_JOIN = " · "  # middle dot, VIZ_SPEC S1.4's own separator
STRIP_TREE = "taxonomy: {tree}"
STRIP_BASIS_FULL = "full counting (the ERC and SDG lenses stay fractional)"
STRIP_DEPTH = "depth = {depth} rows shown per lens"
STRIP_C1_ON = "core-shape restriction on (L1 limited to the seed's own core subfields)"
STRIP_L7_ON = "experimental SDG-specialisation view on"
STRIP_TYPE = "type: {types}"
STRIP_COUNTRY = "country: {countries}"
STRIP_EXCLUDE_OWN_COUNTRY = "the seed's own country excluded"
STRIP_SIZE_RANGE = "size between {lo}-{hi} publications"
STRIP_SCALE_GUARD = "scale guard on"
STRIP_FAMILY = "family filter on (L0 field overlap at or above {threshold})"

# --------------------------------------------------------- empty states -----

EMPTY_STATE_JOIN = " and "
NO_ACTIVE_FILTER_LABEL = "the active filters"
EMPTY_STATE_TEMPLATE = ("No candidate matches {filters} for {seed}. Remove a filter, or show more rows "
                        "per lens.")
UNDEFINED_LENS_TEMPLATE = "{lens} cannot be computed for this seed: {reason}."

# ----------------------------------------------------------- depth/export ---

# U4 / PRESS-A: E7 retires
# the per-lens CSV this line used to point at (".or download the full
# ranking"), in favour of the ONE all-lens workbook at the end of the page
# rewritten so the sentence still points at something real. `EXPORT_BUTTON_
# LABEL` (the retired per-lens/per-tab CSV button's own label) is DELETED
# outright rather than left for a future sweep: this stream is the one that
# orphaned it, and grep confirms zero remaining callers anywhere in the app.
DEPTH_CAPTION_TEMPLATE = ("showing the top {n} of {m} ranked candidates; search the tail below, or "
                          "download every lens as one workbook at the end of the page")
TAIL_SEARCH_EMPTY_TEMPLATE = "'{query}' does not appear anywhere in this lens's ranking for this seed."
# ADD_COMPARATOR_HELP DELETED (TEV-U wave 3 deletion ledger, SEL's own
# flag): the old per-page "add a comparator by name" flow this help text
# belonged to is gone (superseded by `selection.render_sidebar`'s shared
# search); confirmed zero usage by grep across lib/ and tests/.

# ---- Find page ----

FIND = {
    # ---- sidebar: counting and taxonomy (R2 / L29) -----------------------
    "SCENARIO_HEADER": "Counting & taxonomy",
    "TREE_LABEL": "Subject taxonomy",
    "TREE_HELP": ("OpenAlex files every publication under a topic, and every topic under a subfield "
                  "and a field; a measurable share of those subfield placements is wrong, and the two "
                  "repaired versions of the taxonomy correct them, the best-fit one more thoroughly "
                  "than the conservative one. Changing this setting moves publications between "
                  "subfields and fields, so the profile charts and the subfield lenses (L0, L1, L2f, "
                  "C1) shift with it, while the topic, ERC and SDG views stay as they are."),
    "BASIS_LABEL": "Counting basis",
    "BASIS_HELP": ("Fractional counting credits an institution the author share it holds on a "
                   "publication, so a paper written with many partners counts for a fraction; full "
                   "counting credits the whole publication to every institution named on it, which "
                   "raises the totals of institutions that co-publish widely. The ERC and SDG lenses "
                   "(L4, L5, L6, L7) are fractional-only and do not change with this setting."),
    "FILTERS_HELP": "Applied after ranking: they remove rows, they never change a rank.",
    "TYPE_LABEL": "Institution type",
    "COUNTRY_LABEL": "Country",
    "EXCLUDE_OWN_LABEL": "Exclude the seed's own country",
    "SIZE_LABEL": "Size range (full counting)",
    "SCALE_GUARD_LABEL": "Scale guard (comparable size band)",
    "SCALE_GUARD_HELP": ("Keeps candidates within a size ratio of the seed; the ratio is banded "
                         "by the seed's own size."),
    "FAMILY_LABEL": "Family filter (field overlap)",
    "FAMILY_HELP": "Keeps candidates whose L0 field overlap with the seed is at or above {threshold}.",
    # ---- the two independent-slot pickers Find and Compare both use
    # (lib.selection.render_slots): one search box per slot, no shared list.
    "SLOT_EMPTY_LABEL": "Empty slot",
    "SLOT_LABEL": "Slot {n}",
    "PAGE_TITLE": "Find",
    "PAGE_INTRO": "Add institutions in the sidebar, then read who resembles the one you profile, across independent lenses.",
    #  / A14: the verbose "Snapshot: <label> (generated <timestamp>)"
    # stamp is GONE from every page. The key and its four call-site keywords
    # (`snapshot`, `generated_at`, `n_institutions`, `sep`) are kept exactly as
    # they were -- `str.format` ignores the keywords a template stops using
    # so every caller (Find, Compare, Methods) drops the string without any
    # of their files being edited. Find and Menu use the richer
    # DATA_CAPTION below; the Methods page keeps its factual provenance in its
    # own METHODS["snapshot"] section, which is where a vintage belongs.
    "SNAPSHOT_CAPTION": "{n_institutions} institutions in the index.",
    # SEED_SEARCH_LABEL labels Find's own search box. SEED_PICK_LABEL/
    # PLACEHOLDER/PROMPT are the dropdown a search resolves to.
    "SEED_SEARCH_LABEL": "Institution name, acronym or alternative name",
    "SEED_PICK_LABEL": "Institution to profile",
    "SEED_PROMPT": "Add an institution using the sidebar search to see its benchmark.",

    # ---- what a publication is (every clause verified against the
    # upstream harvest and classification logic, cross-checked against
    # `app/config.yaml`).
    "PUBLICATIONS_TOOLTIP": (
        "A publication here is an OpenAlex record of type article, review, book, book chapter or "
        "letter, carrying a DOI and published between {y0} and {y1}. {bonus_year} is harvested as a "
        "bonus year and reported for volumes only, never in the impact indicators. A record counts "
        "for an institution when that institution is named on the record itself: full counting "
        "credits the whole publication to each institution named, fractional counting credits the "
        "author share it holds. Retracted records are counted in the totals and left out of the "
        "subject classification, so the subfield, topic, ERC and SDG panels rest on a slightly "
        "smaller set than the size tiles."),

    # ---- legacy seed card, superseded by the profile tiles below ---------
    "EV_L2F": ("L2f compares specialisations only in subfields where both institutions publish enough "
               "to judge: {value} of this institution's subfields qualify."),
    "EV_SDG": "SDG-tagged share of publications: {value}",
    "EV_ERC": "Share of the seed's fractional publications that carry an ERC panel: {value}",  # must not share the retired coverage line's prefix (probe/test check)
    "EV_FRONTIER": "Frontier top-quartile share: {value}",
    "EV_CATCHALL": "Share of publications in catch-all topics, outside the subject scope: {value}",
    "LINK_ROR": "ROR",
    "LINK_HOMEPAGE": "Homepage",
    "TAB_OVERVIEW": "Overview",
    "TAB_ASPIRATIONAL": "Aspirational",
    "OVERVIEW_INTRO": ("Candidates that several independent lenses agree on. Order here is agreement, "
                       "not a score."),
    "CONCORDANCE_EMPTY": ("No candidate is found by more than one of the lenses defined for this seed. "
                          "Open the single-lens tabs instead."),
    "BASIS_DISCLOSURE": "This lens is fractional-only: the counting-basis setting does not change it.",
    "EVIDENCE_LABEL": "Evidence for this seed {sep} {text}",
    "EV_NONE": "No lens-specific evidence line for this seed.",
    "TAIL_SEARCH_LABEL": "Search the full ranking (beyond the rows shown)",
    "TAIL_CAPTION": "Matches anywhere in this lens's ranking, with their original rank.",
    "POP_CAPTION": "Ranked against {n_pop} institutions in the index, the seed excluded.",
    "ASP_INTRO": ("Candidates already found by L1 whose impact interval sits entirely above the "
                  "seed's. Kept in L1-overlap order."),
    "ASP_SORT_LABEL": "Sort by PP(top10%) instead of L1 overlap",
    "ASP_EMPTY": "No L1 candidate's impact interval sits fully above {seed}'s in the pool.",
    "ASP_UNDEFINED": ("The aspirational view needs a defined L1 ranking and a PP(top10%) value with an "
                      "interval for the seed; one of them is missing here."),
    "ASP_CAPTION": ("{n_rows} candidates clear the interval test, out of {n_pool} in the L1 pool "
                    "considered."),
    "COL_RANK": "Rank",
    "COL_INSTITUTION": "Institution",
    "COL_COUNTRY": "Country",
    "COL_TYPE": "Type",
    "COL_PP": "PP(top10%)",
    "COL_L1": "L1 overlap",

    # L22: shared table columns -- both size bases, and the lens-specific
    # evidence cell (replaces the old "Top field" line: L22/#7, "top field"
    # only ever fit L1). Names are the contract looks up.
    "COL_SIZE_FULL": "Size (full)",
    "COL_SIZE_FRAC": "Size (fractional)",
    "COL_EVIDENCE": "Evidence",

    # L16: the controls row (depth / C1 / L7 / post-filters), moved out of
    # the sidebar to sit with the benchmark tables it controls (feedback #1).
    "C1_HELP": ("Restricts the anchor lens (L1) to the seed's own top-{core_top_n} subfields, "
                "for a tighter reading of its core specialisation."),
    "L7_HELP": ("An experimental view, off by default: most of what it surfaces is noise, "
                "with an occasional peer no other lens finds."),
    "POSTFILTERS_EXPANDER": "Post-filters (applied after ranking)",

    # ---- the lens guide (R2 / L29) ---------------------------------------
    "LENS_INTRO_HEADER": "How to read the lenses",
    "LENS_INTRO_LEAD": ("Each lens compares two institutions in a different way, so a candidate can "
                        "rank high on one and be absent from another; the codes are stable "
                        "identifiers, reused in the Overview, in the evidence column and in the "
                        "downloads. Concordance counts the lenses that agree on a candidate, a "
                        "measure of agreement rather than a score."),
    "LENS_LEGEND_CAPTION": ("Codes name the lenses that place a candidate in their top-{N}; see the "
                            "lens guide above."),

    # L17/L18: the profile section that replaces the old seed card.
    "PROFILE_HEADER": "Profile",
    "TILES_HEADER": "Key figures",

    # ---- R2 / L31: every tile positioned against the index ---------------
    "TILE_BASELINE_SUB": "index median {median} {sep} higher than {pct} of institutions",
    "BASELINE_HELP": ("The reference is the whole index, which is made up mostly of universities, so "
                      "the median describes what that population does rather than a level to reach. "
                      "A value under it places the institution within the population, and says "
                      "nothing on its own about how well it performs."),

    "WORDCLOUD_CAPTION": ("Subfields {sep} size = publications on the current counting basis, "
                          "colour = domain"),

    # Yearly breakdown pair (L17 block 4): one segmented control swaps the
    # global + per-year charts between a domain view and a document-type view.
    "BREAKDOWN_CONTROL_LABEL": "Break down by",
    "BREAKDOWN_DOMAIN": "Domain",
    "BREAKDOWN_DOCTYPE": "Document type",
    "BREAKDOWN_GLOBAL_TITLE": "Overall breakdown",
    "BREAKDOWN_YEARLY_TITLE": "Yearly breakdown",

    # L17 block 5: the six collapsed chart panels.
    "PANEL_FIELDS": "Fields",
    "PANEL_SUBFIELDS": "Top {n} subfields",
    "PANEL_TOPICS": "Top topics",
    "PANEL_FRONTIER": "Frontier positioning",
    "PANEL_SDG": "SDG profile",
    "PANEL_ERC": "ERC profile",

    # L20: the shared sort toggle every bar-chart panel carries.
    "SORT_LABEL": "Sort by",
    "SORT_VOLUME": "Volume / share",
    "SORT_TAXONOMY": "Taxonomy order",

    # ---- R2 / L33: the frontier panel's two modes ------------------------
    "FRONTIER_MODE_LABEL": "Topics shown",
    "FRONTIER_MODE_TOP": "Top {n} topics by volume",
    "FRONTIER_MODE_EMERGING": "All topics in the global top quartile of emergence",

    # L20 panel captions.
    "CAPTION_SI": ("SI = the institution's share of a cell divided by the mean share across the "
                   "institutions active in it, so the dashed line marks what an average institution "
                   "holds"),
    "CAPTION_SI_FLOOR": ("Solid marks: at least {floor_solid} fractional publications in the cell. "
                         "Hollow marks: between {floor_thin} and {floor_solid}. Below {floor_thin}, "
                         "no mark at all. The similarity lenses keep their own {floor_solid} rule."),
    "CAPTION_TOPICS_CATCHALL": ("{n} of the topics shown are catch-all topics, outside the subject "
                                "scope, flagged {glyph}; catch-all topics hold {catchall} of this "
                                "institution's publications."),
    "CAPTION_FRONTIER": ("{n_shown} topics are placed here, and {n_excluded} are excluded or carry no "
                         "frontier score. Frontier scores measure attention dynamics rather than "
                         "novelty or quality: a low score can mark a foundational area."),
    "CAPTION_SDG": ("Shares of SDG-tagged output; a publication can carry several SDGs, so the shares "
                    "need not sum to one. SDG {n_missing} is not covered. Matches reflect the "
                    "SIRIS classifier's reading of the SDGs, and different classifiers disagree "
                    "substantially."),
    "CAPTION_ERC": ("Shares of ERC-classified output over {n_panels} panels, covering {erc_share} of "
                    "this institution's publications; the Biotechnology and Arts panels have low "
                    "recall, so read those two with care."),
    "FRACTIONAL_ONLY_PANEL": ("This panel is fractional-only: the counting-basis setting does not "
                              "change it"),

    # The benchmark half of the page -- the section the controls row heads.
    "BENCHMARK_HEADER": "Benchmark",
    "BENCHMARK_INTRO": ("Candidate peers, ranked by each lens independently. The controls "
                        "below govern every tab."),

    # L23 / bug #9: the publications link carries the harvest's own
    # server-side filters, so it counts the same corpus the app does, give or
    # take the drift between a live query and a frozen snapshot.

    # The yearly breakdown's residual series: publications the topic table
    # cannot place in a domain (they carry no primary topic). Shown, never
    # hidden, so the domain and document-type views sum to the same total.
    "UNCLASSIFIED_LABEL": "Unclassified",
    "BREAKDOWN_DOCTYPE_MISSING": ("No document-type rows for this institution in the "
                                  "snapshot; showing the domain breakdown instead."),

    # Empty states for the profile section's own blocks (VIZ_SPEC S1.6: an
    # explicit reason, never a blank panel and never a silent gap).
    "WORDCLOUD_EMPTY": "No subfield mass for this institution under the current settings.",
    "PANEL_EMPTY": "No data for this panel under the current settings.",
    "FRONTIER_EMPTY": ("No topic of this institution carries a frontier score, so there is "
                       "nothing to place on the two axes."),

    # The displayed cut of the two "top N" panels, stated parametrically
    # (VIZ_SPEC S2.16: "the depth of the cut is stated in the panel caption").
    "CAPTION_TOP_N_VOLUME": ("Showing the top {n} subfields by publications on the current counting "
                             "basis; the CSV export carries every subfield."),
    "CAPTION_TOP_N_SHARE": ("Showing the top {n} topics by share of output; the CSV export "
                            "carries every topic."),

    # ======================================================================
    # Every key below is additive: the profile tiles above were later
    # replaced by four summary cards (see CARD_* below); only
    # TILE_BASELINE_SUB and BASELINE_HELP are still read from that section.
    # ======================================================================

    # : the results list no longer auto-loads its best match. The
    # placeholder is what the reader sees until they pick deliberately.
    "SEED_PICK_PLACEHOLDER": "Choose which one to profile",

    # : FOUR cards replace the eight tiles. Each shows one big value,
    # the index-baseline line (TILE_BASELINE_SUB above), and carries ALL of
    # its methodology in its own `?` tooltip -- the sublines that used to
    # print a definition under every tile are gone from the page surface.
    "KPI_PUBS_LABEL": "Publications",
    "KPI_SDG_LABEL": "SDG-tagged share",
    "KPI_SDG_HELP": (
        "Share of the institution's SDG-eligible fractional mass that carries at least one hit "
        "from the SDG keyword vocabulary. Eligibility excludes records the classifier cannot "
        "read (no usable text, or an untranslated language); the SDG panel below names the goals "
        "the vocabulary does not cover, which are missing from every institution alike."),
    "KPI_FRONTIER_LABEL": "Frontier top-quartile share",
    "KPI_FRONTIER_HELP": (
        "Share of the institution's frontier-scorable output sitting in topics that fall in the "
        "global top quartile of emergence. A topic that carries no frontier score is left out of "
        "both the numerator and the denominator, so this is a share of what can be scored, never "
        "a share of everything published."),
    "KPI_PP_LABEL": "PP10_WD",

    # : the two P5 profile tiles (moved here from
    # views_find.py module constants, ).
    "KPI_STARS_LABEL": "Star papers",
    "KPI_LED_LABEL": "Topics led",

    # : two identity-column facts. The columns land on index.parquet
    # later this phase; until they do, both read n/a -- never 0.

    #  / A15: what the cloud encodes, and the one thing a reader has to
    # know before comparing two renders of it.
    "WORDCLOUD_HELP": (
        "Word size is the subfield's publications on the current counting basis and word colour "
        "is its OpenAlex domain. Fractional counting up-weights few-author subfields, social "
        "sciences and humanities in particular, so the two bases render at different scales: "
        "compare positions within one basis, never sizes across the two."),

    # : the breakdown pair gets a section title carrying the bonus-year
    # footnote in its tooltip; the standalone banner under the pair is gone and
    # the control's own "Break down by" label is collapsed.
    "BREAKDOWN_SECTION_TITLE": "Publication breakdown",
    "BREAKDOWN_SECTION_HELP": (
        "Both figures read the counting basis chosen in the sidebar and split the same total: "
        "one shows it over the whole window, the other year by year. {year}{star} is a bonus "
        "year, marked with a star on the year axis: it is reported for volumes only and left out "
        "of every impact indicator."),

    # : what replaces the snapshot stamp on Find and on the menu.
    "DATA_CAPTION": "{n_institutions} institutions {sep} data from {date}",

    # ======================================================================
    # Phase,.
    # ADDITIVE ONLY, save the three narrow in-place edits the deliverable
    # itself requires and that no other stream reads (noted at each one):
    # TAB_ASPIRATIONAL gains its star, FRONTIER_MODE_TOP drops the {n} the
    # slider below replaces, CAPTION_FRONTIER's wording follows suit (catch-
    # all topics are no longer pre-excluded from the cut it describes).
    # ======================================================================

    #  mode B: the aspirational tab's own framing line, ahead of
    # ASP_INTRO, and the one-line notice a V0-empty seed's fallback carries.
    "ASP_FRAME_INTRO": ("A different exercise from the lenses above: identifying institutions worth "
                        "aspiring to, not institutions that merely resemble this one."),
    "ASP_FRONTIER_FALLBACK": ("No candidate in this institution's look-alike pool clears its impact "
                              "interval, so the list below is ordered by frontier alignment instead: "
                              "shared presence in the topics the world is currently expanding into."),
    "COL_F1": "Frontier alignment",

    #  handoff (FB): the frontier panel's new top-N slider and the
    # coverage caption templated from `charts.frontier_coverage`'s numbers.
    "FRONTIER_TOPN_LABEL": "Maximum topics plotted",
    "CAPTION_FRONTIER_COVERAGE": (
        "Catch-all topics are counted in this cut like any other topic: {n_catchall} of the topics "
        "shown are catch-all, flagged {glyph}. This cut leaves out {pct_not_shown} of the placeable "
        "mass; the smallest topic shown holds {min_mass} publications on the current counting basis."),

    # : DISPLAY lens codes, renumbered L0.L7 in TAB ORDER (the eight
    # defaults) plus L8 (C1) and L9 (L7, the experimental/noise lens) for the
    # two optional tabs -- the codes a reader actually sees on a tab, in the
    # guide, in the concordance chips and in the cross-lens "rank under"
    # reference. Internal engine ids (`lib.engine.ALL_LENSES` and everything
    # keyed on them: CSV exports, `evidence_text`, `rank_under_other_lenses`,
    # ctx dict keys) are UNCHANGED -- LENS_DISPLAY_CODE is the ONE table that
    # translates one into the other, keyed by the internal id it is looked up
    # with. `docs/METHODS_NOTE.md`'s own concordance table (next
    # wave) reads this same dict rather than a second copy of the mapping.
    #
    # LENS_DISPLAY_NAMES is LENS_NAMES' sentence, with the NEW code substituted
    # for the old one -- the full name + one-line intro a tab body now opens
    # on (A11: the tab itself carries only the bare code). The OLD LENS_NAMES/
    # LENS_INTRO/LENS_CAVEAT dicts above are untouched: the Methods page still
    # reads them as they stand until own wave retires the old
    # numbering there too ( FC row).
    "LENS_DISPLAY_CODE": {
        "L0": "L0", "L1": "L1", "L3": "L2", "F1": "L3", "L2f": "L4",
        "L4": "L5", "L5": "L6", "L6": "L7", "C1": "L8", "L7": "L9",
    },
    "LENS_DISPLAY_NAMES": {
        "L0": "L0 · Field overlap",
        "L1": "L1 · Subfield overlap",
        "L3": "L2 · Topic overlap",
        "F1": "L3 · Frontier-topic overlap",
        "L2f": "L4 · Shared specialisations",
        "L4": "L5 · ERC panel overlap",
        "L5": "L6 · ERC specialisation overlap",
        "L6": "L7 · SDG profile overlap",
        "C1": "L8 · Core-shape overlap",
        "L7": "L9 · SDG specialisation (experimental)",
    },

    # ======================================================================
    # The KPI tiles' help text was later replaced by cards; the keys the
    # cards no longer use (KPI_PUBS_HELP, KPI_PP_HELP, IDENTITY_FACTS_HELP,
    # PUBLICATIONS_LINK_LABEL) have been deleted.
    # ======================================================================

    # -1a: the type correction is no longer a badge. It renders INLINE in
    # the identity line -- "government* (was: facility) · Brest, France" -- with
    # the star, and only the star, in red, and the whole line's tooltip saying
    # what the star means. Ten institutions carry it (Ifremer, TNO, CNR,
    # SINTEF, DLR, Ikerbasque and the four German centres); every one of them
    # crashed the profile while the correction and the umbrella badge were
    # asserted mutually exclusive.
    "IDENTITY_TYPE_CORRECTED": "{kind}{star} (was: {was})",
    "IDENTITY_TYPE_HELP": (
        "The type marked with a star is a SIRIS correction: OpenAlex records this institution "
        "under the type in brackets, which misdescribes what it is and would place it against the "
        "wrong comparison group. The corrected type is what every filter, median and comparison on "
        "this page uses."),

    # -6: the institution NAME is the link to its publications in
    # OpenAlex, so the row of links carries only the two links that point
    # somewhere else. What a publication IS moved into the publications card's
    # own tooltip, where the figure it qualifies is.
    "IDENTITY_NAME_HELP": (
        "The institution name opens its publications in OpenAlex, filtered exactly as this "
        "analysis filters them. The live count differs slightly from the figure shown here: "
        "OpenAlex keeps changing, this analysis reads a fixed extract."),

    # -6: SIX cards, name first. The publications card carries the
    # fractional count as its small line instead of an index position; the
    # other five carry the index baseline.
    "KPI_PUBS_FRAC_NOTE": "({n} in fractional counting)",
    "KPI_PUBS_HELP_FULL": (
        "The large figure counts every publication the institution is named on. The figure under "
        "it credits only the author share it holds, which is the fairer basis for comparing "
        "institutions of different sizes and the basis most of this page uses."),
    # PP10_WD's own suffix plus the FIXED two-axes
    # explainer every impact tooltip carries. This is the FIRST
    # (and, on this page, only) mention of "the European baseline" -- the
    # ruled wording, spelled out in full here and shortened everywhere else
    # the app repeats it.
    "KPI_PP_HELP_R2": (
        "Share of the institution's fractional output that sits in the world top decile of its "
        "own citation distribution: the European baseline (EU27 plus the United Kingdom, "
        "Switzerland, Norway and Iceland) is used elsewhere on this page for the typical level; "
        "this measure alone is read against the world, for the excellence tail. Articles and "
        "reviews only; the bonus year is excluded."),
    "KPI_INTL_LABEL": "International co-publications",
    "KPI_COMPANY_LABEL": "Industrial co-publications",
    "KPI_INTL_HELP": (
        "Share of the institution's publications from {y0} to {y1}, full counting, carrying at "
        "least one other institution named on the record and based in another country. "
        "Institutions OpenAlex cannot place in a country are counted in the denominator and never "
        "treated as domestic."),
    "KPI_COMPANY_HELP": (
        "Share of the institution's publications from {y0} to {y1}, full counting, carrying at "
        "least one company named on the record. The type is the one OpenAlex records for the "
        "partner, so an institute a company owns but OpenAlex types otherwise is not counted."),

    # -8 (Find scope) needs NO new string: what stays visible under a
    # chart is ONE reading line, and the second and third grey lines move
    # verbatim, same keys -- into that line's own `?` tooltip. A relocation is
    # not a rewrite; rewriting these sentences is pass.

    # , (D5/D4, CHROME_CONTRACT.md S7): the SDG and ERC
    # profile panels read `sdg.parquet`/`erc.parquet`, both denominated on the
    # WHOLE-RUN window (window_conventions.sdg_mass_window, data_contract.yaml
    # six years, the bonus year included), never the five-year corpus
    # window this page states everywhere else. Disclosure only: the basis
    # itself is unchanged, this just says it in words where the ratio it
    # qualifies is on screen.
    "RATIO_WHOLE_RUN_BASIS": ("This panel's shares are computed on the {window} window (the whole "
                              "run, including the bonus year), not the {corpus} window used "
                              "elsewhere on this page."),

    # E7: the ONE end-of-page workbook replacing every
    # per-lens CSV -- see `lib/exports_xlsx.py`/`lib/views_find.py:
    # _find_workbook`. Sheet labels are plain nouns; the per-lens sheets
    # themselves are named from `LENS_DISPLAY_NAMES`, not typed here.
    "EXPORT_XLSX_BUTTON": "Download this profile and benchmark (Excel)",
    "EXPORT_XLSX_HELP": ("One sheet per lens, plus the profile's own key figures and the ranked-"
                         "by-how-many-lenses overview, computed for every lens regardless of "
                         "which tab is open."),
    "XLSX_SHEET_PROFILE": "Profile",
    "XLSX_SHEET_OVERVIEW": "Overview",
    "XLSX_SHEET_ASPIRATIONAL": "Aspirational",
}

# : the two dicts above, hoisted to module level so `lib/ranked.py`
# (which has no reason to import the whole FIND dict) and any other caller can
# read `copy.LENS_DISPLAY_CODE` directly, exactly like the pre-existing
# `copy.LENS_NAMES` at module level above.
LENS_DISPLAY_CODE = FIND["LENS_DISPLAY_CODE"]
LENS_DISPLAY_NAMES = FIND["LENS_DISPLAY_NAMES"]

# In-place edits the //A11 wiring requires (narrow, noted above):
FIND["TAB_ASPIRATIONAL"] = "★ " + FIND["TAB_ASPIRATIONAL"]           # "★ Aspirational"
FIND["FRONTIER_MODE_TOP"] = "Top topics by volume"                        # the slider now states n
FIND["CAPTION_FRONTIER"] = (
    "{n_shown} topics are placed here; {n_excluded} carry no frontier score and cannot be placed. "
    "Frontier scores measure attention dynamics rather than novelty or quality: a low score can mark "
    "a foundational area.")

# ==========================================================================
#  ,: the narrative wrapper (NAV), the Compare page
# (COMPARE) and the Methods page (METHODS +
# METHODS_SOURCES). Same RULE and same VOICE as everything above: no digit
# outside an allowlisted token or a `{placeholder}`, no em dash and no "--"
# standing in for one, and no engine vocabulary (the words an engineer uses
# for the machinery, in place of the words a strategy officer uses for the
# question). Sources are cited section by section in `docs/METHODS_NOTE.md`,
# which carries the same text with the numbers written out; the app never
# renders that file.
# ==========================================================================

# ------------------------------------------------------- nav + Menu cards
# : four pages, in the order a reader walks them. The label is what the
# sidebar shows, the blurb is what the Menu card says, the lead is the one
# sentence the page opens on (the question it answers).

NAV = {
    "MENU_HEADER": "BenchUp",
    "MENU_INTRO": ("Three pages, in the order most readings take: find institutions that resemble "
                   "yours, put two of them side by side, and read how every figure on the way "
                   "was built."),

    "FIND_LABEL": "Find peers",
    "FIND_BLURB": ("Start from one institution and see who resembles it, lens by lens, with the "
                   "agreement between lenses shown rather than averaged away."),

    "COMPARE_LABEL": "Compare",
    "COMPARE_BLURB": ("Put two institutions side by side: key figures, thematic and SDG shape, "
                      "frontier positioning and the shared frontier, and the relationship "
                      "between the two."),

    "METHODS_LABEL": "How it is built",
    "METHODS_BLURB": ("Every definition, threshold and known weakness behind the figures, one "
                      "section per question a reader is entitled to ask."),
    "METHODS_LEAD": "Where does each number come from, and what does it leave out?",
}

# --------------------------------------------------------- Compare page ----
# Every key below is what `lib/views_compare.py` actually renders: the
# N-institution "Compare by" matrix, ERC panels, dynamics, the pooled
# frontier scatter, coverage and impact-by-subfield sections are not part of
# the app. Every caption names its own window and basis: Compare is PINNED
# to the best-fit taxonomy and full counting, so no key here offers a
# toggle-facing sentence the way Find's do.

COMPARE = {
    "PAGE_TITLE": "Compare",
    "PAGE_INTRO": ("Two institutions, side by side, on the same measures: what each one "
                   "publishes, where its frontier work sits, and what the two already share."),
    "PROMPT_NEED_TWO": "Pick two institutions above to compare them.",
    "PIN_CAPTION": ("Every figure here is on the best-fit taxonomy and full counting "
                    "(fractional counts appear in hover). Most figures cover {y0} to {y1}; "
                    "the share of an institution's own output is measured against its whole "
                    "record, through {whole_y1}."),
    "DEEPLINK_LABEL": "Share this comparison, exactly as it stands, with this link.",

    # ---- 1. key-figure cards (D8) -----------------------------------------
    "CARDS_HEADER": "Key figures",
    "CARDS_NOTE": "One card per institution; the dot marks the higher figure.",
    "CARDS_NOTE_TIP": ("Every figure names the European median across the whole index in its "
                       "own tooltip; a measure an institution holds too little to support "
                       "reads n/a, never zero."),
    "CARD_PUBLICATIONS": "Publications",
    "CARD_PUBLICATIONS_TIP": ("{y0} to {y1}, full counting. In fractional counting: {frac}. "
                              "European median: {eu_median}."),
    "CARD_VOL_CHANGE": "Change in mean annual volume",
    "CARD_VOL_CHANGE_TIP": ("Mean annual publications over {w2}, against the same average over "
                            "{w1}. European median: {eu_median}."),
    "CARD_FWCI": "FWCI_EU",
    "CARD_FWCI_TIP": ("Median field-weighted citation impact against the European baseline, {y0} "
                      "to {y1}. Mean: {mean}. European median of the same statistic: "
                      "{eu_median}."),
    "CARD_PP10": "PP10_WD",
    "CARD_PP10_TIP": ("Share of {y0} to {y1} articles and reviews in the world top decile of "
                      "citations for their own subfield, year and document type. European "
                      "median: {eu_median}."),
    "CARD_STARS": "Star papers",
    "CARD_STARS_TIP": ("Share of {y0} to {y1} articles and reviews that are among the world's "
                       "most-cited works in their own topic and year. Count: {count}. European "
                       "median: {eu_median}."),
    "CARD_TOPICS_LED": "Topics led",
    "CARD_TOPICS_LED_TIP": ("Topics where this institution ranks among the world top ten "
                            "publishers, {pool} pool. European median: {eu_median}."),
    "CARD_FRONTIER": "Frontier share",
    "CARD_FRONTIER_TIP": ("Share of {y0} to {y1} output sitting in the global top-quarter "
                          "frontier topics. European median: {eu_median}."),
    "CARD_SDG": "SDG-tagged share",
    "CARD_SDG_TIP": ("Share of {y0} to {y1} output carrying at least one Sustainable "
                     "Development Goal tag. European median: {eu_median}."),
    "CARD_COPUB": "International & company co-publication",
    "CARD_COPUB_TIP": ("International co-publication: {intl}, European median {intl_eu}. "
                       "Company co-publication: {company}, European median {company_eu}. "
                       "{y0} to {y1}."),

    # ---- 2. thematic shape (D3) --------------------------------------------
    "SHAPE_HEADER": "Thematic shape",
    "TAB_PROFILE": "Profile",
    "TAB_IMPACT": "Impact",
    "SHAPE_BASIS_CAPTION": ("Top {n} subfields by the pair's combined volume, best-fit "
                            "taxonomy, full counting."),
    "SHAPE_NOTE_PROFILE": ("Each bar is a subfield's share of that institution's own output; "
                           "the diamond is the European mean."),
    "SHAPE_NOTE_IMPACT": ("Each bar is PP10_WD against the world reference; a row resting on "
                          "fewer than {floor} covered works carries a dagger."),

    # ---- 3. SDG profile (D4) ------------------------------------------------
    "SDG_HEADER": "SDG profile",
    "SDG_BASIS_CAPTION": ("Every Sustainable Development Goal this taxonomy tags, best-fit "
                          "taxonomy, full counting."),
    "SDG_NOTE_PROFILE": ("Each bar is a goal's share of that institution's own tagged output; "
                         "the diamond is the European mean."),
    "SDG_NOTE_IMPACT": ("Each bar is PP10_WD against the world reference; a row resting on "
                        "fewer than {floor} covered works carries a dagger."),
    "SDG_UNTAGGED": "{name}: {share} of output carries no Sustainable Development Goal tag.",

    # ---- 4. frontier: positioning + the shared deep dive (D5) ---------------
    "FRONTIER_HEADER": "Frontier",
    "FRONTIER_POSITIONING_SHARE": "Share of output in frontier topics",
    "FRONTIER_POSITIONING_PUBLISHED": "Topics published in",
    "FRONTIER_POSITIONING_TOP_DECILE": "of which world top-decile",
    "FRONTIER_POSITIONING_LED": "Topics led",
    "FRONTIER_POSITIONING_STARS": "Star papers in frontier topics",
    "FRONTIER_POSITIONING_TIP": ("Frontier topics are the global top quarter by frontier score; "
                                 "world top-decile is the global top tenth by that same score, "
                                 "{y0} to {y1}."),
    "FRONTIER_SHARED_LINE": "{n} frontier topics are held by both institutions.",
    "SHARED_FRONTIER_HEADER": "Who holds the shared frontier",
    "SHARED_FRONTIER_BASIS_CAPTION": ("Shared frontier topics, ranked by the pair's combined "
                                      "publications, full counting."),
    "SHOW_ALL": "Show all {n}",
    "SHARED_FRONTIER_NOTE": ("Each bar splits into that institution's own publications, with "
                             "their joint publications on the topic centred in red."),
    "SHARED_FRONTIER_TIP": ("Expansion reads how fast world attention to the topic is growing; "
                            "acceleration reads whether that growth is itself speeding up. Both "
                            "measure attention, not novelty or quality. \N{BLACK DIAMOND} marks "
                            "a topic in the world top-decile by frontier score. Below {floor} "
                            "joint publications the pair's joint segment is not shown "
                            "separately, and the table's joint column reads n/a."),
    "SHARED_FRONTIER_TABLE_CAPTION": ("Every column the chart above shows, plus keywords, each "
                                      "institution's own change in mean annual volume ({w1} "
                                      "against {w2}, a dagger under {floor} works over the "
                                      "window), each institution's world rank on the topic, and "
                                      "star-paper counts. The three links open that "
                                      "institution's -- or the pair's joint -- publications on "
                                      "the topic in OpenAlex."),
    "COL_TOPIC": "Topic",
    "COL_KEYWORDS": "Keywords",
    "COL_FRONTIERNESS": "Frontierness",
    "COL_EXPANSION": "Expansion",
    "COL_ACCELERATION": "Acceleration",
    "COL_VOL": "{name}",
    "COL_VOL_JOINT": "Joint",
    "COL_CHANGE": "{name} change",
    "COL_RANK": "{name} world rank",
    "COL_STARS": "{name} stars",
    "COL_LINK": "{name}'s publications",
    "COL_LINK_JOINT": "Joint publications",
    "RANK_POOL_UNIVERSITIES": "universities",
    "RANK_POOL_ALL": "all institutions",

    # ---- 5. the relationship (D7) --------------------------------------------
    "RELATIONSHIP_HEADER": "The relationship",
    "RELATIONSHIP_NEVER": "These two institutions have no recorded joint publications.",
    "MOMENTUM_TIP": ("Compares mean annual joint articles and reviews over {w2} against {w1} "
                     "({c2} against {c1} a year). {sig}"),
    "MOMENTUM_SIGNIFICANT": "The change is significant at the {alpha} level (p {p}).",
    "MOMENTUM_NOT_SIGNIFICANT": "The change is not significant at the {alpha} level (p {p}).",
    "MOMENTUM_NO_TEST": "There is too little joint work over the window for a significance test.",
    "YEARLY_CAPTION": "Joint articles and reviews with a subject topic, {y0} to {y1}.",
    "YEARLY_TOPICLESS_NOTE": (" A small number of this pair's joint publications carry no "
                              "subject topic and are not shown in the breakdown above; the "
                              "total below still counts them."),
    "YEARLY_FALLBACK_CAPTION": ("Below {floor} joint publications this pair has too little "
                                "co-published work for a domain breakdown; every joint "
                                "publication, {y0} to {y1}, is shown as one series instead."),
    "RECIPROCITY_HEADER": "Strategic reciprocity by field",
    "RECIPROCITY_CAPTION": ("Each bar is a field's share of that institution's own publications; "
                            "the number between the two bars is how many publications the pair "
                            "signed together in that field. A field that weighs heavily for both "
                            "and carries many joint publications is where the relationship "
                            "matters to both sides."),
    "JOINT_STARS_LINE": ("{n} of their joint publications are among the world's most-cited "
                         "works in their own topic and year."),
    "JOINT_STARS_CAPTION": "Sorted by citations, most cited first.",
    "JOINT_STARS_LINK_LABEL": "View on OpenAlex",

    # ---- 6. the workbook (D2/E7) ---------------------------------------------
    "EXPORT_BUTTON": "Download this view (Excel)",
    "EXPORT_HELP": ("One workbook: the key figures, every subfield, the SDG profile, frontier "
                    "positioning, the shared frontier with its links, and the relationship's "
                    "yearly and reciprocity figures."),
    "XLSX_SHEET_CARDS": "Cards",
    "XLSX_SHEET_SUBFIELDS": "Subfields",
    "XLSX_SHEET_SDG": "SDG",
    "XLSX_SHEET_POSITIONING": "Positioning",
    "XLSX_SHEET_SHARED_FRONTIER": "Shared frontier",
    "XLSX_SHEET_RELATIONSHIP_YEARLY": "Relationship yearly",
    "XLSX_SHEET_RECIPROCITY": "Reciprocity",
}

# --------------------------------------------------------- Methods page ----
# , BenchUp V4 trim,. Eleven sections, one per
# objection a reader is entitled to raise about the trimmed app, in the
# order a reader meets them. The app renders these templates and fills
# every `{placeholder}` at run time from CFG, the manifest or the shipped
# tables (the mapping is METHODS_SOURCES below, and `docs/METHODS_NOTE.md`
# carries the same sections with the numbers written out).


def _lens_concordance_table() -> str:
    """/-MU: one line per lens, the DISPLAY code a reader sees on
    a tab, the lens's name, and the internal identifier the evidence column,
    the CSV export and the rest of this note still use. Built from
    `LENS_DISPLAY_CODE`/`LENS_DISPLAY_NAMES` rather than a second hand-typed list, so the two
    numberings cannot drift apart. Order follows tab order (defaults L0.L7,
    then the two optional tabs C1->L8, L7->L9). A markdown TABLE (`|---|`)
    would read fine but types a literal "--" into a copy.py string constant,
    which the VOICE rule bans outright; a bold-code list reads just as
    clearly in a rendered `st.markdown` expander and keeps the scan clean."""
    order = ["L0", "L1", "L3", "F1", "L2f", "L4", "L5", "L6", "C1", "L7"]
    lines = []
    for internal in order:
        name = LENS_DISPLAY_NAMES[internal].split(" · ", 1)[1]
        lines.append(f"**{LENS_DISPLAY_CODE[internal]}** ({internal}): {name}")
    return "\n\n".join(lines)


# The impact-interval coverage sentence, hoisted to
# module level so the Compare page can reuse the SAME wording
# rather than a second hand-typed caption ("impact intervals with stated
# coverage"). `ci_coverage` and `n_bootstrap`
# are plain facts (config.yaml methods_facts / source_manifest.json), never
# typed in here; `tests/test_pages_methods.py` pins the coverage number
# against the function it is actually read off.

# FWCI_NOT_AVAILABLE_LINE (-11(c) / MU3) DELETED (TEV-U wave 3, MT
# sweep casualty #4): FWCI is a real, always-attempted column now (ruling 4,
# `fwci_ref.parquet` + `collab_pairs`/`collab_pair_topics`/`collab_pair_
# fields`'s own `fwci_median`), never a "not available" descope line -- the
# ONE caller (`ops/_probe_collab.py`, itself deleted this wave, superseded by
# `tests/ui/probe.py`) is gone with it. Zero other usage confirmed
# (`grep -rn "FWCI_NOT_AVAILABLE_LINE"` across lib/tests/ops).

# -2 /: the colour-system rule stated once, in plain terms, so
# a future chart caption on any page can quote it rather than re-explaining
# the same convention. The rule itself: institution colour fills a mark, a
# taxonomy's own colour never does (COMPARE's CAPTION_ACCENT_ERC/_SDG already
# say the narrower, per-chart version of this same sentence).

METHODS = {
    "what_it_is": {
        "title": "What the tool is",
        "body": (
            "BenchUp compares European research institutions on their published output, read from "
            "OpenAlex, the same way for every institution in its index. A strategy officer can check "
            "where a competitor or a prospective partner stands without asking them for their own "
            "numbers.\n\n"
            "Every list and every chart the tool produces is a set of candidates for review: a lens "
            "that places an institution close to another, or a chart that puts two institutions side "
            "by side, is a starting point for a conversation. The index behind every page holds "
            "{n_institutions} institutions across {n_countries} countries."),
    },
    "data_windows": {
        "title": "Data and windows",
        "body": (
            "The snapshot behind every page is the OpenAlex harvest of {snapshot}. The perimeter is "
            "{n_countries} countries: the European Union, together with the United Kingdom, "
            "Switzerland, Norway and Iceland. An institution outside that perimeter never enters the "
            "index, though it can still appear as a co-author on someone else's publication.\n\n"
            "A publication counts if OpenAlex carries it as one of: {doc_types}, with a DOI.\n\n"
            "Two windows are in use, and every chart and card states which one it reads. Impact, star "
            "papers, world leaders and the relationship block all read {core_ar_window}. Find's own "
            "volume charts read the whole run instead, {y0} to {bonus_year}, because a change over "
            "time needs every year harvested; {bonus_year} still carries its own bonus-year mark, "
            "since the harvest catches it only partway through and it is left out of every impact "
            "figure."),
    },
    "counting_bases": {
        "title": "Counting bases, and the Compare pin",
        "body": (
            "An institution is credited with a publication when the publication's own record names "
            "it directly, never through OpenAlex's own parent-child organisation graph, which would "
            "graft a partner's whole output onto a shared institution.\n\n"
            "Full counting credits the whole publication to every institution named on it. Fractional "
            "counting instead splits the publication across the institutions an author declares, by "
            "that author's own share. Neither is more correct, and the setting that governs them is "
            "stated on every page that uses it.\n\n"
            "Find offers both bases, plus {n_trees} taxonomy trees, as sidebar toggles. Compare pins "
            "every figure to the best-fit tree and full counting instead, so the two institutions on "
            "the page are always read the same way; the fractional count sits in the hover wherever "
            "a Compare figure needs it."),
    },
    "taxonomy": {
        "title": "The subject taxonomy",
        "body": (
            "OpenAlex files every publication under a topic, and every topic under a subfield and a "
            "field. A measurable share of those subfield placements is wrong, so this tool ships "
            "three versions of the tree: the original OpenAlex placement, a conservative repair, and "
            "a best-fit repair.\n\n"
            "The best-fit tree moves {n_best_diff} of the taxonomy's {n_topics} topics to a different "
            "subfield from OpenAlex's own placement; the conservative tree accepts a smaller set, "
            "{n_cons_diff} topics, changing only the cases with the clearest evidence.\n\n"
            "Compare always reads the best-fit tree. Find lets a reader switch between the three, and "
            "the choice reshapes every subfield and field figure on the page. Topic-grain figures, "
            "frontier scores, star papers and world leaders among them, are unaffected by the choice: "
            "a topic is the taxonomy's base unit, and a tree only decides which subfield it rolls up "
            "into."),
    },
    "two_baselines": {
        "title": "Two baselines, kept apart",
        "body": (
            "Two impact figures sit behind the tool, and they are never averaged into one score, "
            "because they read two different things.\n\n"
            "FWCI_EU is a typical-level reading: the median, across an institution's own "
            "publications, of each publication's citations set against the average publication of "
            "the same subfield, year and document type, computed over the tool's European baseline, "
            "the {n_countries}-country perimeter above. The mean of the same distribution sits in "
            "hover, beside the median.\n\n"
            "PP10_WD is an excellence-tail reading instead: the share of an institution's articles "
            "and reviews, {y0} to {y1}, landing in the world top decile of citations for their own "
            "subfield, year and document type, computed against the whole world rather than the "
            "European baseline.\n\n"
            "The two differ on two axes at once: what each one measures, a typical level against an "
            "excellence tail, and whom each one is measured against, Europe against the world. An "
            "institution can sit close to the European typical level on FWCI_EU and still stand out, "
            "or fail to, on the world's own top decile."),
    },
    "frontier_scores": {
        "title": "Frontier scores",
        "body": (
            "Frontier scores read how fast world attention to a topic is moving. Expansion is a "
            "standardised reading of how fast the world's publication volume in a topic grew over "
            "the latest period; acceleration is a standardised reading of whether that growth is "
            "itself speeding up or slowing down, against the period before it. A well-established, "
            "foundational topic can carry a low score simply because the world's attention to it has "
            "stopped growing.\n\n"
            "{n_excluded} of the taxonomy's {n_topics} topics carry no frontier score at all: "
            "catch-all topics sitting outside the taxonomy's own subject scope, excluded by "
            "construction. Every scored topic sits in one of four quadrants, crossing the sign of "
            "expansion against the sign of acceleration.\n\n"
            "The frontier topic pool Compare measures an institution against is fixed at the global "
            "top quarter of scored topics. A further mark, a filled diamond in the shared-frontier "
            "table, flags a topic in the global top {top_decile_pct} of frontier score among every "
            "scored topic, a stricter cut than the top-quarter pool it sits inside."),
    },
    "world_leaders": {
        "title": "World leaders",
        "body": (
            "For every topic, this tool ranks the world's publishers twice: once across every "
            "institution type, and once restricted to universities alone. Both leaderboards run up "
            "to {leader_depth} institutions deep, articles and reviews only, {y0} to {y1}, pulled "
            "live from OpenAlex on the day the leader list was built.\n\n"
            "The two leaderboards exist because a single ranking across every institution type "
            "favours large, multi-site research and technology organisations by construction: a body "
            "that runs many institutes under one name accumulates more publications than any single "
            "university. An institution's own 'topics led' figure reads the fair pool for its own "
            "type: the university leaderboard for a university, the all-institution leaderboard for "
            "everyone else. Every rank shown on the page names its own pool, so a reader never "
            "mistakes one leaderboard's tenth place for the other's."),
    },
    "star_papers": {
        "title": "Star papers",
        "body": (
            "A star paper is one of the world's most-cited works within its own topic and "
            "publication year: the top {star_pct} by citations, articles and reviews only, {y0} to "
            "{y1}, pulled live from OpenAlex on the day the star list was built. A tie sitting "
            "exactly on the cutoff, beyond the number the cut allows, is left out rather than "
            "included.\n\n"
            "Star share is the size-free reading: an institution's own star-paper count divided by "
            "its own article-and-review output over the same window. A small institution with a "
            "handful of highly cited papers can post a very high share on a very small base. "
            "{top_star_name} illustrates the case on this snapshot, with a {top_star_share} star "
            "share resting on a small output; the raw count sits beside the share for exactly this "
            "reason, so a high share is never read without its own denominator."),
    },
    "relationship": {
        "title": "The relationship",
        "body": (
            "A pair's joint total, at the top of Compare's relationship block, counts every "
            "publication naming both institutions directly, any document type, over the whole run. "
            "Everything below it reads a narrower window instead: {core_ar_window}, the same filter "
            "carried on every link, so the number on the page and the count the link opens on "
            "agree.\n\n"
            "The yearly stack breaks that joint total down by year and by the four OpenAlex domains. "
            "A small share of joint publications, about {topicless_pct} of joint volume across every "
            "qualifying pair, carries no subject topic and cannot be placed in a domain; the stack "
            "leaves them out, though the total above it still counts them. A topic or a field "
            "breakdown needs at least {pair_qualifying_floor} shared articles and reviews to stay "
            "meaningful; a pair below that floor keeps its joint total and a link to every shared "
            "publication, without the breakdown.\n\n"
            "Momentum compares a pair's mean annual joint output over {momentum_w2} against "
            "{momentum_w1}, recentred against the same ratio's median across every eligible pair, so "
            "corpus-wide growth over those years does not read as growth specific to the pair. A "
            "change is only shown once a significance test on the two windows' raw counts clears the "
            "{momentum_alpha} level; below it, the pair reads as no significant change rather than "
            "up or down.\n\n"
            "Reciprocity reads a pair's joint output in a field against each side's own portfolio: "
            "each field carries two bars, one institution's own share of its output sitting in "
            "that field, and the pair's joint publications in that field are shown once, between "
            "the two bars. A field that weighs heavily for both institutions and carries many "
            "joint publications is where the relationship matters to both sides."),
    },
    "matching": {
        "title": "Matching",
        "body": (
            "Find compares one seed institution against the rest of the index through several "
            "independent lenses, each reading resemblance a different way: shared fields, shared "
            "subfields, shared topics, shared frontier topics, shared specialisations, and more.\n\n"
            + _lens_concordance_table() +
            "\n\nEvery lens shows its top {depth_max} candidates; the full ranking is always computed "
            "underneath, and can be searched or downloaded whatever the display cutoff. Concordance "
            "counts how many of the lenses defined for a seed place a given candidate inside their "
            "own top-{concordance_n}, a measure of how many independent readings agree rather than a "
            "score of its own: it adds no candidate the lenses do not already find on their own. A "
            "further tab, aspirational, answers a different question: which of a seed's own "
            "subfield-lens candidates its own impact already exceeds."),
    },
    "limits": {
        "title": "Limits",
        "body": (
            "A lens places a candidate close to a seed by shared output shape. That is a resemblance "
            "signal a reader still has to judge for a true partnership case; an institution with a "
            "genuinely different output shape from the seed's own, a national-system peer or a "
            "mission peer among them, can go unfound by every lens at once.\n\n"
            "The taxonomy repair leaves gaps too: {n_forced_or_nofit} of the taxonomy's {n_topics} "
            "topics needed a forced or a no-fit placement, sitting in the tree without a confident "
            "match. The type behind a fair pool, or a company and international share, follows a "
            "small set of corrections SIRIS made to OpenAlex's own institution type; a type this "
            "tool has not reviewed keeps OpenAlex's own label.\n\n"
            "World leaders and star papers are pulled from OpenAlex on the day they were built, a "
            "different moment from the harvest snapshot behind every other figure on the page, so "
            "the two can drift a little apart. OpenAlex itself keeps changing: a rerun on a later "
            "date, against a fresh OpenAlex pull, will not reproduce this snapshot's exact counts, "
            "even from the same code."),
    },
}

METHODS_SOURCES = {
    "n_institutions": "manifest()'s index.parquet row count, or len(index()) as a fallback",
    "n_countries": "CFG perimeter_countries, list length",
    "snapshot": "manifest()'s own snapshot field, or CFG snapshot as a fallback",
    "doc_types": "CFG corpus_types, formatted as a plain-English list",
    "y0": "CFG window, first year",
    "y1": "CFG window, second year",
    "bonus_year": "CFG bonus_year",
    "core_ar_window": "docs/data_contract.yaml window_conventions.core_ar_window, read verbatim",
    "n_trees": "CFG scenario.toggles.tree, list length",
    "n_topics": "row count of topics_dim.parquet",
    "n_excluded": "count of topics_dim.is_excluded == True",
    "n_best_diff": "count of topics_dim rows where bestfit_subfield_id differs from original_subfield_id",
    "n_cons_diff": "count of topics_dim rows where conservative_subfield_id differs from original_subfield_id",
    "n_forced_or_nofit": "count of topics_dim rows with fit_quality in (forced, no_fit)",
    "top_decile_pct": "the complement of lib.compare_data.ELITE_FRONTIER_PERCENTILE, formatted as a percent",
    "leader_depth": "measured live: the maximum rank value in topic_leaders.parquet",
    "star_pct": "views_methods.STAR_TOP_PCT, the star-paper cut from the star-papers pipeline step's own k formula (not shipped to any table), formatted as a percent",
    "top_star_name": "measured live: the display_name of the index row with the highest star_share",
    "top_star_share": "measured live: that same row's star_share, formatted as a percent",
    "pair_qualifying_floor": "lib.compare_data.PAIR_QUALIFYING_FLOOR",
    "topicless_pct": "measured live: the complement of (sum of collab_pair_domain_year.vol over sum of collab_pairs.core_total), pairs with core_total at or above PAIR_QUALIFYING_FLOOR",
    "momentum_w1": "data/collab_facts.json, the earlier momentum window",
    "momentum_w2": "data/collab_facts.json, the later momentum window",
    "momentum_alpha": "data/collab_facts.json's own alpha value, formatted as a percent",
    "concordance_n": "CFG concordance_N",
    "depth_max": "CFG depth.max",
}

# ------------------------------------------------ Methods page chrome
METHODS_UI = {
    "DOWNLOAD_LABEL": "Download the source note (Markdown)",
    "DOWNLOAD_CAPTION": ("This page and the file above come from the same templates: the numbers here are "
                         "filled at run time from the snapshot loaded, the file states them in full with a "
                         "citation per section."),
}

# ----------------------------------------------------- digit-ban self-check

_ALLOWLIST_RE = re.compile(
    r"\bL0\b|\bL1\b|\bL2f\b|\bL2\b|\bL3\b|\bL4\b|\bL5\b|\bL6\b|\bL7\b|\bL8\b|\bL9\b|\bF1\b|\bC1\b|"
    r"top10|PP\(top10%\)|PP10_WD|EU27"
)
# "EU27" added alongside "PP10_WD" -- the E1 ruled
# perimeter phrase, "the European baseline (EU27 plus the United Kingdom,
# Switzerland, Norway and Iceland)", is typed verbatim wherever a page
# defines the term for the first time (Find's own PP10_WD tooltip among
# them), and "27" is a stable identifier (the EU's own member-state count),
# not a data value a rebuild could change.
#  adds L2/L8/L9 -- L2 is the renumbered topic lens's own DISPLAY
# code (L2f, a DIFFERENT lens, must stay in the alternation and BEFORE L2 so
# the longer token matches first), L8/L9 are the two optional lenses' codes
# to the allowlist above; `tests/test_narrative.py:has_digit_violation`
# carries its own copy of this same stripping behaviour and is updated
# alongside it.
# PP10_WD is added: the suffix-naming ruling names the
# impact figure FWCI_EU / PP10_WD on every axis, hover and caption
# project-wide (FWCI_EU carries no digit and needs no entry here); PP10_WD
# is a stable metric identifier, the same category of exemption as the lens
# codes above, never a typed number. `tests/digit_allowlist.txt` gets the
# same token, and drops "" (its last live use retired this round by
# this same stream's Menu.py fix), so the shared allowlist's own cap holds.
# A `{named}` format placeholder is never rendered literally -- the RULE at
# the top of this file exempts it explicitly -- so a digit inside the
# placeholder's own name (e.g. the FIND section's "{y0}"/"{y1}") is not a
# digit-ban violation. Stripped before the scan below, same as this file's
# independent reimplementation in tests/test_narrative.py's
# `has_digit_violation` (kept in sync with that stripping behaviour, not with
# its literal regex source).
_PLACEHOLDER_RE = re.compile(r"\{[^{}]*\}")


def _iter_strings(value):
    """Every string inside a constant, however deeply nested. 's
    `METHODS` is a dict of {"title", "body"} sub-dicts, so a one-level-only
    walk would have skipped every Methods-page sentence:
    the scan must recurse or it goes vacuous exactly where the longest new
    copy lives. `tests/test_narrative.py` carries the same widening."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


def scan_for_digit_violations() -> list[tuple[str, str]]:
    """Every string constant above (dict values included), digits allowed only
    inside the allowlisted lens codes / top10 / PP(top10%) / a `{placeholder}`.
    Returns (constant_name, offending_value) pairs; empty list = PASS."""
    violations = []
    for name, value in globals().items():
        if name.startswith("_") or not name.isupper():
            continue
        for v in _iter_strings(value):
            cleaned = _PLACEHOLDER_RE.sub("", _ALLOWLIST_RE.sub("", v))
            if re.search(r"\d", cleaned):
                violations.append((name, v))
    return violations


if __name__ == "__main__":
    import sys

    bad = scan_for_digit_violations()
    if bad:
        print("DIGIT-BAN FAILURES:")
        for name, v in bad:
            print(f"  {name}: {v!r}")
        sys.exit(1)
    print("copy.py digit scan: PASS")
