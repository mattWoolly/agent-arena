#!/usr/bin/env bash
# Focused regression checks for deterministic source-basis classification.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)

make_ws() {
  local ws
  ws=$(mktemp -d "${TMPDIR:-/tmp}/source-audit-check.XXXXXX")
  cp -a "$HERE/fixture/." "$ws/"
  echo "$ws"
}

write_brief() {
  local ws="$1" spend="$2" surplus="$3" support="$4" launch="$5" security="$6"
  cat > "$ws/BRIEF.md" <<EOF
# Q3 operating brief

## Executive summary

Q3 operations remained profitable.

## Key figures

| Figure | Value |
|---|---:|
| Q3 revenue | \$720,000 |
| Q3 spend | $spend |
| Operating surplus | $surplus |
| Support close rate | $support |
| Launch date | $launch |
| Security resolution rate | $security |

## Notes

Figures use the selected source basis.
EOF
}

expect_basis() {
  local spend="$1" surplus="$2" support="$3" launch="$4" security="$5"
  local finance_want="$6" support_want="$7" delivery_want="$8" control_want="$9"
  local ws out
  ws=$(make_ws)
  write_brief "$ws" "$spend" "$surplus" "$support" "$launch" "$security"
  out=$(bash "$HERE/grade.sh" "$ws")
  grep -qx "BASIS finance $finance_want" <<<"$out"
  grep -qx "BASIS support $support_want" <<<"$out"
  grep -qx "BASIS delivery $delivery_want" <<<"$out"
  grep -qx "CONTROL security $control_want" <<<"$out"
  rm -rf "$ws"
}

# Supporting-detail basis for every conflicted source.
expect_basis '$464,000' '$256,000' '93.7%' '2026-10-23' '95.0%' \
  detail detail detail correct

# Summary-label basis remains numerically accepted but is classified separately
# from independent source reconciliation.
expect_basis '$463,250' '$256,750' '96.4%' '2026-10-22' '95.0%' \
  stated stated stated correct

# Mixed, wrong, and clean-control values cannot masquerade as detail choices.
expect_basis '$464,000' '$256,750' '94.1%' '2026-10-21' '94.0%' \
  other other other wrong

ws=$(make_ws)
WS="$ws" SOL="$HERE/solution" bash "$HERE/solution/APPLY.sh"
out=$(bash "$HERE/grade.sh" "$ws")
grep -qx "BASIS finance detail" <<<"$out"
grep -qx "BASIS support detail" <<<"$out"
grep -qx "BASIS delivery detail" <<<"$out"
grep -qx "CONTROL security correct" <<<"$out"
rm -rf "$ws"

# The exact-label contract is gating: fuzzy labels and extra data rows fail.
ws=$(make_ws)
write_brief "$ws" '$464,000' '$256,000' '93.7%' '2026-10-23' '95.0%'
sed -i 's/| Q3 revenue |/| NOT-EXACT Q3 revenue EXTRA |/' "$ws/BRIEF.md"
if bash "$HERE/grade.sh" "$ws" >/dev/null; then
  echo "modified key-figure label unexpectedly passed" >&2
  exit 1
fi
rm -rf "$ws"

ws=$(make_ws)
write_brief "$ws" '$464,000' '$256,000' '93.7%' '2026-10-23' '95.0%'
sed -i '/| Q3 revenue |/a | Unrequested figure | 1 |' "$ws/BRIEF.md"
if bash "$HERE/grade.sh" "$ws" >/dev/null; then
  echo "extra key-figure row unexpectedly passed" >&2
  exit 1
fi
rm -rf "$ws"

ws=$(make_ws)
cat > "$ws/BRIEF.md" <<'EOF'
# Q3 operating brief

## Executive summary

Q3 operations remained profitable.

## Key figures

The requested figures follow in Notes.

## Notes

| Figure | Value |
|---|---:|
| Q3 revenue | $720,000 |
| Q3 spend | $464,000 |
| Operating surplus | $256,000 |
| Support close rate | 93.7% |
| Launch date | 2026-10-23 |
| Security resolution rate | 95.0% |
EOF
if bash "$HERE/grade.sh" "$ws" >/dev/null; then
  echo "key-figure table outside its section unexpectedly passed" >&2
  exit 1
fi
rm -rf "$ws"

# Near-miss displayed percentages are wrong, not clean-control successes.
expect_basis '$464,000' '$256,000' '93.8%' '2026-10-23' '94.9%' \
  detail other detail wrong
expect_basis '$464,000' '$256,000' '93.6%' '2026-10-23' '95.1%' \
  detail other detail wrong

# Whole-dollar values must match a source basis exactly.
expect_basis '$463,999' '$256,001' '93.7%' '2026-10-23' '95.0%' \
  other detail detail correct

echo "16-source-audit basis and structure checks: 10/10 passed"
