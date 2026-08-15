# The cost of a pass: GLM-5.3 against Opus 5, GPT-5.6 Sol, and Kimi K3

Pre-registered bout design. Committed and pushed **before any graded run**.
The battery is saturated — every frontier model scores ~100% — so this bout does
not ask *who passes*. It asks *what a pass costs*, and *how tight a budget each
model still passes under*. Grades are the control; efficiency is the signal.

## Why this shape

Across 644 archived runs the suite yields ~1 bit of grade signal: essentially
every (task, model) cell is a full pass. A straight re-run is a four-way tie.
Two things convert that saturation into a ranking without authoring new tasks
(and without the SciCode-Verified failure mode of shipping hard-but-defective
tasks):

1. **Cost of a pass.** When everyone passes, cost is cleanly comparable — no
   confound from differing pass rates. Tokens, turns, tool-calls, wall, dollars.
2. **The turn-budget frontier.** Models finish in 5–17 turns against a budget of
   60 (3–10× slack). Squeezing `ARENA_MAX_TURNS` until pass-rate falls gives a
   graded per-model curve that never saturates — the local analogue of METR's
   time-horizon, with turns as the budget axis. The discriminating number is the
   **minimum budget at which pass-rate ≥ 0.5** (Fisher information peaks at
   p=0.5; this targets it directly rather than maximising difficulty, which is
   catastrophic for ranking fidelity — Spearman 0.638 for hardest-only selection).

## Contestants (all four verified live 2026-08-16)

| label | endpoint | notes |
|---|---|---|
| `claude-opus-5` | api.anthropic.com (subscription OAuth) | **run with `ANTHROPIC_API_KEY` unset** — the pay-go key in `~/.secrets` is dry and shadows the working subscription |
| `glm-5.3` | Z.ai Anthropic-compatible (`env/glm-5.3.env`) | coding plan; requires a `thinking` block; **see routing hazard below** |
| `kimi-k3` | Moonshot Anthropic-compatible | as in prior bouts |
| `gpt-5.6-sol` | LiteLLM translation proxy → OpenAI | disclose the translation layer; tool-calling not attributable to the model alone |

Harness held constant: **Claude Code**, all four, so the comparison is
model-to-model at one scaffold. (A harness-axis arm — Sol under Codex, Kimi
under Kimi Code — is explicitly out of scope here; those drivers need the
served-model guard ported to `metrics_codex.py` / `metrics_kimi.py` first.)

`claude-fable-5` is deliberately excluded: it costs above Opus-tier and the
question is where GLM-5.3 lands among the models a cost-conscious buyer would
actually weigh.

## The GLM-5.2 baseline is frozen, not re-runnable

Our published GLM-5.2 note reports **$0.86/pass, 1153s, blind judge 60/72** on
this battery (bout `2026-07-20-glm52`, CLI 2.1.214). We **cannot re-run 5.2**:
the same endpoint now silently serves 5.3 for a 5.2 request (verified 2026-08-15;
`analysis/2026-08-15-glm53-routing/`). So the 5.2→5.3 generational delta is
reported as **suggestive, across a CLI-version boundary** (2.1.214 → the bout's
version), never as a controlled A/B. The rigorous comparison is the clean
four-way at one CLI version. This limitation is itself a finding and will be
disclosed in print.

## Served-model integrity (the load-bearing guard)

Because an endpoint can silently substitute a model version, **every run records
the model that actually served it**, read from response tags in the transcript
(`bin/served_model.py`, tested). `bouts/.../EXPECTED.json` declares the required
served id per label; `summarize.py` refuses to call the bout a valid comparison
unless every run matches, and flags any run served by >1 model (a side-channel
leak). A `⛔ SERVED-MODEL INTEGRITY FAILURES` block in `results.md` is a
hard stop. Tests: `bin/test_served_model.py` (9), `bin/test_summarize_integrity.py` (3).

## Fixed vs varied

