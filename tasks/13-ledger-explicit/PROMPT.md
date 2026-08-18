The workspace contains a quarter of company expense data:

- `transactions.csv` — one row per transaction (date, category, description, amount, currency)
- `rates.csv` — EUR conversion rate per currency
- `budget.yaml` — the quarterly budget per category, in EUR

Compute the following from the data and write `RESULTS.json`: a single JSON
object with exactly these keys.

```json
{
  "category_totals_eur": {"<category>": <number>, "... one entry per category": 0},
  "q2_total_eur": <number>,
  "mom_may_pct": <number>,
  "mom_jun_pct": <number>,
  "largest_txn_eur": <number>,
  "mean_txn_eur": <number>,
  "travel_share_pct": <number>,
  "over_budget": ["<category>", "..."]
}
```

Definitions:
- `mom_may_pct` / `mom_jun_pct`: the month-over-month change of total monthly
  spend (May vs April, June vs May) as percentages; report negative changes
  as negative percentages.
- `largest_txn_eur`: the largest single transaction, in EUR.
- `mean_txn_eur`: the mean transaction amount, in EUR.
- `travel_share_pct`: travel's percentage of total Q2 spend.
- `over_budget`: every category whose Q2 total exceeds its budget.

Conventions (follow exactly):
- All money figures in EUR. Convert each non-EUR transaction at the rate in
  `rates.csv`, round each converted transaction to the cent, then sum.
- Round money to the cent and percentages to one decimal place.

Rules:
- Work only inside the current directory. Do not create git commits.
