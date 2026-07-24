#!/usr/bin/env python3
"""Forensics of the single spontaneous delegation in the 120-run corpus
(see DESIGN.md). Parses the target run and its two sibling runs, extracts
the subagent panel timeline, per-run cost records, findings sets, and
judge medians; emits excursion.json and excursion.md.

Finding matches are hand-adjudicated: the first pass writes materials.md
and stops if adjudications.json is missing; after adjudication the second
pass computes the H1-H6 scorecard. Fails loudly on unrecognized events.
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CELL = "bouts/2026-07-17-fable-sol-kimi/05-review-transplant"
TARGET = f"{CELL}/gpt-5.6-sol/run-2"
SIBLINGS = [f"{CELL}/gpt-5.6-sol/run-1", f"{CELL}/gpt-5.6-sol/run-3"]
ANCHORS = [f"{CELL}/claude-fable-5/run-{i}" for i in (1, 2, 3)] + \
          [f"{CELL}/kimi-k3/run-{i}" for i in (1, 2, 3)]

KNOWN_SYSTEM = {"init", "task_progress", "background_tasks_changed",
                "task_started", "task_updated", "task_notification"}


def ts_parse(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def parse_transcript(path):
    """Claude Code session JSONL -> flat ordered event list."""
    events = []
    for line in open(path):
        d = json.loads(line)
        t = d.get("type")
        if t == "system":
            st = d.get("subtype")
            if st not in KNOWN_SYSTEM:
                raise ValueError(f"{path}: unrecognized system subtype {st!r}")
            if st in ("task_started", "task_updated", "task_notification"):
                events.append({"kind": st, "ts": d.get("timestamp"),
                               "task_id": d.get("task_id"),
                               "tool_use_id": d.get("tool_use_id"),
                               "description": d.get("description"),
                               "prompt": d.get("prompt"),
                               "patch": d.get("patch"),
                               "summary": d.get("summary"),
                               "usage": d.get("usage")})
        elif t == "assistant":
            ts = d.get("timestamp")
            for blk in d.get("message", {}).get("content", []):
                if blk.get("type") == "tool_use":
                    events.append({"kind": "tool_use", "ts": ts,
                                   "id": blk["id"], "name": blk["name"],
                                   "input": blk.get("input", {})})
                elif blk.get("type") not in ("text", "thinking"):
                    raise ValueError(
                        f"{path}: unrecognized assistant block {blk.get('type')!r}")
        elif t == "user":
            ts = d.get("timestamp")
            content = d.get("message", {}).get("content")
            if not isinstance(content, list):
                raise ValueError(f"{path}: non-list user content")
            for blk in content:
                if blk.get("type") != "tool_result":
                    raise ValueError(
                        f"{path}: unrecognized user block {blk.get('type')!r}")
                text = blk.get("content")
                if isinstance(text, list):
                    text = "\n".join(x.get("text", "") for x in text
                                     if isinstance(x, dict))
                events.append({"kind": "tool_result", "ts": ts,
                               "tool_use_id": blk.get("tool_use_id"),
                               "text": text or ""})
        elif t == "result":
            events.append({"kind": "result", "ts": d.get("timestamp"),
                           "text": d.get("result", "")})
        else:
            raise ValueError(f"{path}: unrecognized entry type {t!r}")
    return events


def run_costs(run):
    """(cli_cost, real_cost_or_None, wall) for one run dir."""
    m = json.load(open(os.path.join(ROOT, run, "metrics.json")))
    proxy = os.path.join(ROOT, run, "proxy_usage.jsonl")
    real = None
    if os.path.exists(proxy):
        real = sum(json.loads(l)["response_cost"] for l in open(proxy))
    return {"run": run, "cli_cost": m["total_cost_usd"],
            "real_cost": round(real, 4) if real is not None else None,
            "wall": m["wall_seconds"], "tool_calls": m["tool_calls_total"],
            "out_tok": m["output_tokens"]}


def findings_of(run):
    """Parse `- path:line desc` lines from the run's findings.md."""
    p = os.path.join(ROOT, run, "workspace", "findings.md")
    out = []
    for line in open(p):
        line = line.strip()
        if line.startswith("- "):
            out.append(line[2:])
    return out


def judge_medians(run):
    j = json.load(open(os.path.join(ROOT, run, "judge.json")))
    return j["median"]


