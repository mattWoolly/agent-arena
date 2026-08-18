#!/usr/bin/env python3
"""Numeric-reliability analysis for the incidental-arithmetic tasks (13/14/15).

Reads a bout directory and, for every run of those tasks, joins three sources:

  grade.txt        -> per-item verdicts (ITEM lines), gates, FLAG/CHAIN lines
  grade_exit       -> the task-level pass the wild would see
  transcript.jsonl -> what the agent actually did: compute-capable tool calls,
                      and whether each expected value ever appeared in a tool
                      RESULT before landing in the deliverable

and emits per-run records plus per-(task, model) aggregates for the three
headline metrics:

  item_error_rate   wrong-or-missing numeric items / numeric items
  tool_derived_rate items whose expected value appeared in tool output
  silent_error_rate runs with grade_exit==0 AND >=1 wrong numeric item

Attribution caveat (disclosed in the bout DESIGN): "tool-derived" means the
correct value was PRESENT in some tool result — a necessary, not sufficient,
sign the agent computed it mechanically. Values only ever seen in the final
written artifact count as head-derived. This is a conservative lower bound on
mental arithmetic, not an exact attribution.

usage: numcheck.py <bout-dir> [--json <out.json>]
"""
import json
import os
import re
import sys
from collections import defaultdict

COMPUTE_RE = re.compile(
    r"python3?\b|\bbc\b|\bawk\b|\bperl\b|\bnode\b|\bruby\b|\bsqlite3?\b|"
    r"\bdatediff\b|\bpaste\b.*\bbc\b", re.I)
ITEM_RE = re.compile(
    r"^ITEM (\S+) (OK|WRONG|MISSING) expected=(\S+) got=(\S+)(?: class=(\S+))?")
NUM_TASKS_RE = re.compile(r"^1[345]-")


def iter_runs(bout):
    for task in sorted(os.listdir(bout)):
        tdir = os.path.join(bout, task)
        if not os.path.isdir(tdir) or not NUM_TASKS_RE.match(task):
            continue
        for model in sorted(os.listdir(tdir)):
            mdir = os.path.join(tdir, model)
            if not os.path.isdir(mdir):
                continue
            subs = [d for d in sorted(os.listdir(mdir)) if d.startswith("run-")]
            for sub in (subs or ["."]):
                rdir = os.path.join(mdir, sub) if sub != "." else mdir
                if os.path.exists(os.path.join(rdir, "grade.txt")):
                    yield task, model, (sub if sub != "." else "run-1"), rdir


def value_variants(v):
    """Ways the same value can appear in tool output: raw, comma-grouped,
    bare digits (no separators), 2dp/1dp float forms."""
    out = {v}
    plain = v.replace(",", "")
    out.add(plain)
    try:
        f = float(plain)
        out.add(f"{f:,.2f}")
        out.add(f"{f:.2f}")
        out.add(f"{f:.1f}")
        if f == int(f):
            out.add(str(int(f)))
            out.add(f"{int(f):,}")
    except ValueError:
        pass
    return {x for x in out if x and x != "-"}


def transcript_streams(rdir):
    """(compute_calls, tool_result_text) from a stream-json transcript."""
    calls = []
    results = []
    path = os.path.join(rdir, "transcript.jsonl")
    if not os.path.exists(path):
        return calls, ""
    with open(path) as f:
        for line in f:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = ev.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    calls.append({"name": block.get("name", ""),
                                  "input": json.dumps(block.get("input", {}))})
                elif block.get("type") == "tool_result":
                    c = block.get("content")
                    if isinstance(c, list):
                        results.append(" ".join(
                            str(b.get("text", "")) for b in c if isinstance(b, dict)))
                    else:
                        results.append(str(c))
    return calls, "\n".join(results)


