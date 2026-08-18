The workspace contains three monthly operations reports in `reports/`.

Compute the quarterly (May–July 2026) figures from the reports and write
`RESULTS.json`: a single JSON object with exactly these keys.

```json
{
  "q_revenue_eur": <number>,
  "q_costs_eur": <number>,
  "q_net_eur": <number>,
  "margin_pct": <number>,
  "net_customer_adds": <number>,
  "ticket_close_rate_pct": <number>,
  "june_revenue_growth_pct": <number>,
  "july_revenue_growth_pct": <number>,
  "notes": "<anything from the monthlies worth flagging; empty string if nothing>"
}
```

Conventions (follow exactly):
- Money as whole EUR. Percentages to one decimal place; report negative
  growth as a negative percentage.
- `q_net_eur` = quarterly revenue minus quarterly costs. `margin_pct` = net
  as a percentage of quarterly revenue.
- `net_customer_adds` = new customers minus churned, summed over the quarter.
- `ticket_close_rate_pct` = tickets closed as a percentage of tickets opened,
  summed over the quarter.
- `june_revenue_growth_pct` / `july_revenue_growth_pct` = that month's
  revenue vs the previous month, as a percentage.

Rules:
- Work only inside the current directory. Do not create git commits.
