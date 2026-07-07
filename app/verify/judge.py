"""LLM-as-judge escalation for flagged claims.

The judge is behind a Protocol so tests inject spies and production can swap
in a real LLM client without touching the pipeline. Only flagged claims are
ever passed to a judge — enforced by the pipeline, asserted by tests.
"""

import re
from dataclasses import dataclass
from typing import Protocol

from app.models import SourceDocument
from app.verify.cheap import SUPPORT_THRESHOLD, _tokens

# Sentence boundary = terminal punctuation followed by whitespace, so decimal
# amounts like "$4.1M" are never split apart.
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class JudgeVerdict:
    supported: bool
    confidence: float
    reason: str


class JudgeClient(Protocol):
    def judge(self, claim: str, sources: list[SourceDocument]) -> JudgeVerdict: ...


class HeuristicJudge:
    """Deterministic stand-in for an LLM judge.

    Re-examines a flagged claim with a more permissive containment check
    (any single source sentence covering most of the claim). Replace with an
    Anthropic-backed client for production semantic judging.
    """

    def judge(self, claim: str, sources: list[SourceDocument]) -> JudgeVerdict:
        claim_tokens = _tokens(claim)
        if not claim_tokens:
            return JudgeVerdict(supported=False, confidence=0.5, reason="empty claim")
        best = 0.0
        for doc in sources:
            for sentence in _SENTENCE.split(doc.text):
                tokens = _tokens(sentence)
                if tokens:
                    best = max(best, len(claim_tokens & tokens) / len(claim_tokens))
        if best >= SUPPORT_THRESHOLD:
            return JudgeVerdict(
                supported=True, confidence=best, reason="evidence found on closer read"
            )
        return JudgeVerdict(
            supported=False,
            confidence=1.0 - best,
            reason="no source sentence substantiates the claim",
        )


def self_consistent_judge(
    client: JudgeClient, claim: str, sources: list[SourceDocument], samples: int = 3
) -> JudgeVerdict:
    """Strict rigor: majority vote over multiple judge samples."""
    verdicts = [client.judge(claim, sources) for _ in range(samples)]
    supporting = [v for v in verdicts if v.supported]
    majority = supporting if len(supporting) * 2 > len(verdicts) else [
        v for v in verdicts if not v.supported
    ]
    confidence = sum(v.confidence for v in majority) / len(majority)
    agreement = len(majority) / len(verdicts)
    return JudgeVerdict(
        supported=majority[0].supported,
        confidence=confidence * agreement,
        reason=majority[0].reason,
    )
