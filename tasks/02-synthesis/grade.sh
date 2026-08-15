#!/usr/bin/env bash
# grade.sh <workspace> — score = hidden test functions passed (6 total, 5 problems + perf)
set -u
WS=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=../_lib/arena_pytest.sh
. "$HERE/../_lib/arena_pytest.sh"

OUT=$(arena_pytest "$WS" "$HERE/hidden_tests/test_hidden.py" -vv 2>&1)

echo "$OUT" | grep -E "PASSED|FAILED|ERROR" | sed 's/^.*::/  /'
PASSED=$(echo "$OUT" | grep -c "PASSED")
TOTAL=6
echo "SCORE: $PASSED/$TOTAL"
[[ "$PASSED" -eq "$TOTAL" ]] && exit 0 || exit 1
