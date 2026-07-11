"""LLM-as-judge escalation for flagged claims.

The judge is behind a Protocol so tests inject spies and production can swap
in a real LLM client without touching the pipeline. Only flagged claims are
ever passed to a judge — enforced by the pipeline, asserted by tests.
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
from anthropic.types import TextBlock

from app.models import SourceDocument
from app.verify.cheap import SUPPORT_THRESHOLD, _tokens, split_sentences

DEFAULT_JUDGE_MODEL = "claude-sonnet-5"

_JUDGE_SYSTEM_PROMPT = (
    "You are a strict fact-checking judge. Given a CLAIM and one or more SOURCE "
    "documents, decide whether the claim is directly supported by the sources — "
    "explicitly stated or trivially entailed, never by outside knowledge or "
    "assumption. Respond with ONLY a single-line JSON object of the form "
    '{"supported": true|false, "confidence": <0.0-1.0>, "reason": "<one sentence>"}. '
    "No prose outside the JSON object."
)


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
            for sentence in split_sentences(doc.text):
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


class AnthropicJudge:
    """LLM-as-judge backed by the Anthropic Messages API.

    Only claims flagged by the cheap pass ever reach this client (enforced by
    the pipeline). Fails closed: an API error or an unparsable response is
    treated as unsupported with zero confidence, so a judge outage can never
    manufacture grounding evidence that doesn't exist.
    """

    def __init__(
        self, client: anthropic.Anthropic | None = None, model: str = DEFAULT_JUDGE_MODEL
    ) -> None:
        self._client = client or anthropic.Anthropic()
        self._model = model

    def judge(self, claim: str, sources: list[SourceDocument]) -> JudgeVerdict:
        source_block = "\n\n".join(f"[{doc.id}]\n{doc.text}" for doc in sources)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=200,
                system=_JUDGE_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": f"CLAIM: {claim}\n\nSOURCES:\n{source_block}"}
                ],
            )
        except anthropic.APIError as exc:
            return JudgeVerdict(
                supported=False, confidence=0.0, reason=f"judge unavailable: {exc}"
            )
        text = "".join(
            block.text for block in response.content if isinstance(block, TextBlock)
        )
        return _parse_judge_response(text)


def _parse_judge_response(text: str) -> JudgeVerdict:
    try:
        data: dict[str, Any] = json.loads(text.strip())
        return JudgeVerdict(
            supported=bool(data["supported"]),
            confidence=max(0.0, min(1.0, float(data["confidence"]))),
            reason=str(data["reason"])[:300],
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return JudgeVerdict(
            supported=False, confidence=0.0, reason="judge response unparsable"
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
