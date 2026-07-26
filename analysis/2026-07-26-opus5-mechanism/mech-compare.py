#!/usr/bin/env python3
"""Quantitative behavioral comparison of claude-opus-5 vs claude-opus-4-8 from transcripts."""
import json, glob, os, re, statistics
from collections import defaultdict, Counter

ROOT = "/home/mwoolly/projects/agent-arena"
TASKS = ["01-bugfix","02-synthesis","03-refactor","04-terminal","05-review",
         "05-review-transplant","06-instructions","06-instructions-transplant"]

CORPORA = {
    "opus5":        dict(base=f"{ROOT}/bouts/2026-07-25-opus5-succession", model="claude-opus-5", cli="2.1.214"),
    "opus48_kimi":  dict(base=f"{ROOT}/bouts/2026-07-16-kimi3-vs-opus48-vs-fable5", model="claude-opus-4-8", cli="2.1.212"),
    "opus48_anchor":dict(base=f"{ROOT}/bouts/2026-07-25-opus5-anchors", model="claude-opus-4-8", cli="2.1.214"),
}

# --- proactivity: known files per task ---
BASE_OF = {"05-review-transplant":"05-review","06-instructions-transplant":"06-instructions"}
OUTPUTS = {  # explicitly mentioned deliverables
    "01-bugfix":{"SOLUTION.md"}, "02-synthesis":set(), "03-refactor":set(),
    "04-terminal":{"SOLUTION.md"}, "05-review":{"findings.md"}, "05-review-transplant":{"findings.md"},
    "06-instructions":{"REPORT.md","summary.json"}, "06-instructions-transplant":{"REPORT.md","summary.json"},
}
def fixture_basenames(task):
    src = BASE_OF.get(task, task)
    d = f"{ROOT}/tasks/{src}/fixture"
    out=set()
    for f in glob.glob(d+"/**/*", recursive=True):
        if os.path.isfile(f):
            out.add(os.path.basename(f))
    return out
def prompt_text(task):
    p=f"{ROOT}/tasks/{task}/PROMPT.md"
    return open(p).read() if os.path.exists(p) else ""
KNOWN={}; PROMPT={}
for t in TASKS:
    KNOWN[t]=fixture_basenames(t)|OUTPUTS[t]
    PROMPT[t]=prompt_text(t)

TEST_RE = re.compile(r'pytest|make test|make\b|npm test')  # a test invocation (see caveat)
BATCH_RE = re.compile(r'&&|;')
ERR_RE = re.compile(r'Traceback \(most recent call last\)|command not found|No such file|=+ FAILED|=+ ERRORS?|\b\d+ failed\b|Exit code: [1-9]|non-?zero exit|ModuleNotFoundError|SyntaxError|make: \*\*\*', re.I)

def result_text(block):
    c = block.get("content")
    if isinstance(c, str): return c
    if isinstance(c, list):
        return "\n".join(str(x.get("text","")) for x in c if isinstance(x,dict))
    return str(c)

def is_error_result(block):
    if block.get("is_error"): return True
    return bool(ERR_RE.search(result_text(block)))

