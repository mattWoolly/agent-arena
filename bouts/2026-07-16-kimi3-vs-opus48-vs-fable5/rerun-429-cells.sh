#!/usr/bin/env bash
set -u
cd /home/mwoolly/projects/agent-arena
B=bouts/2026-07-16-kimi3-vs-opus48-vs-fable5
A=$B/_launch-day-429

# Probe: don't start 11 runs into a still-overloaded API.
set -a; . env/kimi-k3.env; set +a
code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 30 \
  "$ANTHROPIC_BASE_URL/v1/messages" \
  -H "x-api-key: $ANTHROPIC_AUTH_TOKEN" -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"kimi-k3","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}')
if [[ "$code" != 200 ]]; then echo "PROBE FAILED: http=$code — Moonshot still unhealthy, aborting"; exit 2; fi
echo "probe ok (200), starting reruns"

CELLS="04-terminal:1 05-review:3 05-review-transplant:1 05-review-transplant:2 05-review-transplant:3 06-instructions:1 06-instructions:2 06-instructions:3 06-instructions-transplant:1 06-instructions-transplant:2 06-instructions-transplant:3"
for c in $CELLS; do
  t=${c%:*}; k=${c#*:}
  mkdir -p "$A/$t/kimi-k3"
  # keep the FIRST archived copy; never clobber the launch-day record
  [[ -d "$A/$t/kimi-k3/run-$k" ]] || cp -a "$B/$t/kimi-k3/run-$k" "$A/$t/kimi-k3/run-$k"
  bin/run-task.sh "tasks/$t" kimi-k3 "$B" "$k"
  n=$(grep -c '"subtype":"api_retry"' "$B/$t/kimi-k3/run-$k/transcript.jsonl" || true)
  echo "RERUN $t run-$k: retries=$n grade_exit=$(cat "$B/$t/kimi-k3/run-$k/grade_exit" 2>/dev/null || echo n/a)"
done
python3 bin/summarize.py "$B"
echo RERUN-PASS COMPLETE
