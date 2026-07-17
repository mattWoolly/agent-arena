# Agent Arena

Head-to-head harness for comparing agentic coding models running under Claude Code.
Give one or more model IDs the same graded tasks in isolated workspaces, capture
everything, and let the graders (not vibes) decide.

## Layout

```
bin/
  run-bout.sh    # run all (or selected) tasks for N models, with repeats and serial mode
  run-task.sh    # run ONE model on ONE task: seed workspace, run claude -p, grade
  arena-proxy.sh # start/stop a local translation proxy for models with no Anthropic-compatible endpoint
  metrics.py     # extract cost/turns/tokens/tool-calls from a run's transcript
  summarize.py   # aggregate a bout directory into results.md + results.json (mean ±sd across repeats)
env/
  <model>.env         # optional per-model environment (endpoint/auth); gitignored
  <model>.env.example # tracked template with placeholders, no secrets
tasks/
  01-bugfix/         # SWE-bench style: fix library code until tests pass
  02-synthesis/      # HumanEval/MBPP style: implement 5 specified functions
  03-refactor/       # Aider-refactor style: dict config -> frozen dataclass
  04-terminal/       # Terminal-Bench style: repair a broken build environment
  05-review/         # code-review style: find planted defects in a diff
  06-instructions/   # IFEval style: report generation under hard constraints
bouts/
  <date>-<name>/     # results: per task, per model (per run-K/ with repeats):
                     # transcript.jsonl, result.json, workspace.diff, grade.txt,
                     # metrics.json, run_env.json, peek_check, workspace/
                     # (workspace/ is local-only and untracked, except findings.md)
```

Each task directory contains:

- `PROMPT.md` — the exact prompt sent to the agent (byte-identical for every model)
- `fixture/` — files seeded into the agent's workspace
- `setup.sh` — optional post-copy mutation (e.g. planting CRLF line endings)
- `grade.sh` — hidden grader; the agent never sees it. Exit 0 = pass. Emits `SCORE: n/m`.
- `solution/` or `hidden_tests/` — grader assets, also hidden from the agent
- `check-grader.sh` — optional self-test proving the grader fails the raw fixture
  and passes a reference solution

## Running a bout

```
bin/run-bout.sh 2026-07-06-opus48-vs-fable5 claude-opus-4-8 claude-fable-5
# a subset of tasks:
bin/run-bout.sh smoke claude-opus-4-8 claude-fable-5 02-synthesis
# more than two models (a ladder):
bin/run-bout.sh ladder claude-haiku-4-5 claude-sonnet-5 claude-opus-4-8 claude-fable-5
# repeated runs for variance, executed serially with rotating model order:
bin/run-bout.sh -r 5 -s noise-floor claude-opus-4-8
```

Flags: `-r N` repeats each (task, model) cell N times (runs land in `run-K/`
subdirs; `results.md` reports pass k/N and mean ±sd). `-s` runs cells one at a
time so concurrent runs never share rate-limit headroom — use it whenever
wall-clock is a claim you intend to publish. Any argument that names a
directory under `tasks/` selects that task; everything else is a model ID.

Run configuration is pinned and recorded per run (`run_env.json`, merged into
`metrics.json`): CLI version, API base URL, per-model env file (if any),
`--effort` (default `xhigh`, override with `ARENA_EFFORT`), and
`--setting-sources` (default `project`, override with
`ARENA_SETTING_SOURCES`) — so runs never silently inherit the host machine's
user-level Claude configuration.

### Non-Anthropic models

A model served through an Anthropic-compatible endpoint (e.g. Moonshot's
`kimi-k3`) runs under the same harness: put its endpoint and auth vars in
`env/<model>.env` (copy the tracked `.env.example`, fill in the key). If that
file exists, `run-task.sh` sources it with allexport for that run's process
only — one process per (task, model) cell, so models never share environment.
The base URL and env-file name (never its contents) are recorded in
`run_env.json`. Real `.env` files are gitignored; only `.env.example`
templates are tracked.

