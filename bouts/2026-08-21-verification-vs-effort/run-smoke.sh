#!/usr/bin/env bash
# Four development-only smokes, one per factorial cell.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
MODEL=claude-sonnet-5
CLI_VERSION="2.1.239 (Claude Code)"

# Force native subscription OAuth. Pay-as-you-go keys and alternate provider
# selectors must not shadow the Claude.ai Max subscription.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL
unset ANTHROPIC_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL
unset ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL
unset ANTHROPIC_CUSTOM_HEADERS ANTHROPIC_BETAS
unset CLAUDE_CODE_SUBAGENT_MODEL ARENA_PROXY_UPSTREAM
unset CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY
[[ ! -e "$ROOT/env/$MODEL.env" ]] || {
  echo "refusing native OAuth smoke: env/$MODEL.env exists" >&2
  exit 2
}

write_auth_status() {
  local destination="$1" raw
  if ! raw=$(claude auth status --json 2>/dev/null); then
    echo "unable to verify Claude authentication" >&2
    return 1
  fi
  jq -e '
    .loggedIn == true
    and .authMethod == "claude.ai"
    and .apiProvider == "firstParty"
    and .apiKeySource == null
    and .subscriptionType == "max"
  ' <<<"$raw" >/dev/null || {
    echo "refusing run: Claude auth is not first-party Max subscription OAuth" >&2
    return 1
  }
  jq '{loggedIn, authMethod, apiProvider, apiKeySource, subscriptionType}' \
    <<<"$raw" > "$destination"
}

check_auth_status() {
  jq -e '
    keys == ["apiKeySource", "apiProvider", "authMethod", "loggedIn", "subscriptionType"]
    and .loggedIn == true
    and .authMethod == "claude.ai"
    and .apiProvider == "firstParty"
    and .apiKeySource == null
    and .subscriptionType == "max"
  ' "$1" >/dev/null
}

check_grade() {
  local out="$1" id
  [[ "$(<"$out/grade_exit")" == 0 ]]
  [[ "$(grep -Ec '^ITEM ' "$out/grade.txt")" -eq 8 ]]
  for id in q_revenue q_costs q_net margin net_adds close_rate mom_jun mom_jul; do
    [[ "$(grep -Ec "^ITEM $id (OK|WRONG|MISSING)( |$)" "$out/grade.txt")" -eq 1 ]]
  done
  [[ "$(grep -Ec '^FLAG ' "$out/grade.txt")" -eq 1 ]]
  [[ "$(grep -Ec '^FLAG discrepancy (yes|no)$' "$out/grade.txt")" -eq 1 ]]
  [[ "$(grep -Ec '^SCORE: [0-9]+/[0-9]+$' "$out/grade.txt")" -eq 1 ]]
}

check_run() {
  local effort="$1" out="$2"
  jq -e --arg model "$MODEL" '
    .served_model == $model and .served_model_leak == false
    and .agent_exit == 0 and .is_error == false
    and (.total_cost_usd | type == "number") and .total_cost_usd >= 0
    and (.output_tokens | type == "number") and .output_tokens >= 0
    and (.num_turns | type == "number") and .num_turns >= 0
    and (.wall_seconds | type == "number") and .wall_seconds >= 0
  ' "$out/metrics.json" >/dev/null
  jq -e --arg effort "$effort" --arg cli "$CLI_VERSION" '
    .effort == $effort and .base_url == "https://api.anthropic.com"
    and .proxy_upstream == "none" and .model_env == "none"
    and .setting_sources == "project" and .max_turns == 60
    and .timeout_s == 1500 and .cli_version == $cli
  ' "$out/run_env.json" >/dev/null
  check_auth_status "$out/auth_status.json"
  grep -qx clean "$out/peek_check"
  check_grade "$out"
}

smoke_total() {
  local bout metrics cost total=0
  for bout in \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-low" \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-xhigh"; do
    [[ -d "$bout" ]] || { echo "missing bout directory: $bout" >&2; return 1; }
    while IFS= read -r -d '' metrics; do
      if ! cost=$(jq -er '
        if ((.total_cost_usd | type) == "number" and .total_cost_usd >= 0)
        then .total_cost_usd
        else error("invalid total_cost_usd")
        end
      ' "$metrics"); then
        echo "invalid cost artifact: $metrics" >&2
        return 1
      fi
      total=$(awk -v total="$total" -v cost="$cost" \
        'BEGIN { printf "%.17g", total + cost }')
    done < <(find "$bout" -mindepth 4 -maxdepth 4 -type f \
                    -name metrics.json -print0)
  done
  printf '%s\n' "$total"
}

enforce_budget() {
  local cost
  cost=$(smoke_total)
  if awk -v total="$cost" 'BEGIN { exit !(total > 5) }'; then
    echo "smoke notional cost exceeded the USD 5 stop: $cost" >&2
    return 1
  fi
}

if [[ "${1:-}" == --check-artifacts ]]; then
  [[ "$#" -eq 3 ]] || {
    echo "usage: $0 --check-artifacts <effort> <run-dir>" >&2
    exit 2
  }
  check_run "$2" "$3"
  exit
fi
[[ "$#" -eq 0 ]] || { echo "usage: $0 [--check-artifacts ...]" >&2; exit 2; }

run_one() {
  local effort="$1" task="$2" bout="$3" out
  enforce_budget
  out="$ROOT/bouts/$bout/$task/$MODEL/run-1"
  if [[ -f "$out/metrics.json" && -f "$out/grade.txt" &&
        -f "$out/grade_exit" && -f "$out/run_env.json" &&
        -f "$out/peek_check" && -f "$out/auth_status.json" ]]; then
    echo "smoke already complete: $effort $task"
    check_run "$effort" "$out"
    return
  fi
  [[ ! -e "$out" ]] || { echo "partial smoke exists: $out" >&2; exit 2; }
  mkdir -p "$out"
  write_auth_status "$out/auth_status.json"
  ARENA_EFFORT="$effort" ARENA_SETTING_SOURCES=project \
    ARENA_MAX_TURNS=60 ARENA_TIMEOUT_S=1500 \
    "$ROOT/bin/run-task.sh" "$ROOT/tasks/$task" "$MODEL" \
    "$ROOT/bouts/$bout" 1
  check_run "$effort" "$out"
  enforce_budget
}

run_one low   15-rollup        2026-08-21-verification-vs-effort-smoke-low
run_one xhigh 15-rollup-verify 2026-08-21-verification-vs-effort-smoke-xhigh
run_one xhigh 15-rollup        2026-08-21-verification-vs-effort-smoke-xhigh
run_one low   15-rollup-verify 2026-08-21-verification-vs-effort-smoke-low

python3 "$ROOT/bin/summarize.py" "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-low"
python3 "$ROOT/bin/summarize.py" "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-xhigh"
