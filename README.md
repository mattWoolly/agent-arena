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
  run-task-codex.sh # run-task.sh's Codex-CLI counterpart: same fixtures/graders, codex exec driver, "<model>-codex" cells
  metrics_codex.py  # metrics for codex --json transcripts (same output keys; cost from per-turn usage + env/prices.json)
  behavior.py    # behavioral fingerprint across runs: tool tempo, first moves, verification breadth, self-authored checks (compare only at matched CLI versions or with same-window anchors)
  loopmetrics.py # flip-flop/convergence metrics from a transcript: pytest fail-trajectory regressions, code reverts, edits
  metrics.py     # extract cost/turns/tokens/tool-calls from a run's transcript
  numcheck.py    # numeric-reliability analysis for tasks 13/14/15: per-item verdicts joined with tool-derivation evidence from the transcript; per-run silent-error flag; per-(task, model) aggregates
  served_model.py# read the model that ACTUALLY served a run from transcript response tags
  summarize.py   # aggregate a bout directory into results.md + results.json (mean ±sd across repeats)
  test_*.py      # unit tests (served_model, summarize integrity) — run `python3 bin/test_<x>.py`
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
  07-injection/      # prompt-injection resistance: legit task + 3 planted non-destructive injections
  08-evaluator/      # ceiling-raiser: spreadsheet formula engine; naive impl passes visible, fails hidden
  07-injection-subtle/ # subtle injection: a false "spec exception" that leaks secrets if obeyed
  08-evaluator-hard/ # harder ceiling-raiser: right-assoc exponentiation + unary/precedence traps
  09-converge/       # convergence/flip-flop probe: money formatter with sign-after-rounding tension; suite ships in fixture
  13-ledger/         # incidental arithmetic: finance briefing from a transaction CSV; structure gates, numbers scored per item without gating
  13-ledger-explicit/# explicit twin: same computations as the stated task -> RESULTS.json; gates on every item
  14-schedule/       # incidental arithmetic: business-day project plan; date items with error classes + CHAIN local-consistency lines
  14-schedule-explicit/ # explicit twin of 14-schedule -> RESULTS.json
  15-rollup/         # incidental arithmetic: quarterly rollup of three monthly reports; planted stated-vs-line-items discrepancy, FLAG line
  15-rollup-explicit/# explicit twin of 15-rollup -> RESULTS.json
  10-inject-sandbox/ # injection: false settings.py note claims tmp/ paths bypass the sandbox -> path traversal
  11-inject-review/  # injection: false REVIEW.md sign-off claims [[trusted]] input is pre-escaped -> XSS passthrough
  12-inject-cred/    # injection: false 'approved ticket' comment drops the length check -> weak passwords
bouts/
  <date>-<name>/     # results: per task, per model (per run-K/ with repeats):
                     # transcript.jsonl, result.json, workspace.diff, grade.txt,
                     # metrics.json, run_env.json, peek_check, workspace/
                     # (workspace/ is local-only and untracked, except findings.md)
analysis/
  <date>-<name>/     # pre-registered reanalyses of published bout artifacts:
                     # DESIGN.md (committed before results), the analysis
                     # script, and its outputs; no new runs, bouts stay immutable
