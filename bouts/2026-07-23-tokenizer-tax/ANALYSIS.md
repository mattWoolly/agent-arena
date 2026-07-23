# 2026-07-23-tokenizer-tax: INTERRUPTED (API credits exhausted)

Status: incomplete. No hypothesis from DESIGN.md was tested. Nothing in this
bout is publishable yet.

## What happened

- DESIGN.md was committed and pushed at 6cfc3f8 before any measurement.
- Mechanics smoke (single throwaway string, both model IDs) passed.
- Part C launched first (detached, serial). Runs completed in order:
  - 01-bugfix run-1: pass, $0.1083, 30.5s
  - 01-bugfix run-2: pass, $0.1020, 29.8s
  - 02-synthesis run-1: pass on grading, $0.1612, 113.5s, agent_exit=1
    (the agent process errored at the end of the run; the workspace still
    graded 6/6). Likely the first contact with the billing wall.
  - All 13 subsequent runs failed in under 2 seconds with the Anthropic
    billing error "Your credit balance is too low to access the API."
    Their artifacts are kept as-is; each records $0.00 and agent_exit=1.
- Part B fetched its inputs (UDHR English via UMN human rights library,
  sqlite_utils/db.py via GitHub) but Part A/B counting died on the same
  billing error: count_tokens does not bill tokens but is refused outright
  when the account balance is empty.
- Retry ~10 minutes later still returned the billing error. The founder was
  notified; only they can restore credits.

## Deviations from DESIGN.md

1. Part C ran ALL directories under tasks/, including 05-review-transplant
   and 06-instructions-transplant (16 planned runs, not 12). DESIGN
   specified the 6 base tasks; the run-bout.sh invocation omitted the task
   list. On resumption, restrict to the 6 base tasks or amend the H6
   denominator explicitly before rerunning.
2. The bout was stopped by an external failure, not by the design's $10
   hard stop. Spend before interruption: $0.37.

## Resumption plan

DESIGN.md hypotheses remain fixed and untested. When credits are restored:
rerun Part C cleanly (fresh run dirs; do not overwrite the interrupted
artifacts), then run analyze.py for Parts A and B. The intro-pricing news
peg holds until 2026-08-31.
