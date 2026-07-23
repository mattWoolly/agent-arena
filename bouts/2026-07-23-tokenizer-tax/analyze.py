#!/usr/bin/env python3
"""Part A + Part B of the 2026-07-23-tokenizer-tax bout.

Counts identical content under claude-sonnet-4-6 (old tokenizer) and
claude-sonnet-5 (new tokenizer) via /v1/messages/count_tokens, over the 30
public Sonnet 5 runs from bouts/2026-07-07-ladder-noise. Writes counts.json.

Run from the repo root:  python3 bouts/2026-07-23-tokenizer-tax/analyze.py
Requires ANTHROPIC_API_KEY in the environment (source ~/.secrets).
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOUT = Path(__file__).resolve().parent
LADDER = ROOT / "bouts" / "2026-07-07-ladder-noise"
MODELS = ["claude-sonnet-4-6", "claude-sonnet-5"]
TASKS = ["01-bugfix", "02-synthesis", "03-refactor", "04-terminal",
         "05-review", "06-instructions"]

API = "https://api.anthropic.com/v1/messages/count_tokens"
KEY = os.environ["ANTHROPIC_API_KEY"]

calls = 0

def count(model: str, text: str) -> int:
    """Count tokens for text under model; retries on 429/5xx."""
    global calls
    body = json.dumps({"model": model,
                       "messages": [{"role": "user", "content": text}]}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "content-type": "application/json",
        "x-api-key": KEY,
        "anthropic-version": "2023-06-01"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                calls += 1
                return json.load(r)["input_tokens"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 529) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def extract_run(tdir: Path):
    """Extract per-category text from one run's transcript.jsonl."""
    prose, tool_inputs, tool_results = [], [], []
    for line in open(tdir / "transcript.jsonl", encoding="utf-8"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = d.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        if d.get("type") == "assistant":
            for b in content:
                if b.get("type") == "text" and b.get("text"):
                    prose.append(b["text"])
                elif b.get("type") == "tool_use" and b.get("name") in ("Edit", "Write"):
                    inp = b.get("input") or {}
                    for k in ("content", "old_string", "new_string", "file_text"):
                        if isinstance(inp.get(k), str):
                            tool_inputs.append(inp[k])
        elif d.get("type") == "user":
            for b in content:
                if b.get("type") != "tool_result":
                    continue
                c = b.get("content")
                if isinstance(c, str):
                    tool_results.append(c)
                elif isinstance(c, list):
                    for cb in c:
                        if isinstance(cb, dict) and cb.get("type") == "text":
                            tool_results.append(cb.get("text") or "")
    return "\n".join(prose), "\n".join(tool_inputs), "\n".join(tool_results)


def workspace_text(ws: Path) -> str:
    parts = []
    for p in sorted(ws.rglob("*")):
        if not p.is_file() or ".git" in p.parts:
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        parts.append(t)
    return "\n".join(parts)


def ratio_pair(text: str):
    """Return (old_count, new_count) or None for empty/tiny text."""
    if len(text.strip()) < 200:
        return None
    old = count(MODELS[0], text)
    new = count(MODELS[1], text)
    return old, new


def main():
    out = {"generated_by": "analyze.py", "models": MODELS,
           "part_b": {}, "categories": {}, "per_run_blend": [],
           "task_prompts": {}}

    # ---- Part B: method validation ----
    for name, fname in [("udhr_english", "partb_udhr_eng.txt"),
                        ("sqlite_utils_db_py", "partb_dbpy.txt")]:
        text = (BOUT / fname).read_text(encoding="utf-8")
        old, new = ratio_pair(text)
        out["part_b"][name] = {"old": old, "new": new,
                               "ratio": round(new / old, 4),
                               "chars": len(text)}
        print(f"[part B] {name}: {old} -> {new}  ratio {new/old:.4f}",
              flush=True)

    # ---- task prompts ----
    tp_old = tp_new = 0
    for task in TASKS:
        text = (ROOT / "tasks" / task / "PROMPT.md").read_text(encoding="utf-8")
        old, new = ratio_pair(text)
        out["task_prompts"][task] = {"old": old, "new": new}
        tp_old += old
        tp_new += new
    out["categories"]["task-prompts"] = {"old": tp_old, "new": tp_new,
                                         "ratio": round(tp_new / tp_old, 4)}
    print(f"[cat] task-prompts ratio {tp_new/tp_old:.4f}", flush=True)

    # ---- per-run extraction over the 30 Sonnet 5 ladder runs ----
    cat_tot = {c: [0, 0] for c in
               ("assistant-prose", "tool-input-code", "tool-results", "diffs")}
    for task in TASKS:
        prompt_text = (ROOT / "tasks" / task / "PROMPT.md").read_text(encoding="utf-8")
        for k in range(1, 6):
            rdir = LADDER / task / "claude-sonnet-5" / f"run-{k}"
            prose, tin, tres = extract_run(rdir)
            diff = ""
            dp = rdir / "workspace.diff"
            if dp.exists():
                try:
                    diff = dp.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    diff = dp.read_text(encoding="utf-8", errors="replace")
            for cname, text in [("assistant-prose", prose),
                                ("tool-input-code", tin),
                                ("tool-results", tres),
                                ("diffs", diff)]:
                pair = ratio_pair(text)
                if pair:
                    cat_tot[cname][0] += pair[0]
                    cat_tot[cname][1] += pair[1]
            # per-run blend: what the conversation actually contained
            blend_text = "\n".join([prompt_text, prose, tin, tres])
            b_old, b_new = ratio_pair(blend_text)
            out["per_run_blend"].append(
                {"task": task, "run": k, "old": b_old, "new": b_new,
                 "ratio": round(b_new / b_old, 4)})
            print(f"[blend] {task} run-{k}: {b_old} -> {b_new} "
                  f"({b_new/b_old:.4f})", flush=True)

    for cname, (o, n) in cat_tot.items():
        out["categories"][cname] = {"old": o, "new": n,
                                    "ratio": round(n / o, 4) if o else None}
        print(f"[cat] {cname} ratio {n/o:.4f}" if o else f"[cat] {cname} empty",
              flush=True)

    # ---- workspace code (run-1 of each task, sonnet-5 arm) ----
    wo = wn = 0
    for task in TASKS:
        ws = LADDER / task / "claude-sonnet-5" / "run-1" / "workspace"
        pair = ratio_pair(workspace_text(ws))
        if pair:
            wo += pair[0]
            wn += pair[1]
    out["categories"]["workspace-code"] = {"old": wo, "new": wn,
                                           "ratio": round(wn / wo, 4)}
    print(f"[cat] workspace-code ratio {wn/wo:.4f}", flush=True)

    blends = [r["ratio"] for r in out["per_run_blend"]]
    out["blend_summary"] = {
        "mean": round(sum(blends) / len(blends), 4),
        "min": min(blends), "max": max(blends), "n": len(blends)}
    out["api_calls"] = calls
    (BOUT / "counts.json").write_text(json.dumps(out, indent=1))
    print(f"\nblend mean {out['blend_summary']['mean']} "
          f"[{out['blend_summary']['min']}, {out['blend_summary']['max']}] "
          f"over {len(blends)} runs; {calls} count_tokens calls", flush=True)


if __name__ == "__main__":
    sys.exit(main())
