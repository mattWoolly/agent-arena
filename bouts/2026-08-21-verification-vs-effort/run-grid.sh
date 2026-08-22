#!/usr/bin/env bash
# Execute the precommitted ORDER.tsv serially and resume only complete cells.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
ORDER="$HERE/ORDER.tsv"
LOG="$HERE/RUN_LOG.tsv"
CLI_VERSION="2.1.239 (Claude Code)"

# Force native subscription OAuth. A pay-as-you-go key must not shadow it.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL
unset ANTHROPIC_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL
unset ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL
unset CLAUDE_CODE_SUBAGENT_MODEL ARENA_PROXY_UPSTREAM
[[ ! -e "$ROOT/env/claude-sonnet-5.env" ]] || {
  echo "refusing native OAuth grid: env/claude-sonnet-5.env exists" >&2
  exit 2
}

check_run() {
  local effort="$1" model="$2" out="$3"
  jq -e --arg model "$model" \
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
  [[ -f "$out/grade_exit" ]]
  grep -qx clean "$out/peek_check"
  [[ "$(grep -Ec '^FLAG (finance|support|delivery) (yes|no)$' "$out/grade.txt")" -eq 3 ]]
  grep -Eq '^FALSE_FLAG security (yes|no)$' "$out/grade.txt"
}

notional_total() {
  find "$ROOT/bouts/2026-08-21-verification-vs-effort-low" \
       "$ROOT/bouts/2026-08-21-verification-vs-effort-xhigh" \
       -type f -name metrics.json -print0 2>/dev/null \
    | xargs -0 -r jq -r '.total_cost_usd // 0' \
    | awk '{ total += $1 } END { printf "%.5f", total }'
}

if [[ ! -f "$LOG" ]]; then
  printf 'timestamp\tsequence\teffort\ttask\tmodel\trepeat\tstatus\n' > "$LOG"
fi

tail -n +2 "$ORDER" | while IFS=$'\t' read -r sequence effort task model repeat; do
  bout="$ROOT/bouts/2026-08-21-verification-vs-effort-$effort"
  out="$bout/$task/$model/run-$repeat"
  if [[ -f "$out/metrics.json" && -f "$out/grade.txt" &&
        -f "$out/grade_exit" && -f "$out/run_env.json" &&
        -f "$out/peek_check" ]]; then
    check_run "$effort" "$model" "$out"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sequence" "$effort" "$task" \
      "$model" "$repeat" skipped-complete >> "$LOG"
    continue
  fi
  [[ ! -e "$out" ]] || { echo "partial run exists: $out" >&2; exit 2; }
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sequence" "$effort" "$task" \
    "$model" "$repeat" starting >> "$LOG"
  ARENA_EFFORT="$effort" ARENA_SETTING_SOURCES=project \
    ARENA_MAX_TURNS=60 ARENA_TIMEOUT_S=1500 \
    "$ROOT/bin/run-task.sh" "$ROOT/tasks/$task" "$model" "$bout" "$repeat"
  [[ -f "$out/metrics.json" && -f "$out/grade.txt" &&
     -f "$out/grade_exit" && -f "$out/run_env.json" &&
     -f "$out/peek_check" ]] || {
    echo "run did not produce complete artifacts: $out" >&2
    exit 3
  }
  check_run "$effort" "$model" "$out"
  total=$(notional_total)
  if awk -v total="$total" 'BEGIN { exit !(total > 20) }'; then
    echo "notional confirmation cost exceeded the USD 20 run stop: $total" >&2
    exit 4
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sequence" "$effort" "$task" \
    "$model" "$repeat" complete >> "$LOG"
done

python3 "$ROOT/bin/summarize.py" "$ROOT/bouts/2026-08-21-verification-vs-effort-low"
python3 "$ROOT/bin/summarize.py" "$ROOT/bouts/2026-08-21-verification-vs-effort-xhigh"
