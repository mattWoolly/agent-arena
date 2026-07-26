# Opus 5 vs Opus 4.8: behavioral mechanism comparison

Corpora: opus5 core grid (24 runs, xhigh, CLI 2.1.214) vs opus 4.8 kimi-bout
grid (24 runs, xhigh, CLI 2.1.212) with the same-window 4.8 anchors (9 runs,
CLI 2.1.214) as the drift control. mech-compare.py/json are the fan-out
agent's originals; bin/behavior.py is the productionized permanent tool.

## Findings (drift-controlled)

- Tempo: opus5 12.33 tool calls/run vs 4.8's 7.67 (anchors 8.22); Bash
  nearly doubled; holds on all 8 tasks individually. Thinking blocks/run up
  (5.67 vs 3.96) but thinking per tool call DOWN (0.46 vs 0.52): it acts
  more per unit of thought.
- First move: opus5 opens with Bash 21/24 (ls orientation 15/24); 4.8
  splits Bash/Read roughly evenly.
- Verification: definition-sensitive, so three definitions were run.
  (a) strict "last tool call is a test": near-floor for both, fragile.
  (b) "check within final 3 calls, of runs that test": 4.8 1.00, opus5
  0.846 — conditional on testing, BOTH finish with verification.
  (c) breadth: opus5 invokes checks in 13/24 runs vs 4.8's 9/24, and is
  the only model in the arena to AUTHOR its own verification scripts where
  no test harness exists (3 events: 02-synthesis runs 1-2 wrote _check.py;
  run-2 additionally built an independent reference implementation of
  luhn_valid to cross-check, then removed its scaffolding and verified
  workspace cleanliness with git status). 4.8: zero such events anywhere.
  The claim that survives all three definitions: opus5 verifies more
  broadly and invents verification; when 4.8 tests, it also finishes with
  tests.
- Discounted as CLI/window-noisy (the two 4.8 corpora disagree with each
  other): mean Bash command length, errors/run, first-test position.
- Re-reads: near-floor for both Anthropic models (opus5 3, 4.8 0); does
  not discriminate here (contrast: Sol-in-Claude-Code re-read in 24/24).

Maps to Anthropic's launch claims: "much stronger at verifying its work"
validates in the breadth+authorship sense with receipts; "thoughtful and
proactive" is supported by the self-authored checks; effort-dial claims
were covered by the 2026-07-25 bout.
