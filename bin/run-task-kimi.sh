#!/usr/bin/env bash
# Run ONE model on ONE task, driven by Kimi Code (Moonshot's CLI).
# usage: run-task-kimi.sh <task-dir> <model-alias> <bout-dir> [run-index]
#
# Cross-driver counterpart of run-task.sh / run-task-codex.sh: same fixture
# seeding, throwaway workspace outside the repo, same hidden graders,
# byte-identical PROMPT.md. Cells are labeled "<alias>-kimicode". Kimi Code
# runs in a fresh HOME copied from an exact external config-only source.
# PYTHONUSERBASE remains pinned to the real user's package directory. Prompt
# mode auto-approves; per-turn usage comes from the emitted session wire log.
set -u

TASK_DIR=$(cd "$1" && pwd)
ALIAS="$2"            # e.g. arena/k3
BOUT_DIR=$(mkdir -p "$3" && cd "$3" && pwd)
RUN_IDX="${4:-}"
TASK_NAME=$(basename "$TASK_DIR")
ROOT=$(cd "$(dirname "$0")/.." && pwd)
LABEL_MODEL="${ARENA_KIMI_LABEL:-kimi-k3-kimicode}"   # per-arm cells (e.g. effort ladder) override this
EFFORT_NOTE="${ARENA_KIMI_EFFORT:-max (kimi-code default for k3)}"
KIMI_BIN="$HOME/.kimi-code/bin/kimi"
SOURCE_ARENA_HOME="${ARENA_KIMI_HOME:-$HOME/.kimi-arena}"
USER_SITE_BASE="$HOME/.local"
OUT_DIR="$BOUT_DIR/$TASK_NAME/$LABEL_MODEL"
[[ -n "$RUN_IDX" ]] && OUT_DIR="$OUT_DIR/run-$RUN_IDX"
mkdir -p "$(dirname "$OUT_DIR")"
if ! mkdir "$OUT_DIR"; then
  echo "refusing to overwrite existing run artifact directory: $OUT_DIR" >&2
  exit 2
fi
LABEL="$TASK_NAME/$LABEL_MODEL${RUN_IDX:+ run-$RUN_IDX}"

case "$SOURCE_ARENA_HOME" in
  "$ROOT"/*|"$ROOT")
    echo "refusing to run: isolated Kimi home is inside the repository" > "$OUT_DIR/stderr.log"
    echo "refusing in-repository Kimi home" >&2
    exit 1;;
esac
if [[ ! -f "$SOURCE_ARENA_HOME/.kimi-code/config.toml" ]]; then
  echo "isolated Kimi config.toml is missing" > "$OUT_DIR/stderr.log"
  echo "missing isolated Kimi configuration" >&2
  exit 1
fi

RUN_AUTH_HOME=""
ARENA_HOME="$SOURCE_ARENA_HOME"
TARGET_ENV=(env HOME="$ARENA_HOME" PYTHONUSERBASE="$USER_SITE_BASE")
SKILLS_ARGS=()
MODEL_ENV_REC="none (isolated HOME=$ARENA_HOME, outside repo; PYTHONUSERBASE=$USER_SITE_BASE)"
SETTING_SOURCES_REC="arena config.toml only"
if [[ "${ARENA_PLAN_PROBE:-0}" == "1" ]]; then
  RUN_AUTH_HOME=$(mktemp -d "${TMPDIR:-/tmp}/arena-kimi-home.XXXXXX")
  chmod 700 "$RUN_AUTH_HOME"
  mkdir -p "$RUN_AUTH_HOME/.kimi-code" "$RUN_AUTH_HOME/empty-skills"
  cp "$SOURCE_ARENA_HOME/.kimi-code/config.toml" "$RUN_AUTH_HOME/.kimi-code/config.toml"
  chmod 600 "$RUN_AUTH_HOME/.kimi-code/config.toml"
  ARENA_HOME="$RUN_AUTH_HOME"
  TARGET_ENV=(env -u ARENA_KIMI_HOME -u KIMI_API_KEY HOME="$ARENA_HOME" PYTHONUSERBASE="$USER_SITE_BASE")
  SKILLS_ARGS=(--skills-dir "$ARENA_HOME/empty-skills")
  MODEL_ENV_REC="none (fresh config-only HOME; isolated PYTHONUSERBASE)"
  SETTING_SOURCES_REC="arena config.toml plus explicit empty skills directory"
fi

WS=$(mktemp -d "${TMPDIR:-/tmp}/arena-ws.XXXXXX")
trap 'rm -rf "$WS" ${RUN_AUTH_HOME:+"$RUN_AUTH_HOME"}' EXIT
cp -a "$TASK_DIR/fixture/." "$WS/"
if [[ -f "$TASK_DIR/setup.sh" ]]; then
  (cd "$WS" && bash "$TASK_DIR/setup.sh")
fi
git -C "$WS" init -q
git -C "$WS" add -A
git -C "$WS" -c user.email=arena@local -c user.name=arena \
  -c commit.gpgsign=false commit -qm baseline

PROMPT=$(cat "$TASK_DIR/PROMPT.md"; printf '\034')
PROMPT=${PROMPT%$'\034'}
TIMEOUT_S="${ARENA_TIMEOUT_S:-1500}"

# Preserve the exact bytes passed as the positional prompt.
printf '%s' "$PROMPT" > "$OUT_DIR/prompt.txt"
PROMPT_SHA=$(sha256sum "$OUT_DIR/prompt.txt" | awk '{print $1}')
PRICE_SHA=$(sha256sum "$ROOT/env/prices.json" | awk '{print $1}')
HARNESS_COMMIT=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)
HARNESS_DIRTY=false
git -C "$ROOT" diff --quiet && git -C "$ROOT" diff --cached --quiet || HARNESS_DIRTY=true

CLI_VERSION="kimi-code $($KIMI_BIN -V 2>/dev/null | head -1)"
cat > "$OUT_DIR/run_env.json" <<EOF
{
  "cli_version": "$CLI_VERSION",
  "driver": "kimi -p --output-format stream-json (prompt mode auto-approves)",
  "harness_commit": "$HARNESS_COMMIT",
  "harness_tracked_dirty": $HARNESS_DIRTY,
  "prompt_sha256": "$PROMPT_SHA",
  "price_sheet_sha256": "$PRICE_SHA",
  "base_url": "https://api.moonshot.ai/v1 (platform, metered)",
  "proxy_upstream": "none",
  "model_env": "$MODEL_ENV_REC",
  "model_alias": "$ALIAS",
  "effort": "$EFFORT_NOTE",
  "setting_sources": "$SETTING_SOURCES_REC",
  "timeout_s": $TIMEOUT_S,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "[$LABEL] starting"
START=$(date +%s.%N)
date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT_DIR/target_started"
(
  cd "$WS" && "${TARGET_ENV[@]}" \
    timeout "$TIMEOUT_S" "$KIMI_BIN" \
    -p "$PROMPT" \
    -m "$ALIAS" \
    "${SKILLS_ARGS[@]}" \
    --output-format stream-json \
    < /dev/null \
    > "$OUT_DIR/transcript.jsonl" 2> "$OUT_DIR/stderr.log"
)
AGENT_EXIT=$?
date -u +%Y-%m-%dT%H:%M:%SZ > "$OUT_DIR/target_returned"
END=$(date +%s.%N)
echo "$AGENT_EXIT" > "$OUT_DIR/agent_exit"
python3 -c "print(f'{$END - $START:.1f}')" > "$OUT_DIR/wall_seconds"

# This run's exact session journal, associated by the session id emitted by
# Kimi rather than a race-prone timestamp search.
SESSION_ID=$(jq -r 'select(.type == "session.resume_hint") | .session_id' \
  "$OUT_DIR/transcript.jsonl" 2>/dev/null | tail -1)
if [[ -n "$SESSION_ID" && "$SESSION_ID" != "null" ]]; then
  WIRE=$(find "$ARENA_HOME/.kimi-code/sessions" -type f \
    -path "*/$SESSION_ID/agents/main/wire.jsonl" -print -quit 2>/dev/null)
  [[ -n "$WIRE" ]] && cp "$WIRE" "$OUT_DIR/wire.jsonl"
