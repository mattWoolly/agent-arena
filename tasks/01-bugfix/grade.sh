#!/usr/bin/env bash
# grade.sh <workspace>  — exit 0 iff visible + hidden tests pass and tests/ untouched
set -u
WS=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
FAIL=0
POINTS=0

if diff -rq -x __pycache__ -x '*.pyc' "$HERE/fixture/tests" "$WS/tests" > /dev/null 2>&1; then
  POINTS=$((POINTS + 1))
else
  echo "FAIL: tests/ was modified"
  FAIL=1
fi

if (cd "$WS" && python3 -m pytest -q tests/ > /dev/null 2>&1); then
  echo "visible tests: pass"
  POINTS=$((POINTS + 1))
else
  echo "FAIL: visible tests failing"
  FAIL=1
fi

cp "$HERE/hidden_tests/test_hidden.py" "$WS/_arena_test_hidden.py"
if (cd "$WS" && python3 -m pytest -q _arena_test_hidden.py > /dev/null 2>&1); then
  echo "hidden tests: pass"
  POINTS=$((POINTS + 1))
else
  echo "FAIL: hidden tests failing"
  FAIL=1
fi
rm -f "$WS/_arena_test_hidden.py"

[[ -s "$WS/SOLUTION.md" ]] && echo "SOLUTION.md: present" || echo "note: SOLUTION.md missing/empty"

echo "SCORE: $POINTS/3"
exit "$FAIL"
