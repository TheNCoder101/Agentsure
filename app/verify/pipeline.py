"""Verification pipeline: claims -> cheap pass -> (escalation) -> aggregate.

Cost tiering per spec: `fast` runs the cheap pass only; `standard` escalates
flagged claims to the judge; `strict` adds self-consistency sampling. Claims
that pass the cheap pass are NEVER sent to the judge.
"""

from dataclasses import dataclass

from app.models import ClaimEvidence, RigorLevel, SourceDocument, UnsupportedClaim, Verdict
from app.verify.cheap import run_cheap_pass
from app.verify.claims import extract_claims
from app.verify.judge import JudgeClient, self_consistent_judge

STRICT_SAMPLES = 3


@dataclass(frozen=True)
class VerificationResult:
    verdict: Verdict
    unsupported_claims: list[UnsupportedClaim]
    per_claim_evidence: list[ClaimEvidence]
    confidence: float


def run_verification(
    output: str,
    sources: list[SourceDocument],
    rigor_level: RigorLevel,
    judge_client: JudgeClient,
) -> VerificationResult:
    claims = extract_claims(output)
    if not claims:
        # Fail closed: an output with no extractable factual claims cannot be
        # attested as grounded.
        return VerificationResult(
            verdict=Verdict.UNSUPPORTED,
            unsupported_claims=[
                UnsupportedClaim(
                    claim=output, reason="no verifiable atomic claims could be extracted"
                )
            ],
            per_claim_evidence=[],
            confidence=0.0,
        )

    evidence: list[ClaimEvidence] = []
    unsupported: list[UnsupportedClaim] = []
    claim_confidences: list[float] = []

    for check in run_cheap_pass(claims, sources):
        supported, score, reason = check.supported, check.score, check.reason

        if check.flagged and rigor_level is not RigorLevel.FAST:
            if rigor_level is RigorLevel.STRICT:
                verdict = self_consistent_judge(
                    judge_client, check.claim, sources, samples=STRICT_SAMPLES
                )
            else:
                verdict = judge_client.judge(check.claim, sources)
            supported = verdict.supported
            score = max(0.0, min(1.0, verdict.confidence))
            reason = verdict.reason

        evidence.append(
            ClaimEvidence(
                claim=check.claim,
                supported=supported,
                source_id=check.source_id if supported else None,
                score=round(score, 4),
            )
        )
        if supported:
            claim_confidences.append(score)
        else:
            unsupported.append(UnsupportedClaim(claim=check.claim, reason=reason))
            claim_confidences.append(1.0 - score)

    if not unsupported:
        verdict_value = Verdict.SUPPORTED
    elif len(unsupported) == len(claims):
        verdict_value = Verdict.UNSUPPORTED
    else:
        verdict_value = Verdict.PARTIALLY_SUPPORTED

    confidence = round(sum(claim_confidences) / len(claim_confidences), 4)
    return VerificationResult(
        verdict=verdict_value,
        unsupported_claims=unsupported,
        per_claim_evidence=evidence,
        confidence=max(0.0, min(1.0, confidence)),
    )
