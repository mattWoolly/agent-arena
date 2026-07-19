#!/usr/bin/env python3
"""Mechanism-trace reanalysis of the 120 published runs (see DESIGN.md).

Parses all three transcript formats (Claude Code session JSONL, Codex
--json events, Kimi Code message log), emits mechanism.json (per-run
records) and mechanism.md (hypothesis scorecard + per-task tables).
Fails loudly on unrecognized events rather than skipping them.
"""
import json
import glob
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

BOUTS = {
    "claude-code": "bouts/2026-07-17-fable-sol-kimi",
    "codex": "bouts/2026-07-17-sol-codex-homegame",
    "kimi-code": "bouts/2026-07-18-kimi-homegame",
}

# Pre-registered definition (DESIGN.md): task-management calls.
TASK_MGMT = {"TaskCreate", "TaskUpdate", "TaskGet", "TaskList"}
# Present in transcripts but outside the pre-registered enumeration; counted
# as repo-touching per the pre-registration, tallied separately for the note.
TASK_MGMT_ADJACENT = {"TaskOutput", "TaskStop", "Agent", "SendMessage"}
MODIFY_TOOLS = {"Edit", "Write", "file_change"}
DELIVERABLES = ("SOLUTION.md", "findings.md", "REPORT.md")
CHECKERS = {  # repair-style tasks only (H3)
    "01-bugfix": re.compile(r"pytest"),
    "04-terminal": re.compile(r"make(\s+-\S+)*\s+test|\bmake\b\s*$|\bmake\b\s"),
}
CODE_TASKS = {"01-bugfix", "02-synthesis", "03-refactor", "04-terminal"}


def is_deliverable(path_or_arg):
    return any(d in (path_or_arg or "") for d in DELIVERABLES)


def parse_claude(path):
    """Claude Code session JSONL -> ordered [(tool, arg, ts)]."""
    calls = []
    for line in open(path):
        d = json.loads(line)
        t = d.get("type")
        if t in ("system", "user", "result"):
            continue
        if t != "assistant":
            raise ValueError(f"{path}: unrecognized entry type {t!r}")
        ts = d.get("timestamp")
        for blk in d.get("message", {}).get("content", []):
            if blk.get("type") == "tool_use":
                inp = blk.get("input", {})
                arg = inp.get("command") or inp.get("file_path") or ""
                calls.append((blk["name"], arg, ts))
    return calls


def parse_codex(path):
    """Codex --json events -> ordered [(tool, arg, None)].

    command_execution -> Bash-equivalent; file_change -> modification;
    agent_message -> not a tool call.
    """
    calls = []
    seen_ids = set()
    for line in open(path):
        d = json.loads(line)
        t = d.get("type")
        if t in ("thread.started", "turn.started", "turn.completed",
                 "turn.failed", "item.started", "error"):
            continue
        if t != "item.completed":
            raise ValueError(f"{path}: unrecognized event type {t!r}")
        item = d["item"]
        it = item["type"]
        if it == "agent_message":
            continue
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        if it == "command_execution":
            calls.append(("Bash", item.get("command", ""), None))
        elif it == "file_change":
            paths = " ".join(c.get("path", "") for c in item.get("changes", []))
            calls.append(("file_change", paths, None))
        else:
            raise ValueError(f"{path}: unrecognized item type {it!r}")
    return calls


def parse_kimi(path):
    """Kimi Code message log -> ordered [(tool, arg, None)]."""
    calls = []
    for line in open(path):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError(f"{path}: unparseable line")
        role = d.get("role")
        if role in ("tool", "user", "system", "meta"):
            continue
        if role != "assistant":
            raise ValueError(f"{path}: unrecognized role {role!r}")
        for tc in d.get("tool_calls") or []:
            fn = tc["function"]
            args = json.loads(fn["arguments"] or "{}")
            arg = args.get("command") or args.get("path") or args.get("file_path") or ""
            calls.append((fn["name"], arg, None))
    return calls


PARSERS = {"claude-code": parse_claude, "codex": parse_codex, "kimi-code": parse_kimi}


