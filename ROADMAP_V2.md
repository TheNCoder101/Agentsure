# Agentsure V2 roadmap — from demo to something regulated teams pay for

> CTO/PM planning doc. Source of truth for prioritization until items are
> broken down into `fix_plan.md` backlog entries. See `specs/verification-gate.md`
> for the technical spec and `GTM.md` for the existing commercial model.

## Where we are

V1 was built in one day via the Ralph autonomous loop and, on the surface,
looks GTM-ready: a full pricing ladder (Free/Starter/Growth/PAYG/Enterprise
modeled on Tavily), a landing page with a live console, self-serve API keys,
and a credit-metering billing layer. 48 tests pass, ruff/mypy are clean.

But the product's own tagline is **"Proof, not promises — the receipt is the
product."** Measured against that bar, V1 currently breaks its own promise in
three places:

1. **The judge is fake.** `HeuristicJudge` (`app/verify/judge.py`) is a
   deterministic string-containment stand-in. There is no LLM call anywhere
   in the pipeline. We are selling "AI-audited proof" with no AI in the loop.
2. **The receipt disappears.** Receipts are computed, signed, and returned
   once — never persisted. There is no way to look one up later, export it,
   or hand a compliance officer an audit trail. That's the literal product
   promise, unmet.
3. **Nothing else is real either.** `/subscribe` doesn't touch Stripe (no
   payment collection), there's no rate limiting or abuse control, no CI, no
   deployment, no legal pages.

This is not a criticism of the build — it's the correct MVP given the spec's
explicit v1 non-goals (no auth, no billing, no persistence, no UI). The GTM
build session got ahead of the spec by shipping commercial surface before the
underlying substance existed. **V2's job is to close that gap first, then add
the features that create genuine willingness to pay** — not just make the
fake parts real, but make the product something a risk team actively wants,
integrates deeply, and would be painful to rip out.

Two structural issues also matter for the plan:

- **Symmetric signing undermines the core pitch.** Receipts are HMAC-SHA256
  signed with a server-side secret, so only Agentsure can verify a receipt's
  authenticity (`POST /receipt/verify` calls back to us). The pitch is "hand
  it to a regulator" — a regulator won't want to trust our API to vouch for
  its own signature. Audit-grade proof needs to be independently, offline
  verifiable by a third party. Points at asymmetric signing (Ed25519) with a
  published public key.
- **No integration story.** Zero references anywhere to LangChain, LangGraph,
  CrewAI, OpenAI Agents SDK, or MCP. The ICP is literally "teams deploying
  agents," but today the only integration path is raw curl.

## Strategy

**Phase 0 — make the existing promise true.** Nothing in Phase 1 matters if
the judge is fake and receipts vanish — that's not a feature gap, it's a
correctness gap in what's already being marketed. Ship before charging real
money.

**Phase 1 — build the reasons to pay, not just the reasons it works.** Once
the core promise is true, these turn "a hallucination checker" into something
a compliance team depends on and a dev team can't easily replace.

**Phase 2 — moat.** After Phase 0/1 have paying customers.

---

## Phase 0 — Close the credibility gap (blocks any paid customer)

Ordered by trust unlocked per unit of effort:

