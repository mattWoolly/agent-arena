#!/usr/bin/env python3
"""Aggregate a bout directory into results.json + results.md.

Handles both run layouts:
  <bout>/<task>/<model>/metrics.json          single run (legacy)
  <bout>/<task>/<model>/run-N/metrics.json    repeated runs (run-bout.sh -r N)

With repeats, wall/cost/token columns report mean ±sd across runs and the
pass column reports k/N.
"""
import json
import statistics
import sys
from pathlib import Path


def collect(bout: Path) -> list[dict]:
    rows = []
    for task_dir in sorted(p for p in bout.iterdir() if p.is_dir()):
        for model_dir in sorted(p for p in task_dir.iterdir() if p.is_dir()):
            run_dirs = sorted(model_dir.glob("run-*")) or [model_dir]
            for rd in run_dirs:
                mpath = rd / "metrics.json"
                if not mpath.exists():
                    continue
                m = json.loads(mpath.read_text())
                m["task"] = task_dir.name
                m["run"] = rd.name if rd != model_dir else "run-1"
                rows.append(m)
    return rows


def mean_sd(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None
    mu = statistics.fmean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else None
    return mu, sd


def fmt(mu, sd, spec="{:.0f}"):
    if mu is None:
        return "—"
    s = spec.format(mu)
    if sd is not None:
        s += " ±" + spec.format(sd)
    return s


def main(bout_dir: str) -> None:
    bout = Path(bout_dir)
    rows = collect(bout)
    (bout / "results.json").write_text(json.dumps(rows, indent=2))

    models = sorted({r["model"] for r in rows})
    tasks = sorted({r["task"] for r in rows})

    lines = [f"# Bout results: {bout.name}", ""]
    lines.append("| task | model | pass | score | wall(s) | cost($) | turns | out-tok | cache-read-tok |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for t in tasks:
        for m in models:
            rs = [r for r in rows if r["task"] == t and r["model"] == m]
            if not rs:
                continue
            n = len(rs)
            passes = sum(1 for r in rs if r.get("grade_pass"))
            scores = sorted({r.get("score", "—") for r in rs})
            wall = mean_sd([r.get("wall_seconds") for r in rs])
            cost = mean_sd([r.get("total_cost_usd") for r in rs])
            turns = mean_sd([r.get("num_turns") for r in rs])
            otok = mean_sd([r.get("output_tokens") for r in rs])
            ctok = mean_sd([r.get("cache_read_tokens") for r in rs])
            lines.append(
                "| " + " | ".join([
                    t, m,
                    f"{passes}/{n}",
                    ", ".join(str(s) for s in scores),
                    fmt(*wall),
                    fmt(*cost, spec="{:.2f}"),
                    fmt(*turns, spec="{:.1f}") if n > 1 else fmt(*turns),
                    fmt(*otok),
                    fmt(*ctok),
                ]) + " |"
            )

    lines.append("")
    for m in models:
        rs = [r for r in rows if r["model"] == m]
        n_runs = len(rs)
        passes = sum(1 for r in rs if r.get("grade_pass"))
        # Per-pass-through totals: sum of per-task means, so repeats don't inflate them.
        cost_total = sum((mean_sd([r.get("total_cost_usd") for r in rs if r["task"] == t])[0] or 0) for t in tasks)
        wall_total = sum((mean_sd([r.get("wall_seconds") for r in rs if r["task"] == t])[0] or 0) for t in tasks)
        lines.append(
            f"- **{m}**: {passes}/{n_runs} runs passed; per pass-through of all tasks: "
            f"~${cost_total:.2f}, ~{wall_total:.0f}s wall"
        )

    suspect = [r for r in rows if r.get("peek_check", "clean") != "clean"]
    if suspect:
        lines.append("")
        lines.append("**⚠ peek-check warnings** (transcript referenced grader assets):")
        for r in suspect:
            lines.append(f"- {r['task']}/{r['model']}/{r['run']}: {r['peek_check']}")

    envs = sorted({
        (r.get("run_env", {}).get("cli_version", "?"), r.get("run_env", {}).get("effort", "?"),
         r.get("run_env", {}).get("setting_sources", "?"))
        for r in rows if r.get("run_env")
    })
    if envs:
        lines.append("")
        for cli, effort, sources in envs:
            lines.append(f"- env: `{cli}`, effort=`{effort}`, setting-sources=`{sources}`")

    (bout / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1])
