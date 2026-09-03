"""
app/lib/links.py -- outbound OpenAlex/ROR deep links: the works link
carries the SAME server-side filters the harvest itself used, not just the
publication-year window an earlier card link had.
"""
from __future__ import annotations

from urllib.parse import quote

from lib.app_config import CFG

WORKS_BASE = "https://openalex.org/works"


def works_url(institution_id: str, *, years: tuple[int, int] | None = None,
             types: list[str] | None = None, has_doi: bool | None = None) -> str:
    """`https://openalex.org/works?filter=authorships.institutions.id:{id},
    publication_year:{y0}-{y1},type:t1|t2|.,has_doi:true` -- defaults from
    CFG (`window`, `corpus_types`, `openalex_filters.has_doi`); `|` is
    percent-encoded (`quote(filter_str, safe=":,-")`, a pattern shared with
    an earlier SIRIS Streamlit tool) so the
    link survives copy/paste and markdown rendering unbroken."""
    y0, y1 = years if years is not None else CFG["window"]
    type_list = types if types is not None else CFG["corpus_types"]
    doi = CFG["openalex_filters"]["has_doi"] if has_doi is None else has_doi
    filt = (f"authorships.institutions.id:{institution_id},"
           f"publication_year:{y0}-{y1},"
           f"type:{'|'.join(type_list)},"
           f"has_doi:{'true' if doi else 'false'}")
    return f"{WORKS_BASE}?filter={quote(filt, safe=':,-')}"


def copubs_url(institution_a: str, institution_b: str, *, years: tuple[int, int] | None = None,
               types: list[str] | None = None, has_doi: bool | None = None) -> str:
    """Co-publications between two institutions on OpenAlex (A7): the SAME `authorships.institutions.id` key repeated once per
    institution, comma-joined -- OpenAlex ANDs repeated filters on one key
    (VERIFIED with live `filter=` calls, $0.0008: A alone
    5,211 / B alone 8,827 / both keys repeated 174, Universite de Strasbourg x
    Aix-Marseille Universite, 2023). The `+` intersection form is FORBIDDEN
    `id:A+B` silently returns A's own count with HTTP 200, no error (#14)
    never build the filter that way here."""
    y0, y1 = years if years is not None else CFG["window"]
    type_list = types if types is not None else CFG["corpus_types"]
    doi = CFG["openalex_filters"]["has_doi"] if has_doi is None else has_doi
    filt = (f"authorships.institutions.id:{institution_a},"
           f"authorships.institutions.id:{institution_b},"
           f"publication_year:{y0}-{y1},"
           f"type:{'|'.join(type_list)},"
           f"has_doi:{'true' if doi else 'false'}")
    return f"{WORKS_BASE}?filter={quote(filt, safe=':,-')}"


TAXON_FILTER_KEY = {
    "topic": "primary_topic.id",
    "subfield": "primary_topic.subfield.id",
    "field": "primary_topic.field.id",
}
TAXON_LEVELS = tuple(TAXON_FILTER_KEY)

# The pair tables' counting basis --
# the default type filter for `copubs_taxon_url` below.
CORE_AR_TYPES = ["article", "review"]


def copubs_taxon_url(institution_a: str, institution_b: str, level: str, taxon_id,
                     *, years: tuple[int, int] | None = None, types: list[str] | None = None,
                     has_doi: bool | None = None) -> str:
    """CD3 -11(e): a pair's co-publications RESTRICTED to one taxon (a
    topic, subfield or field row of a pair table) -- the same repeated-
    key AND convention `copubs_url` already verified live (
    OpenAlex ANDs two `authorships.institutions.id:` filters, never a `+`
    union, #14), with ONE more repeated key added: `primary_topic.id:`,
    `primary_topic.subfield.id:` or `primary_topic.field.id:` depending on
    `level` -- OpenAlex's own taxonomy nesting on the work's PRIMARY topic,
    matching the pair tables' own `topic_id`/`field_id` grain (never the
    tree-specific `{tree}_subfield_id` BenchUp repairs internally: OpenAlex
    has no concept of BenchUp's repaired trees, so a SUBFIELD-level link uses
    the topic's OpenAlex-native subfield, a documented approximation on the
    conservative/original trees' repaired cells).

    Construct-only: no live call is
    made here or required before shipping -- the shape is verified against
    `copubs_url`'s own already-live-verified convention, not by a fresh probe."""
    if level not in TAXON_LEVELS:
        raise ValueError(f"level must be one of {TAXON_LEVELS}, got {level!r}")
    y0, y1 = years if years is not None else CFG["window"]
    # Default type filter is CORE-AR (articles+reviews), NOT the 5-type harvest
    # list: this builder exists only for the pair view's TABLE rows, whose every
    # displayed count is articles+reviews 2020-2024 (plan §2.1 "link count
    # == displayed count"; inspection finding I-2). Pass `types=` explicitly
    # for any other basis.
    type_list = types if types is not None else CORE_AR_TYPES
    doi = CFG["openalex_filters"]["has_doi"] if has_doi is None else has_doi
    filt = (f"authorships.institutions.id:{institution_a},"
           f"authorships.institutions.id:{institution_b},"
           f"{TAXON_FILTER_KEY[level]}:{taxon_id},"
           f"publication_year:{y0}-{y1},"
           f"type:{'|'.join(type_list)},"
           f"has_doi:{'true' if doi else 'false'}")
    return f"{WORKS_BASE}?filter={quote(filt, safe=':,-')}"


