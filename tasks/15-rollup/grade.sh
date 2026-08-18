#!/usr/bin/env bash
# grade.sh <workspace> — thin wrapper; the logic lives in grade.py (this dir).
set -u
WS=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
python3 "$HERE/grade.py" "$WS"