fi

# Peek check, same contract as the other drivers.
PEEK=$(grep -o -e "$ROOT" -e "grade\.sh" -e "hidden_tests" -e "check-grader" \
  "$OUT_DIR/transcript.jsonl" | sort -u | tr '\n' ' ')
if [[ -n "$PEEK" ]]; then
  echo "suspect: $PEEK" > "$OUT_DIR/peek_check"
  echo "[$LABEL] WARNING: transcript references grader assets: $PEEK" >&2
else
  echo "clean" > "$OUT_DIR/peek_check"
fi

# Ordinary bouts retain the established config-key leakscan. The planning
# probe uses the wrapper's exact TOML parser, whole-artifact rescans, and
# mandatory external quarantine instead.
if [[ "${ARENA_PLAN_PROBE:-0}" != "1" ]]; then
  LEAKSCAN="$ROOT/env/$LABEL_MODEL.leakscan"
  [[ -f "$LEAKSCAN" ]] || LEAKSCAN="$ROOT/env/kimi-k3-kimicode.leakscan"
  if [[ -f "$LEAKSCAN" ]]; then
    while IFS= read -r _sec; do
      [[ -z "$_sec" ]] && continue
      if grep -qF "$_sec" "$OUT_DIR/transcript.jsonl" "$OUT_DIR/wire.jsonl" 2>/dev/null || \
         grep -rqF "$_sec" "$WS" 2>/dev/null; then
        echo "SECRET LEAK: leakscan value appears in published artifacts" >> "$OUT_DIR/peek_check"
        echo "[$LABEL] WARNING: SECRET LEAKED into published artifacts; do not publish this run" >&2
      fi
    done < <(bash "$LEAKSCAN" 2>/dev/null)
  fi
fi

if ! git -C "$WS" add -A; then
  echo "workspace capture failed" >> "$OUT_DIR/stderr.log"
  exit 3
fi
git -C "$WS" diff --cached > "$OUT_DIR/workspace.diff"
git -C "$WS" diff --cached --stat > "$OUT_DIR/workspace.diffstat"

if [[ -f "$TASK_DIR/grade.sh" ]]; then
  bash "$TASK_DIR/grade.sh" "$WS" > "$OUT_DIR/grade.txt" 2>&1
  echo "$?" > "$OUT_DIR/grade_exit"
fi

rm -rf "$OUT_DIR/workspace"
mkdir -p "$OUT_DIR/workspace"
cp -a "$WS/." "$OUT_DIR/workspace/"
rm -rf "$OUT_DIR/workspace/.git"

python3 "$ROOT/bin/metrics_kimi.py" "$OUT_DIR" "$LABEL_MODEL" "${ARENA_KIMI_PRICE_KEY:-kimi-k3}" > "$OUT_DIR/metrics.json" 2>> "$OUT_DIR/stderr.log"

echo "[$LABEL] done: agent_exit=$AGENT_EXIT grade_exit=$(cat "$OUT_DIR/grade_exit" 2>/dev/null || echo n/a) wall=$(cat "$OUT_DIR/wall_seconds")s"
