#!/usr/bin/env python3
"""04-terminal walkthrough reanalysis (see DESIGN.md).

Parses all 19 public runs of 04-terminal across three transcript formats,
pairs every tool call with its result, classifies checker executions
against the four ground-truth faults, and emits walkthrough.json (per-run
timelines, fault-discovery order, proactive-scan candidates, SOLUTION.md
mappings) and walkthrough.md (hypothesis scorecard + tables).

Hand adjudications live in adjudications.json (created after reviewing the
script's candidates; every entry quotes the evidence verbatim). The script
merges them when present. Fails loudly on unrecognized events.
"""
import json
import glob
import os
import re
from collections import Counter
from datetime import datetime

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

CELLS = [
    # (harness, bout, config, label)
    ("claude-code", "bouts/2026-07-17-fable-sol-kimi", "claude-fable-5", "Fable 5 / Claude Code"),
    ("claude-code", "bouts/2026-07-17-fable-sol-kimi", "gpt-5.6-sol", "Sol / Claude Code"),
    ("claude-code", "bouts/2026-07-17-fable-sol-kimi", "kimi-k3", "Kimi K3 / Claude Code"),
    ("codex", "bouts/2026-07-17-sol-codex-homegame", "gpt-5.6-sol-codex", "Sol / Codex"),
    ("kimi-code", "bouts/2026-07-18-kimi-homegame", "kimi-k3-kimicode", "Kimi K3 / Kimi Code"),
    ("claude-code", "bouts/2026-07-20-glm52", "glm-5.2", "GLM-5.2 / Claude Code"),
    ("claude-code", "bouts/2026-07-20-glm52", "claude-opus-4-8", "Opus 4.8 / Claude Code"),
]

TASK_MGMT = {"TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskOutput",
             "TaskStop", "update_plan"}

def is_checker_cmd(cmd):
    """True if any sub-command actually EXECUTES the checker chain.

    Tokenizes on ; && || | and newlines, then inspects each sub-command's
    leading tokens, so `cat scripts/run_checks.sh` or a printf that merely
    mentions the script do not count as checker executions.
    """
    cmd = cmd or ""
    # unwrap Codex's `/bin/bash -lc '...'` / `bash -c "..."` envelope
    m = re.match(r"^\s*(?:/\S*/)?(?:ba)?sh\s+-l?c\s+(['\"])(.*)\1\s*$",
                 cmd, re.S)
    if m:
        cmd = m.group(2)
    for sub in re.split(r"[;\n]|&&|\|\||\|", cmd):
        toks = sub.strip().split()
        # skip env-var prefixes like FOO=bar
        while toks and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]):
            toks = toks[1:]
        if not toks:
            continue
        head = toks[0]
        base = os.path.basename(head)
        if base == "make":
            return True
        if base == "run_checks.sh":
            return True
        if base in ("bash", "sh") and len(toks) > 1 and \
                os.path.basename(toks[1]) == "run_checks.sh":
            return True
        if base in ("python", "python3") and any(
                os.path.basename(t) == "validate_config.py" for t in toks[1:2]):
            return True
    return False


# Fault signatures in checker OUTPUT (ground truth, DESIGN.md). F3's
# real-world signature: the kernel fails to resolve the CRLF-suffixed
# shebang, so make reports the script itself as missing (Error 127) even
# though it exists; "bad interpreter" appears only in some bash paths.
FAULT_SIGS = [
    ("F1-makefile-separator", re.compile(r"missing separator")),
    ("F2-exec-bit", re.compile(r"[Pp]ermission denied")),
    ("F3-crlf", re.compile(
        r"bad interpreter|run_checks\.sh: No such file or directory|"
        r"cannot execute: required file not found")),
    ("F4-json-comma", re.compile(
        r"Expecting property name|JSONDecodeError|json\.decoder|Extra data|"
        r"Expecting ',' delimiter|Illegal trailing comma|"
        r"validate_config\.py\", line")),
    # NOT planted by the task: the Kimi Code driver's isolated HOME
    # (auth isolation, see bouts/2026-07-18-kimi-homegame/DESIGN.md) drops
    # ~/.local from python3's user site-packages, so pytest goes missing
    # in that harness's runs only.
    ("F5-env-pytest-unplanted", re.compile(r"No module named pytest")),
]
PLANTED = {"F1-makefile-separator", "F2-exec-bit", "F3-crlf", "F4-json-comma"}
GREEN_RE = re.compile(r"\bpassed\b|all checks passed")

