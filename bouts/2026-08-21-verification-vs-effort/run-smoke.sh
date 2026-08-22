#!/usr/bin/env bash
# Four development-only smokes, one per factorial cell.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
MODEL=claude-sonnet-5
CLI_VERSION="2.1.239 (Claude Code)"

# Force native subscription OAuth. A pay-as-you-go key must not shadow it.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL
unset ANTHROPIC_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL
unset ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL
unset CLAUDE_CODE_SUBAGENT_MODEL ARENA_PROXY_UPSTREAM
[[ ! -e "$ROOT/env/$MODEL.env" ]] || {
  echo "refusing native OAuth smoke: env/$MODEL.env exists" >&2
  exit 2
}

check_run() {
  local effort="$1" out="$2"
  jq -e --arg model "$MODEL" \
    '.served_model == $model and .served_model_leak == false
     and .agent_exit == 0 and .is_error == false
     and (.total_cost_usd | type == "number")
     and (.output_tokens | type == "number")
     and (.num_turns | type == "number")
     and (.wall_seconds | type == "number")' \
    "$out/metrics.json" >/dev/null
  jq -e --arg effort "$effort" --arg cli "$CLI_VERSION" \
    '.effort == $effort and .base_url == "https://api.anthropic.com"
     and .proxy_upstream == "none" and .model_env == "none"
     and .setting_sources == "project" and .max_turns == 60
     and .timeout_s == 1500 and .cli_version == $cli' \
    "$out/run_env.json" >/dev/null
  [[ "$(cat "$out/grade_exit")" == 0 ]]
  grep -qx clean "$out/peek_check"
  grep -Eq '^FLAG discrepancy (yes|no)$' "$out/grade.txt"
}

run_one() {
  local effort="$1" task="$2" bout="$3" out
  out="$ROOT/bouts/$bout/$task/$MODEL/run-1"
  if [[ -f "$out/metrics.json" && -f "$out/grade.txt" &&
        -f "$out/grade_exit" && -f "$out/run_env.json" &&
        -f "$out/peek_check" ]]; then
    echo "smoke already complete: $effort $task"
    check_run "$effort" "$out"
    return
  fi
  [[ ! -e "$out" ]] || { echo "partial smoke exists: $out" >&2; exit 2; }
  ARENA_EFFORT="$effort" ARENA_SETTING_SOURCES=project \
    ARENA_MAX_TURNS=60 ARENA_TIMEOUT_S=1500 \
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
