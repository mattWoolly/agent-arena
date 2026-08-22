#!/usr/bin/env bash
# Four development-only smokes, one per factorial cell.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
MODEL=claude-sonnet-5

# Force native subscription OAuth. A pay-as-you-go key must not shadow it.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL
unset ANTHROPIC_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL
unset ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL
unset CLAUDE_CODE_SUBAGENT_MODEL ARENA_PROXY_UPSTREAM

check_run() {
  local effort="$1" out="$2"
  jq -e --arg model "$MODEL" \
    '.served_model == $model and .served_model_leak == false' \
    "$out/metrics.json" >/dev/null
  jq -e --arg effort "$effort" \
    '.effort == $effort and .base_url == "https://api.anthropic.com"' \
    "$out/run_env.json" >/dev/null
  grep -qx clean "$out/peek_check"
  grep -Eq '^FLAG discrepancy (yes|no)$' "$out/grade.txt"
}

run_one() {
  local effort="$1" task="$2" bout="$3" out
  out="$ROOT/bouts/$bout/$task/$MODEL/run-1"
  if [[ -f "$out/metrics.json" && -f "$out/grade.txt" ]]; then
    echo "smoke already complete: $effort $task"
    check_run "$effort" "$out"
    return
  fi
  [[ ! -e "$out" ]] || { echo "partial smoke exists: $out" >&2; exit 2; }
  ARENA_EFFORT="$effort" ARENA_SETTING_SOURCES=project \
    "$ROOT/bin/run-task.sh" "$ROOT/tasks/$task" "$MODEL" \
    "$ROOT/bouts/$bout" 1
  check_run "$effort" "$out"
}

run_one low   15-rollup        2026-08-21-verification-vs-effort-smoke-low
run_one xhigh 15-rollup-verify 2026-08-21-verification-vs-effort-smoke-xhigh
run_one xhigh 15-rollup        2026-08-21-verification-vs-effort-smoke-xhigh
run_one low   15-rollup-verify 2026-08-21-verification-vs-effort-smoke-low

python3 "$ROOT/bin/summarize.py" "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-low"
python3 "$ROOT/bin/summarize.py" "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-xhigh"
