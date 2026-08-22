#!/usr/bin/env bash
# Prompt variant: use the parent task's hidden grader unchanged.
exec bash "$(cd "$(dirname "$0")/../16-source-audit" && pwd)/grade.sh" "$@"
