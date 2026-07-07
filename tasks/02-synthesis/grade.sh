#!/usr/bin/env bash
# grade.sh <workspace> — score = hidden test functions passed (6 total, 5 problems + perf)
set -u
WS=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)

cp "$HERE/hidden_tests/test_hidden.py" "$WS/_arena_test_hidden.py"
OUT=$(cd "$WS" && python3 -m pytest -v _arena_test_hidden.py 2>&1)
rm -f "$WS/_arena_test_hidden.py"

echo "$OUT" | grep -E "PASSED|FAILED|ERROR" | sed 's/^.*::/  /'
PASSED=$(echo "$OUT" | grep -c "PASSED")
TOTAL=6
echo "SCORE: $PASSED/$TOTAL"
[[ "$PASSED" -eq "$TOTAL" ]] && exit 0 || exit 1
