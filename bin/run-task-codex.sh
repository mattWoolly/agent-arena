#!/usr/bin/env bash
# Run ONE model on ONE task, driven by the Codex CLI instead of Claude Code.
# usage: run-task-codex.sh <task-dir> <model> <bout-dir> [run-index]
#
# The harness-comparison counterpart of run-task.sh: same fixture seeding,
# same throwaway workspace outside the repo, same hidden graders, byte-
# identical PROMPT.md. Only the driver differs, which is the variable under
# test. The output-dir label is "<model>-codex" so cells never collide with
# Claude-Code-driven runs of the same model. A fresh CODEX_HOME is created for
# every plan-probe slot from an exact external auth-only source.
set -u

TASK_DIR=$(cd "$1" && pwd)
MODEL="$2"
BOUT_DIR=$(mkdir -p "$3" && cd "$3" && pwd)
RUN_IDX="${4:-}"
TASK_NAME=$(basename "$TASK_DIR")
ROOT=$(cd "$(dirname "$0")/.." && pwd)
LABEL_MODEL="$MODEL-codex"

OUT_DIR="$BOUT_DIR/$TASK_NAME/$LABEL_MODEL"
[[ -n "$RUN_IDX" ]] && OUT_DIR="$OUT_DIR/run-$RUN_IDX"
mkdir -p "$(dirname "$OUT_DIR")"
if ! mkdir "$OUT_DIR"; then
  echo "refusing to overwrite existing run artifact directory: $OUT_DIR" >&2
  exit 2
fi
LABEL="$TASK_NAME/$LABEL_MODEL${RUN_IDX:+ run-$RUN_IDX}"

