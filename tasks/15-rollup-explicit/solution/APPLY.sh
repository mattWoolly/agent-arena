#!/usr/bin/env bash
# Reference solution: writes a correct RESULTS.json into $WS (line-items cost
# basis; discrepancy flagged in notes).
set -eu
python3 - "$WS" <<'PY'
import json, os, re, sys
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
r1 = lambda x: round(x, 1)
jun = months[1]
json.dump({
    "q_revenue_eur": qr,
    "q_costs_eur": qc,
    "q_net_eur": qr - qc,
    "margin_pct": r1((qr - qc) / qr * 100),
    "net_customer_adds": sum(m["new"] - m["churn"] for m in months),
    "ticket_close_rate_pct": r1(sum(m["cl"] for m in months)
                                / sum(m["op"] for m in months) * 100),
    "june_revenue_growth_pct": r1((months[1]["rev"] - months[0]["rev"])
                                  / months[0]["rev"] * 100),
    "july_revenue_growth_pct": r1((months[2]["rev"] - months[1]["rev"])
                                  / months[1]["rev"] * 100),
    "notes": (f"June stated cost total (EUR {jun['stated']:,}) does not match "
              f"the sum of its own cost lines (EUR {jun['lines']:,}); "
              f"line-item basis used for quarterly costs."),
}, open(f"{ws}/RESULTS.json", "w"), indent=2)
PY
