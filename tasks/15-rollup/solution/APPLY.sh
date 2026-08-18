#!/usr/bin/env bash
# Reference solution: writes a correct Q-REPORT.md into $WS. Uses the
# line-items cost basis and flags the June stated-total discrepancy.
set -eu
python3 - "$WS" <<'PY'
import os, re, sys
ws = sys.argv[1]
order = {"may": 0, "jun": 1, "jul": 2}
months = []
for fn in sorted(os.listdir(f"{ws}/reports")):
    t = open(f"{ws}/reports/{fn}").read()
    num = lambda s: int(s.replace(",", ""))
    months.append({
        "key": re.search(r"2026-(\w{3})", fn).group(1),
        "rev": num(re.search(r"came in at \*\*€([\d,]+)", t).group(1)),
        "stated": num(re.search(r"Total costs: \*\*€([\d,]+)", t).group(1)),
        "lines": sum(num(x) for x in re.findall(r"^\| [a-z& ]+ \| ([\d,]+) \|", t, re.M)),
        "new": int(re.search(r"signed (\d+)", t).group(1)),
        "churn": int(re.search(r"churned (\d+)", t).group(1)),
        "op": int(re.search(r"(\d+) tickets opened", t).group(1)),
        "cl": int(re.search(r"(\d+) closed", t).group(1)),
    })
months.sort(key=lambda m: order[m["key"]])
qr = sum(m["rev"] for m in months)
qc = sum(m["lines"] for m in months)
net = qr - qc
adds = sum(m["new"] - m["churn"] for m in months)
p = lambda x: f"{x:.1f}"
mom6 = (months[1]["rev"] - months[0]["rev"]) / months[0]["rev"] * 100
mom7 = (months[2]["rev"] - months[1]["rev"]) / months[1]["rev"] * 100
close = sum(m["cl"] for m in months) / sum(m["op"] for m in months) * 100
jun = months[1]
open(f"{ws}/Q-REPORT.md", "w").write(f"""# Quarterly operations report — May–July 2026

## Summary

Revenue held above €389k every month and peaked in June; July gave some of
that back. Costs stayed controlled, margin landed at {p(net / qr * 100)}%, and
the customer base grew by {adds} net accounts over the quarter.

## Key figures

| Figure | Value |
|---|---|
| Quarterly revenue | €{qr:,} |
| Quarterly costs | €{qc:,} |
| Net | €{net:,} |
| Margin | {p(net / qr * 100)}% |
| Net customer adds | {adds} |
| Ticket close rate | {p(close)}% |
| June revenue growth | {p(mom6)}% |
| July revenue growth | {p(mom7)}% |

## Notes

The June report's stated cost total (€{jun['stated']:,}) does not match the
sum of its own cost lines (€{jun['lines']:,}) — a €{jun['lines'] - jun['stated']:,}
discrepancy. Quarterly costs above use the line-item sums; the June monthly
should be corrected at source.
""")
PY
