#!/usr/bin/env python3
"""Grade REPORT.md + summary.json against ground truth computed from the CSV."""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

TASK = Path(__file__).parent
FORBIDDEN = ["leverage", "delve", "robust", "seamless", "revolutionize"]
HEADINGS = ["## Overview", "## Top Products", "## Regional Performance", "## Recommendations"]


def truth():
    revenues = []
    by_product = defaultdict(float)
    by_region = defaultdict(float)
    with open(TASK / "fixture/data/sales.csv", newline="") as f:
        for row in csv.DictReader(f):
            rev = int(row["units"]) * float(row["unit_price"])
            revenues.append(rev)
            by_product[row["product"]] += rev
            by_region[row["region"]] += rev
    revenues.sort()
    n = len(revenues)
    median = revenues[n // 2] if n % 2 else (revenues[n // 2 - 1] + revenues[n // 2]) / 2
    return {
        "total_revenue": round(sum(revenues), 2),
        "orders": n,
        "median_order_value": round(median, 2),
        "top_product_by_revenue": max(by_product, key=by_product.get),
        "revenue_by_region": {r: round(v, 2) for r, v in by_region.items()},
    }


def main(workspace):
    ws = Path(workspace)
    t = truth()
    points, fails = 0, []

    report_path = ws / "REPORT.md"
    report = report_path.read_text() if report_path.exists() else ""
    if not report:
        fails.append("REPORT.md missing")

    # 1. Headings: exactly the four H2s, in order, no other headings.
    heads = [l.strip() for l in report.splitlines() if re.match(r"\s*#{1,6}\s", l)]
    if heads == HEADINGS:
        points += 1
    else:
        fails.append(f"headings wrong: {heads}")

    # 2. Word count <= 250.
    words = len(report.split())
    if 0 < words <= 250:
        points += 1
    else:
        fails.append(f"word count {words} (limit 250)")

    # 3. Overview states exact formatted total revenue and order count.
    expected_fmt = f"${t['total_revenue']:,.2f}"
    if expected_fmt in report and re.search(rf"\b{t['orders']}\b", report):
        points += 1
    else:
        fails.append(f"missing exact figures: need {expected_fmt} and {t['orders']} orders")

    # 4. Forbidden words absent.
    hit = [w for w in FORBIDDEN if re.search(rf"\b{w}\w*", report, re.I)]
    if not hit:
        points += 1
    else:
        fails.append(f"forbidden words used: {hit}")

    # 5. Recommendations: exactly 3 bullets, each <= 25 words.
    rec = report.split("## Recommendations", 1)[-1] if "## Recommendations" in report else ""
    bullets = [l for l in rec.splitlines() if l.strip().startswith("- ")]
    if len(bullets) == 3 and all(len(b.split()) <= 26 for b in bullets):  # 26: includes the "-"
        points += 1
    else:
        fails.append(f"recommendations bullets: {len(bullets)}, lengths {[len(b.split()) - 1 for b in bullets]}")

    # 6. summary.json exact keys, correct values.
    ok = False
    spath = ws / "summary.json"
    if spath.exists():
        try:
            s = json.loads(spath.read_text())
            same_keys = set(s.keys()) == set(t.keys())
            close = lambda a, b: abs(float(a) - float(b)) < 0.011
            ok = (
                same_keys
                and close(s["total_revenue"], t["total_revenue"])
                and int(s["orders"]) == t["orders"]
                and close(s["median_order_value"], t["median_order_value"])
                and s["top_product_by_revenue"] == t["top_product_by_revenue"]
                and set(s["revenue_by_region"]) == set(t["revenue_by_region"])
                and all(close(s["revenue_by_region"][r], t["revenue_by_region"][r]) for r in t["revenue_by_region"])
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            fails.append(f"summary.json unreadable: {e}")
    if ok:
        points += 1
    else:
        fails.append(f"summary.json wrong (truth: {json.dumps(t)})")

    for f in fails:
        print(f"FAIL: {f}")
    print(f"SCORE: {points}/6")
    return 0 if points == 6 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
