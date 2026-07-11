"""Cheap pass: token-overlap entailment plus surface checks.

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
        "whose", "he", "she", "they", "we", "you", "i",
    ]
)
_WORD = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
# Digits preceded by a letter (Q3, FY26) are labels, not quantities.
_NUMBER = re.compile(r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)*%?")
_CITATION = re.compile(r"\[\d+\]|\([A-Z][A-Za-z-]+(?: et al\.)?,? \d{4}\)")
# Sentence boundary = terminal punctuation followed by whitespace, so decimal
# amounts like "$4.1M" are never split apart.
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# "not"/"no" used to be stopwords (stripped before scoring), which meant a
# flipped claim like "revenue did not increase" could score as strongly
# supported against a source stating the opposite — token overlap alone
# can't see a polarity flip. Detected separately via _is_negated below, and
# no longer filtered out of the token set either (see _STOPWORDS above).
_NEGATION = re.compile(r"\b(?:not|never|cannot|no|none|nobody|nothing|neither|nor)\b|\w+n't\b")

_SUFFIXES = ("ing", "ies", "ed", "es", "s")


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


def _stem(token: str) -> str:
    """Lossy suffix stripping so tense/inflection variants overlap (e.g.
    increase/increased/increases/increasing all reduce to the same stem).

    Deliberately simple, not linguistically correct — collisions between
    unrelated words are an acceptable trade-off since this only feeds a
    cheap pre-filter, never the final verdict.
    """
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)]
            if suffix == "ies":
                return token + "y"
            break
    return token[:-1] if token.endswith("e") and len(token) > 3 else token


def _tokens(text: str) -> set[str]:
    return {_stem(t) for t in _WORD.findall(text.lower()) if t not in _STOPWORDS}


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip("%") for n in _NUMBER.findall(text)}


def _is_negated(text: str) -> bool:
    return bool(_NEGATION.search(text.lower()))


def _overlap(claim_tokens: set[str], doc_tokens: set[str]) -> float:
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & doc_tokens) / len(claim_tokens)


def split_sentences(text: str) -> list[str]:
    return _SENTENCE.split(text)


@dataclass(frozen=True)
class _IndexedSource:
    doc: SourceDocument
    tokens: set[str]
    sentences: list[tuple[str, set[str]]]


def _index_sources(sources: list[SourceDocument]) -> list[_IndexedSource]:
    """Precompute tokens once per source per /verify call, instead of
    recomputing the same document's tokens for every claim checked against
    it (previously O(claims x sources), redundantly re-tokenizing)."""
    return [
        _IndexedSource(
            doc=doc,
            tokens=_tokens(doc.text),
            sentences=[(s, _tokens(s)) for s in split_sentences(doc.text)],
        )
        for doc in sources
    ]


def _check_indexed(claim: str, indexed: list[_IndexedSource]) -> CheapCheck:
    claim_tokens = _tokens(claim)
    best_score, best_doc = 0.0, indexed[0].doc
    for src in indexed:
        score = _overlap(claim_tokens, src.tokens)
        if score > best_score:
            best_score, best_doc = score, src.doc

    # Surface check: the closest-matching source sentence must agree on
    # negation polarity. Only fires when a sentence match is confident
    # (clears the support threshold) — otherwise an unrelated sentence that
    # happens to contain "not" could cause a false flag.
    best_sentence, sentence_score = "", 0.0
    for src in indexed:
        for sentence, sentence_tokens in src.sentences:
            score = _overlap(claim_tokens, sentence_tokens)
            if score > sentence_score:
                sentence_score, best_sentence = score, sentence
    if sentence_score >= SUPPORT_THRESHOLD and _is_negated(claim) != _is_negated(best_sentence):
        return CheapCheck(
            claim=claim,
            supported=False,
            score=min(best_score, 0.3),
            source_id=None,
            reason="negation mismatch: claim's polarity contradicts the closest "
            "matching source sentence",
        )

    # Surface check: citation markers in the claim must exist in some source.
    # Runs before the number check — a fabricated "[7]" is a citation problem,
    # not a numeric one.
    for citation in _CITATION.findall(claim):
        if not any(citation in src.doc.text for src in indexed):
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
    for src in indexed:
        source_numbers |= _numbers(src.doc.text)
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


def check_claim(claim: str, sources: list[SourceDocument]) -> CheapCheck:
    """Score one claim against all source documents; best document wins.

    Convenience wrapper for single-claim use. `run_cheap_pass` indexes
    sources once and reuses that index across every claim in a request
    instead of re-tokenizing the same documents per claim.
    """
    return _check_indexed(claim, _index_sources(sources))


def run_cheap_pass(claims: list[str], sources: list[SourceDocument]) -> list[CheapCheck]:
    indexed = _index_sources(sources)
    return [_check_indexed(claim, indexed) for claim in claims]
