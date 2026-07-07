#!/usr/bin/env bash
# Run a bout: every task (or a subset) for one or more models.
#
# usage: run-bout.sh [-r N] [-s] <bout-name> <model> [<model> ...] [task ...]
#   -r N   repeat each (task, model) cell N times; N>1 stores runs in run-K/ subdirs
#   -s     serial mode: one run at a time (no shared rate-limit headroom between
#          models; model order rotates each repeat so nobody always goes first)
#
# Any argument after the bout name that names a directory under tasks/ selects
# that task; every other argument is treated as a model ID. The classic
# two-model call `run-bout.sh <name> <model-a> <model-b>` works unchanged.
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)

REPEATS=1
SERIAL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -r) REPEATS="$2"; shift 2 ;;
    -s) SERIAL=1; shift ;;
    -*) echo "unknown flag: $1" >&2; exit 1 ;;
    *) break ;;
  esac
done

if [[ $# -lt 2 ]]; then
  echo "usage: run-bout.sh [-r N] [-s] <bout-name> <model> [<model> ...] [task ...]" >&2
  exit 1
fi

BOUT_NAME="$1"; shift
BOUT="$ROOT/bouts/$BOUT_NAME"
mkdir -p "$BOUT"

MODELS=()
TASKS=()
for arg in "$@"; do
  if [[ -d "$ROOT/tasks/$arg" ]]; then TASKS+=("$arg"); else MODELS+=("$arg"); fi
done
if [[ ${#MODELS[@]} -lt 1 ]]; then
  echo "need at least one model" >&2
  exit 1
fi
if [[ ${#TASKS[@]} -eq 0 ]]; then
  for d in "$ROOT"/tasks/*/; do TASKS+=("$(basename "$d")"); done
fi

echo "bout=$BOUT_NAME models=${MODELS[*]} tasks=${TASKS[*]} repeats=$REPEATS serial=$SERIAL"

for t in "${TASKS[@]}"; do
  for ((k = 1; k <= REPEATS; k++)); do
    IDX=""
    [[ "$REPEATS" -gt 1 ]] && IDX="$k"
    echo "=== $t (run $k/$REPEATS) ==="
    if [[ "$SERIAL" -eq 1 ]]; then
      n=${#MODELS[@]}
      for ((i = 0; i < n; i++)); do
        m="${MODELS[$(((i + k - 1) % n))]}"
        "$ROOT/bin/run-task.sh" "$ROOT/tasks/$t" "$m" "$BOUT" $IDX
      done
    else
      PIDS=()
      for m in "${MODELS[@]}"; do
        "$ROOT/bin/run-task.sh" "$ROOT/tasks/$t" "$m" "$BOUT" $IDX &
        PIDS+=($!)
      done
      for p in "${PIDS[@]}"; do wait "$p"; done
    fi
  done
done

python3 "$ROOT/bin/summarize.py" "$BOUT"
echo "BOUT COMPLETE: $BOUT"
