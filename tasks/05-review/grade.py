#!/usr/bin/env python3
"""Grade findings.md against plants.json: recall over 6 planted defects, plus precision."""
import json
import re
import sys
from pathlib import Path

TASK = Path(__file__).parent
LINE_RE = re.compile(r"^[-*]\s+`?([\w./-]+):(\d+)(?:-(\d+))?`?\s+(.*)$")


def main(workspace):
    ws = Path(workspace)
    plants = json.loads((TASK / "plants.json").read_text())
    fpath = ws / "findings.md"
    if not fpath.exists():
        print("FAIL: findings.md not created")
        print("SCORE: 0/6")
        return 1

    findings = []
    for raw in fpath.read_text().splitlines():
        m = LINE_RE.match(raw.strip())
        if m:
            lo = int(m.group(2))
            hi = int(m.group(3) or m.group(2))
            findings.append({"file": m.group(1), "lo": lo, "hi": hi, "desc": m.group(4), "raw": raw})

    matched_plants = set()
    matched_findings = set()
    for i, f in enumerate(findings):
        for p in plants:
            if not f["file"].endswith(p["file"]) and not p["file"].endswith(f["file"]):
                continue
            line_hit = f["lo"] <= p["lines"][1] + 3 and f["hi"] >= p["lines"][0] - 3
            pat_hit = any(re.search(pat, f["desc"], re.I) for pat in p["patterns"])
            if line_hit or pat_hit:
                matched_plants.add(p["id"])
                matched_findings.add(i)

    recall_n = len(matched_plants)
    fps = [f["raw"] for i, f in enumerate(findings) if i not in matched_findings]
    precision = (len(matched_findings) / len(findings)) if findings else 0.0

    for p in plants:
        print(f"{'FOUND ' if p['id'] in matched_plants else 'MISSED'} {p['id']}")
    print(f"findings lines parsed: {len(findings)}; unmatched (potential FPs): {len(fps)}")
    for raw in fps:
        print(f"  FP? {raw}")
    print(f"precision: {precision:.2f}")
    print(f"SCORE: {recall_n}/6")
    return 0 if (recall_n >= 5 and precision >= 0.7) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
