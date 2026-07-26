#!/usr/bin/env bash
# Prove the grader: raw fixture FAILs, clean reference PASSes 3/3, and a
# naive-but-plausible implementation that passes visible tests still FAILs
# the hidden edge cases (the whole point of a ceiling-raiser).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
rc=0
mk() { local d; d=$(mktemp -d); cp -a "$HERE/fixture/." "$d/"; echo "$d"; }

WS=$(mk)
if bash "$HERE/grade.sh" "$WS" >/dev/null 2>&1; then echo "BAD: raw fixture passed"; rc=1; else echo "ok: raw fixture fails"; fi
rm -rf "$WS"

WS=$(mk); cp "$HERE/solution/engine.py" "$WS/sheet/engine.py"; echo "ref" > "$WS/SOLUTION.md"
out=$(bash "$HERE/grade.sh" "$WS" 2>&1); echo "$out" | grep -q "SCORE: 3/3" && echo "ok: clean reference 3/3" || { echo "BAD: reference not 3/3"; echo "$out"; rc=1; }
rm -rf "$WS"

# Naive impl: eval-based, no cycle detection, wrong on unary/assoc edge cases.
# Passes the three visible tests, must fail hidden.
WS=$(mk)
cat > "$WS/sheet/engine.py" <<'PY'
class CycleError(Exception):
    pass

def evaluate(cells):
    import re
    out = {}
    def val(name, seen=()):
        raw = cells[name].strip()
        if not raw.startswith("="):
            return float(raw)
        expr = raw[1:]
        def repl(m):
            return str(val(m.group(0), seen))
        expr = re.sub(r"[A-Za-z]+[0-9]*", repl, expr)
        return float(eval(expr))
    for k in cells:
        out[k] = val(k)
    return out
PY
echo naive > "$WS/SOLUTION.md"
vis=$(cd "$WS" && python3 -m pytest -q tests/ >/dev/null 2>&1 && echo VISPASS || echo VISFAIL)
out=$(bash "$HERE/grade.sh" "$WS" 2>&1)
if [[ "$vis" == "VISPASS" ]] && echo "$out" | grep -q "FAIL: hidden"; then
  echo "ok: naive impl passes visible, fails hidden (discriminating)"
else
  echo "WARN: naive impl behavior — visible=$vis; grader said:"; echo "$out" | grep -E 'hidden|SCORE'
fi
rm -rf "$WS"
exit "$rc"
