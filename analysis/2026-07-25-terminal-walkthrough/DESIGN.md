# Pre-registered analysis: one terminal task, five models, three harnesses

Date: 2026-07-25. Zero new API spend: this is a reanalysis of transcripts
already public in this repo. No graded runs are executed.

## Question

`04-terminal` is the battery's environment-forensics task: `make test` is
broken by four independent planted faults that reveal themselves strictly
one at a time (a space-indented Makefile recipe kills the parse; then the
check script's stripped exec bit; then its CRLF shebang; then a trailing
comma in `data/config.json`). Every one of the 19 public runs scored 4/4.
The scores carry no information; the trajectories carry all of it. This
analysis walks the task move by move across five models and three
harnesses and asks: who peels the onion one error at a time, who reads
ahead and batches, what the harness changes, and whether the run's own
SOLUTION.md report can be trusted against the known ground truth.

## Ground truth (from the task definition, fixed before analysis)

From `tasks/04-terminal/` fixture + setup.sh, the fault set is exactly:

1. `Makefile`: the `test` recipe line is space-indented (make parse error,
   "missing separator"), planted in the fixture.
2. `scripts/run_checks.sh`: exec bit stripped (Permission denied), planted
   by setup.sh.
3. `scripts/run_checks.sh`: CRLF line endings (bad interpreter:
   `/bin/bash\r`), planted by setup.sh.
4. `data/config.json`: trailing comma (invalid JSON, caught by
   `tools/validate_config.py`), planted in the fixture.

Discovery is serial by construction: fault N+1's error message cannot
appear until fault N is fixed, unless the agent goes looking without being
told.

## Corpus (fixed before analysis)

19 runs of `04-terminal`, 7 configurations, 5 models, 3 harnesses:

- `bouts/2026-07-17-fable-sol-kimi/04-terminal/` — Fable 5, GPT-5.6 Sol,
  Kimi K3 under Claude Code, 3 runs each (9).
- `bouts/2026-07-17-sol-codex-homegame/04-terminal/` — Sol under Codex, 3.
- `bouts/2026-07-18-kimi-homegame/04-terminal/` — Kimi K3 under Kimi
  Code, 3.
- `bouts/2026-07-20-glm52/04-terminal/` — GLM-5.2 under Claude Code, 3;
  Opus 4.8 under Claude Code, 1 (anchor; n=1, reported as such).

Per run: transcript.jsonl, workspace (incl. SOLUTION.md, preserved in all
19), workspace.diff/diffstat, wall_seconds, metrics.json, grade.txt.

## Disclosure of prior looks (what is exploratory vs confirmatory)

Already public, and examined during today's scoping: per-run surface stats
from each bout's results.json (wall, cost, tokens, tool-call category
counts, and final_message strings — including Fable run-1's claim of "four
independent environment/config problems"); the 07-19 mechanism-trace
aggregates (per-task read/call tables, first-call distributions, 9/9
Bash-first on this task); the task definition and grader.

Also already public but NOT re-opened today: the 07-19 trace's
mechanism.json, whose per-run records include ordered tool-call traces
with command first-lines for 15 of these 19 runs (all but the GLM bout),
plus each run's workspace.diffstat. Checker-cycle counts (H1, H4) and
fix-file sets (H7) are therefore DERIVABLE from published artifacts for
most of the corpus; those hypotheses pin exact values of shapes a reader
could partially reconstruct, and we flag them as quantification rather
than blind prediction. The 07-19 design additionally disclosed an
exploratory look at this task's Claude Code call sequences in a prior
session. Genuinely unexamined anywhere: all transcript event CONTENTS
(full commands, tool results, error text, assistant messages, timestamps
beyond time-to-first-modification), the GLM-bout traces, all 19
SOLUTION.md texts, and all workspace.diff contents.

## Definitions

- "Checker execution": a Bash/exec event whose command runs `make test`,
  `make check`, or `./scripts/run_checks.sh` (or a strict subset such as
  `python3 tools/validate_config.py`), in any harness's command syntax.
- "Checker cycle count": number of checker executions in the run,
  including the final green one.
- "Proactive fix/scan": a tool event that fixes or inspects fault N's
  artifact before any checker execution has surfaced fault N's error
  message (e.g. a repo-wide CRLF sweep after only the Makefile error has
  been seen, or opening config.json before the validator has failed).
  Reading a file for unrelated reasons does not count; the event must
  target the fault's mechanism. Borderline calls are adjudicated by hand
  and recorded verbatim in walkthrough.json.
- "Inter-event gap": wall-clock between one tool event's completion
  timestamp and the next tool event's start, i.e. time attributable to
  model generation/latency rather than tool execution.
- "Fix-file set": paths modified per workspace.diff, excluding SOLUTION.md
  and bytecode; mode-only changes count as modifications.
- "Accurate SOLUTION.md": enumerates all four ground-truth faults and no
  invented extras (the exec bit and CRLF may be reported as one combined
  script problem or two; both mappings count as covering faults 2-3, and
  the adjudication is recorded verbatim).

## Hypotheses (falsifiable; misses reported first in any article)

- H1 (peel, don't batch): in >= 15 of 19 runs the checker cycle count is
  >= 5, i.e. the serial floor (four failures plus one green) is paid in
  full. [quantification; partially derivable from published traces]
- H2 (nobody generalizes the damage): a proactive fix/scan occurs in <= 3
  of the 19 runs. The task prompt's "botched merge from another machine"
  is a standing invitation to sweep for line-ending damage; we predict
  almost nobody RSVPs.
- H3 (harness sign, exact values): Sol's median wall under Codex is <=
  0.5x its median under Claude Code; Kimi's median wall under Kimi Code is
  >= 2.5x its median under Claude Code. [quantification; derivable from
  published results.json; listed to pin the single-task numbers]
- H4 (the home-field slowdown is loops, not lag): Kimi under Kimi Code has
  a median checker cycle count >= 1.5x Kimi under Claude Code. Fallback
  read if cycles tie: >= 50% of Kimi Code wall-clock sits in inter-event
  gaps in >= 2 of 3 runs. [cycle half partially derivable]
- H5 (the report can be trusted): >= 16 of 19 SOLUTION.md files are
  accurate per the definition above.
- H6 (run the failure first): in >= 17 of 19 runs, the first repo-touching
  call executes the checker rather than surveying (ls/find/cat/Read).
- H7 (one destination): all 19 fix-file sets equal {Makefile,
  scripts/run_checks.sh, data/config.json}. [partially derivable from
  published diffstats]

## Method

`analyze.py` (committed here) adapts the 07-19 parser for the three
transcript formats, fails loudly on unrecognized events, and emits
`walkthrough.json` (per-run: ordered event timeline with timestamps,
checker executions and the error each surfaced, fault-discovery order,
proactive-scan adjudications, inter-event gap totals, SOLUTION.md fault
mapping with verbatim quotes, fix-file sets) and `walkthrough.md` (the
hypothesis scorecard plus per-configuration tables). The article's
narrative walks one run per configuration with verbatim command/error
snippets, run paths cited.

## Reporting rules

Standing disclosures apply: Claude Code is home field for Anthropic
models, the judge in the source bouts is Opus 4.8 (not exercised here:
04-terminal grades deterministically), Fable 5 co-authors the harness and
the articles, harness effects have a sign per pairing. Misses first. All
claims cite run paths in this repo.
