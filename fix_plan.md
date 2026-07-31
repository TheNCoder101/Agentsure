# fix_plan.md — living backlog

> The loop reads this top-to-bottom, does the first unchecked `[ ]` item, then
> checks it off and appends to the Progress log. Bootstrap (phase 0) will break
> big items into smaller ones. Keep items small enough for one iteration.

## Backlog (ordered by priority)
- [x] Scaffold FastAPI app: `app/main.py` with `GET /health` returning `{"ok": true}` + a passing test. _(done in bootstrap)_
- [x] Define request Pydantic models for `POST /verify` per spec + model validation tests. _(done in GTM build)_
- [x] Define response Pydantic models per spec + model tests. _(done in GTM build)_
- [x] Implement claim extraction (`app/verify/claims.py`) + tests. _(done in GTM build)_
- [x] Implement cheap-pass entailment check (`app/verify/cheap.py`) + tests. _(done in GTM build)_
- [x] Add cheap-pass surface checks: number-mismatch + fabricated-citation detection + tests. _(done in GTM build)_
- [x] Implement the `fast` rigor path end-to-end through `POST /verify` + integration test. _(done in GTM build)_
- [x] Implement canonical receipt serialization + determinism tests. _(done in GTM build)_
- [x] Add sha256 hashing + `receipt_id`/`issued_at` generation + tests. _(done in GTM build)_
- [x] Implement HMAC-SHA256 signing from `SIGNING_KEY` env + tests. _(done in GTM build)_
- [x] Implement `POST /receipt/verify`; tampering with each field flips valid->false + tests. _(done in GTM build)_
- [x] Wire the real signed receipt into `POST /verify` + integration test. _(done in GTM build)_
- [x] Implement LLM-judge interface + injectable stub (`app/verify/judge.py`) + tests. _(done in GTM build; real LLM client still open below)_
- [x] Wire `standard` rigor path; spy-test that unflagged claims are never sent. _(done in GTM build)_
- [x] Wire `strict` rigor path: self-consistency sampling + tests. _(done in GTM build)_
- [x] Add `ruff` + `mypy` config; make the whole tree clean. _(done in bootstrap: configured in pyproject.toml, both green)_
- [x] Audit spec acceptance criteria: each has an explicit test. _(done in GTM build: tests/test_api.py + tests/test_receipt.py)_
- [x] Add a README section documenting the endpoints + a curl example. _(done in GTM build)_

### GTM backlog (post-MVP, see GTM.md launch checklist)
- [ ] Stripe Checkout on `POST /subscribe` + webhook -> `store.set_plan`; PAYG monthly invoicing.
- [ ] Replace `HeuristicJudge` with an Anthropic-backed `JudgeClient` (interface already injected) + recorded-fixture tests.
- [ ] Abuse controls: per-key/per-IP rate limits, email verification (one free key per email), key revocation endpoint.
- [ ] Receipt persistence + export (Growth plan retention promise); SQLite -> Postgres migration path.
- [ ] Deployment: Dockerfile, TLS at api.agentsure.dev, uptime monitoring, structured logging (SIGNING_KEY redaction test).
- [ ] Legal pages: ToS + privacy policy routes linked from landing footer.

### Governance-research backlog (from Gardhouse, Oueslati & Kolt, "Regulating AI Agents," July 2026)
- [x] Add `severity` (info/moderate/high) to `UnsupportedClaim`, derived in `app/verify/pipeline.py`, addressing the AI Act Article 14 human-oversight/override gap the paper identifies. _(done)_
- [x] Add `issuer_ref` chain-of-custody field to `Receipt`, signed as part of the canonical body, addressing the paper's "many-hands problem" (Part IV.B). _(done)_
- [x] Add `session_id` grouping on `POST /verify` + `GET /sessions/{session_id}/summary` (verdict counts, unsupported-rate trend, receipt_ids), addressing the paper's critique that one-off point-in-time compliance artifacts (DPIAs, FRIAs) miss harm that "materializes only through the aggregate of multiple exchanges." _(done)_
- [x] `docs/compliance-mapping.md` mapping receipt fields to AI Act Articles 9/14/15/27. _(done)_
- [ ] Landing page: surface `session_id`/severity in the console's custom-verification tab once there's a concrete customer workflow asking for it — deferred until requested, not built speculatively.

#### Researched, not yet scoped (flagged by the paper, deliberately deferred)
- Bias/protected-category detection on claim content (paper Part II.D, equity) — a materially different capability (fairness/discrimination detection) than grounding verification; needs its own design pass before it becomes a backlog item, not a schema extension.
- Continuous/scheduled re-verification of a standing claim over time (paper Part IV.C, institutional monitoring) — real implication of "one-off vs. ongoing" critique, but requires background-job infrastructure; a v2 concern once session aggregation proves useful to early customers.

## Blockers
_(agent appends here and stops if it cannot proceed)_

## Progress log
_(agent appends one line per iteration: date — task — outcome — next)_
- 2026-07-06 — bootstrap — scaffolded pyproject/app/tests with GET /health; pytest, ruff check, mypy app all green; split backlog into ~150-line iterations — next: request models for POST /verify.
- 2026-07-07 — GTM build (user-directed, superseded loop cadence) — implemented full MVP (engine, receipts, /verify, /receipt/verify) + commercial layer (vg- keys, Tavily-modeled credit plans, /usage, /subscribe) + landing page with working console; 48 tests, ruff+mypy green; smoke-tested live incl. Playwright UI run — next: GTM backlog (Stripe, real LLM judge, deploy).
- 2026-07-07 — governance-research build (user-directed) — digested "Regulating AI Agents" (Gardhouse, Oueslati & Kolt, July 2026) and added claim severity, receipt issuer_ref chain-of-custody, and session-level verdict aggregation (`GET /sessions/{id}/summary`), each traced to a specific gap the paper identifies in EU AI Act Articles 9/14/27 and the "many-hands problem"; added docs/compliance-mapping.md; 57 tests, ruff+mypy green — next: bias-detection and continuous-reverification are deliberately deferred (see Researched-not-yet-scoped), otherwise resume GTM backlog.