def topic_url(institution_id: str, topic_id, *, years: tuple[int, int] | None = None,
              types: list[str] | None = None, has_doi: bool | None = None,
              sort: str | None = None) -> str:
    """Institution-in-topic: `https://openalex.org/works?
    filter=authorships.institutions.id:{I},primary_topic.id:{T},
    publication_year:2020-2024,type:article|review[,has_doi:true]` -- the
    shared-frontier table's `url_a`/`url_b`. Defaults CORE-AR (article,
    review) and the 2020-2024 window (`CFG['window']`), matching
    every other Compare-grain link in this module; `has_doi` still defaults
    from `CFG` (unchanged convention) even though the spec for this link
    does not spell it out. `sort` (e.g. `'cited_by_count:desc'`) is appended
    verbatim when given, unencoded (a plain `field:direction` token, safe as
    a query value)."""
    y0, y1 = years if years is not None else CFG["window"]
    type_list = types if types is not None else CORE_AR_TYPES
    doi = CFG["openalex_filters"]["has_doi"] if has_doi is None else has_doi
    filt = (f"authorships.institutions.id:{institution_id},"
           f"primary_topic.id:{topic_id},"
           f"publication_year:{y0}-{y1},"
           f"type:{'|'.join(type_list)},"
           f"has_doi:{'true' if doi else 'false'}")
    url = f"{WORKS_BASE}?filter={quote(filt, safe=':,-')}"
    return f"{url}&sort={sort}" if sort else url


def joint_topic_url(institution_a: str, institution_b: str, topic_id, *,
                    years: tuple[int, int] | None = None, types: list[str] | None = None,
                    has_doi: bool | None = None, sort: str | None = None) -> str:
    """, joint = both ids repeated in the SAME filter (the
    `copubs_taxon_url(., "topic",.)` shape, already live-verified) -- the shared-frontier mirror chart's own
    `url_joint` (feeds each y-tick's `<a href>`, `charts_compare.
    mirror_frontier`'s contract) and table `url_joint` column."""
    url = copubs_taxon_url(institution_a, institution_b, "topic", topic_id,
                           years=years, types=types, has_doi=has_doi)
    return f"{url}&sort={sort}" if sort else url


def joint_stars_url(institution_a: str, institution_b: str, *,
                    years: tuple[int, int] | None = None, types: list[str] | None = None,
                    has_doi: bool | None = None) -> str:
    """, joint-stars link: the pair's joint-publications
    filter (`copubs_url`, CORE-AR types by default -- NOT `CFG['corpus_
    types']`'s 5-type harvest list, since every star-paper figure this link
    backs is CORE-AR only) plus `sort=cited_by_count:desc`. The star-paper
    definition itself is a within-topic-year top-1% cut OpenAlex cannot
    filter on directly, so this is the honest "most cited first" proxy this
    link names, never a literal re-application of the percentile rule."""
    url = copubs_url(institution_a, institution_b, years=years,
                     types=(types if types is not None else CORE_AR_TYPES), has_doi=has_doi)
    return f"{url}&sort=cited_by_count:desc"


def ror_url(ror_id: str) -> str:
    """Accepts a bare ROR id (e.g. `03xyz1234`) or an already-full
    `https://ror.org/.` URL (index.parquet ships the full URL -- this stays
    a no-op passthrough for that shape, and builds the URL for a bare id)."""
    ror_id = ror_id.strip()
    return ror_id if ror_id.startswith("http") else f"https://ror.org/{ror_id}"


# share_link_block moved to lib/selection.py: it is a
# Streamlit UI element, and this module is on test_narrative's pure-module
# list (no streamlit import, checked over the whole AST).
