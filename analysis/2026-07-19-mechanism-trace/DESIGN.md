# Pre-registered analysis: mechanism traces from 120 published runs

Date: 2026-07-19. Zero new API spend: this is a reanalysis of transcripts
already public in this repo. No graded runs are executed.

## Question

Every configuration in the published three-way bout passed every task, and
the published notes described working styles at the aggregate level (tool
mixes, diffstat identity, wall-clock variance). This analysis goes one
level down: what does each model actually DO, move by move, on the same
task? First action, what it reads before it edits, when it runs the tests,
what it repeats, and what any of that costs.

## Corpus (fixed before analysis)

- `bouts/2026-07-17-fable-sol-kimi/` — 8 tasks x 3 models x 3 repeats,
  all under Claude Code (72 runs).
- `bouts/2026-07-17-sol-codex-homegame/` — 8 tasks x 3 repeats, Sol under
  Codex (24 runs).
- `bouts/2026-07-18-kimi-homegame/` — 8 tasks x 3 repeats, Kimi K3 under
  Kimi Code (24 runs).

Featured narrative task: `01-bugfix` (lrucache). Corpus-wide statistics
cover all eight task variants.

## Disclosure of prior looks (what is exploratory vs confirmatory)

Before writing these hypotheses we examined, during topic scoping: the
tool-call sequences of `01-bugfix` and `04-terminal` in the Claude Code
bout (18 of 120 runs) and per-run metrics.json summaries. We have NOT
examined the other six tasks' transcripts, any home-game transcript, or
any timestamp data. Hypotheses generalize patterns seen in those 18 runs;
the other 102 runs and all timing claims are confirmatory territory.

## Definitions

- "Task-management calls": TaskCreate/TaskUpdate/TaskGet/TaskList (Claude
  Code) and update_plan or equivalent planning tools (Codex, Kimi Code).
- "Repo-touching call": any tool call that is not task management.
- "File modification": Edit/Write/apply_patch/str_replace-style calls,
  excluding writes of `SOLUTION.md`/`findings.md`/`report.md` deliverables.
- "Checker": the task's stated verification command (01: pytest, 03: the
  checker in the prompt, 04: make test). Repair-style tasks = 01, 04
  (something is failing at t=0).
- "Re-read": a Read of a file path already Read earlier in the same run.

## Hypotheses (falsifiable; misses reported first in any article)

- H1 (diagnose before reading): In >= 80% of the 72 Claude Code runs, the
  first repo-touching call is a Bash survey or checker execution, not a
  file Read.
- H2 (the ritual is harness-supplied): (a) Sol emits >= 1 TaskCreate
  before any repo-touching call in >= 20 of its 24 Claude Code runs, and
  task-management calls are >= 25% of its total tool calls in that bout;
  (b) under Codex the overhead does not survive: mean planning-tool calls
  per Sol run < 2 (vs >= 9 in Claude Code).
- H3 (look before you leap): On repair-style tasks (01, 04), the agent
  runs the checker before its first file modification in >= 90% of the 30
  runs across all five configurations.
- H4 (re-reading is a Sol trait, not a task trait): Sol re-reads at least
  one file in >= 16 of its 24 Claude Code runs; Fable does so in <= 4 of
  its 24.
- H5 (Kimi frugality): Kimi in Claude Code has the lowest total Read
  count of the three configurations on >= 6 of 8 tasks, and at least one
  passing Kimi run on a code task never Reads any test file.
- H6 (Sol moves most): Sol in Claude Code has the highest tool-call total
  of the three Claude Code configurations on >= 7 of 8 tasks.
- H7 (motion delays the fix): Fable's median elapsed time from first tool
  call to first file modification is shorter than Sol's (both in Claude
  Code) on >= 7 of 8 tasks, from transcript timestamps.

## Method

One script (`analyze.py`, committed here) parses every transcript in the
corpus and emits `mechanism.json` (per-run: ordered tool-call trace with
classified phases, first-move class, checker-before-edit flag, re-read
count, per-category call counts, time-to-first-modification) and
`mechanism.md` (the hypothesis scorecard plus per-task tables). Codex and
Kimi Code transcripts differ in format; the parser handles each driver's
format explicitly and fails loudly on unrecognized events rather than
skipping them.

## Reporting rules

Standing disclosures apply: Claude Code is home field for Anthropic
models, the judge in the source bouts is Opus 4.8, Fable 5 co-authors the
harness and the articles, harness effects have a sign per pairing. All
claims in any resulting article must cite run paths in this repo.