1. **Real LLM judge.** ✅ Shipped 2026-07-11: `AnthropicJudge` in
   `app/verify/judge.py`, wired in behind `ANTHROPIC_API_KEY`
   (`app/main.py:get_judge`), fails closed on any API error or unparsable
   response. Labeled eval set + benchmark harness in
   `app/verify/benchmark.py` (8 cases incl. adversarial near-miss-number,
   fabricated-citation, and unstated-causal-reasoning claims). **Still
   outstanding: the actual accuracy number.** The harness has only been run
   against a scripted fake judge in tests — nobody has run
   `uv run python -m app.verify.benchmark` against the live Anthropic API
   yet (needs real credentials; not something the automated loop can do
   under CLAUDE.md's no-network-side-effects rule). Run it and commit the
   number — that's what turns this into marketing collateral. **Don't put
   "AI-verified" copy on the landing page until that number exists.**
2. **Receipt persistence + lookup/export.** Add a receipt store (SQLite now,
   same Postgres migration path already planned), `GET /receipts/{id}`, and
   CSV/PDF export. Without this the "Growth plan retention" promise in
   `GTM.md` is sold but not deliverable.
3. **Asymmetric receipt signing (Ed25519).** Sign the canonical receipt body
   with Ed25519, publish the public key at a stable URL
   (`/.well-known/agentsure-receipt-key` or similar), and ship a tiny
   standalone verifier so a regulator/auditor can check a receipt's
   authenticity without ever calling our API. Makes "audit-grade" a true
   claim instead of a marketing phrase.
4. **Stripe billing go-live.** `POST /subscribe` + webhook → `store.set_plan`;
   PAYG monthly invoicing. Until this exists, "Starter $30/mo" is fiction —
   plans are hand-provisioned.
5. **Abuse controls.** Per-key/per-IP rate limits, one-free-key-per-email
   (email verification), key revocation endpoint.
6. **Deploy + observability.** Dockerfile, CI (`.github/workflows` — none
   exists today, so lint/type/test isn't enforced on push), TLS at
   `api.agentsure.dev`, uptime monitoring, structured logs with a test
   proving `SIGNING_KEY` is never logged.
7. **Legal.** ToS, privacy policy, DPA template.
8. ~~**Housekeeping.**~~ `pyproject.toml` lists both `httpx>=0.27` and
   `httpx2` — checked: this is intentional, not a typo. Starlette's
   `TestClient` recommends installing `httpx2`, and removing it reintroduces
   a deprecation warning in the test run.

Each item should land as its own properly-sized (~150 line) `fix_plan.md`
backlog entry per the existing Ralph loop discipline in `CLAUDE.md`, rather
than another single mega-commit.

## Phase 1 — Build the reasons to pay

1. **Native agent-framework integrations.** Thin Python/TS SDK, a LangChain
   tool, an MCP server exposing `verify` as a tool, an OpenAI Agents SDK
   guardrail wrapper. The ICP builds on these frameworks today; "wrap your
   agent output in one tool call" beats "write your own HTTP client." Highest
   -leverage adoption unlock, currently doesn't exist at all.
2. **Compliance dashboard, not just a dev console.** The landing page console
   is built for developers testing the API. Risk/compliance teams — the
   actual economic buyer — need to browse verification history, see
   trend/failure-rate analytics, review/override flagged claims, and manage
   team seats with RBAC (today there's no org/team concept, just one email
   per key). Justifies a per-seat or per-org price component instead of pure
   API metering.
3. **Org-level policy configuration.** Required rigor per workflow type,
   custom claim taxonomies (policy numbers for insurance, dollar figures for
   fintech, dosages for healthcare), blocklist/allowlist rules. Makes the
   product sticky, configured infrastructure instead of a commodity API call.
4. **Alerting/webhooks.** Real-time Slack/email/webhook on failed or
   low-confidence verifications.
5. **Pricing/packaging rework.** Pure Tavily-style credit metering fits a
   developer-led motion but undersells what a compliance buyer values
   (retention, export, SSO, seats, audit reports). Add a **"Compliance"
   tier** between Growth and Enterprise: multi-seat dashboard, extended
   receipt retention, exportable audit reports, SSO — priced on org/seat
   rather than credits, bridging the $100/mo self-serve ladder to the
   enterprise motion instead of leaving a cliff.
6. **Pick one vertical and go deep before going horizontal.** The ICP spans
   four verticals with zero vertical-specific claim types, copy, or design
   partners. Recommend **insurance claims** as the first wedge — matches the
   brand, "verify claim against source documents" maps naturally onto actual
   insurance claims, and the vertical has acute, well-understood
   audit/regulatory pressure (state DOI requirements). Ship the 5 design
   partners GTM.md already plans, but from one vertical, get one detailed
   case study, then expand.

## Phase 2 — Moat

- **Accuracy flywheel.** Log every human override/dispute from the compliance
  dashboard as labeled training data to improve the judge over time — a
  compounding advantage a thin LLM-call wrapper can't replicate.
- **SOC 2 Type II.** The real unlock for larger regulated-enterprise deals;
  start early, it takes months.
- **Data residency / multi-region deploy** for EU finance/healthcare buyers
  once there's enough enterprise pipeline to justify it.

## Sequencing

Phase 0 items 1–3 (real judge, persisted+exportable receipts, verifiable
signatures) are most urgent — not new scope, just making already-marketed
claims true, and they double as the eval-benchmark sales asset. Items 4–7
(Stripe, abuse controls, deploy, legal) can run in parallel once 1–3 are
underway. Phase 1's integrations should start as soon as Phase 0's judge is
real — a fake-judge integration would just propagate the credibility problem
into every framework it touches.

## Verification

- Phase 0: full pytest suite stays green (currently 48 tests) plus new tests
  for the real judge (recorded-fixture tests against actual Anthropic
  responses, not live calls in CI), receipt persistence/export, and Ed25519
  signature verification (a standalone script verifying a receipt using only
  the published public key, no API call). `ruff check` and `mypy app` clean.
- The accuracy benchmark (Phase 0.1) should be run and its results committed
  as a visible number before any "real LLM judge" claim goes on the landing
  page — don't market a capability ahead of proof.
- Phase 1: smoke-test each framework integration against a live local
  `/verify` call, the same way the GTM build session Playwright-tested the
  console.
