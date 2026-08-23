# Frozen experiment runbook

All commands run from the Agent Arena repository root. The confirmatory command
is intentionally blocked until explicit user approval of the exact manifest
freeze ID. Do not edit the prompt, rubric, design, manifest, or analyzer between
approval and execution.

## Validate the frozen package

```bash
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning/MANIFEST.json
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json
python3 bin/test_plan_experiment.py
python3 bin/test_served_model.py
python3 bin/test_summarize_integrity.py
bin/check-graders.sh
```

The isolated Codex and Kimi authentication/config homes must be outside the
published worktree. Export their paths only in the operator shell; neither path
nor credential content is a frozen treatment variable.

```bash
export ARENA_CODEX_HOME=/absolute/path/to/isolated/codex-home
export ARENA_KIMI_HOME=/absolute/path/to/isolated/kimi-home
```

## Excluded smoke only

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json
```

Inspect only transport/integrity fields in each `run_record.json`, then verify
every smoke directory with:

```bash
python3 bin/plan_experiment.py verify-run bouts/2026-08-22-pre-requirements-planning-smoke/16-pre-requirements-plan/claude-opus-5/run-1
python3 bin/plan_experiment.py verify-run bouts/2026-08-22-pre-requirements-planning-smoke/16-pre-requirements-plan/gpt-5.6-sol-codex/run-1
python3 bin/plan_experiment.py verify-run bouts/2026-08-22-pre-requirements-planning-smoke/16-pre-requirements-plan/kimi-k3-kimicode/run-1
```

## Confirmatory dry run (no API calls)

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning/MANIFEST.json --dry-run
```

## Confirmatory execution (forbidden before approval)

After the user explicitly approves the frozen design, substitute the exact
committed `freeze_id` below. The runner rejects a missing or different value.

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning/MANIFEST.json --approval 99bd98a1b21bb62e09f3758b9830e06b947b59a29fbc240173c16ddcca83072b
```

Do not run reserves with the primary schedule. Record an objective invalidation
and explicit reserve linkage first; if the five reserves for a condition are
exhausted, stop and amend.

One reserve is run explicitly and only for an ineligible primary of the same
condition. Use identifiers and one exact reason from `replace_only` in the
manifest:

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning/MANIFEST.json \
  --approval 99bd98a1b21bb62e09f3758b9830e06b947b59a29fbc240173c16ddcca83072b \
  --reserve [frozen-reserve-slot-id] \
  --replacement-for [ineligible-primary-slot-id] \
  --exclusion-reason [preregistered-reason]
```

## Blind and analyze after the complete matrix

Set a fresh secret blinding key. Preserve the generated mapping for audit but
withhold it from both semantic reviewers until their independent reviews are
locked.

```bash
export ARENA_BLIND_KEY=[fresh-secret-value]
python3 bin/plan_experiment.py blind bouts/2026-08-22-pre-requirements-planning/MANIFEST.json --output-dir analysis/2026-08-22-pre-requirements-planning/blinded
```

Copy the reviewer/adjudication templates to append-only working files, fill
them against only `review-packets.json` and the hidden rubric, and code the
instruction exposure before revealing `blind-map.json`. Then generate both
outputs together:

```bash
python3 analysis/2026-08-22-pre-requirements-planning/analyze.py \
  --manifest bouts/2026-08-22-pre-requirements-planning/MANIFEST.json \
  --packets analysis/2026-08-22-pre-requirements-planning/blinded/review-packets.json \
  --blind-map analysis/2026-08-22-pre-requirements-planning/blinded/blind-map.json \
  --reviewer-a analysis/2026-08-22-pre-requirements-planning/reviewer-a.json \
  --reviewer-b analysis/2026-08-22-pre-requirements-planning/reviewer-b.json \
  --adjudications analysis/2026-08-22-pre-requirements-planning/adjudications.json \
  --instruction-exposure analysis/2026-08-22-pre-requirements-planning/instruction-exposure.json \
  --output-json analysis/2026-08-22-pre-requirements-planning/analysis.json \
  --output-report analysis/2026-08-22-pre-requirements-planning/REPORT.md
```
