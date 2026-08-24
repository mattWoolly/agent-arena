# Amended frozen experiment runbook (technical amendment 003)

Run all commands from the Agent Arena repository root. Read the base design
and technical amendments 001, 002, and 003 together. Every earlier manifest,
ledger, intent, run artifact, and amendment is immutable.

## Reproduce the current freezes

```bash
python3 bin/plan_experiment.py manifest --phase confirmatory --output bouts/2026-08-22-pre-requirements-planning-amendment-3/MANIFEST.json --bout-dir bouts/2026-08-22-pre-requirements-planning-amendment-3 --design bouts/2026-08-22-pre-requirements-planning/DESIGN.md --analysis-script analysis/2026-08-22-pre-requirements-planning/analyze.py --report-template analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md --runs 20 --reserves 5 --seed 2808222026 --frozen-at 2026-08-23T22:55:00Z
python3 bin/plan_experiment.py manifest --phase smoke --output bouts/2026-08-22-pre-requirements-planning-smoke-amendment-3/MANIFEST.json --bout-dir bouts/2026-08-22-pre-requirements-planning-smoke-amendment-3 --smoke-continuation-from bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json --design bouts/2026-08-22-pre-requirements-planning/DESIGN.md --analysis-script analysis/2026-08-22-pre-requirements-planning/analyze.py --report-template analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md --runs 1 --reserves 0 --seed 2808222027 --frozen-at 2026-08-23T22:55:00Z
```

Publication is atomic and no-clobber. Reproduce each manifest in a clean
disposable checkout where its output is absent, then compare its exact bytes
with the committed file.

## Offline validation

```bash
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning-amendment-3/MANIFEST.json
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning-smoke-amendment-3/MANIFEST.json
ARENA_SYNTHETIC_ONLY=1 python3 bin/test_plan_experiment.py
ARENA_SYNTHETIC_ONLY=1 python3 bin/test_served_model.py
python3 bin/test_summarize_integrity.py
bin/check-graders.sh
ruff check bin/plan_experiment.py bin/credential_guard.py bin/test_plan_experiment.py bin/test_served_model.py bin/metrics.py bin/metrics_codex.py bin/metrics_kimi.py analysis/2026-08-22-pre-requirements-planning/analyze.py
bash -n bin/run-task.sh bin/run-task-codex.sh bin/run-task-kimi.sh
git diff --check
git fsck --no-reflogs
```

The synthetic suite must prove that one concurrent manifest publisher wins;
every post-journal crash consumes its slot; partial, duplicate, missing,
symlinked, malformed, reordered, or mismatched claim/intent/ledger evidence
fails closed; inherited-plus-current smoke accounting cannot exceed three; and
a newly ineligible confirmatory primary or reserve prevents the next mocked
`Popen` while an eligible replacement permits the next frozen primary.

Run aggregate credential scans for all three exact external source homes
against the whole repository and require zero leaks, unsafe entries, and
symlinks. Then run both no-API gates from an exact clean committed tree with
the three source-home environment variables configured as in the base
runbook:

```bash
python3 bin/plan_experiment.py preflight bouts/2026-08-22-pre-requirements-planning-amendment-3/MANIFEST.json
python3 bin/plan_experiment.py preflight bouts/2026-08-22-pre-requirements-planning-smoke-amendment-3/MANIFEST.json
```

## Independent review gate

Two separate fresh-context reviewers must approve the exact committed
amendment-003 candidate: one protocol/reproducibility reviewer and one
security/adversarial reviewer. Reviews are offline and may not call targets,
inspect response semantics, or access credentials. Any blocker requires a new
amendment and new bout directories; do not rewrite amendment 003.

## The two remaining excluded smoke calls

Only after both approvals, run the frozen Kimi-then-Claude suffix:

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-smoke-amendment-3/MANIFEST.json
```

The cumulative smoke maximum remains three calls: the immutable initial Codex
attempt plus at most these two calls. Never retry a failed, uncertain, claimed,
or unresolved slot. Preserve the claim journal, intent files, ledger, and raw
artifacts. Do not open response text or broad metrics or configuration objects.
Use only these response-free technical views:

```bash
python3 bin/plan_experiment.py smoke-status bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json --historical
python3 bin/plan_experiment.py smoke-status bouts/2026-08-22-pre-requirements-planning-smoke-amendment-3/MANIFEST.json
```

The excluded-smoke evidence and handoff must disclose the initial accidental
display of the Codex response and instruction-policy value.

## Confirmatory dry run and approval lock

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-amendment-3/MANIFEST.json --dry-run
jq -r .freeze_id bouts/2026-08-22-pre-requirements-planning-amendment-3/MANIFEST.json
```

Confirmatory execution remains forbidden until the user explicitly approves
that exact committed freeze ID. Only after approval may it be passed through
`--approval`.

If a primary is newly ineligible, the command stops after preserving its
ledger row. Run only the next frozen reserve explicitly:

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-amendment-3/MANIFEST.json \
  --approval <APPROVED_AMENDMENT_003_FREEZE_ID> \
  --reserve <NEXT_FROZEN_RESERVE_SLOT_ID> \
  --replacement-for <INELIGIBLE_PRIMARY_OR_RESERVE_SLOT_ID> \
  --exclusion-reason <SUPPORTED_PREREGISTERED_REASON>
```

An ineligible reserve pauses again. Resume primary execution only after its
effective replacement chain ends in an eligible attempt. Any unresolved
claim, intent, or ledger state blocks execution and requires a separately
frozen amendment; it is never repaired or retried.

Do not merge, deploy, or run the paid confirmatory matrix as part of this work.
