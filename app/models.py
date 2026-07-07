"""Request/response models for the verification gate, per specs/verification-gate.md."""

from enum import StrEnum

from pydantic import BaseModel, Field


class RigorLevel(StrEnum):
    FAST = "fast"
    STANDARD = "standard"
    STRICT = "strict"


class Verdict(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    PARTIALLY_SUPPORTED = "partially_supported"


class SourceDocument(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class VerifyRequest(BaseModel):
    output: str = Field(min_length=1)
    source_documents: list[SourceDocument] = Field(min_length=1)
    rigor_level: RigorLevel = RigorLevel.STANDARD


class UnsupportedClaim(BaseModel):
    claim: str
    reason: str


class ClaimEvidence(BaseModel):
    claim: str
    supported: bool
    source_id: str | None
    score: float = Field(ge=0.0, le=1.0)


class Receipt(BaseModel):
    receipt_id: str
    issued_at: str
    verdict: Verdict
    output_sha256: str
    sources_sha256: list[str]
    rigor_level: RigorLevel
    engine_version: str
    signature: str


class VerifyResponse(BaseModel):
    verdict: Verdict
    unsupported_claims: list[UnsupportedClaim]
    per_claim_evidence: list[ClaimEvidence]
    confidence: float = Field(ge=0.0, le=1.0)
    receipt: Receipt


class ReceiptVerifyResponse(BaseModel):
    valid: bool
