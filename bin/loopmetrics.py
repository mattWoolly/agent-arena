#!/usr/bin/env python3
"""Flip-flop / convergence metrics for a run's transcript.

usage: loopmetrics.py <bout-dir> <model-dirname> [<bout-dir> <model-dirname> ...]

Measures, per run, the "flip-flopping in agentic loops" complaint directly:
- test_runs: how many times the agent ran pytest (parsed from tool_result
  summary lines, "N passed[, M failed]").
- regressions: transitions where the failing-test count INCREASED between two
  successive pytest runs (broke something that was passing) -- the whack-a-mole
  signature. Monotone convergence has zero.
- fail_trajectory: the sequence of failing counts across runs.
- edits: Edit/Write operations touching the target source file.
- reverts: an Edit whose new_string re-introduces a substring a prior Edit had
  removed (old_string), i.e. toggling a code region back -- code-level flip-flop.
- converged: did the run's final grade pass.
Reports per-corpus means and the per-run vectors. Compare only at matched CLI
versions or with a same-window anchor.
"""
import json
import re
import sys
from pathlib import Path

SUMMARY = re.compile(r'(\d+)\s+passed(?:,\s*(\d+)\s+failed)?|(\d+)\s+failed')
TARGET_HINT = ("money.py", "loader.py", "engine.py", "redactor.py", ".py")


def parse_pytest(text):
    """Return failing count from a pytest summary blob, or None if not a summary."""
    if "passed" not in text and "failed" not in text and "error" not in text:
        return None
    passed = failed = None
    m = re.search(r'(\d+)\s+failed', text)
    if m:
        failed = int(m.group(1))
    m = re.search(r'(\d+)\s+passed', text)
    if m:
        passed = int(m.group(1))
    if "error" in text and failed is None:
        me = re.search(r'(\d+)\s+error', text)
        if me:
            failed = int(me.group(1))
    if passed is None and failed is None:
        return None
    return failed or 0


def analyze_run(tpath):
    fails = []          # failing count per pytest run, in order
    edits = 0
    removed = []        # substrings removed by prior edits (for revert detection)
    reverts = 0
    tool_ran_pytest = {}  # tool_use id -> True if this was a pytest invocation
    for line in tpath.read_text().splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        if t == "assistant":
            for b in ev.get("message", {}).get("content", []):
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                name = b.get("name"); inp = b.get("input") or {}
                if name == "Bash" and "pytest" in (inp.get("command") or ""):
                    tool_ran_pytest[b.get("id")] = True
                if name in ("Edit", "Write") and str(inp.get("file_path", "")).endswith(".py") \
                        and "test" not in str(inp.get("file_path", "")):
                    edits += 1
                    old = inp.get("old_string") or ""
                    new = inp.get("new_string") or inp.get("content") or ""
                    # revert = this edit re-introduces something a prior edit removed
                    for r in removed:
                        if r and len(r) > 12 and r in new:
                            reverts += 1
                            break
                    if old and len(old) > 12:
                        removed.append(old.strip())
        elif t == "user":
            for b in ev.get("message", {}).get("content", []):
                if not isinstance(b, dict) or b.get("type") != "tool_result":
                    continue
                if b.get("tool_use_id") in tool_ran_pytest:
                    content = b.get("content")
                    text = content if isinstance(content, str) else json.dumps(content)
                    fc = parse_pytest(text)
                    if fc is not None:
                        fails.append(fc)
    # regressions: failing count increases between successive pytest runs
    regressions = sum(1 for i in range(1, len(fails)) if fails[i] > fails[i - 1])
    return {
        "test_runs": len(fails),
        "fail_trajectory": fails,
        "regressions": regressions,
        "edits": edits,
        "reverts": reverts,
    }


def corpus(bout, model):
    runs = sorted(bout.glob(f'*/{model}/run-*')) or sorted(bout.glob(f'*/{model}'))
    rows = []
    for rd in runs:
        tp = rd / "transcript.jsonl"
        if not tp.exists():
            continue
        m = analyze_run(tp)
        ge = rd / "grade_exit"
        m["converged"] = ge.exists() and ge.read_text().strip() == "0"
        m["run"] = str(rd.relative_to(bout))
        rows.append(m)
    n = max(len(rows), 1)
    agg = {
        "corpus": f"{bout.name}/{model}",
        "runs": len(rows),
        "converged": sum(r["converged"] for r in rows),
        "mean_test_runs": round(sum(r["test_runs"] for r in rows) / n, 2),
        "mean_regressions": round(sum(r["regressions"] for r in rows) / n, 2),
        "runs_with_regression": sum(1 for r in rows if r["regressions"] > 0),
        "mean_edits": round(sum(r["edits"] for r in rows) / n, 2),
        "mean_reverts": round(sum(r["reverts"] for r in rows) / n, 2),
        "runs_with_revert": sum(1 for r in rows if r["reverts"] > 0),
        "detail": rows,
    }
    return agg


def main():
    args = sys.argv[1:]
    out = [corpus(Path(args[i]), args[i + 1]) for i in range(0, len(args), 2)]
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
