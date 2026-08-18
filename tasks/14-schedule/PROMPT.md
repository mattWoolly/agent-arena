The workspace contains a delivery-plan input:

- `milestones.yaml` — the ordered milestones with durations in business days
- `holidays.csv` — company holidays

Write `PLAN.md`, the delivery plan for the engineering org. Structure it with
exactly these three second-level headings, in this order:

## Timeline
## Countdown
## Notes

Content requirements:
- `Timeline`: a markdown table with columns `Milestone | Start | End`, one
  row per milestone in plan order, all dates in ISO format (YYYY-MM-DD).
- `Countdown`: a markdown table with exactly these row labels, one per row in
  the first column: `Business days until kickoff`, `Total business days`.
- `Notes`: brief prose — the shape of the plan and anything worth calling
  out.

Scheduling conventions (follow exactly):
- Business days are Monday–Friday, excluding every date in `holidays.csv`.
- Milestones run strictly in the listed order: the first starts on
  `project_start`; each later milestone starts on the next business day after
  the previous one ends.
- A milestone's duration counts business days inclusive of its start day: a
  3-business-day milestone starting Monday ends Wednesday.
- `Business days until kickoff`: business days after today, 2026-08-17, up to
  and including the project start date.
- `Total business days`: business days from project start through the last
  milestone's end, inclusive.

Rules:
- Work only inside the current directory. Do not create git commits.
