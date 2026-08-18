# Results: incidental arithmetic (2026-08-17 bout)

90/90 runs completed and passed. Served-model integrity clean (90/90 matched
EXPECTED.json, no side-channel leaks, 0 peek flags). CLI 2.1.234, effort
`xhigh`, serial grid. Spend: ~$10.3 API (GLM + Kimi + Sol) + ~$9.7 notional
subscription-side (Opus + Sonnet, computed from transcript usage at list
prices as always) — under the $25 target.

**Amendment 1 (disclosed):** the first graded repeat exposed a sign bug in the
grader's own number parser — cells annotated like `1312.26 (T0057, travel)`
tripped the accounting-parentheses-negative heuristic and scored three
different models WRONG with identical `got=-1312.26`. Fixed at `6b7c6c0`
(fullmatch on a parenthesized bare number, 7-case regression check); **all 90
runs regraded from stored workspaces with the amended grader**, so every
number below is single-grader-version. The irony is on the record: the only
arithmetic-adjacent defect this bout found was in the evaluator.

## The headline

**1,140 numeric items — 570 per arm — zero wrong. All five models, all three
domains, both framings.** No currency slips, no carry errors, no
calendar-vs-business-day confusion, no off-by-ones down an 8-milestone
dependency chain crossing three holidays, no sign errors on negative growth.
Zero silent errors in 45 incidental runs.

## Hypothesis scorecard (design frozen at d782cfd)

| # | bet | verdict |
|---|---|---|
| H1 | incidental ≥2× explicit per-item error, ≥3/5 models | **FALSIFIED** — 0.0% vs 0.0% everywhere |
| H2 | ≥90% explicit runs tooled; ≤60% incidental | **HALF** — explicit 41/45 (91%) ✓; incidental 36/45 (80%) ✗ |
| H3 | head-derived items err ≥15%, tool-derived ≤5% | **FALSIFIED** — head-derived error 0%; see Sol below |
| H4 | ≥25% of incidental runs silently carry a wrong number | **FALSIFIED** — 0/45 |
| H5 | Sonnet 5 ≥2× Opus 5 error rate | **FALSIFIED** — both zero |
| H6 | date items worst domain | **FALSIFIED** — three-way tie at zero |
| H7 | ≤50% of 15-pair runs flag the planted discrepancy | **MISS (narrow)** — 18/30 (60%) pooled; the split is the finding (below) |
| H8 | 100% served-model integrity, 0 leaks | **HIT** |

1 hit, 1 half, 6 falsified. Per the pre-registration, the falsifications are
the yield: this is the pre-declared "harness is the mitigation" branch, now
with data. The 2026 practitioner claim — agents doing vibes-arithmetic on
numbers embedded in deliverables — did not reproduce at the frontier tier, at
`xhigh` effort, in an agentic harness with Python at hand. Frontier ≠
deployed tiers: cheap/fast modes and non-agentic surfaces are untested here
and remain the likely home of the complaint.

## What did discriminate

**1. Verification behavior — who notices the books don't balance.** The June
monthly's stated cost total disagrees with its own line items by €300.
Flag rates across both arms (never gated, purely emergent):

| model | flagged | note |
|---|---|---|
| claude-opus-5 | **6/6** | flagged in every run, both framings |
| glm-5.3 | **6/6** | same |
| kimi-k3 | 4/6 | inconsistent |
| claude-sonnet-5 | 2/6 | 0/3 incidental — its Notes quote June's cost figures three ways and never cross-check the stated total (manually audited; a real miss, not a detector artifact) |
| gpt-5.6-sol | **0/6** | used the stated total (467,640) in all three explicit runs; trusted every printed number, never summed a column |

On a battery where correctness is saturated, *whether a model audits its
inputs* is the grade separator — consistent with the series finding that
discrimination now lives in adversarial/verification behavior, not code or
arithmetic correctness.

**2. Tool style varies by model and domain — and the in-head work was
right.** Everyone tooled up on the 120-row CSV (30/30 runs). But Sol computed
the entire business-day chain in-head (0/3 incidental runs made a compute
call; only ~6% of its date values ever appeared in tool output) and scored
51/51. Kimi did all three incidental rollups in-head, 24/24. H3's mechanism —
head-computed means error-prone — is dead on this cohort: mental arithmetic
at the frontier, inside long reasoning, was flawless at these magnitudes
(3-addend 6-digit sums, holiday-aware date chains).

**3. Cost spread persists on identical perfect output** (per 6-task
pass-through): Kimi $0.54, Sonnet $1.19, GLM $1.36, Sol $1.54, Opus $2.03 —
a 3.8× price range for byte-equivalent correctness, echoing the 08-16 bout.

## Limitations (carried from DESIGN + one new)

- Frontier models, `xhigh`, one scaffold (Claude Code). The claim tested is
  about *agents in harnesses*; chat-tier and cheap-mode behavior is out of
  scope and likely where the folk claim lives.
- Labeled-table extraction makes the incidental arm less purely incidental
  than free prose (pre-declared trade-off).
- "Tool-derived" is a conservative lower bound (value present in tool
  output), so the H3 reading rests on the *error* side (0%), which is bound-
  free.
- New: magnitudes here top out at ~7 digits and 120 rows. AI-rithmetic-style
  length-degradation lives at longer operands; this bout says nothing about
  them. A follow-up dial: scale operand length/row count until p≈0.5.

## Follow-ups queued

1. **Effort/tier dial on the same battery** — the folk claim may live at
   `low`/default effort or on cheaper models (Haiku-tier); the battery and
   instruments now exist and cost ~$3.50/model-pass.
2. **The verification split as its own probe** — plant discrepancies of
   varying subtlety; the 6/6 vs 0/6 spread at €300 suggests a clean
   psychometric curve is available.
