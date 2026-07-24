# Pre-registered analysis: the only delegation in 120 runs

Date: 2026-07-24. Zero new API spend: this is a forensic reanalysis of one
transcript (plus its comparators) already public in this repo. No graded
runs are executed.

## Question

The month's discourse says the harness supplies "parallel workers" and the
model supplies judgment; Codex CLI shipped subagent support in July. Our
120-run corpus contains exactly one observation of a model using workers
unprompted: `bouts/2026-07-17-fable-sol-kimi/05-review-transplant/
gpt-5.6-sol/run-2` (97 tool calls, 4 Agent spawns). The 2026-07-19
mechanism trace flagged it as a bonus find and characterized it as a
spontaneous blinded 4-subagent review panel, but never analyzed the
excursion's content. This analysis asks: what did the panel actually do,
what did it cost, and what did it buy?

## Corpus (fixed before analysis)

- Target: `05-review-transplant/gpt-5.6-sol/run-2` (transcript, workspace
  findings.md, judge.json samples, result.json, wall_seconds,
  proxy_usage.jsonl).
- Siblings: same cell run-1 and run-3 (the non-delegating baselines).
- Anchors: `claude-fable-5` and `kimi-k3` cells on the same task (surface
  metrics only, for the cost frame).

## Disclosure of prior looks (what is exploratory vs confirmatory)

Published or examined before this design was written: the run's tool-call
category counts (97 calls: Agent 4, Read 27, Bash 39, Write 1, SendMessage
4, TaskCreate 3, TaskUpdate 8, TaskList 4, TaskGet 3, TaskOutput 1,
TaskStop 3, from mechanism.md), the cell aggregates in the bout results.md
(wall 357 +/- 409 s, cost $1.39 +/- 1.81, out-tok 28377 +/- 38499, all
three runs pass 3/3 and judge median 6/6), and the 07-19 characterization
quoted above. The cell aggregates make the excursion's outlier status
derivable in rough form, so H2 tests exact values of a pattern we can
already see the shape of; it is listed for quantification, not discovery.
NOT examined: the transcript's event contents (subagent prompts, subagent
outputs, timestamps, main-thread text), the target or sibling findings.md
deliverables, any judge.json sample text for this cell, per-run
wall/cost/usage records, and the sibling transcripts. All hypotheses below
except H2 live entirely in that unexamined territory.

## Definitions

- "Subagent lifetime": from the timestamp of its Agent spawn call to the
  timestamp of the last event that returns or reads its output
  (TaskOutput/SendMessage result or completion notification), from
  transcript timestamps.
- "Overlap": two lifetimes overlap if their intervals intersect for more
  than 10% of the shorter lifetime.
- "Finding": one `- <path>:<line> <description>` line in a findings.md
  deliverable, per the task's output contract; for subagent reports, any
  defect claim with a file location in the subagent's returned text.
- "Match": two findings match if they name the same path, line numbers
  within +/- 2, and the same defect mechanism. Borderline calls are
  adjudicated by hand and every adjudication is recorded verbatim in
  excursion.json (quote both sides).
- "Ceiling": judge median 2 on all three rubric dimensions (= 6/6 total).

## Hypotheses (falsifiable; misses reported first in any article)

- H1 (the parallel workers ran serially): No two of the four subagent
  lifetimes overlap. Prediction: the panel was sequential in practice,
  i.e. the one observed spontaneous delegation did not use the harness's
  parallelism. Refuted if any two lifetimes overlap.
- H2 (the panel multiplied cost, quantified): The excursion run's metered
  cost is >= 5x the median of its two siblings, and its wall clock >= 3x.
  (Shape known from published aggregates; exact multiples are what this
  pins down.)
- H3 (blind reviewers disagree): At least one defect reported by one
  subagent has no match in at least one other subagent's report. Refuted
  if all four reports contain matching finding sets.
- H4 (the funnel drops findings): At least one defect reported by a
  subagent has no match in the final findings.md. Refuted if every
  subagent finding survives to the deliverable.
- H5 (no judge-visible dividend): Both siblings already score ceiling, and
  the excursion's findings.md does not contain more distinct findings than
  the larger sibling deliverable. Refuted if a sibling is sub-ceiling (the
  panel would then have room to buy depth) or the excursion out-finds both
  siblings.
- H6 (delegation without trust): The main thread itself Read every file
  under `src/` that it assigned to a subagent, i.e. Sol reviewed the code
  AND commissioned the panel, doing the work twice. Refuted if at least
  one delegated file was never Read by the main thread.

## Method

One script (`analyze.py`, committed here) parses the target and sibling
transcripts, extracts the Agent spawn events with their prompts, the
subagent lifecycle events and returned outputs, timestamps for the overlap
computation, and the per-run wall/cost/usage records; it emits
`excursion.json` (ordered annotated trace, subagent intervals, extracted
finding sets with match adjudications, per-run cost table) and
`excursion.md` (the hypothesis scorecard plus the panel timeline). The
parser fails loudly on unrecognized event shapes rather than skipping
them. Finding extraction from free-text subagent reports is done by hand
against the definitions above and recorded in the json; nothing is scored
by an LLM (the arena Anthropic key is dead today, which also enforces the
zero-spend constraint).

## Reporting rules

Standing disclosures apply: Claude Code is home field for Anthropic
models, the judge in the source bout is Opus 4.8, Fable 5 co-authors the
harness and the articles, harness effects have a sign per pairing. One
more for this piece: the run under the microscope is a competitor model
inside Anthropic's harness, and the subagent behavior under study is a
Claude Code feature; whether the same excursion happens under Codex is
untested here (single run, no causal claims about frequency). All claims
in any resulting article must cite run paths in this repo.