def build_panel(events):
    """Reconstruct the subagent panel: spawns, rounds, lifetimes.

    System events carry no timestamps: a round's start is the timestamp of
    the tool_use (Agent or SendMessage) that opened it; its end is the
    task_updated patch's end_time (epoch ms, converted to UTC).
    """
    spawns = [e for e in events if e["kind"] == "tool_use" and e["name"] == "Agent"]
    use_ts = {e["id"]: e["ts"] for e in events if e["kind"] == "tool_use"}
    tasks = {}
    pending = {}  # task_id -> round awaiting its end_time patch
    for e in events:
        if e["kind"] == "task_started":
            t = tasks.setdefault(e["task_id"], {"task_id": e["task_id"],
                                                "rounds": []})
            r = {"tool_use_id": e["tool_use_id"],
                 "prompt": e["prompt"],
                 "description": e["description"],
                 "started": use_ts.get(e["tool_use_id"]), "completed": None}
            t["rounds"].append(r)
            pending[e["task_id"]] = r
        elif e["kind"] == "task_updated":
            end_ms = (e.get("patch") or {}).get("end_time")
            if end_ms and e["task_id"] in pending:
                pending[e["task_id"]]["completed"] = datetime.fromtimestamp(
                    end_ms / 1000, tz=timezone.utc).isoformat()
                del pending[e["task_id"]]
        elif e["kind"] == "task_notification":
            t = tasks[e["task_id"]]
            for r in t["rounds"]:
                if r["tool_use_id"] == e["tool_use_id"]:
                    r["report"] = e["summary"]
                    r["usage"] = e["usage"]
    # attach spawn metadata (model, bg flag) by exact tool_use_id match
    for s in spawns:
        for t in tasks.values():
            if t["rounds"][0]["tool_use_id"] == s["id"]:
                t["model"] = s["input"].get("model")
                t["background"] = s["input"].get("run_in_background")
                t["spawn_prompt"] = s["input"].get("prompt")
    return tasks


def lifetimes_overlap(tasks):
    """Per DESIGN: intervals intersect > 10% of the shorter lifetime."""
    ivals = []
    for t in tasks.values():
        start = ts_parse(t["rounds"][0]["started"])
        ends = [ts_parse(r["completed"]) for r in t["rounds"] if r["completed"]]
        if not ends:
            raise ValueError(f"task {t['task_id']} never completed")
        ivals.append((t["task_id"], start, max(ends)))
    pairs = []
    for i in range(len(ivals)):
        for k in range(i + 1, len(ivals)):
            a, b = ivals[i], ivals[k]
            lo, hi = max(a[1], b[1]), min(a[2], b[2])
            inter = (hi - lo).total_seconds()
            shorter = min((a[2] - a[1]).total_seconds(),
                          (b[2] - b[1]).total_seconds())
            pairs.append({"pair": (a[0], b[0]),
                          "intersect_s": round(max(inter, 0), 1),
                          "shorter_s": round(shorter, 1),
                          "overlaps": inter > 0.1 * shorter})
    return ivals, pairs


def subagent_outputs(events):
    """Texts returned by the panel: results of Agent/TaskOutput/TaskGet/
    SendMessage calls plus task notifications."""
    by_id = {e["id"]: e for e in events if e["kind"] == "tool_use"}
    outs = []
    for e in events:
        if e["kind"] == "tool_result" and e["tool_use_id"] in by_id:
            src = by_id[e["tool_use_id"]]
            if src["name"] in ("Agent", "TaskOutput", "TaskGet", "SendMessage",
                               "TaskList", "TaskStop"):
                outs.append({"via": src["name"], "ts": e["ts"],
                             "input": src["input"], "text": e["text"]})
    return outs


