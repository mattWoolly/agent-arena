#!/usr/bin/env bash
# grade.sh <workspace> — visible tests unmodified+passing, dataclass reqs, no subscripting
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
  echo "hidden tests (Config dataclass contract): pass"
  POINTS=$((POINTS + 1))
else
  echo "FAIL: hidden tests failing"
  FAIL=1
fi
rm -f "$WS/_arena_test_hidden.py"

if grep -rnE '(cfg|config)\[' "$WS/reportgen/" > /dev/null 2>&1; then
  echo "FAIL: config subscripting still present:"
  grep -rnE '(cfg|config)\[' "$WS/reportgen/"
  FAIL=1
else
  echo "no config subscripting: pass"
  POINTS=$((POINTS + 1))
fi

echo "SCORE: $POINTS/4"
exit "$FAIL"
