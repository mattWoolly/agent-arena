#!/usr/bin/env bash
# Run ONE model on ONE task.
# usage: run-task.sh <task-dir> <model> <bout-dir> [run-index]
#
# The agent works in a throwaway directory OUTSIDE this repo, so graders,
# hidden tests, and reference solutions are unreachable by construction —
# not just by convention. The finished workspace is copied back into the
# bout directory afterwards so published artifacts are unchanged in shape.
set -u

TASK_DIR=$(cd "$1" && pwd)
MODEL="$2"
BOUT_DIR=$(mkdir -p "$3" && cd "$3" && pwd)
RUN_IDX="${4:-}"
TASK_NAME=$(basename "$TASK_DIR")
ROOT=$(cd "$(dirname "$0")/.." && pwd)

OUT_DIR="$BOUT_DIR/$TASK_NAME/$MODEL"
[[ -n "$RUN_IDX" ]] && OUT_DIR="$OUT_DIR/run-$RUN_IDX"
mkdir -p "$OUT_DIR"
LABEL="$TASK_NAME/$MODEL${RUN_IDX:+ run-$RUN_IDX}"

# Seed an isolated workspace from the fixture, apply optional mutations, baseline it.
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

# Pinned run configuration — overridable, but always explicit and recorded,
# so a run never silently inherits this machine's user-level Claude config.
MAX_TURNS="${ARENA_MAX_TURNS:-60}"
TIMEOUT_S="${ARENA_TIMEOUT_S:-1500}"
EFFORT="${ARENA_EFFORT:-xhigh}"
SETTING_SOURCES="${ARENA_SETTING_SOURCES:-project}"

CLI_VERSION=$(claude --version 2>/dev/null | head -1)
cat > "$OUT_DIR/run_env.json" <<EOF
{
  "cli_version": "$CLI_VERSION",
  "effort": "$EFFORT",
  "setting_sources": "$SETTING_SOURCES",
  "max_turns": $MAX_TURNS,
  "timeout_s": $TIMEOUT_S,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "[$LABEL] starting"
START=$(date +%s.%N)
(
  cd "$WS" && timeout "$TIMEOUT_S" claude -p "$PROMPT" \
    --model "$MODEL" \
    --effort "$EFFORT" \
    --setting-sources "$SETTING_SOURCES" \
    --dangerously-skip-permissions \
    --max-turns "$MAX_TURNS" \
    --output-format stream-json --verbose \
    > "$OUT_DIR/transcript.jsonl" 2> "$OUT_DIR/stderr.log"
)
AGENT_EXIT=$?
END=$(date +%s.%N)
echo "$AGENT_EXIT" > "$OUT_DIR/agent_exit"
python3 -c "print(f'{$END - $START:.1f}')" > "$OUT_DIR/wall_seconds"

# Final result envelope is the last "result" event in the stream.
grep '"type":"result"' "$OUT_DIR/transcript.jsonl" | tail -1 > "$OUT_DIR/result.json" || true

# Peek check: the workspace is outside the repo, so any reference to the
# arena tree or grader assets in the transcript means the agent went looking.
PEEK=$(grep -o -e "$ROOT" -e "grade\.sh" -e "hidden_tests" -e "check-grader" \
  "$OUT_DIR/transcript.jsonl" | sort -u | tr '\n' ' ')
if [[ -n "$PEEK" ]]; then
  echo "suspect: $PEEK" > "$OUT_DIR/peek_check"
  echo "[$LABEL] WARNING: transcript references grader assets: $PEEK" >&2
else
  echo "clean" > "$OUT_DIR/peek_check"
fi

# Capture exactly what the agent changed.
git -C "$WS" add -A
git -C "$WS" diff --cached > "$OUT_DIR/workspace.diff"
git -C "$WS" diff --cached --stat > "$OUT_DIR/workspace.diffstat"

# Grade (hidden from the agent; runs against the workspace).
if [[ -f "$TASK_DIR/grade.sh" ]]; then
  bash "$TASK_DIR/grade.sh" "$WS" > "$OUT_DIR/grade.txt" 2>&1
  echo "$?" > "$OUT_DIR/grade_exit"
fi

# Publish the finished workspace into the bout dir (sans the scratch .git).
rm -rf "$OUT_DIR/workspace"
mkdir -p "$OUT_DIR/workspace"
cp -a "$WS/." "$OUT_DIR/workspace/"
rm -rf "$OUT_DIR/workspace/.git"

# Metrics from transcript + result envelope (+ run_env.json + peek_check).
python3 "$ROOT/bin/metrics.py" "$OUT_DIR" "$MODEL" > "$OUT_DIR/metrics.json" 2>> "$OUT_DIR/stderr.log"

echo "[$LABEL] done: agent_exit=$AGENT_EXIT grade_exit=$(cat "$OUT_DIR/grade_exit" 2>/dev/null || echo n/a) wall=$(cat "$OUT_DIR/wall_seconds")s"