def main():
    events = parse_transcript(os.path.join(ROOT, TARGET, "transcript.jsonl"))
    tasks = build_panel(events)
    ivals, pairs = lifetimes_overlap(tasks)
    outs = subagent_outputs(events)
    costs = [run_costs(r) for r in [TARGET] + SIBLINGS + ANCHORS]
    findings = {r: findings_of(r) for r in [TARGET] + SIBLINGS}
    judges = {r: judge_medians(r) for r in [TARGET] + SIBLINGS}

    # main-thread Read coverage of delegated src files (H6)
    src_dir = os.path.join(ROOT, TARGET, "workspace", "src")
    src_files = sorted(os.listdir(src_dir))
    reads = [e["input"].get("file_path", "") for e in events
             if e["kind"] == "tool_use" and e["name"] == "Read"]
    read_src = {f for f in src_files if any(f in p for p in reads)}

    adj_path = os.path.join(OUT_DIR, "adjudications.json")
    if not os.path.exists(adj_path):
        # first pass: dump materials for hand adjudication, then stop
        lines = ["# Adjudication materials (raw panel outputs)", ""]
        for t in tasks.values():
            lines += [f"## Task {t['task_id']} ({t['rounds'][0]['description']}, "
                      f"model={t.get('model')})", ""]
            for i, r in enumerate(t["rounds"]):
                lines += [f"### Round {i+1} prompt", "", r["prompt"] or "", "",
                          f"### Round {i+1} report (usage {r.get('usage')})",
                          "```", r.get("report") or "(none)", "```", ""]
        lines += ["## Returned outputs (chronological)", ""]
        for o in outs:
            lines += [f"### via {o['via']} at {o['ts']}", "```",
                      (o["text"] or "")[:6000], "```", ""]
        lines += ["## Final findings.md (target)", ""]
        lines += [f"- {f}" for f in findings[TARGET]]
        for s in SIBLINGS:
            lines += ["", f"## Final findings.md ({s.rsplit('/',1)[1]})", ""]
            lines += [f"- {f}" for f in findings[s]]
        with open(os.path.join(OUT_DIR, "materials.md"), "w") as f:
            f.write("\n".join(lines) + "\n")
        print("materials.md written; create adjudications.json then rerun")
        return

    adj = json.load(open(adj_path))
    score = {}
    # H1: no two lifetimes overlap
    any_overlap = any(p["overlaps"] for p in pairs)
    n_over = sum(1 for p in pairs if p["overlaps"])
    score["H1"] = {"hit": not any_overlap,
                   "detail": f"{n_over}/{len(pairs)} lifetime pairs overlap "
                             f"(hit requires 0); spawns and completions in excursion.json"}
    # H2: cost >= 5x sibling median, wall >= 3x
    t_c = costs[0]
    sib = sorted(c["real_cost"] for c in costs[1:3])
    sib_med = sum(sib) / 2
    sib_wall = sorted(c["wall"] for c in costs[1:3])
    wall_med = sum(sib_wall) / 2
    cm = t_c["real_cost"] / sib_med
    wm = t_c["wall"] / wall_med
    score["H2"] = {"hit": cm >= 5 and wm >= 3,
                   "detail": f"real cost ${t_c['real_cost']:.2f} vs sibling median "
                             f"${sib_med:.2f} ({cm:.1f}x, threshold 5x); wall "
                             f"{t_c['wall']:.0f}s vs {wall_med:.0f}s ({wm:.1f}x, threshold 3x)"}
    # H3: >=1 finding by one subagent unmatched in another's report
    score["H3"] = {"hit": bool(adj["h3_disagreements"]),
                   "detail": f"{len(adj['h3_disagreements'])} cross-subagent "
                             f"disagreements adjudicated (hit requires >=1)"}
    # H4: >=1 subagent finding missing from final findings.md
    score["H4"] = {"hit": bool(adj["h4_dropped"]),
                   "detail": f"{len(adj['h4_dropped'])} subagent findings "
                             f"absent from final findings.md (hit requires >=1)"}
    # H5: siblings at ceiling and target does not out-find them
    ceiling = all(all(v == 2 for v in judges[s].values()) for s in SIBLINGS)
    n_t = len(findings[TARGET])
    n_max = max(len(findings[s]) for s in SIBLINGS)
    score["H5"] = {"hit": ceiling and n_t <= n_max,
                   "detail": f"siblings at judge ceiling: {ceiling}; findings "
                             f"count target {n_t} vs sibling max {n_max} "
                             f"(hit requires ceiling and target <= max)"}
    # H6: main thread Read every delegated src file itself
    missed = [f for f in src_files if f not in read_src]
    score["H6"] = {"hit": not missed,
                   "detail": f"src files: {src_files}; Read by main thread: "
                             f"{sorted(read_src)}; not Read: {missed} (hit requires none missed)"}

    out = {"target": TARGET, "siblings": SIBLINGS,
           "panel": {tid: t for tid, t in tasks.items()},
           "lifetimes": [{"task_id": i[0], "start": i[1].isoformat(),
                          "end": i[2].isoformat()} for i in ivals],
           "overlap_pairs": pairs,
           "costs": costs, "findings": findings, "judge_medians": judges,
           "subagent_outputs": outs, "adjudications": adj,
           "scorecard": score,
           "trace": [f"{e.get('name') or e['kind']}: "
                     f"{json.dumps(e.get('input','') , default=str)[:120]}"
                     for e in events if e["kind"] == "tool_use"]}
    with open(os.path.join(OUT_DIR, "excursion.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)

    hits = sum(1 for v in score.values() if v["hit"])
    lines = ["# Excursion forensics results", "",
             f"Target: `{TARGET}` (97 tool calls, 4 subagent spawns).",
             f"Scorecard: {hits}/6 hypotheses hit.", ""]
    for h in sorted(score):
        v = score[h]
        lines.append(f"- **{h}: {'HIT' if v['hit'] else 'MISS'}** — {v['detail']}")
    lines += ["", "## Panel timeline", ""]
    for t in sorted(tasks.values(), key=lambda x: x["rounds"][0]["started"]):
        for i, r in enumerate(t["rounds"]):
            lines.append(f"- {r['started']} -> {r['completed']} | "
                         f"{r['description']} (model={t.get('model')}, "
                         f"round {i+1})")
    lines += ["", "## Cost table (real = metered proxy usage; cli = harness display)", "",
              "| run | real $ | cli $ | wall s | calls | out-tok |",
              "| --- | --- | --- | --- | --- | --- |"]
    for c in costs:
        lines.append(f"| {c['run'].split('/', 2)[2]} | "
                     f"{c['real_cost'] if c['real_cost'] is not None else 'n/a (native)'} | "
                     f"{c['cli_cost']:.2f} | {c['wall']:.0f} | "
                     f"{c['tool_calls']} | {c['out_tok']} |")
    with open(os.path.join(OUT_DIR, "excursion.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
