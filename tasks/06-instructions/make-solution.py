#!/usr/bin/env python3
"""Emit a reference REPORT.md + summary.json into a workspace (for grader self-test)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from grade import truth  # noqa: E402


def main(workspace):
    ws = Path(workspace)
    t = truth()
    regions = sorted(t["revenue_by_region"], key=t["revenue_by_region"].get, reverse=True)
    report = f"""## Overview

Total revenue was ${t['total_revenue']:,.2f} across {t['orders']} orders,
with a median order value of ${t['median_order_value']:,.2f}.

## Top Products

{t['top_product_by_revenue']} earned the most revenue of any product.

## Regional Performance

{regions[0]} led all regions; {regions[-1]} trailed.

## Recommendations

- Grow {t['top_product_by_revenue']} inventory ahead of next month.
- Investigate why {regions[-1]} trails other regions.
- Track median order value weekly to catch pricing drift.
"""
    (ws / "REPORT.md").write_text(report)
    (ws / "summary.json").write_text(json.dumps(t, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