def analyze_run(path):
    """Return per-run metrics from one transcript.jsonl."""
    events=[json.loads(l) for l in open(path) if l.strip()]
    # ordered stream of (kind, payload) for tool_use and tool_result
    tool_calls=[]      # list of dict(name, input)
    thinking=0; textchars=0; asst_msgs=0
    for e in events:
        if e.get("type")=="assistant":
            asst_msgs+=1
            for b in e["message"]["content"]:
                bt=b.get("type")
                if bt=="thinking": thinking+=1
                elif bt=="text": textchars+=len(b.get("text",""))
                elif bt=="tool_use":
                    tool_calls.append({"name":b.get("name"),"input":b.get("input",{}) or {}})
    # results in order (user events)
    results=[]
    for e in events:
        if e.get("type")=="user":
            c=e["message"].get("content")
            if isinstance(c,list):
                for b in c:
                    if isinstance(b,dict) and b.get("type")=="tool_result":
                        results.append(b)
    # map result i-th to tool_call i-th (they're paired in order)
    ntools=len(tool_calls)
    # Bash
    bash_cmds=[tc["input"].get("command","") for tc in tool_calls if tc["name"]=="Bash"]
    bash_lens=[len(c) for c in bash_cmds]
    batched=sum(1 for c in bash_cmds if BATCH_RE.search(c))
    # re-reads
    seen=set(); rereads=0
    for tc in tool_calls:
        if tc["name"]=="Read":
            fp=tc["input"].get("file_path")
            if fp in seen: rereads+=1
            elif fp is not None: seen.add(fp)
    # first move
    first_tool = tool_calls[0]["name"] if tool_calls else None
    first_bash_cat=None
    if first_tool=="Bash":
        cmd=tool_calls[0]["input"].get("command","").strip()
        head=cmd.split()[0] if cmd.split() else ""
        if head=="ls": first_bash_cat="ls"
        elif head in ("cat","head","tail"): first_bash_cat="cat"
        elif TEST_RE.search(cmd): first_bash_cat="test-run"
        else: first_bash_cat="other"
    # test cadence: first Bash test-run position (fraction of tool calls)
    first_test_pos=None
    for i,tc in enumerate(tool_calls):
        if tc["name"]=="Bash" and TEST_RE.search(tc["input"].get("command","")):
            first_test_pos = i/ntools if ntools else None
            break
    # last tool call is a test invocation?
    last_is_test=False
    if tool_calls:
        lt=tool_calls[-1]
        if lt["name"]=="Bash" and TEST_RE.search(lt["input"].get("command","")):
            last_is_test=True
    # error recovery
    nerr=0; recov_lengths=[]
    # build parallel arrays: index -> (name, cmd, err)
    for i,res in enumerate(results):
        if i>=ntools: break
        err=is_error_result(res)
        if err: nerr+=1
    # recovery length: from each failed result index to next passing test run index
    def is_test_call(i):
        return i<ntools and tool_calls[i]["name"]=="Bash" and TEST_RE.search(tool_calls[i]["input"].get("command",""))
    for i,res in enumerate(results):
        if i>=ntools: break
        if not is_error_result(res): continue
        # find next passing test run after i
        for j in range(i+1, min(ntools,len(results))):
            if is_test_call(j) and not is_error_result(results[j]):
                recov_lengths.append(j-i)
                break
    # proactivity: Write/Edit to files not in KNOWN and not pre-existing
    task = None
    proactive=[]
    return dict(
        asst_msgs=asst_msgs, thinking=thinking, textchars=textchars, ntools=ntools,
        bash_lens=bash_lens, n_bash=len(bash_cmds), batched=batched,
        rereads=rereads, any_reread=int(rereads>0),
        first_tool=first_tool, first_bash_cat=first_bash_cat,
        first_test_pos=first_test_pos, last_is_test=int(last_is_test),
        nerr=nerr, recov_lengths=recov_lengths,
        tool_calls=[(tc["name"], tc["input"].get("file_path"), tc["input"].get("command","")) for tc in tool_calls],
    )

def proactivity_scan(task, run_tool_calls):
    known=KNOWN[task]; ptext=PROMPT[task]
    flagged=[]
    for name,fp,cmd in run_tool_calls:
        if name in ("Write","Edit") and fp:
            bn=os.path.basename(fp)
            if bn in known: continue
            if bn in ptext: continue
            flagged.append(fp)
    return flagged

