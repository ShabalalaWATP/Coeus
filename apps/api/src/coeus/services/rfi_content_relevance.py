"""Score an offer on the report's own words rather than its cover metadata.

Title and summary say what a product is called. The retrieved passages say what
it contains, which is the only thing that answers "does this actually address
the request". Scoring here is deterministic and reads nothing beyond the
passages retrieval already returned.
"""

from coeus.domain.search_index import SearchPassage
from coeus.domain.search_relevance import matched_tokens
from coeus.domain.store_ranking import tokenize

# Enough passages to judge coverage without turning ranking into a scan.
RFI_PASSAGE_WORK_LIMIT = 12


def content_relevance(
    passages: tuple[SearchPassage, ...],
    query_tokens: tuple[str, ...],
    question_tokens: tuple[str, ...],
) -> tuple[float, tuple[str, ...]]:
    """Return how far the retrieved text answers the request, with its reasons.

    Three things matter, in order. Whether the operational question is covered,
    because that is what the requester actually asked. Whether the request is
    covered across the report as a whole. And whether any single passage carries
    enough of it to be worth reading, which separates a report that addresses
    the subject from one that mentions it in passing.
    """
    if not passages or not query_tokens:
        return 0.0, ()
    bounded = passages[:RFI_PASSAGE_WORK_LIMIT]
    excerpt_tokens = [tokenize(passage.excerpt) for passage in bounded]
    combined = tuple(token for tokens in excerpt_tokens for token in tokens)
    if not combined:
        return 0.0, ()
    breadth = len(matched_tokens(query_tokens, combined)) / len(query_tokens)
    depth = max(
        (
            len(matched_tokens(query_tokens, tokens)) / len(query_tokens)
            for tokens in excerpt_tokens
        ),
        default=0.0,
    )
    answers = (
        len(matched_tokens(question_tokens, combined)) / len(question_tokens)
        if question_tokens
        else breadth
    )
    score = min(1.0, (0.45 * answers) + (0.35 * breadth) + (0.20 * depth))
    return score, _reasons(len(bounded), answers, breadth, depth)


def _reasons(count: int, answers: float, breadth: float, depth: float) -> tuple[str, ...]:
    reasons = [f"content:passages-{count}"]
    if answers >= 0.5:
        reasons.append("content:answers-question")
    if depth >= 0.5:
        reasons.append("content:passage-covers-request")
    elif breadth >= 0.5:
        reasons.append("content:report-covers-request")
    return tuple(reasons)
