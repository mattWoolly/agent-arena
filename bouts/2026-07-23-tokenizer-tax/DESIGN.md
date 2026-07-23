# Bout design: 2026-07-23-tokenizer-tax (pre-registered)

This file is committed and pushed **before** the first measurement run.
Hypotheses below are fixed; any deviation is recorded in ANALYSIS.md, not
edited here.

## Question

Sonnet 5 ships a new tokenizer. Anthropic's docs say it produces
"approximately 30% more tokens" for the same text (range roughly 1.0-1.35x);
Simon Willison measured static text at English 1.42x, Spanish 1.33x, Python
1.27x, Mandarin 1.01x (2026-06-30, his token-counter tool, UDHR +
sqlite_utils/db.py). Blog-tier analyses extrapolate to "50-80% more expensive
in production," resting on an assumed 3-3.4x adaptive-thinking output
multiplier with no published methodology.

Every number in that discourse is static text. Nobody has measured what the
tokenizer change does to a real agentic workload, where the bill is dominated
by context re-reads (our 30 public Sonnet 5 runs: mean ~297K cache-read
tokens per run vs ~4.4K output tokens) and the content is a blend of code,
terminal output, diffs, JSON tool calls, and prose. We measure it.

## Data

- **Part A (reanalysis, no new agent runs):** the 30 Sonnet 5 runs from the
  public `2026-07-07-ladder-noise` bout (5 repeats x 6 tasks, all committed
  to this repo with full transcripts, workspaces, and diffs).
- **Part B (method validation):** Willison's inputs, refetched from public
  sources: the UDHR English text and `sqlite_utils/db.py` from the
  sqlite-utils GitHub repo.
- **Part C (live anchor):** a new Sonnet 4.6 arm on the same battery.

## Method

**Part A.** Extract content by category from the Sonnet 5 run artifacts:

1. `task-prompts`: `tasks/*/PROMPT.md` (6 files)
2. `assistant-prose`: assistant text blocks from the 30 transcripts
3. `tool-input-code`: Edit/Write tool inputs (code payloads)
4. `tool-results`: tool_result content (terminal output, file reads)
5. `workspace-code`: source files in each task's run-1 workspace
6. `diffs`: `workspace.diff` per run

Count each category's concatenated text with
`POST /v1/messages/count_tokens` under `claude-sonnet-4-6` and
`claude-sonnet-5` (identical bytes to both; the endpoint is model-specific
and does not bill tokens). Report the per-category ratio and a per-run
blended ratio: for each run, concatenate that run's observed conversation
content (task prompt + assistant text + tool inputs + tool results) and
count it whole; the blend is the mean across the 30 runs.

**Known gap, disclosed:** transcripts do not include the Claude Code system
prompt or tool schemas, so the fixed harness prefix (roughly 30K tokens per
the first request's cache-creation + cache-read usage) is not directly
measurable. Counterfactual bills therefore carry a sensitivity range: the
unobserved prefix share is scaled by the observed min and max category
ratios rather than a point estimate.

**Counterfactual bills.** Reconstruct each run's full billed ledger (input,
output, cache write, cache read per request) from transcript usage records.
Compute three bills per full 6-task pass:
- measured: Sonnet 5 at intro pricing ($2/$10 per MTok, ends 2026-08-31)
- Sept 1: same token ledger at list ($3/$15)
- counterfactual 4.6: token ledger deflated by the blended ratio (with the
  sensitivity range above), priced at Sonnet 4.6 list ($3/$15)

**Part B.** Reproduce Willison's two headline numbers with our counting
path to validate the method before trusting Part A.

**Part C.** `bin/run-bout.sh -r 2 -s 2026-07-23-tokenizer-tax
claude-sonnet-4-6` (all 6 tasks, 2 repeats, serial, same hermetic config as
the ladder bout: mktemp workspaces, --setting-sources project, effort
xhigh pinned, run_env.json recorded, peek check on every transcript).
This yields a real 4.6 bill and pass rate, and an empirical read on the
verbosity assumption behind the "50-80%" claims. The 4.6 arm is 4.6's own
work, not a tokenizer isolate; it anchors the counterfactual but does not
replace it, and the writeup keeps the two separate.

## Hypotheses (falsifiable, fixed before any counting)

- **H1:** The blended inflation ratio on observed per-run conversation
  content lands in [1.25, 1.38]; below the 1.42 English headline because
  agent content is code- and terminal-heavy.
- **H2:** Tool-result content (terminal output) inflates less than
  assistant prose: ratio(tool-results) < ratio(assistant-prose).
- **H3:** Intro-priced Sonnet 5 is cheaper than the Sonnet 4.6
  counterfactual at list prices for the same runs (requires blend < 1.5).
- **H4:** At Sept 1 list pricing, the effective increase vs the 4.6
  counterfactual for this workload is between +25% and +40%; below both the
  42% English headline and the 50-80% production claim.
- **H5:** Method validation reproduces Willison within tolerance: UDHR
  English ratio 1.42 +/- 0.03; sqlite_utils db.py ratio 1.27 +/- 0.03.
- **H6:** Sonnet 4.6 passes at least 11/12 live runs, and Sonnet 5's mean
  output tokens per task from the ladder bout are less than 2x Sonnet 4.6's
  measured mean on the same tasks (testing the assumed 3-3.4x multiplier).

## Budget

Part A and B: no model spend (count_tokens does not bill tokens; rate
limits respected with throttling). Part C: 12 Sonnet 4.6 runs at list
pricing, estimated $2.50-$6.00 based on Sonnet 5's $0.216 mean per run.
Hard stop if Part C exceeds $10.

## Disclosures (standing, plus bout-specific)

- Claude Code is home field for Anthropic models; both arms run in it.
- No LLM judge in this bout: graders are the deterministic per-task
  scripts (check-graders.sh 12/12 before Part C).
- The harness author and analyst is Claude (Fable 5), an Anthropic model
  analyzing Anthropic pricing. Counting is done by Anthropic's own
  count_tokens endpoint, which is also the billing meter; this measures the
  tax as billed, not tokenizer internals.
- Sonnet 5 ladder runs were recorded 2026-07-07 on CLI 2.1.212; the 4.6 arm
  runs on today's CLI version (recorded in run_env.json). Harness drift
  between those dates is a disclosed confound for cross-arm behavior
  comparisons (H6), not for Part A, which re-tokenizes fixed artifacts.
- Willison's figures are treated as the reference for method validation
  only; his inputs are refetched, not vendored.
