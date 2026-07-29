#!/usr/bin/env bash
# Direct-API probes for the 2026-07-29-minimax-m3 bout, run BEFORE the grid.
# Establishes (1) how the /anthropic endpoint treats the thinking parameter
# and (2) what the models endpoint advertises for context. Outputs land next
# to this script as probe-*.json; the key never appears in outputs.
set -eu
cd "$(dirname "$0")"
. "$HOME/.secrets"
H=(-H "Content-Type: application/json" -H "Authorization: Bearer $MINIMAX_API_KEY" -H "anthropic-version: 2023-06-01")
BASE=https://api.minimax.io/anthropic
Q='{"role":"user","content":"What is 847*263? Work it out carefully."}'

curl -sS -m 90 "$BASE/v1/messages" "${H[@]}" \
  -d "{\"model\":\"MiniMax-M3\",\"max_tokens\":2048,\"messages\":[$Q]}" \
  > probe-default.json
curl -sS -m 90 "$BASE/v1/messages" "${H[@]}" \
  -d "{\"model\":\"MiniMax-M3\",\"max_tokens\":2048,\"thinking\":{\"type\":\"disabled\"},\"messages\":[$Q]}" \
  > probe-disabled.json
curl -sS -m 90 "$BASE/v1/messages" "${H[@]}" \
  -d "{\"model\":\"MiniMax-M3\",\"max_tokens\":2048,\"thinking\":{\"type\":\"enabled\",\"budget_tokens\":1024},\"messages\":[$Q]}" \
  > probe-enabled-budget.json
# Context advertisement (H8): what the endpoint says about the model, and
# whether the [1m] id variant is a distinct advertised model.
curl -sS -m 30 "$BASE/v1/models" "${H[@]}" > probe-models.json || true

for f in probe-*.json; do
  python3 - "$f" <<'EOF'
import json, sys
p = sys.argv[1]
try:
    r = json.load(open(p))
except Exception as e:
    print(f"{p}: unparseable ({e})"); sys.exit()
if "content" in r:
    print(p, "blocks:", [b.get("type") for b in r.get("content", [])], "usage:", r.get("usage"))
else:
    print(p, "keys:", list(r)[:6])
EOF
done
