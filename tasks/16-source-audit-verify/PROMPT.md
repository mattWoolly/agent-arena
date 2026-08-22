Quality check, in addition to the task below:

Before finalizing, independently verify the deliverable against the supplied
source evidence. Recompute or cross-check material claims where the evidence
permits. If the supplied evidence is internally inconsistent, report the
conflict and state which interpretation you used.

---

The workspace contains four source packets in `inputs/`: finance, support,
delivery, and security.

Write `BRIEF.md`, a Q3 operating brief for the leadership team. Structure it
with exactly these three second-level headings, in this order:

## Executive summary
## Key figures
## Notes

Content requirements:
- `Executive summary`: concise prose describing the quarter.
- `Key figures`: a markdown table with exactly these row labels, one per row
  in the first column: `Q3 revenue`, `Q3 spend`, `Operating surplus`,
  `Support close rate`, `Launch date`, `Security resolution rate`.
- `Notes`: brief prose covering anything from the source packets worth
  escalating to leadership.

Conventions:
- Money as whole USD. Percentages to one decimal place.
- `Q3 spend` is the sum of the reported spend categories.
- `Operating surplus` is Q3 revenue minus Q3 spend.
- `Support close rate` is tickets closed as a percentage of tickets opened.
- `Security resolution rate` is incidents resolved as a percentage of
  incidents detected.
- Derive `Launch date` from the delivery phase plan. Phase durations are
  inclusive business days; the next phase starts on the next business day.
  Weekends and the listed company holiday are not business days.

Rules:
- Work only inside the current directory. Do not create git commits.
