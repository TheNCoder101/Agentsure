# GTM plan — Agentsure Verification Gate

> See `ROADMAP_V2.md` for the prioritized V2 plan (why the launch checklist
> below is necessary but not sufficient, and what comes after it).

## Positioning
**"Proof, not promises."** An inline API an AI agent calls before committing a
high-stakes output. Returns a verdict + a signed, tamper-evident audit receipt
a compliance officer can hand to a regulator. The receipt is the product.

**ICP:** teams deploying agents in regulated workflows (fintech ops, insurance
claims, healthcare admin, legal drafting) whose risk teams currently block
agent rollouts for lack of auditable grounding evidence.

## Commercial model (modeled on Tavily's self-serve API business)
Researched July 2026. Tavily's model: instant self-serve key (`tvly-` prefix),
1,000 free API credits/month with no card, credit cost varies by request depth
(basic = 1, advanced = 2), then $30/$100 monthly tiers and $0.008/credit
pay-as-you-go, enterprise on request. We mirror it one-for-one:

| Plan | Price | Credits / month | Effective $/credit |
|------|-------|-----------------|--------------------|
| Free | $0, no card | 1,000 | — |
| Starter | $30/mo | 4,000 | $0.0075 |
| Growth (featured) | $100/mo | 15,000 | $0.0067 |
| Pay-as-you-go | usage-billed | uncapped | $0.008 |
| Enterprise | custom | custom | custom (SLAs, private deploy, SSO) |

**Credit metering by rigor** (mirrors Tavily basic/advanced): `fast` = 1,
`standard` = 2, `strict` = 3. Credits reset monthly, no rollover.

## What is live in this repo (self-serve loop works end to end)
1. Landing page at `GET /` — premium editorial design, pricing, live console.
2. `POST /keys` — instant `vg-` API key from an email, Free plan, no card.
   Keys stored SHA-256-hashed; plaintext shown once.
3. `POST /verify` — the product: claims → cheap pass → judge escalation
   (flagged claims only) → verdict + HMAC-SHA256-signed receipt. Auth via
   `X-API-Key`; credits debited per rigor; `402` when exhausted.
4. `POST /receipt/verify` — public tamper check; any altered field → `false`.
5. `GET /usage` — plan, period, credits used/remaining.
6. `POST /subscribe` — plan switching (provisioning step; card collection is
   the Stripe milestone below).

## Launch checklist (ordered; each is a backlog item in fix_plan.md)
- [ ] **Billing go-live:** Stripe Checkout on `POST /subscribe` + webhook →
      `store.set_plan`; monthly invoice for PAYG overage. Until then, paid
      plans are provisioned on invoice (acceptable for first 10 customers).
- [ ] **Real LLM judge:** swap `HeuristicJudge` for an Anthropic-backed
      `JudgeClient` (interface already injected everywhere).
- [ ] **Abuse controls:** per-key + per-IP rate limits, one free key per email
      (verification email), key revocation endpoint.
- [ ] **Receipt retention:** persist receipts (SQLite → Postgres) + export for
      the Growth plan's retention promise.
- [ ] **Deploy:** containerize, TLS at api.agentsure.dev, uptime monitoring,
      structured logs (SIGNING_KEY never logged — enforced in code).
- [ ] **Legal:** ToS, privacy policy, DPA template for enterprise.
- [ ] **Design partners:** 5 teams from the ICP on Free/Starter, weekly
      feedback loop; case study each.

## First-quarter metrics that matter
Signups → first `/verify` call (activation), calls/key/week (retention),
free→paid conversion, credits consumed by rigor (validates tiered pricing).
