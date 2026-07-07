# Agent Arena

Head-to-head harness for comparing agentic coding models running under Claude Code.
Give two model IDs the same graded tasks in isolated workspaces, capture everything,
and let the graders (not vibes) decide.

## Layout

```
bin/
  run-bout.sh    # run all (or selected) tasks for two models, pairwise-parallel
  run-task.sh    # run ONE model on ONE task: seed workspace, run claude -p, grade
  metrics.py     # extract cost/turns/tokens/tool-calls from a run's transcript
  summarize.py   # aggregate a bout directory into results.md + results.json
tasks/
  01-bugfix/         # SWE-bench style: fix library code until tests pass
  02-synthesis/      # HumanEval/MBPP style: implement 5 specified functions
  03-refactor/       # Aider-refactor style: dict config -> frozen dataclass
  04-terminal/       # Terminal-Bench style: repair a broken build environment
  05-review/         # code-review style: find planted defects in a diff
  06-instructions/   # IFEval style: report generation under hard constraints
bouts/
  <date>-<name>/     # results: per task, per model: workspace/, transcript.jsonl,
                     # result.json, workspace.diff, grade.txt, metrics.json
```

Each task directory contains:

- `PROMPT.md` — the exact prompt sent to the agent (byte-identical for both models)
- `fixture/` — files seeded into the agent's workspace
- `setup.sh` — optional post-copy mutation (e.g. planting CRLF line endings)
- `grade.sh` — hidden grader; the agent never sees it. Exit 0 = pass. Emits `SCORE: n/m`.
- `solution/` or `hidden_tests/` — grader assets, also hidden from the agent
- `check-grader.sh` — optional self-test proving the grader fails the raw fixture
  and passes a reference solution

## Running a bout

```
bin/run-bout.sh 2026-07-06-opus48-vs-fable5 claude-opus-4-8 claude-fable-5
# or a subset:
bin/run-bout.sh smoke claude-opus-4-8 claude-fable-5 02-synthesis
```

Requirements: `claude` CLI on PATH (authed), `python3`, `pytest`, `jq`, `make`, `git`.

Agents run with `--dangerously-skip-permissions` confined to throwaway workspaces
under `bouts/`. Prompts instruct them to stay in the working directory; workspaces
are fresh git repos so every change is diffable and attributable.

## What gets measured

- **Correctness** — each task's `grade.sh`, run against hidden tests/checkers
- **Cost & speed** — `total_cost_usd`, wall-clock, API duration from the result envelope
- **Effort shape** — turns, tool calls by type, output tokens, diff size
- **Ergonomics** — from transcripts: did it follow output contracts, over-ask,
  over-build, produce a readable final summary (human-scored rubric)

## Honest-reporting rules

Single runs are anecdotes, not benchmarks. Report Ns, publish raw numbers,
never extrapolate a task win into a general claim. If the harness author is one
of the models under test, disclose it.
