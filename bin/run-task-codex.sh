#!/usr/bin/env bash
# Run ONE model on ONE task, driven by the Codex CLI instead of Claude Code.
# usage: run-task-codex.sh <task-dir> <model> <bout-dir> [run-index]
#
# The harness-comparison counterpart of run-task.sh: same fixture seeding,
# same throwaway workspace outside the repo, same hidden graders, byte-
# identical PROMPT.md. Only the driver differs, which is the variable under
# test. The output-dir label is "<model>-codex" so cells never collide with
# Claude-Code-driven runs of the same model. Auth comes from the isolated
# CODEX_HOME in .codex-arena/ (API-key login, gitignored), never the user's
# ~/.codex ChatGPT session.
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

WS=$(mktemp -d "${TMPDIR:-/tmp}/arena-ws.XXXXXX")
trap 'rm -rf "$WS"' EXIT
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

MAX_TURNS="${ARENA_MAX_TURNS:-60}"
TIMEOUT_S="${ARENA_TIMEOUT_S:-1500}"
if [[ "${ARENA_PLAN_PROBE:-0}" == "1" ]]; then
  if [[ -z "${ARENA_CODEX_HOME:-}" ]]; then
    echo "ARENA_CODEX_HOME is required and must point to an isolated home outside the repository" > "$OUT_DIR/stderr.log"
    echo "missing external ARENA_CODEX_HOME" >&2
    exit 1
  fi
  CODEX_HOME=$(cd "$ARENA_CODEX_HOME" 2>/dev/null && pwd) || {
    echo "ARENA_CODEX_HOME is not an accessible directory" > "$OUT_DIR/stderr.log"
    exit 1
  }
  case "$CODEX_HOME" in
    "$ROOT"|"$ROOT"/*)
      echo "ARENA_CODEX_HOME must be outside the repository" > "$OUT_DIR/stderr.log"
      echo "refusing in-repository CODEX_HOME" >&2
      exit 1;;
  esac
  if [[ ! -f "$CODEX_HOME/auth.json" ]]; then
    echo "isolated CODEX_HOME has no auth.json" > "$OUT_DIR/stderr.log"
    exit 1
  fi
  if [[ -e "$CODEX_HOME/AGENTS.md" || -e "$CODEX_HOME/instructions.md" || -e "$CODEX_HOME/config.toml" ]]; then
    echo "isolated CODEX_HOME contains a config or user instruction file" > "$OUT_DIR/stderr.log"
    exit 1
  fi
else
  CODEX_HOME="${ARENA_CODEX_HOME:-$ROOT/.codex-arena}"
fi
export CODEX_HOME

# Preserve the exact bytes passed as the positional prompt.
printf '%s' "$PROMPT" > "$OUT_DIR/prompt.txt"
PROMPT_SHA=$(sha256sum "$OUT_DIR/prompt.txt" | awk '{print $1}')
PRICE_SHA=$(sha256sum "$ROOT/env/prices.json" | awk '{print $1}')
HARNESS_COMMIT=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)
HARNESS_DIRTY=false
git -C "$ROOT" diff --quiet && git -C "$ROOT" diff --cached --quiet || HARNESS_DIRTY=true

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
  "setting_sources": "none (--ignore-user-config, isolated CODEX_HOME)",
  "max_turns": $MAX_TURNS,
  "timeout_s": $TIMEOUT_S,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "[$LABEL] starting"
START=$(date +%s.%N)
: > "$OUT_DIR/last_message.txt"
(
  cd "$WS" && timeout "$TIMEOUT_S" codex exec --json \
    -m "$MODEL" \
    -s workspace-write \
    --dangerously-bypass-approvals-and-sandbox \
    --ignore-user-config \
    --skip-git-repo-check \
    -o "$OUT_DIR/last_message.txt" \
    "$PROMPT" \
    > "$OUT_DIR/transcript.jsonl" 2> "$OUT_DIR/stderr.log"
)
AGENT_EXIT=$?
END=$(date +%s.%N)
echo "$AGENT_EXIT" > "$OUT_DIR/agent_exit"
python3 -c "print(f'{$END - $START:.1f}')" > "$OUT_DIR/wall_seconds"

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

# Secret-leak check via the model label's leakscan (the OpenAI key is in the
# codex process env, so published artifacts must be scanned for it).
if [[ -f "$ROOT/env/$LABEL_MODEL.leakscan" ]]; then
  while IFS= read -r _sec; do
    [[ -z "$_sec" ]] && continue
    if grep -qF "$_sec" "$OUT_DIR/transcript.jsonl" \
         "$OUT_DIR/session.jsonl" 2>/dev/null || grep -rqF "$_sec" "$WS" 2>/dev/null; then
      echo "SECRET LEAK: leakscan value appears in transcript or workspace" >> "$OUT_DIR/peek_check"
      echo "[$LABEL] WARNING: SECRET LEAKED into published artifacts; do not publish this run" >&2
    fi
  done < <(bash "$ROOT/env/$LABEL_MODEL.leakscan" 2>/dev/null)
fi

git -C "$WS" add -A
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

# Repeat the leak scan after every publishable raw artifact has been written.
if [[ -f "$ROOT/env/$LABEL_MODEL.leakscan" ]]; then
  while IFS= read -r _sec; do
    [[ -z "$_sec" ]] && continue
    if grep -rqF "$_sec" "$OUT_DIR" "$WS" 2>/dev/null; then
      echo "SECRET LEAK: leakscan value appears in published artifacts" >> "$OUT_DIR/peek_check"
      echo "[$LABEL] WARNING: SECRET LEAKED into published artifacts; quarantine this run" >&2
    fi
  done < <(bash "$ROOT/env/$LABEL_MODEL.leakscan" 2>/dev/null)
fi

echo "[$LABEL] done: agent_exit=$AGENT_EXIT grade_exit=$(cat "$OUT_DIR/grade_exit" 2>/dev/null || echo n/a) wall=$(cat "$OUT_DIR/wall_seconds")s"
