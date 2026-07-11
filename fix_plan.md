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

### V2 Phase 0 backlog — close the credibility gap (see ROADMAP_V2.md; ordered by trust unlocked per unit of effort, re-sequenced ahead of the original GTM order below)
- [x] Replace `HeuristicJudge` with an Anthropic-backed `JudgeClient` (interface already injected) + recorded-fixture tests + a checked-in labeled accuracy benchmark (known-supported/unsupported/adversarial claims). _(done 2026-07-11: `AnthropicJudge` in app/verify/judge.py, wired in app/main.py behind `ANTHROPIC_API_KEY`, fails closed on API error/unparsable response; benchmark harness in app/verify/benchmark.py with 8 labeled cases, run manually via `uv run python -m app.verify.benchmark` — NOT wired into pytest, since scoring it needs a live Anthropic call. Real accuracy number against the live model is still outstanding — see Blockers.)_
- [ ] Receipt persistence + `GET /receipts/{id}` lookup + CSV/PDF export (Growth plan retention promise); SQLite -> Postgres migration path.
- [ ] Asymmetric receipt signing (Ed25519) alongside existing HMAC; publish the public key at a stable well-known URL; ship a standalone offline verifier so a receipt can be checked without calling our API.
- [ ] Stripe Checkout on `POST /subscribe` + webhook -> `store.set_plan`; PAYG monthly invoicing.
- [ ] Abuse controls: per-key/per-IP rate limits, email verification (one free key per email), key revocation endpoint.
- [ ] Deployment: Dockerfile, CI (`.github/workflows` — none exists today), TLS at api.agentsure.dev, uptime monitoring, structured logging (SIGNING_KEY redaction test).
- [ ] Legal pages: ToS + privacy policy routes linked from landing footer.
- [x] Housekeeping: verify whether the `httpx2` dependency in pyproject.toml is intentional or a typo. _(done 2026-07-11: it's real and intentional — Starlette's TestClient recommends installing it, and removing it reintroduces a deprecation warning in the test run. Left in place, no action needed.)_

### V2 Phase 1 backlog — build the reasons to pay (see ROADMAP_V2.md; start once the real judge above ships)
- [ ] Agent-framework integrations: thin Python/TS SDK, LangChain tool, MCP server exposing `verify`, OpenAI Agents SDK guardrail wrapper.
- [ ] Compliance dashboard: verification history, trend/failure analytics, flagged-claim review/override, org/team concept with seats + RBAC.
- [ ] Org-level policy configuration: required rigor per workflow type, custom claim taxonomies, blocklist/allowlist rules.
- [ ] Alerting/webhooks on failed or low-confidence verifications (Slack/email/webhook).
- [ ] Pricing: add a "Compliance" tier between Growth and Enterprise (seats, extended retention, exportable reports, SSO).
- [ ] Vertical go-to-market: insurance claims as first wedge; 5 design partners from that vertical; one case study.

## Blockers
_(agent appends here and stops if it cannot proceed)_
- 2026-07-11 — the Phase 0 accuracy benchmark (app/verify/benchmark.py) is implemented and unit-tested, but has not been run against the real Anthropic API in this environment (no ANTHROPIC_API_KEY available, and CLAUDE.md rule 10 forbids network side-effects in the automated loop). Someone with API credentials needs to run `uv run python -m app.verify.benchmark` and commit the resulting accuracy number before any "real LLM judge" claim goes on the landing page, per the roadmap's own verification section.

## Progress log
_(agent appends one line per iteration: date — task — outcome — next)_
- 2026-07-06 — bootstrap — scaffolded pyproject/app/tests with GET /health; pytest, ruff check, mypy app all green; split backlog into ~150-line iterations — next: request models for POST /verify.
- 2026-07-07 — GTM build (user-directed, superseded loop cadence) — implemented full MVP (engine, receipts, /verify, /receipt/verify) + commercial layer (vg- keys, Tavily-modeled credit plans, /usage, /subscribe) + landing page with working console; 48 tests, ruff+mypy green; smoke-tested live incl. Playwright UI run — next: GTM backlog (Stripe, real LLM judge, deploy).
- 2026-07-11 — V2 planning (user-directed, no code changes) — audited V1 against its own "proof, not promises" claim: judge is a heuristic stand-in (no real LLM call anywhere), receipts are never persisted despite a sold retention promise, HMAC signing is server-verify-only which undercuts the "hand to a regulator" pitch, and there is zero agent-framework integration story. Wrote `ROADMAP_V2.md` (Phase 0: real judge + persisted/exportable receipts + Ed25519 offline-verifiable signing + Stripe + abuse controls + deploy + legal; Phase 1: framework SDKs/MCP, compliance dashboard, org policy config, alerting, a new "Compliance" pricing tier, insurance-claims vertical focus; Phase 2: accuracy flywheel, SOC 2, data residency) and re-sequenced the GTM backlog below by trust-unlocked-per-effort — next: Phase 0 item 1, real Anthropic-backed JudgeClient + accuracy benchmark.
- 2026-07-11 — V2 Phase 0 item 1 (user-directed) — added `anthropic` SDK dependency; implemented `AnthropicJudge` in app/verify/judge.py (fails closed to unsupported/0.0 confidence on API error or unparsable response; text-block extraction narrowed via `isinstance(block, TextBlock)` for mypy strict); wired judge selection in app/main.py (`ANTHROPIC_API_KEY` present -> real judge, cached via lru_cache; otherwise HeuristicJudge fallback), verified both branches with a network-free wiring smoke test. Added fixture-mocked tests (tests/test_judge_anthropic.py, real `anthropic.types.TextBlock` fixtures, no live calls) and a labeled accuracy-benchmark harness (app/verify/benchmark.py, 8 cases incl. adversarial near-miss-number/fabricated-citation/unstated-causal-reasoning; tests/test_benchmark.py tests the harness itself with a scripted judge). Also investigated the `httpx2` dependency flagged as suspicious in ROADMAP_V2.md — it's real (Starlette's TestClient recommends it; removing it reintroduces a deprecation warning) and was mistakenly called out; correction made in both docs. 60 tests pass, ruff+mypy clean — next: the real-Anthropic accuracy run is blocked on API credentials (see Blockers); after that, Phase 0 item 2 (receipt persistence + export).