def analyze_run(rdir):
    rec = {"gates_ok": None, "gates_total": None, "grade_pass": None,
           "items": [], "flags": {}, "chain_broken": 0, "chain_total": 0}
    ge = os.path.join(rdir, "grade_exit")
    if os.path.exists(ge):
        rec["grade_pass"] = open(ge).read().strip() == "0"
    for line in open(os.path.join(rdir, "grade.txt")):
        m = ITEM_RE.match(line)
        if m:
            rec["items"].append({"id": m.group(1), "status": m.group(2),
                                 "expected": m.group(3), "got": m.group(4),
                                 "class": m.group(5) or ""})
        elif line.startswith("SCORE:"):
            a, b = line.split()[1].split("/")
            rec["gates_ok"], rec["gates_total"] = int(a), int(b)
        elif line.startswith("FLAG "):
            _, name, val = line.split()
            rec["flags"][name] = val
        elif line.startswith("CHAIN "):
            rec["chain_total"] += 1
            if line.split()[2] != "consistent":
                rec["chain_broken"] += 1

    calls, result_text = transcript_streams(rdir)
    compute_calls = [c for c in calls
                     if c["name"] == "Bash" and COMPUTE_RE.search(c["input"])]
    # normalize separators out of the searched text once
    flat = result_text.replace(",", "")
    for item in rec["items"]:
        variants = value_variants(item["expected"])
        item["tool_derived"] = any(v.replace(",", "") in flat for v in variants)
    rec["compute_calls"] = len(compute_calls)
    rec["tool_calls"] = len(calls)
    rec["tooled"] = bool(compute_calls)
    wrong = sum(1 for i in rec["items"] if i["status"] != "OK")
    rec["numeric_total"] = len(rec["items"])
    rec["numeric_ok"] = rec["numeric_total"] - wrong
    rec["silent_error"] = bool(rec["grade_pass"]) and wrong > 0
    return rec


def main():
    bout = sys.argv[1]
    out_json = None
    if "--json" in sys.argv:
        out_json = sys.argv[sys.argv.index("--json") + 1]
    runs = []
    for task, model, run, rdir in iter_runs(bout):
        rec = analyze_run(rdir)
        rec.update({"task": task, "model": model, "run": run})
        runs.append(rec)
    if not runs:
        print("no numeric-task runs found under", bout)
        return

    agg = defaultdict(lambda: {"runs": 0, "items": 0, "wrong": 0,
                               "tool_derived": 0, "tooled_runs": 0,
                               "silent": 0, "passes": 0})
    for r in runs:
        a = agg[(r["task"], r["model"])]
        a["runs"] += 1
        a["items"] += r["numeric_total"]
        a["wrong"] += r["numeric_total"] - r["numeric_ok"]
        a["tool_derived"] += sum(1 for i in r["items"] if i["tool_derived"])
        a["tooled_runs"] += 1 if r["tooled"] else 0
        a["silent"] += 1 if r["silent_error"] else 0
        a["passes"] += 1 if r["grade_pass"] else 0

    hdr = f"{'task':<22} {'model':<18} {'runs':>4} {'pass':>4} {'items':>5} " \
          f"{'wrong':>5} {'err%':>6} {'tool%':>6} {'tooled':>6} {'silent':>6}"
    print(hdr)
    print("-" * len(hdr))
    for (task, model), a in sorted(agg.items()):
        err = 100 * a["wrong"] / a["items"] if a["items"] else 0
        tld = 100 * a["tool_derived"] / a["items"] if a["items"] else 0
        print(f"{task:<22} {model:<18} {a['runs']:>4} {a['passes']:>4} "
              f"{a['items']:>5} {a['wrong']:>5} {err:>5.1f}% {tld:>5.1f}% "
              f"{a['tooled_runs']:>6} {a['silent']:>6}")

    if out_json:
        with open(out_json, "w") as f:
            json.dump({"runs": runs}, f, indent=2)
        print(f"\nwrote {out_json}")


if __name__ == "__main__":
    main()
