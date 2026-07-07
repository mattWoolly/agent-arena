#!/usr/bin/env bash
# Plant the environment damage in the freshly seeded workspace:
# CRLF line endings on the check script, and a stripped exec bit.
set -e
sed -i 's/$/\r/' scripts/run_checks.sh
chmod -x scripts/run_checks.sh