Because the agent can read its own environment and transcripts/workspaces are
published, every run also gets a secret-leak check: if the auth token appears
in `transcript.jsonl` or the finished workspace, `peek_check` records
`SECRET LEAK` and the run is flagged as unpublishable. A model may also ship
an `env/<model>.leakscan` script (tracked; contains no secrets) that prints
extra secret values, one per line; run-task.sh executes it in a subshell
after the agent finishes and scans published artifacts for each value, so
secrets that never enter the agent's environment are still checked.

### Models with no Anthropic-compatible endpoint (translation proxy)

Some vendors (OpenAI) don't serve an Anthropic-compatible endpoint. For those,
`bin/arena-proxy.sh start <model>` runs a local LiteLLM proxy
(`env/litellm.<model>.yaml`, bound to 127.0.0.1, pid/log under `.proxy/`)
that translates the Messages API to the vendor's, and the model's env file
points `ANTHROPIC_BASE_URL` at it. The upstream key is pulled from
`~/.secrets` at proxy launch and exported only to the proxy process; the
contestant never holds it, and the model's `.leakscan` file lets the leak
check scan for it anyway. Set `ARENA_PROXY_UPSTREAM` in the env file: it is
recorded verbatim in `run_env.json` so published runs say what actually sat
behind localhost (`base_url` alone would just say 127.0.0.1). Disclose the
translation layer in anything published from such runs; tool-calling behavior
through a third-party translator is not attributable to the model alone.

The CLI prices unknown model IDs from its own Claude table, so for any model
listed in `env/prices.json` (list prices per 1M tokens, with cache tiers and
long-context multipliers where the vendor defines them) `metrics.py`
recomputes `total_cost_usd` from usage, preferring per-request transcript
usage and falling back to the result envelope's aggregate when a proxy zeroes
out per-message usage. The CLI's figure is preserved as `total_cost_usd_cli`
and `cost_source` records which path priced the run. Caveat, disclosed where
it matters: if a proxy fails to propagate the vendor's cached-token counts
(observed with LiteLLM: cache fields all zero), computed cost is an upper
bound at full input rates.

Requirements: `claude` CLI on PATH (authed), `python3`, `pytest`, `jq`, `make`, `git`.

Agents run with `--dangerously-skip-permissions` in throwaway workspaces created
with `mktemp` **outside this repository**, so graders, hidden tests, and reference
solutions are unreachable by construction. The finished workspace is copied back
into `bouts/` for publication. After every run a peek check greps the transcript
for references to the arena tree or grader assets and flags the run if any appear;
workspaces are fresh git repos so every change is diffable and attributable.

## Rubric judging (depth qualities)

Deterministic graders decide pass/fail; some qualities they can't price
(finding-synthesis, quantification, citation precision) can be scored
separately with an LLM judge:

```
bin/judge-run.sh <task-dir> <run-out-dir> [judge-model] [n-samples]
```

The task's `rubric.md` starts with `FILES: <deliverable> ...` followed by 0–2
scored dimensions. The judge (default `claude-opus-4-8`, always disclosed)
sees only rubric + deliverable content — never model names or paths — and is
sampled N times (default 3); `judge.json` in the run dir records every sample
plus the per-dimension median. Judge scores never gate a run's pass/fail.

Tasks may have prompt variants (e.g. `05-review-transplant/`): same fixture
and grader as the parent task via symlink/wrapper, different `PROMPT.md`, for
prompting experiments where the intervention is the variable under test.

## What gets measured

- **Correctness** — each task's `grade.sh`, run against hidden tests/checkers
- **Cost & speed** — `total_cost_usd`, wall-clock, API duration from the result envelope
- **Effort shape** — turns, tool calls by type, output tokens, diff size
- **Ergonomics** — from transcripts: did it follow output contracts, over-ask,
  over-build, produce a readable final summary (human-scored rubric)

## Honest-reporting rules

Single runs are anecdotes, not benchmarks. Report Ns, publish raw numbers,
never extrapolate a task win into a general claim. If the harness author is one
of the models under test, disclose it.

## Contributing

Any change to `bin/` or `tasks/` must update this README in the same commit if
it adds, removes, or changes a flag, environment variable, artifact, or
behavior a user of the harness would rely on. The README is the harness's
contract; code and contract move together.

A pre-commit hook enforces this. Enable it once per clone:

```
git config core.hooksPath .githooks
```

For a change with genuinely no user-facing surface: `SKIP_README=1 git commit ...`
