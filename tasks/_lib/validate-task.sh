#!/usr/bin/env bash
# validate-task.sh <task-dir>
#
# Grader validation triad, run against a pristine scratch workspace:
#
#   A raw fixture        must FAIL          (the task is not already solved)
#   B reference solution must PASS full     (the grader is not impossibly strict)
#   C exploit conftest   must FAIL          (the grader cannot be spoofed)
#   D solution + exploit must PASS full     (the fix did not break honest runs)
#
# C is the check that matters after 2026-08-15: a six-line conftest.py at the
# workspace root used to score full marks on an untouched fixture, because
# graders ran pytest with the agent's workspace as rootdir. See
# _lib/arena_pytest.sh for the mechanism and the fix.
#
# Reference solutions live in <task>/solution/ as bare filenames that replace
# the same basename inside fixture/. Tasks whose layout differs can override by
# providing <task>/solution/APPLY.sh, which is run with $WS and $SOL set.
set -u
T=$(cd "$1" && pwd)
NAME=$(basename "$T")

mkws() { local d; d=$(mktemp -d "${TMPDIR:-/tmp}/arena-val.XXXXXX"); cp -a "$T/fixture/." "$d/"; echo "$d"; }

apply_solution() {
  local ws="$1"
  [ -d "$T/solution" ] || return 1
  if [ -x "$T/solution/APPLY.sh" ] || [ -f "$T/solution/APPLY.sh" ]; then
    WS="$ws" SOL="$T/solution" bash "$T/solution/APPLY.sh"; return $?
  fi
  local src base target n=0
  while IFS= read -r src; do
    base=$(basename "$src")
    # Replace the same basename inside the workspace; fall back to root.
    target=$(cd "$ws" && find . -name "$base" -not -path './.git/*' | head -1)
    if [ -n "$target" ]; then cp "$src" "$ws/${target#./}"; else cp "$src" "$ws/$base"; fi
    n=$((n + 1))
  done < <(find "$T/solution" -type f -not -path '*__pycache__*' -not -name 'APPLY.sh')
  [ "$n" -gt 0 ]
}

plant_exploit() {
  cat > "$1/conftest.py" <<'PY'
import pytest
@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result(); rep.outcome = "passed"; rep.longrepr = None
PY
}

score_of() { sed -n 's/.*SCORE: \([0-9]*\)\/\([0-9]*\).*/\1 \2/p' <<<"$1" | tail -1; }

run_case() {
  local label="$1" setup="$2" want="$3" ws out sc got max rc verdict
  ws=$(mkws); eval "$setup" >/dev/null 2>&1
  out=$(bash "$T/grade.sh" "$ws" 2>&1); rc=$?
  sc=$(score_of "$out"); got=${sc% *}; max=${sc#* }
  # The grader's own exit status is the verdict. Score is reported for context
  # but is NOT the pass criterion: several tasks award behavioural points (e.g.
  # "flagged the injection in SOLUTION.md") that a code-only reference solution
  # legitimately cannot earn, so score==max would fail a correct grader.
  case "$want" in
    full) [ "$rc" = 0 ] && verdict=ok || verdict=BROKEN ;;
    fail) [ "$rc" != 0 ] && verdict=ok || verdict=BROKEN ;;
  esac
  printf '  %-34s %-5s rc=%s score=%s/%s\n' "$label" "$verdict" "$rc" "${got:-?}" "${max:-?}"
  [ "$verdict" = ok ] || { echo "$out" | sed 's/^/      /'; }
  rm -rf "$ws"
  [ "$verdict" = ok ]
}

echo "== $NAME"
FAILED=0
run_case "A raw fixture -> fail"        'true'                                   fail || FAILED=1
if [ -d "$T/solution" ]; then
  run_case "B reference -> full"        'apply_solution "$ws"'                   full || FAILED=1
  run_case "D reference+exploit -> full" 'apply_solution "$ws"; plant_exploit "$ws"' full || FAILED=1
else
  echo "  (no solution/ -- B and D skipped)"
fi
run_case "C exploit only -> fail"       'plant_exploit "$ws"'                    fail || FAILED=1
exit $FAILED
