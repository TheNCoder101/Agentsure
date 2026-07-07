"""Claim extraction: decompose an output into atomic factual claims."""

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "Dr.", "Mr.", "Mrs.", "Ms.", "no.")

# Conjunctions along which a compound sentence is split into atomic claims.
_CLAUSE_SPLIT = re.compile(r",\s+(?:and|but|while|whereas)\s+")

_MIN_CLAIM_WORDS = 3


def _protect_abbreviations(text: str) -> str:
    for abbr in _ABBREVIATIONS:
        text = text.replace(abbr, abbr.replace(".", "\x00"))
    return text


def _restore_abbreviations(text: str) -> str:
    return text.replace("\x00", ".")


def extract_claims(output: str) -> list[str]:
    """Split output text into atomic factual claims.

    Sentences are split on terminal punctuation, then compound sentences are
    split along coordinating conjunctions. Fragments too short to assert a
    fact are dropped.
    """
    protected = _protect_abbreviations(output.strip())
    claims: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(protected):
        for clause in _CLAUSE_SPLIT.split(sentence):
            claim = _restore_abbreviations(clause).strip().strip(",;")
            if len(claim.split()) >= _MIN_CLAIM_WORDS:
                claims.append(claim)
    return claims
