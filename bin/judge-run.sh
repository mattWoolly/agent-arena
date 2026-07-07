#!/usr/bin/env bash
# Rubric-judge one run's deliverables on depth qualities the deterministic
# graders don't price. Separate from pass/fail — judge scores never gate a run.
#
# usage: judge-run.sh <task-dir> <run-out-dir> [judge-model] [n-samples]
#
# Reads <task-dir>/rubric.md (first line: `FILES: <deliverable> [...]`; rest is
# the rubric). Judges the deliverables from <run-out-dir>/workspace/ blind —
# the judge sees rubric + content only, never model names or paths. Samples the
# judge N times (default 3) and writes <run-out-dir>/judge.json with all
# samples plus the per-dimension median.
set -u

TASK_DIR=$(cd "$1" && pwd)
OUT_DIR=$(cd "$2" && pwd)
JUDGE_MODEL="${3:-claude-opus-4-8}"
N="${4:-3}"

RUBRIC="$TASK_DIR/rubric.md"
[[ -f "$RUBRIC" ]] || { echo "no rubric.md in $TASK_DIR" >&2; exit 1; }

FILES=$(head -1 "$RUBRIC" | sed -n 's/^FILES: *//p')
[[ -n "$FILES" ]] || { echo "rubric.md must start with 'FILES: <name> ...'" >&2; exit 1; }
RUBRIC_BODY=$(tail -n +2 "$RUBRIC")

CONTENT=""
for f in $FILES; do
  p="$OUT_DIR/workspace/$f"
  [[ -f "$p" ]] || { echo "deliverable missing: $p" >&2; exit 1; }
  CONTENT+="--- $f ---
$(cat "$p")
"
done

PROMPT="You are grading an anonymous submission against a rubric. You do not
know what produced it. Score each rubric dimension 0, 1, or 2, exactly as the
rubric defines, with a one-sentence rationale quoting or citing the submission.

Respond with ONLY a JSON object, no code fences, of the form:
{\"scores\": {\"<dimension>\": {\"score\": <0|1|2>, \"why\": \"<one sentence>\"}}}

RUBRIC:
$RUBRIC_BODY

SUBMISSION:
$CONTENT"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

for ((i = 1; i <= N; i++)); do
  for attempt in 1 2; do
    RAW=$(cd "$TMP" && claude -p "$PROMPT" \
      --model "$JUDGE_MODEL" \
      --effort high \
      --setting-sources project \
      --max-turns 1 \
      --output-format json 2>/dev/null | jq -r '.result // empty')
    CLEAN=$(printf '%s' "$RAW" | sed -e 's/^```json//' -e 's/^```//' -e 's/```$//')
    if printf '%s' "$CLEAN" | jq -e '.scores' > /dev/null 2>&1; then
      printf '%s' "$CLEAN" | jq -c '.scores' > "$TMP/sample-$i.json"
      break
    fi
    [[ "$attempt" -eq 2 ]] && { echo "judge sample $i unparseable after retry" >&2; exit 1; }
  done
done

python3 - "$TMP" "$JUDGE_MODEL" "$N" > "$OUT_DIR/judge.json" <<'EOF'
import json, statistics, sys
from pathlib import Path

tmp, model, n = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
samples = [json.loads((tmp / f"sample-{i}.json").read_text()) for i in range(1, n + 1)]
dims = sorted(samples[0].keys())
median = {d: statistics.median(s[d]["score"] for s in samples) for d in dims}
json.dump({"judge_model": model, "n_samples": n, "median": median,
           "samples": samples}, sys.stdout, indent=2)
print()
EOF

echo "judged $(basename "$OUT_DIR"): $(jq -c '.median' "$OUT_DIR/judge.json")"
