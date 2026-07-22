"""Deterministic UK-English proofing findings for human QC review."""

import re
from itertools import pairwise
from uuid import uuid4

from coeus.domain.product_submission import DraftProductVersion
from coeus.domain.qc import QcAgentFinding

MAX_FINDINGS = 100
CORRECTIONS = {
    "accomodate": "accommodate",
    "acheive": "achieve",
    "adress": "address",
    "alot": "a lot",
    "analisis": "analysis",
    "assessement": "assessment",
    "calender": "calendar",
    "colleciton": "collection",
    "definately": "definitely",
    "enviroment": "environment",
    "existance": "existence",
    "foriegn": "foreign",
    "goverment": "government",
    "independant": "independent",
    "inteligence": "intelligence",
    "occurence": "occurrence",
    "recieve": "receive",
    "relevent": "relevant",
    "seperate": "separate",
    "sucess": "success",
    "thier": "their",
    "untill": "until",
}
WORD = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")


def proofing_findings(draft: DraftProductVersion) -> tuple[QcAgentFinding, ...]:
    sections = (
        ("title", draft.title),
        ("summary", draft.summary),
        ("description", draft.description),
        ("extracted product text", draft.content),
    )
    findings: list[QcAgentFinding] = [
        _finding(
            "proofing_coverage",
            asset.name,
            "Human review required",
            f"asset {asset.name}",
            "No text was extracted from this image, so automated spelling checks could not "
            "inspect words rendered inside it.",
        )
        for asset in draft.assets
        if asset.preview_kind == "image" and not asset.extracted_text.strip()
    ]
    for location, text in sections:
        findings.extend(_spelling(location, text))
        findings.extend(_repeated_words(location, text))
        if len(findings) >= MAX_FINDINGS:
            break
    return tuple(findings[:MAX_FINDINGS])


def _spelling(location: str, text: str) -> list[QcAgentFinding]:
    results: list[QcAgentFinding] = []
    for match in WORD.finditer(text):
        original = match.group(0)
        suggestion = CORRECTIONS.get(original.casefold())
        if suggestion:
            results.append(
                _finding(
                    "spelling",
                    original,
                    _match_case(original, suggestion),
                    f"{location}, character {match.start() + 1}",
                    "Possible UK-English spelling error. Human confirmation is required.",
                )
            )
    return results


def _repeated_words(location: str, text: str) -> list[QcAgentFinding]:
    words = list(WORD.finditer(text))
    return [
        _finding(
            "grammar",
            f"{left.group(0)} {right.group(0)}",
            left.group(0),
            f"{location}, character {left.start() + 1}",
            "Possible duplicated word. Human confirmation is required.",
        )
        for left, right in pairwise(words)
        if left.group(0).casefold() == right.group(0).casefold()
    ]


def _finding(
    category: str, original: str, suggestion: str, location: str, detail: str
) -> QcAgentFinding:
    return QcAgentFinding(
        finding_id=uuid4(),
        category=category,
        severity="warning",
        original_text=original,
        suggested_text=suggestion,
        location=location,
        detail=detail,
        confidence=0.9,
        blocking=False,
    )


def _match_case(original: str, suggestion: str) -> str:
    if original.isupper():
        return suggestion.upper()
    if original[:1].isupper():
        return suggestion[:1].upper() + suggestion[1:]
    return suggestion
