# Bout analysis: Opus 4.8 vs Fable 5 — 2026-07-06

Single run per task per model (N=1 per cell). Every number below was read from the
raw artifacts in this directory (results.json, grade.txt, metrics.json, transcripts)
and the grades were re-verified by hand where noted.

## Headline

Both models passed all six tasks with full scores (12/12 runs, every grader at
maximum points). The differentiators were speed and cost, not correctness:

| Metric (totals across 6 tasks) | claude-opus-4-8 | claude-fable-5 |
|---|---|---|
| Tasks passed | 6/6 | 6/6 |
| Wall clock | 291 s | 434 s |
| API cost | $1.59 | $3.45 |
| Turns | 56 | 63 |
| Output tokens | 18,083 | 20,812 |
| Permission denials | 0 | 0 |
| Output-contract violations | 0 | 0 |

- Opus 4.8 was faster on every single task (range: 28–76 s vs 45–97 s).
- Cost ratio 2.17× ≈ the 2× list-price gap (Fable $10/$50 per MTok vs Opus $5/$25,
  per the Anthropic model reference, checked 2026-07-06) plus Fable's ~15% higher
  output-token count.

## Hand-verification performed

- 01-bugfix: hidden test suites re-run; both diffs are minimal correct fixes
  (get() recency + put() update-eviction), 16 insertions each; tests/ untouched.
- 04-terminal: `make test` re-run by hand in both workspaces — exit 0. Both found
  all four planted faults (Makefile spaces-not-tab, CRLF, exec bit, JSON trailing
  comma) and neither bypassed a check.
- 05-review: both models found all 6 planted defects with 0 false positives
  (verified against plants.json and by reading findings.md).
- 06-instructions: both summary.json files byte-equivalent and matching the
  grader's independently computed ground truth from the CSV.

## Ergonomics notes (from transcripts and final messages)

- Both followed every output contract exactly (findings.md line format 6/6 parsed,
  SOLUTION.md present, no git commits, no files outside the workspace).
- Diff sizes near-identical — no overengineering on either side.
- Final summaries: Opus terser (e.g. 397 vs 632 chars on bugfix), Fable's extra
  length carried real content, not padding — examples:
  - Review finding #4 (Fable): connected the swallowed exception to the shared
    `seen=[]` list — failed users are marked seen and never retried. Opus reported
    both defects separately but not the interaction.
  - 06 report (Fable): quantified "West trailing North by 35%" in a recommendation.
  - Fable cited precise locations (Makefile:4, cache.py:30-34) unprompted.
- Neither model asked questions or stalled; zero retries needed.

## Honest caveats

- N=1 per cell: an anecdote with instrumentation, not a benchmark.
- Tasks were sized to finish in minutes; none exercised the long-horizon,
  large-context work where the bigger model's advantages are claimed to show.
- The harness author and analyst is Fable 5 (this analysis was produced by the
  model being tested). Graders are deterministic scripts to limit that bias.
- Both runs shared the same machine/account; no load isolation beyond that.
