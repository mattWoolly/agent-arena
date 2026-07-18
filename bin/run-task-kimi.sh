#!/usr/bin/env bash
# Run ONE model on ONE task, driven by Kimi Code (Moonshot's CLI).
# usage: run-task-kimi.sh <task-dir> <model-alias> <bout-dir> [run-index]
#
# Cross-driver counterpart of run-task.sh / run-task-codex.sh: same fixture
# seeding, throwaway workspace outside the repo, same hidden graders,
# byte-identical PROMPT.md. Cells are labeled "<alias>-kimicode". Kimi Code
# runs with HOME pointed at the isolated .kimi-arena/ (gitignored), whose
# config uses the metered Moonshot platform API key, never the user's
# ~/.kimi-code device-code login. Prompt mode auto-approves (no --yolo
# needed; the CLI rejects it alongside -p). Per-turn usage comes from the
# session's wire.jsonl, which is copied into the run dir.
set -u

TASK_DIR=$(cd "$1" && pwd)
ALIAS="$2"            # e.g. arena/k3
BOUT_DIR=$(mkdir -p "$3" && cd "$3" && pwd)
RUN_IDX="${4:-}"
TASK_NAME=$(basename "$TASK_DIR")
ROOT=$(cd "$(dirname "$0")/.." && pwd)
LABEL_MODEL="kimi-k3-kimicode"
KIMI_BIN="$HOME/.kimi-code/bin/kimi"
ARENA_HOME="$ROOT/.kimi-arena"

OUT_DIR="$BOUT_DIR/$TASK_NAME/$LABEL_MODEL"
[[ -n "$RUN_IDX" ]] && OUT_DIR="$OUT_DIR/run-$RUN_IDX"
mkdir -p "$OUT_DIR"
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

PROMPT=$(cat "$TASK_DIR/PROMPT.md")
TIMEOUT_S="${ARENA_TIMEOUT_S:-1500}"

CLI_VERSION="kimi-code $($KIMI_BIN -V 2>/dev/null | head -1)"
cat > "$OUT_DIR/run_env.json" <<EOF
{
  "cli_version": "$CLI_VERSION",
  "driver": "kimi -p --output-format stream-json (prompt mode auto-approves)",
  "base_url": "https://api.moonshot.ai/v1 (platform, metered)",
  "proxy_upstream": "none",
  "model_env": "none (isolated HOME=.kimi-arena)",
  "effort": "max (kimi-code default for k3)",
  "setting_sources": "arena config.toml only",
  "timeout_s": $TIMEOUT_S,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

WIRE_MARK=$(mktemp)
echo "[$LABEL] starting"
START=$(date +%s.%N)
(
  cd "$WS" && HOME="$ARENA_HOME" timeout "$TIMEOUT_S" "$KIMI_BIN" \
    -p "$PROMPT" \
    -m "$ALIAS" \
    --output-format stream-json \
    > "$OUT_DIR/transcript.jsonl" 2> "$OUT_DIR/stderr.log"
)
AGENT_EXIT=$?
END=$(date +%s.%N)
echo "$AGENT_EXIT" > "$OUT_DIR/agent_exit"
python3 -c "print(f'{$END - $START:.1f}')" > "$OUT_DIR/wall_seconds"

# This run's session journal: the only wire.jsonl newer than our marker.
WIRE=$(find "$ARENA_HOME/.kimi-code/sessions" -name wire.jsonl -newer "$WIRE_MARK" 2>/dev/null | head -1)
[[ -n "$WIRE" ]] && cp "$WIRE" "$OUT_DIR/wire.jsonl"
rm -f "$WIRE_MARK"

# Peek check, same contract as the other drivers.
PEEK=$(grep -o -e "$ROOT" -e "grade\.sh" -e "hidden_tests" -e "check-grader" \
  "$OUT_DIR/transcript.jsonl" | sort -u | tr '\n' ' ')
if [[ -n "$PEEK" ]]; then
  echo "suspect: $PEEK" > "$OUT_DIR/peek_check"
  echo "[$LABEL] WARNING: transcript references grader assets: $PEEK" >&2
else
  echo "clean" > "$OUT_DIR/peek_check"
fi

# Secret-leak check: the platform key sits in the arena config the agent's
# shell can read (its HOME points there), so scan everything we publish.
if [[ -f "$ROOT/env/$LABEL_MODEL.leakscan" ]]; then
  while IFS= read -r _sec; do
    [[ -z "$_sec" ]] && continue
    if grep -qF "$_sec" "$OUT_DIR/transcript.jsonl" "$OUT_DIR/wire.jsonl" 2>/dev/null || \
       grep -rqF "$_sec" "$WS" 2>/dev/null; then
      echo "SECRET LEAK: leakscan value appears in published artifacts" >> "$OUT_DIR/peek_check"
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

python3 "$ROOT/bin/metrics_kimi.py" "$OUT_DIR" "$LABEL_MODEL" > "$OUT_DIR/metrics.json" 2>> "$OUT_DIR/stderr.log"

echo "[$LABEL] done: agent_exit=$AGENT_EXIT grade_exit=$(cat "$OUT_DIR/grade_exit" 2>/dev/null || echo n/a) wall=$(cat "$OUT_DIR/wall_seconds")s"
