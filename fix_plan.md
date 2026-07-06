# fix_plan.md — living backlog

> The loop reads this top-to-bottom, does the first unchecked `[ ]` item, then
> checks it off and appends to the Progress log. Bootstrap (phase 0) will break
> big items into smaller ones. Keep items small enough for one iteration.

## Backlog (ordered by priority)
- [x] Scaffold FastAPI app: `app/main.py` with `GET /health` returning `{"ok": true}` + a passing test. _(done in bootstrap)_
- [ ] Define request Pydantic models for `POST /verify` per spec (`VerifyRequest`, `SourceDocument`, `RigorLevel` enum; no logic yet) + model validation tests.
- [ ] Define response Pydantic models per spec (`VerifyResponse`, `UnsupportedClaim`, `ClaimEvidence`, `Receipt`; no logic yet) + model tests.
- [ ] Implement claim extraction (`app/verify/claims.py`): output text -> list of atomic claims + tests.
- [ ] Implement cheap-pass entailment check (`app/verify/cheap.py`): per-claim semantic overlap vs. source docs -> supported flag + score + tests.
- [ ] Add cheap-pass surface checks to `app/verify/cheap.py`: number-mismatch detection + fabricated-citation pattern detection + tests.
- [ ] Implement the `fast` rigor path end-to-end through `POST /verify` (claims -> cheap pass -> aggregate verdict + confidence; stub receipt) + integration test.
- [ ] Implement canonical receipt serialization (`app/receipt/build.py`): deterministic sorted-key, whitespace-free JSON body + determinism tests.
- [ ] Add sha256 hashing to receipt builder: `output_sha256` + per-source `sources_sha256`, plus `receipt_id`/`issued_at` generation + tests.
- [ ] Implement HMAC-SHA256 signing (`app/receipt/sign.py`): sign canonical body with `SIGNING_KEY` from env (never logged, never in a response) + tests.
- [ ] Implement `POST /receipt/verify`: re-check signature, return `{"valid": true|false}`; test that tampering with EACH receipt field flips valid->false.
- [ ] Wire the real signed receipt into the `POST /verify` response (replace stub) + integration test.
- [ ] Implement LLM-judge interface + stub (`app/verify/judge.py`): claim-level check with an injectable client so tests never hit a real API + tests.
- [ ] Wire `standard` rigor path: escalate ONLY flagged claims to the judge; spy-test that unflagged claims are never sent.
- [ ] Wire `strict` rigor path: self-consistency via multiple judge samples on flagged claims + tests (re-assert unflagged claims never escalate).
- [x] Add `ruff` + `mypy` config; make the whole tree clean. _(done in bootstrap: configured in pyproject.toml, both green)_
- [ ] Audit spec acceptance criteria: ensure each has an explicit test (known-unsupported caught; fully-grounded returns `supported` with no unsupported_claims); add any missing.
- [ ] Add a README section documenting the endpoints + a curl example.

## Blockers
_(agent appends here and stops if it cannot proceed)_

## Progress log
_(agent appends one line per iteration: date — task — outcome — next)_
- 2026-07-06 — bootstrap — scaffolded pyproject/app/tests with GET /health; pytest, ruff check, mypy app all green; split backlog into ~150-line iterations — next: request models for POST /verify.
