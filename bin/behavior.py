#!/usr/bin/env python3
"""Behavioral fingerprint for a set of runs: how a model works, not whether it passed.

usage: behavior.py <bout-dir> <model-dirname> [more <bout-dir> <model-dirname> pairs]

Computes, per (bout, model) corpus, from transcript.jsonl files:
  tool calls/run and by tool; thinking blocks/run and per tool call (cadence
  only: the CLI does not persist thinking content); explanatory text chars/run;
  Bash batching fraction (&&/;); first tool-call fingerprint (tool, and for
  Bash an ls/cat/test/other category); re-read count (Read of an already-Read
  path); verify-before-finish rate (last tool call is a test invocation);
  first-test position as a fraction of the run's tool calls; self-check-file
  events (Write of a path matching check/verify/scratch outside fixture files,
  the "wrote its own test harness" signal).

Emits one JSON object to stdout. Born in the Opus 5 succession bout
(analysis/2026-07-26-opus5-mechanism), where these metrics separated models
a saturated grader battery could not. Compare corpora only at matched CLI
versions or alongside a same-window anchor; several of these metrics drift
with harness version (documented in that analysis).
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

TEST_RE = re.compile(r'\b(pytest|make(\s+test)?\b|npm test|python3?\s+\S*(_?check|selftest)\S*\.py)\b')
CHECK_RE = re.compile(r'(_?check|verify|scratch|selftest)[^/]*\.(py|sh|js)$', re.I)


def corpus(bout: Path, model: str) -> dict:
    runs = sorted(bout.glob(f'*/{model}/run-*/transcript.jsonl')) or sorted(bout.glob(f'*/{model}/transcript.jsonl'))
    agg = {
        "runs": 0, "tool_calls": 0, "by_tool": Counter(), "thinking_blocks": 0,
        "text_chars": 0, "bash_cmds": 0, "bash_batched": 0, "re_reads": 0,
        "runs_with_reread": 0, "first_tool": Counter(), "first_bash_kind": Counter(),
        "verify_before_finish": 0, "runs_with_tests": 0, "first_test_pos": [],
        "self_check_writes": [],
    }
    for t in runs:
        agg["runs"] += 1
        calls = []
        read_paths, rereads = set(), 0
        for line in t.read_text().splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") != "assistant":
                continue
            for b in ev.get("message", {}).get("content", []):
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "thinking":
                    agg["thinking_blocks"] += 1
                elif bt == "text":
                    agg["text_chars"] += len(b.get("text", ""))
                elif bt == "tool_use":
                    name = b.get("name", "?")
                    inp = b.get("input") or {}
                    calls.append((name, inp))
                    agg["by_tool"][name] += 1
                    if name == "Bash":
                        cmd = inp.get("command", "")
                        agg["bash_cmds"] += 1
                        if "&&" in cmd or ";" in cmd:
                            agg["bash_batched"] += 1
                    if name == "Read":
                        p = inp.get("file_path", "")
                        if p in read_paths:
                            rereads += 1
                        read_paths.add(p)
                    if name == "Write" and CHECK_RE.search(inp.get("file_path", "")):
                        agg["self_check_writes"].append(str(t.parent.relative_to(bout)) + ":" + inp.get("file_path", ""))
        agg["tool_calls"] += len(calls)
        agg["re_reads"] += rereads
        agg["runs_with_reread"] += 1 if rereads else 0
        if calls:
            fname, finp = calls[0]
            agg["first_tool"][fname] += 1
            if fname == "Bash":
                c = finp.get("command", "").strip()
                kind = "ls" if c.startswith("ls") else "cat" if c.startswith("cat") else \
                    "test" if TEST_RE.search(c) else "other"
                agg["first_bash_kind"][kind] += 1
            test_idx = [i for i, (n, i2) in enumerate(calls) if n == "Bash" and TEST_RE.search(i2.get("command", ""))]
            if test_idx:
                agg["runs_with_tests"] += 1
                agg["first_test_pos"].append(round(test_idx[0] / len(calls), 3))
                # "verifies before finishing": a test/check invocation within the
                # final 3 tool calls (models that verify often end on cleanup,
                # e.g. rm _check.py && git status, not on the test itself).
                if test_idx[-1] >= len(calls) - 3:
                    agg["verify_before_finish"] += 1
    n = max(agg["runs"], 1)
    out = {
        "corpus": f"{bout.name}/{model}",
        "runs": agg["runs"],
        "tool_calls_per_run": round(agg["tool_calls"] / n, 2),
        "by_tool": dict(agg["by_tool"]),
        "thinking_blocks_per_run": round(agg["thinking_blocks"] / n, 2),
        "thinking_per_tool_call": round(agg["thinking_blocks"] / max(agg["tool_calls"], 1), 2),
        "text_chars_per_run": round(agg["text_chars"] / n),
        "bash_batched_frac": round(agg["bash_batched"] / max(agg["bash_cmds"], 1), 3),
        "re_reads_total": agg["re_reads"],
        "runs_with_reread": agg["runs_with_reread"],
        "first_tool": dict(agg["first_tool"]),
        "first_bash_kind": dict(agg["first_bash_kind"]),
        "runs_with_tests": agg["runs_with_tests"],
        "verify_before_finish_rate_of_test_runs": round(agg["verify_before_finish"] / max(agg["runs_with_tests"], 1), 3),
        "mean_first_test_pos": round(sum(agg["first_test_pos"]) / max(len(agg["first_test_pos"]), 1), 3),
        "self_check_writes": agg["self_check_writes"],
    }
    return out


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2 or len(args) % 2:
        sys.exit("usage: behavior.py <bout-dir> <model-dirname> [<bout-dir> <model-dirname> ...]")
    results = [corpus(Path(args[i]), args[i + 1]) for i in range(0, len(args), 2)]
    json.dump(results, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
