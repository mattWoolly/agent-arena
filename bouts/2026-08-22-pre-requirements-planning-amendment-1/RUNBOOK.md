# Amended frozen experiment runbook

Run all commands from the Agent Arena repository root. The base design and
hypotheses remain in
`bouts/2026-08-22-pre-requirements-planning/DESIGN.md`; read them together with
`AMENDMENT.md`. The original manifests and first smoke artifacts are immutable.

## Reproduce the amended freezes

```bash
python3 bin/plan_experiment.py manifest --phase confirmatory --output bouts/2026-08-22-pre-requirements-planning-amendment-1/MANIFEST.json --bout-dir bouts/2026-08-22-pre-requirements-planning-amendment-1 --design bouts/2026-08-22-pre-requirements-planning/DESIGN.md --analysis-script analysis/2026-08-22-pre-requirements-planning/analyze.py --report-template analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md --runs 20 --reserves 5 --seed 2808222026 --frozen-at 2026-08-23T18:00:00Z
python3 bin/plan_experiment.py manifest --phase smoke --output bouts/2026-08-22-pre-requirements-planning-smoke-amendment-1/MANIFEST.json --bout-dir bouts/2026-08-22-pre-requirements-planning-smoke-amendment-1 --smoke-continuation-from bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json --design bouts/2026-08-22-pre-requirements-planning/DESIGN.md --analysis-script analysis/2026-08-22-pre-requirements-planning/analyze.py --report-template analysis/2026-08-22-pre-requirements-planning/REPORT_TEMPLATE.md --runs 1 --reserves 0 --seed 2808222027 --frozen-at 2026-08-23T18:00:00Z
```

Manifest creation is no-clobber. Reproduction must occur in a clean checkout
where those output files do not yet exist, or compare a newly generated
temporary file byte-for-byte with the committed manifest.

## Offline validation

```bash
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning-amendment-1/MANIFEST.json
python3 bin/plan_experiment.py validate bouts/2026-08-22-pre-requirements-planning-smoke-amendment-1/MANIFEST.json
ARENA_SYNTHETIC_ONLY=1 python3 bin/test_plan_experiment.py
ARENA_SYNTHETIC_ONLY=1 python3 bin/test_served_model.py
python3 bin/test_summarize_integrity.py
bin/check-graders.sh
ruff check bin/plan_experiment.py bin/credential_guard.py bin/test_plan_experiment.py bin/test_served_model.py bin/metrics.py bin/metrics_codex.py bin/metrics_kimi.py analysis/2026-08-22-pre-requirements-planning/analyze.py
bash -n bin/run-task.sh bin/run-task-codex.sh bin/run-task-kimi.sh
git diff --check
```

Set the three external auth/config source-home variables exactly as described
in the base runbook, then run both no-API gates from a clean committed tree:

```bash
python3 bin/plan_experiment.py preflight bouts/2026-08-22-pre-requirements-planning-amendment-1/MANIFEST.json
python3 bin/plan_experiment.py preflight bouts/2026-08-22-pre-requirements-planning-smoke-amendment-1/MANIFEST.json
```

## The two remaining excluded smoke calls

Do not run this command until two fresh independent reviewers approve the exact
amended commit. It contains only the still-unattempted Kimi and Claude slots in
their original frozen order. It makes exactly two calls and cannot retry Codex.

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-smoke-amendment-1/MANIFEST.json
```

Do not open response text or broad metrics/configuration objects. Produce only
the redacted technical view, which is tested not to serialize target or
instruction content:

```bash
python3 bin/plan_experiment.py smoke-status bouts/2026-08-22-pre-requirements-planning-smoke/MANIFEST.json --historical
python3 bin/plan_experiment.py smoke-status bouts/2026-08-22-pre-requirements-planning-smoke-amendment-1/MANIFEST.json
```

## Confirmatory dry run and approval lock

```bash
python3 bin/plan_experiment.py run bouts/2026-08-22-pre-requirements-planning-amendment-1/MANIFEST.json --dry-run
```

Confirmatory execution is forbidden until the user explicitly approves the
exact committed freeze. Retrieve it without copying response artifacts:

```bash
jq -r .freeze_id bouts/2026-08-22-pre-requirements-planning-amendment-1/MANIFEST.json
```

Only after that approval, pass the approved value through `--approval`. Do not
merge or deploy as part of this work.
