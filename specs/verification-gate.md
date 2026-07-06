# SPEC — Verification Gate MVP (source of truth)

## Problem
A regulated business cannot let an agent act in high-value workflows because it
has no way to prove — to its risk team, auditors, or regulator — that a given
output was independently grounded in real evidence before it was acted on. We
sell that proof.

## MVP scope (what v1 must do, nothing more)
A single service exposing `POST /verify`. It decides whether an agent's output
is supported by supplied source evidence, and emits a signed audit receipt.

### Endpoint contract
`POST /verify`

Request:
```json
{
  "output": "string — the agent's proposed output/answer",
  "source_documents": [
    { "id": "doc-1", "text": "string — evidence the output must be grounded in" }
  ],
  "rigor_level": "fast | standard | strict"
}
```

Response:
```json
{
  "verdict": "supported | unsupported | partially_supported",
  "unsupported_claims": [
    { "claim": "string", "reason": "string" }
  ],
  "per_claim_evidence": [
    { "claim": "string", "supported": true, "source_id": "doc-1", "score": 0.0 }
  ],
  "confidence": 0.0,
  "receipt": {
    "receipt_id": "uuid",
    "issued_at": "RFC3339 timestamp",
    "verdict": "supported | unsupported | partially_supported",
    "output_sha256": "hex digest of the output text",
    "sources_sha256": ["hex digest per source doc"],
    "rigor_level": "fast | standard | strict",
    "engine_version": "semver",
    "signature": "HMAC-SHA256 over the canonical receipt body"
  }
}
```

## The pipeline (cost-tiered by rigor)
1. **Claim extraction.** Decompose `output` into atomic factual claims.
2. **Cheap pass (always):** semantic-entailment + surface checks (number
   mismatch, fabricated-citation pattern) of each claim vs. `source_documents`.
3. **Escalation (standard/strict only):** send only the *flagged* claims to an
   LLM-as-judge claim-level check. Never send unflagged claims — cost control.
4. **Aggregate** to a verdict + confidence.
5. **Receipt:** build canonical body, hash inputs, HMAC-sign, return.

`rigor_level`: `fast` = step 2 only; `standard` = 2+3; `strict` = 2+3 with
self-consistency (multiple judge samples) on flagged claims.

## Receipt integrity requirements (this is the moat — treat as security code)
- Canonical serialization MUST be deterministic (sorted keys, no whitespace
  drift) so the signature is reproducible.
- `signature = HMAC_SHA256(key = SIGNING_KEY, msg = canonical_receipt_body)`.
- A `POST /receipt/verify` endpoint re-checks a receipt's signature and returns
  `{ "valid": true|false }`. Tampering with any field must flip it to false.
- `SIGNING_KEY` comes from env only; never logged, never in a response.

## Non-goals for v1 (do NOT build these yet)
- No auth/multi-tenancy, no billing, no dashboard, no persistence layer beyond
  an in-memory/SQLite receipt store, no connectors, no UI.
- No streaming. Synchronous request/response only.

## Acceptance criteria (the MVP is "done" when all hold)
- [ ] `POST /verify` returns the full contract above for all three rigor levels.
- [ ] A known-unsupported claim is caught (verdict != supported).
- [ ] A fully-grounded output returns `supported` with no unsupported_claims.
- [ ] Tampering with any receipt field makes `POST /receipt/verify` return false.
- [ ] Unflagged claims are never escalated (assert via a spy/mock on the judge).
- [ ] `ruff`, `mypy`, and the full `pytest` suite are green.
