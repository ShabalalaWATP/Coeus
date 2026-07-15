"""Pure lexical ranking policy shared by Store adapters and RFI services."""

from re import findall

from coeus.domain.search_relevance import matched_tokens, token_sets_overlap
from coeus.domain.store import StoreProduct
from coeus.domain.store_semantics import product_semantic_text

STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "in",
        "is",
        "mock",
        "of",
        "on",
        "or",
        "synthetic",
        "the",
        "to",
        "what",
        "with",
    }
)


def tokenize(text: str) -> tuple[str, ...]:
    """Return distinct, normalised retrieval tokens in source order."""
    return tuple(
        dict.fromkeys(
            token
            for token in findall(r"[a-z0-9]+", text.casefold())
            if len(token) >= 2 and token not in STOP_WORDS
        )
    )


def token_overlap(left: str, right: str) -> bool:
    return token_sets_overlap(tokenize(left), tokenize(right))


def lexical_text_score(query: str, document: str) -> float:
    """Return the fraction of distinct query tokens present in a document."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0
    matches = matched_tokens(query_tokens, tokenize(document))
    return min(len(matches) / len(query_tokens), 1.0)


def lexical_score_for_product(product: StoreProduct, query: str) -> float:
    metadata = product.metadata
    normalised_query = " ".join(tokenize(query))
    normalised_title = " ".join(tokenize(metadata.title))
    if normalised_query and normalised_query == normalised_title:
        return 1.0
    title_score = lexical_text_score(query, metadata.title)
    labelled_score = lexical_text_score(
        query, " ".join((*sorted(metadata.tags), *sorted(metadata.semantic_labels)))
    )
    full_score = lexical_text_score(query, product_semantic_text(product))
    return min(1.0, (0.50 * title_score) + (0.30 * labelled_score) + (0.20 * full_score))
