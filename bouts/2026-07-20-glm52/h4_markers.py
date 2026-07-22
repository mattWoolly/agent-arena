#!/usr/bin/env python3
"""H4 markers for the GLM-5.2 bout (DESIGN.md), reusing the pre-registered
mechanism-trace definitions verbatim via import from analyze.py.

Emits h4_markers.json: per-run records for glm-5.2 cells plus the three
pre-registered aggregates (re-read runs, Edit-vs-Write totals, task-mgmt
calls per run).
"""
import glob
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
ANALYZE = os.path.join(ROOT, "analysis", "2026-07-19-mechanism-trace", "analyze.py")

spec = importlib.util.spec_from_file_location("mtrace", ANALYZE)
mtrace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mtrace)

records = []
for path in sorted(glob.glob(os.path.join(HERE, "*", "glm-5.2", "run-*", "transcript.jsonl"))):
    rel = os.path.relpath(path, HERE)
    task, config, run, _ = rel.split(os.sep)
    records.append(mtrace.analyze_run("claude-code", task, config, run, path))

n = len(records)
reread_runs = sum(1 for r in records if r["n_reread_files"] >= 1)
edits = sum(r["counts"].get("Edit", 0) for r in records)
writes = sum(r["counts"].get("Write", 0) for r in records)
task_mgmt_per_run = sum(r["n_task_mgmt"] for r in records) / n if n else 0.0

out = {
    "n_runs": n,
    "h4a_reread_runs": reread_runs,
    "h4a_hit": reread_runs <= 4,
    "h4b_edit_calls": edits,
    "h4b_write_calls": writes,
    "h4b_hit": edits >= writes,
    "h4c_task_mgmt_per_run": round(task_mgmt_per_run, 2),
    "h4c_hit": task_mgmt_per_run < 2,
    "records": records,
}
with open(os.path.join(HERE, "h4_markers.json"), "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "records"}, indent=1))
