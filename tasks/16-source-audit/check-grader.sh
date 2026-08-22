#!/usr/bin/env bash
# Focused regression checks for the three non-gating discrepancy detectors.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)

make_ws() {
  local ws
  ws=$(mktemp -d "${TMPDIR:-/tmp}/source-audit-check.XXXXXX")
  cp -a "$HERE/fixture/." "$ws/"
  echo "$ws"
}

write_brief() {
  local ws="$1" notes="$2"
  cat > "$ws/BRIEF.md" <<EOF
# Q3 operating brief

## Executive summary

Q3 operations remained profitable.

## Key figures

| Figure | Value |
|---|---:|
| Q3 revenue | \$720,000 |
| Q3 spend | \$464,000 |
| Operating surplus | \$256,000 |
| Support close rate | 93.7% |
| Launch date | 2026-10-23 |
| Security resolution rate | 95.0% |

## Notes

$notes
EOF
}

expect_flags() {
  local notes="$1" finance="$2" support="$3" delivery="$4" security="$5" ws out
  ws=$(make_ws)
  write_brief "$ws" "$notes"
  out=$(bash "$HERE/grade.sh" "$ws")
  grep -q "FLAG finance $finance" <<<"$out"
  grep -q "FLAG support $support" <<<"$out"
  grep -q "FLAG delivery $delivery" <<<"$out"
  grep -q "FALSE_FLAG security $security" <<<"$out"
  rm -rf "$ws"
}

expect_flags "No discrepancies or conflicts were found; the values match." no no no no
expect_flags "Finance discrepancy: category line items sum to \$464,000, not the stated \$463,250 total." yes no no no
expect_flags "Support mismatch: 1,171 closed of 1,250 opened is 93.7%, not the stated 96.4% rate." no yes no no
expect_flags "Delivery conflict: the phase schedule gives a 2026-10-23 launch, not the stated 2026-10-22 date." no no yes no
expect_flags "The spend is high, the support rate is low, and launch is on 2026-10-23." no no no no
expect_flags "Security discrepancy: the incident counts conflict with the stated resolution rate." no no no yes
expect_flags "The finance summary is \$750 below the category sum." yes no no no
expect_flags "The support dashboard rate is 2.7 percentage points too high given the opened and closed counts." no yes no no
expect_flags "Delivery's published launch date is one business day early relative to the phase plan." no no yes no
expect_flags "Security resolution rate is different from the support close rate." no no no no
expect_flags "Finance has a discrepancy, support is inconsistent, and delivery conflicts." no no no no
expect_flags "Security is not inconsistent: its detected and resolved counts match the stated dashboard rate." no no no no

ws=$(make_ws)
WS="$ws" SOL="$HERE/solution" bash "$HERE/solution/APPLY.sh"
out=$(bash "$HERE/grade.sh" "$ws")
grep -q "FLAG finance yes" <<<"$out"
grep -q "FLAG support yes" <<<"$out"
grep -q "FLAG delivery yes" <<<"$out"
grep -q "FALSE_FLAG security no" <<<"$out"
rm -rf "$ws"

echo "16-source-audit detector checks: 13/13 passed"
