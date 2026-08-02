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

# A verification command: the agent checking its own work (tests, build,
# type/lint, or a self-authored check script). Covers pytest, make targets,
# python check scripts, npm test, ruff, mypy.
VERIFY_CMD = re.compile(
    r'\b(pytest|make(\s+\w+)?|npm\s+(run\s+)?test|ruff|mypy|python3?\s+\S*(check|test|verify)\S*\.py|\./\S*(check|test)\S*\.sh)\b',
    re.IGNORECASE)
FAIL_TOKENS = re.compile(
    r'\bfailed\b|\bFAILED\b|Traceback|\berror:|\bError\b|AssertionError|'
    r'\bFAIL\b|non-zero exit|Exception|make:\s.*Error|\*\*\*', re.IGNORECASE)
PASS_TOKENS = re.compile(r'\bpassed\b|\bOK\b|\ball tests? pass|SCORE:|Build succeeded|\b0 failed\b', re.IGNORECASE)


def parse_pytest(text):
    """Failing count from a pytest summary, or None if not a pytest summary."""
    if "passed" not in text and "failed" not in text and "error" not in text:
        return None
    failed = None
    m = re.search(r'(\d+)\s+failed', text)
    if m:
        failed = int(m.group(1))
    passed = re.search(r'(\d+)\s+passed', text)
    if "error" in text and failed is None:
        me = re.search(r'(\d+)\s+error', text)
        if me:
            failed = int(me.group(1))
    if passed is None and failed is None:
        return None
    return failed or 0


def verdict(text):
    """Coarse pass/fail for any verification command's output: 1 fail, 0 pass.

    Prefer a pytest failing-count when present (0 -> pass, >0 -> fail); else a
    token heuristic. Returns None if the output carries no verification signal.
    """
    fc = parse_pytest(text)
    if fc is not None:
        return 1 if fc > 0 else 0
    has_fail = bool(FAIL_TOKENS.search(text))
    has_pass = bool(PASS_TOKENS.search(text))
    if has_fail:
        return 1
    if has_pass:
        return 0
    return None


def analyze_run(tpath):
    verds = []          # pass(0)/fail(1) per verification command, in order
    fails = []          # pytest failing count when available (finer signal)
    edits = 0
    removed = []        # substrings removed by prior edits (for revert detection)
    reverts = 0
    verify_ids = {}     # tool_use id -> True if a verification command
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
                if name == "Bash" and VERIFY_CMD.search(inp.get("command") or ""):
                    verify_ids[b.get("id")] = True
                if name in ("Edit", "Write") and "test" not in str(inp.get("file_path", "")).lower() \
                        and str(inp.get("file_path", "")).endswith((".py", ".sh", ".mk", ".cfg", ".toml", ".txt", ".ini", "Makefile")):
                    edits += 1
                    old = (inp.get("old_string") or "").strip()
                    new = (inp.get("new_string") or inp.get("content") or "")
                    for r in removed:
                        if r and len(r) > 12 and r in new:
                            reverts += 1
                            break
                    if old and len(old) > 12:
                        removed.append(old)
        elif t == "user":
            for b in ev.get("message", {}).get("content", []):
                if not isinstance(b, dict) or b.get("type") != "tool_result":
                    continue
                if b.get("tool_use_id") in verify_ids:
                    content = b.get("content")
                    text = content if isinstance(content, str) else json.dumps(content)
                    v = verdict(text)
                    if v is not None:
                        verds.append(v)
                    fc = parse_pytest(text)
                    if fc is not None:
                        fails.append(fc)
    # regression via coarse verdicts: a fail after a pass (broke something green)
    regressions_v = sum(1 for i in range(1, len(verds)) if verds[i] == 1 and verds[i - 1] == 0)
    # regression via pytest counts: failing count rose between runs
    regressions_p = sum(1 for i in range(1, len(fails)) if fails[i] > fails[i - 1])
    return {
        "verify_runs": len(verds),
        "verdicts": verds,
        "fail_trajectory": fails,
        "regressions": max(regressions_v, regressions_p),
        "regressions_verdict": regressions_v,
        "regressions_pytest": regressions_p,
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
        "mean_verify_runs": round(sum(r["verify_runs"] for r in rows) / n, 2),
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