def analyze_run(harness, task, config, run, path):
    calls = PARSERS[harness](path)
    rec = {
        "harness": harness, "task": task, "config": config, "run": run,
        "path": os.path.relpath(path, ROOT),
        "n_calls": len(calls),
        "counts": dict(Counter(c[0] for c in calls)),
        "trace": [f"{n}: {re.sub(chr(10), ' ; ', a)[:100]}" for n, a, _ in calls],
    }
    # classification streams
    mgmt = [c for c in calls if c[0] in TASK_MGMT]
    repo = [c for c in calls if c[0] not in TASK_MGMT]
    rec["n_task_mgmt"] = len(mgmt)
    rec["n_mgmt_adjacent"] = sum(1 for c in calls if c[0] in TASK_MGMT_ADJACENT)
    # H1 / first moves
    rec["first_call"] = calls[0][0] if calls else None
    rec["first_repo_call"] = repo[0][0] if repo else None
    rec["taskcreate_before_repo"] = bool(
        calls and calls[0][0] in TASK_MGMT
        and any(c[0] == "TaskCreate" for c in calls[: len(calls) - len(repo) or None]
                if c[0] in TASK_MGMT)
    ) if repo else False
    # simpler and exact: TaskCreate appears before the first repo-touching call
    if repo:
        first_repo_idx = calls.index(repo[0])
        rec["taskcreate_before_repo"] = any(
            c[0] == "TaskCreate" for c in calls[:first_repo_idx])
    # modifications (excluding deliverables)
    mods = [(i, c) for i, c in enumerate(calls)
            if c[0] in MODIFY_TOOLS and not is_deliverable(c[1])]
    rec["n_modifications"] = len(mods)
    rec["first_mod_idx"] = mods[0][0] if mods else None
    # H3 checker before first modification
    checker = CHECKERS.get(task)
    if checker:
        limit = mods[0][0] if mods else len(calls)
        rec["checker_before_edit"] = any(
            checker.search(a) for n, a, _ in calls[:limit] if n == "Bash")
        rec["ran_checker_ever"] = any(
            checker.search(a) for n, a, _ in calls if n == "Bash")
    # H4 re-reads
    read_paths = [a for n, a, _ in calls if n == "Read"]
    rec["n_reads"] = len(read_paths)
    rec["n_reread_files"] = sum(1 for p, k in Counter(read_paths).items() if k >= 2)
    # H5b test-file reads
    rec["read_test_file"] = any("test" in p.lower() for p in read_paths)
    # H7 time to first modification (Claude Code only, has timestamps)
    rec["secs_to_first_mod"] = None
    if harness == "claude-code" and mods and calls[0][2] and mods[0][1][2]:
        t0 = datetime.fromisoformat(calls[0][2].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(mods[0][1][2].replace("Z", "+00:00"))
        rec["secs_to_first_mod"] = round((t1 - t0).total_seconds(), 1)
    return rec


def main():
    records = []
    for harness, bout in BOUTS.items():
        pattern = os.path.join(ROOT, bout, "*", "*", "run-*", "transcript.jsonl")
        paths = sorted(glob.glob(pattern))
        if not paths:
            raise SystemExit(f"no transcripts under {bout}")
        for p in paths:
            parts = p.split(os.sep)
            run = parts[-2]
            config = parts[-3]
            task = parts[-4]
            records.append(analyze_run(harness, task, config, run, p))
    n = {h: sum(1 for r in records if r["harness"] == h) for h in BOUTS}
    assert n == {"claude-code": 72, "codex": 24, "kimi-code": 24}, n

    cc = [r for r in records if r["harness"] == "claude-code"]
    by = lambda cfg: [r for r in cc if r["config"] == cfg]
    fable, sol, kimi = by("claude-fable-5"), by("gpt-5.6-sol"), by("kimi-k3")
    tasks = sorted({r["task"] for r in cc})

    score = {}
    # H1: first repo-touching call is Bash in >=80% of 72 CC runs
    h1n = sum(1 for r in cc if r["first_repo_call"] == "Bash")
    score["H1"] = {"hit": h1n / 72 >= 0.8, "detail": f"{h1n}/72 runs open with Bash ({h1n/72:.0%}); threshold 80%"}
    # H2a
    tcb = sum(1 for r in sol if r["taskcreate_before_repo"])
    mgmt_share = sum(r["n_task_mgmt"] for r in sol) / sum(r["n_calls"] for r in sol)
    h2a = tcb >= 20 and mgmt_share >= 0.25
    # H2b
    sol_cx = [r for r in records if r["harness"] == "codex"]
    cx_mgmt = sum(r["n_task_mgmt"] for r in sol_cx) / 24
    cc_mgmt = sum(r["n_task_mgmt"] for r in sol) / 24
    h2b = cx_mgmt < 2
    score["H2"] = {"hit": h2a and h2b,
                   "detail": f"(a) TaskCreate-first in {tcb}/24 Sol CC runs, task-mgmt {mgmt_share:.0%} of its calls (thresholds 20, 25%); "
                             f"(b) planning calls/run: Codex {cx_mgmt:.2f} vs CC {cc_mgmt:.1f} (threshold <2)"}
    # H3
    rep = [r for r in records if r["task"] in CHECKERS]
    h3_ok = [r for r in rep if r.get("checker_before_edit")]
    no_mod = [r for r in rep if r["n_modifications"] == 0]
    score["H3"] = {"hit": len(h3_ok) / len(rep) >= 0.9,
                   "detail": f"{len(h3_ok)}/{len(rep)} repair-task runs ran the checker before first tool-based modification "
                             f"({len(h3_ok)/len(rep):.0%}; threshold 90%); {len(no_mod)} runs had no tool-based modification (fixed via Bash), counted per pre-reg definition"}
    # H4
    sol_rr = sum(1 for r in sol if r["n_reread_files"] >= 1)
    fab_rr = sum(1 for r in fable if r["n_reread_files"] >= 1)
    score["H4"] = {"hit": sol_rr >= 16 and fab_rr <= 4,
                   "detail": f"re-read >=1 file: Sol {sol_rr}/24 (>=16), Fable {fab_rr}/24 (<=4); Kimi {sum(1 for r in kimi if r['n_reread_files']>=1)}/24 for reference"}
    # H5
    kimi_low = 0
    per_task_reads = {}
    for t in tasks:
        reads = {c: sum(r["n_reads"] for r in cc if r["task"] == t and r["config"] == c)
                 for c in ("claude-fable-5", "gpt-5.6-sol", "kimi-k3")}
        per_task_reads[t] = reads
        if reads["kimi-k3"] == min(reads.values()) and \
           list(reads.values()).count(reads["kimi-k3"]) == 1:
            kimi_low += 1
        elif reads["kimi-k3"] == min(reads.values()):
            kimi_low += 1  # ties count as lowest; note in output
    kimi_no_test = [r["path"] for r in kimi
                    if r["task"] in CODE_TASKS and not r["read_test_file"]]
    score["H5"] = {"hit": kimi_low >= 6 and len(kimi_no_test) >= 1,
                   "detail": f"Kimi lowest reads on {kimi_low}/8 tasks (>=6, ties count); {len(kimi_no_test)} passing code-task runs never Read a test file"}
    # H6
    sol_top = 0
    per_task_calls = {}
    for t in tasks:
        calls = {c: sum(r["n_calls"] for r in cc if r["task"] == t and r["config"] == c)
                 for c in ("claude-fable-5", "gpt-5.6-sol", "kimi-k3")}
        per_task_calls[t] = calls
        if calls["gpt-5.6-sol"] == max(calls.values()):
            sol_top += 1
    score["H6"] = {"hit": sol_top >= 7, "detail": f"Sol highest tool-call total on {sol_top}/8 tasks (threshold 7)"}
    # H7
    h7 = 0
    h7_detail = {}
    for t in tasks:
        fm = sorted(r["secs_to_first_mod"] for r in fable if r["task"] == t and r["secs_to_first_mod"] is not None)
        sm = sorted(r["secs_to_first_mod"] for r in sol if r["task"] == t and r["secs_to_first_mod"] is not None)
        if not fm or not sm:
            h7_detail[t] = "n/a (a side has no tool-based modification)"
            continue
        med = lambda xs: xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs)//2-1] + xs[len(xs)//2]) / 2
        h7_detail[t] = f"Fable {med(fm):.0f}s vs Sol {med(sm):.0f}s"
        if med(fm) < med(sm):
            h7 += 1
    score["H7"] = {"hit": h7 >= 7, "detail": f"Fable median time-to-first-edit shorter on {h7}/8 tasks (threshold 7): {h7_detail}"}

    with open(os.path.join(OUT_DIR, "mechanism.json"), "w") as f:
        json.dump({"records": records, "scorecard": score,
                   "per_task_reads": per_task_reads,
                   "per_task_calls": per_task_calls}, f, indent=1)

    hits = sum(1 for v in score.values() if v["hit"])
    lines = ["# Mechanism-trace results", "",
             f"Corpus: 120 runs (72 Claude Code, 24 Codex, 24 Kimi Code).",
             f"Scorecard: {hits}/7 hypotheses hit.", ""]
    for h in sorted(score):
        v = score[h]
        lines.append(f"- **{h}: {'HIT' if v['hit'] else 'MISS'}** — {v['detail']}")
    lines += ["", "## Reads per task (Claude Code bout, sum over 3 runs)", "",
              "| task | Fable 5 | Sol | Kimi K3 |", "| --- | --- | --- | --- |"]
    for t in tasks:
        r = per_task_reads[t]
        lines.append(f"| {t} | {r['claude-fable-5']} | {r['gpt-5.6-sol']} | {r['kimi-k3']} |")
    lines += ["", "## Tool calls per task (Claude Code bout, sum over 3 runs)", "",
              "| task | Fable 5 | Sol | Kimi K3 |", "| --- | --- | --- | --- |"]
    for t in tasks:
        r = per_task_calls[t]
        lines.append(f"| {t} | {r['claude-fable-5']} | {r['gpt-5.6-sol']} | {r['kimi-k3']} |")
    lines += ["", "## First repo-touching call by task (Claude Code bout, 9 runs each)", ""]
    for t in tasks:
        fm = Counter(r["first_repo_call"] for r in cc if r["task"] == t)
        lines.append(f"- {t}: {dict(fm)}")
    lines += ["", "## Notable runs", ""]
    for r in cc:
        if r["counts"].get("Agent"):
            lines.append(f"- {r['path']}: {r['n_calls']} calls including "
                         f"{r['counts']['Agent']} Agent (subagent) spawns; counts {r['counts']}")
    outliers = [r for r in cc if r["n_calls"] >= 3 * (sum(x["n_calls"] for x in cc if x["config"] == r["config"] and x["task"] == r["task"]) / 3)]
    lines += ["", f"(runs at >=3x their cell mean: {[r['path'] for r in outliers] or 'none'})"]
    with open(os.path.join(OUT_DIR, "mechanism.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:40]))


if __name__ == "__main__":
    main()
