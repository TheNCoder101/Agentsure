# Ralph build harness — Verification Gate MVP

An autonomous Claude Code build system that grinds out the verification-gate MVP
one small, tested, committed step at a time, using **Claude Fable 5** as the
model in a **Ralph loop**.

## The mental model
- **Context is disposable; the filesystem is memory.** Each loop iteration is a
  fresh Claude Code run. Everything durable lives in files that get re-read at
  the top of every loop: `CLAUDE.md` (constitution), `specs/` (source of truth),
  `fix_plan.md` (backlog + progress log).
- **The loop does one task per iteration**, proves it with tests, and the driver
  commits it. A bad step is one `git revert` away.

## The staged chain (run in order)
| Phase | Prompt | How to run | Purpose |
|------|--------|-----------|---------|
| 0. Bootstrap | `prompts/00_bootstrap.md` | one-shot (below) | scaffold repo, split backlog |
| 1. Build | `prompts/10_build_loop.md` | `./loop.sh prompts/10_build_loop.md` | implement the backlog |
| 2. Harden | `prompts/20_harden_loop.md` | `./loop.sh prompts/20_harden_loop.md` | receipt integrity, edges, cost leaks |

A pure single infinite loop is fragile — staging separates "build features" from
"make it audit-proof," each with its own prompt and stop condition.

## Setup
```bash
npm install -g @anthropic-ai/claude-code      # Node 20+
export ANTHROPIC_API_KEY=sk-...               # or your configured auth
cp .env.example .env && echo "SIGNING_KEY=$(openssl rand -hex 32)" >> .env
git init && git add -A && git commit -m "harness"
chmod +x loop.sh
# deps used by the driver: jq, bc, git
```

## Run it
```bash
# Phase 0 — one-shot bootstrap (not looped):
claude -p "$(cat prompts/00_bootstrap.md)" \
  --model claude-fable-5 --permission-mode acceptEdits \
  --allowedTools "Read,Edit,Write,Bash(git *),Bash(uv *),Bash(python *)"
git add -A && git commit -m "bootstrap"

# Phase 1 — build loop:
./loop.sh prompts/10_build_loop.md

# Phase 2 — harden loop:
./loop.sh prompts/20_harden_loop.md
```

## Guardrails (why each exists)
- **Iteration cap** (`MAX_ITERS`) and **cost ceiling** (`COST_CEILING_USD`) —
  Ralph classically runs forever; these stop a runaway from draining your
  account. The driver reads `total_cost_usd` from each run's JSON output and
  halts when the cumulative spend crosses the ceiling.
- **`--max-turns`** — bounds work *inside* one iteration so a single loop can't
  spiral.
- **Per-iteration commit** — every step is independently revertible.
- **Stop-file** — `touch .ralph-stop` to halt gracefully after the current
  iteration.
- **Constitution re-read every loop** — `CLAUDE.md` is auto-loaded by Claude
  Code, so the Ten Golden Rules (one task/loop, never weaken a test, small
  diffs) apply to every fresh context. We deliberately do **not** pass `--bare`,
  which would skip `CLAUDE.md`.
- **Scoped `--allowedTools`** — the agent can edit code and run the test/lint
  toolchain and git, but not arbitrary shell. For a fully hands-off overnight
  run, do it inside a container/worktree; only there consider
  `--dangerously-skip-permissions`.

## Tuning cost
Fable 5 is a top-tier model — looping it is powerful but not cheap. Levers:
- Lower `MAX_ITERS` / `COST_CEILING_USD` and run in short supervised bursts.
- Keep backlog items genuinely small (fewer turns per item = less spend).
- Consider running the **harden** loop on Fable 5 (integrity-critical) but a
  cheaper model on mechanical build items — set `MODEL=` per invocation.

## A note on Fable 5 routing
Fable 5 ships with safeguards that occasionally route a request to Opus 4.8
(on average under 5% of sessions, mostly security/bio/LLM-R&D topics). For
ordinary app-building this is a non-event — but if an iteration's JSON reports a
different model than you set, that's why. It won't break the loop.

## What "done" looks like
When `./loop.sh prompts/10_build_loop.md` prints `backlog has no open items`,
every acceptance criterion in `specs/verification-gate.md` should hold. Verify
by hand: run the suite, then `curl` a known-unsupported claim and confirm the
verdict, and tamper with a receipt field and confirm `/receipt/verify` returns
`false`.
