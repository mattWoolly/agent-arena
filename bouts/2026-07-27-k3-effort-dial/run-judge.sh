#!/usr/bin/env bash
# Judge pass for the 2026-07-27 K3 effort-dial bout: Opus 4.8, blind,
# 3 samples, over the rubric tasks (05-review, 06-instructions) in all
# three effort arms. Run after the grid completes.
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BOUT="$ROOT/bouts/2026-07-27-k3-effort-dial"

for TASK in 05-review 06-instructions; do
  for EFF in low high max; do
    for RUN in 1 2 3; do
      DIR="$BOUT/$TASK/kimi-k3-${EFF}-kimicode/run-$RUN"
      if [[ -d "$DIR" && ! -f "$DIR/judge.json" ]]; then
        bash "$ROOT/bin/judge-run.sh" "$ROOT/tasks/$TASK" "$DIR" claude-opus-4-8 3
      fi
    done
  done
done
echo "JUDGE COMPLETE $(date -u +%FT%TZ)"
