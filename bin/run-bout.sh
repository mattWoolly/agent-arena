#!/usr/bin/env bash
# Run a bout: every task (or a subset) for two models, pairwise-parallel.
# usage: run-bout.sh <bout-name> <model-a> <model-b> [task-name ...]
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BOUT_NAME="$1"; MODEL_A="$2"; MODEL_B="$3"; shift 3
BOUT="$ROOT/bouts/$BOUT_NAME"
mkdir -p "$BOUT"

if [[ $# -gt 0 ]]; then
  TASKS=("$@")
else
  TASKS=()
  for d in "$ROOT"/tasks/*/; do TASKS+=("$(basename "$d")"); done
fi

echo "bout=$BOUT_NAME models=$MODEL_A,$MODEL_B tasks=${TASKS[*]}"
for t in "${TASKS[@]}"; do
  echo "=== $t ==="
  "$ROOT/bin/run-task.sh" "$ROOT/tasks/$t" "$MODEL_A" "$BOUT" &
  PA=$!
  "$ROOT/bin/run-task.sh" "$ROOT/tasks/$t" "$MODEL_B" "$BOUT" &
  PB=$!
  wait "$PA"; wait "$PB"
done

python3 "$ROOT/bin/summarize.py" "$BOUT"
echo "BOUT COMPLETE: $BOUT"
