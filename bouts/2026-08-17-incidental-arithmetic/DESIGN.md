# Incidental arithmetic: do agents ship wrong numbers when the numbers aren't the task?

Pre-registered bout design. Committed and pushed **before any graded run**.

## The question

The 2026 literature splits on agent arithmetic. Practitioners report agents
doing vibes-arithmetic on numbers embedded in larger deliverables (running
totals, percentages, date offsets) while academic work on tool use reports the
opposite failure — indiscriminate over-calling of tools. Nobody has isolated
the variable both camps skip: whether the computation is **the stated task** or
**incidental to it**. Finance-agent benchmarks (BlueFin's ~30-point gap between
formula correctness and output validation) name silent numeric errors as a
failure class but don't measure when they happen. This bout measures exactly
that split, on one battery, at one scaffold.

Three questions, in order of importance:

1. **Incidental vs explicit.** Same data, same computations, same tolerances —
   one arm frames them as a report to write, the other as values to compute.
   Does per-item accuracy move?
2. **The tool split.** With Bash and Python freely available in both arms, do
   agents compute mechanically or in-head, and does that choice track the
   framing?
3. **Silent errors.** In the incidental arm the task-level grade deliberately
   gates on document structure only, the way the wild does. How many runs
   "pass" while carrying a wrong number?

## Design: three matched task pairs

| pair | domain | numeric items | the in-head temptation |
|---|---|---|---|
| `13-ledger` / `-explicit` | 120-row expense CSV, 3 currencies, budgets | 13 | multi-row sums, conversion, percentages |
| `14-schedule` / `-explicit` | business-day chain, 8 milestones, 3 holidays | 17 | calendar arithmetic, error compounding down the chain |
| `15-rollup` / `-explicit` | 3 monthly reports → quarterly rollup | 8 (+1 FLAG) | 3-addend 6-digit sums — the classic carried-numbers regime |

Item IDs are 1:1 across the arms of a pair; conventions (rounding, bases,
inclusive-day rules) are pinned verbatim in both prompts. Neither prompt
mentions tools — that silence is the manipulation. 38 numeric items per
incidental pass-through; ×3 repeats = 114 scored items per model per arm.

**Grading policy (per `tasks/_lib/numgrade.py`):**
- Every quantity is an individual ITEM (many bits per run, not one).
- Defensible alternative readings are accepted as canonical values (rounding
  per-transaction vs at the end; June's stated cost total vs its own line
  items). Interpretation is not arithmetic error.
- WRONG items get a mechanical error class: `no-conversion`, `calendar-days`,
  `holidays-ignored`, `off-by-one`, `sign-error`, `near-slip` (≤2% relative),
  `gross`.
- Incidental arm: exit status gates on structure/coverage/internal-consistency
  only → silent numeric errors stay observable. Explicit arm: gates on every
  item.
- `14-*` also emits CHAIN lines (local consistency against the model's own
  previous milestone): one early slip propagated cleanly is a different
  failure from eight independent slips.
- `15-*` plants a EUR 300 stated-vs-line-items discrepancy in the June report;
  flagging it is reported (FLAG line), never gated, and both cost bases are
  accepted for every derived item.

**Validation done before this freeze (zero-spend):** A/B/C/D triad green on
all six tasks (`validate-task.sh`); `check-graders.sh` 24/24; reference
solutions are independent implementations and score full NUMERIC on all three
incidental graders (three-way agreement: generator, grader lib, solutions);
planted-error probes confirmed detection + classes (`gross`, `near-slip`,
`sign-error`, `holidays-ignored` 13/13 tagged, dual-basis acceptance);
`numcheck.py` verified on a synthetic run.

## Contestants

| label | route | note |
|---|---|---|
| `claude-opus-5` | subscription OAuth | run with `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` unset (dry pay-go key shadows the subscription) |
| `claude-sonnet-5` | subscription OAuth | the within-vendor tier axis; served id to be confirmed at smoke |
| `glm-5.3` | Z.ai Anthropic-compatible | `env/glm-5.3.env`; thinking block |
| `kimi-k3` | Moonshot Anthropic-compatible | prior-bout config |
| `gpt-5.6-sol` | LiteLLM translation proxy | disclose the translation layer as always |

