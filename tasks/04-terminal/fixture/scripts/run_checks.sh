#!/bin/bash
set -e
python3 tools/validate_config.py data/config.json
echo "all checks passed"
