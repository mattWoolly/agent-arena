#!/usr/bin/env bash
# variant task: same grader as the parent task
exec bash "$(cd "$(dirname "$0")/../05-review" && pwd)/grade.sh" "$@"
