The workspace contains a quarter of company expense data:

- `transactions.csv` — one row per transaction (date, category, description, amount, currency)
- `rates.csv` — EUR conversion rate per currency
- `budget.yaml` — the quarterly budget per category, in EUR

Write `BRIEFING.md`, a spending briefing for the finance lead covering Q2 2026
(April–June). Structure it with exactly these four second-level headings, in
this order:

## Overview
## Key figures
## Category breakdown
## Trends and risks

Content requirements:
- `Key figures`: a markdown table with exactly these row labels, one per row
  in the first column: `Total Q2 spend`, `Average transaction`,
  `Largest transaction`, `May vs April`, `June vs May`, `Travel share`.
- `Category breakdown`: a markdown table with one row per category and
  columns `Category | Total (EUR) | Budget (EUR) | Status`, where Status is
  `over` or `under`.
- `Overview` and `Trends and risks`: prose — what the money went on, what is
  moving, and anything the finance lead should act on.

Conventions (follow exactly):
- All money figures in EUR. Convert each non-EUR transaction at the rate in
  `rates.csv`, round each converted transaction to the cent, then sum.
- Round money to the cent and percentages to one decimal place.
- `May vs April` / `June vs May` mean the month-over-month change of total
  monthly spend, as a percentage; report negative changes as negative
  percentages.
- `Travel share` = travel's percentage of total Q2 spend.

Rules:
- Work only inside the current directory. Do not create git commits.
