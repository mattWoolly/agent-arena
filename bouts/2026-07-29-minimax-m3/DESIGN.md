# Bout design: 2026-07-29-minimax-m3 (pre-registered)

This file is committed and pushed **before** the first graded run.
Hypotheses below are fixed; any deviation is recorded in ANALYSIS.md, not
edited here.

## Question

MiniMax M3 (released 2026-06-01) is the third Chinese open-weight flagship
to reach this battery, after Kimi K3 and GLM-5.2, and the third installment
in the effort-control arc with a twist: Opus 5 exposes a five-level effort
dial (our bout: it moved the bill 2.2x, not the grades), Kimi K3 exposes a
three-level dial (our bout: it moved the thinking 12.1x, not the bill), and
M3 exposes no dial at all, only a switch: thinking `adaptive` (default) or
`disabled`. The vendor's launch blog states the two modes "share the same
pricing" and pitches frontier coding (SWE-Bench Pro 59.0%, Terminal-Bench
2.1 66.0%, self-reported, no technical report at launch) at a $0.30/$1.20
sticker, 4.7x below GLM-5.2's, which holds our series' cheapest-clean-pass
record ($0.86). Nobody has published what the switch does to a real agentic
workload. We measure it, through MiniMax's own documented Claude Code
integration (their Anthropic-compatible endpoint).

Two integration claims ride along, both wire-verifiable:

1. A GitHub issue on MiniMax's own repo reports the `/anthropic` endpoint
   advertising a 200K context instead of M3's headline 1M, causing early
   compaction in Claude Code. We record what the endpoint actually
   advertises under the plain `MiniMax-M3` model id.
2. Secondary sources disagree on M3's cache-read price ($0.06 vs $0.12).
   The primary pricing doc (fetched 2026-07-29) resolves it: $0.06 standard
   tier, $0.12 is the >512K long-context tier. prices.json pins the
   standard tier; battery tasks never approach 512K.

## Grid

- 6 base tasks: 01-bugfix, 02-synthesis, 03-refactor, 04-terminal,
  05-review, 06-instructions.
- 2 arms, both `claude -p` (Claude Code) against
  `https://api.minimax.io/anthropic`, model slots pinned to `MiniMax-M3`:
  - `minimax-m3`: stock harness behavior (M3 default = adaptive thinking).
  - `minimax-m3-nothink`: thinking suppressed via `MAX_THINKING_TOKENS=0`.
- r3 per cell, serial mode (`-s`): execution time is a claim.
- Total: 36 graded runs.

## Arm-mechanism pinning (at smoke, before any graded run)

Direct-API probes (scripted in `probes/`, run before the grid) establish
that the endpoint honors the Anthropic `thinking` parameter: default
requests returned no thinking block on a short prompt; an explicit
`{"type":"disabled"}` is accepted; `{"type":"enabled","budget_tokens":N}`
returns thinking blocks. The smoke cell for each arm is inspected at the
wire (thinking blocks present/absent in transcript.jsonl, output token
counts) before the grid starts. If `MAX_THINKING_TOKENS=0` fails to
suppress thinking through Claude Code, the fallback is the strongest
suppression the harness offers, and the substitution is recorded in
ANALYSIS.md. Lesson from the K3 bout applies: never trust a requested
setting until it is proven at the wire.

## Hypotheses (falsifiable, priors cited)

- **H1 (saturation holds):** each arm passes >= 17/18 runs. Prior: the
  battery is saturated for frontier-class models (K3 54/54, GLM-5.2 24/24,
  Opus 5 84/84).
- **H2 (cheapest-pass record):** the `minimax-m3` arm's mean metered cost
  per 6-task pass comes in under GLM-5.2's $0.86 record. Predicted ~$0.25
  if M3's token profile resembles GLM's (sticker is 4.7x lower).
- **H3 (the switch is connected):** the adaptive arm emits thinking blocks
  on >= 4 of 6 tasks; the nothink arm emits zero thinking blocks in all 18
  runs. This is the wire-connectivity proof, per-run, not per-probe.
- **H4 (bill insensitivity):** per-pass cost ratio adaptive/nothink < 1.3x.
  Prior: K3's dial moved thinking 12.1x but the bill only 1.4x because the
  agentic bill is cache-read context traffic; the vendor claims the modes
  share pricing, and thinking tokens bill as output either way.
- **H5 (grade insensitivity):** arms differ by at most 1 graded run out of
  18. Prior: grades were effort-flat in both previous installments.
- **H6 (thinking costs minutes):** adaptive arm mean execution time per
  pass >= 1.3x the nothink arm. Prior: K3 at max ran 1.9x the execution
  time of low for the same grades.
- **H7 (judge can't see the switch):** blind Opus 4.8 judge on the rubric
  tasks (05-review, 06-instructions), same protocol as the K3 bout:
  per-arm totals within 3 points of each other out of 36. Prior: judge
  depth was effort-insensitive at this power in both prior installments.
- **H8 (context advertisement):** under the plain `MiniMax-M3` id, the
  integration surfaces a 200K-class context in Claude Code, not the
  headline 1M (the vendor's own docs work around this by pinning
  `MiniMax-M3[1m]` and a 1M auto-compact window). Verified from the
  harness's view of the model during smoke; the workaround config is
  probed but not used for graded runs (comparability with prior bouts).

## Budget

Estimated: grid < $3 (36 runs at a sticker 4.7x below GLM's $0.86/pass),
probes + smoke < $1, judge pass ~ $1.50 (Opus 4.8, unmetered `claude -p`,
estimated by the K3-bout convention). Bout cap $15; if spend approaches the
cap the grid stops at a complete replicate boundary and the truncation is
disclosed.

## Disclosures (standing, from the arena README)

Claude Code is Anthropic's harness: for MiniMax this is an away game, and
harness effects have a sign per pairing. The judge is Opus 4.8, an
Anthropic model. Fable co-authors the harness and the articles. M3's
benchmark claims are self-reported with no technical report at launch;
nothing here verifies or refutes them beyond this battery. Vendor peak
windows: MiniMax is Beijing-based; runs are scheduled outside 12:00-18:00
Beijing by the same courtesy convention used for Moonshot.