MAX_TURNS="${ARENA_MAX_TURNS:-60}"
TIMEOUT_S="${ARENA_TIMEOUT_S:-1500}"
RUN_AUTH_HOME=""
RUNTIME_SCAN_HOME=""
RULE_ARGS=()
SETTING_SOURCES_REC="none (--ignore-user-config, isolated CODEX_HOME)"
if [[ "${ARENA_PLAN_PROBE:-0}" == "1" ]]; then
  if [[ -L /tmp || ! -d /tmp ]]; then
    echo "fixed plan-probe temp root /tmp must be a real directory" > "$OUT_DIR/stderr.log"
    exit 1
  fi
  PLAN_TMPDIR="${ARENA_PLAN_TMPDIR:-/tmp}"
  if [[ "$PLAN_TMPDIR" != /* || -L "$PLAN_TMPDIR" || ! -d "$PLAN_TMPDIR" ]]; then
    echo "plan-probe temp root must be an absolute real directory" > "$OUT_DIR/stderr.log"
    exit 1
  fi
  TMPDIR=$(cd "$PLAN_TMPDIR" && pwd -P) || exit 1
  case "$TMPDIR" in
    "$ROOT"|"$ROOT"/*)
      echo "fixed plan-probe temp root must be outside the repository" > "$OUT_DIR/stderr.log"
      exit 1;;
  esac
  case "$TMPDIR" in
    /tmp|/tmp/arena-plan-attempt.*/runtime) ;;
    *) echo "plan-probe temp root is outside the frozen /tmp policy" > "$OUT_DIR/stderr.log"; exit 1;;
  esac
  export TMPDIR
  if [[ -z "${ARENA_CODEX_HOME:-}" ]]; then
    echo "ARENA_CODEX_HOME is required and must point to an isolated home outside the repository" > "$OUT_DIR/stderr.log"
    echo "missing external ARENA_CODEX_HOME" >&2
    exit 1
  fi
  SOURCE_CODEX_HOME=$(cd "$ARENA_CODEX_HOME" 2>/dev/null && pwd) || {
    echo "ARENA_CODEX_HOME is not an accessible directory" > "$OUT_DIR/stderr.log"
    exit 1
  }
  case "$SOURCE_CODEX_HOME" in
    "$ROOT"|"$ROOT"/*)
      echo "ARENA_CODEX_HOME must be outside the repository" > "$OUT_DIR/stderr.log"
      echo "refusing in-repository CODEX_HOME" >&2
      exit 1;;
  esac
  if [[ ! -f "$SOURCE_CODEX_HOME/auth.json" ]]; then
    echo "isolated CODEX_HOME has no auth.json" > "$OUT_DIR/stderr.log"
    exit 1
  fi
  RUN_AUTH_HOME=$(mktemp -d "${TMPDIR:-/tmp}/arena-codex-home.XXXXXX") || {
    echo "could not create disposable Codex home" > "$OUT_DIR/stderr.log"
    exit 1
  }
  chmod 700 "$RUN_AUTH_HOME"
  cp "$SOURCE_CODEX_HOME/auth.json" "$RUN_AUTH_HOME/auth.json"
  chmod 600 "$RUN_AUTH_HOME/auth.json"
  CODEX_HOME="$RUN_AUTH_HOME"
  RULE_ARGS=(--ignore-rules)
  SETTING_SOURCES_REC="none (--ignore-user-config, --ignore-rules, fresh auth-only HOME/CODEX_HOME)"
else
  CODEX_HOME="${ARENA_CODEX_HOME:-$ROOT/.codex-arena}"
fi
export CODEX_HOME

WS=$(mktemp -d "${TMPDIR:-/tmp}/arena-ws.XXXXXX") || {
  echo "could not create disposable target workspace" > "$OUT_DIR/stderr.log"
  exit 1
}
trap 'rm -rf "$WS" ${RUN_AUTH_HOME:+"$RUN_AUTH_HOME"} ${RUNTIME_SCAN_HOME:+"$RUNTIME_SCAN_HOME"}' EXIT
cp -a "$TASK_DIR/fixture/." "$WS/"
if [[ -f "$TASK_DIR/setup.sh" ]]; then
  (cd "$WS" && bash "$TASK_DIR/setup.sh")
fi
git -C "$WS" init -q
git -C "$WS" add -A
git -C "$WS" -c user.email=arena@local -c user.name=arena \
  -c commit.gpgsign=false commit -qm baseline

PROMPT=$(cat "$TASK_DIR/PROMPT.md"; printf '\034')
PROMPT=${PROMPT%$'\034'}

# Preserve the exact bytes passed as the positional prompt.
printf '%s' "$PROMPT" > "$OUT_DIR/prompt.txt"
PROMPT_SHA=$(sha256sum "$OUT_DIR/prompt.txt" | awk '{print $1}')
PRICE_SHA=$(sha256sum "$ROOT/env/prices.json" | awk '{print $1}')
if [[ "${ARENA_PLAN_PROBE:-0}" == "1" && -n "${ARENA_HARNESS_COMMIT:-}" ]]; then
  HARNESS_COMMIT="$ARENA_HARNESS_COMMIT"
  HARNESS_DIRTY="${ARENA_HARNESS_TRACKED_DIRTY:-true}"
else
  HARNESS_COMMIT=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)
  HARNESS_DIRTY=false
  git -C "$ROOT" diff --quiet && git -C "$ROOT" diff --cached --quiet || HARNESS_DIRTY=true
fi

CLI_VERSION=$(codex --version 2>/dev/null | head -1)
cat > "$OUT_DIR/run_env.json" <<EOF
{
  "cli_version": "$CLI_VERSION",
  "driver": "codex exec --json -s workspace-write --dangerously-bypass-approvals-and-sandbox",
  "harness_commit": "$HARNESS_COMMIT",
  "harness_tracked_dirty": $HARNESS_DIRTY,
  "prompt_sha256": "$PROMPT_SHA",
  "price_sheet_sha256": "$PRICE_SHA",
  "base_url": "https://api.openai.com (native)",
  "proxy_upstream": "none",
  "model_env": "none",
  "effort": "codex-default",
  "setting_sources": "$SETTING_SOURCES_REC",
  "max_turns": $MAX_TURNS,
  "timeout_s": $TIMEOUT_S,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "[$LABEL] starting"
START=$(date +%s.%N)
: > "$OUT_DIR/last_message.txt"
date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT_DIR/target_started"
(
  cd "$WS" && env -u ARENA_CODEX_HOME -u ARENA_PLAN_TMPDIR -u ARENA_HARNESS_COMMIT \
    -u ARENA_HARNESS_TRACKED_DIRTY HOME="$CODEX_HOME" CODEX_HOME="$CODEX_HOME" \
    timeout --kill-after=10s "$TIMEOUT_S" codex exec --json \
    -m "$MODEL" \
    -s workspace-write \
    --dangerously-bypass-approvals-and-sandbox \
    --ignore-user-config \
    "${RULE_ARGS[@]}" \
    --skip-git-repo-check \
    -o "$OUT_DIR/last_message.txt" \
    "$PROMPT" < /dev/null \
    > "$OUT_DIR/transcript.jsonl" 2> "$OUT_DIR/stderr.log"
)
AGENT_EXIT=$?
date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT_DIR/target_returned"
END=$(date +%s.%N)
echo "$AGENT_EXIT" > "$OUT_DIR/agent_exit"
python3 -c "from decimal import Decimal; print(Decimal('$END') - Decimal('$START'))" > "$OUT_DIR/wall_seconds"

# Codex's public JSON stream omits the exact base/developer instruction stack.
# Its session rollout contains that context. Associate it by the thread id
# emitted in transcript.jsonl, never by timestamps, and preserve it raw.
THREAD_ID=$(jq -r 'select(.type == "thread.started") | .thread_id' \
  "$OUT_DIR/transcript.jsonl" 2>/dev/null | head -1)
if [[ -n "$THREAD_ID" && "$THREAD_ID" != "null" ]]; then
  SESSION_FILE=$(find "$CODEX_HOME/sessions" -type f -name "*$THREAD_ID.jsonl" \
    -print -quit 2>/dev/null)
  [[ -n "$SESSION_FILE" ]] && cp "$SESSION_FILE" "$OUT_DIR/session.jsonl"
fi

# Peek check, same contract as run-task.sh.
PEEK=$(grep -o -e "$ROOT" -e "grade\.sh" -e "hidden_tests" -e "check-grader" \
  "$OUT_DIR/transcript.jsonl" | sort -u | tr '\n' ' ')
if [[ -n "$PEEK" ]]; then
  echo "suspect: $PEEK" > "$OUT_DIR/peek_check"
  echo "[$LABEL] WARNING: transcript references grader assets: $PEEK" >&2
else
  echo "clean" > "$OUT_DIR/peek_check"
fi

# Preserve the established leakscan behavior for ordinary bouts. The planning
# probe instead uses the wrapper's exact parsed-credential scanner and
# quarantine path, which also covers session.jsonl and every published entry.
if [[ "${ARENA_PLAN_PROBE:-0}" != "1" && -f "$ROOT/env/$LABEL_MODEL.leakscan" ]]; then
  while IFS= read -r _sec; do
    [[ -z "$_sec" ]] && continue
    if grep -qF "$_sec" "$OUT_DIR/transcript.jsonl" || grep -rqF "$_sec" "$WS" 2>/dev/null; then
      echo "SECRET LEAK: leakscan value appears in transcript or workspace" >> "$OUT_DIR/peek_check"
      echo "[$LABEL] WARNING: SECRET LEAKED into published artifacts; do not publish this run" >&2
    fi
  done < <(bash "$ROOT/env/$LABEL_MODEL.leakscan" 2>/dev/null)
fi

if ! git -C "$WS" add -A; then
  echo "workspace capture failed" >> "$OUT_DIR/stderr.log"
  exit 3
fi
git -C "$WS" diff --cached > "$OUT_DIR/workspace.diff"
git -C "$WS" diff --cached --stat > "$OUT_DIR/workspace.diffstat"

if [[ -f "$TASK_DIR/grade.sh" ]]; then
  bash "$TASK_DIR/grade.sh" "$WS" > "$OUT_DIR/grade.txt" 2>&1
  echo "$?" > "$OUT_DIR/grade_exit"
fi

rm -rf "$OUT_DIR/workspace"
mkdir -p "$OUT_DIR/workspace"
cp -a "$WS/." "$OUT_DIR/workspace/"
rm -rf "$OUT_DIR/workspace/.git"

python3 "$ROOT/bin/metrics_codex.py" "$OUT_DIR" "$LABEL_MODEL" > "$OUT_DIR/metrics.json" 2>> "$OUT_DIR/stderr.log"

# Scan with any final/rotated auth.json values from the disposable runtime
# home. Only an aggregate receipt leaves the scan home; exit 86 requires the
# parent wrapper to quarantine the attempt.
if [[ "${ARENA_PLAN_PROBE:-0}" == "1" ]]; then
  RUNTIME_RECEIPT="$OUT_DIR/credential_scan.runtime.json"
  if [[ -e "$RUNTIME_RECEIPT" || -L "$RUNTIME_RECEIPT" ]]; then
    echo "runtime credential scan receipt path already exists" >> "$OUT_DIR/stderr.log"
    exit 86
  fi
  RUNTIME_SCAN_HOME=$(mktemp -d "${TMPDIR:-/tmp}/arena-codex-scan.XXXXXX") || {
    echo "could not create runtime credential scan home" >> "$OUT_DIR/stderr.log"
    exit 86
  }
  if ! chmod 700 "$RUNTIME_SCAN_HOME" || \
     ! cp "$CODEX_HOME/auth.json" "$RUNTIME_SCAN_HOME/auth.json" || \
     ! chmod 600 "$RUNTIME_SCAN_HOME/auth.json" || \
     ! python3 "$ROOT/bin/credential_guard.py" codex "$RUNTIME_SCAN_HOME" "$OUT_DIR" \
       > "$RUNTIME_RECEIPT"; then
    echo "runtime credential-state scan failed; parent quarantine required" >> "$OUT_DIR/stderr.log"
    exit 86
  fi
  rm -rf "$RUNTIME_SCAN_HOME"
  RUNTIME_SCAN_HOME=""
fi

echo "[$LABEL] done: agent_exit=$AGENT_EXIT grade_exit=$(cat "$OUT_DIR/grade_exit" 2>/dev/null || echo n/a) wall=$(cat "$OUT_DIR/wall_seconds")s"
