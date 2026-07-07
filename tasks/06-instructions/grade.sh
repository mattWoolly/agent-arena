#!/usr/bin/env bash
# grade.sh <workspace> — delegate to grade.py; CSV must be untouched
set -u
WS=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
FAIL=0

if ! diff -q "$HERE/fixture/data/sales.csv" "$WS/data/sales.csv" > /dev/null 2>&1; then
  echo "FAIL: sales.csv was modified"
  FAIL=1
fi

python3 "$HERE/grade.py" "$WS" || FAIL=1
exit "$FAIL"
