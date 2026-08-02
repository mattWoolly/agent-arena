#!/usr/bin/env bash
# Prove the grader AND the tension: raw fixture fails; reference passes 2/2;
# a naive "decide sign from the raw input" implementation fails specifically
# the rounds-to-zero test while passing the rest (so the whack-a-mole is real
# and localized, not an impossible task).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
rc=0
mk() { local d; d=$(mktemp -d); cp -a "$HERE/fixture/." "$d/"
  git -C "$d" init -q && git -C "$d" add -A
  git -C "$d" -c user.email=t@t -c user.name=t -c commit.gpgsign=false commit -qm base; echo "$d"; }

WS=$(mk)
bash "$HERE/grade.sh" "$WS" >/dev/null 2>&1 && { echo "BAD: raw passed"; rc=1; } || echo "ok: raw fixture fails"
rm -rf "$WS"

WS=$(mk); cp "$HERE/solution/money.py" "$WS/money/money.py"; echo ref > "$WS/SOLUTION.md"
out=$(bash "$HERE/grade.sh" "$WS" 2>&1); echo "$out" | grep -q "SCORE: 2/2" && echo "ok: reference 2/2" || { echo "BAD: reference not 2/2"; echo "$out"; rc=1; }
rm -rf "$WS"

# Naive: sign from RAW input, otherwise correct rounding. Should fail exactly
# the rounds-to-zero test.
WS=$(mk)
cat > "$WS/money/money.py" <<'PY'
from decimal import Decimal, ROUND_HALF_UP
def format_amount(amount, *, currency="$", parens_for_negative=True, group=True):
    negative = amount < 0                      # BUG: sign from raw input
    d = Decimal(str(abs(amount))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, cents = divmod(int((d*100).to_integral_value()), 100)
    ws = f"{whole:,}" if group else str(whole)
    body = f"{currency}{ws}.{cents:02d}"
    if negative:
        return f"({body})" if parens_for_negative else f"-{body}"
    return body
PY
echo naive > "$WS/SOLUTION.md"
res=$(cd "$WS" && python3 -m pytest -q 2>&1)
if echo "$res" | grep -q 'test_small_negative_rounds_to_zero' && echo "$res" | grep -qE 'test_negative_half_away_from_zero PASSED|passed'; then
  # confirm the specific failure and that most tests pass
  nfail=$(echo "$res" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0)
  echo "ok: naive(sign-from-raw) fails the rounds-to-zero case ($nfail failing) — tension is real and localized"
else
  echo "WARN: naive impl failure not as expected:"; echo "$res" | tail -3
fi
rm -rf "$WS"
exit "$rc"