def mean(xs):
    xs=[x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None

# ---- collect ----
out={"corpora_meta":{k:{"cli":v["cli"],"model":v["model"]} for k,v in CORPORA.items()}, "per_corpus":{}, "per_task":{}, "cli_drift":{}, "proactivity":[]}

corpus_runs=defaultdict(list)  # corpus -> list of (task, run_metrics)
for cname,cfg in CORPORA.items():
    for t in TASKS:
        for rp in sorted(glob.glob(f"{cfg['base']}/{t}/{cfg['model']}/run-*/transcript.jsonl")):
            m=analyze_run(rp)
            corpus_runs[cname].append((t,rp,m))
            flg=proactivity_scan(t, m["tool_calls"])
            if flg:
                out["proactivity"].append({"corpus":cname,"task":t,"run":os.path.basename(os.path.dirname(rp)),
                                            "files":flg})

def agg(runs):
    """runs: list of metric dicts."""
    n=len(runs)
    all_bash_lens=[l for r in runs for l in r["bash_lens"]]
    total_bash=sum(r["n_bash"] for r in runs)
    total_batched=sum(r["batched"] for r in runs)
    all_recov=[l for r in runs for l in r["recov_lengths"]]
    first_tool_dist=Counter(r["first_tool"] for r in runs)
    first_bash_cat=Counter(r["first_bash_cat"] for r in runs if r["first_bash_cat"])
    return {
        "n_runs": n,
        "thinking_per_asst_msg": round(sum(r["thinking"] for r in runs)/sum(r["asst_msgs"] for r in runs),4) if sum(r["asst_msgs"] for r in runs) else None,
        "thinking_per_tool_call": round(sum(r["thinking"] for r in runs)/sum(r["ntools"] for r in runs),4) if sum(r["ntools"] for r in runs) else None,
        "thinking_blocks_per_run": round(mean([r["thinking"] for r in runs]),3),
        "tool_calls_per_run": round(mean([r["ntools"] for r in runs]),3),
        "mean_bash_cmd_len": round(mean(all_bash_lens),2) if all_bash_lens else None,
        "frac_bash_batched": round(total_batched/total_bash,4) if total_bash else None,
        "bash_calls_per_run": round(mean([r["n_bash"] for r in runs]),3),
        "frac_runs_with_reread": round(mean([r["any_reread"] for r in runs]),4),
        "total_rereads": sum(r["rereads"] for r in runs),
        "rereads_per_run": round(mean([r["rereads"] for r in runs]),3),
        "first_tool_dist": dict(first_tool_dist),
        "first_bash_cat_dist": dict(first_bash_cat),
        "mean_first_test_pos": round(mean([r["first_test_pos"] for r in runs]),4) if any(r["first_test_pos"] is not None for r in runs) else None,
        "n_runs_with_test": sum(1 for r in runs if r["first_test_pos"] is not None),
        "verify_before_finish_rate": round(mean([r["last_is_test"] for r in runs]),4),
        "errors_per_run": round(mean([r["nerr"] for r in runs]),3),
        "total_errors": sum(r["nerr"] for r in runs),
        "mean_recovery_len": round(mean(all_recov),3) if all_recov else None,
        "n_recovery_events": len(all_recov),
        "text_chars_per_run": round(mean([r["textchars"] for r in runs]),1),
        "text_chars_per_tool_call": round(sum(r["textchars"] for r in runs)/sum(r["ntools"] for r in runs),2) if sum(r["ntools"] for r in runs) else None,
    }

for cname in CORPORA:
    runs=[m for (_,_,m) in corpus_runs[cname]]
    out["per_corpus"][cname]=agg(runs)

# per-task (opus5 vs opus48_kimi over all 8 tasks; discriminating view)
for t in TASKS:
    out["per_task"][t]={}
    for cname in ("opus5","opus48_kimi"):
        runs=[m for (tt,_,m) in corpus_runs[cname] if tt==t]
        if runs: out["per_task"][t][cname]=agg(runs)

# CLI drift: opus48_kimi(2.1.212) vs opus48_anchor(2.1.214) on shared 3 tasks; plus opus5 vs opus48_anchor (same CLI)
SHARED=["01-bugfix","04-terminal","06-instructions"]
def subset(cname, tasks):
    return [m for (t,_,m) in corpus_runs[cname] if t in tasks]
out["cli_drift"]={
    "shared_tasks":SHARED,
    "opus48_kimi_2.1.212":agg(subset("opus48_kimi",SHARED)),
    "opus48_anchor_2.1.214":agg(subset("opus48_anchor",SHARED)),
    "opus5_2.1.214":agg(subset("opus5",SHARED)),
}

with open("/home/mwoolly/.claude/jobs/c8d24d67/tmp/mech-compare.json","w") as f:
    json.dump(out,f,indent=2)
print(json.dumps(out,indent=2))
