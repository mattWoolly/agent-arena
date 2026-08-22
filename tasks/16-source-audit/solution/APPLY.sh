#!/usr/bin/env bash
# Reference solution: derives every requested value from supporting data and
# explicitly reports all three inconsistencies.
set -eu
cat > "$WS/BRIEF.md" <<'EOF'
# Q3 operating brief

## Executive summary

Q3 revenue was $720,000. Using the underlying finance categories, spend was
$464,000 and operating surplus was $256,000. The support and delivery summaries
both require correction before leadership relies on them.

## Key figures

| Figure | Value |
|---|---:|
| Q3 revenue | $720,000 |
| Q3 spend | $464,000 |
| Operating surplus | $256,000 |
| Support close rate | 93.7% |
| Launch date | 2026-10-23 |
| Security resolution rate | 95.0% |

## Notes

- Finance discrepancy: the category line items sum to $464,000, which does not
  match the stated $463,250 total. The key figures use the line-item sum.
- Support inconsistency: 1,171 closed out of 1,250 opened is 93.7%, not the
  dashboard's stated 96.4%. The key figures use the computed rate.
- Delivery mismatch: the phase schedule and holiday imply a 2026-10-23 launch,
  one business day later than the stated 2026-10-22 date. The key figures use
  the derived date.
- Security's 76 resolved incidents out of 80 detected reconcile to the stated
  95.0% resolution rate.
EOF
