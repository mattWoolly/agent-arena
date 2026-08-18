#!/usr/bin/env bash
# Model-routing probe for Z.ai's Anthropic-compatible endpoint.
#
# Established 2026-08-15, shortly after GLM-5.3 shipped: requesting an older
# GLM-5.x version returns GLM-5.3, silently. Nothing errors; the only signal is
# the `model` field on the response. This script records that so the claim is
# reproducible and dated, because vendor routing can change without notice.
#
# Reads the key from env/glm-5.2.env (gitignored). Never echoes it.
# Writes routing.txt next to this script.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)

# shellcheck disable=SC1090
set -a; . "$ROOT/env/glm-5.2.env"; set +a

ask() {
  curl -s -X POST "$ANTHROPIC_BASE_URL/v1/messages" \
    -H "x-api-key: $ANTHROPIC_AUTH_TOKEN" \
    -H "anthropic-version: 2023-06-01" \
    -H "content-type: application/json" --max-time 60 \
    -d "{\"model\":\"$1\",\"max_tokens\":8,\"thinking\":{\"type\":\"enabled\"},\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}"
}

served() {
  python3 -c "
import sys, json
d = json.load(sys.stdin)
if 'model' in d:
    print(d['model'])
else:
    e = d.get('error', {})
    print('ERROR %s: %s' % (e.get('code'), str(e.get('message'))[:70]))
"
}

{
  echo "# Z.ai Anthropic-compatible endpoint model routing"
  echo "# probed: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# base_url: $ANTHROPIC_BASE_URL"
  echo "# account: GLM Coding Plan attached"
  echo
  echo "## requested -> served"
  for M in glm-5.3 glm-5.2 glm-5.1 glm-5 glm-4.7 glm-4.5-air \
           claude-opus-4-8 claude-sonnet-4-6 not-a-real-model-xyz; do
    printf '%-24s -> %s\n' "$M" "$(ask "$M" | served)"
  done

  echo
  echo "## stability: 5 repeats requesting glm-5.2"
  for _ in 1 2 3 4 5; do
    printf 'glm-5.2 -> %s\n' "$(ask glm-5.2 | served)"
  done

  echo
  echo "## glm-5.3 request-shape validation"
  echo "## NOTE: with no active plan on the key (~04:39Z today) the shapes"
  echo "## without a thinking block returned 400/1210. With the coding plan"
  echo "## attached they all succeed. The 1210 was account state, not a"
  echo "## request-shape rule -- recorded here so the retraction is dated."
  shape() {
    local label="$1" body="$2"
    local out
    out=$(curl -s -X POST "$ANTHROPIC_BASE_URL/v1/messages" \
      -H "x-api-key: $ANTHROPIC_AUTH_TOKEN" -H "anthropic-version: 2023-06-01" \
      -H "content-type: application/json" --max-time 60 -d "$body")
    printf '%-34s -> %s\n' "$label" "$(echo "$out" | served)"
  }
  shape 'no thinking field'      '{"model":"glm-5.3","max_tokens":8,"messages":[{"role":"user","content":"hi"}]}'
  shape 'thinking.disabled'      '{"model":"glm-5.3","max_tokens":8,"thinking":{"type":"disabled"},"messages":[{"role":"user","content":"hi"}]}'
  shape 'thinking.enabled'       '{"model":"glm-5.3","max_tokens":8,"thinking":{"type":"enabled"},"messages":[{"role":"user","content":"hi"}]}'
  shape 'thinking.adaptive'      '{"model":"glm-5.3","max_tokens":8,"thinking":{"type":"adaptive"},"messages":[{"role":"user","content":"hi"}]}'
  shape 'output_config.effort=high' '{"model":"glm-5.3","max_tokens":8,"output_config":{"effort":"high"},"messages":[{"role":"user","content":"hi"}]}'
  shape 'output_config.effort=max'  '{"model":"glm-5.3","max_tokens":8,"output_config":{"effort":"max"},"messages":[{"role":"user","content":"hi"}]}'
} | tee "$HERE/routing.txt"
