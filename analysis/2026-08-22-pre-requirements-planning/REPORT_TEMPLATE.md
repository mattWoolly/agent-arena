# Confirmatory report template: pre-requirements planning behavior

This is a frozen template, not a result. The confirmatory runner remains gated
until explicit user approval. Populate it only through `analyze.py` after all
eligible confirmatory runs have two independent blinded reviews and every
disagreement has a recorded third-party adjudication.

## Scope statement

Report observable behavior under each exact recorded model, CLI, effort,
instruction-stack, and tool configuration. Do not call the result an intrinsic
model default. State the convenience-sample selection and all instruction-stack
exposures, especially any policy that requires or encourages orchestration or
independent QA.

## Run accounting

- Frozen manifest ID: `[freeze_id]`
- Planned primary slots: `20 per condition`
- Valid primary slots: `[x per condition]`
- Invalid attempts and objective reasons: `[append-only ledger references]`
- Preallocated replacements used: `[links from reserve slots]`
- Smoke runs included in confirmatory denominators: `0`
- Protocol amendments: `[none, or committed amendment identifiers]`

## Primary endpoints

For every condition, report `x/n`, the rate, and the two-sided 95% Wilson
interval for `A>=2`, `B>=2`, `C==3`, `D>=2`, the full three-transition gate
chain, restraint, embargo compliance, and full compliance. Also report the
strict endpoints and complete A-D distributions. Never describe 20/20 as proof
of universal behavior.

## Delivery discipline

Report all seven E component rates, the `E_total` distribution,
`delivery_disciplined`, and every transition gate. Do not substitute a generic
checklist count for the preregistered conjunctive definitions.

## Restraint and embargo

Report each semantic and deterministic F flag separately. Keep tool calls,
subagent spawning, refusals, empty target outputs, questions, invented details,
implementation/solution content, and non-outline prose in the behavioral
denominator unless a preregistered objective exclusion applies. Report any
security quarantine separately as safety-forced missingness.

## Instruction attribution

Join each condition to the instruction-exposure coding frozen before semantic
outputs were unblinded. Use `policy-required under the recorded stack`,
`instruction-exposed`, or `not mentioned anywhere in the recorded stack` as
applicable. Do not infer a policy effect without a randomized instruction
intervention.
Partial or opaque instruction coverage must be labeled
`unknown_or_unobservable` when no stronger visible exposure is established; it
cannot support a “not mentioned anywhere” claim.

## Review quality

Name or pseudonymize two distinct independent reviewers and the third
adjudicator. Report pre-adjudication exact agreement and linearly weighted
Cohen's kappa for A-D, plus exact agreement and unweighted kappa for binary E/F
flags and the separate blinding-integrity flag. Require reciprocal independence
declarations. Report `NA` when kappa is
undefined and preserve every original decision, exact quote, offset, output
hash, and adjudication in the machine-readable per-run provenance.

## Secondary outcomes

Report token use, elapsed time, and notional cost descriptively as median, IQR,
range, with the observed and unavailable count for each metric. Report
duplicate-output hashes, truncation, missing outputs, invalid
attempts, replacement counts, and every scorable-output sensitivity rate. If a
cross-driver structured refusal field does not exist, label refusal prevalence
not estimable rather than inferring it from prose. These are secondary and do
not rank agents.

Generate `analysis.json`, `REPORT.md`, and `ANALYSIS_MANIFEST.json` once with
no-clobber semantics. The bundle manifest must content-address every review,
adjudication, instruction-exposure input, blinded packet/map, and both generated
outputs, plus the execution ledger and every effective run record and artifact
manifest consumed by analysis.

## Limitations

At minimum discuss sample precision, convenience selection, instruction/harness
confounding, unavailable vendor-owned system or served-model details, version
drift handling, normal/default effort observability, and semantic-review limits.
Confirm that hidden reasoning was neither requested nor scored.
Disclose every adjudicated model/condition self-identification and its effect on
reviewer blinding, both per run and by condition.