# Fault-targeting events: (fault, kind, regex on command/path).
TARGET_RES = [
    ("F1-makefile-separator", "fix", re.compile(r"(sed|printf|awk).*Makefile|Makefile.*(sed -i|\\t)")),
    ("F1-makefile-separator", "edit", re.compile(r"Makefile$")),
    ("F1-makefile-separator", "scan", re.compile(r"cat(\s+-A|\s+-e)?\s+\S*Makefile|sed -n .*l.*Makefile|od .*Makefile|grep .*Makefile")),
    ("F2-exec-bit", "fix", re.compile(r"chmod\s+(\+x|a\+x|u\+x|755|0?755)\s+\S*run_checks")),
    ("F2-exec-bit", "scan", re.compile(r"ls\s+-l\S*\s+\S*(scripts|run_checks)|stat\s+\S*run_checks|test -x")),
    ("F3-crlf", "fix", re.compile(r"(sed -i|dos2unix|tr -d).*(\\r|run_checks)|sed -i .*run_checks")),
    ("F3-crlf", "edit", re.compile(r"run_checks\.sh$")),
    ("F3-crlf", "scan", re.compile(r"file\s+\S*run_checks|cat -A|cat -e|od -c|sed -n .*l|grep .*\$'\\\\r'|grep -rl?I?U? .*\\\\r|xxd")),
    ("F4-json-comma", "fix", re.compile(r"sed -i .*config\.json")),
    ("F4-json-comma", "edit", re.compile(r"data/config\.json$")),
    ("F4-json-comma", "scan", re.compile(r"cat\s+\S*config\.json|json\.load|python3? -m json\.tool|validate_config")),
]

DELIVER_RE = re.compile(r"SOLUTION\.md")

SOLUTION_KEYS = {
    "F1-makefile-separator": re.compile(r"separator|makefile|tab|indent", re.I),
    "F2-exec-bit": re.compile(r"exec|chmod|\+x|permission|executable", re.I),
    "F3-crlf": re.compile(r"crlf|carriage|line ending|\\r|dos2unix|windows.{0,20}line|\^M", re.I),
    "F4-json-comma": re.compile(r"trailing comma|comma|json", re.I),
}


