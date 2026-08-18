#!/usr/bin/env bash
# Reference solution: writes a correct RESULTS.json into $WS.
set -eu
python3 - "$WS" <<'PY'
import csv, json, sys
from decimal import Decimal, ROUND_HALF_UP
ws = sys.argv[1]
cents = lambda x: Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
rates = {r["currency"]: Decimal(r["eur_per_unit"])
         for r in csv.DictReader(open(f"{ws}/rates.csv"))}
budgets = {}
for line in open(f"{ws}/budget.yaml"):
    parts = line.strip().rstrip(":").split(": ")
    if len(parts) == 2 and parts[1].isdigit():
        budgets[parts[0]] = Decimal(parts[1])
cat, mon, conv = {}, {}, []
for row in csv.DictReader(open(f"{ws}/transactions.csv")):
    e = cents(Decimal(row["amount"]) * rates[row["currency"]])
    cat[row["category"]] = cat.get(row["category"], Decimal(0)) + e
    m = int(row["date"][5:7])
    mon[m] = mon.get(m, Decimal(0)) + e
    conv.append(e)
q2 = sum(conv)
p1 = lambda x: float(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
json.dump({
    "category_totals_eur": {c: float(cat[c]) for c in sorted(cat)},
    "q2_total_eur": float(q2),
    "mom_may_pct": p1((mon[5] - mon[4]) / mon[4] * 100),
    "mom_jun_pct": p1((mon[6] - mon[5]) / mon[5] * 100),
    "largest_txn_eur": float(max(conv)),
    "mean_txn_eur": float(cents(q2 / len(conv))),
    "travel_share_pct": p1(cat["travel"] / q2 * 100),
    "over_budget": sorted(c for c in cat if cat[c] > budgets[c]),
}, open(f"{ws}/RESULTS.json", "w"), indent=2)
PY
