#!/usr/bin/env bash
# Run ONE model on ONE task.
# usage: run-task.sh <task-dir> <model> <bout-dir>
set -u

TASK_DIR=$(cd "$1" && pwd)
MODEL="$2"
BOUT_DIR=$(mkdir -p "$3" && cd "$3" && pwd)
TASK_NAME=$(basename "$TASK_DIR")

OUT_DIR="$BOUT_DIR/$TASK_NAME/$MODEL"
WS="$OUT_DIR/workspace"
mkdir -p "$WS"

# Seed the workspace from the fixture, apply optional mutations, baseline it.
cp -a "$TASK_DIR/fixture/." "$WS/"
if [[ -f "$TASK_DIR/setup.sh" ]]; then
  (cd "$WS" && bash "$TASK_DIR/setup.sh")
fi
git -C "$WS" init -q
git -C "$WS" add -A
git -C "$WS" -c user.email=arena@local -c user.name=arena \
  -c commit.gpgsign=false commit -qm baseline

PROMPT=$(cat "$TASK_DIR/PROMPT.md")

MAX_TURNS="${ARENA_MAX_TURNS:-60}"
TIMEOUT_S="${ARENA_TIMEOUT_S:-1500}"

echo "[$TASK_NAME/$MODEL] starting"
START=$(date +%s.%N)
(
  cd "$WS" && timeout "$TIMEOUT_S" claude -p "$PROMPT" \
    --model "$MODEL" \
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

# Capture exactly what the agent changed.
git -C "$WS" add -A
git -C "$WS" diff --cached > "$OUT_DIR/workspace.diff"
git -C "$WS" diff --cached --stat > "$OUT_DIR/workspace.diffstat"

# Grade (hidden from the agent; runs against the workspace).
if [[ -f "$TASK_DIR/grade.sh" ]]; then
  bash "$TASK_DIR/grade.sh" "$WS" > "$OUT_DIR/grade.txt" 2>&1
  echo "$?" > "$OUT_DIR/grade_exit"
fi

# Metrics from transcript + result envelope.
python3 "$(dirname "$0")/metrics.py" "$OUT_DIR" "$MODEL" > "$OUT_DIR/metrics.json" 2>> "$OUT_DIR/stderr.log"

echo "[$TASK_NAME/$MODEL] done: agent_exit=$AGENT_EXIT grade_exit=$(cat "$OUT_DIR/grade_exit" 2>/dev/null || echo n/a) wall=$(cat "$OUT_DIR/wall_seconds")s"