Harness constant: **Claude Code** for all five. `claude-fable-5` excluded
(above-Opus tier, and Fable co-authors this series). Served-model integrity
enforced via `EXPECTED.json` + `summarize.py` hard-stop, as in the 08-16 bout.

## Fixed vs varied

| | |
|---|---|
| **Fixed** | prompts (byte-identical per task), harness, effort `xhigh`, `ARENA_MAX_TURNS` 60, timeout 1500s, setting-sources `project`, graders (this commit) |
| **Varied (primary)** | model × arm (incidental / explicit) |

**Grid:** 6 tasks × 5 models × r=3, serial (`run-bout.sh -r 3 -s`) = **90 runs**.
Smoke first: 1 run each of `13-ledger` + `13-ledger-explicit` on
`claude-sonnet-5`, checked end-to-end (served id, grade.txt ITEM lines,
numcheck join) before the grid fires.

## Metrics

Per (task, model): per-item error rate; tool-derivation rate; per-run
compute-tool invocation; silent-error rate (grade_exit==0 ∧ ≥1 wrong item);
error-class distribution; CHAIN consistency; FLAG rate; plus the standard
cost/turns/tokens/wall via `metrics.py`/`summarize.py`.

**Attribution caveat (pre-declared):** `numcheck.py`'s "tool-derived" means
the expected value appeared in some tool RESULT during the run — a
conservative lower bound on mechanical computation, not exact attribution.
Values seen only in the final artifact count as head-derived.

## Hypotheses (frozen)

- **H1 (core):** pooled per-item error rate in the incidental arm is ≥2× the
  explicit arm AND ≥5 points higher, in ≥3 of 5 models.
- **H2 (tool split):** ≥90% of explicit runs make ≥1 compute-tool call; ≤60%
  of incidental runs do (pooled).
- **H3 (mechanism):** within incidental runs, tool-derived items err ≤5%,
  head-derived items ≥15% (pooled).
- **H4 (silent errors):** ≥25% of incidental runs pass their gates while
  carrying ≥1 wrong numeric item (pooled).
- **H5 (tier):** Sonnet 5's pooled numeric error rate ≥2× Opus 5's.
- **H6 (category):** date items (14-pair) have the highest incidental-arm
  error rate of the three domains.
- **H7 (verification behavior):** ≤50% of 15-pair runs flag the planted June
  discrepancy.
- **H8 (integrity):** 100% of runs served by the declared model; 0 leaks.

A clean null on H1/H2 — frontier coding agents tooling up regardless of
framing — is a publishable finding against the practitioner narrative: the
agentic harness itself as the mitigation. That reading is licensed only
because the arms are matched.

## Threats to validity (pre-declared)

1. Requiring labeled tables in the incidental deliverables (for deterministic
   extraction) makes them less purely incidental than free prose. Chosen
   deliberately: prose extraction would put grader judgment inside the
   measurement. The framing manipulation survives in the task's stated
   purpose.
2. Tolerances forgive last-digit rounding variance by design (±0.02 dual-basis
   money, ±0.15 on 1-dp percentages); measured error rates are lower bounds.
3. Effort pinned at `xhigh` — the arms are compared fairly, but absolute rates
   may not transfer to cheaper effort settings. A follow-up dial arm is out of
   scope here.
4. One scaffold (Claude Code). Harness-axis replication is future work.
5. r=3 gives 114 items/model/arm — adequate for the pooled hypotheses, thin
   for per-task-per-model cells; those are reported descriptively only.

## Budget

Target ≤$25 API spend, hard cap $50 (bout convention). Anthropic models ride
the subscription (cost still computed from transcript usage at list prices,
`cost_source` recorded, as established in the cache-economics analysis).
Estimated API dollars: GLM + Kimi + Sol ≈ 54 paid runs of small-read/
small-write tasks ≈ $10–20.

## Analysis plan

`summarize.py` (grades/cost/integrity) + `numcheck.py --json` (items/tools/
silent errors), then per-hypothesis scoring in ANALYSIS.md. H1 compared
per-model on matched item sets; binomial CIs on pooled rates; no NHST theater
beyond that. All misses reported. Iterate-on-findings discipline applies: a
flat result triggers a claims-driven redesign note, not a shelved bout.
