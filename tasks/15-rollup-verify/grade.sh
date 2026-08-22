#!/usr/bin/env bash
# Prompt variant: use the parent task's hidden grader unchanged.
exec bash "$(cd "$(dirname "$0")/../15-rollup" && pwd)/grade.sh" "$@"
