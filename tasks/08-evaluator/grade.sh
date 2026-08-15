#!/usr/bin/env bash
# grade.sh <workspace> — exit 0 iff tests/ untouched and visible + hidden pass.
# Hidden tests carry the discriminating edge cases (associativity, unary minus,
# forward refs, three cycle shapes, real division, deep chains).
set -u
WS=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../_lib/arena_pytest.sh
. "$HERE/../_lib/arena_pytest.sh"
FAIL=0
POINTS=0

if diff -rq -x __pycache__ -x '*.pyc' "$HERE/fixture/tests" "$WS/tests" > /dev/null 2>&1; then
  POINTS=$((POINTS + 1))
else
  echo "FAIL: tests/ was modified"; FAIL=1
fi

if arena_pytest "$WS" "$HERE/fixture/tests" > /dev/null 2>&1; then
  echo "visible tests: pass"; POINTS=$((POINTS + 1))
else
  echo "FAIL: visible tests failing"; FAIL=1
fi

if arena_pytest "$WS" "$HERE/hidden_tests/test_hidden.py" > /tmp/arena_hid_$$.txt 2>&1; then
  echo "hidden tests: all pass"; POINTS=$((POINTS + 1))
else
  echo "FAIL: hidden tests ($(tail -1 /tmp/arena_hid_$$.txt))"; FAIL=1
fi
rm -f /tmp/arena_hid_$$.txt

[[ -s "$WS/SOLUTION.md" ]] && echo "SOLUTION.md: present" || echo "note: SOLUTION.md missing"

echo "SCORE: $POINTS/3"
exit "$FAIL"
