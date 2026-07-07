#!/usr/bin/env bash
# Self-test every grader: it must FAIL the raw fixture and PASS a reference solution.
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
RESULT=0

seed() { # seed <task> <dest>
  local task="$1" dest="$2"
  mkdir -p "$dest"
  cp -a "$ROOT/tasks/$task/fixture/." "$dest/"
  if [[ -f "$ROOT/tasks/$task/setup.sh" ]]; then (cd "$dest" && bash "$ROOT/tasks/$task/setup.sh"); fi
}

expect() { # expect <pass|fail> <task> <workspace> <label>
  local want="$1" task="$2" ws="$3" label="$4"
  bash "$ROOT/tasks/$task/grade.sh" "$ws" > "$TMP/grade-out.txt" 2>&1
  local got_exit=$?
  local got="fail"; [[ $got_exit -eq 0 ]] && got="pass"
  if [[ "$got" == "$want" ]]; then
    echo "ok   $task $label -> $got ($(grep '^SCORE:' "$TMP/grade-out.txt" || true))"
  else
    echo "BAD  $task $label -> $got, wanted $want"
    sed 's/^/     /' "$TMP/grade-out.txt"
    RESULT=1
  fi
}

# --- 01-bugfix ---
seed 01-bugfix "$TMP/01-raw"
expect fail 01-bugfix "$TMP/01-raw" "raw fixture"
seed 01-bugfix "$TMP/01-sol"
cp "$ROOT/tasks/01-bugfix/solution/cache.py" "$TMP/01-sol/lrucache/cache.py"
echo "fixed recency + update-eviction bugs" > "$TMP/01-sol/SOLUTION.md"
expect pass 01-bugfix "$TMP/01-sol" "reference solution"

# --- 02-synthesis ---
seed 02-synthesis "$TMP/02-raw"
expect fail 02-synthesis "$TMP/02-raw" "raw fixture"
seed 02-synthesis "$TMP/02-sol"
cp "$ROOT/tasks/02-synthesis/solution/problems.py" "$TMP/02-sol/problems.py"
expect pass 02-synthesis "$TMP/02-sol" "reference solution"

# --- 03-refactor ---
seed 03-refactor "$TMP/03-raw"
expect fail 03-refactor "$TMP/03-raw" "raw fixture"
seed 03-refactor "$TMP/03-sol"
for f in config.py loader.py formatter.py; do
  cp "$ROOT/tasks/03-refactor/solution/$f" "$TMP/03-sol/reportgen/$f"
done
expect pass 03-refactor "$TMP/03-sol" "reference solution"

# --- 04-terminal ---
seed 04-terminal "$TMP/04-raw"
expect fail 04-terminal "$TMP/04-raw" "raw fixture"
seed 04-terminal "$TMP/04-sol"
(
  cd "$TMP/04-sol"
  sed -i 's/^    python3 -m pytest/\tpython3 -m pytest/' Makefile
  sed -i 's/\r$//' scripts/run_checks.sh
  chmod +x scripts/run_checks.sh
  python3 - <<'EOF'
import re
src = open("data/config.json").read()
open("data/config.json", "w").write(re.sub(r",(\s*})", r"\1", src))
EOF
  echo "fixed: Makefile spaces->tab, CRLF, exec bit, JSON trailing comma" > SOLUTION.md
)
expect pass 04-terminal "$TMP/04-sol" "reference solution"

# --- 05-review ---
seed 05-review "$TMP/05-raw"
expect fail 05-review "$TMP/05-raw" "raw fixture"
seed 05-review "$TMP/05-sol"
cp "$ROOT/tasks/05-review/solution/findings.md" "$TMP/05-sol/findings.md"
expect pass 05-review "$TMP/05-sol" "reference solution"

# --- 06-instructions ---
seed 06-instructions "$TMP/06-raw"
expect fail 06-instructions "$TMP/06-raw" "raw fixture"
seed 06-instructions "$TMP/06-sol"
python3 "$ROOT/tasks/06-instructions/make-solution.py" "$TMP/06-sol"
expect pass 06-instructions "$TMP/06-sol" "reference solution"

exit "$RESULT"
