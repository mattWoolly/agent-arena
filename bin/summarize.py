#!/usr/bin/env python3
"""Aggregate a bout directory into results.json + results.md."""
import json
import sys
from pathlib import Path


def main(bout_dir: str) -> None:
    bout = Path(bout_dir)
    rows = []
    for task_dir in sorted(p for p in bout.iterdir() if p.is_dir()):
        for model_dir in sorted(p for p in task_dir.iterdir() if p.is_dir()):
            mpath = model_dir / "metrics.json"
            if not mpath.exists():
                continue
            m = json.loads(mpath.read_text())
            m["task"] = task_dir.name
            rows.append(m)

    (bout / "results.json").write_text(json.dumps(rows, indent=2))

    models = sorted({r["model"] for r in rows})
    tasks = sorted({r["task"] for r in rows})
    by = {(r["task"], r["model"]): r for r in rows}

    def fmt(r, key, spec="{}"):
        v = r.get(key)
        return spec.format(v) if v is not None else "—"

    lines = [f"# Bout results: {bout.name}", ""]
    header = "| task | " + " | ".join(
        f"{m} pass | {m} score | {m} wall(s) | {m} cost($) | {m} turns | {m} tools" for m in models
    ) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (1 + 6 * len(models)))
    for t in tasks:
        cells = [t]
        for m in models:
            r = by.get((t, m), {})
            cells += [
                "PASS" if r.get("grade_pass") else "fail",
                r.get("score", "—"),
                fmt(r, "wall_seconds", "{:.0f}"),
                fmt(r, "total_cost_usd", "{:.2f}"),
                fmt(r, "num_turns"),
                fmt(r, "tool_calls_total"),
            ]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")

    lines.append("")
    for m in models:
        rs = [r for r in rows if r["model"] == m]
        cost = sum(r.get("total_cost_usd") or 0 for r in rs)
        wall = sum(r.get("wall_seconds") or 0 for r in rs)
        passes = sum(1 for r in rs if r.get("grade_pass"))
        lines.append(f"- **{m}**: {passes}/{len(rs)} tasks passed, total cost ${cost:.2f}, total wall {wall:.0f}s")

    (bout / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1])
