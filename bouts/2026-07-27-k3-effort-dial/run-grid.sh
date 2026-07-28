#!/usr/bin/env bash
# Effort-ladder grid for the 2026-07-27 K3 bout: 3 efforts x 6 base tasks
# x r=3, fully serial (execution time is a claim). Arm order rotates per
# run index so no effort systematically inherits a warm or cold window.
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BOUT="$ROOT/bouts/2026-07-27-k3-effort-dial"
TASKS=(01-bugfix 02-synthesis 03-refactor 04-terminal 05-review 06-instructions)
EFFORTS=(low high max)

for TASK in "${TASKS[@]}"; do
  for RUN in 1 2 3; do
    for i in 0 1 2; do
      EFF="${EFFORTS[$(( (i + RUN - 1) % 3 ))]}"
      ARENA_KIMI_LABEL="kimi-k3-${EFF}-kimicode" \
      ARENA_KIMI_EFFORT="$EFF" \
        bash "$ROOT/bin/run-task-kimi.sh" "$ROOT/tasks/$TASK" "arena/k3-$EFF" "$BOUT" "$RUN"
    done
  done
done
echo "GRID COMPLETE $(date -u +%FT%TZ)"
