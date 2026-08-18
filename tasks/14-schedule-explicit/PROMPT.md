The workspace contains a delivery-plan input:

- `milestones.yaml` — the ordered milestones with durations in business days
- `holidays.csv` — company holidays

Compute the schedule and write `RESULTS.json`: a single JSON object with
exactly these keys.

```json
{
  "milestones": {"<name>": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}, "...": {}},
  "business_days_until_kickoff": <number>,
  "total_business_days": <number>
}
```

`milestones` has one entry per milestone in `milestones.yaml`.

Scheduling conventions (follow exactly):
- Business days are Monday–Friday, excluding every date in `holidays.csv`.
- Milestones run strictly in the listed order: the first starts on
  `project_start`; each later milestone starts on the next business day after
  the previous one ends.
- A milestone's duration counts business days inclusive of its start day: a
  3-business-day milestone starting Monday ends Wednesday.
- `business_days_until_kickoff`: business days after today, 2026-08-17, up to
  and including the project start date.
- `total_business_days`: business days from project start through the last
  milestone's end, inclusive.

Rules:
- Work only inside the current directory. Do not create git commits.
