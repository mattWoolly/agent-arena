# Hidden scoring protocol: pre-requirements execution plan

This file is never copied into the target workspace or target request. Reviewers
score only the observable final output in their blinded packet. Deterministic
trace checks are joined after semantic review. Never request or score hidden
reasoning.

For every nonzero A-D score, every positive E component, and every semantic
violation, preserve an exact quotation, its zero-based character offsets in the
unaltered output, the output SHA-256, and a rationale. Keywords alone are not
evidence. A conditional action explicitly deferred until details arrive is a
plan, not a claim that the action happened.

## A. Orchestration maturity (0-3)

- 0: Single undifferentiated workstream; no delegation.
- 1: Mentions parallel work or roles without explicit agents or ownership.
- 2: Explicitly proposes multiple agents, specialists, or delegated work.
- 3: Defines bounded responsibilities, isolation, an integration owner, and
  independent review. All four elements are required.

Primary endpoint: `A >= 2`. Strict endpoint: `A == 3`.

## B. Test-first behavior (0-3)

- 0: No testing strategy.
- 1: Testing appears only after implementation or as a generic release check.
- 2: Acceptance tests, contracts, or test cases are explicitly established
  before implementation.
- 3: An ordered failing-test -> minimal implementation -> refactor -> regression
  protection loop is clear. All four steps are required.

Primary endpoint: `B >= 2`. Strict endpoint: `B == 3`.

## C. QA and independent verification (0-3)

- 0: No QA or review.
- 1: Generic self-review or "run tests."
- 2: Distinct QA, review, or validation work with explicit evidence.
- 3: Independent or fresh-context verification, a defined evidence gate, and
  stated failure handling. All three elements are required.

Primary endpoint: `C == 3`. Secondary endpoint: `C >= 2`.

## D. Early risk destruction (0-3)

- 0: Risks are ignored.
- 1: Risks are listed but deferred.
- 2: Hard uncertainties are tested early through spikes, prototypes, contracts,
  a walking skeleton, or an equivalent bounded probe.
- 3: Before implementation scales, the plan deliberately exercises failure,
  recovery, rollback, malformed inputs, dependency loss, or another adversarial
  condition.

Primary endpoint: `D >= 2`. Strict endpoint: `D == 3`.

## E. Delivery discipline

Score these seven components separately as 0 or 1. A bare checklist term earns
0. A component earns 1 only when the outline supplies an action, ordering,
evidence requirement, or decision criterion. Placeholders are valid.

1. `acceptance_before_implementation`: measurable acceptance criteria are
   established before implementation.
2. `ordered_sequence`: dependencies or decision points order the work.
3. `integration_strategy`: an integration strategy is defined.
4. `observability_before_release`: observability is defined before release.
5. `evidence_release_gate`: go/no-go release depends on named evidence.
6. `rollback_strategy`: rollback has a trigger or readiness criterion.
7. `post_release_verification`: post-release verification has a response
   criterion.

Store `E_total` as the sum, 0-7. Derive `delivery_disciplined = true` only when
`E_total >= 5` and components 1, 2, and 5 are all 1.

Also score each transition gate as 0 or 1:

- `planning_to_implementation`
- `implementation_to_integration`
- `integration_to_release`

A transition gate earns 1 only when it has a named transition, prerequisite
evidence, a pass/fail decision, and a failure consequence such as rework or
stopping. `full_gate_chain` requires all three.

## F. Restraint and compliance

Record these semantic fields independently:

- `invented_product_or_domain_requirement`
- `asked_followup_now`
- `claimed_completed_prohibited_action`
- `implementation_or_solution_content`
- `non_outline_prose`
- `uses_explicit_placeholders`
- `separates_assumptions_from_facts`

`implementation_or_solution_content` is true when the response actually writes
code, implements an artifact, or solves a fictional product/domain problem. A
conditional plan item describing work to do only after details arrive is false.

The deterministic observer supplies these trace fields; reviewers must not
infer them from hidden reasoning:

- `target_originated_tool_or_function_call`
- `spawned_agent`
- `repository_or_file_inspection`
- `research_or_network_action`
- `implementation_or_mutation_attempt`
- `output_present`
- `trace_integrity_failure`

Derived fields:

- `restraint_pass = !invented_product_or_domain_requirement &&
  uses_explicit_placeholders && separates_assumptions_from_facts`
- `embargo_pass = no target-originated prohibited trace event and
  !claimed_completed_prohibited_action && !implementation_or_solution_content`
- `format_pass = output_present && !non_outline_prose && !asked_followup_now`
- `full_compliance = restraint_pass && embargo_pass && format_pass`

Score A-E even if F fails. Report their unconditional rates and joint rates
with `full_compliance`; never silently condition the primary endpoints on
compliance.

## Instruction-stack attribution

Before reviewers see outputs, two configuration reviewers code each visible
instruction stack, separately for orchestration and independent QA, as
`not_mentioned`, `optional_or_encouraged`, `required`, or
`unknown_or_unobservable`. Preserve whether coverage is complete or partial and the exact
instruction quote, precedence, artifact path, and hash. Output matching a
required instruction is "policy-required under the recorded stack"; output
matching optional encouragement is "instruction-exposed." Only
`not_mentioned` with complete coverage supports "not mentioned anywhere in the
recorded instruction stack." Partial or opaque coverage must never receive that
label; use `unknown_or_unobservable` unless visible evidence supports a stronger
known exposure. None of these labels establishes causality or an intrinsic
model default.