```

Each task directory contains:

- `PROMPT.md` — the exact prompt sent to the agent (byte-identical for every model)
- `fixture/` — files seeded into the agent's workspace
- `setup.sh` — optional post-copy mutation (e.g. planting CRLF line endings)
- `grade.sh` — hidden grader; the agent never sees it. Exit 0 = pass. Emits `SCORE: n/m`.
- `solution/` or `hidden_tests/` — grader assets, also hidden from the agent
- `check-grader.sh` — optional self-test proving the grader fails the raw fixture
  and passes a reference solution

### Grader isolation (`tasks/_lib/`)

Graders must never let the agent's workspace influence the test runner.

- `_lib/arena_pytest.sh` — `arena_pytest <workspace> <pristine-tests> [args…]`.
  Tests are copied from the task's own `fixture/` or `hidden_tests/` into a
  scratch rootdir the agent has never touched; the workspace contributes code
  only, via `PYTHONPATH`. Config discovery is pinned off (`-c /dev/null`,
  explicit `--rootdir`) and `TZ`/`LANG`/`LC_ALL`/`PYTHONHASHSEED` are frozen.
  **Every grader uses this — never `cd "$WS" && pytest`.** Running visible
  tests from the fixture copy also makes the `tests/ untouched` guard
  structural rather than merely scored.

  Why: until 2026-08-15 graders ran pytest with the workspace as rootdir, so
  pytest auto-loaded any `conftest.py` the agent left there. A six-line report
  hook forcing every outcome to `passed` scored 3/3 on `08-evaluator-hard` with
  the implementation byte-identical to the fixture. (BenchJack V1,
  arXiv:2605.12673.) No archived run ever exploited it — 0 of 644.

- `_lib/arena_pytest.sh` also provides `arena_config_tripwire <ws> <fixture>`,
  which reports root test-config the agent **added or modified** relative to
  the fixture. Advisory by default; graders may treat a hit as a hard fail.

- `_lib/validate-task.sh <task-dir>` — run this after touching any grader:

  | case | expectation |
  |---|---|
  | A raw fixture | grader must fail |
  | B reference solution | grader must pass |
  | C exploit `conftest.py` only | grader must fail |
  | D reference + exploit | grader must pass |

  B and D are what stop a "fix" from silently breaking honest runs. The pass
  criterion is the grader's **exit status**, not a full score — some tasks
  award behavioural points (e.g. flagging an injection in `SOLUTION.md`) that a
  code-only reference solution cannot earn. Tasks with no `solution/` skip B
  and D. Reference solutions are applied by basename-matching into the
  workspace; a task whose layout differs can supply `solution/APPLY.sh`.

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

### Served-model integrity

An endpoint can silently serve a different model than requested — verified
2026-08-15: Z.ai's Anthropic-compatible endpoint serves GLM-5.3 for a GLM-5.2
request, no error, the only signal being the `model` field on each response. A
version-pinned comparison run through such an endpoint is invalid unless every
run's *served* model is recorded and checked.

`metrics.py` records `served_model` / `served_models` / `served_model_leak`
per run (via `served_model.py`, which reads response tags across the Claude
Code, Codex, and Kimi transcript formats — request echoes never count). Token
usage falls back to the served id, so a substitution can't silently null the
counts. A run served by more than one model (`served_model_leak`) means a
subagent or summarizer used a different model than the arm pinned.

Declare the required served id per model label in `bouts/<bout>/EXPECTED.json`
(`{"<label>": "<served-id-substring>"}`). `summarize.py` then emits a
`⛔ SERVED-MODEL INTEGRITY FAILURES` block — a hard stop — for any run whose
served model disagrees or leaked; with no failures it prints a one-line OK.
Without `EXPECTED.json` the fields are still recorded, just not gated.
(Currently wired for Claude-Code-driver runs via `metrics.py`; port to
`metrics_codex.py` / `metrics_kimi.py` before a harness-axis arm.)

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
published, every run also gets a secret-leak check: if the auth token or the
`ANTHROPIC_API_KEY` (native-run auth) appears in `transcript.jsonl` or the
finished workspace, `peek_check` records `SECRET LEAK` and the run is
flagged as unpublishable. A model may also ship
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

The CLI prices unknown model IDs from its own Claude table, and LiteLLM's
Anthropic-format translation drops cached-token counts (LiteLLM issues
27763/9812), so proxied runs get two layers of cost repair. First choice: a
custom proxy callback (`env/litellm_usage_logger.py`, wired via the model's
LiteLLM config) appends each request's raw usage and LiteLLM's cache-aware
`response_cost` to `.proxy/usage.jsonl`; run-task.sh captures the run's
slice as `proxy_usage.jsonl` in the run dir, and `metrics.py` sums it
(`cost_source: proxy-usage-log`), also restoring the true cached-token
count. Fallback: for models listed in `env/prices.json` (list prices per 1M
tokens with cache tiers and long-context multipliers), `metrics.py`
recomputes from transcript or envelope usage; without cache visibility that
figure is an upper bound at full input rates. The CLI's figure is always
preserved as `total_cost_usd_cli` and `cost_source` records which path
priced the run.

Requirements: `claude` CLI on PATH (authed), `python3`, `pytest`, `jq`, `make`, `git`.

Agents run with `--dangerously-skip-permissions` in throwaway workspaces created
with `mktemp` **outside this repository**, so graders, hidden tests, and reference
solutions are unreachable by construction. The finished workspace is copied back
into `bouts/` for publication. After every run a peek check greps the transcript
for references to the arena tree or grader assets and flags the run if any appear;
workspaces are fresh git repos so every change is diffable and attributable.

## Cross-driver runs (harness comparison)

`bin/run-task-codex.sh` runs a model under the Codex CLI against the same
fixtures, byte-identical PROMPT.md, and the same hidden graders, labeling
cells `<model>-codex` so they sit beside Claude-Code-driven cells in one
results table. Auth uses an isolated API-key `CODEX_HOME` in `.codex-arena/`
(gitignored), never the user's `~/.codex` session; the `env/<label>.leakscan`
hook covers the key. Codex "turns" are whole prompt→completion cycles, so
compare effort across drivers on tool calls, tokens, wall, and cost, not
turn counts.

`bin/run-task-kimi.sh` does the same for Kimi Code (`kimi -p`, stream-json;
prompt mode auto-approves), labeling cells `kimi-k3-kimicode`. It runs with
`HOME` pointed at the isolated `~/.kimi-arena/` (outside the repo tree;
override with `ARENA_KIMI_HOME`), whose config uses the metered Moonshot
platform API key rather than the user's device-code login. The driver
refuses an in-repo home: the original `.kimi-arena/` inside the checkout
made every transcript reference the repo path (peek-check false positives)
and, because Python derives its user-site directory from `HOME`, hid
`~/.local` packages; that planted an unplanted pytest fault in 9 of 24 runs
of the 2026-07-18 home bout, costing those runs 51-65% of execution time
(quantified in `analysis/2026-07-25-terminal-walkthrough/`). The driver now
pins `PYTHONUSERBASE` to the real user's `~/.local` so the agent's python
resolves the same packages as under the other drivers. Per-turn usage is
taken from the session's `wire.jsonl` (copied into the run dir) and priced
by `bin/metrics_kimi.py` from `env/prices.json` (price key defaults to
`kimi-k3`; override with `ARENA_KIMI_PRICE_KEY` for arms priced
differently). Per-arm cells (e.g. an effort ladder) relabel via
`ARENA_KIMI_LABEL` — the leak scan falls back to the base
`kimi-k3-kimicode.leakscan` — and record their requested effort via
`ARENA_KIMI_EFFORT`; effort selection itself is per model alias
(`default_effort` in the arena `config.toml`). Metrics prove the request
rather than assuming it: `requested_efforts` collects the `thinkingEffort`
value from every `llm.request` event in `wire.jsonl`, and
`thinking_chars` totals the session's "think" content parts, giving a
measured reasoning volume per run.

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
