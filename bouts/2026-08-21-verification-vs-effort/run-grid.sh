#!/usr/bin/env bash
# Execute the precommitted ORDER.tsv serially and resume only complete cells.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
ORDER="$HERE/ORDER.tsv"
LOG="$HERE/RUN_LOG.tsv"
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
  echo "refusing native OAuth grid: env/$MODEL.env exists" >&2
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
  local out="$1" grade_exit id source
  grade_exit=$(<"$out/grade_exit")
  [[ "$grade_exit" =~ ^[0-9]{1,3}$ ]]
  (( 10#$grade_exit <= 255 ))

  [[ "$(grep -Ec '^ITEM ' "$out/grade.txt")" -eq 6 ]]
  for id in q3_revenue q3_spend operating_surplus support_close_rate \
            launch_date security_resolution_rate; do
    [[ "$(grep -Ec "^ITEM $id (OK|WRONG|MISSING)( |$)" "$out/grade.txt")" -eq 1 ]]
  done
  [[ "$(grep -Ec '^BASIS ' "$out/grade.txt")" -eq 3 ]]
  for source in finance support delivery; do
    [[ "$(grep -Ec "^BASIS $source (detail|stated|other)$" "$out/grade.txt")" -eq 1 ]]
  done
  [[ "$(grep -Ec '^CONTROL ' "$out/grade.txt")" -eq 1 ]]
  [[ "$(grep -Ec '^CONTROL security (correct|wrong)$' "$out/grade.txt")" -eq 1 ]]
  [[ "$(grep -Ec '^SCORE: [0-9]+/[0-9]+$' "$out/grade.txt")" -eq 1 ]]
}

check_run() {
  local effort="$1" model="$2" out="$3"
  jq -e --arg model "$model" '
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

sum_notional() {
  find "$@" -type f -name metrics.json -print0 2>/dev/null \
    | xargs -0 -r jq -r '.total_cost_usd // 0' \
    | awk '{ total += $1 } END { printf "%.5f", total }'
}

confirmation_total() {
  sum_notional \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-low" \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-xhigh"
}

smoke_total() {
  sum_notional \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-low" \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-xhigh"
}

all_total() {
  sum_notional \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-low" \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-smoke-xhigh" \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-low" \
    "$ROOT/bouts/2026-08-21-verification-vs-effort-xhigh"
}

enforce_budget() {
  local smoke_cost confirmation_cost total_cost
  smoke_cost=$(smoke_total)
  confirmation_cost=$(confirmation_total)
  total_cost=$(all_total)
  if awk -v total="$smoke_cost" 'BEGIN { exit !(total > 5) }'; then
    echo "smoke notional cost exceeded the USD 5 stop: $smoke_cost" >&2
    return 1
  fi
  if awk -v total="$confirmation_cost" 'BEGIN { exit !(total > 20) }'; then
    echo "confirmation notional cost exceeded the USD 20 stop: $confirmation_cost" >&2
    return 1
  fi
  if awk -v total="$total_cost" 'BEGIN { exit !(total > 25) }'; then
    echo "total notional cost exceeded the USD 25 hard stop: $total_cost" >&2
    return 1
  fi
}

check_smokes() {
  local effort task bout out
  while IFS=$'\t' read -r effort task bout; do
    out="$ROOT/bouts/$bout/$task/$MODEL/run-1"
    [[ -f "$out/metrics.json" && -f "$out/grade.txt" &&
       -f "$out/grade_exit" && -f "$out/run_env.json" &&
       -f "$out/peek_check" && -f "$out/auth_status.json" ]] || {
      echo "required smoke is missing or incomplete: $out" >&2
      return 1
    }
    "$HERE/run-smoke.sh" --check-artifacts "$effort" "$out" || {
      echo "required smoke failed validation: $out" >&2
      return 1
    }
  done <<'EOF'
low	15-rollup	2026-08-21-verification-vs-effort-smoke-low
low	15-rollup-verify	2026-08-21-verification-vs-effort-smoke-low
xhigh	15-rollup	2026-08-21-verification-vs-effort-smoke-xhigh
xhigh	15-rollup-verify	2026-08-21-verification-vs-effort-smoke-xhigh
EOF
}

if [[ "${1:-}" == --check-artifacts ]]; then
  [[ "$#" -eq 4 ]] || {
    echo "usage: $0 --check-artifacts <effort> <model> <run-dir>" >&2
    exit 2
  }
  check_run "$2" "$3" "$4"
  exit
fi
if [[ "${1:-}" == --check-smokes ]]; then
  [[ "$#" -eq 1 ]] || { echo "usage: $0 --check-smokes" >&2; exit 2; }
  enforce_budget
  check_smokes
  exit
fi
[[ "$#" -eq 0 ]] || {
  echo "usage: $0 [--check-artifacts ...|--check-smokes]" >&2
  exit 2
}

enforce_budget
check_smokes

if [[ ! -f "$LOG" ]]; then
  printf 'timestamp\tsequence\teffort\ttask\tmodel\trepeat\tstatus\n' > "$LOG"
fi

tail -n +2 "$ORDER" | while IFS=$'\t' read -r sequence effort task model repeat; do
  enforce_budget
  [[ "$model" == "$MODEL" ]]
  [[ "$effort" == low || "$effort" == xhigh ]]
  [[ "$task" == 16-source-audit || "$task" == 16-source-audit-verify ]]
  [[ "$repeat" =~ ^([1-9]|10)$ ]]
  bout="$ROOT/bouts/2026-08-21-verification-vs-effort-$effort"
  out="$bout/$task/$model/run-$repeat"
  if [[ -f "$out/metrics.json" && -f "$out/grade.txt" &&
        -f "$out/grade_exit" && -f "$out/run_env.json" &&
        -f "$out/peek_check" && -f "$out/auth_status.json" ]]; then
    check_run "$effort" "$model" "$out"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sequence" "$effort" "$task" \
      "$model" "$repeat" skipped-complete >> "$LOG"
    continue
  fi
  [[ ! -e "$out" ]] || { echo "partial run exists: $out" >&2; exit 2; }
  mkdir -p "$out"
  write_auth_status "$out/auth_status.json"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sequence" "$effort" "$task" \
    "$model" "$repeat" starting >> "$LOG"
  ARENA_EFFORT="$effort" ARENA_SETTING_SOURCES=project \
    ARENA_MAX_TURNS=60 ARENA_TIMEOUT_S=1500 \
    "$ROOT/bin/run-task.sh" "$ROOT/tasks/$task" "$model" "$bout" "$repeat"
  [[ -f "$out/metrics.json" && -f "$out/grade.txt" &&
     -f "$out/grade_exit" && -f "$out/run_env.json" &&
     -f "$out/peek_check" && -f "$out/auth_status.json" ]] || {
    echo "run did not produce complete artifacts: $out" >&2
    exit 3
  }
  check_run "$effort" "$model" "$out"
  enforce_budget
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sequence" "$effort" "$task" \
    "$model" "$repeat" complete >> "$LOG"
done

python3 "$ROOT/bin/summarize.py" "$ROOT/bouts/2026-08-21-verification-vs-effort-low"
python3 "$ROOT/bin/summarize.py" "$ROOT/bouts/2026-08-21-verification-vs-effort-xhigh"
