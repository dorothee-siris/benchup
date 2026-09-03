"""
app/lib/search.py -- accent-insensitive seed search over the institution index. Stdlib only (no rapidfuzz, no unidecode):
NFKD accent strip + casefold, then a WORD-TOKEN match hierarchy with a
difflib token-level fuzzy fallback for typos.

Why token-level, not whole-string, prefix/substring: naive whole-string `startswith` ranks
"Gdansk University of Physical Education" ABOVE "University of Gdansk" for
the query "gdansk" (the second is only a whole-string substring), which is
the wrong read -- the user typed the INSTITUTION's name as a whole WORD, not
a string prefix of an arbitrary field. Matching whether the query is a whole
token (exact) or a token-prefix inside the field puts every institution that
contains "Gdansk" as a real word in the same top tier, where the existing
"ties by total_full desc" rule then does the right thing (University of
Gdansk, 8,786 works, outranks the four smaller Gdansk-named institutions).
Whole-name difflib was measured to return junk for a typo -- the
fuzzy fallback below runs difflib per QUERY TOKEN against a vocabulary of
institution-name TOKENS, then substring-matches the returned token(s), never
the raw multi-word name.
"""
from __future__ import annotations

import unicodedata
from difflib import get_close_matches

import pandas as pd

_SEARCH_FIELDS = ["display_name", "display_name_acronyms", "display_name_alternatives"]
_PRIORITY = {"exact": 0, "prefix": 1, "substring": 2, "fuzzy": 3}

# Module-level token vocabulary
# rebuilt every time `build_search_index` runs; `search`'s fuzzy fallback
# reads it directly rather than taking it as a parameter.
_TOKEN_VOCAB: set[str] = set()


def normalize(text) -> str:
    """NFKD -> strip combining marks -> casefold. None/NaN/"" -> ""."""
    if not isinstance(text, str) or not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold()


def build_search_index(index_df: pd.DataFrame) -> list[tuple]:
    """One entry per (institution, name/acronym/alternative TEXT), each tagged
    with its institution_id and total_full_2020_2024 (the tie-break key).
    `display_name_alternatives` is pipe-split into one entry per alternative
    name. Also rebuilds the module-level token vocabulary `search` uses for
    its fuzzy fallback."""
    global _TOKEN_VOCAB
    entries: list[tuple] = []
    vocab: set[str] = set()
    for row in index_df[[*_SEARCH_FIELDS, "institution_id", "display_name",
                          "country_code", "type", "total_full_2020_2024"]].itertuples(index=False):
        iid, disp = row.institution_id, row.display_name
        country, type_ = str(row.country_code), str(row.type)
        total = row.total_full_2020_2024
        for field in _SEARCH_FIELDS:
            raw = getattr(row, field)
            if not isinstance(raw, str) or not raw:
                continue
            for part in raw.split("|"):
                norm = normalize(part)
                if not norm:
                    continue
                entries.append((iid, norm, disp, country, type_, total))
                vocab.update(norm.split())
    _TOKEN_VOCAB = vocab
    return entries


def _match_kind(norm_query: str, norm_text: str) -> str | None:
    """exact = the query IS the whole field text or one whole word of it;
    prefix = the query is the start of one word of it (or of the whole
    field, for a multi-word query); substring = present anywhere else."""
    if norm_text == norm_query:
        return "exact"
    tokens = norm_text.split()
    if norm_query in tokens:
        return "exact"
    if norm_text.startswith(norm_query) or any(t.startswith(norm_query) for t in tokens):
        return "prefix"
    if norm_query in norm_text:
        return "substring"
    return None


def search(query: str, idx: list[tuple], k: int = 10) -> list[dict]:
    """rank = exact > prefix > substring, ties by total_full_2020_2024 desc;
    if fewer than k hits, fuzzy fallback = difflib.get_close_matches per query
    TOKEN against the vocabulary (cutoff 0.8), then substring on the matched
    token(s) -- never whole-name difflib.
    One institution_id appears once (its single BEST-tier hit)."""
    norm_query = normalize(query)
    best: dict[str, dict] = {}

    def _consider(iid, kind, disp, country, type_, total):
        cur = best.get(iid)
        if cur is None or _PRIORITY[kind] < _PRIORITY[cur["match_kind"]]:
            best[iid] = {"id": iid, "display_name": disp, "country_code": country,
                        "type": type_, "total_full_2020_2024": total, "match_kind": kind}

    if not norm_query:
        return []

    for iid, norm_text, disp, country, type_, total in idx:
        kind = _match_kind(norm_query, norm_text)
        if kind:
            _consider(iid, kind, disp, country, type_, total)

    if len(best) < k:
        matched_tokens: set[str] = set()
        for tok in norm_query.split():
            matched_tokens.update(get_close_matches(tok, _TOKEN_VOCAB, n=5, cutoff=0.8))
        if matched_tokens:
            for iid, norm_text, disp, country, type_, total in idx:
                if iid in best:
                    continue
                if any(t in norm_text for t in matched_tokens):
                    _consider(iid, "fuzzy", disp, country, type_, total)

    ranked = sorted(best.values(),
                     key=lambda h: (_PRIORITY[h["match_kind"]], -(h["total_full_2020_2024"] or 0)))
    return ranked[:k]
