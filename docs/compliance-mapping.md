# Compliance mapping: Agentsure receipts and the EU AI Act

This document maps what Agentsure actually returns — receipt fields and the
session-summary endpoint — to specific obligations in the EU AI Act (the
world's most consequential AI regulation), and to the gaps in how those
obligations are currently implementable in practice. The gap analysis is
drawn from:

> Kathrin Gardhouse, Amin Oueslati & Noam Kolt, *Regulating AI Agents*
> (July 2026) — a systematic analysis of how the AI Act's provisions apply
> to autonomous AI agents.

This is a positioning reference for sales and compliance conversations, not
a legal opinion. Agentsure does not make AI Act conformity determinations;
it produces evidence a deployer's own compliance process can use.

## Article 9 — Risk management system
Article 9 requires providers of high-risk AI systems to run a "continuous
iterative process" of risk identification across the system's lifecycle,
not just a one-time assessment. The paper notes this is one of the AI Act's
better-suited provisions for agents in principle, but that ex ante conformity
assessments and periodic reporting still dominate in practice.

**How Agentsure helps:** every `POST /verify` call is itself a lifecycle risk
check, and `GET /sessions/{session_id}/summary`'s `unsupported_rate_trend`
gives a running, evidence-backed signal of whether an agent's grounding is
degrading over time — the "continuous" part of Article 9 that one-off audits
don't provide.

## Article 14 — Human oversight
Article 14(4) requires that human overseers be able to "correctly interpret"
a system's output and "decide not to use... or override" it. The paper
observes this presupposes agent behavior can be made legible to a human in
real time — often not the case in practice.

**How Agentsure helps:** `UnsupportedClaim.severity` (`info` / `moderate` /
`high`) is exactly this legibility layer — a machine-readable signal for
"does a human need to look at this before it's acted on," derived from
whether the rejection came from a hard evidence conflict (fabricated
citation, mismatched number), a reasoned judge review, or a lighter cheap-pass
flag alone.

## Article 15 — Accuracy, robustness, consistency
The paper's sharpest critique: these three proxies are conceptually ill-suited
to agents, whose competence is "jagged" (strong on some tasks, unpredictably
weak on others) rather than uniformly measurable against a fixed standard.

**How Agentsure helps:** rigor levels (`fast`/`standard`/`strict`) don't
claim to produce a single accuracy number. They instead let a deployer choose
how much scrutiny a given claim gets, and the receipt records which rigor was
actually applied — an honest declaration of *how hard we looked*, not an
unearned accuracy percentage.

## Article 27 — Fundamental Rights Impact Assessment (FRIA)
FRIAs are a one-off or periodic exercise performed before deployment. The
paper argues this is a poor fit for agents whose behavior can change after
deployment, and that reassessment should be continuous, not episodic.

**How Agentsure helps:** because every verification call is logged and
`session_id` groups related calls, a deployer can attach a live, growing body
of receipts to an existing FRIA rather than relying on the point-in-time
assessment alone — evidence that supports the "review and update" duty the
paper says the Act leaves implicit.

## The "many-hands problem" (Part IV.B of the paper)
The paper's central institutional critique: responsibility for agent risk is
split across model providers, system providers, and deployers, with no
single actor holding a complete view, and third-party tool providers falling
outside the Act's categories entirely. The authors' own recommendation is to
**"pool key information... into a centralized body."**

**How Agentsure helps:** `Receipt.issuer_ref` lets a receipt carry an
identifier for whoever issued it (a system provider, a specific deployment)
as it moves down the value chain — from an AI agent vendor, to their
enterprise customer's compliance team, to that customer's auditor — with
`POST /receipt/verify` letting any of those parties independently confirm
nothing was altered in transit. It is a small, concrete instance of the
pooled, cross-actor evidence trail the paper argues is currently missing.

## What this is not
Agentsure does not perform bias/protected-category detection (the paper's
Part II.D equity concerns) or continuous scheduled re-verification of a
standing claim over time — both are real implications of the paper's
analysis, deliberately deferred; see `fix_plan.md`.
