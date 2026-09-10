"""
 lib/links.py acceptance tests (.2 L23).
Run: python -m pytest tests/test_links.py -q
"""
from __future__ import annotations

from urllib.parse import unquote

import pytest

from lib.links import (MAX_STAR_IDS_PER_URL, copubs_taxon_url, copubs_url, joint_stars_url,
                       joint_topic_url, ror_url, star_ids_url, topic_url, works_url)


def test_works_url_contains_all_four_filters_and_no_raw_pipe():
    url = works_url("I40413290")
    assert "|" not in url, "raw pipe leaked into the URL unencoded"
    decoded = unquote(url)
    assert "authorships.institutions.id:I40413290" in decoded
    assert "publication_year:2020-2024" in decoded
    assert "type:article|review|book|book-chapter|letter" in decoded
    assert "has_doi:true" in decoded


def test_works_url_overrides():
    url = works_url("I1", years=(2015, 2019), types=["article"], has_doi=False)
    decoded = unquote(url)
    assert "publication_year:2015-2019" in decoded
    assert "type:article" in decoded
    assert "has_doi:false" in decoded


def test_ror_url_bare_and_full():
    assert ror_url("03xyz1234") == "https://ror.org/03xyz1234"
    assert ror_url("https://ror.org/03xyz1234") == "https://ror.org/03xyz1234"


def test_copubs_url_comma_form_and_no_plus():
    """A7 / measurement #13-14: the co-publications filter repeats the SAME key
    (`authorships.institutions.id`) once per institution, comma-joined
    OpenAlex ANDs repeated filters on one key. The `+` intersection form is
    FORBIDDEN (it silently returns the first id's own count, HTTP 200, no
    error) -- assert it never appears in the built URL."""
    url = copubs_url("I68947357", "I21491767")
    assert "+" not in url, "the `+` intersection form leaked into the URL -- it is silently wrong"
    decoded = unquote(url)
    assert "authorships.institutions.id:I68947357" in decoded
    assert "authorships.institutions.id:I21491767" in decoded
    assert decoded.count("authorships.institutions.id:") == 2
    assert "publication_year:2020-2024" in decoded
    assert "type:article|review|book|book-chapter|letter" in decoded
    assert "has_doi:true" in decoded


def test_copubs_url_overrides():
    url = copubs_url("I1", "I2", years=(2023, 2023), types=["article"], has_doi=False)
    decoded = unquote(url)
    assert "publication_year:2023-2023" in decoded
    assert "type:article" in decoded
    assert "has_doi:false" in decoded
    assert "+" not in url


# ------------------------------------------------- copubs_taxon_url (CD3) ----

@pytest.mark.parametrize("level,key", [
    ("topic", "primary_topic.id"),
    ("subfield", "primary_topic.subfield.id"),
    ("field", "primary_topic.field.id"),
])
def test_copubs_taxon_url_shape_per_level(level, key):
    """-11(e): the pair filter PLUS one more repeated key naming the
    taxon on the work's PRIMARY topic -- verified by construction against
    `copubs_url`'s own already-live-verified convention."""
    url = copubs_taxon_url("I68947357", "I21491767", level, "T12345")
    assert "+" not in url
    decoded = unquote(url)
    assert decoded.count("authorships.institutions.id:") == 2
    assert "authorships.institutions.id:I68947357" in decoded
    assert "authorships.institutions.id:I21491767" in decoded
    assert f"{key}:T12345" in decoded
    assert "publication_year:2020-2024" in decoded
    # CORE-AR default: a taxon link sits
    # beside an articles+reviews table count and must return that same count
    # never the 5-type harvest list works_url/copubs_url default to.
    assert "type:article|review," in decoded
    assert "book" not in decoded
    assert "has_doi:true" in decoded


def test_copubs_taxon_url_field_id_is_an_int():
    """A field/subfield taxon_id is an int (topics_dim.field_id/subfield_id,
    not a topic string) -- the builder must not choke on it."""
    url = copubs_taxon_url("I68947357", "I21491767", "field", 31)
    assert "primary_topic.field.id:31" in unquote(url)


def test_copubs_taxon_url_rejects_unknown_level():
    with pytest.raises(ValueError):
        copubs_taxon_url("I1", "I2", "bogus", "T1")


