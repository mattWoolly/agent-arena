#!/usr/bin/env bash
# grade.sh <workspace> — exit 0 iff tests/ untouched and the suite passes.
# This task's suite lives in the fixture (the agent iterates against it); the
# grader just confirms the final state converged.
set -u
WS=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../_lib/arena_pytest.sh
. "$HERE/../_lib/arena_pytest.sh"
FAIL=0; POINTS=0

if diff -rq -x __pycache__ -x '*.pyc' "$HERE/fixture/tests" "$WS/tests" > /dev/null 2>&1; then
  POINTS=$((POINTS + 1))
else
  echo "FAIL: tests/ was modified"; FAIL=1
fi

if arena_pytest "$WS" "$HERE/fixture/tests" > /dev/null 2>&1; then
  echo "suite: pass (converged)"; POINTS=$((POINTS + 1))
else
  echo "FAIL: suite not passing"; FAIL=1
fi

[[ -s "$WS/SOLUTION.md" ]] && echo "SOLUTION.md: present" || echo "note: SOLUTION.md missing"
echo "SCORE: $POINTS/2"
exit "$FAIL"
