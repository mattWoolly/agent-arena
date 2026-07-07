#!/usr/bin/env bash
# grade.sh <workspace> — delegate to grade.py; also verify sources untouched
set -u
WS=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
FAIL=0

if ! diff -rq -x __pycache__ -x '*.pyc' "$HERE/fixture/src" "$WS/src" > /dev/null 2>&1; then
  echo "FAIL: src/ was modified"
  FAIL=1
fi

python3 "$HERE/grade.py" "$WS" || FAIL=1
exit "$FAIL"
