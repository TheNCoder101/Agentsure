"""Cheap pass: semantic-overlap entailment plus surface checks.

Runs on every claim regardless of rigor level. Claims that fail here are
"flagged" — only flagged claims may be escalated to the LLM judge.
"""

import re
from dataclasses import dataclass

from app.models import SourceDocument

SUPPORT_THRESHOLD = 0.55

_STOPWORDS = frozenset(
    [
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
        "has", "have", "in", "is", "it", "its", "of", "on", "or", "that", "the",
        "this", "to", "was", "were", "will", "with", "which", "who", "whom",
        "whose", "he", "she", "they", "we", "you", "i", "not", "no",
    ]
)
_WORD = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
# Digits preceded by a letter (Q3, FY26) are labels, not quantities.
_NUMBER = re.compile(r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)*%?")
_CITATION = re.compile(r"\[\d+\]|\([A-Z][A-Za-z-]+(?: et al\.)?,? \d{4}\)")


@dataclass(frozen=True)
class CheapCheck:
    claim: str
    supported: bool
    score: float
    source_id: str | None
    reason: str

    @property
    def flagged(self) -> bool:
        return not self.supported


def _tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if t not in _STOPWORDS}


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip("%") for n in _NUMBER.findall(text)}


def _overlap(claim_tokens: set[str], doc_tokens: set[str]) -> float:
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & doc_tokens) / len(claim_tokens)


def check_claim(claim: str, sources: list[SourceDocument]) -> CheapCheck:
    """Score one claim against all source documents; best document wins."""
    claim_tokens = _tokens(claim)
    best_score, best_doc = 0.0, sources[0]
    for doc in sources:
        score = _overlap(claim_tokens, _tokens(doc.text))
        if score > best_score:
            best_score, best_doc = score, doc

    # Surface check: citation markers in the claim must exist in some source.
    # Runs before the number check — a fabricated "[7]" is a citation problem,
    # not a numeric one.
    for citation in _CITATION.findall(claim):
        if not any(citation in doc.text for doc in sources):
            return CheapCheck(
                claim=claim,
                supported=False,
                score=min(best_score, 0.4),
                source_id=None,
                reason=f"fabricated citation pattern: {citation} not present in any source",
            )

    # Surface check: every number in the claim must appear in some source.
    claim_numbers = _numbers(claim)
    source_numbers: set[str] = set()
    for doc in sources:
        source_numbers |= _numbers(doc.text)
    missing_numbers = claim_numbers - source_numbers
    if missing_numbers:
        return CheapCheck(
            claim=claim,
            supported=False,
            score=min(best_score, 0.4),
            source_id=best_doc.id if best_score > 0 else None,
            reason=f"number mismatch: {', '.join(sorted(missing_numbers))} not found in sources",
        )

    if best_score >= SUPPORT_THRESHOLD:
        return CheapCheck(
            claim=claim, supported=True, score=best_score, source_id=best_doc.id, reason=""
        )
    return CheapCheck(
        claim=claim,
        supported=False,
        score=best_score,
        source_id=best_doc.id if best_score > 0 else None,
        reason="insufficient evidence overlap with any source document",
    )


def run_cheap_pass(claims: list[str], sources: list[SourceDocument]) -> list[CheapCheck]:
    return [check_claim(claim, sources) for claim in claims]