def iso(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def parse_claude(path):
    """-> ordered events {tool, arg, result, ts_call, ts_result}."""
    uses = []   # (id, tool, arg, ts)
    results = {}  # id -> (text, ts)
    for line in open(path):
        d = json.loads(line)
        t = d.get("type")
        if t in ("system", "result"):
            continue
        if t == "assistant":
            for blk in d.get("message", {}).get("content", []):
                if blk.get("type") == "tool_use":
                    inp = blk.get("input", {})
                    arg = inp.get("command") or inp.get("file_path") or \
                        json.dumps(inp)[:200]
                    uses.append((blk["id"], blk["name"], arg, d.get("timestamp")))
        elif t == "user":
            for blk in d.get("message", {}).get("content", []) or []:
                if isinstance(blk, dict) and blk.get("type") == "tool_result":
                    c = blk.get("content")
                    if isinstance(c, list):
                        c = " ".join(x.get("text", "") for x in c
                                     if isinstance(x, dict))
                    results[blk.get("tool_use_id")] = (c or "", d.get("timestamp"))
        else:
            raise ValueError(f"{path}: unrecognized entry type {t!r}")
    return [{"tool": n, "arg": a, "ts_call": ts,
             "result": results.get(i, ("", None))[0],
             "ts_result": results.get(i, ("", None))[1]}
            for i, n, a, ts in uses]


def parse_codex(path):
    events = []
    seen = set()
    for line in open(path):
        d = json.loads(line)
        t = d.get("type")
        if t in ("thread.started", "turn.started", "turn.completed",
                 "turn.failed", "item.started", "error"):
            continue
        if t != "item.completed":
            raise ValueError(f"{path}: unrecognized event type {t!r}")
        item = d["item"]
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        it = item["type"]
        if it == "agent_message":
            continue
        if it == "command_execution":
            events.append({"tool": "Bash", "arg": item.get("command", ""),
                           "result": item.get("aggregated_output", ""),
                           "exit_code": item.get("exit_code"),
                           "ts_call": None, "ts_result": None})
        elif it == "file_change":
            paths = " ".join(c.get("path", "") for c in item.get("changes", []))
            events.append({"tool": "file_change", "arg": paths, "result": "",
                           "ts_call": None, "ts_result": None})
        else:
            raise ValueError(f"{path}: unrecognized item type {it!r}")
    return events


def parse_kimi(path):
    events = []
    by_id = {}
    for line in open(path):
        d = json.loads(line)
        role = d.get("role")
        if role in ("user", "system", "meta"):
            continue
        if role == "assistant":
            for tc in d.get("tool_calls") or []:
                fn = tc["function"]
                args = json.loads(fn["arguments"] or "{}")
                arg = args.get("command") or args.get("path") or \
                    args.get("file_path") or json.dumps(args)[:200]
                ev = {"tool": fn["name"], "arg": arg, "result": "",
                      "ts_call": None, "ts_result": None}
                events.append(ev)
                by_id[tc.get("id") or f"{fn['name']}_{len(events)-1}"] = ev
        elif role == "tool":
            tid = d.get("tool_call_id")
            if tid in by_id:
                by_id[tid]["result"] = d.get("content") or ""
            else:  # positional fallback: attach to earliest result-less event
                for ev in events:
                    if not ev["result"]:
                        ev["result"] = d.get("content") or ""
                        break
        else:
            raise ValueError(f"{path}: unrecognized role {role!r}")
    return events


PARSERS = {"claude-code": parse_claude, "codex": parse_codex,
           "kimi-code": parse_kimi}


def classify_checker_output(text):
    for fault, sig in FAULT_SIGS:
        if sig.search(text or ""):
            return fault
    if GREEN_RE.search(text or ""):
        return "green"
    if "config ok" in (text or ""):
        return "green-partial"
    return "other"


def analyze_run(harness, config, run, path):
    events = PARSERS[harness](path)
    rec = {"harness": harness, "config": config, "run": run,
           "path": os.path.relpath(path, ROOT),
           "n_events": len(events),
           "counts": dict(Counter(e["tool"] for e in events))}

    checkers = []
    surfaced = {}  # fault -> event index where its error first appeared
    for i, e in enumerate(events):
        if e["tool"] in ("Bash",) and is_checker_cmd(e["arg"]):
            cls = classify_checker_output(e["result"])
            checkers.append({"idx": i, "cmd": (e["arg"] or "")[:120],
                             "surfaced": cls,
                             "result_head": (e["result"] or "")[:200]})
            if cls.startswith("F") and cls not in surfaced:
                surfaced[cls] = i
    rec["checker_cycles"] = len(checkers)
    rec["checkers"] = checkers
    rec["fault_order"] = sorted(surfaced, key=surfaced.get)

    # fault-targeting events + proactive candidates
    targets = {}
    for i, e in enumerate(events):
        hay = e["arg"] or ""
        for fault, kind, rx in TARGET_RES:
            if e["tool"] in ("Edit", "Write", "file_change") and kind == "edit":
                if rx.search(hay) and not DELIVER_RE.search(hay):
                    targets.setdefault(fault, []).append(
                        {"idx": i, "kind": "edit", "ev": f"{e['tool']}: {hay[:100]}"})
            elif e["tool"] == "Bash" and kind in ("fix", "scan") and rx.search(hay):
                targets.setdefault(fault, []).append(
                    {"idx": i, "kind": kind, "ev": f"Bash: {hay[:120]}"})
            elif e["tool"] == "Read" and kind == "edit" and rx.search(hay):
                targets.setdefault(fault, []).append(
                    {"idx": i, "kind": "read", "ev": f"Read: {hay[:100]}"})
    rec["proactive_candidates"] = []
    for fault, evs in targets.items():
        first_t = min(evs, key=lambda x: x["idx"])
        seen_at = surfaced.get(fault)
        if seen_at is None or first_t["idx"] < seen_at:
            rec["proactive_candidates"].append(
                {"fault": fault, "first_target": first_t,
                 "error_seen_at": seen_at})

    # inter-event gaps (claude-code only)
    rec["gap_seconds"] = None
    if harness == "claude-code":
        gaps = 0.0
        ok = True
        for a, b in zip(events, events[1:]):
            t0, t1 = iso(a["ts_result"] or a["ts_call"]), iso(b["ts_call"])
            if not t0 or not t1:
                ok = False
                break
            gaps += max(0.0, (t1 - t0).total_seconds())
        rec["gap_seconds"] = round(gaps, 1) if ok else None

    rec["n_task_mgmt"] = sum(1 for e in events if e["tool"] in TASK_MGMT)
    first_repo = next((e for e in events if e["tool"] not in TASK_MGMT), None)
    rec["first_repo_event"] = first_repo and f"{first_repo['tool']}: {(first_repo['arg'] or '')[:100]}"
    rec["opens_with_checker"] = bool(
        first_repo and first_repo["tool"] == "Bash"
        and is_checker_cmd(first_repo["arg"]))

    # SOLUTION.md
    run_dir = os.path.dirname(path)
    sol_path = os.path.join(run_dir, "workspace", "SOLUTION.md")
    rec["solution_md"] = open(sol_path).read() if os.path.exists(sol_path) else None
    rec["solution_automap"] = {
        f: bool(rec["solution_md"] and rx.search(rec["solution_md"]))
        for f, rx in SOLUTION_KEYS.items()}

    # fix-file set from workspace.diff
    diff_path = os.path.join(run_dir, "workspace.diff")
    files, modes = set(), set()
    if os.path.exists(diff_path):
        for line in open(diff_path):
            m = re.match(r"diff --git a/(\S+) b/", line)
            if m and "SOLUTION.md" not in m.group(1) and "__pycache__" not in m.group(1):
                files.add(m.group(1))
            if re.match(r"(old|new) mode ", line):
                modes.add(line.strip())
    rec["fix_file_set"] = sorted(files)
    rec["mode_changes"] = sorted(modes)

    rec["timeline"] = [
        f"[{i}] {e['tool']}: {re.sub(chr(10), ' ; ', e['arg'] or '')[:110]}"
        + (f"  => {re.sub(chr(10), ' ; ', e['result'])[:110]}" if e["result"] else "")
        for i, e in enumerate(events)]
    return rec


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def main():
    adjud = {}
    adj_path = os.path.join(OUT_DIR, "adjudications.json")
    if os.path.exists(adj_path):
        adjud = json.load(open(adj_path))

    records = []
    for harness, bout, config, label in CELLS:
        base = os.path.join(ROOT, bout, "04-terminal", config)
        paths = sorted(glob.glob(os.path.join(base, "run-*", "transcript.jsonl")))
        if not paths:  # single-run anchor layout: transcript directly in config dir
            paths = sorted(glob.glob(os.path.join(base, "transcript.jsonl")))
        if not paths:
            raise SystemExit(f"no transcripts for {label}")
        for p in paths:
            run = p.split(os.sep)[-2]
            if run == config:
                run = "run-1"
            rec = analyze_run(harness, config, run, p)
            rec["label"] = label
            ws = os.path.join(os.path.dirname(p), "wall_seconds")
            rec["wall_seconds"] = float(open(ws).read().strip()) if os.path.exists(ws) else None
            records.append(rec)
    assert len(records) == 19, len(records)

    def cell(label):
        return [r for r in records if r["label"] == label]

    score = {}
    # H1: >= 15/19 runs pay the serial floor (checker cycles >= 5)
    h1n = sum(1 for r in records if r["checker_cycles"] >= 5)
    score["H1"] = {"hit": h1n >= 15,
                   "detail": f"{h1n}/19 runs ran the checker >=5 times (threshold 15); "
                             f"cycles: { {r['path'].split('/')[1]+'/'+r['config']+'/'+r['run']: r['checker_cycles'] for r in records} }"}
    # H2: proactive fix/scan in <= 3/19 runs (after adjudication)
    pro_runs = []
    for r in records:
        key = f"{r['config']}/{r['run']}"
        cands = r["proactive_candidates"]
        adj = adjud.get("proactive", {}).get(key)
        if adj is not None:
            if adj["proactive"]:
                pro_runs.append(key)
        elif cands:
            pro_runs.append(key + " [UNADJUDICATED]")
    score["H2"] = {"hit": len(pro_runs) <= 3,
                   "detail": f"proactive fix/scan in {len(pro_runs)}/19 runs (threshold <=3): {pro_runs or 'none'}"}
    # H3: harness sign
    sol_cc = median([r["wall_seconds"] for r in cell("Sol / Claude Code")])
    sol_cx = median([r["wall_seconds"] for r in cell("Sol / Codex")])
    kimi_cc = median([r["wall_seconds"] for r in cell("Kimi K3 / Claude Code")])
    kimi_kc = median([r["wall_seconds"] for r in cell("Kimi K3 / Kimi Code")])
    score["H3"] = {"hit": sol_cx <= 0.5 * sol_cc and kimi_kc >= 2.5 * kimi_cc,
                   "detail": f"Sol median wall: Codex {sol_cx:.0f}s vs CC {sol_cc:.0f}s "
                             f"(ratio {sol_cx/sol_cc:.2f}, need <=0.5); Kimi: Kimi Code {kimi_kc:.0f}s "
                             f"vs CC {kimi_cc:.0f}s (ratio {kimi_kc/kimi_cc:.2f}, need >=2.5)"}
    # H4: Kimi Code cycles >= 1.5x Kimi CC cycles
    kc_cyc = median([r["checker_cycles"] for r in cell("Kimi K3 / Kimi Code")])
    cc_cyc = median([r["checker_cycles"] for r in cell("Kimi K3 / Claude Code")])
    score["H4"] = {"hit": kc_cyc >= 1.5 * cc_cyc,
                   "detail": f"Kimi median checker cycles: Kimi Code {kc_cyc} vs CC {cc_cyc} "
                             f"(ratio {kc_cyc/cc_cyc:.2f}, need >=1.5)"}
    # H5: >= 16/19 SOLUTION.md accurate (adjudicated)
    acc, inacc = [], []
    for r in records:
        key = f"{r['config']}/{r['run']}"
        adj = adjud.get("solutions", {}).get(key)
        if adj is None:
            inacc.append(key + " [UNADJUDICATED]")
        elif adj["accurate"]:
            acc.append(key)
        else:
            inacc.append(key)
    score["H5"] = {"hit": len(acc) >= 16,
                   "detail": f"{len(acc)}/19 SOLUTION.md accurate (threshold 16); not accurate: {inacc or 'none'}"}
    # H6: >= 17/19 open with the checker
    h6n = sum(1 for r in records if r["opens_with_checker"])
    h6_not = [f"{r['config']}/{r['run']}: {r['first_repo_event']}"
              for r in records if not r["opens_with_checker"]]
    score["H6"] = {"hit": h6n >= 17,
                   "detail": f"{h6n}/19 first repo-touching call is the checker (threshold 17); exceptions: {h6_not or 'none'}"}
    # H7: fix-file set identical in 19/19
    expected = {"Makefile", "data/config.json", "scripts/run_checks.sh"}
    h7_bad = [f"{r['config']}/{r['run']}: {r['fix_file_set']}"
              for r in records if set(r["fix_file_set"]) != expected]
    score["H7"] = {"hit": not h7_bad,
                   "detail": f"fix-file set == {sorted(expected)} in {19 - len(h7_bad)}/19 runs; deviations: {h7_bad or 'none'}"}

    out = {"records": records, "scorecard": score,
           "adjudications_loaded": bool(adjud)}
    with open(os.path.join(OUT_DIR, "walkthrough.json"), "w") as f:
        json.dump(out, f, indent=1)

    hits = sum(1 for v in score.values() if v["hit"])
    lines = ["# 04-terminal walkthrough results", "",
             "Corpus: 19 runs, 7 configurations, 5 models, 3 harnesses. All 19 scored 4/4.",
             f"Scorecard: {hits}/7 hypotheses hit.", ""]
    for h in sorted(score):
        v = score[h]
        lines.append(f"- **{h}: {'HIT' if v['hit'] else 'MISS'}** — {v['detail']}")
    lines += ["", "## Per-configuration medians", "",
              "| configuration | wall s | checker cycles | tool events | task-mgmt | inter-event gap s |",
              "| --- | --- | --- | --- | --- | --- |"]
    for _, _, _, label in CELLS:
        rs = cell(label)
        gaps = [r["gap_seconds"] for r in rs if r["gap_seconds"] is not None]
        gap_s = f"{median(gaps):.0f}" if gaps else "n/a (no timestamps)"
        lines.append(
            f"| {label} (n={len(rs)}) "
            f"| {median([r['wall_seconds'] for r in rs]):.0f} "
            f"| {median([r['checker_cycles'] for r in rs]):.0f} "
            f"| {median([r['n_events'] for r in rs]):.0f} "
            f"| {median([r['n_task_mgmt'] for r in rs]):.0f} "
            f"| {gap_s} |")
    f5_runs = [r for r in records
               if any(c["surfaced"] == "F5-env-pytest-unplanted"
                      for c in r["checkers"])]
    lines += ["", "## The fifth fault nobody planted", "",
              "The task plants four faults. The Kimi Code driver's isolated "
              "HOME (auth isolation, bouts/2026-07-18-kimi-homegame/DESIGN.md) "
              "drops ~/.local from python3's user site-packages, so `python3 "
              "-m pytest` fails with `No module named pytest` in that harness "
              "only. Cost, from the driver's timestamped wire.jsonl (time "
              "from the first pytest-missing error to the first green pytest "
              "run; the four planted faults were already fixed when this "
              "error can first appear, since pytest is last in the make "
              "chain):", ""]
    for r in f5_runs:
        wire = os.path.join(ROOT, os.path.dirname(r["path"]), "wire.jsonl")
        ts0 = ts_n = ts_f5 = ts_green = None
        for line in open(wire):
            d = json.loads(line)
            t = d.get("time") or d.get("created_at")
            if t is None:
                continue
            t = int(t)
            ts0 = ts0 or t
            ts_n = t
            if ts_f5 is None and "No module named pytest" in line:
                ts_f5 = t
            elif ts_f5 is not None and ts_green is None and "3 passed" in line:
                ts_green = t
        seg = (ts_green - ts_f5) / 1000
        pre = (ts_f5 - ts0) / 1000
        wall = (ts_n - ts0) / 1000
        r["f5_segment_s"] = round(seg, 1)
        r["f5_first_error_at_s"] = round(pre, 1)
        lines.append(
            f"- {r['path']}: planted faults done by t+{pre:.0f}s; fifth-fault "
            f"segment {seg:.0f}s of {wall:.0f}s wall ({seg/wall:.0%}); also "
            f"explains this run's published peek-check warning "
            f"(site-packages paths contain /home/mwoolly).")
    if f5_runs:
        lines += ["",
                  "For comparison, the same model's full walls in Claude Code "
                  "on this task (all four planted faults, no fifth): "
                  + ", ".join(f"{r['wall_seconds']:.0f}s"
                              for r in cell("Kimi K3 / Claude Code")) + "."]
    lines += ["", "## Fault discovery order (per run)", ""]
    for r in records:
        lines.append(f"- {r['label']} {r['run']}: cycles={r['checker_cycles']}, "
                     f"order={[f.split('-')[0] for f in r['fault_order']]}, "
                     f"proactive_candidates={len(r['proactive_candidates'])}")
    with open(os.path.join(OUT_DIR, "walkthrough.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:34]))


if __name__ == "__main__":
    main()
