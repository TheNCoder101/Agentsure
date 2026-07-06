# CLAUDE.md — Project Constitution

> Claude Code reads this file automatically at the start of every run.
> In a Ralph loop each iteration is a FRESH context, so this file is the
> only memory that survives. Treat every rule here as non-negotiable.

## What we are building
An **audit-grade verification gate**: an inline API an AI agent calls before
it commits a high-stakes output. It returns a verdict AND a signed, tamper-
evident **audit receipt** that a compliance officer can hand to a regulator.
The receipt — not the detection — is the product. Full spec:
`specs/verification-gate.md`.

## The Ten Golden Rules (violating any is a failed iteration)
1. **One task per loop.** Read `fix_plan.md`, pick the single highest-priority
   unchecked `[ ]` item, do ONLY that. Do not batch.
2. **Tests are law.** Never mark a task done unless the full test suite is
   green. Run it; do not assume.
3. **Never weaken a test to pass it.** Deleting, skipping, or loosening an
   assertion to get green is a critical failure. If a test is genuinely wrong,
   record why in the progress log and stop.
4. **Small diffs.** If your change touches more than ~3 files or ~150 lines,
   you have taken too much. Split it and put the rest back on the backlog.
5. **Never rewrite working code** you were not asked to change.
6. **Leave breadcrumbs.** Append one line to the `## Progress log` in
   `fix_plan.md` every iteration: what you did, what you learned, what's next.
7. **Commit is done by the loop driver, not you.** Just leave the working tree
   in a clean, test-green state.
8. **If blocked, stop cleanly.** Write the blocker under `## Blockers` in
   `fix_plan.md` and do nothing else. A recorded blocker is worth more than a
   guessed-at hack.
9. **The spec is the source of truth.** If reality and `specs/` disagree, the
   spec wins — or you flag the spec as wrong in the progress log. Never drift
   silently.
10. **No secrets, no network side-effects, no `rm -rf`, no force-push.**

## Stack & layout
- Language/runtime: **Python 3.12 + FastAPI** (async), **pytest** for tests.
- Package manager: `uv` (fallback `pip`).
- Layout:
  - `app/` — service code (`app/main.py`, `app/verify/`, `app/receipt/`)
  - `tests/` — pytest, mirrors `app/`
  - `specs/` — source of truth (read-only intent; do not edit to match code)
- Lint/type: `ruff` + `mypy`. Both must pass before a task is done.

## Definition of Done (per task)
- [ ] Code implements exactly the backlog item, no more.
- [ ] New/updated tests cover it and the WHOLE suite passes.
- [ ] `ruff check` and `mypy app` are clean.
- [ ] Backlog item checked off `[x]` and a progress-log line appended.

## First action of EVERY loop
Read, in order: this file → `specs/verification-gate.md` → `fix_plan.md`.
Then pick your one task.