def test_copubs_taxon_url_overrides():
    url = copubs_taxon_url("I1", "I2", "topic", "T1", years=(2023, 2023), types=["article"], has_doi=False)
    decoded = unquote(url)
    assert "publication_year:2023-2023" in decoded
    assert "type:article" in decoded
    assert "has_doi:false" in decoded
    assert "+" not in url


# --------------------------------------------- topic_url / joint_topic_url ---
# : institution-in-topic and joint-in-topic
# links for the shared-frontier table/mirror chart.

def test_topic_url_shape():
    url = topic_url("I154202486", "T10753")
    decoded = unquote(url)
    assert decoded.count("authorships.institutions.id:") == 1
    assert "authorships.institutions.id:I154202486" in decoded
    assert "primary_topic.id:T10753" in decoded
    assert "publication_year:2020-2024" in decoded
    assert "type:article|review," in decoded  # CORE-AR default, not the 5-type harvest list
    assert "book" not in decoded
    assert "has_doi:true" in decoded
    assert "sort=" not in url


def test_topic_url_sort_appended_unencoded():
    url = topic_url("I1", "T1", sort="cited_by_count:desc")
    assert url.endswith("&sort=cited_by_count:desc")


def test_joint_topic_url_shape_matches_copubs_taxon_url_topic_level():
    """"joint = both ids in the same filter": `joint_topic_url` must be
    the SAME shape `copubs_taxon_url(., "topic",.)` already ships
    (the measured, live-verified AND convention) -- checked here
    by direct string equality (minus an optional `sort` suffix), not just by
    re-testing the individual filter pieces."""
    a = joint_topic_url("I154202486", "I4210107283", "T10753")
    b = copubs_taxon_url("I154202486", "I4210107283", "topic", "T10753")
    assert a == b
    decoded = unquote(a)
    assert decoded.count("authorships.institutions.id:") == 2
    assert "primary_topic.id:T10753" in decoded
    assert "+" not in a


def test_joint_topic_url_sort_appended():
    url = joint_topic_url("I1", "I2", "T1", sort="cited_by_count:desc")
    assert url.endswith("&sort=cited_by_count:desc")


# ------------------------------------------------------------ joint_stars ---

# --------------------------------------------------------------- star_ids_url
# The balance bars' star-mode link column -- a concatenated OpenAlex
# work-id list, percent-encoded the SAME way every other builder in this
# module does.

def test_star_ids_url_shape_and_no_raw_pipe():
    url = star_ids_url(["W1", "W2", "W3"])
    assert "|" not in url, "raw pipe leaked into the URL unencoded"
    decoded = unquote(url)
    assert decoded == "https://openalex.org/works?filter=ids.openalex:W1|W2|W3"
    assert url.startswith("https://openalex.org/works?filter=")


def test_star_ids_url_strips_full_urls_to_bare_ids():
    url = star_ids_url(["https://openalex.org/W1", "W2"])
    decoded = unquote(url)
    assert decoded == "https://openalex.org/works?filter=ids.openalex:W1|W2"


def test_star_ids_url_sort_appended():
    url = star_ids_url(["W1"], sort="cited_by_count:desc")
    assert url.endswith("&sort=cited_by_count:desc")


def test_star_ids_url_cap_is_a_hundred():
    ok = star_ids_url([f"W{i}" for i in range(MAX_STAR_IDS_PER_URL)])
    assert ok  # exactly at the cap: no error
    with pytest.raises(ValueError):
        star_ids_url([f"W{i}" for i in range(MAX_STAR_IDS_PER_URL + 1)])


def test_joint_stars_url_core_ar_and_sort():
    """Joint-stars link: the joint filter, CORE-AR types (never the
    5-type harvest list `copubs_url` defaults to), sorted most-cited-first
    the honest proxy for the top-1%-within-topic-year star definition,
    which OpenAlex cannot filter on directly."""
    url = joint_stars_url("I154202486", "I4210107283")
    assert url.endswith("&sort=cited_by_count:desc")
    decoded = unquote(url)
    assert decoded.count("authorships.institutions.id:") == 2
    assert "type:article|review," in decoded
    assert "book" not in decoded
    assert "publication_year:2020-2024" in decoded
    assert "+" not in url
