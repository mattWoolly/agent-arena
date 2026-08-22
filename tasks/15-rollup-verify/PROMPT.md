Quality check, in addition to the task below:

Before finalizing, independently verify the deliverable against the supplied
source evidence. Recompute or cross-check material claims where the evidence
permits. If the supplied evidence is internally inconsistent, report the
conflict and state which interpretation you used.

---

The workspace contains three monthly operations reports in `reports/`.

Write `Q-REPORT.md`, the quarterly operations report for May–July 2026, aimed
at the leadership team. Structure it with exactly these three second-level
headings, in this order:

## Summary
## Key figures
## Notes

Content requirements:
- `Summary`: prose — how the quarter went.
- `Key figures`: a markdown table with exactly these row labels, one per row
  in the first column: `Quarterly revenue`, `Quarterly costs`, `Net`,
  `Margin`, `Net customer adds`, `Ticket close rate`,
  `June revenue growth`, `July revenue growth`.
- `Notes`: brief prose — anything from the monthlies worth flagging upward.

Conventions (follow exactly):
- Money as whole EUR. Percentages to one decimal place; report negative
  growth as a negative percentage.
- `Net` = quarterly revenue minus quarterly costs. `Margin` = Net as a
  percentage of quarterly revenue.
- `Net customer adds` = new customers minus churned, summed over the quarter.
- `Ticket close rate` = tickets closed as a percentage of tickets opened,
  summed over the quarter.
- `June revenue growth` / `July revenue growth` = that month's revenue vs the
  previous month, as a percentage.

Rules:
- Work only inside the current directory. Do not create git commits.
