#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────────────────────────
# Ralph loop driver for Claude Code.
# Runs one fresh-context iteration at a time until the backlog is empty,
# a cost ceiling is hit, a stop-file appears, or the iteration cap is reached.
#
# Usage:
#   ./loop.sh prompts/10_build_loop.md          # build phase
#   ./loop.sh prompts/20_harden_loop.md         # harden phase
#   MAX_ITERS=10 COST_CEILING_USD=8 ./loop.sh   # override guardrails
#
# Requires: claude (Claude Code), jq, bc, git.  Run inside a git repo.
# ───────────────────────────────────────────────────────────────────

MODEL="${MODEL:-claude-fable-5}"   # NOTE: confirm this alias in your Claude Code
                                   # version via `/model`; adjust if it differs.
PROMPT_FILE="${1:-prompts/10_build_loop.md}"
MAX_ITERS="${MAX_ITERS:-40}"
COST_CEILING_USD="${COST_CEILING_USD:-25}"
MAX_TURNS="${MAX_TURNS:-40}"       # bound work within a single iteration
STOP_FILE=".ralph-stop"            # `touch .ralph-stop` to halt gracefully
BACKLOG="fix_plan.md"

command -v claude >/dev/null || { echo "claude not found (npm i -g @anthropic-ai/claude-code)"; exit 1; }
command -v jq >/dev/null || { echo "jq required"; exit 1; }
command -v bc >/dev/null || { echo "bc required"; exit 1; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "run inside a git repo"; exit 1; }

total_cost="0"; i=0
echo "▶ Ralph  model=$MODEL  prompt=$PROMPT_FILE  cap=$MAX_ITERS  budget=\$$COST_CEILING_USD"

while (( i < MAX_ITERS )); do
  i=$((i+1))

  [[ -f "$STOP_FILE" ]] && { echo "■ stop-file present — halting"; break; }
  if ! grep -qE '^\s*-\s*\[ \]' "$BACKLOG"; then
    echo "✓ backlog has no open items — done building"; break
  fi

  echo "── iteration $i ─────────────────────────────────────────"

  # FRESH context every loop: deliberately NO --resume. Memory lives on disk.
  # NOT using --bare, because we WANT CLAUDE.md re-read every iteration.
  out="$(claude -p "$(cat "$PROMPT_FILE")" \
        --model "$MODEL" \
        --permission-mode acceptEdits \
        --allowedTools "Read,Edit,Write,Grep,Glob,Bash(git *),Bash(uv *),Bash(pytest *),Bash(ruff *),Bash(mypy *),Bash(python *)" \
        --max-turns "$MAX_TURNS" \
        --output-format json)" || { echo "✗ claude exited non-zero — halting"; break; }

  # Print the model's own summary (last text result) for the operator log.
  echo "$out" | jq -r '.result // empty' 2>/dev/null | sed 's/^/   /' || true

  # Cost accounting from structured output.
  iter_cost="$(echo "$out" | jq -r '.total_cost_usd // 0')"
  total_cost="$(echo "$total_cost + $iter_cost" | bc -l)"
  printf "   iteration cost \$%.4f   cumulative \$%.4f\n" "$iter_cost" "$total_cost"

  # Detect the agent's own "nothing left" signal.
  if echo "$out" | jq -r '.result // ""' | grep -q "BACKLOG EMPTY"; then
    echo "✓ agent reports backlog empty — done"; break
  fi

  # Commit each iteration so any bad step is a one-command rollback.
  if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git status --porcelain)" ]]; then
    git add -A && git commit -q -m "ralph($i): $(basename "$PROMPT_FILE" .md)" || true
  else
    echo "   (no file changes this iteration)"
  fi

  # Budget circuit-breaker.
  if (( $(echo "$total_cost >= $COST_CEILING_USD" | bc -l) )); then
    echo "■ cost ceiling \$$COST_CEILING_USD reached — halting"; break
  fi
done

echo "▶ finished: $i iteration(s), ~\$$(printf '%.2f' "$total_cost") spent"
echo "  review with:  git log --oneline | head -n $i"