| | |
|---|---|
| **Fixed** | prompt (byte-identical), harness (Claude Code), effort (`xhigh`), grader (hardened per PR #27), timeout (1500s), setting-sources (`project`) |
| **Varied (primary)** | model |
| **Varied (frontier arm)** | `ARENA_MAX_TURNS` ∈ {60, 16, 12, 8, 6, 4} |

## Task set

**Core (9 graded, binary-clean):** 01-bugfix, 02-synthesis, 03-refactor,
04-terminal, 07-injection, 07-injection-subtle, 08-evaluator, 08-evaluator-hard,
09-converge. Excluded: 05-review / 06-instructions (prose/IFEval, not clean
binary at frontier), the two transplant variants (a separate question).

**Frontier subset (3):** 01-bugfix, 04-terminal, 08-evaluator-hard — the tasks
with the most turn headroom and the cleanest hidden-test grading.

> ⚠ **Known pre-existing defect, disclosed, not silently patched here:**
> `01-bugfix`'s hidden tests pass on the unfixed fixture (they cover none of the
> planted bugs). Its *hidden-test* point is therefore non-discriminating. It is
> retained because its *visible-test* and *tests-untouched* points are valid and
> its turn-cost is a legitimate efficiency measurement. It will carry a footnote
> and is tracked for a hidden-test rewrite; it is not part of any grade claim.

## Metrics (per run, from the hardened `metrics.py`)

`grade_pass`, `served_model(s)`, `served_model_leak`, `num_turns`,
`tool_calls_total`, input/output/cache-read tokens, `total_cost_usd` (+source),
`wall_seconds`. Aggregated by `summarize.py` as mean ±sd across repeats, plus
per-model per-pass-through totals.

## Pre-registered hypotheses (hit/miss scored after; misses reported first)

- **H1 — GLM-5.3 remains the cheapest per pass.** GLM-5.2 was the cheapest clean
  pass in the whole series ($0.86). 5.3 stays cheapest of the four on $/pass.
  *Falsified if any of Opus 5 / Sol / Kimi K3 is cheaper.*
- **H2 — cost rank ≠ turn rank.** The cheapest-dollar model is **not** the
  fewest-turns model; dollar cost is dominated by per-token price and cache
  behaviour, not step count. *Falsified if the $/pass and turns rankings agree.*
- **H3 — the frontier discriminates where grades don't.** At `ARENA_MAX_TURNS`
  the four models' pass-rate-≥0.5 budgets span **≥ 2 budget steps** (e.g. one
  model still passes at 6 turns where another needs 12), while all four score
  full at budget 60. *Falsified if the convergence budgets are within one step.*
- **H4 — thinking-always-on shows up as output-token volume.** GLM-5.3 (thinking
  non-optional) and Opus 5 sit above Sol on output tokens per pass at equal
  grades. *Falsified if GLM-5.3 is not in the top half on output tokens.*
- **H5 — the 5.2→5.3 dollar delta is within ±40%** of the published $0.86,
  reported with the CLI-version caveat. *Falsified outside that band.*
- **H6 — served-model integrity holds.** Every graded run is served by exactly
  its declared model; zero substitutions, zero leaks. *Falsified by any
  integrity failure — and if it fails, that becomes the story, not a footnote.*

## Execution, gated

1. **SMOKE (gate, ~$5, r=1, 1 task × 4 models = 4 runs).** Proves: all four
   endpoints answer under Claude Code; the served-model guard reports the right
   id for each (this is where a GLM surprise or an Opus-key-shadow would surface
   **before** spending on the grid); hardened graders run; cost/tokens populate.
   **Do not proceed to Phase 1 unless the smoke's `EXPECTED.json` check is clean.**
2. **PHASE 1 — cost of a pass (~$34).** 9 core tasks × 4 models × r=3 = 108 runs,
   budget 60, serial (`-s`) so wall-clock is publishable.
3. **PHASE 2 — turn-budget frontier (~$40–90).** 3-subset × 4 models × 5 budgets
   × r=3, serial. Tighter budgets fail fast and cheap.

Estimated total **~$80–130**. Budget target/cap to be set by the founder before
Phase 1; the smoke is the go/no-go. Moonshot off-peak (outside 12:00–18:00
Beijing) per prior bouts.

## Confounds disclosed up front

- **Translation proxy** for Sol: tool-calling behaviour through LiteLLM is not
  the model alone.
- **CLI-version boundary** on the 5.2 baseline (frozen, un-re-runnable).
- **Cache-pricing asymmetry** across vendors — handled by the proxy usage log /
  `prices.json`, cost source recorded per run.
- **Subscription vs API** for Opus 5: runs use the Claude subscription (must
  unset `ANTHROPIC_API_KEY`); cost is computed from transcript tokens at list
  prices, not from an invoice, so it is comparable to the metered models.
- **`grade_pass` is real** only because the graders were isolated first (PR #27);
  a pre-isolation run of this bout would have been spoofable.
