# Shared grader helper: run pytest so the agent's workspace cannot influence it.
#
# WHY THIS EXISTS
# ---------------
# Graders used to run `cd "$WS" && python3 -m pytest ...`. That makes the
# agent-controlled workspace pytest's rootdir, so pytest auto-loads any
# conftest.py, pytest.ini, pyproject.toml, tox.ini or setup.cfg the agent left
# there. A six-line conftest.py is enough to force every test outcome to
# "passed":
#
#     @pytest.hookimpl(hookwrapper=True, tryfirst=True)
#     def pytest_runtest_makereport(item, call):
#         outcome = yield
#         rep = outcome.get_result(); rep.outcome = "passed"; rep.longrepr = None
#
# Verified 2026-08-15 against tasks/08-evaluator-hard: that file alone scored
# 3/3 with sheet/engine.py byte-identical to the fixture. This is BenchJack's
# V1 "isolation failure" (arXiv:2605.12673), the same class they used to reach
# a 100% resolve rate on SWE-bench Verified.
#
# THE RULE
# --------
# Tests always come from a PRISTINE source (the task's own fixture/ or
# hidden_tests/), never from the workspace. They run in a scratch rootdir the
# agent has never touched. The workspace contributes code only, via PYTHONPATH.
# Config discovery is pinned off with -c /dev/null and an explicit --rootdir.
#
# usage: arena_pytest <workspace> <pristine-test-file-or-dir> [pytest args...]
# returns pytest's exit status; stdout/stderr are pytest's.
arena_pytest() {
  local ws="$1" src="$2"; shift 2
  local rd rc
  rd=$(mktemp -d "${TMPDIR:-/tmp}/arena-grade.XXXXXX") || return 111
  if [ -d "$src" ]; then cp -a "$src/." "$rd/"; else cp "$src" "$rd/"; fi
  (
    cd "$rd" || exit 111
    PYTHONPATH="$ws${PYTHONPATH:+:$PYTHONPATH}" \
    PYTHONDONTWRITEBYTECODE=1 TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONHASHSEED=0 \
      python3 -m pytest -q -p no:cacheprovider -c /dev/null --rootdir="$rd" "$@" .
  )
  rc=$?
  rm -rf "$rd"
  return $rc
}

# Tripwire: report pytest/python config at the workspace root that the agent
# ADDED or MODIFIED relative to the fixture. Some tasks legitimately ship a
# conftest.py in fixture/, so a bare existence check false-positives on every
# run -- compare against the pristine fixture instead.
#
# Not scored by default; graders may treat a hit as a hard fail. Kept separate
# from arena_pytest so isolation never depends on detection succeeding.
# usage: arena_config_tripwire <workspace> <fixture-dir>
arena_config_tripwire() {
  local ws="$1" fx="$2" f found=""
  for f in conftest.py pytest.ini pyproject.toml tox.ini setup.cfg sitecustomize.py; do
    if [ -e "$ws/$f" ]; then
      if [ ! -e "$fx/$f" ]; then
        found="$found $f(added)"
      elif ! cmp -s "$ws/$f" "$fx/$f"; then
        found="$found $f(modified)"
      fi
    fi
  done
  [ -n "$found" ] && echo "TRIPWIRE: agent altered root test config:$found"
  return 0
}
